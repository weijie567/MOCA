from __future__ import annotations

from datetime import UTC, datetime
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun
from src.replay.lifecycle import RunLifecycleService
from src.replay.service import ReplayService


TERMINAL_STATUSES = {"completed", "rejected", "expired", "error", "cancelled"}


async def _create_run(
    session: AsyncSession,
    *,
    final_status: str,
    scenario: str,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    thread_id = f"phase35-{scenario}-{run_id}"
    now = datetime.now(UTC)
    session.add(
        AgentRun(
            id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=uuid.uuid4(),
            input_query=f"phase35 replay timeline {scenario}",
            final_status=final_status,
            final_response="safe final response" if final_status == "completed" else None,
            started_at=now,
            completed_at=now if final_status in TERMINAL_STATUSES else None,
            total_latency_ms=10,
        )
    )
    await session.flush()
    return run_id, tenant_id, thread_id


async def _append_approval_requested(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
    approval_id: str,
) -> None:
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="approval_requested",
        actor={"type": "system", "id": "approval_gate"},
        resource_refs={"approval_id": approval_id},
        redacted_payload={"status": "pending", "risk_level": "high"},
    )


async def _append_approval_decided(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
    approval_id: str,
    decision_type: str,
    approval_status: str,
    clarification_request_id: str | None = None,
) -> None:
    payload = {
        "decision_type": decision_type,
        "approval_status": approval_status,
        "reason_code": f"approval_{decision_type}",
    }
    if clarification_request_id is not None:
        payload["clarification_request_id"] = clarification_request_id
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="approval_decided",
        actor={"type": "approver", "id": "manager-1"},
        resource_refs={"approval_id": approval_id},
        redacted_payload=payload,
    )


async def _append_approval_resumed(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
    approval_id: str,
) -> None:
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="approval_resumed",
        actor={"type": "system", "id": "approval_gate"},
        resource_refs={"approval_id": approval_id},
        redacted_payload={"status": "resumed", "resume_source": "trusted_approval"},
    )


async def _append_approval_expired(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
    approval_id: str,
) -> None:
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="approval_expired",
        actor={"type": "system", "id": "approval_sla_scanner"},
        resource_refs={"approval_id": approval_id},
        redacted_payload={"status": "expired", "sla_due_at": "2026-06-29T00:00:00Z"},
        schema_version="minimal_event_envelope.v1",
    )


async def _append_action_draft_created(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
) -> None:
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="action_draft_created",
        actor={"type": "agent", "id": "moca"},
        resource_refs={
            "draft_id": str(uuid.uuid4()),
            "action_payload_hash": "sha256:" + "1" * 64,
            "safety_snapshot_hash": "sha256:" + "2" * 64,
        },
        redacted_payload={
            "action_type": "issue_coupon",
            "execution_mode": "demo",
            "external_side_effect": False,
            "draft_outcome": {"schema_version": "draft_outcome.v1", "status": "not_executed_demo"},
        },
    )


async def _append_node_error(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
) -> None:
    operation_id = uuid.uuid4()
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="node_started",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"node": "investigate"},
        redacted_payload={"status": "started"},
        operation_id=operation_id,
        attempt=1,
        node_name="investigate",
    )
    await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="node_failed",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"node": "investigate"},
        redacted_payload={"status": "failed", "error_code": "GRAPH_ERROR", "safe_message": "node failed safely"},
        error_json={"code": "GRAPH_ERROR", "message": "safe graph error", "retryable": False},
        operation_id=operation_id,
        attempt=1,
        node_name="investigate",
    )


def _assert_valid_timeline(replay: dict, *, final_status: str) -> None:
    timeline = replay["timeline"]
    assert timeline
    assert replay["schema_version"] == "replay_response.v3"
    assert replay["final_status"] == final_status
    assert [event["sequence"] for event in timeline] == list(range(1, len(timeline) + 1))
    assert {event["schema_version"] for event in timeline} == {"replay_event.v3"}


def _statuses(replay: dict) -> list[str]:
    return [
        event["redacted_payload"]["status"]
        for event in replay["timeline"]
        if event["event_type"] == "run_status_changed"
    ]


