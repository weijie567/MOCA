from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    AgentRun,
    CaseMemory,
    CaseMemoryIdentityClaim,
    CaseMemoryLineageLink,
    MemoryTombstone,
    MemoryWriteEvent,
)
from src.memory.case_memory import CASE_MEMORY_TYPE, CaseMemoryRepository, CaseMemoryService
from src.memory.schemas import CaseMemoryCorrection, CaseMemoryReviewDecision, CaseMemoryWriteCandidate


async def _insert_run(session: AsyncSession, seeded_session: dict, *, marker: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=f"case-memory-concurrency:{marker}",
            input_query="case memory lifecycle race",
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
    marker: str,
    source_event_id: str | None = None,
    expires_at: datetime | None = None,
) -> CaseMemoryWriteCandidate:
    refund_case = seeded_session["refund_case"]
    return CaseMemoryWriteCandidate(
        tenant_id=refund_case.tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(refund_case.id),
        case_type="refund_dispute",
        summary="Concurrent exact identity precedent.",
        excerpt="Reviewed context only.",
        applicability="Applies only to the tested lifecycle race.",
        outcome="Support completed review.",
        caveats="Not policy or action authority.",
        source_type="llm_candidate",
        source_ref={
            "source_type": "llm_candidate",
            "run_id": str(run_id),
            "agent_run_id": str(run_id),
            "event_id": source_event_id or f"case-memory-race:{marker}",
            "business_object_type": "refund_case",
            "business_object_id": str(refund_case.id),
            "outcome_id": f"outcome:{marker}",
        },
        pii_classification="none",
        expires_at=expires_at,
    )


async def _race(
    session_factory: async_sessionmaker[AsyncSession],
    *operations: Callable[[AsyncSession], Awaitable[object]],
) -> list[object]:
    barrier = asyncio.Barrier(len(operations))

    async def run(operation: Callable[[AsyncSession], Awaitable[object]]) -> object:
        async with session_factory() as race_session:
            await barrier.wait()
            try:
                result = await operation(race_session)
                await race_session.commit()
                return result
            except Exception as exc:  # noqa: BLE001 - exceptions are race outcomes under assertion
                await race_session.rollback()
                return exc

    return list(await asyncio.gather(*(run(operation) for operation in operations)))


async def _counts(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: uuid.UUID,
) -> tuple[int, int, int, int, int]:
    async with session_factory() as check:
        memories = await check.scalar(
            select(func.count()).select_from(CaseMemory).where(CaseMemory.tenant_id == tenant_id)
        )
        claims = await check.scalar(
            select(func.count())
            .select_from(CaseMemoryIdentityClaim)
            .where(CaseMemoryIdentityClaim.tenant_id == tenant_id)
        )
        links = await check.scalar(
            select(func.count()).select_from(CaseMemoryLineageLink).where(CaseMemoryLineageLink.tenant_id == tenant_id)
        )
        events = await check.scalar(
            select(func.count())
            .select_from(MemoryWriteEvent)
            .where(
                MemoryWriteEvent.tenant_id == tenant_id,
                MemoryWriteEvent.memory_type == CASE_MEMORY_TYPE,
            )
        )
        tombstones = await check.scalar(
            select(func.count())
            .select_from(MemoryTombstone)
            .where(
                MemoryTombstone.tenant_id == tenant_id,
                MemoryTombstone.memory_type == CASE_MEMORY_TYPE,
            )
        )
    return int(memories or 0), int(claims or 0), int(links or 0), int(events or 0), int(tombstones or 0)


@pytest.mark.asyncio
async def test_identical_exact_candidate_submission_race_has_one_durable_owner(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, marker="identical-submit")
    await session.commit()
    candidate = _candidate(seeded_session, run_id=run_id, marker="identical-submit")
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)

    results = await _race(
        factory,
        *[
            lambda current: CaseMemoryService(CaseMemoryRepository(current)).submit_case_memory_candidate(candidate)
            for _ in range(2)
        ],
    )

    assert not [result for result in results if isinstance(result, Exception)]
    assert sorted(result.status for result in results) == ["needs_review", "skipped"]
    assert len({result.memory_id for result in results}) == 1
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (1, 1, 0, 2, 0)


