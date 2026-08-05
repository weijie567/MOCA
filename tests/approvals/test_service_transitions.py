from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agent.trace import write_agent_run
from src.approvals.schemas import ApprovalDecisionCommand, ApprovalRequestCreateCommand
from src.approvals.repository import ApprovalRepository
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.approvals.snapshot_service import compute_action_payload_hash
from src.db.models import (
    AgentRun,
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
)
from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection
from src.knowledge.text_hash import evidence_text_hash
from src.repositories.evidence_version_repo import EvidenceVersionRepository


PROPOSED_ACTION_HASH = "sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094"


async def _create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    thread_id: str = "approval-service-thread",
) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=thread_id,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="approval service test",
        final_status="interrupted",
        final_response=None,
        started_at=now,
        completed_at=now,
        total_latency_ms=10,
    )
    return run_id


def _evidence_ref(
    *,
    tenant_id: UUID,
    evidence_id: str = "refund-policy/chunk-001@v3",
    chunk_id: str = "chunk-001",
    text_hash: str = "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    rank: int = 1,
    retrieval_config_version: str = "retrieval.v1",
) -> dict[str, Any]:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": str(tenant_id),
        "evidence_id": evidence_id,
        "doc_key": "refund-policy",
        "chunk_id": chunk_id,
        "policy_version": "v3",
        "text_hash": text_hash,
        "retrieved_at": "2026-06-15T00:00:00.000Z",
        "retrieval_config_version": retrieval_config_version,
        "rank": rank,
    }


def _business_fact_ref(*, tenant_id: UUID, resource_id: str = "RF-APPROVAL-1") -> dict[str, Any]:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": str(tenant_id),
        "source_system": "moca_demo",
        "resource_type": "refund_case",
        "resource_id": resource_id,
        "resource_version": "v1",
        "data_freshness_at": "2026-06-15T00:00:00Z",
        "retrieved_at": "2026-06-15T00:01:00Z",
    }


def _target_merchant_ref(*, tenant_id: UUID, merchant_id: str = "merchant-1") -> dict[str, Any]:
    return {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": merchant_id,
        "source": "business_fact_ref",
        "business_fact_ref": _business_fact_ref(tenant_id=tenant_id),
    }


def _risk_decision_payload(*, tenant_id: UUID, run_id: UUID, action_payload_hash: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "risk_decision.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "action_id": "act-approval-service",
        "action_payload_hash": action_payload_hash or PROPOSED_ACTION_HASH,
        "risk_level": "high",
        "reason_codes": ["manual_review", "policy_threshold"],
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "approval_required": True,
        "evaluated_at": "2026-06-15T00:02:00.000Z",
        "risk_rule_ref": "risk:manual-review",
        "risk_reason": "Manual review required.",
    }