def _has_event_type(replay: dict, event_type: str) -> bool:
    return any(event["event_type"] == event_type for event in replay["timeline"])


def _has_event_with_payload(replay: dict, event_type: str, **expected: str) -> bool:
    return any(
        event["event_type"] == event_type
        and all(event["redacted_payload"].get(key) == value for key, value in expected.items())
        for event in replay["timeline"]
    )


def _sequence_for(replay: dict, event_type: str, **payload: str) -> int:
    for event in replay["timeline"]:
        if event["event_type"] == event_type and all(
            event["redacted_payload"].get(key) == value for key, value in payload.items()
        ):
            return int(event["sequence"])
    raise AssertionError(f"missing event {event_type} with {payload}")


@pytest.mark.asyncio
async def test_normal_completed_timeline_has_running_completed_statuses(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session, final_status="completed", scenario="normal_completed")
    lifecycle = RunLifecycleService(session)

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await lifecycle.mark_completed(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="running")

    replay = await ReplayService(session).get_replay(run_id)

    _assert_valid_timeline(replay, final_status="completed")
    assert _statuses(replay) == ["running", "completed"]


@pytest.mark.asyncio
async def test_interrupted_approval_required_timeline_stays_current_interrupted(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(
        session,
        final_status="interrupted",
        scenario="interrupted_approval_required",
    )
    service = ReplayService(session)
    lifecycle = RunLifecycleService(session)
    approval_id = "approval-interrupted-1"

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await _append_approval_requested(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="approval_required",
        clarification_ref=approval_id,
    )

    replay = await service.get_replay(run_id)

    _assert_valid_timeline(replay, final_status="interrupted")
    assert _statuses(replay)[-1] == "interrupted"
    assert _has_event_type(replay, "approval_requested")
    assert any(event["resource_refs"].get("approval_id") == approval_id for event in replay["timeline"])
    assert not _has_event_with_payload(replay, "run_status_changed", status="completed")


@pytest.mark.asyncio
async def test_resumed_completed_timeline_continues_sequence_after_resume(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(
        session,
        final_status="completed",
        scenario="resumed_completed",
    )
    service = ReplayService(session)
    lifecycle = RunLifecycleService(session)
    approval_id = "approval-resume-1"

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await _append_approval_requested(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="approval_required",
        clarification_ref=approval_id,
    )
    await _append_approval_decided(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
        decision_type="accept",
        approval_status="approved",
    )
    await _append_approval_resumed(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_resumed(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="interrupted",
        reason_code="approval_resumed",
    )
    await _append_action_draft_created(service, run_id=run_id, tenant_id=tenant_id, thread_id=thread_id)
    await lifecycle.mark_completed(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="resumed",
        reason_code="resumed_approved",
    )

    replay = await service.get_replay(run_id)

    _assert_valid_timeline(replay, final_status="completed")
    assert _statuses(replay) == ["running", "interrupted", "resumed", "completed"]
    decided = _sequence_for(replay, "approval_decided", decision_type="accept")
    resumed = _sequence_for(replay, "approval_resumed", status="resumed")
    action = _sequence_for(replay, "action_draft_created", execution_mode="demo")
    completed = _sequence_for(replay, "run_status_changed", status="completed")
    assert decided < resumed < action < completed


@pytest.mark.asyncio
async def test_rejected_timeline_preserves_partial_events_and_terminal_status(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session, final_status="rejected", scenario="rejected")
    service = ReplayService(session)
    lifecycle = RunLifecycleService(session)
    approval_id = "approval-rejected-1"

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await _append_approval_requested(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="approval_required",
        clarification_ref=approval_id,
    )
    await _append_approval_decided(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
        decision_type="reject",
        approval_status="rejected",
    )
    await lifecycle.mark_rejected(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="interrupted",
        reason_code="approval_rejected",
    )

    replay = await service.get_replay(run_id)

    _assert_valid_timeline(replay, final_status="rejected")
    assert _statuses(replay)[-1] == "rejected"
    assert _has_event_with_payload(replay, "approval_decided", decision_type="reject")
    assert _has_event_type(replay, "approval_requested")


@pytest.mark.asyncio
async def test_responded_needs_info_timeline_has_safe_decision_without_completion(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(
        session,
        final_status="interrupted",
        scenario="responded_needs_info",
    )
    service = ReplayService(session)
    lifecycle = RunLifecycleService(session)
    approval_id = "approval-respond-1"
    clarification_request_id = "clarification-respond-1"

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await _append_approval_requested(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="approval_required",
        clarification_ref=approval_id,
    )
    await _append_approval_decided(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
        decision_type="respond",
        approval_status="needs_info",
        clarification_request_id=clarification_request_id,
    )
    await lifecycle.mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="interrupted",
        reason_code="needs_info_response",
        clarification_ref=clarification_request_id,
    )

    replay = await service.get_replay(run_id)

    _assert_valid_timeline(replay, final_status="interrupted")
    assert _has_event_with_payload(replay, "approval_decided", decision_type="respond")
    assert _has_event_with_payload(replay, "approval_decided", approval_status="needs_info")
    assert _statuses(replay)[-1] == "interrupted"
    assert not _has_event_with_payload(replay, "run_status_changed", status="completed")
    assert not _has_event_type(replay, "action_execution_started")
    assert not _has_event_type(replay, "action_execution_completed")


@pytest.mark.asyncio
async def test_expired_timeline_records_sla_expiry_and_terminal_status(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session, final_status="expired", scenario="expired")
    service = ReplayService(session)
    lifecycle = RunLifecycleService(session)
    approval_id = "approval-expired-1"

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await _append_approval_requested(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="approval_required",
        clarification_ref=approval_id,
    )
    await _append_approval_expired(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        approval_id=approval_id,
    )
    await lifecycle.mark_expired(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="interrupted",
        reason_code="approval_expired",
    )

    replay = await service.get_replay(run_id)

    _assert_valid_timeline(replay, final_status="expired")
    assert _statuses(replay)[-1] == "expired"
    assert _has_event_type(replay, "approval_expired")
    assert not _has_event_type(replay, "approval_resumed")
    assert not _has_event_type(replay, "action_draft_created")


@pytest.mark.asyncio
async def test_error_timeline_keeps_safe_error_code_without_raw_stack_trace(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session, final_status="error", scenario="error")
    service = ReplayService(session)
    lifecycle = RunLifecycleService(session)

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await _append_node_error(service, run_id=run_id, tenant_id=tenant_id, thread_id=thread_id)
    await lifecycle.mark_error(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="graph_error",
        error_code="GRAPH_ERROR",
    )

    replay = await service.get_replay(run_id)
    serialized = json.dumps(replay, default=str, sort_keys=True)

    _assert_valid_timeline(replay, final_status="error")
    assert _statuses(replay)[-1] == "error"
    assert _has_event_with_payload(replay, "node_failed", error_code="GRAPH_ERROR")
    assert _has_event_with_payload(replay, "run_status_changed", error_code="GRAPH_ERROR")
    assert "Traceback" not in serialized
    assert "sk_live_secret" not in serialized


@pytest.mark.asyncio
async def test_cancelled_timeline_records_source_metadata_without_action_execution(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session, final_status="cancelled", scenario="cancelled")
    lifecycle = RunLifecycleService(session)

    await lifecycle.mark_running(run_id=run_id, tenant_id=tenant_id, thread_id=thread_id, previous_status="pending")
    await lifecycle.mark_cancelled(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        previous_status="running",
        reason_code="client_cancelled",
        cancellation_source="client",
    )

    replay = await ReplayService(session).get_replay(run_id)

    _assert_valid_timeline(replay, final_status="cancelled")
    assert _statuses(replay) == ["running", "cancelled"]
    assert _has_event_with_payload(replay, "run_status_changed", cancellation_source="client")
    assert replay["timeline"][-1]["actor"] == {"type": "system", "id": "run_lifecycle_service"}
    assert not _has_event_type(replay, "action_execution_started")
    assert not _has_event_type(replay, "action_execution_completed")
