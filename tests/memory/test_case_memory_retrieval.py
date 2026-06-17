from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, CaseMemory, MemoryTombstone, MemoryWriteEvent, SessionMemory
from src.knowledge.schemas import EvidenceRefV1
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.identity import canonical_memory_content_hash, canonical_source_identity_hash
from src.memory.schemas import CaseMemoryReviewDecision, CaseMemorySearchRequest, CaseMemoryWriteCandidate


CASE_MEMORY_TYPE = "case_memory"


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str = "case-memory") -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="write or retrieve reviewed case precedent",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _embedding(first: float = 1.0) -> list[float]:
    return [first, *([0.0] * 1023)]


def _source_ref(
    *,
    source_type: str,
    run_id: uuid.UUID,
    case_id: str,
    event_id: str = "evt-case-memory-1",
) -> dict[str, str]:
    return {
        "source_type": source_type,
        "run_id": str(run_id),
        "event_id": event_id,
        "business_object_type": "refund_case",
        "business_object_id": case_id,
        "outcome_id": f"outcome-{case_id}",
    }


def _candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    source_type: str = "llm_candidate",
    summary: str = "Damaged item refund precedent with verified logistics evidence.",
    excerpt: str = "When logistics confirms damage, refund handling can be expedited after review.",
    source_ref: dict[str, str] | None = None,
    pii_classification: str = "none",
) -> CaseMemoryWriteCandidate:
    refund_case = seeded_session["refund_case"]
    return CaseMemoryWriteCandidate(
        tenant_id=refund_case.tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(refund_case.id),
        case_type="refund_dispute",
        summary=summary,
        excerpt=excerpt,
        applicability="Applies when refund dispute has confirmed damaged item evidence.",
        outcome="Refund approved after support verification.",
        caveats="Not authority for policy or action execution.",
        source_type=source_type,
        source_ref=source_ref
        or _source_ref(
            source_type=source_type,
            run_id=run_id,
            case_id=str(refund_case.id),
        ),
        policy_family="refund",
        policy_version="v1",
        policy_refs=[{"doc_key": "refund_policy", "chunk_id": "chunk-1", "policy_version": "v1"}],
        embedding=_embedding(),
        pii_classification=pii_classification,
    )


def _case_row(
    seeded_session: dict,
    *,
    tenant_id: uuid.UUID | None = None,
    scope_type: str = "case",
    scope_id: str | None = None,
    case_type: str = "refund_dispute",
    summary: str = "Reviewed damaged-item refund precedent.",
    excerpt: str = "Approved refund after evidence review.",
    review_status: str = "approved",
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
    pii_classification: str = "none",
    policy_family: str | None = "refund",
    policy_version: str | None = "v1",
    source_identity_hash: str | None = None,
    embedding: list[float] | None = None,
) -> CaseMemory:
    refund_case = seeded_session["refund_case"]
    resolved_tenant_id = tenant_id or refund_case.tenant_id
    resolved_scope_id = scope_id or str(refund_case.id)
    source_ref = {"source_type": "human_reviewed", "business_object_id": resolved_scope_id}
    return CaseMemory(
        id=uuid.uuid4(),
        tenant_id=resolved_tenant_id,
        scope_type=scope_type,
        scope_id=resolved_scope_id,
        case_type=case_type,
        summary=summary,
        excerpt=excerpt,
        applicability="Applies to reviewed refund dispute precedents.",
        outcome="Support resolved the refund dispute.",
        caveats="Precedent only; not policy evidence.",
        content_hash=canonical_memory_content_hash(memory_type=CASE_MEMORY_TYPE, content=summary),
        policy_family=policy_family,
        policy_version=policy_version,
        policy_refs_json=[{"doc_key": "refund_policy", "chunk_id": "chunk-1", "policy_version": "v1"}],
        source_ref_json=source_ref,
        source_identity_hash=source_identity_hash,
        embedding=embedding or _embedding(),
        review_status=review_status,
        pii_classification=pii_classification,
        expires_at=expires_at,
        deleted_at=deleted_at,
    )


async def _events(session: AsyncSession, run_id: uuid.UUID) -> list[MemoryWriteEvent]:
    result = await session.execute(
        select(MemoryWriteEvent).where(MemoryWriteEvent.run_id == run_id).order_by(MemoryWriteEvent.created_at)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_case_memory_candidate_requires_review_before_retrieval(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id, source_type="llm_candidate")

    result = await service.submit_case_memory_candidate(candidate)
    before_approval = await service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            case_type=candidate.case_type,
            policy_family="refund",
            policy_version="v1",
            query_embedding=_embedding(),
        )
    )
    approved_event = await service.approve_case_memory(
        CaseMemoryReviewDecision(
            tenant_id=candidate.tenant_id,
            run_id=run_id,
            case_memory_id=result.memory_id,
            reviewer_user_id=seeded_session["users"]["approval_manager"].id,
            reason_code="approved",
            review_reason="reviewed damaged item precedent",
        )
    )
    after_approval = await service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            case_type=candidate.case_type,
            policy_family="refund",
            policy_version="v1",
            query_embedding=_embedding(),
        )
    )

    row = await session.get(CaseMemory, result.memory_id)
    assert result.status == "needs_review"
    assert result.review_status == "needs_review"
    assert row is not None
    assert row.review_status == "approved"
    assert row.content_hash == result.content_hash
    assert row.source_identity_hash == result.source_identity_hash
    assert row.reviewed_by_user_id == seeded_session["users"]["approval_manager"].id
    assert row.review_reason == "reviewed damaged item precedent"
    assert before_approval.items == []
    assert [item.case_memory_id for item in after_approval.items] == [str(row.id)]
    assert approved_event.memory_type == CASE_MEMORY_TYPE
    assert approved_event.decision == "write"
    assert approved_event.reason_code == "approved"


