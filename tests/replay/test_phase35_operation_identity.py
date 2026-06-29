from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun
from src.replay.service import ReplayService


async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, str]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    thread_id = f"phase35-operation-{run_id}"
    now = datetime.now(UTC)
    session.add(
        AgentRun(
            id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=uuid.uuid4(),
            input_query="phase35 operation identity",
            final_status="completed",
            final_response="safe final response",
            started_at=now,
            completed_at=now,
            total_latency_ms=10,
        )
    )
    await session.flush()
    return run_id, tenant_id, thread_id


async def _append_operation_event(
    service: ReplayService,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    thread_id: str,
    event_type: str,
    operation_id: uuid.UUID,
    attempt: int,
    parent_operation_id: uuid.UUID | None = None,
) -> dict:
    return await service.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type=event_type,
        actor={"type": "agent", "id": "moca"},
        resource_refs={"operation_ref": event_type.removesuffix("_started").removesuffix("_completed").removesuffix("_failed")},
        redacted_payload={"status": event_type.rsplit("_", maxsplit=1)[-1]},
        operation_id=operation_id,
        parent_operation_id=parent_operation_id,
        attempt=attempt,
    )


def _operation_events(replay: dict, *event_types: str) -> list[dict]:
    wanted = set(event_types)
    return [event for event in replay["timeline"] if event["event_type"] in wanted]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("started_type", "terminal_type"),
    [
        ("tool_call_started", "tool_call_completed"),
        ("rag_retrieval_started", "rag_retrieval_completed"),
        ("llm_call_started", "llm_call_failed"),
        ("memory_write_started", "memory_write_completed"),
    ],
)
async def test_started_terminal_operation_pairs_share_operation_id_and_attempt(
    session: AsyncSession,
    started_type: str,
    terminal_type: str,
) -> None:
    run_id, tenant_id, thread_id = await _create_run(session)
    service = ReplayService(session)
    operation_id = uuid.uuid4()

    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type=started_type,
        operation_id=operation_id,
        attempt=1,
    )
    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type=terminal_type,
        operation_id=operation_id,
        attempt=1,
    )

    replay = await service.get_replay(run_id)
    started, terminal = _operation_events(replay, started_type, terminal_type)

    assert started["operation_id"] == operation_id
    assert terminal["operation_id"] == operation_id
    assert started["attempt"] == 1
    assert terminal["attempt"] == 1
    assert started["provenance"]["pairing_status"] == "unresolved"
    assert terminal["provenance"]["pairing_status"] == "paired"


@pytest.mark.asyncio
async def test_retry_terminal_uses_new_operation_id_parent_operation_id_and_incremented_attempt(
    session: AsyncSession,
) -> None:
    run_id, tenant_id, thread_id = await _create_run(session)
    service = ReplayService(session)
    parent_operation_id = uuid.uuid4()
    retry_operation_id = uuid.uuid4()

    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_started",
        operation_id=parent_operation_id,
        attempt=1,
    )
    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_failed",
        operation_id=parent_operation_id,
        attempt=1,
    )
    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_started",
        operation_id=retry_operation_id,
        parent_operation_id=parent_operation_id,
        attempt=2,
    )
    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_completed",
        operation_id=retry_operation_id,
        parent_operation_id=parent_operation_id,
        attempt=2,
    )

    replay = await service.get_replay(run_id)
    retry_started, retry_terminal = _operation_events(replay, "tool_call_started", "tool_call_completed")[-2:]

    assert retry_started["operation_id"] == retry_operation_id
    assert retry_terminal["operation_id"] == retry_operation_id
    assert retry_terminal["operation_id"] != parent_operation_id
    assert retry_started["parent_operation_id"] == parent_operation_id
    assert retry_terminal["parent_operation_id"] == parent_operation_id
    assert retry_started["attempt"] == 2
    assert retry_terminal["attempt"] == 2
    assert retry_terminal["provenance"]["pairing_status"] == "paired"
    assert [event["sequence"] for event in replay["timeline"]] == list(range(1, len(replay["timeline"]) + 1))


@pytest.mark.asyncio
async def test_terminal_operation_rejects_mismatched_started_event_family(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session)
    service = ReplayService(session)
    operation_id = uuid.uuid4()

    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_started",
        operation_id=operation_id,
        attempt=1,
    )

    with pytest.raises(ValueError, match="family must match"):
        await _append_operation_event(
            service,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            event_type="rag_retrieval_completed",
            operation_id=operation_id,
            attempt=1,
        )


@pytest.mark.asyncio
async def test_retry_terminal_rejects_attempt_mismatch(session: AsyncSession) -> None:
    run_id, tenant_id, thread_id = await _create_run(session)
    service = ReplayService(session)
    parent_operation_id = uuid.uuid4()
    retry_operation_id = uuid.uuid4()

    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_started",
        operation_id=parent_operation_id,
        attempt=1,
    )
    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_failed",
        operation_id=parent_operation_id,
        attempt=1,
    )
    await _append_operation_event(
        service,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type="tool_call_started",
        operation_id=retry_operation_id,
        parent_operation_id=parent_operation_id,
        attempt=2,
    )

    with pytest.raises(ValueError, match="attempt must match"):
        await _append_operation_event(
            service,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            event_type="tool_call_completed",
            operation_id=retry_operation_id,
            parent_operation_id=parent_operation_id,
            attempt=3,
        )
