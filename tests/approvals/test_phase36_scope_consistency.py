from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.service import create_coupon_grant_draft
from src.approvals.repository import ApprovalRepository
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    compute_action_payload_hash,
    persist_action_safety_snapshot,
)
from src.approvals.snapshots import (
    build_action_safety_snapshot,
    snapshot_hash_projection,
)
from src.db.models import ActionDraft, AgentRun
from src.db.models import ActionSafetySnapshot as ActionSafetySnapshotRow
from src.db.models import ApprovalAssignment, ApprovalLevel, ApprovalRequest
from tests.approvals.test_service_transitions import (
    _create_command,
    _create_run,
    _decision_command,
    _evidence_ref,
    _phase34_binding_overrides,
)


def _hashable_binding_payload(value: dict) -> dict:
    normalized = dict(value)
    business_fact_ref = dict(normalized["business_fact_ref"])
    for key in ("data_freshness_at", "retrieved_at"):
        if isinstance(business_fact_ref.get(key), str) and business_fact_ref[key].endswith("Z"):
            parsed = datetime.fromisoformat(business_fact_ref[key].replace("Z", "+00:00"))
            business_fact_ref[key] = parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"
    normalized["business_fact_ref"] = business_fact_ref
    return normalized


def _hashable_business_fact_refs(values: list[dict]) -> list[dict]:
    normalized_refs = []
    for value in values:
        normalized = dict(value)
        for key in ("data_freshness_at", "retrieved_at"):
            if isinstance(normalized.get(key), str) and normalized[key].endswith("Z"):
                parsed = datetime.fromisoformat(normalized[key].replace("Z", "+00:00"))
                normalized[key] = parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"
        normalized_refs.append(normalized)
    return normalized_refs


async def _mark_run_business_merchant(
    session: AsyncSession,
    run_id,
    binding: dict,
    *,
    merchant_id: str | None = None,
) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = merchant_id or binding["target_merchant_id"]
    run.target_merchant_ref = binding["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    return run


async def _assert_no_approval_requests_persist(session: AsyncSession, run_id) -> None:
    rows = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id))).scalars().all()
    assert rows == [], "ApprovalRequest should not persist when scope validation fails"


async def _assert_no_drafts(session: AsyncSession, run_id) -> None:
    rows = (await session.execute(select(ActionDraft).where(ActionDraft.run_id == run_id))).scalars().all()
    assert rows == []


def _action_tool_kwargs(request: ApprovalRequest, **overrides) -> dict[str, object]:
    payload = {
        "approval_request_id": str(request.id),
        "action_payload_hash": request.action_payload_hash,
        "safety_snapshot_ref": request.safety_snapshot_ref,
        "safety_snapshot_hash": request.safety_snapshot_hash,
        "target_merchant_id": request.target_merchant_id,
        "target_merchant_ref": request.target_merchant_ref,
        "business_fact_refs": request.business_fact_refs,
        "verified_evidence_refs": request.verified_evidence_refs,
        "claim_verification_ref": request.claim_verification_ref,
        "claim_verification_summary": request.claim_verification_summary,
        "risk_decision_ref": request.risk_decision_ref,
        "risk_decision": request.risk_decision,
    }
    payload.update(overrides)
    return payload


async def _approved_business_merchant_request(
    session: AsyncSession,
    seeded_session,
    *,
    merchant_id: str = "merchant-1",
) -> ApprovalRequest:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id, merchant_id=merchant_id)
    await _mark_run_business_merchant(session, run_id, binding)
    created = await ApprovalService(session).create_request(
        _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **binding)
    )
    request = await session.get(ApprovalRequest, created.approval_id)
    assert request is not None
    level = (
        await session.execute(select(ApprovalLevel).where(ApprovalLevel.approval_request_id == request.id))
    ).scalar_one()
    assignment = (
        await session.execute(select(ApprovalAssignment).where(ApprovalAssignment.approval_level_id == level.id))
    ).scalar_one()
    await ApprovalService(session).decide(
        _decision_command(request, level, assignment, actor_id=seeded_session["users"]["admin_user"].id)
    )
    await session.refresh(request)
    return request


