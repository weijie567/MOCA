from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, LongTermMemory, MemoryWriteEvent
from src.memory.identity import (
    build_long_term_memory_candidate_identity,
    canonical_memory_content_hash,
    canonical_source_identity_hash,
)
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
    source_ref_business_object_type: str | None = None,
    source_ref_business_object_id: str | None = None,
    pii_classification: str = "none",
    expires_at: datetime | None = None,
) -> LongTermMemoryWriteCandidate:
    merchant = seeded_session["merchant"]
    source_ref = {
        "source_type": source_type,
        "run_id": str(run_id),
        "business_object_id": source_ref_business_object_id or str(merchant.id),
    }
    if source_ref_business_object_type is not None:
        source_ref["business_object_type"] = source_ref_business_object_type
    return LongTermMemoryWriteCandidate(
        tenant_id=merchant.tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        memory_kind="preference",
        content=content,
        source_type=source_type,
        source_ref=source_ref,
        confidence=0.91,
        pii_classification=pii_classification,
        expires_at=expires_at,
    )


def _pending_long_term_row(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    content: str,
    memory_kind: str,
    source_type: str = "semantic_episode_candidate",
) -> LongTermMemory:
    merchant = seeded_session["merchant"]
    source_ref = {
        "source_type": source_type,
        "run_id": str(run_id),
        "business_object_id": str(merchant.id),
    }
    return LongTermMemory(
        id=uuid.uuid4(),
        tenant_id=merchant.tenant_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        memory_kind=memory_kind,
        content=content,
        content_hash=canonical_memory_content_hash(memory_type="long_term_fact", content=content),
        source_type=source_type,
        source_ref_json=source_ref,
        source_identity_hash=canonical_source_identity_hash(source_ref),
        confidence=Decimal("0.9100"),
        pii_classification="none",
        review_status="needs_review",
        is_current=False,
        created_by_run_id=run_id,
    )


async def _events(session: AsyncSession, run_id: uuid.UUID) -> list[MemoryWriteEvent]:
    result = await session.execute(
        select(MemoryWriteEvent).where(MemoryWriteEvent.run_id == run_id).order_by(MemoryWriteEvent.created_at)
    )
    return list(result.scalars().all())


class _FakeLongTermRepository:
    def __init__(self) -> None:
        self.insert_kwargs = None
        self.event_kwargs = None

    async def check_tombstone_before_write(self, **kwargs):
        return None

    async def retire_expired_current_by_content_hash(self, **kwargs) -> None:
        return None

    async def retire_unpublished_current_by_content_hash(self, **kwargs) -> None:
        return None

    async def get_active_by_content_hash(self, **kwargs):
        return None

    async def insert_memory(self, candidate, **kwargs):
        self.insert_kwargs = kwargs
        return SimpleNamespace(id=uuid.uuid4(), review_status=kwargs["review_status"])

    async def emit_write_event(self, **kwargs):
        self.event_kwargs = kwargs
        return SimpleNamespace(id=uuid.uuid4())


@pytest.mark.asyncio
async def test_non_preference_memory_kind_is_skipped_before_insert_without_database() -> None:
    repository = _FakeLongTermRepository()
    service = LongTermMemoryService(repository)  # type: ignore[arg-type]
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    candidate = LongTermMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id="merchant-1",
        memory_kind="fact",
        content="Current order ORD-1001 status is delivered.",
        source_type="deterministic_tool_result",
        source_ref={
            "source_type": "deterministic_tool_result",
            "run_id": str(run_id),
            "business_object_type": "order",
            "business_object_id": "ORD-1001",
        },
        pii_classification="none",
    )

    result = await service.write_memory(candidate)

    assert result.status == "skipped"
    assert result.review_status is None
    assert result.decision == "skip"
    assert result.reason_code == "not_preference_memory_kind"
    assert repository.insert_kwargs is None
    assert repository.event_kwargs is not None
    assert repository.event_kwargs["decision"] == "skip"
    assert repository.event_kwargs["reason_code"] == "not_preference_memory_kind"
    assert repository.event_kwargs["policy_version"] == "memory_write_policy.v1"
    assert repository.event_kwargs["blocked_by"] == ["memory_kind"]
    assert repository.event_kwargs["authority_class"] == "contextual_only"


