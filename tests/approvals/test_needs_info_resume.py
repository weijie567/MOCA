from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.schemas import ApprovalDecisionCommand, ApprovalInfoCommand
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.db.models import ActionSafetySnapshot, AgentTraceEvent, ApprovalDecision, ApprovalEvent, ApprovalRequest
from tests.approvals.test_service_transitions import (
    _approval_bundle,
    _decision_command as _base_decision_command,
    _evidence_ref,
)


ACTIVE_REQUEST_STATUSES = {"pending", "needs_info"}


def _decision_command(*args, **kwargs):
    kwargs.setdefault("actor_role", "admin")
    return _base_decision_command(*args, **kwargs)


def _changed_action(request: ApprovalRequest, *, amount: str = "88.00") -> dict[str, Any]:
    return {
        **request.proposed_action,
        "amount": amount,
        "args": {**request.proposed_action.get("args", {}), "coupon_type": "service_recovery"},
        "reason": "manager edited compensation after clarification",
    }


def _changed_evidence(request: ApprovalRequest) -> list[dict[str, Any]]:
    return [
        _evidence_ref(
            tenant_id=request.tenant_id,
            evidence_id="refund-policy/chunk-002@v3",
            chunk_id="chunk-002",
            text_hash="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            rank=1,
        )
    ]


def _info_command(
    request: ApprovalRequest,
    *,
    actor_id: UUID,
    actor_role: str = "admin",
    clarification_request_id: str | None = None,
    info_payload: dict[str, Any] | None = None,
    **overrides: Any,
) -> ApprovalInfoCommand:
    payload = {
        "approval_id": request.id,
        "clarification_request_id": clarification_request_id or request.clarification_request_id,
        "tenant_id": request.tenant_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "thread_id": request.thread_id,
        "expected_request_version": request.version,
        "expected_level_version": 2,
        "expected_assignment_version": 2,
        "expected_revision": request.revision,
        "info_payload": info_payload or {"response_text": "customer confirmed the refund case details"},
    }
    payload.update(overrides)
    return ApprovalInfoCommand.model_validate(payload)


async def _respond(
    session: AsyncSession,
    request: ApprovalRequest,
    level,
    assignment,
    *,
    actor_id: UUID,
    response_text: str = "Please confirm the refund case and coupon amount.",
):
    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type="respond",
            response_text=response_text,
        )
    )
    await session.refresh(request)
    await session.refresh(level)
    await session.refresh(assignment)
    return result


async def _active_revision_count(session: AsyncSession, request: ApprovalRequest) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(ApprovalRequest)
        .where(
            ApprovalRequest.tenant_id == request.tenant_id,
            ApprovalRequest.run_id == request.run_id,
            ApprovalRequest.status.in_(ACTIVE_REQUEST_STATUSES),
            ApprovalRequest.legacy_non_executable.is_(False),
        )
    )
    return int(count or 0)