def _phase34_binding_overrides(
    *,
    tenant_id: UUID,
    run_id: UUID,
    merchant_id: str = "merchant-1",
    evidence_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_ref = evidence_ref or _evidence_ref(tenant_id=tenant_id)
    evidence_projection = canonical_evidence_projection([EvidenceRefV1.model_validate(evidence_ref)])
    action_payload_hash = compute_action_payload_hash(
        _proposed_action(tenant_id=tenant_id, run_id=run_id, evidence_refs=evidence_projection)
    )
    return {
        "target_merchant_id": merchant_id,
        "target_merchant_ref": _target_merchant_ref(tenant_id=tenant_id, merchant_id=merchant_id),
        "business_fact_refs": [_business_fact_ref(tenant_id=tenant_id)],
        "verified_evidence_refs": evidence_projection,
        "claim_verification_ref": "claim_verification_bundle:bundle-1",
        "claim_verification_summary": {"overall_status": "verified", "safe_support_ref_count": 1},
        "risk_decision_ref": f"risk_decision:{run_id}:{action_payload_hash}",
        "risk_decision": _risk_decision_payload(
            tenant_id=tenant_id,
            run_id=run_id,
            action_payload_hash=action_payload_hash,
        ),
        "approval_idempotency_key": f"approval:{tenant_id}:{run_id}:act-approval-service",
        "evidence_refs": evidence_projection,
    }


async def _seed_canonical_approval_evidence(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    suffix: str,
) -> dict[str, Any]:
    doc_key = f"approval-policy-{suffix}"[:64]
    chunk_id = f"chunk-{suffix}"[:64]
    content = f"Canonical approval fixture {suffix}."
    document = PolicyDocument(
        tenant_id=tenant_id,
        doc_key=doc_key,
        doc_type="refund_rule",
        title=f"Approval fixture {suffix}",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        version=1,
        content=content,
        source_type="phase64_2_test",
    )
    session.add(document)
    await session.flush()
    document_version = PolicyDocumentVersion(
        tenant_id=tenant_id,
        policy_document_id=document.id,
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        doc_key=doc_key,
        document_version=1,
        content=content,
        content_hash=evidence_text_hash(content),
        source_locator_json={"source_type": "phase64_2_test"},
        lifecycle_status="active",
        retention_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(document_version)
    await session.flush()
    chunk_version = PolicyChunkVersion(
        tenant_id=tenant_id,
        policy_document_version_id=document_version.id,
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        doc_key=doc_key,
        document_version=1,
        chunk_id=chunk_id,
        chunk_version=1,
        content=content,
        text_hash=evidence_text_hash(content),
        source_locator_json={"source_type": "phase64_2_test"},
        lifecycle_status="active",
        retention_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(chunk_version)
    await session.flush()
    repository = EvidenceVersionRepository(session)
    resolution = await repository.mint_for_chunk_version(
        chunk_version,
        expected_tenant_id=tenant_id,
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert resolution.identity is not None
    return canonical_evidence_projection(
        [
            repository.evidence_ref_from_identity(
                resolution.identity,
                retrieved_at="2026-06-15T00:00:00.000Z",
                retrieval_config_version="retrieval.v1",
                rank=1,
            )
        ]
    )[0]


async def _mark_run_business_scope(session: AsyncSession, run_id: UUID, binding: dict[str, Any]) -> None:
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = binding["target_merchant_id"]
    run.target_merchant_ref = binding["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()


def _canonical_evidence_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [EvidenceRefV1.model_validate(ref).model_dump(mode="json") for ref in refs]


def _proposed_action(*, tenant_id: UUID, run_id: UUID, evidence_refs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "proposed_action.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "action_id": "act-approval-service",
        "action_type": "issue_coupon",
        "target_type": "refund_case",
        "target_id": "RF-APPROVAL-1",
        "amount": "100.00",
        "currency": "CNY",
        "args": {"coupon_type": "cash"},
        "reason": "refund delay compensation",
        "evidence_refs": evidence_refs,
    }


def _create_command(
    *,
    tenant_id: UUID,
    run_id: UUID,
    requested_by: UUID,
    thread_id: str = "approval-service-thread",
    risk_level: str = "high",
    risk_rule_ref: str | None = "risk:manual-review",
    expires_at: datetime | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> ApprovalRequestCreateCommand:
    refs = evidence_refs or [_evidence_ref(tenant_id=tenant_id)]
    payload = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "thread_id": thread_id,
        "requested_by": requested_by,
        "proposed_action": _proposed_action(tenant_id=tenant_id, run_id=run_id, evidence_refs=refs),
        "action_payload_hash": None,
        "approval_policy_id": "manual-review",
        "policy_version": "policy.v1",
        "risk_level": risk_level,
        "risk_rule_ref": risk_rule_ref,
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "retrieval_config_version": "retrieval.v1",
        "evidence_refs": refs,
        "created_at": datetime(2026, 6, 15, 0, 0, 0, tzinfo=UTC),
        "expires_at": expires_at or datetime.now(UTC) + timedelta(hours=1),
    }
    payload.update(overrides)
    return ApprovalRequestCreateCommand.model_validate(payload)


async def _approval_bundle(
    session: AsyncSession,
    seeded_session,
    *,
    requested_by_key: str = "cs_zhang",
    thread_id: str = "approval-service-thread",
    expires_at: datetime | None = None,
    risk_rule_ref: str | None = "risk:manual-review",
    command_overrides: dict[str, Any] | None = None,
) -> tuple[ApprovalRequest, ApprovalLevel, ApprovalAssignment]:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"][requested_by_key].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by, thread_id=thread_id)
    evidence_ref = await _seed_canonical_approval_evidence(
        session,
        tenant_id=tenant_id,
        suffix=str(run_id),
    )
    binding_overrides = _phase34_binding_overrides(
        tenant_id=tenant_id,
        run_id=run_id,
        evidence_ref=evidence_ref,
    )
    await _mark_run_business_scope(session, run_id, binding_overrides)
    service = ApprovalService(session)

    created = await service.create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id=thread_id,
            expires_at=expires_at,
            risk_rule_ref=risk_rule_ref,
            **{**binding_overrides, **(command_overrides or {})},
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
    return request, level, assignment


def _decision_command(
    request: ApprovalRequest,
    level: ApprovalLevel,
    assignment: ApprovalAssignment,
    *,
    actor_id: UUID,
    actor_role: str = "admin",
    decision_type: str = "accept",
    **overrides: Any,
) -> ApprovalDecisionCommand:
    payload = {
        "approval_id": request.id,
        "tenant_id": request.tenant_id,
        "run_id": request.run_id,
        "thread_id": request.thread_id,
        "level_id": level.id,
        "assignment_id": assignment.id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "decision_type": decision_type,
        "expected_request_version": request.version,
        "expected_level_version": level.version,
        "expected_assignment_version": assignment.version,
        "expected_revision": request.revision,
        "action_payload_hash": request.action_payload_hash,
        "safety_snapshot_hash": request.safety_snapshot_hash,
        "reason": "reviewed",
    }
    payload.update(overrides)
    return ApprovalDecisionCommand.model_validate(payload)


async def _counts(session: AsyncSession) -> tuple[int, int]:
    decisions = await session.scalar(select(func.count()).select_from(ApprovalDecision))
    events = await session.scalar(select(func.count()).select_from(ApprovalEvent))
    return int(decisions or 0), int(events or 0)


async def _assert_no_orphan_decision_or_event_rows(
    session: AsyncSession,
    before: tuple[int, int],
) -> None:
    assert await _counts(session) == before
    decision_ids = set((await session.execute(select(ApprovalDecision.id))).scalars())
    orphan_events = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_decision_id.is_not(None),
                ApprovalEvent.approval_decision_id.not_in(decision_ids),
            )
        )
    ).scalars()
    assert list(orphan_events) == []


async def _assert_transition_error(
    session: AsyncSession,
    command: ApprovalDecisionCommand,
    *,
    code: str | set[str],
) -> None:
    before = await _counts(session)
    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).decide(command)

    allowed_codes = {code} if isinstance(code, str) else code
    assert exc.value.code in allowed_codes
    await _assert_no_orphan_decision_or_event_rows(session, before)


@pytest.mark.asyncio
async def test_accept_decision_inserts_exactly_one_decision_and_event(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    result = await ApprovalService(session).decide(_decision_command(request, level, assignment, actor_id=actor_id))

    assert result.status == "approved"
    assert result.decision_type == "accept"
    assert result.revision == 1
    assert result.request_version == 2
    assert result.level_version == 2
    assert result.assignment_version == 2
    assert result.action_payload_hash == request.action_payload_hash
    assert result.safety_snapshot_hash == request.safety_snapshot_hash
    assert result.resume_payload is not None
    assert result.resume_payload["schema_version"] == "approval_result.v1"
    assert result.resume_payload["tenant_id"] == str(request.tenant_id)
    assert result.resume_payload["run_id"] == str(request.run_id)
    assert result.resume_payload["safety_snapshot_ref"] == request.safety_snapshot_ref
    assert result.resume_payload["decided_by"] == str(actor_id)
    assert result.graph_thread_id == f"{request.tenant_id}:{request.requested_by}:{request.thread_id}"

    decisions = (await session.execute(select(ApprovalDecision))).scalars().all()
    events = (
        (await session.execute(select(ApprovalEvent).where(ApprovalEvent.event_type == "approval_decided")))
        .scalars()
        .all()
    )
    assert len(decisions) == 1
    assert len(events) == 1

    decision = decisions[0]
    assert decision.tenant_id == request.tenant_id
    assert decision.run_id == request.run_id
    assert decision.thread_id == request.thread_id
    assert decision.request_revision == 1
    assert decision.request_version == 1
    assert decision.level_version == 1
    assert decision.assignment_version == 1

    event = events[0]
    assert event.approval_request_id == request.id
    assert event.approval_decision_id == decision.id
    assert event.tenant_id == request.tenant_id
    assert event.run_id == request.run_id
    assert event.thread_id == request.thread_id
    assert event.event_type == "approval_decided"


@pytest.mark.asyncio
async def test_create_request_persists_phase34_binding_fields(session: AsyncSession, seeded_session):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    evidence_ref = await _seed_canonical_approval_evidence(session, tenant_id=tenant_id, suffix=str(run_id))
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id, evidence_ref=evidence_ref)
    await _mark_run_business_scope(session, run_id, binding)

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
    assert request.target_merchant_id == "merchant-1"
    assert request.target_merchant_ref == binding["target_merchant_ref"]
    assert request.business_fact_refs == binding["business_fact_refs"]
    assert request.verified_evidence_refs == _canonical_evidence_refs(binding["verified_evidence_refs"])
    assert request.claim_verification_ref == "claim_verification_bundle:bundle-1"
    assert request.claim_verification_summary == {"overall_status": "verified", "safe_support_ref_count": 1}
    assert request.risk_decision_ref == binding["risk_decision_ref"]
    assert request.risk_decision == binding["risk_decision"]
    assert request.approval_idempotency_key == binding["approval_idempotency_key"]
    assert created.target_merchant_id == request.target_merchant_id
    assert [ref.model_dump(mode="json") for ref in created.business_fact_refs] == binding["business_fact_refs"]
    assert [ref.model_dump(mode="json") for ref in created.verified_evidence_refs] == _canonical_evidence_refs(
        binding["verified_evidence_refs"]
    )
    assert created.risk_decision_ref == binding["risk_decision_ref"]
    assert created.risk_decision.model_dump(mode="json") == binding["risk_decision"]
    assert created.approval_idempotency_key == binding["approval_idempotency_key"]


@pytest.mark.asyncio
async def test_accept_decision_returns_persisted_phase34_bindings_in_resume_payload(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    evidence_ref = await _seed_canonical_approval_evidence(session, tenant_id=tenant_id, suffix=str(run_id))
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id, evidence_ref=evidence_ref)
    await _mark_run_business_scope(session, run_id, binding)
    created = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id="phase34-binding-approval",
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
    actor_id = seeded_session["users"]["admin_user"].id

    result = await ApprovalService(session).decide(_decision_command(request, level, assignment, actor_id=actor_id))

    assert result.target_merchant_id == request.target_merchant_id
    assert result.target_merchant_ref.model_dump(mode="json") == request.target_merchant_ref
    assert [ref.model_dump(mode="json") for ref in result.business_fact_refs] == request.business_fact_refs
    assert [ref.model_dump(mode="json") for ref in result.verified_evidence_refs] == request.verified_evidence_refs
    assert result.claim_verification_ref == request.claim_verification_ref
    assert result.claim_verification_summary == request.claim_verification_summary
    assert result.risk_decision_ref == request.risk_decision_ref
    assert result.risk_decision.model_dump(mode="json") == request.risk_decision
    assert result.approval_idempotency_key == request.approval_idempotency_key
    assert result.resume_payload is not None
    assert result.resume_payload["target_merchant_id"] == request.target_merchant_id
    assert result.resume_payload["business_fact_refs"] == request.business_fact_refs
    assert result.resume_payload["verified_evidence_refs"] == request.verified_evidence_refs
    assert result.resume_payload["risk_decision_ref"] == request.risk_decision_ref
    assert result.resume_payload["risk_decision"] == request.risk_decision
    assert result.resume_payload["approval_idempotency_key"] == request.approval_idempotency_key


@pytest.mark.asyncio
async def test_edit_decision_reroutes_to_risk_without_approved_resume_authority(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by)
    evidence_ref = await _seed_canonical_approval_evidence(session, tenant_id=tenant_id, suffix=str(run_id))
    binding = _phase34_binding_overrides(tenant_id=tenant_id, run_id=run_id, evidence_ref=evidence_ref)
    await _mark_run_business_scope(session, run_id, binding)
    created = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id="phase34-edit-reroute",
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
    actor_id = seeded_session["users"]["admin_user"].id
    edited_action = {**request.proposed_action, "amount": "88.00", "reason": "Reviewer edited amount."}

    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type="edit",
            edited_action=edited_action,
        )
    )

    assert result.status == "superseded"
    assert result.resume_payload is not None
    assert result.resume_payload["status"] == "superseded"
    assert result.resume_payload["decision_type"] == "edit"
    assert result.resume_payload["resume_route"] == "risk_gate"
    assert result.resume_payload["new_action_payload_hash"]
    assert result.resume_payload["new_action_payload_hash"] != result.action_payload_hash
    assert result.superseded_by_request_id is None
    assert request.superseded_by_request_id is None
    approval_count = await session.scalar(
        select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.run_id == request.run_id)
    )
    assert approval_count == 1