@pytest.mark.asyncio
async def test_case_memory_candidate_event_is_observable(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id, source_type="summary_candidate")

    result = await service.submit_case_memory_candidate(candidate)
    events = await _events(session, run_id)

    assert result.status == "needs_review"
    assert events[-1].memory_type == CASE_MEMORY_TYPE
    assert events[-1].memory_id == result.memory_id
    assert events[-1].decision == "needs_review"
    assert events[-1].reason_code == "requires_review"
    assert events[-1].candidate_hash == result.candidate_hash
    assert events[-1].source_ref_json["source_type"] == "summary_candidate"


@pytest.mark.asyncio
async def test_case_memory_reject_decision_is_observable(session: AsyncSession, seeded_session: dict) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id, source_type="cross_case_pattern_candidate")
    write_result = await service.submit_case_memory_candidate(candidate)

    reject_event = await service.reject_case_memory(
        CaseMemoryReviewDecision(
            tenant_id=candidate.tenant_id,
            run_id=run_id,
            case_memory_id=write_result.memory_id,
            reviewer_user_id=seeded_session["users"]["approval_manager"].id,
            reason_code="rejected",
            review_reason="not a reviewed precedent",
        )
    )
    retrieved = await service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            case_type=candidate.case_type,
            query_embedding=_embedding(),
        )
    )
    row = await session.get(CaseMemory, write_result.memory_id)

    assert row is not None
    assert row.review_status == "rejected"
    assert row.reviewed_by_user_id == seeded_session["users"]["approval_manager"].id
    assert reject_event.memory_type == CASE_MEMORY_TYPE
    assert reject_event.decision == "skip"
    assert reject_event.reason_code == "rejected"
    assert reject_event.candidate_hash == write_result.candidate_hash
    assert retrieved.items == []


@pytest.mark.asyncio
async def test_case_memory_retrieval_applies_metadata_filters_before_results(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime.now(UTC)
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    scope_id = str(seeded_session["refund_case"].id)
    visible = _case_row(seeded_session, summary="Visible reviewed refund precedent.")
    visible_auto = _case_row(
        seeded_session,
        summary="Visible auto-approved refund precedent.",
        review_status="auto_approved",
        embedding=_embedding(0.95),
    )
    filtered_rows = [
        _case_row(seeded_session, summary="Needs review must not surface.", review_status="needs_review"),
        _case_row(seeded_session, summary="Rejected must not surface.", review_status="rejected"),
        _case_row(seeded_session, summary="Deleted must not surface.", deleted_at=now),
        _case_row(seeded_session, summary="Expired must not surface.", expires_at=now - timedelta(seconds=1)),
        _case_row(seeded_session, summary="Prohibited must not surface.", pii_classification="prohibited"),
        _case_row(seeded_session, summary="Cross tenant must not surface.", tenant_id=other_tenant_id),
        _case_row(seeded_session, summary="Wrong case type must not surface.", case_type="chargeback"),
        _case_row(seeded_session, summary="Wrong policy family must not surface.", policy_family="shipping"),
        _case_row(seeded_session, summary="Wrong policy version must not surface.", policy_version="v2"),
    ]
    tombstoned = _case_row(seeded_session, summary="Tombstoned must not surface.")
    source_hash = canonical_source_identity_hash({"source_type": "human_reviewed", "event_id": "evt-tombstoned"})
    source_tombstoned = _case_row(
        seeded_session,
        summary="Source tombstoned must not surface.",
        source_identity_hash=source_hash,
    )
    session.add_all([visible, visible_auto, *filtered_rows, tombstoned, source_tombstoned])
    await session.flush()
    session.add_all(
        [
            MemoryTombstone(
                tenant_id=tenant_id,
                memory_type=CASE_MEMORY_TYPE,
                scope_type="case",
                scope_id=scope_id,
                content_hash=tombstoned.content_hash,
                source_ref_json={"source_type": "human_reviewed"},
                reason_code="case_deleted",
            ),
            MemoryTombstone(
                tenant_id=tenant_id,
                memory_type=CASE_MEMORY_TYPE,
                scope_type="case",
                scope_id=scope_id,
                content_hash=None,
                source_ref_json={"source_type": "human_reviewed", "event_id": "evt-tombstoned"},
                source_identity_hash=source_hash,
                reason_code="source_deleted",
            ),
        ]
    )
    await session.flush()

    result = await CaseMemoryRepository(session).search_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="case",
            scope_id=scope_id,
            case_type="refund_dispute",
            policy_family="refund",
            policy_version="v1",
            query_embedding=_embedding(),
            limit=10,
            now=now,
        )
    )

    assert [item.case_memory_id for item in result.items] == [str(visible.id), str(visible_auto.id)]
    assert {item.excerpt for item in result.items} == {
        "Approved refund after evidence review.",
        "Approved refund after evidence review.",
    }
    assert all(item.policy_refs for item in result.items)
    assert all(item.source_refs for item in result.items)