async def _active_revision(session: AsyncSession, request: ApprovalRequest) -> ApprovalRequest:
    rows = (
        (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.tenant_id == request.tenant_id,
                    ApprovalRequest.run_id == request.run_id,
                    ApprovalRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                    ApprovalRequest.legacy_non_executable.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    return rows[0]


async def _assert_old_revision_cannot_execute(
    session: AsyncSession,
    command: ApprovalDecisionCommand,
    *,
    code: str = "approval_conflict",
) -> None:
    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).decide(command)
    assert exc.value.code == code


@pytest.mark.asyncio
async def test_respond_writes_needs_info_and_no_resume_payload(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    result = await _respond(session, request, level, assignment, actor_id=actor_id)

    assert result.status == "needs_info"
    assert result.decision_type == "respond"
    assert result.resume_payload is None
    assert result.request_version == 2
    assert result.level_version == 2
    assert result.assignment_version == 2
    assert result.action_payload_hash == request.action_payload_hash
    assert result.safety_snapshot_hash == request.safety_snapshot_hash
    assert request.status == "needs_info"
    assert request.clarification_request_id

    decision = (await session.execute(select(ApprovalDecision))).scalar_one()
    lifecycle_events = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(
                    AgentTraceEvent.run_id == request.run_id,
                    AgentTraceEvent.event_type == "run_status_changed",
                )
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert decision.decision_type == "respond"
    assert decision.response_text == "Please confirm the refund case and coupon amount."
    assert decision.reason == "reviewed"
    assert [event.redacted_payload["status"] for event in lifecycle_events] == ["interrupted"]
    assert lifecycle_events[0].redacted_payload["reason_code"] == "needs_info_response"
    assert lifecycle_events[0].redacted_payload["clarification_ref"] == request.clarification_request_id
    assert all(event.redacted_payload["status"] != "completed" for event in lifecycle_events)


@pytest.mark.asyncio
async def test_respond_does_not_create_action_draft_or_approval_result(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    result = await _respond(session, request, level, assignment, actor_id=actor_id)

    assert result.resume_payload is None
    assert result.status == "needs_info"
    old_revision_cannot_execute = _decision_command(request, level, assignment, actor_id=actor_id)
    await _assert_old_revision_cannot_execute(session, old_revision_cannot_execute)


@pytest.mark.asyncio
async def test_attach_info_wrong_clarification_id_fails_closed(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).attach_info(
            _info_command(
                request,
                actor_id=actor_id,
                clarification_request_id=f"{request.clarification_request_id}-wrong",
            )
        )

    assert exc.value.code == "approval_conflict"
    assert await _active_revision_count(session, request) == 1


@pytest.mark.asyncio
async def test_attach_info_wrong_tenant_or_thread_fails_closed(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)

    for command in [
        _info_command(request, actor_id=actor_id, tenant_id=seeded_session["other_tenant"].id),
        _info_command(request, actor_id=actor_id, thread_id="wrong-thread"),
    ]:
        with pytest.raises(ApprovalTransitionError) as exc:
            await ApprovalService(session).attach_info(command)
        assert exc.value.code in {"approval_not_found", "approval_conflict"}

    assert await _active_revision_count(session, request) == 1


@pytest.mark.asyncio
async def test_attach_info_stale_request_level_assignment_versions_fail_closed(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)

    for overrides in [
        {"expected_request_version": request.version - 1},
        {"expected_level_version": level.version - 1},
        {"expected_assignment_version": assignment.version - 1},
        {"expected_revision": request.revision + 1},
    ]:
        with pytest.raises(ApprovalTransitionError) as exc:
            await ApprovalService(session).attach_info(_info_command(request, actor_id=actor_id, **overrides))
        assert exc.value.code == "approval_conflict"


@pytest.mark.asyncio
async def test_attach_info_changed_payload_supersedes_pending_rebind(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)
    old_action_payload_hash = request.action_payload_hash
    old_decision_command = _decision_command(request, level, assignment, actor_id=actor_id)

    result = await ApprovalService(session).attach_info(
        _info_command(
            request,
            actor_id=actor_id,
            info_payload={"response_text": "confirmed", "proposed_action": _changed_action(request)},
        )
    )
    await session.refresh(request)

    assert request.status == "superseded"
    assert request.superseded_by_request_id is None
    assert result.approval_id == request.id
    assert result.status == "superseded"
    assert result.superseded_by_request_id is None
    assert result.new_action_payload_hash
    assert old_action_payload_hash != result.new_action_payload_hash
    assert await _active_revision_count(session, request) == 0
    assert result.resume_payload is None
    await _assert_old_revision_cannot_execute(session, old_decision_command)


@pytest.mark.asyncio
async def test_attach_info_malformed_changed_payload_fails_closed_without_orphans(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)
    malformed_action = {**_changed_action(request), "amount": 88.0}
    before_decisions = await session.scalar(select(func.count()).select_from(ApprovalDecision))
    before_events = await session.scalar(select(func.count()).select_from(ApprovalEvent))

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).attach_info(
            _info_command(
                request,
                actor_id=actor_id,
                info_payload={"response_text": "confirmed", "proposed_action": malformed_action},
            )
        )

    await session.refresh(request)
    await session.refresh(level)
    await session.refresh(assignment)
    assert exc.value.code == "approval_not_executable"
    assert request.status == "needs_info"
    assert level.status == "pending"
    assert assignment.status == "pending"
    assert await session.scalar(select(func.count()).select_from(ApprovalDecision)) == before_decisions
    assert await session.scalar(select(func.count()).select_from(ApprovalEvent)) == before_events
    assert await _active_revision_count(session, request) == 1


@pytest.mark.asyncio
async def test_attach_info_changed_payload_records_pending_rebind_event(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)

    result = await ApprovalService(session).attach_info(
        _info_command(
            request,
            actor_id=actor_id,
            info_payload={"response_text": "confirmed", "proposed_action": _changed_action(request)},
        )
    )
    await session.refresh(request)

    event = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_request_id == request.id,
                ApprovalEvent.event_type == "approval_info_attached",
            )
        )
    ).scalar_one()

    assert result.approval_id == request.id
    assert event.metadata_json["changed_revision_material"] is True
    assert event.metadata_json["pending_rebind"] is True
    assert event.resource_refs_json["request_ref"] == f"approval_request:{request.id}:r{request.revision}"
    assert event.resource_refs_json["action_payload_hash"] == request.action_payload_hash
    assert event.resource_refs_json["new_action_payload_hash"] == result.new_action_payload_hash
    assert event.resource_refs_json["new_safety_snapshot_hash"]