@pytest.mark.asyncio
async def test_manager_service_decision_is_allowed_for_assigned_role(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id

    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            actor_role="manager",
        )
    )

    assert result.status == "approved"
    assert result.decision_type == "accept"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        (
            "stale_request_version",
            lambda command: command.model_copy(
                update={"expected_request_version": command.expected_request_version + 1}
            ),
        ),
        (
            "stale_level_version",
            lambda command: command.model_copy(update={"expected_level_version": command.expected_level_version + 1}),
        ),
        (
            "stale_assignment_version",
            lambda command: command.model_copy(
                update={"expected_assignment_version": command.expected_assignment_version + 1}
            ),
        ),
        (
            "stale_revision",
            lambda command: command.model_copy(update={"expected_revision": command.expected_revision + 1}),
        ),
    ],
)
async def test_stale_version_or_revision_returns_conflict_without_orphans(
    session: AsyncSession,
    seeded_session,
    name: str,
    mutate: Callable[[ApprovalDecisionCommand], ApprovalDecisionCommand],
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    command = mutate(_decision_command(request, level, assignment, actor_id=actor_id))

    assert name in {
        "stale_request_version",
        "stale_level_version",
        "stale_assignment_version",
        "stale_revision",
    }
    await _assert_transition_error(session, command, code="approval_conflict")


@pytest.mark.asyncio
async def test_expired_request_returns_conflict_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(
        session,
        seeded_session,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(request, level, assignment, actor_id=actor_id),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_wrong_tenant_returns_not_found_or_forbidden_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            tenant_id=seeded_session["other_tenant"].id,
        ),
        code={"approval_not_found", "approval_forbidden"},
    )


