from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1
from src.actions.service import create_coupon_grant_draft
from src.approvals.service import ApprovalService
from src.approvals.schemas import RiskDecisionV1, TargetMerchantBindingV1
from src.approvals.snapshot_service import compute_action_payload_hash, persist_action_safety_snapshot
from src.db.models import ActionDraft, AgentRun, ApprovalAssignment, ApprovalLevel, ApprovalRequest
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1
from tests.approvals.test_service_transitions import (
    _create_command,
    _create_run,
    _decision_command,
    _phase34_binding_overrides,
)


def _business_fact_ref() -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id="tenant-1",
        source_system="moca_demo",
        resource_type="refund_case",
        resource_id="RF-1001",
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 29, 0, 0, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 29, 0, 1, tzinfo=UTC),
    )


def _evidence_ref() -> EvidenceRefV1:
    return EvidenceRefV1(
        tenant_id="tenant-1",
        evidence_id="refund-policy/chunk-001@v3",
        doc_key="refund-policy",
        chunk_id="chunk-001",
        policy_version="v3",
        text_hash="sha256:" + "a" * 64,
        retrieved_at="2026-06-29T00:00:00.000Z",
        retrieval_config_version="retrieval.v1",
        rank=1,
    )


def _risk_decision() -> RiskDecisionV1:
    return RiskDecisionV1(
        tenant_id="tenant-1",
        run_id="run-1",
        action_id="act-1",
        action_payload_hash="sha256:" + "b" * 64,
        risk_level="high",
        reason_codes=["coupon_amount"],
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        approval_required=True,
        evaluated_at="2026-06-29T00:02:00.000Z",
    )


def _target_merchant_ref() -> TargetMerchantBindingV1:
    return TargetMerchantBindingV1(
        target_merchant_id="merchant-1",
        source="business_fact_ref",
        business_fact_ref=_business_fact_ref().model_dump(mode="json"),
    )


def _draft_payload() -> dict[str, object]:
    risk_decision = _risk_decision()
    return {
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "draft_id": "draft-1",
        "proposed_action": {
            "schema_version": "proposed_action.v1",
            "action_id": "act-1",
            "action_type": "issue_coupon",
            "target_id": "RF-1001",
        },
        "action_payload_hash": risk_decision.action_payload_hash,
        "approval_ref": "approval_request/approval-1",
        "approval_revision_ref": "approval_request/approval-1@rev1",
        "safety_snapshot_ref": "action_safety_snapshot/snap-1",
        "safety_snapshot_hash": "sha256:" + "c" * 64,
        "target_id": "RF-1001",
        "target_merchant_id": "merchant-1",
        "target_merchant_ref": _target_merchant_ref().model_dump(mode="json"),
        "business_fact_refs": [_business_fact_ref().model_dump(mode="json")],
        "verified_evidence_refs": [_evidence_ref().model_dump(mode="json")],
        "claim_verification_ref": "claim_verification_bundle/bundle-1",
        "claim_verification_summary": {"overall_status": "verified", "safe_support_ref_count": 1},
        "risk_decision_ref": "risk_decision/run-1/act-1",
        "risk_decision": risk_decision.model_dump(mode="json"),
        "auto_allowed_binding_ref": None,
        "idempotency_key": "tenant-1:run-1:rev1:issue_coupon:RF-1001:sha256-bbbb",
        "status": "draft_created",
        "execution_mode": "demo",
        "draft_outcome": DraftOutcomeV1().model_dump(mode="json"),
    }


def test_action_draft_v2_data_rejects_unknown_phase34_fields():
    payload = _draft_payload()
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_exposes_phase34_binding_refs():
    draft = ActionDraftV2Data.model_validate(_draft_payload())

    assert draft.target_merchant_id == "merchant-1"
    assert draft.target_merchant_ref == _target_merchant_ref()
    assert draft.business_fact_refs == [_business_fact_ref()]
    assert draft.verified_evidence_refs == [_evidence_ref()]
    assert draft.claim_verification_summary == {"overall_status": "verified", "safe_support_ref_count": 1}
    assert draft.risk_decision == _risk_decision()
    assert draft.risk_decision_ref == "risk_decision/run-1/act-1"


def test_action_draft_v2_data_rejects_unvalidated_business_fact_dicts():
    payload = _draft_payload()
    payload["business_fact_refs"] = [{"resource_type": "refund_case", "resource_id": "RF-1001"}]

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_rejects_unvalidated_risk_decision_dicts():
    payload = _draft_payload()
    risk_decision = dict(payload["risk_decision"])
    risk_decision["schema_version"] = "risk_decision.v999"
    payload["risk_decision"] = risk_decision

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


async def _approved_phase34_request(session: AsyncSession, seeded_session) -> ApprovalRequest:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = binding["target_merchant_id"]
    run.target_merchant_ref = binding["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    created = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            **binding,
        )
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
        _decision_command(
            request,
            level,
            assignment,
            actor_id=seeded_session["users"]["admin_user"].id,
        )
    )
    await session.refresh(request)
    return request


def _phase34_tool_kwargs(request: ApprovalRequest, **overrides) -> dict[str, object]:
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