@pytest.mark.asyncio
async def test_case_memory_text_query_filters_without_embedding(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    scope_id = str(seeded_session["refund_case"].id)
    matching = _case_row(
        seeded_session,
        summary="Refund timeout precedent for payment-channel verification.",
        excerpt="When a refund timeout mentions a payment channel, verify gateway state before advice.",
    )
    unrelated = _case_row(
        seeded_session,
        summary="Damaged item precedent after warehouse inspection.",
        excerpt="Warehouse inspection confirmed damage before refund handling.",
    )
    session.add_all([matching, unrelated])
    await session.flush()

    result = await CaseMemoryRepository(session).search_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="case",
            scope_id=scope_id,
            case_type="refund_dispute",
            policy_family="refund",
            policy_version="v1",
            query="payment-channel timeout",
            limit=10,
        )
    )

    assert [item.case_memory_id for item in result.items] == [str(matching.id)]


@pytest.mark.asyncio
async def test_case_memory_is_separate_from_session_memory(session: AsyncSession, seeded_session: dict) -> None:
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    session.add(
        SessionMemory(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id="legacy-session-precedent",
            active_slots_json={"schema_version": "session_slots.v1", "slots": {}},
            session_summary="Legacy session-derived refund precedent should never become reviewed case memory.",
            unresolved_questions_json=[],
            last_business_context_refs_json={},
        )
    )
    await session.flush()

    result = await CaseMemoryRepository(session).search_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="case",
            scope_id=str(seeded_session["refund_case"].id),
            case_type="refund_dispute",
            query_embedding=_embedding(),
        )
    )

    assert result.items == []


@pytest.mark.asyncio
async def test_case_memory_view_is_not_evidence_ref(session: AsyncSession, seeded_session: dict) -> None:
    row = _case_row(seeded_session)
    session.add(row)
    await session.flush()

    result = await CaseMemoryRepository(session).search_reviewed(
        CaseMemorySearchRequest(
            tenant_id=row.tenant_id,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
            case_type=row.case_type,
            query_embedding=_embedding(),
        )
    )

    assert len(result.items) == 1
    item_payload = result.items[0].model_dump(mode="json")
    assert set(item_payload) == {
        "case_memory_id",
        "excerpt",
        "applicability",
        "outcome",
        "caveats",
        "score",
        "policy_refs",
        "source_refs",
    }
    assert "raw_payload" not in item_payload
    assert "text_hash" not in item_payload
    assert "evidence_id" not in item_payload
    with pytest.raises(ValidationError):
        EvidenceRefV1.model_validate(item_payload)


@pytest.mark.asyncio
async def test_case_memory_tombstone_blocks_writes_by_content_hash_and_source_identity(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    repository = CaseMemoryRepository(session)
    service = CaseMemoryService(repository)
    original = _candidate(seeded_session, run_id=run_id, source_type="human_reviewed")
    write_result = await service.submit_case_memory_candidate(original)
    tombstone_event = await service.forget_case_memory(
        tenant_id=original.tenant_id,
        case_memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="case_forget",
    )

    content_blocked = await service.submit_case_memory_candidate(
        _candidate(
            seeded_session,
            run_id=run_id,
            source_type="human_reviewed",
            summary=original.summary,
            source_ref=_source_ref(
                source_type="human_reviewed",
                run_id=run_id,
                case_id=str(seeded_session["refund_case"].id),
                event_id="evt-different-case-memory-source",
            ),
        )
    )
    source_ref = _source_ref(
        source_type="deterministic_tool_result",
        run_id=run_id,
        case_id=str(seeded_session["refund_case"].id),
        event_id="evt-source-only-tombstone",
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
    source_blocked = await service.submit_case_memory_candidate(
        _candidate(
            seeded_session,
            run_id=run_id,
            source_type="deterministic_tool_result",
            summary="Different summary from the same deleted source.",
            source_ref=source_ref,
        )
    )
    events = await _events(session, run_id)

    assert tombstone_event.memory_type == CASE_MEMORY_TYPE
    assert tombstone_event.decision == "tombstone"
    assert tombstone_event.reason_code == "case_forget"
    assert content_blocked.status == "skipped"
    assert content_blocked.reason_code == "tombstone_match"
    assert content_blocked.memory_id is None
    assert source_blocked.status == "skipped"
    assert source_blocked.reason_code == "tombstone_match"
    assert source_blocked.memory_id is None
    assert [event.reason_code for event in events].count("tombstone_match") == 2
