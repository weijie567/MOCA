from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.approvals.schemas import ApprovalDecisionCommand, ApprovalRequestCreateCommand
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.db.models import (
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
)


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
) -> tuple[ApprovalRequest, ApprovalLevel, ApprovalAssignment]:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"][requested_by_key].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by, thread_id=thread_id)
    service = ApprovalService(session)

    created = await service.create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id=thread_id,
            expires_at=expires_at,
            risk_rule_ref=risk_rule_ref,
        )
    )

    request = await session.get(ApprovalRequest, created.approval_id)
    assert request is not None
    level = (
        await session.execute(
            select(ApprovalLevel).where(ApprovalLevel.approval_request_id == request.id)
        )
    ).scalar_one()
    assignment = (
        await session.execute(
            select(ApprovalAssignment).where(ApprovalAssignment.approval_level_id == level.id)
        )
    ).scalar_one()
    return request, level, assignment


def _decision_command(
    request: ApprovalRequest,
    level: ApprovalLevel,
    assignment: ApprovalAssignment,
    *,
    actor_id: UUID,
    actor_role: str = "manager",
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
    actor_id = seeded_session["users"]["approval_manager"].id

    result = await ApprovalService(session).decide(
        _decision_command(request, level, assignment, actor_id=actor_id)
    )

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
        await session.execute(select(ApprovalEvent).where(ApprovalEvent.event_type == "approval_decided"))
    ).scalars().all()
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
@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        (
            "stale_request_version",
            lambda command: command.model_copy(update={"expected_request_version": command.expected_request_version + 1}),
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
    actor_id = seeded_session["users"]["approval_manager"].id
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
    actor_id = seeded_session["users"]["approval_manager"].id

    await _assert_transition_error(
        session,
        _decision_command(request, level, assignment, actor_id=actor_id),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_wrong_tenant_returns_not_found_or_forbidden_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id

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
    actor_id = seeded_session["users"]["approval_manager"].id

    await _assert_transition_error(
        session,
        _decision_command(request, level, assignment, actor_id=actor_id, run_id=uuid4()),
        code="approval_conflict",
    )


@pytest.mark.asyncio
async def test_wrong_thread_returns_conflict_without_orphans(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id

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
            actor_role="manager",
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
    actor_id = seeded_session["users"]["approval_manager"].id

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
    actor_id = seeded_session["users"]["approval_manager"].id

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
    actor_id = seeded_session["users"]["approval_manager"].id
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
    actor_id = seeded_session["users"]["approval_manager"].id

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
        await ApprovalService(session).decide(
            _decision_command(request, level, assignment, actor_id=actor_id)
        )

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