@pytest.mark.asyncio
async def test_wrong_run_returns_conflict_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(request, level, assignment, actor_id=actor_id, run_id=uuid4()),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_wrong_thread_returns_conflict_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            thread_id="wrong-thread-id",
        ),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_self_approval_returns_forbidden_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=request.requested_by,
        ),
        code="approval_forbidden",
    )


@pytest.mark.asyncio
async def test_wrong_assignment_level_binding_rolls_back_without_orphans(session: AsyncSession, seeded_session):
    request, level, _assignment = await _approval_bundle(session, seeded_session)
    _other_request, _other_level, other_assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-service-other-thread",
    )
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            other_assignment,
            actor_id=actor_id,
            expected_assignment_version=other_assignment.version,
        ),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_wrong_level_request_binding_rolls_back_without_orphans(session: AsyncSession, seeded_session):
    request, _level, _assignment = await _approval_bundle(session, seeded_session)
    _other_request, other_level, other_assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-service-other-thread",
    )
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            other_level,
            other_assignment,
            actor_id=actor_id,
            expected_level_version=other_level.version,
            expected_assignment_version=other_assignment.version,
        ),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_malformed_edit_action_returns_transition_error_without_orphans(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    malformed_action = {
        **request.proposed_action,
        "amount": 88.0,
    }

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type="edit",
            edited_action=malformed_action,
        ),
        code="approval_not_executable",
    )