def test_action_safety_snapshot_contract_accepts_target_merchant_proof() -> None:
    tenant_id = "11111111-1111-1111-1111-111111111111"
    run_id = "22222222-2222-2222-2222-222222222222"
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)

    snapshot = build_action_safety_snapshot(
        tenant_id=tenant_id,
        run_id=run_id,
        snapshot_id="snapshot-1",
        snapshot_ref="snapshot:snapshot-1",
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v1",
        evidence=[_evidence_ref(tenant_id=tenant_id)],
        action_payload_hash="sha256:" + "1" * 64,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        created_at=datetime(2026, 6, 30, 0, 0, tzinfo=UTC),
    )

    assert snapshot.target_merchant_id == "merchant-1"
    assert snapshot.target_merchant_ref.model_dump(mode="json") == binding["target_merchant_ref"]
    assert [ref.model_dump(mode="json") for ref in snapshot.business_fact_refs] == binding["business_fact_refs"]


def test_snapshot_hash_projection_includes_target_merchant_binding_material() -> None:
    tenant_id = "11111111-1111-1111-1111-111111111111"
    run_id = "22222222-2222-2222-2222-222222222222"
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    snapshot = build_action_safety_snapshot(
        tenant_id=tenant_id,
        run_id=run_id,
        snapshot_id="snapshot-1",
        snapshot_ref="snapshot:snapshot-1",
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v1",
        evidence=[_evidence_ref(tenant_id=tenant_id)],
        action_payload_hash="sha256:" + "1" * 64,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        created_at=datetime(2026, 6, 30, 0, 0, tzinfo=UTC),
    )

    projection = snapshot_hash_projection(snapshot)

    assert projection["target_merchant_id"] == "merchant-1"
    assert projection["target_merchant_ref"] == _hashable_binding_payload(binding["target_merchant_ref"])
    assert projection["business_fact_refs"] == _hashable_business_fact_refs(binding["business_fact_refs"])


def test_action_safety_snapshot_row_declares_target_merchant_columns_and_index() -> None:
    columns = ActionSafetySnapshotRow.__table__.c
    index_names = {index.name for index in ActionSafetySnapshotRow.__table__.indexes}

    assert "target_merchant_id" in columns
    assert "target_merchant_ref" in columns
    assert "business_fact_refs" in columns
    assert "ix_action_safety_snapshots_tenant_target_merchant" in index_names


@pytest.mark.asyncio
async def test_persist_action_safety_snapshot_stores_and_reloads_target_merchant_proof(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    command = _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **binding)
    action_payload_hash = compute_action_payload_hash(command.proposed_action)

    persisted = await persist_action_safety_snapshot(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        proposed_action=command.proposed_action,
        action_payload_hash=action_payload_hash,
        policy_config_version=command.policy_config_version,
        risk_config_version=command.risk_config_version,
        retrieval_config_version=command.retrieval_config_version,
        evidence_refs=command.evidence_refs,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        created_at=command.created_at,
        created_by=requested_by,
    )

    row = (
        await session.execute(select(ActionSafetySnapshotRow).where(ActionSafetySnapshotRow.run_id == run_id))
    ).scalar_one()
    assert row.target_merchant_id == binding["target_merchant_id"]
    assert row.target_merchant_ref == binding["target_merchant_ref"]
    assert row.business_fact_refs == binding["business_fact_refs"]

    reloaded = await ApprovalRepository(session).get_snapshot_by_ref_or_hash(
        tenant_id=tenant_id,
        safety_snapshot_ref=persisted.safety_snapshot_ref,
        safety_snapshot_hash=persisted.safety_snapshot_hash,
    )
    assert reloaded is not None
    assert reloaded.target_merchant_id == binding["target_merchant_id"]
    assert reloaded.target_merchant_ref == binding["target_merchant_ref"]
    assert reloaded.business_fact_refs == binding["business_fact_refs"]