@pytest.mark.asyncio
async def test_disallowed_source_type_is_skipped_before_insert_without_database() -> None:
    repository = _FakeLongTermRepository()
    service = LongTermMemoryService(repository)  # type: ignore[arg-type]
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    candidate = LongTermMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id="merchant-1",
        memory_kind="preference",
        content="Merchant prefers concise refund summaries.",
        source_type="deterministic_tool_result",
        source_ref={"source_type": "deterministic_tool_result", "run_id": str(run_id)},
        pii_classification="none",
    )

    result = await service.write_memory(candidate)

    assert result.status == "skipped"
    assert result.review_status is None
    assert result.reason_code == "source_type_not_allowed"
    assert repository.insert_kwargs is None
    assert repository.event_kwargs is not None
    assert repository.event_kwargs["decision"] == "skip"
    assert repository.event_kwargs["reason_code"] == "source_type_not_allowed"
    assert repository.event_kwargs["blocked_by"] == ["source_type_not_allowed"]


@pytest.mark.asyncio
async def test_hard_rule_human_reviewed_preference_is_skipped_before_insert_without_database() -> None:
    repository = _FakeLongTermRepository()
    service = LongTermMemoryService(repository)  # type: ignore[arg-type]
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    candidate = LongTermMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id="merchant-1",
        memory_kind="preference",
        content="Merchant rule says must refund below 10 yuan.",
        source_type="human_reviewed",
        source_ref={"source_type": "human_reviewed", "run_id": str(run_id)},
        pii_classification="none",
    )

    result = await service.write_memory(candidate)

    assert result.status == "skipped"
    assert result.review_status is None
    assert result.reason_code == "hard_rule_not_preference"
    assert repository.insert_kwargs is None
    assert repository.event_kwargs is not None
    assert repository.event_kwargs["decision"] == "skip"
    assert repository.event_kwargs["reason_code"] == "hard_rule_not_preference"
    assert repository.event_kwargs["blocked_by"] == ["preference_text"]


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
    assert events[-1].tenant_id == row.tenant_id
    assert events[-1].run_id == run_id
    assert events[-1].source_ref_json["source_type"] == "explicit_user_preference"
    assert events[-1].candidate_hash == result.candidate_hash


@pytest.mark.asyncio
async def test_sensitive_long_term_memory_is_not_prompt_retrieved(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id)

    result = await service.write_memory(candidate)
    row = await session.get(LongTermMemory, result.memory_id)
    assert row is not None
    row.pii_classification = "sensitive"
    await session.flush()
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )

    assert retrieved == []


@pytest.mark.asyncio
async def test_duplicate_active_long_term_write_returns_skipped_existing_memory(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id)

    first = await service.write_memory(candidate)
    duplicate = await service.write_memory(candidate)
    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == candidate.tenant_id,
                    LongTermMemory.scope_type == candidate.scope_type,
                    LongTermMemory.scope_id == candidate.scope_id,
                    LongTermMemory.content_hash == first.content_hash,
                    LongTermMemory.deleted_at.is_(None),
                    LongTermMemory.is_current.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    events = await _events(session, run_id)

    assert duplicate.status == "skipped"
    assert duplicate.memory_id == first.memory_id
    assert duplicate.review_status == "auto_approved"
    assert duplicate.reason_code == "duplicate_active_identity"
    assert [row.id for row in rows] == [first.memory_id]
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "duplicate_active_identity"
    assert events[-1].memory_id == first.memory_id


@pytest.mark.asyncio
async def test_expired_current_long_term_memory_does_not_block_fresh_same_content_write(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    now = datetime.now(UTC)
    expired_candidate = _candidate(
        seeded_session,
        run_id=run_id,
        expires_at=now - timedelta(seconds=1),
    )

    expired = await service.write_memory(expired_candidate, now=now)
    refreshed = await service.write_memory(_candidate(seeded_session, run_id=run_id), now=now)
    expired_row = await session.get(LongTermMemory, expired.memory_id)
    refreshed_row = await session.get(LongTermMemory, refreshed.memory_id)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=expired_candidate.tenant_id,
        scope_type=expired_candidate.scope_type,
        scope_id=expired_candidate.scope_id,
        now=now,
    )

    assert refreshed.status == "written"
    assert refreshed.memory_id != expired.memory_id
    assert expired_row is not None
    assert refreshed_row is not None
    assert expired_row.is_current is False
    assert refreshed_row.is_current is True
    assert [row.memory_id for row in retrieved] == [str(refreshed_row.id)]