@pytest.mark.asyncio
async def test_source_distinct_race_is_not_idempotent(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session, marker="source-distinct")
    await session.commit()
    candidates = [
        _candidate(seeded_session, run_id=run_id, marker=marker, source_event_id=marker)
        for marker in ("source-a", "source-b")
    ]
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    results = await _race(
        factory,
        *[
            lambda current, candidate=candidate: CaseMemoryService(
                CaseMemoryRepository(current)
            ).submit_case_memory_candidate(candidate)
            for candidate in candidates
        ],
    )

    assert not [result for result in results if isinstance(result, Exception)]
    assert [result.status for result in results] == ["needs_review", "needs_review"]
    assert len({result.memory_id for result in results}) == 2
    assert len({result.source_identity_hash for result in results}) == 2
    assert await _counts(factory, tenant_id=candidates[0].tenant_id) == (2, 2, 0, 2, 0)


async def _seed_pending(
    session: AsyncSession,
    seeded_session: dict,
    *,
    marker: str,
    expires_at: datetime | None = None,
) -> tuple[uuid.UUID, CaseMemoryWriteCandidate]:
    run_id = await _insert_run(session, seeded_session, marker=marker)
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        marker=marker,
        expires_at=expires_at,
    )
    written = await CaseMemoryService(CaseMemoryRepository(session)).submit_case_memory_candidate(candidate)
    await session.commit()
    assert written.memory_id is not None
    return written.memory_id, candidate


def _review(
    seeded_session: dict,
    *,
    candidate: CaseMemoryWriteCandidate,
    memory_id: uuid.UUID,
    reason_code: str,
    review_reason: str,
) -> CaseMemoryReviewDecision:
    return CaseMemoryReviewDecision(
        tenant_id=candidate.tenant_id,
        run_id=candidate.run_id,
        case_memory_id=memory_id,
        reviewer_user_id=seeded_session["users"]["admin_user"].id,
        expected_lifecycle_version=1,
        reason_code=reason_code,
        review_reason=review_reason,
    )


