from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, LongTermMemory, MemoryWriteEvent
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository
from src.memory.schemas import LongTermMemoryWriteCandidate


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str = "long-term-memory") -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="remember preference",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    content: str = "Merchant prefers concise refund summaries.",
    source_type: str = "explicit_user_preference",
    pii_classification: str = "none",
) -> LongTermMemoryWriteCandidate:
    merchant = seeded_session["merchant"]
    return LongTermMemoryWriteCandidate(
        tenant_id=merchant.tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        memory_kind="preference",
        content=content,
        source_type=source_type,
        source_ref={"source_type": source_type, "run_id": str(run_id), "business_object_id": str(merchant.id)},
        confidence=0.91,
        pii_classification=pii_classification,
    )


async def _events(session: AsyncSession, run_id: uuid.UUID) -> list[MemoryWriteEvent]:
    result = await session.execute(
        select(MemoryWriteEvent).where(MemoryWriteEvent.run_id == run_id).order_by(MemoryWriteEvent.created_at)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_explicit_user_remember_request_auto_approves(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    result = await service.write_memory(_candidate(seeded_session, run_id=run_id))

    row = await session.get(LongTermMemory, result.memory_id)
    events = await _events(session, run_id)
    assert result.status == "written"
    assert result.review_status == "auto_approved"
    assert row is not None
    assert row.review_status == "auto_approved"
    assert row.pii_classification == "none"
    assert events[-1].decision == "write"
    assert events[-1].memory_type == "long_term_fact"
    assert events[-1].memory_id == row.id
    assert events[-1].candidate_hash == result.candidate_hash


@pytest.mark.asyncio
async def test_deterministic_durable_source_auto_approves(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Confirmed merchant resolution SLA is two business days.",
            source_type="deterministic_tool_result",
        )
    )

    row = await session.get(LongTermMemory, result.memory_id)
    assert result.status == "written"
    assert result.review_status == "auto_approved"
    assert row is not None
    assert row.review_status == "auto_approved"


@pytest.mark.asyncio
async def test_llm_candidate_requires_review(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        content="Model inferred merchant may prefer high-touch handling.",
        source_type="llm_candidate",
    )

    result = await service.write_memory(candidate)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )

    row = await session.get(LongTermMemory, result.memory_id)
    events = await _events(session, run_id)
    assert result.status == "needs_review"
    assert result.review_status == "needs_review"
    assert row is not None
    assert row.review_status == "needs_review"
    assert retrieved == []
    assert events[-1].decision == "needs_review"


@pytest.mark.asyncio
async def test_prohibited_pii_candidate_is_skipped_and_evented(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        content="Customer phone number is 13800138000.",
        pii_classification="prohibited",
    )

    result = await service.write_memory(candidate)
    rows = (
        await session.execute(
            select(LongTermMemory).where(
                LongTermMemory.tenant_id == candidate.tenant_id,
                LongTermMemory.scope_type == candidate.scope_type,
                LongTermMemory.scope_id == candidate.scope_id,
            )
        )
    ).scalars().all()
    events = await _events(session, run_id)

    assert result.status == "skipped"
    assert result.memory_id is None
    assert result.reason_code == "pii_blocked"
    assert rows == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "pii_blocked"
    assert events[-1].pii_classification == "prohibited"
    assert events[-1].candidate_hash == result.candidate_hash