@pytest.mark.asyncio
async def test_deterministic_durable_source_is_skipped(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Confirmed merchant resolution SLA is two business days.",
            source_type="deterministic_tool_result",
            source_ref_business_object_type="merchant",
        )
    )

    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == seeded_session["tenant"].id,
                    LongTermMemory.source_type == "deterministic_tool_result",
                )
            )
        )
        .scalars()
        .all()
    )
    events = await _events(session, run_id)

    assert result.status == "skipped"
    assert result.review_status is None
    assert result.reason_code == "source_type_not_allowed"
    assert rows == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "source_type_not_allowed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_type", "business_object_type"),
    [
        ("deterministic_tool_result", "order"),
        ("confirmed_business_outcome", "refund"),
        ("approved_approval_state", "refund_case"),
    ],
)
async def test_current_business_object_long_term_candidate_is_skipped(
    session: AsyncSession,
    seeded_session: dict,
    source_type: str,
    business_object_type: str,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        content=f"Current {business_object_type} ORD-1001 status is approved.",
        source_type=source_type,
        source_ref_business_object_type=business_object_type,
        source_ref_business_object_id="ORD-1001",
    )

    result = await service.write_memory(candidate)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )

    events = await _events(session, run_id)
    assert result.status == "skipped"
    assert result.review_status is None
    assert result.decision == "skip"
    assert result.reason_code == "source_type_not_allowed"
    assert result.memory_id is None
    assert retrieved == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "source_type_not_allowed"


@pytest.mark.asyncio
async def test_llm_candidate_is_skipped(session: AsyncSession, seeded_session: dict) -> None:
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

    events = await _events(session, run_id)
    assert result.status == "skipped"
    assert result.review_status is None
    assert result.reason_code == "source_type_not_allowed"
    assert result.memory_id is None
    assert retrieved == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "source_type_not_allowed"


@pytest.mark.asyncio
async def test_pending_long_term_candidate_does_not_block_later_auto_approved_same_content_write(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    pending_run_id = await _insert_run(session, seeded_session, thread_id="pending-long-term-candidate")
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    content = "Merchant prefers invoice follow-ups in concise summaries."
    pending_candidate = _candidate(
        seeded_session,
        run_id=pending_run_id,
        content=content,
        source_type="semantic_episode_candidate",
    )
    pending_result = await service.write_memory(pending_candidate)

    trusted_run_id = await _insert_run(session, seeded_session, thread_id="trusted-long-term-write")
    trusted_result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=trusted_run_id,
            content=content,
            source_type="explicit_user_preference",
        )
    )
    pending_row = await session.get(LongTermMemory, pending_result.memory_id)
    trusted_row = await session.get(LongTermMemory, trusted_result.memory_id)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=pending_candidate.tenant_id,
        scope_type=pending_candidate.scope_type,
        scope_id=pending_candidate.scope_id,
    )

    assert pending_result.status == "needs_review"
    assert trusted_result.status == "written"
    assert pending_row is not None
    assert trusted_row is not None
    assert pending_row.review_status == "needs_review"
    assert pending_row.is_current is False
    assert trusted_row.review_status == "auto_approved"
    assert trusted_row.is_current is True
    assert [row.memory_id for row in retrieved] == [str(trusted_row.id)]


@pytest.mark.asyncio
@pytest.mark.parametrize("pii_classification", ["sensitive", "prohibited"])
async def test_blocked_pii_candidate_is_skipped_and_evented(
    session: AsyncSession,
    seeded_session: dict,
    pii_classification: str,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        content="Customer phone number is 13800138000.",
        pii_classification=pii_classification,
    )

    result = await service.write_memory(candidate)
    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == candidate.tenant_id,
                    LongTermMemory.scope_type == candidate.scope_type,
                    LongTermMemory.scope_id == candidate.scope_id,
                )
            )
        )
        .scalars()
        .all()
    )
    events = await _events(session, run_id)

    assert result.status == "skipped"
    assert result.memory_id is None
    assert result.reason_code == "pii_blocked"
    assert rows == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "pii_blocked"
    assert events[-1].pii_classification == pii_classification
    assert events[-1].candidate_hash == result.candidate_hash


