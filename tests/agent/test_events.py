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
    RAG_RETRIEVAL_TOOLS,
    allocate_sequence,
    classify_event_family,
    emit_event,
)
import src.agent.events as events_module
from src.agent.trace import write_agent_run
from src.db.models import AgentTraceEvent


OPERATION_EVENT_PREFIXES = ("node_", "tool_call_", "rag_retrieval_", "llm_call_", "memory_write_")


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
    if operation_id is None and event_type.startswith(OPERATION_EVENT_PREFIXES):
        operation_id = uuid.uuid4()
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
async def test_emit_event_delegates_to_emit_decision_event(monkeypatch):
    calls = []

    async def spy_emit_decision_event(session, **kwargs):
        calls.append((session, kwargs))
        redacted_payload = {
            **kwargs["redacted_payload"],
            "iteration": kwargs["iteration"],
            "reason_codes": ["scope_denied", "missing_permission"],
        }
        return {
            "schema_version": "minimal_event_envelope.v1",
            "event_id": uuid.uuid4(),
            "sequence": 7,
            "operation_id": kwargs.get("operation_id"),
            "run_id": uuid.UUID(str(kwargs["run_id"])),
            "tenant_id": uuid.UUID(str(kwargs["tenant_id"])),
            "thread_id": kwargs["thread_id"],
            "trace_id": kwargs.get("trace_id"),
            "event_type": kwargs["event_type"],
            "occurred_at": datetime.now(UTC),
            "actor": kwargs["actor"],
            "resource_refs": kwargs["resource_refs"],
            "redaction_policy_version": kwargs["redaction_policy_version"],
            "redacted_payload": redacted_payload,
        }

    monkeypatch.setattr(events_module, "emit_decision_event", spy_emit_decision_event)

    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    emitted = await emit_event(
        object(),
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="event-test-thread",
        event_type="tool_call_started",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload={"status": "started"},
        operation_id=uuid.uuid4(),
        iteration=3,
        reason_code="scope_denied",
        reason_codes=["missing_permission", "scope_denied"],
    )

    _session, kwargs = calls[0]
    assert emitted["schema_version"] == "minimal_event_envelope.v1"
    assert emitted["sequence"] == 7
    assert emitted["redacted_payload"]["iteration"] == 3
    assert emitted["redacted_payload"]["reason_codes"] == ["scope_denied", "missing_permission"]
    assert kwargs["reason_code"] == "scope_denied"
    assert kwargs["reason_codes"] == ["missing_permission", "scope_denied"]


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


def test_case_memory_keeps_single_retrieval_tool_name():
    assert "search_case_memory" in RAG_RETRIEVAL_TOOLS
    assert "search_reviewed_case_memory" not in RAG_RETRIEVAL_TOOLS
    assert classify_event_family("search_case_memory") == "rag_retrieval"


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


def test_action_draft_created_event_type_and_retention_are_registered():
    assert "action_draft_created" in MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["action_draft_created"] == "minimal_event"
    assert not any(event_type.startswith("action_execution_") for event_type in MINIMAL_EVENT_TYPES)


def test_no_action_execution_event_family_is_registered():
    forbidden = {
        "action_execution_started",
        "action_execution_completed",
        "action_execution_failed",
    }

    assert forbidden.isdisjoint(MINIMAL_EVENT_TYPES)
    assert forbidden.isdisjoint(EVENT_RETENTION_CLASSIFICATION)


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
        (
            await session.execute(
                select(AgentTraceEvent).where(
                    AgentTraceEvent.run_id == run_id,
                    AgentTraceEvent.operation_id == operation_id,
                )
            )
        )
        .scalars()
        .all()
    )
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


@pytest.mark.asyncio
async def test_action_draft_created_rejects_raw_payload_like_event_data(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    for key in ("raw_payload", "raw_args", "arguments"):
        with pytest.raises(ValueError, match=key):
            await _emit(
                session,
                run_id=run_id,
                tenant_id=tenant_id,
                event_type="action_draft_created",
                redacted_payload={"summary": {key: {"target_id": "RF-1001"}}},
            )


@pytest.mark.asyncio
async def test_action_execution_events_cannot_be_emitted_in_phase14_demo(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError, match="action_execution_completed"):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            event_type="action_execution_completed",
            redacted_payload={"status": "completed"},
        )