@pytest.mark.asyncio
async def test_attach_info_changed_payload_leaves_no_unbound_active_revision(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)

    result = await ApprovalService(session).attach_info(
        _info_command(
            request,
            actor_id=actor_id,
            info_payload={"response_text": "confirmed", "proposed_action": _changed_action(request)},
        )
    )

    await session.refresh(request)

    assert result.approval_id == request.id
    assert result.status == "superseded"
    assert request.superseded_by_request_id is None
    assert await _active_revision_count(session, request) == 0
    request_count = await session.scalar(
        select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.run_id == request.run_id)
    )
    assert request_count == 1


@pytest.mark.asyncio
async def test_edit_generates_new_action_payload_hash_before_reroute(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    old_action_payload_hash = request.action_payload_hash

    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type="edit",
            edited_action=_changed_action(request, amount="77.00"),
        )
    )
    await session.refresh(request)
    assert result.decision_type == "edit"
    assert result.status == "superseded"
    assert result.superseded_by_request_id is None
    assert request.superseded_by_request_id is None
    assert result.new_action_payload_hash
    assert old_action_payload_hash != result.new_action_payload_hash
    assert result.resume_payload is not None
    assert result.resume_payload["decision_type"] == "edit"
    assert result.resume_payload["status"] == "superseded"
    assert result.resume_payload["new_action_payload_hash"] == result.new_action_payload_hash
    assert result.resume_payload["resume_route"] == "assess_risk_and_approval"


@pytest.mark.asyncio
async def test_attach_info_changed_evidence_or_config_requires_new_snapshot_hash(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, request, level, assignment, actor_id=actor_id)
    old_snapshot_hash = request.safety_snapshot_hash

    result = await ApprovalService(session).attach_info(
        _info_command(
            request,
            actor_id=actor_id,
            info_payload={
                "response_text": "confirmed with updated policy evidence",
                "evidence_refs": _changed_evidence(request),
                "retrieval_config_version": "retrieval.v2",
            },
        )
    )
    await session.refresh(request)
    event = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_request_id == request.id,
                ApprovalEvent.event_type == "approval_info_attached",
            )
        )
    ).scalar_one()
    new_safety_snapshot_hash = event.resource_refs_json["new_safety_snapshot_hash"]
    snapshot = (
        await session.execute(
            select(ActionSafetySnapshot).where(ActionSafetySnapshot.immutable_hash == new_safety_snapshot_hash)
        )
    ).scalar_one()

    assert request.status == "superseded"
    assert request.superseded_by_request_id is None
    assert result.approval_id == request.id
    assert result.status == "superseded"
    assert old_snapshot_hash != new_safety_snapshot_hash
    assert event.metadata_json["pending_rebind"] is True
    assert snapshot.retrieval_config_version == "retrieval.v2"


@pytest.mark.asyncio
async def test_attach_info_timeout_cancelled_old_revision_cannot_execute(session: AsyncSession, seeded_session):
    expired_request, expired_level, expired_assignment = await _approval_bundle(
        session,
        seeded_session,
        expires_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    actor_id = seeded_session["users"]["admin_user"].id
    await _respond(session, expired_request, expired_level, expired_assignment, actor_id=actor_id)
    expired_request.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.flush()

    with pytest.raises(ApprovalTransitionError) as expired_exc:
        await ApprovalService(session).attach_info(_info_command(expired_request, actor_id=actor_id))
    assert expired_exc.value.code == "approval_conflict"

    cancelled_request, cancelled_level, cancelled_assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="cancelled-needs-info",
    )
    await _respond(session, cancelled_request, cancelled_level, cancelled_assignment, actor_id=actor_id)
    cancelled_request.status = "cancelled"
    await session.flush()

    with pytest.raises(ApprovalTransitionError) as cancelled_exc:
        await ApprovalService(session).attach_info(_info_command(cancelled_request, actor_id=actor_id))
    assert cancelled_exc.value.code == "approval_conflict"

    old_revision_cannot_execute = _decision_command(
        expired_request,
        expired_level,
        expired_assignment,
        actor_id=actor_id,
    )
    await _assert_old_revision_cannot_execute(session, old_revision_cannot_execute)


@pytest.mark.asyncio
async def test_edit_supersedes_old_revision_and_reroutes_to_risk(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    old_decision_command = _decision_command(request, level, assignment, actor_id=actor_id)

    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type="edit",
            edited_action=_changed_action(request, amount="66.00"),
        )
    )
    await session.refresh(request)
    decision = (await session.execute(select(ApprovalDecision))).scalar_one()

    assert decision.decision_type == "edit"
    assert decision.edited_action_json == _changed_action(request, amount="66.00")
    assert request.status == "superseded"
    assert request.superseded_by_request_id is None
    assert result.superseded_by_request_id is None
    assert result.resume_payload is not None
    assert result.resume_payload["resume_route"] == "assess_risk_and_approval"
    assert await _active_revision_count(session, request) == 0
    await _assert_old_revision_cannot_execute(session, old_decision_command)