@pytest.mark.asyncio
async def test_review_and_delete_paths_are_evented(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Model candidate waiting for approval.",
            source_type="semantic_episode_candidate",
        )
    )
    second_result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Model candidate waiting for rejection.",
            source_type="semantic_episode_candidate",
        )
    )

    approved_event = await service.approve_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        run_id=run_id,
    )
    rejected_event = await service.reject_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=second_result.memory_id,
        run_id=run_id,
    )
    deleted_event = await service.delete_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        run_id=run_id,
    )

    first_row = await session.get(LongTermMemory, first_result.memory_id)
    second_row = await session.get(LongTermMemory, second_result.memory_id)
    assert first_row is not None
    assert second_row is not None
    assert first_row.review_status == "deleted"
    assert first_row.deleted_at is not None
    assert first_row.is_current is False
    assert second_row.review_status == "rejected"
    assert second_row.is_current is False
    assert approved_event.decision == "write"
    assert approved_event.reason_code == "approved"
    assert approved_event.memory_type == "long_term_fact"
    assert rejected_event.decision == "skip"
    assert rejected_event.reason_code == "rejected"
    assert rejected_event.memory_type == "long_term_fact"
    assert deleted_event.decision == "delete"
    assert deleted_event.reason_code == "deleted"
    assert deleted_event.memory_type == "long_term_fact"
    assert first_row.source_type == "human_reviewed"
    assert first_row.source_ref_json["source_type"] == "human_reviewed"
    assert approved_event.source_ref_json["source_type"] == "human_reviewed"
    assert approved_event.candidate_hash == build_long_term_memory_candidate_identity(first_row).candidate_hash
    assert rejected_event.candidate_hash == second_result.candidate_hash
    assert deleted_event.candidate_hash == build_long_term_memory_candidate_identity(first_row).candidate_hash


@pytest.mark.asyncio
async def test_approve_semantic_episode_preference_candidate_publishes_as_human_reviewed(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="approve-semantic-preference")
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Semantic candidate preference waiting for review.",
            source_type="semantic_episode_candidate",
        )
    )
    row = await session.get(LongTermMemory, result.memory_id)
    assert row is not None
    assert row.source_type == "semantic_episode_candidate"
    assert row.source_ref_json["source_type"] == "semantic_episode_candidate"

    event = await service.approve_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=result.memory_id,
        run_id=run_id,
    )
    await session.refresh(row)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=row.tenant_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
    )

    assert row.review_status == "approved"
    assert row.is_current is True
    assert row.source_type == "human_reviewed"
    assert row.source_ref_json["source_type"] == "human_reviewed"
    assert row.source_ref_json["run_id"] == str(run_id)
    assert row.source_identity_hash == build_long_term_memory_candidate_identity(row).source_identity_hash
    assert event.decision == "write"
    assert event.source_ref_json["source_type"] == "human_reviewed"
    assert event.candidate_hash == build_long_term_memory_candidate_identity(row).candidate_hash
    assert event.candidate_hash != result.candidate_hash
    assert [item.memory_id for item in retrieved] == [str(row.id)]
    assert retrieved[0].source_type == "human_reviewed"


@pytest.mark.asyncio
async def test_hard_rule_semantic_episode_candidate_is_skipped_and_unretrievable(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="hard-rule-semantic-preference")
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Merchant says must refund below 10 yuan.",
            source_type="semantic_episode_candidate",
        )
    )
    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == seeded_session["tenant"].id,
                    LongTermMemory.content == "Merchant says must refund below 10 yuan.",
                )
            )
        )
        .scalars()
        .all()
    )
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=seeded_session["tenant"].id,
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
    )
    events = await _events(session, run_id)

    assert result.status == "skipped"
    assert result.memory_id is None
    assert result.review_status is None
    assert result.reason_code == "hard_rule_not_preference"
    assert rows == []
    assert retrieved == []
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "hard_rule_not_preference"
    assert events[-1].blocked_by_json == ["preference_text"]


