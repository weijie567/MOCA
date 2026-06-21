from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, MemoryWriteEvent
from src.memory.write_isolation import run_memory_side_effect_in_isolated_session


@pytest.mark.asyncio
async def test_isolated_memory_side_effect_rolls_back_child_only(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    run = AgentRun(
        id=uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id="write-isolation-thread",
        input_query="test write isolation",
        final_status="running",
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()

    run.final_status = "completed"
    await session.flush()

    async def failing_memory_side_effect(memory_session: AsyncSession) -> None:
        memory_session.add(
            MemoryWriteEvent(
                tenant_id=user.tenant_id,
                run_id=run.id,
                memory_type="none",
                memory_id=None,
                decision="skip",
                reason_code="test_child_rollback",
                pii_classification="none",
                candidate_hash="sha256:test_child_rollback",
                source_ref_json={"test": "write_isolation"},
            )
        )
        await memory_session.flush()
        raise RuntimeError("child rollback only")

    with pytest.raises(RuntimeError, match="child rollback only"):
        await run_memory_side_effect_in_isolated_session(session, failing_memory_side_effect)

    await session.commit()
    persisted = await session.get(AgentRun, run.id)
    child_event_count = (
        await session.execute(
            select(func.count(MemoryWriteEvent.id)).where(
                MemoryWriteEvent.run_id == run.id,
                MemoryWriteEvent.reason_code == "test_child_rollback",
            )
        )
    ).scalar_one()

    assert persisted is not None
    assert persisted.final_status == "completed"
    assert child_event_count == 0