async def _assert_no_drafts(session: AsyncSession, run_id: UUID) -> None:
    rows = (await session.execute(select(ActionDraft).where(ActionDraft.run_id == run_id))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_rejects_phase34_approval_binding_mismatch(
    session: AsyncSession,
    seeded_session,
):
    request = await _approved_phase34_request(session, seeded_session)
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload=dict(request.proposed_action),
        session=session,
        **_phase34_tool_kwargs(request, verified_evidence_refs=[]),
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "APPROVAL_BINDING_MISMATCH"
    await _assert_no_drafts(session, request.run_id)


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_persists_phase34_binding_projection(
    session: AsyncSession,
    seeded_session,
):
    request = await _approved_phase34_request(session, seeded_session)
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload=dict(request.proposed_action),
        session=session,
        **_phase34_tool_kwargs(request),
    )

    assert result["status"] == "success"
    draft = await session.get(ActionDraft, UUID(result["data"]["draft_id"]))
    assert draft is not None
    assert draft.target_merchant_id == request.target_merchant_id
    assert draft.target_merchant_ref == request.target_merchant_ref
    assert draft.business_fact_refs == request.business_fact_refs
    assert draft.verified_evidence_refs == request.verified_evidence_refs
    assert draft.claim_verification_ref == request.claim_verification_ref
    assert draft.claim_verification_summary == request.claim_verification_summary
    assert draft.risk_decision_ref == request.risk_decision_ref
    assert draft.risk_decision == request.risk_decision
    action_draft = ActionDraftV2Data.model_validate(result["data"]["action_draft"])
    assert action_draft.target_merchant_id == request.target_merchant_id
    assert [ref.model_dump(mode="json") for ref in action_draft.business_fact_refs] == request.business_fact_refs
    assert [ref.model_dump(mode="json") for ref in action_draft.verified_evidence_refs] == request.verified_evidence_refs
    assert action_draft.risk_decision_ref == request.risk_decision_ref
    assert action_draft.risk_decision.model_dump(mode="json") == request.risk_decision


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_accepts_exact_auto_allowed_binding(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = binding["target_merchant_id"]
    run.target_merchant_ref = binding["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    command = _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=user_id, **binding)
    action_payload_hash = compute_action_payload_hash(command.proposed_action)
    snapshot = await persist_action_safety_snapshot(
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
        created_by=user_id,
    )
    auto_allowed_binding = {
        "schema_version": "auto_allowed_action_binding.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "target_merchant_id": binding["target_merchant_id"],
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": snapshot.safety_snapshot_ref,
        "safety_snapshot_hash": snapshot.safety_snapshot_hash,
        "risk_decision_ref": binding["risk_decision_ref"],
        "idempotency_key": f"auto:{tenant_id}:{run_id}",
        "business_fact_refs": binding["business_fact_refs"],
        "verified_evidence_refs": binding["verified_evidence_refs"],
        "claim_verification_ref": binding["claim_verification_ref"],
        "claim_verification_summary": binding["claim_verification_summary"],
    }

    result = await create_coupon_grant_draft(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        run_id=str(run_id),
        approval_request_id=None,
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload=dict(command.proposed_action),
        session=session,
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=snapshot.safety_snapshot_ref,
        safety_snapshot_hash=snapshot.safety_snapshot_hash,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        verified_evidence_refs=binding["verified_evidence_refs"],
        claim_verification_ref=binding["claim_verification_ref"],
        claim_verification_summary=binding["claim_verification_summary"],
        risk_decision_ref=binding["risk_decision_ref"],
        risk_decision=binding["risk_decision"],
        auto_allowed_binding=auto_allowed_binding,
    )

    assert result["status"] == "success"
    draft = await session.get(ActionDraft, UUID(result["data"]["draft_id"]))
    assert draft is not None
    assert draft.approval_request_id is None
    assert draft.approval_revision_ref == f"auto_allowed:{binding['risk_decision_ref']}"
    assert draft.auto_allowed_binding_ref == f"auto_allowed:{binding['risk_decision_ref']}"
    assert len(draft.idempotency_key) <= 256
    assert draft.idempotency_key.startswith(f"{tenant_id}:{run_id}:auto_allowed_sha256:")
    assert "key_sha256:" in draft.idempotency_key


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_rejects_auto_allowed_binding_mismatch(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id)
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id)
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = binding["target_merchant_id"]
    run.target_merchant_ref = binding["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    command = _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=user_id, **binding)
    action_payload_hash = compute_action_payload_hash(command.proposed_action)
    snapshot = await persist_action_safety_snapshot(
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
        created_by=user_id,
    )
    auto_allowed_binding = {
        "schema_version": "auto_allowed_action_binding.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "target_merchant_id": "merchant-other",
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": snapshot.safety_snapshot_ref,
        "safety_snapshot_hash": snapshot.safety_snapshot_hash,
        "risk_decision_ref": binding["risk_decision_ref"],
        "idempotency_key": f"auto:{tenant_id}:{run_id}",
        "business_fact_refs": binding["business_fact_refs"],
        "verified_evidence_refs": binding["verified_evidence_refs"],
    }

    result = await create_coupon_grant_draft(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        run_id=str(run_id),
        approval_request_id=None,
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload=dict(command.proposed_action),
        session=session,
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=snapshot.safety_snapshot_ref,
        safety_snapshot_hash=snapshot.safety_snapshot_hash,
        target_merchant_id=binding["target_merchant_id"],
        target_merchant_ref=binding["target_merchant_ref"],
        business_fact_refs=binding["business_fact_refs"],
        verified_evidence_refs=binding["verified_evidence_refs"],
        claim_verification_ref=binding["claim_verification_ref"],
        claim_verification_summary=binding["claim_verification_summary"],
        risk_decision_ref=binding["risk_decision_ref"],
        risk_decision=binding["risk_decision"],
        auto_allowed_binding=auto_allowed_binding,
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "AUTO_ALLOWED_BINDING_MISMATCH"
    await _assert_no_drafts(session, run_id)