@pytest.mark.asyncio
async def test_approve_hard_rule_pending_preference_candidate_raises_soft_preference_required(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="approve-hard-rule-preference")
    row = _pending_long_term_row(
        seeded_session,
        run_id=run_id,
        content="Merchant says must refund below 10 yuan.",
        memory_kind="preference",
    )
    session.add(row)
    await session.flush()
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    with pytest.raises(ValueError, match="long-term approval requires soft preference content"):
        await service.approve_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=row.id,
            run_id=run_id,
        )

    await session.refresh(row)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=row.tenant_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
    )
    assert row.review_status == "needs_review"
    assert row.is_current is False
    assert row.source_type == "semantic_episode_candidate"
    assert row.source_ref_json["source_type"] == "semantic_episode_candidate"
    assert retrieved == []


@pytest.mark.asyncio
async def test_approve_non_preference_long_term_candidate_raises_preference_required(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="approve-non-preference")
    row = _pending_long_term_row(
        seeded_session,
        run_id=run_id,
        content="Non-preference pending long-term row must not be approved.",
        memory_kind="fact",
    )
    session.add(row)
    await session.flush()
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    with pytest.raises(ValueError, match="long-term approval requires preference memory"):
        await service.approve_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=row.id,
            run_id=run_id,
        )

    await session.refresh(row)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=row.tenant_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
    )
    assert row.review_status == "needs_review"
    assert row.is_current is False
    assert row.source_type == "semantic_episode_candidate"
    assert row.source_ref_json["source_type"] == "semantic_episode_candidate"
    assert retrieved == []


@pytest.mark.asyncio
async def test_long_term_review_actions_require_needs_review_active_state(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    auto_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))

    with pytest.raises(ValueError, match="needs_review"):
        await service.approve_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=auto_result.memory_id,
            run_id=run_id,
        )
    with pytest.raises(ValueError, match="needs_review"):
        await service.reject_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=auto_result.memory_id,
            run_id=run_id,
        )

    pending_result = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=run_id,
            content="Model candidate that will be rejected.",
            source_type="semantic_episode_candidate",
        )
    )
    await service.reject_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=pending_result.memory_id,
        run_id=run_id,
    )
    with pytest.raises(ValueError, match="needs_review"):
        await service.approve_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=pending_result.memory_id,
            run_id=run_id,
        )

    replacement_run_id = await _insert_run(session, seeded_session, thread_id="long-term-invalid-review")
    replacement_result = await service.supersede_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=auto_result.memory_id,
        replacement_candidate=_candidate(
            seeded_session,
            run_id=replacement_run_id,
            content="Auto-approved replacement.",
        ),
        run_id=replacement_run_id,
        reason_code="correction",
    )
    with pytest.raises(ValueError, match="needs_review"):
        await service.reject_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=auto_result.memory_id,
            run_id=replacement_run_id,
        )
    deleted_event = await service.delete_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=replacement_result.memory_id,
        run_id=replacement_run_id,
    )
    assert deleted_event.decision == "delete"
    with pytest.raises(ValueError, match="needs_review"):
        await service.approve_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=replacement_result.memory_id,
            run_id=replacement_run_id,
        )


@pytest.mark.asyncio
async def test_supersede_memory_updates_chain_and_emits_event(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))

    replacement_run_id = await _insert_run(session, seeded_session, thread_id="long-term-memory-supersede")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Merchant prefers concise refund summaries and escalation notes.",
    )

    result = await service.supersede_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        replacement_candidate=replacement,
        run_id=replacement_run_id,
        reason_code="correction",
    )

    previous = await session.get(LongTermMemory, first_result.memory_id)
    replacement_row = await session.get(LongTermMemory, result.memory_id)
    current_rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == replacement.tenant_id,
                    LongTermMemory.scope_type == replacement.scope_type,
                    LongTermMemory.scope_id == replacement.scope_id,
                    LongTermMemory.is_current.is_(True),
                    LongTermMemory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    events = await _events(session, replacement_run_id)

    assert previous is not None
    assert replacement_row is not None
    assert previous.review_status == "superseded"
    assert previous.is_current is False
    assert previous.superseded_by == replacement_row.id
    assert replacement_row.supersedes == previous.id
    assert replacement_row.is_current is True
    assert [row.id for row in current_rows] == [replacement_row.id]
    assert result.status == "written"
    assert result.decision == "supersede"
    assert events[-1].decision == "supersede"
    assert events[-1].reason_code == "correction"


