from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import AgentRun, LongTermMemory, MemoryTombstone, MemoryWriteEvent
from src.memory.case_memory import CASE_MEMORY_TYPE, CaseMemoryRepository, CaseMemoryService
from src.memory.identity import canonical_memory_content_hash
from src.memory.repository import LONG_TERM_MEMORY_TYPE, LongTermMemoryRepository
from src.memory.long_term import LongTermMemoryService
from src.memory.schemas import CaseMemoryWriteCandidate, LongTermMemoryWriteCandidate


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str = "memory-tombstones") -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="remember or forget profile memory",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _source_ref(
    *,
    source_type: str,
    run_id: uuid.UUID,
    business_object_id: str,
    event_id: str = "evt-memory-source-1",
) -> dict[str, str]:
    return {
        "source_type": source_type,
        "run_id": str(run_id),
        "event_id": event_id,
        "business_object_type": "merchant",
        "business_object_id": business_object_id,
    }


def _candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    content: str = "Merchant prefers concise refund summaries.",
    source_type: str = "explicit_user_preference",
    source_ref: dict[str, str] | None = None,
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
        source_ref=source_ref
        or _source_ref(
            source_type=source_type,
            run_id=run_id,
            business_object_id=str(merchant.id),
        ),
        confidence=0.91,
        pii_classification="none",
    )


def _case_source_ref(
    *,
    source_type: str,
    run_id: uuid.UUID,
    case_id: str,
    event_id: str = "evt-case-memory-source-1",
) -> dict[str, str]:
    return {
        "source_type": source_type,
        "run_id": str(run_id),
        "event_id": event_id,
        "business_object_type": "refund_case",
        "business_object_id": case_id,
    }


def _case_candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    summary: str = "Reviewed refund dispute precedent for damaged item evidence.",
    source_type: str = "human_reviewed",
    source_ref: dict[str, str] | None = None,
) -> CaseMemoryWriteCandidate:
    refund_case = seeded_session["refund_case"]
    return CaseMemoryWriteCandidate(
        tenant_id=refund_case.tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(refund_case.id),
        case_type="refund_dispute",
        summary=summary,
        excerpt="Use only as reviewed precedent context for similar refund disputes.",
        applicability="Applies to damaged item disputes after source review.",
        outcome="Refund approved after support verification.",
        caveats="Not policy evidence and not action authority.",
        source_type=source_type,
        source_ref=source_ref
        or _case_source_ref(
            source_type=source_type,
            run_id=run_id,
            case_id=str(refund_case.id),
        ),
        policy_family="refund",
        policy_version="v1",
        policy_refs=[{"doc_key": "refund_policy", "chunk_id": "chunk-1", "policy_version": "v1"}],
        embedding=[1.0, *([0.0] * 1023)],
        pii_classification="none",
    )


async def _events(session: AsyncSession, run_id: uuid.UUID) -> list[MemoryWriteEvent]:
    result = await session.execute(
        select(MemoryWriteEvent).where(MemoryWriteEvent.run_id == run_id).order_by(MemoryWriteEvent.created_at)
    )
    return list(result.scalars().all())