@pytest.mark.asyncio
async def test_persist_action_safety_snapshot_rejects_action_bound_snapshot_without_target_binding(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    command = _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **binding)

    with pytest.raises(ActionSafetySnapshotPersistenceError, match="target merchant binding"):
        await persist_action_safety_snapshot(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            proposed_action=command.proposed_action,
            action_payload_hash=compute_action_payload_hash(command.proposed_action),
            policy_config_version=command.policy_config_version,
            risk_config_version=command.risk_config_version,
            retrieval_config_version=command.retrieval_config_version,
            evidence_refs=command.evidence_refs,
            created_at=command.created_at,
            created_by=requested_by,
        )

    assert (
        await session.execute(select(ActionSafetySnapshotRow).where(ActionSafetySnapshotRow.run_id == run_id))
    ).scalars().all() == []


@pytest.mark.asyncio
async def test_approval_create_rejects_business_merchant_run_target_mismatch_without_persist(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    run_binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id, merchant_id="merchant-1")
    command_binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id, merchant_id="merchant-other")
    await _mark_run_business_merchant(session, run_id, run_binding)

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).create_request(
            _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **command_binding)
        )

    assert exc.value.code == "approval_scope_mismatch"
    await _assert_no_approval_requests_persist(session, run_id)


@pytest.mark.asyncio
async def test_approval_create_rejects_business_merchant_run_missing_target_without_persist(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    run_binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    await _mark_run_business_merchant(session, run_id, run_binding)

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).create_request(
            _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by)
        )

    assert exc.value.code == "approval_scope_mismatch"
    await _assert_no_approval_requests_persist(session, run_id)


@pytest.mark.asyncio
async def test_approval_create_rejects_unknown_legacy_run_with_business_target_without_persist(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).create_request(
            _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=requested_by, **binding)
        )

    assert exc.value.code == "approval_scope_mismatch"
    await _assert_no_approval_requests_persist(session, run_id)


@pytest.mark.asyncio
async def test_approval_create_allows_exact_business_merchant_run_binding(
    session: AsyncSession,
    seeded_session,
) -> None:
    request = await _approved_business_merchant_request(session, seeded_session)

    assert request.target_merchant_id == "merchant-1"
    assert request.status == "approved"


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_rejects_run_scope_binding_mismatch(
    session: AsyncSession,
    seeded_session,
) -> None:
    request = await _approved_business_merchant_request(session, seeded_session)
    run = await session.get(AgentRun, request.run_id)
    assert run is not None
    run.target_merchant_id = "merchant-other"
    await session.flush()

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(seeded_session["users"]["cs_zhang"].id),
        run_id=str(request.run_id),
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload=dict(request.proposed_action),
        session=session,
        **_action_tool_kwargs(request),
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "RUN_SCOPE_BINDING_MISMATCH"
    await _assert_no_drafts(session, request.run_id)


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_rejects_snapshot_binding_mismatch(
    session: AsyncSession,
    seeded_session,
) -> None:
    request = await _approved_business_merchant_request(session, seeded_session)
    snapshot = (
        await session.execute(
            select(ActionSafetySnapshotRow).where(
                ActionSafetySnapshotRow.tenant_id == request.tenant_id,
                ActionSafetySnapshotRow.snapshot_ref == request.safety_snapshot_ref,
                ActionSafetySnapshotRow.immutable_hash == request.safety_snapshot_hash,
            )
        )
    ).scalar_one()
    snapshot.target_merchant_id = "merchant-other"
    await session.flush()

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(seeded_session["users"]["cs_zhang"].id),
        run_id=str(request.run_id),
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload=dict(request.proposed_action),
        session=session,
        **_action_tool_kwargs(request),
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "SNAPSHOT_BINDING_MISMATCH"
    await _assert_no_drafts(session, request.run_id)