@pytest.mark.asyncio
async def test_similar_long_term_preferences_do_not_auto_merge_without_supersede(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    first_run_id = await _insert_run(session, seeded_session, thread_id="similar-preference-first")
    second_run_id = await _insert_run(session, seeded_session, thread_id="similar-preference-second")
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=first_run_id,
            content="Merchant prefers concise refund explanations.",
            source_type="explicit_user_preference",
        )
    )
    second = await service.write_memory(
        _candidate(
            seeded_session,
            run_id=second_run_id,
            content="Merchant prefers concise refund explanations with evidence first.",
            source_type="explicit_user_preference",
        )
    )

    rows = (
        (
            await session.execute(
                select(LongTermMemory)
                .where(
                    LongTermMemory.tenant_id == seeded_session["tenant"].id,
                    LongTermMemory.scope_type == "merchant",
                    LongTermMemory.scope_id == str(seeded_session["merchant"].id),
                    LongTermMemory.is_current.is_(True),
                    LongTermMemory.deleted_at.is_(None),
                )
                .order_by(LongTermMemory.created_at)
            )
        )
        .scalars()
        .all()
    )
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=seeded_session["tenant"].id,
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
    )

    assert first.status == "written"
    assert second.status == "written"
    assert {row.id for row in rows} == {first.memory_id, second.memory_id}
    assert {row.content for row in rows} == {
        "Merchant prefers concise refund explanations.",
        "Merchant prefers concise refund explanations with evidence first.",
    }
    assert {row.memory_id for row in retrieved} == {str(first.memory_id), str(second.memory_id)}


@pytest.mark.asyncio
async def test_forget_tombstone_blocks_same_content_and_source_identity_rewrite(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, thread_id="long-term-forget-tombstone")
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        content="Merchant prefers concise follow-up language.",
        source_type="explicit_user_preference",
    )
    first = await service.write_memory(candidate)
    tombstone_event = await service.forget_long_term_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first.memory_id,
        run_id=run_id,
        reason_code="user_deleted",
    )

    rewrite = await service.write_memory(candidate)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )

    assert tombstone_event.decision == "tombstone"
    assert rewrite.status == "skipped"
    assert rewrite.reason_code == "tombstone_match"
    assert rewrite.memory_id is None
    assert retrieved == []


@pytest.mark.asyncio
async def test_supersede_memory_requires_current_published_previous(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))
    await service.delete_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        run_id=run_id,
    )
    replacement_run_id = await _insert_run(session, seeded_session, thread_id="invalid-supersede-anchor")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Replacement must not attach to deleted memory.",
    )

    with pytest.raises(ValueError, match="current published"):
        await service.supersede_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=first_result.memory_id,
            replacement_candidate=replacement,
            run_id=replacement_run_id,
            reason_code="correction",
        )

    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == replacement.tenant_id,
                    LongTermMemory.scope_type == replacement.scope_type,
                    LongTermMemory.scope_id == replacement.scope_id,
                    LongTermMemory.content == replacement.content,
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


@pytest.mark.asyncio
async def test_review_required_supersede_keeps_previous_memory_current_until_approved(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))
    replacement_run_id = await _insert_run(session, seeded_session, thread_id="long-term-pending-supersede")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Model-suggested replacement pending review.",
        source_type="semantic_episode_candidate",
    )

    result = await service.supersede_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        replacement_candidate=replacement,
        run_id=replacement_run_id,
        reason_code="correction",
    )
    previous = await session.get(LongTermMemory, first_result.memory_id)
    pending = await session.get(LongTermMemory, result.memory_id)
    before_approval = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=replacement.tenant_id,
        scope_type=replacement.scope_type,
        scope_id=replacement.scope_id,
    )

    assert result.status == "needs_review"
    assert result.decision == "needs_review"
    assert previous is not None
    assert pending is not None
    assert previous.review_status == "auto_approved"
    assert previous.is_current is True
    assert previous.superseded_by is None
    assert pending.review_status == "needs_review"
    assert pending.is_current is False
    assert pending.supersedes == previous.id
    assert [row.memory_id for row in before_approval] == [str(previous.id)]

    await service.approve_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=pending.id,
        run_id=replacement_run_id,
    )
    await session.refresh(previous)
    await session.refresh(pending)
    after_approval = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=replacement.tenant_id,
        scope_type=replacement.scope_type,
        scope_id=replacement.scope_id,
    )

    assert previous.review_status == "superseded"
    assert previous.is_current is False
    assert previous.superseded_by == pending.id
    assert pending.review_status == "approved"
    assert pending.is_current is True
    assert pending.source_type == "human_reviewed"
    assert pending.source_ref_json["source_type"] == "human_reviewed"
    assert [row.memory_id for row in after_approval] == [str(pending.id)]
    assert after_approval[0].source_type == "human_reviewed"


