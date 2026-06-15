from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import (
    EVENT_RETENTION_CLASSIFICATION,
    MINIMAL_EVENT_TYPES,
    allocate_sequence,
    classify_event_family,
    emit_event,
)
from src.agent.trace import write_agent_run
from src.db.models import AgentTraceEvent


async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="event-test-thread",
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="订单退款为什么超时？",
        final_status="completed",
        final_response="根据政策建议核实退款通道。",
        started_at=now,
        completed_at=now,
        total_latency_ms=12,
    )
    return run_id, tenant_id


async def _emit(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    event_type: str = "tool_call_started",
    operation_id: uuid.UUID | None = None,
    redacted_payload: dict | None = None,
    iteration: int | None = None,
) -> dict:
    return await emit_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="event-test-thread",
        event_type=event_type,
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload=redacted_payload or {"status": "started"},
        operation_id=operation_id,
        iteration=iteration,
    )


@pytest.mark.asyncio
async def test_sequence_monotonic(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    first = await _emit(session, run_id=run_id, tenant_id=tenant_id)
    second = await _emit(session, run_id=run_id, tenant_id=tenant_id)

    assert [first["sequence"], second["sequence"]] == [1, 2]


@pytest.mark.asyncio
async def test_sequence_continues_after_resume(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    session.add(
        AgentTraceEvent(
            event_id=uuid.uuid4(),
            run_id=run_id,
            sequence=5,
            tenant_id=tenant_id,
            thread_id="event-test-thread",
            event_type="node_completed",
            schema_version="minimal_event_envelope.v1",
            occurred_at=datetime.now(UTC),
            actor={"type": "agent", "id": "moca"},
            resource_refs={},
            redaction_policy_version="redaction.v1",
            redacted_payload={"status": "completed"},
        )
    )
    await session.flush()

    assert await allocate_sequence(session, run_id) == 6


@pytest.mark.asyncio
async def test_sequence_no_collision_unique_constraint(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    await _emit(session, run_id=run_id, tenant_id=tenant_id)

    # The shared test AsyncSession is not safe for true concurrent gather calls.
    # Assert the DB backstop rejects a duplicate (run_id, sequence).
    session.add(
        AgentTraceEvent(
            event_id=uuid.uuid4(),
            run_id=run_id,
            sequence=1,
            tenant_id=tenant_id,
            thread_id="event-test-thread",
            event_type="node_completed",
            schema_version="minimal_event_envelope.v1",
            occurred_at=datetime.now(UTC),
            actor={"type": "agent", "id": "moca"},
            resource_refs={},
            redaction_policy_version="redaction.v1",
            redacted_payload={"status": "completed"},
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


def test_classification_by_nature():
    assert classify_event_family("get_order") == "tool_call"
    assert classify_event_family("search_policy") == "rag_retrieval"
    assert classify_event_family("search_case_memory") == "rag_retrieval"
    with pytest.raises(ValueError):
        classify_event_family("issue_coupon")


def test_memory_write_event_types_and_retention_are_registered():
    assert {"memory_write_started", "memory_write_completed", "memory_write_failed"} <= MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_started"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_completed"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_failed"] == "minimal_event"


def test_approval_event_types_and_retention_are_registered():
    assert {"approval_requested", "approval_decided", "approval_expired", "approval_resumed"} <= MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["approval_requested"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["approval_decided"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["approval_expired"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["approval_resumed"] == "minimal_event"


@pytest.mark.asyncio
async def test_single_operation_one_family(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    operation_id = uuid.uuid4()
    family = classify_event_family("get_order")

    await _emit(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        event_type=f"{family}_started",
        operation_id=operation_id,
    )

    rows = (
        await session.execute(
            select(AgentTraceEvent).where(
                AgentTraceEvent.run_id == run_id,
                AgentTraceEvent.operation_id == operation_id,
            )
        )
    ).scalars().all()
    assert [row.event_type for row in rows] == ["tool_call_started"]
    assert not any(row.event_type.startswith("rag_retrieval_") for row in rows)


@pytest.mark.asyncio
async def test_iteration_in_redacted_payload(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    envelope = await _emit(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        event_type="rag_retrieval_started",
        redacted_payload={"status": "started"},
        iteration=2,
    )

    row = (
        await session.execute(select(AgentTraceEvent).where(AgentTraceEvent.event_id == envelope["event_id"]))
    ).scalar_one()
    assert row.redacted_payload["iteration"] == 2
    assert "iteration" not in envelope


@pytest.mark.asyncio
async def test_redaction_guard(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            redacted_payload={"data": {"raw": "tool output"}},
        )

    with pytest.raises(ValueError):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            redacted_payload={"summary": {"prompt": "hidden prompt"}},
        )

    with pytest.raises(ValueError):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            redacted_payload={"events": [{"arguments": {"order_no": "ORD-001"}}]},
        )

    with pytest.raises(ValueError):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            event_type="memory_write_failed",
            redacted_payload={"summary": {"raw": "slot payload"}},
        )

    for key in (
        "raw_prompt",
        "raw_args",
        "raw_payload",
        "raw_tool_output",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "pii",
    ):
        with pytest.raises(ValueError):
            await _emit(
                session,
                run_id=run_id,
                tenant_id=tenant_id,
                event_type="approval_decided",
                redacted_payload={"summary": {key: "unsafe"}},
            )