@pytest.mark.asyncio
async def test_result_projection_validation_error_is_not_reported_as_non_executable(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    class BrokenProjection(BaseModel):
        value: int

    with pytest.raises(ValidationError) as validation_exc:
        BrokenProjection(value="not-an-int")

    class BrokenTrustedApprovalResultV1:
        def __init__(self, **_kwargs: Any) -> None:
            raise validation_exc.value

    monkeypatch.setattr("src.approvals.service.TrustedApprovalResultV1", BrokenTrustedApprovalResultV1)
    before = await _counts(session)

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).decide(_decision_command(request, level, assignment, actor_id=actor_id))

    await session.refresh(request)
    assert exc.value.code == "approval_invalid_result"
    assert request.status == "pending"
    assert request.reason is None
    await _assert_no_orphan_decision_or_event_rows(session, before)


def test_create_request_rejects_missing_risk_context_before_persistence(seeded_session):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id

    with pytest.raises(ValidationError):
        _create_command(
            tenant_id=tenant_id,
            run_id=uuid4(),
            requested_by=requested_by,
            risk_level=None,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_decision_context_matches_shared_fixture_shape(session: AsyncSession, seeded_session):
    request, _level, _assignment = await _approval_bundle(session, seeded_session)

    context = await ApprovalService(session).project_decision_context(request.id, request.tenant_id)
    fixture = json.loads(Path("contracts/fixtures/approval_decision_context_v1.json").read_text())

    assert context is not None
    assert set(context.model_dump(mode="json")) == set(fixture)
    assert context.approval_id == request.id
    assert context.allowed_decision_types == ["accept", "approve", "edit", "respond", "reject", "ignore"]


@pytest.mark.asyncio
async def test_decision_preflight_and_expiry_use_request_first_without_postgres_deadlock(
    test_engine,
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(
        session,
        seeded_session,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    actor_id = seeded_session["users"]["admin_user"].id
    command = _decision_command(request, level, assignment, actor_id=actor_id)
    await session.commit()

    preflight_done = asyncio.Event()
    expiry_request_locked = asyncio.Event()
    decision_request_attempted = asyncio.Event()
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    class DecisionRepository(ApprovalRepository):
        async def lock_request(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
            decision_request_attempted.set()
            return await super().lock_request(approval_id, tenant_id)

    class ExpiryRepository(ApprovalRepository):
        async def lock_request(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
            locked = await super().lock_request(approval_id, tenant_id)
            expiry_request_locked.set()
            await asyncio.wait_for(decision_request_attempted.wait(), timeout=2)
            return locked

    async def decide_worker() -> str:
        async with session_factory() as worker_session:
            service = ApprovalService(worker_session, repository=DecisionRepository(worker_session))
            context = await service.get_decision_context(request.id, request.tenant_id)
            assert context is not None
            preflight_done.set()
            await asyncio.wait_for(expiry_request_locked.wait(), timeout=2)
            try:
                await service.decide(command)
            except ApprovalTransitionError as exc:
                await worker_session.rollback()
                return exc.code
            await worker_session.commit()
            return "decided"

    async def expire_worker() -> str:
        await asyncio.wait_for(preflight_done.wait(), timeout=2)
        async with session_factory() as worker_session:
            service = ApprovalService(worker_session, repository=ExpiryRepository(worker_session))
            expired = await service.expire_due_request(
                request.id,
                request.tenant_id,
                now=datetime.now(UTC) + timedelta(hours=2),
            )
            await worker_session.commit()
            return "expired" if expired is not None else "not_expired"

    decision_result, expiry_result = await asyncio.wait_for(
        asyncio.gather(decide_worker(), expire_worker()),
        timeout=5,
    )

    assert decision_result == "approval_conflict"
    assert expiry_result == "expired"
    async with session_factory() as verify_session:
        persisted_request = await verify_session.get(ApprovalRequest, request.id)
        persisted_level = await verify_session.get(ApprovalLevel, level.id)
        persisted_assignment = await verify_session.get(ApprovalAssignment, assignment.id)
        decision_count = await verify_session.scalar(
            select(func.count()).select_from(ApprovalDecision).where(ApprovalDecision.approval_request_id == request.id)
        )
    assert persisted_request is not None and persisted_request.status == "expired"
    assert persisted_level is not None and persisted_level.status == "expired"
    assert persisted_assignment is not None and persisted_assignment.status == "expired"
    assert decision_count == 0
