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
                schema_version="replay_event.v3",
            )
            await worker_session.commit()
            return int(event["sequence"])

    sequences = await asyncio.gather(*(append_from_writer(index) for index in range(5)))

    assert sorted(sequences) == [1, 2, 3, 4, 5]
    assert len(sequences) == len(set(sequences)), "duplicate sequence values are forbidden"


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

    # Lifecycle/finalizer writer coverage DEFERRED_TO_PLAN: 15-04.
    # External worker allocator coverage DEFERRED_WITH_OWNER: Phase 17.
    rows = (
        await session.execute(
            select(AgentTraceEvent.sequence, AgentTraceEvent.event_type)
            .where(AgentTraceEvent.run_id == run_id)
            .order_by(AgentTraceEvent.sequence)
        )
    ).all()

    assert [graph_writer["sequence"], memory_write_writer["sequence"]] == [1, 2]
    assert [approval_writer["sequence"], action_draft_writer["sequence"], replay_backfill_writer["sequence"]] == [
        3,
        4,
        5,
    ]
    assert [sequence for sequence, _event_type in rows] == [1, 2, 3, 4, 5]
    assert len({sequence for sequence, _event_type in rows}) == 5
    assert "pg_advisory_xact_lock" in inspect.getsource(ReplayService.allocate_sequence)
