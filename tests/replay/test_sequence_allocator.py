from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import inspect
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agent.events import emit_event
from src.agent.trace import write_agent_run
from src.db.models import AgentTraceEvent
from src.replay.decision_events import emit_decision_event
from src.replay.lifecycle import RunLifecycleService
from src.replay.pairing import OperationPairingError
from src.replay.service import ReplayService


async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="sequence-allocator-thread",
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="需要回放事件顺序",
        final_status="running",
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
    )
    return run_id, tenant_id


@pytest.mark.asyncio
async def test_sequence_allocator_resume_sequence_continues_after_existing_rows(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    session.add(
        AgentTraceEvent(
            event_id=uuid.uuid4(),
            run_id=run_id,
            sequence=8,
            tenant_id=tenant_id,
            thread_id="sequence-allocator-thread",
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

    event = await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="approval_requested",
        actor={"type": "approver", "id": "approval-api"},
        resource_refs={"approval_id": str(uuid.uuid4())},
        redacted_payload={"status": "pending"},
    )

    assert event["sequence"] == 9


@pytest.mark.asyncio
async def test_concurrent_append_calls_do_not_duplicate_sequence(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as setup_session:
        run_id, tenant_id = await _create_run(setup_session)
        await setup_session.commit()

    async def append_from_writer(index: int) -> int:
        async with session_factory() as worker_session:
            event = await ReplayService(worker_session).append_event(
                run_id=run_id,
                tenant_id=tenant_id,
                thread_id="sequence-allocator-thread",
                event_type="tool_call_started",
                actor={"type": "agent", "id": f"writer-{index}"},
                resource_refs={"tool": "get_order"},
                redacted_payload={"status": "started", "writer_index": index},
                operation_id=uuid.uuid4(),
                attempt=1,
                schema_version="replay_event.v3",
            )
            await worker_session.commit()
            return int(event["sequence"])

    sequences = await asyncio.gather(*(append_from_writer(index) for index in range(5)))

    assert sorted(sequences) == [2, 3, 4, 5, 6]
    assert len(sequences) == len(set(sequences)), "duplicate sequence values are forbidden"


@pytest.mark.asyncio
async def test_concurrent_terminal_events_do_not_duplicate_operation_pair(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    operation_id = uuid.uuid4()
    async with session_factory() as setup_session:
        run_id, tenant_id = await _create_run(setup_session)
        await ReplayService(setup_session).append_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="sequence-allocator-thread",
            event_type="tool_call_started",
            actor={"type": "agent", "id": "writer-start"},
            resource_refs={"tool": "get_order"},
            redacted_payload={"status": "started"},
            operation_id=operation_id,
            attempt=1,
            schema_version="replay_event.v3",
        )
        await setup_session.commit()

    async def append_terminal(index: int) -> str:
        async with session_factory() as worker_session:
            try:
                await ReplayService(worker_session).append_event(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    thread_id="sequence-allocator-thread",
                    event_type="tool_call_completed",
                    actor={"type": "agent", "id": f"writer-terminal-{index}"},
                    resource_refs={"tool": "get_order"},
                    redacted_payload={"status": "completed", "writer_index": index},
                    operation_id=operation_id,
                    attempt=1,
                    schema_version="replay_event.v3",
                )
                await worker_session.commit()
                return "committed"
            except OperationPairingError:
                await worker_session.rollback()
                return "rejected"

    results = await asyncio.gather(*(append_terminal(index) for index in range(2)))

    assert sorted(results) == ["committed", "rejected"]
    async with session_factory() as verify_session:
        rows = (
            (
                await verify_session.execute(
                    select(AgentTraceEvent.event_type)
                    .where(AgentTraceEvent.run_id == run_id)
                    .where(AgentTraceEvent.operation_id == operation_id)
                    .order_by(AgentTraceEvent.sequence)
                )
            )
            .scalars()
            .all()
        )

    assert list(rows) == ["tool_call_started", "tool_call_completed"]


@pytest.mark.asyncio
async def test_sequence_allocator_covers_pre_lifecycle_writer_surfaces(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    # graph writer: src.agent.events.emit_event
    graph_writer = await emit_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="node_started",
        actor={"type": "agent", "id": "graph-writer"},
        resource_refs={"node": "investigate"},
        redacted_payload={"status": "started"},
        operation_id=uuid.uuid4(),
    )
    # memory_write writer: src.agent.nodes.memory_write.memory_write event helper surface
    memory_write_writer = await emit_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="memory_write_started",
        actor={"type": "agent", "id": "memory_write-writer"},
        resource_refs={"memory_type": "session_memory"},
        redacted_payload={"status": "started"},
        operation_id=uuid.uuid4(),
    )
    # decision event facade: src.replay.decision_events.emit_decision_event
    decision_writer = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-event-writer"},
        resource_refs={},
        redacted_payload={"from_status": "running", "to_status": "decision-recorded"},
    )
    # approval writer: src.approvals.events approval/API event surface
    approval_writer = await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="approval_requested",
        actor={"type": "approver", "id": "approval-writer"},
        resource_refs={"approval_id": str(uuid.uuid4())},
        redacted_payload={"status": "pending"},
    )
    # action draft writer: src.actions.service action draft event helper surface
    action_draft_writer = await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="action_draft_created",
        actor={"type": "agent", "id": "action-draft-writer"},
        resource_refs={"draft_id": str(uuid.uuid4())},
        redacted_payload={"status": "created", "external_side_effect": False},
    )
    # replay backfill writer: ReplayService.append_event
    replay_backfill_writer = await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="run_status_changed",
        actor={"type": "system", "id": "replay-backfill"},
        resource_refs={},
        redacted_payload={"from_status": "running", "to_status": "interrupted"},
    )
    # lifecycle/finalizer writer: RunLifecycleService
    lifecycle_writer = await RunLifecycleService(session).mark_interrupted(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        previous_status="running",
        reason_code="approval_required",
    )

    # graph writer, memory_write writer, approval writer, action draft writer,
    # decision event facade, replay backfill writer, lifecycle writer all share the same allocator.
    # External worker allocator coverage DEFERRED_WITH_OWNER: Phase 17.
    rows = (
        await session.execute(
            select(AgentTraceEvent.sequence, AgentTraceEvent.event_type)
            .where(AgentTraceEvent.run_id == run_id)
            .order_by(AgentTraceEvent.sequence)
        )
    ).all()

    assert [graph_writer["sequence"], memory_write_writer["sequence"]] == [2, 3]
    assert [
        decision_writer["sequence"],
        approval_writer["sequence"],
        action_draft_writer["sequence"],
        replay_backfill_writer["sequence"],
        lifecycle_writer["sequence"],
    ] == [
        4,
        5,
        6,
        7,
        8,
    ]
    assert [sequence for sequence, _event_type in rows] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [event_type for _sequence, event_type in rows][0] == "run_status_changed"
    assert len({sequence for sequence, _event_type in rows}) == 8
    assert "_lock_run" in inspect.getsource(ReplayService.allocate_sequence)
    assert "pg_advisory_xact_lock" in inspect.getsource(ReplayService._lock_run)
