from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import update_agent_run_status, write_agent_run
from src.db.models import AgentRun, AgentTraceEvent
from src.replay.lifecycle import RunLifecycleService


async def _create_run(
    session: AsyncSession,
    *,
    final_status: str = "pending",
) -> tuple[AgentRun, uuid.UUID, uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run = AgentRun(
        id=run_id,
        thread_id="lifecycle-thread",
        tenant_id=tenant_id,
        user_id=user_id,
        input_query="需要生命周期回放",
        final_status=final_status,
        final_response=None,
        started_at=datetime.now(UTC),
        completed_at=None,
        total_latency_ms=None,
    )
    session.add(run)
    await session.flush()
    return run, run_id, tenant_id, user_id


async def _lifecycle_rows(session: AsyncSession, run_id: uuid.UUID) -> list[AgentTraceEvent]:
    return list(
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(
                    AgentTraceEvent.run_id == run_id,
                    AgentTraceEvent.event_type == "run_status_changed",
                )
                .order_by(AgentTraceEvent.sequence)
            )
        ).scalars()
    )


def _required_lifecycle_payload(payload: dict) -> dict:
    return {
        "status": payload["status"],
        "previous_status": payload["previous_status"],
        "reason_code": payload["reason_code"],
        **({"clarification_ref": payload["clarification_ref"]} if "clarification_ref" in payload else {}),
        **({"error_code": payload["error_code"]} if "error_code" in payload else {}),
    }


@pytest.mark.asyncio
async def test_normal_completed_lifecycle_appends_running_then_completed(session: AsyncSession):
    _run, run_id, tenant_id, _user_id = await _create_run(session)
    service = RunLifecycleService(session)

    await service.mark_running(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="pending",
    )
    await service.mark_completed(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="running",
    )

    rows = await _lifecycle_rows(session, run_id)

    assert [row.sequence for row in rows] == [1, 2]
    assert [row.redacted_payload["status"] for row in rows] == ["running", "completed"]
    assert _required_lifecycle_payload(rows[1].redacted_payload) == {
        "status": "completed",
        "previous_status": "running",
        "reason_code": "normal_completed",
    }
    assert rows[1].resource_refs == {"run_id": str(run_id)}


@pytest.mark.asyncio
async def test_interrupted_approval_lifecycle_appends_interrupted(session: AsyncSession):
    _run, run_id, tenant_id, _user_id = await _create_run(session, final_status="running")

    await RunLifecycleService(session).mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="running",
        reason_code="approval_required",
    )

    [row] = await _lifecycle_rows(session, run_id)
    assert _required_lifecycle_payload(row.redacted_payload) == {
        "status": "interrupted",
        "previous_status": "running",
        "reason_code": "approval_required",
    }


@pytest.mark.asyncio
async def test_resumed_approved_lifecycle_appends_resumed_then_completed(session: AsyncSession):
    _run, run_id, tenant_id, _user_id = await _create_run(session, final_status="interrupted")
    service = RunLifecycleService(session)

    await service.mark_resumed(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="interrupted",
        reason_code="approval_accepted",
    )
    await service.mark_completed(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="resumed",
        reason_code="resumed_approved",
    )

    rows = await _lifecycle_rows(session, run_id)
    assert [row.redacted_payload["status"] for row in rows] == ["resumed", "completed"]
    assert rows[-1].redacted_payload["reason_code"] == "resumed_approved"


@pytest.mark.asyncio
async def test_responded_needs_info_lifecycle_stays_interrupted_without_completed(session: AsyncSession):
    _run, run_id, tenant_id, _user_id = await _create_run(session, final_status="interrupted")

    await RunLifecycleService(session).mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="interrupted",
        reason_code="needs_info_response",
        clarification_ref="clarification:abc123",
    )

    rows = await _lifecycle_rows(session, run_id)
    assert [row.redacted_payload["status"] for row in rows] == ["interrupted"]
    assert _required_lifecycle_payload(rows[0].redacted_payload) == {
        "status": "interrupted",
        "previous_status": "interrupted",
        "reason_code": "needs_info_response",
        "clarification_ref": "clarification:abc123",
    }
    assert all(row.redacted_payload["status"] != "completed" for row in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "status", "reason_code", "extra_kwargs"),
    [
        ("mark_rejected", "rejected", "approval_rejected", {}),
        ("mark_expired", "expired", "approval_expired", {}),
        ("mark_error", "error", "graph_error", {"error_code": "GRAPH_ERROR"}),
        ("mark_cancelled", "cancelled", "client_cancelled", {}),
    ],
)
async def test_rejected_expired_error_cancelled_lifecycles_append_safe_terminal_status(
    session: AsyncSession,
    method_name: str,
    status: str,
    reason_code: str,
    extra_kwargs: dict,
):
    _run, run_id, tenant_id, _user_id = await _create_run(session, final_status="running")
    service = RunLifecycleService(session)

    await getattr(service, method_name)(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="lifecycle-thread",
        previous_status="running",
        reason_code=reason_code,
        **extra_kwargs,
    )

    [row] = await _lifecycle_rows(session, run_id)
    required = _required_lifecycle_payload(row.redacted_payload)
    assert required["status"] == status
    assert required["previous_status"] == "running"
    assert required["reason_code"] == reason_code
    if status == "error":
        assert required["error_code"] == "GRAPH_ERROR"


@pytest.mark.asyncio
async def test_write_agent_run_routes_running_and_completed_statuses_through_lifecycle_service(
    session: AsyncSession,
):
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    started_at = datetime.now(UTC)

    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="trace-helper-thread",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="trace helper lifecycle",
        final_status="running",
        final_response=None,
        started_at=started_at,
        completed_at=None,
        total_latency_ms=0,
    )
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="trace-helper-thread",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="trace helper lifecycle",
        final_status="completed",
        final_response="done",
        started_at=started_at,
        completed_at=datetime.now(UTC),
        total_latency_ms=10,
    )

    rows = await _lifecycle_rows(session, run_id)
    assert [row.redacted_payload["status"] for row in rows] == ["running", "completed"]
    assert rows[0].redacted_payload["reason_code"] == "run_started"
    assert rows[1].redacted_payload["previous_status"] == "running"


@pytest.mark.asyncio
async def test_update_agent_run_status_routes_resume_completion_through_lifecycle_service(
    session: AsyncSession,
):
    _run, run_id, tenant_id, _user_id = await _create_run(session, final_status="interrupted")

    await update_agent_run_status(
        session,
        run_id=str(run_id),
        final_status="completed",
        final_response="approved",
        completed_at=datetime.now(UTC),
        total_latency_ms=42,
    )

    rows = await _lifecycle_rows(session, run_id)
    assert [row.redacted_payload["status"] for row in rows] == ["completed"]
    assert _required_lifecycle_payload(rows[0].redacted_payload) == {
        "status": "completed",
        "previous_status": "interrupted",
        "reason_code": "run_completed",
    }
    assert rows[0].resource_refs == {"run_id": str(run_id)}