@pytest.mark.asyncio
async def test_identical_review_retry_race_reuses_one_event(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    memory_id, candidate = await _seed_pending(session, seeded_session, marker="review-retry")
    decision = _review(
        seeded_session,
        candidate=candidate,
        memory_id=memory_id,
        reason_code="approved",
        review_reason="same review payload",
    )
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    results = await _race(
        factory,
        *[
            lambda current: CaseMemoryService(CaseMemoryRepository(current)).approve_case_memory(decision)
            for _ in range(2)
        ],
    )

    assert not [result for result in results if isinstance(result, Exception)]
    assert len({result.id for result in results}) == 1
    async with factory() as check:
        row = await check.get(CaseMemory, memory_id)
        claim = (
            await check.execute(
                select(CaseMemoryIdentityClaim).where(CaseMemoryIdentityClaim.owner_case_memory_id == memory_id)
            )
        ).scalar_one()
    assert row is not None and row.review_status == "approved" and row.lifecycle_version == 2
    assert claim.claim_state == "active" and claim.lifecycle_version == 2
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (1, 1, 0, 2, 0)


@pytest.mark.asyncio
async def test_approve_reject_race_has_one_cas_winner(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    memory_id, candidate = await _seed_pending(session, seeded_session, marker="approve-reject")
    approve = _review(
        seeded_session,
        candidate=candidate,
        memory_id=memory_id,
        reason_code="approved",
        review_reason="approve winner",
    )
    reject = approve.model_copy(update={"reason_code": "rejected", "review_reason": "reject winner"})
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    results = await _race(
        factory,
        lambda current: CaseMemoryService(CaseMemoryRepository(current)).approve_case_memory(approve),
        lambda current: CaseMemoryService(CaseMemoryRepository(current)).reject_case_memory(reject),
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    async with factory() as check:
        row = await check.get(CaseMemory, memory_id)
        claim = (
            await check.execute(
                select(CaseMemoryIdentityClaim).where(CaseMemoryIdentityClaim.owner_case_memory_id == memory_id)
            )
        ).scalar_one()
    assert row is not None and row.review_status in {"approved", "rejected"} and row.lifecycle_version == 2
    assert claim.lifecycle_version == 2
    assert claim.claim_state == ("terminal" if row.review_status == "rejected" else "active")
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (1, 1, 0, 2, 0)


@pytest.mark.asyncio
async def test_review_expiry_race_has_one_terminal_transition(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    cutoff = datetime.now(UTC) + timedelta(seconds=30)
    memory_id, candidate = await _seed_pending(
        session,
        seeded_session,
        marker="review-expiry",
        expires_at=cutoff,
    )
    decision = _review(
        seeded_session,
        candidate=candidate,
        memory_id=memory_id,
        reason_code="approved",
        review_reason="review before logical expiry",
    )
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    results = await _race(
        factory,
        lambda current: CaseMemoryService(CaseMemoryRepository(current)).approve_case_memory(
            decision, now=cutoff - timedelta(seconds=1)
        ),
        lambda current: CaseMemoryService(CaseMemoryRepository(current)).list_pending_review(
            tenant_id=candidate.tenant_id, now=cutoff + timedelta(seconds=1)
        ),
    )

    assert sum(isinstance(result, ValueError) for result in results) <= 1
    async with factory() as check:
        row = await check.get(CaseMemory, memory_id)
        claim = (
            await check.execute(
                select(CaseMemoryIdentityClaim).where(CaseMemoryIdentityClaim.owner_case_memory_id == memory_id)
            )
        ).scalar_one()
    assert row is not None and row.review_status in {"approved", "superseded"}
    assert row.lifecycle_version == claim.lifecycle_version == 2
    assert claim.claim_state == ("terminal" if row.review_status == "superseded" else "active")
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (1, 1, 0, 2, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_action", ["reject", "expiry", "delete", "tombstone"])
async def test_delayed_exact_submit_cannot_revive_terminal_claim(
    session: AsyncSession,
    seeded_session: dict,
    terminal_action: str,
) -> None:
    cutoff = datetime.now(UTC) + timedelta(seconds=30)
    memory_id, candidate = await _seed_pending(
        session,
        seeded_session,
        marker=f"delayed-{terminal_action}",
        expires_at=cutoff if terminal_action == "expiry" else None,
    )
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    terminal_committed = asyncio.Event()
    barrier = asyncio.Barrier(2)

    async def terminal_worker() -> object:
        async with factory() as current:
            await barrier.wait()
            service = CaseMemoryService(CaseMemoryRepository(current))
            if terminal_action == "reject":
                result = await service.reject_case_memory(
                    _review(
                        seeded_session,
                        candidate=candidate,
                        memory_id=memory_id,
                        reason_code="rejected",
                        review_reason="terminal rejection",
                    )
                )
            elif terminal_action == "expiry":
                result = await service.list_pending_review(
                    tenant_id=candidate.tenant_id,
                    now=cutoff + timedelta(seconds=1),
                )
            elif terminal_action == "delete":
                result = await service.delete_case_memory(
                    tenant_id=candidate.tenant_id,
                    case_memory_id=memory_id,
                    run_id=candidate.run_id,
                    expected_lifecycle_version=1,
                )
            else:
                result = await service.forget_case_memory(
                    tenant_id=candidate.tenant_id,
                    case_memory_id=memory_id,
                    run_id=candidate.run_id,
                    expected_lifecycle_version=1,
                )
            await current.commit()
            terminal_committed.set()
            return result

    async def delayed_worker() -> object:
        async with factory() as current:
            await barrier.wait()
            await terminal_committed.wait()
            result = await CaseMemoryService(CaseMemoryRepository(current)).submit_case_memory_candidate(candidate)
            await current.commit()
            return result

    terminal_result, delayed = await asyncio.gather(terminal_worker(), delayed_worker())
    assert terminal_result is not None
    assert delayed.status == "error" and delayed.memory_id is None
    assert delayed.reason_code == "identity_conflict"
    async with factory() as check:
        row = await check.get(CaseMemory, memory_id)
        claim = (
            await check.execute(
                select(CaseMemoryIdentityClaim).where(CaseMemoryIdentityClaim.owner_case_memory_id == memory_id)
            )
        ).scalar_one()
    assert row is not None and row.lifecycle_version == claim.lifecycle_version == 2
    assert claim.claim_state == "terminal"
    expected_tombstones = 1 if terminal_action in {"delete", "tombstone"} else 0
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (1, 1, 0, 3, expected_tombstones)


@pytest.mark.asyncio
async def test_correction_duplicate_submit_race_preserves_lineage_and_two_claims(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    memory_id, candidate = await _seed_pending(session, seeded_session, marker="correction-submit")
    correction = CaseMemoryCorrection(
        tenant_id=candidate.tenant_id,
        run_id=candidate.run_id,
        case_memory_id=memory_id,
        reviewer_user_id=seeded_session["users"]["admin_user"].id,
        expected_lifecycle_version=1,
        reason_code="corrected",
        review_reason="correction race winner",
        summary="Corrected concurrent exact identity precedent.",
        excerpt="Corrected reviewed context only.",
    )
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    results = await _race(
        factory,
        lambda current: CaseMemoryService(CaseMemoryRepository(current)).correct_case_memory(correction),
        lambda current: CaseMemoryService(CaseMemoryRepository(current)).submit_case_memory_candidate(candidate),
    )

    assert not [result for result in results if isinstance(result, Exception)]
    correction_event, duplicate = results
    assert duplicate.status in {"skipped", "error"}
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (2, 2, 1, 3, 0)
    async with factory() as check:
        old_claim = (
            await check.execute(
                select(CaseMemoryIdentityClaim).where(CaseMemoryIdentityClaim.owner_case_memory_id == memory_id)
            )
        ).scalar_one()
        new_row = await check.get(CaseMemory, correction_event.memory_id)
        link = (
            await check.execute(
                select(CaseMemoryLineageLink).where(
                    CaseMemoryLineageLink.survivor_case_memory_id == correction_event.memory_id
                )
            )
        ).scalar_one()
    assert old_claim.claim_state == "terminal" and old_claim.terminal_status == "superseded"
    assert new_row is not None and new_row.corrects_case_memory_id == memory_id
    assert link.related_case_memory_id == memory_id and link.relation == "correction"


@pytest.mark.asyncio
async def test_identical_correction_retry_race_reuses_new_owner_and_event(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    memory_id, candidate = await _seed_pending(session, seeded_session, marker="correction-retry")
    correction = CaseMemoryCorrection(
        tenant_id=candidate.tenant_id,
        run_id=candidate.run_id,
        case_memory_id=memory_id,
        reviewer_user_id=seeded_session["users"]["admin_user"].id,
        expected_lifecycle_version=1,
        reason_code="corrected",
        review_reason="identical correction payload",
        summary="Corrected retry-safe exact identity precedent.",
        excerpt="One corrected reviewed context owner.",
    )
    factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    results = await _race(
        factory,
        *[
            lambda current: CaseMemoryService(CaseMemoryRepository(current)).correct_case_memory(correction)
            for _ in range(2)
        ],
    )

    assert not [result for result in results if isinstance(result, Exception)]
    assert len({result.id for result in results}) == 1
    assert len({result.memory_id for result in results}) == 1
    assert await _counts(factory, tenant_id=candidate.tenant_id) == (2, 2, 1, 2, 0)