async def _current_rows(session: AsyncSession, candidate: LongTermMemoryWriteCandidate) -> list[LongTermMemory]:
    result = await session.execute(
        select(LongTermMemory)
        .where(
            LongTermMemory.tenant_id == candidate.tenant_id,
            LongTermMemory.scope_type == candidate.scope_type,
            LongTermMemory.scope_id == candidate.scope_id,
            LongTermMemory.is_current.is_(True),
            LongTermMemory.deleted_at.is_(None),
        )
        .order_by(LongTermMemory.created_at)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_forget_long_term_memory_creates_tombstone_and_excludes_retrieval_immediately(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id)
    write_result = await service.write_memory(candidate)

    before = await service.repository.retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )
    forget_event = await service.forget_long_term_memory(
        tenant_id=candidate.tenant_id,
        memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="user_forget",
    )

    tombstones = (
        (
            await session.execute(
                select(MemoryTombstone).where(
                    MemoryTombstone.tenant_id == candidate.tenant_id,
                    MemoryTombstone.memory_type == LONG_TERM_MEMORY_TYPE,
                    MemoryTombstone.scope_type == candidate.scope_type,
                    MemoryTombstone.scope_id == candidate.scope_id,
                    MemoryTombstone.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    after = await service.repository.retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )

    assert [row.content for row in before] == [candidate.content]
    assert len(tombstones) == 1
    assert tombstones[0].content_hash == write_result.content_hash
    assert tombstones[0].source_identity_hash == write_result.source_identity_hash
    assert after == []
    assert forget_event.decision == "tombstone"
    assert forget_event.reason_code == "user_forget"


@pytest.mark.asyncio
async def test_tombstone_blocks_same_transaction_rewrite_by_content_hash(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    original = _candidate(seeded_session, run_id=run_id)
    write_result = await service.write_memory(original)
    await service.forget_long_term_memory(
        tenant_id=original.tenant_id,
        memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="user_forget",
    )

    rewrite_run_id = await _insert_run(session, seeded_session, thread_id="same-transaction-rewrite")
    rewrite = _candidate(
        seeded_session,
        run_id=rewrite_run_id,
        content=original.content,
        source_ref=_source_ref(
            source_type="explicit_user_preference",
            run_id=rewrite_run_id,
            business_object_id=str(seeded_session["merchant"].id),
            event_id="evt-different-source",
        ),
    )
    result = await service.write_memory(rewrite)
    events = await _events(session, rewrite_run_id)

    assert result.status == "skipped"
    assert result.memory_id is None
    assert result.reason_code == "tombstone_match"
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "tombstone_match"
    assert (
        await service.repository.retrieve_profile_memory(
            tenant_id=rewrite.tenant_id,
            scope_type=rewrite.scope_type,
            scope_id=rewrite.scope_id,
        )
        == []
    )


@pytest.mark.asyncio
async def test_tombstone_blocks_rewrite_by_source_identity_fallback(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    repository = LongTermMemoryRepository(session)
    service = LongTermMemoryService(repository)
    source_ref = _source_ref(
        source_type="deterministic_tool_result",
        run_id=run_id,
        business_object_id=str(seeded_session["merchant"].id),
    )
    await repository.create_tombstone(
        tenant_id=seeded_session["tenant"].id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
        content_hash=None,
        source_ref_json=source_ref,
        reason_code="source_forget",
        created_by_run_id=run_id,
    )

    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        content="Source generated an updated profile sentence with different text.",
        source_type="deterministic_tool_result",
        source_ref=source_ref,
    )
    result = await service.write_memory(candidate)
    events = await _events(session, run_id)

    assert result.status == "skipped"
    assert result.memory_id is None
    assert result.reason_code == "tombstone_match"
    assert result.source_identity_hash is not None
    assert events[-1].reason_code == "tombstone_match"


@pytest.mark.asyncio
async def test_expired_tombstone_identity_can_be_recreated(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="expired-tombstone-recreate")
    repository = LongTermMemoryRepository(session)
    now = datetime.now(UTC)
    source_ref = _source_ref(
        source_type="explicit_user_preference",
        run_id=run_id,
        business_object_id=str(seeded_session["merchant"].id),
        event_id="evt-expired-tombstone",
    )
    content_hash = canonical_memory_content_hash(
        memory_type=LONG_TERM_MEMORY_TYPE,
        content="Merchant deleted a temporary preference.",
    )
    expired = await repository.create_tombstone(
        tenant_id=seeded_session["tenant"].id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
        content_hash=content_hash,
        source_ref_json=source_ref,
        reason_code="temporary_forget",
        created_by_run_id=run_id,
        expires_at=now - timedelta(seconds=1),
        now=now - timedelta(seconds=2),
    )

    replacement = await repository.create_tombstone(
        tenant_id=seeded_session["tenant"].id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
        content_hash=content_hash,
        source_ref_json=source_ref,
        reason_code="fresh_forget",
        created_by_run_id=run_id,
        now=now,
    )
    await session.refresh(expired)

    assert replacement.id != expired.id
    assert expired.deleted_at == now
    assert replacement.deleted_at is None
    assert replacement.reason_code == "fresh_forget"


@pytest.mark.asyncio
async def test_tombstone_does_not_use_semantic_similarity(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    original = _candidate(seeded_session, run_id=run_id)
    write_result = await service.write_memory(original)
    await service.forget_long_term_memory(
        tenant_id=original.tenant_id,
        memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="user_forget",
    )

    similar_run_id = await _insert_run(session, seeded_session, thread_id="similar-content")
    similar = _candidate(
        seeded_session,
        run_id=similar_run_id,
        content="Merchant prefers concise refund summaries with a short bullet list.",
        source_ref=_source_ref(
            source_type="explicit_user_preference",
            run_id=similar_run_id,
            business_object_id=str(seeded_session["merchant"].id),
            event_id="evt-similar-but-not-identical",
        ),
    )
    result = await service.write_memory(similar)
    rows = await service.repository.retrieve_profile_memory(
        tenant_id=similar.tenant_id,
        scope_type=similar.scope_type,
        scope_id=similar.scope_id,
    )

    assert result.status == "written"
    assert result.reason_code != "tombstone_match"
    assert [row.content for row in rows] == [similar.content]


@pytest.mark.asyncio
async def test_supersede_leaves_exactly_one_current_memory(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    original = _candidate(seeded_session, run_id=run_id)
    first_result = await service.write_memory(original)

    replacement_run_id = await _insert_run(session, seeded_session, thread_id="supersede")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Merchant prefers concise refund summaries and manager escalation notes.",
    )
    supersede_result = await service.supersede_memory(
        tenant_id=original.tenant_id,
        memory_id=first_result.memory_id,
        replacement_candidate=replacement,
        run_id=replacement_run_id,
        reason_code="correction",
    )

    previous = await session.get(LongTermMemory, first_result.memory_id)
    replacement_row = await session.get(LongTermMemory, supersede_result.memory_id)
    current_rows = await _current_rows(session, replacement)
    events = await _events(session, replacement_run_id)

    assert previous is not None
    assert replacement_row is not None
    assert previous.is_current is False
    assert previous.review_status == "superseded"
    assert previous.superseded_by == replacement_row.id
    assert previous.superseded_at is not None
    assert replacement_row.is_current is True
    assert replacement_row.supersedes == previous.id
    assert [row.id for row in current_rows] == [replacement_row.id]
    assert supersede_result.decision == "supersede"
    assert events[-1].decision == "supersede"


@pytest.mark.asyncio
async def test_delayed_rewrite_separate_session_blocks_by_source_identity(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    session_factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    run_id = await _insert_run(session, seeded_session, thread_id="tombstone-session-a")
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    source_ref = _source_ref(
        source_type="explicit_user_preference",
        run_id=run_id,
        business_object_id=str(seeded_session["merchant"].id),
        event_id="evt-delayed-source",
    )
    original = _candidate(
        seeded_session,
        run_id=run_id,
        content="Merchant explicitly asks for concise summaries.",
        source_type="explicit_user_preference",
        source_ref=source_ref,
    )
    write_result = await service.write_memory(original)
    assert write_result.status == "written"
    assert write_result.memory_id is not None
    await service.forget_long_term_memory(
        tenant_id=original.tenant_id,
        memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="user_forget",
    )
    await session.commit()

    async with session_factory() as delayed_session:
        delayed_run_id = uuid.uuid4()
        user = seeded_session["users"]["cs_zhang"]
        delayed_session.add(
            AgentRun(
                id=delayed_run_id,
                tenant_id=user.tenant_id,
                user_id=user.id,
                thread_id="tombstone-session-b-delayed",
                input_query="delayed memory write",
                final_status="completed",
                started_at=datetime.now(UTC),
            )
        )
        await delayed_session.flush()
        delayed_service = LongTermMemoryService(LongTermMemoryRepository(delayed_session))
        delayed_candidate = _candidate(
            seeded_session,
            run_id=delayed_run_id,
            content="Delayed worker rewrites the forgotten explicit preference with new text.",
            source_type="explicit_user_preference",
            source_ref=source_ref,
        )

        result = await delayed_service.write_memory(delayed_candidate)
        retrieved = await delayed_service.repository.retrieve_profile_memory(
            tenant_id=delayed_candidate.tenant_id,
            scope_type=delayed_candidate.scope_type,
            scope_id=delayed_candidate.scope_id,
        )
        events = await _events(delayed_session, delayed_run_id)

    assert result.status == "skipped"
    assert result.memory_id is None
    assert result.reason_code == "tombstone_match"
    assert retrieved == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "tombstone_match"


@pytest.mark.asyncio
async def test_case_memory_tombstone_blocks_rewrite_by_content_hash_and_source_identity(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="case-memory-tombstone")
    repository = CaseMemoryRepository(session)
    service = CaseMemoryService(repository)
    original = _case_candidate(seeded_session, run_id=run_id)
    write_result = await service.submit_case_memory_candidate(original)
    await service.forget_case_memory(
        tenant_id=original.tenant_id,
        case_memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="case_forget",
    )

    content_rewrite = await service.submit_case_memory_candidate(
        _case_candidate(
            seeded_session,
            run_id=run_id,
            summary=original.summary,
            source_ref=_case_source_ref(
                source_type="human_reviewed",
                run_id=run_id,
                case_id=str(seeded_session["refund_case"].id),
                event_id="evt-case-memory-different-source",
            ),
        )
    )
    source_ref = _case_source_ref(
        source_type="deterministic_tool_result",
        run_id=run_id,
        case_id=str(seeded_session["refund_case"].id),
        event_id="evt-case-memory-source-only",
    )
    await repository.create_tombstone(
        tenant_id=original.tenant_id,
        memory_type=CASE_MEMORY_TYPE,
        scope_type=original.scope_type,
        scope_id=original.scope_id,
        content_hash=None,
        source_ref_json=source_ref,
        reason_code="source_forget",
        created_by_run_id=run_id,
    )
    source_rewrite = await service.submit_case_memory_candidate(
        _case_candidate(
            seeded_session,
            run_id=run_id,
            summary="Different reviewed summary from a deleted source identity.",
            source_type="deterministic_tool_result",
            source_ref=source_ref,
        )
    )
    events = await _events(session, run_id)

    assert content_rewrite.status == "skipped"
    assert content_rewrite.memory_id is None
    assert content_rewrite.reason_code == "tombstone_match"
    assert source_rewrite.status == "skipped"
    assert source_rewrite.memory_id is None
    assert source_rewrite.reason_code == "tombstone_match"
    assert [event.memory_type for event in events if event.reason_code == "tombstone_match"] == [
        CASE_MEMORY_TYPE,
        CASE_MEMORY_TYPE,
    ]