@pytest.mark.asyncio
async def test_expired_pending_supersede_cannot_be_approved_and_keeps_previous_current(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))
    now = datetime.now(UTC)
    replacement_run_id = await _insert_run(session, seeded_session, thread_id="expired-pending-supersede")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Pending replacement that expires before approval.",
        source_type="semantic_episode_candidate",
        expires_at=now + timedelta(seconds=1),
    )

    result = await service.supersede_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        replacement_candidate=replacement,
        run_id=replacement_run_id,
        reason_code="correction",
        now=now,
    )
    previous = await session.get(LongTermMemory, first_result.memory_id)
    pending = await session.get(LongTermMemory, result.memory_id)
    assert previous is not None
    assert pending is not None

    with pytest.raises(ValueError, match="unexpired"):
        await service.approve_memory(
            tenant_id=seeded_session["tenant"].id,
            memory_id=result.memory_id,
            run_id=replacement_run_id,
            now=now + timedelta(seconds=2),
        )

    await session.refresh(previous)
    await session.refresh(pending)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=replacement.tenant_id,
        scope_type=replacement.scope_type,
        scope_id=replacement.scope_id,
        now=now + timedelta(seconds=2),
    )

    assert previous.review_status == "auto_approved"
    assert previous.is_current is True
    assert previous.superseded_by is None
    assert pending.review_status == "needs_review"
    assert pending.is_current is False
    assert pending.source_type == "semantic_episode_candidate"
    assert [row.memory_id for row in retrieved] == [str(previous.id)]


@pytest.mark.asyncio
async def test_expired_auto_approved_supersede_replacement_is_skipped_without_mutating_previous(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))
    now = datetime.now(UTC)
    replacement_run_id = await _insert_run(session, seeded_session, thread_id="expired-auto-supersede")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Expired replacement must not hide current memory.",
        expires_at=now - timedelta(seconds=1),
    )

    result = await service.supersede_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        replacement_candidate=replacement,
        run_id=replacement_run_id,
        reason_code="correction",
        now=now,
    )
    previous = await session.get(LongTermMemory, first_result.memory_id)
    assert previous is not None
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=replacement.tenant_id,
        scope_type=replacement.scope_type,
        scope_id=replacement.scope_id,
        now=now,
    )
    events = await _events(session, replacement_run_id)

    assert result.status == "skipped"
    assert result.reason_code == "expired_candidate"
    assert result.memory_id is None
    assert previous.review_status == "auto_approved"
    assert previous.is_current is True
    assert previous.superseded_by is None
    assert [row.memory_id for row in retrieved] == [str(previous.id)]
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "expired_candidate"


@pytest.mark.asyncio
async def test_supersede_memory_skips_prohibited_pii_replacement(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    first_result = await service.write_memory(_candidate(seeded_session, run_id=run_id))
    replacement_run_id = await _insert_run(session, seeded_session, thread_id="long-term-memory-pii-supersede")
    replacement = _candidate(
        seeded_session,
        run_id=replacement_run_id,
        content="Customer phone number is 13800138000.",
        pii_classification="prohibited",
    )

    result = await service.supersede_memory(
        tenant_id=seeded_session["tenant"].id,
        memory_id=first_result.memory_id,
        replacement_candidate=replacement,
        run_id=replacement_run_id,
        reason_code="correction",
    )
    previous = await session.get(LongTermMemory, first_result.memory_id)
    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == replacement.tenant_id,
                    LongTermMemory.scope_type == replacement.scope_type,
                    LongTermMemory.scope_id == replacement.scope_id,
                    LongTermMemory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    events = await _events(session, replacement_run_id)

    assert result.status == "skipped"
    assert result.reason_code == "pii_blocked"
    assert result.memory_id is None
    assert previous is not None
    assert previous.review_status == "auto_approved"
    assert previous.is_current is True
    assert previous.superseded_by is None
    assert [row.id for row in rows] == [first_result.memory_id]
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "pii_blocked"
