from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AgentRun,
    CaseMemory,
    CaseMemoryIdentityClaim,
    MemoryTombstone,
    MemoryWriteEvent,
    SessionMemory,
)
from src.knowledge.evidence_identity import (
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
)
from src.knowledge.schemas import EvidenceRefV1
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.identity import (
    build_case_memory_candidate_identity,
    canonical_memory_candidate_hash,
    canonical_memory_content_hash,
    canonical_source_identity_hash,
)
from src.memory.schemas import (
    CaseMemoryProvenanceV1,
    CaseMemoryReviewDecision,
    CaseMemorySearchRequest,
    CaseMemorySourceAuthorityV1,
    CaseMemoryWriteCandidate,
)


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


_EMBEDDING_UNSET = object()


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
    policy_ref = _canonical_policy_ref(tenant_id=refund_case.tenant_id)
    candidate = CaseMemoryWriteCandidate(
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
        policy_refs=[policy_ref.model_dump(mode="json", exclude_none=True)],
        embedding=_embedding(),
        pii_classification=pii_classification,
    )
    identity = build_case_memory_candidate_identity(candidate)
    assert identity.normalized_source_ref is not None
    assert identity.source_identity_hash is not None
    provenance = CaseMemoryProvenanceV1(
        resolution_status="canonical",
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
        source_authorities=[
            CaseMemorySourceAuthorityV1(
                source_kind="policy_evidence",
                source_ref=identity.normalized_source_ref,
                source_status="success",
                source_authority_class="policy_evidence",
                evidence_refs=[policy_ref],
            )
        ],
        source_run_id=run_id,
        source_event_id=identity.normalized_source_ref.event_id,
        evidence_refs=[policy_ref],
        identity_algorithm_version="memory_identity.v1",
        identity_profile=identity.identity_profile,
        candidate_hash=identity.candidate_hash,
        content_hash=identity.content_hash,
        source_identity_hash=identity.source_identity_hash,
    )
    return candidate.model_copy(update={"provenance": provenance})


def _canonical_policy_ref(*, tenant_id: uuid.UUID) -> EvidenceRefV1:
    material = PersistedEvidenceIdentityMaterialV1(
        tenant_id=str(tenant_id),
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        document_version_id="00000000-0000-0000-0000-000000006481",
        chunk_version_id="00000000-0000-0000-0000-000000006482",
        doc_key="refund_policy",
        document_version=1,
        chunk_id="chunk-1",
        chunk_version=1,
        text_hash=f"sha256:{'d' * 64}",
    )
    resolution = mint_canonical_evidence_identity(
        material,
        expected_tenant_id=str(tenant_id),
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert resolution.identity is not None
    return EvidenceRefV1.from_canonical_identity(
        resolution.identity,
        retrieved_at="2026-08-05T09:00:00Z",
        retrieval_config_version="retrieval.v3",
        rank=1,
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
    source_type: str = "human_reviewed",
    source_ref_json: dict[str, str] | None = None,
    policy_family: str | None = "refund",
    policy_version: str | None = "v1",
    source_identity_hash: str | None = None,
    embedding: list[float] | None | object = _EMBEDDING_UNSET,
) -> CaseMemory:
    refund_case = seeded_session["refund_case"]
    resolved_tenant_id = tenant_id or refund_case.tenant_id
    resolved_scope_id = scope_id or str(refund_case.id)
    source_ref = (
        dict(source_ref_json)
        if source_ref_json is not None
        else {
            "source_type": source_type,
            "business_object_type": "refund_case",
            "business_object_id": str(refund_case.id),
        }
    )
    source_ref.setdefault("business_object_type", "refund_case")
    source_ref.setdefault("business_object_id", str(refund_case.id))
    content_for_identity = (
        "\n".join(
            part
            for part in (
                summary,
                excerpt,
                "Applies to reviewed refund dispute precedents.",
                "Support resolved the refund dispute.",
                "Precedent only; not policy evidence.",
            )
            if part
        )
        if source_type == "closed_case_cwc_candidate"
        else summary
    )
    content_hash = canonical_memory_content_hash(memory_type=CASE_MEMORY_TYPE, content=content_for_identity)
    resolved_source_identity_hash = source_identity_hash or canonical_source_identity_hash(source_ref)
    assert resolved_source_identity_hash is not None
    candidate_hash = canonical_memory_candidate_hash(
        tenant_id=str(resolved_tenant_id),
        memory_type=CASE_MEMORY_TYPE,
        scope_type=scope_type,
        scope_id=resolved_scope_id,
        content_hash=content_hash,
        source_identity_hash=resolved_source_identity_hash,
    )
    policy_ref = _canonical_policy_ref(tenant_id=resolved_tenant_id)
    source_run_id = uuid.uuid4()
    review_decision = review_status if review_status in {"approved", "rejected"} else None
    reviewer_user_id = seeded_session["users"]["admin_user"].id if review_decision else None
    reviewed_at = datetime(2026, 8, 5, 10, 0, tzinfo=UTC) if review_decision else None
    review_reason = "Seeded reviewed-memory fixture." if review_decision else None
    provenance = CaseMemoryProvenanceV1(
        resolution_status="legacy_resolved",
        tenant_id=resolved_tenant_id,
        scope_type=scope_type,
        scope_id=resolved_scope_id,
        source_authorities=[
            CaseMemorySourceAuthorityV1(
                source_kind="policy_evidence",
                source_ref=source_ref,
                source_status="success",
                source_authority_class="policy_evidence",
                evidence_refs=[policy_ref],
            )
        ],
        source_run_id=source_run_id,
        source_event_id=source_ref.get("event_id"),
        evidence_refs=[policy_ref],
        identity_algorithm_version="memory_identity.v1",
        identity_profile="nfkc_casefold_legacy",
        candidate_hash=candidate_hash,
        content_hash=content_hash,
        source_identity_hash=resolved_source_identity_hash,
        review_decision=review_decision,
        reviewer_user_id=reviewer_user_id,
        reviewed_at=reviewed_at,
        review_reason=review_reason,
    )
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
        content_hash=content_hash,
        policy_family=policy_family,
        policy_version=policy_version,
        policy_refs_json=[policy_ref.model_dump(mode="json", exclude_none=True)],
        source_ref_json=source_ref,
        source_identity_hash=resolved_source_identity_hash,
        identity_algorithm_version="memory_identity.v1",
        candidate_hash=candidate_hash,
        identity_resolution_status="legacy_resolved",
        provenance_json=provenance.model_dump(mode="json", exclude_none=True),
        lifecycle_version=2 if review_decision else 1,
        embedding=_embedding() if embedding is _EMBEDDING_UNSET else embedding,
        review_status=review_status,
        reviewed_by_user_id=reviewer_user_id,
        reviewed_at=reviewed_at,
        review_reason=review_reason,
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
            expected_lifecycle_version=1,
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
async def test_case_memory_service_lists_active_pending_review_rows(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime.now(UTC)
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    pending = _case_row(
        seeded_session,
        review_status="needs_review",
        summary="Pending case memory.",
    )
    approved = _case_row(
        seeded_session,
        review_status="approved",
        summary="Approved case memory.",
    )
    deleted_pending = _case_row(
        seeded_session,
        review_status="needs_review",
        summary="Deleted pending case memory.",
        deleted_at=now,
    )
    cross_tenant_pending = _case_row(
        seeded_session,
        tenant_id=other_tenant_id,
        review_status="needs_review",
        summary="Cross-tenant pending case memory.",
    )
    session.add_all([pending, approved, deleted_pending, cross_tenant_pending])
    await session.flush()
    session.add(
        CaseMemoryIdentityClaim(
            identity_algorithm_version=pending.identity_algorithm_version,
            tenant_id=pending.tenant_id,
            scope_type=pending.scope_type,
            scope_id=pending.scope_id,
            candidate_hash=pending.candidate_hash,
            content_hash=pending.content_hash,
            source_identity_hash=pending.source_identity_hash,
            owner_case_memory_id=pending.id,
            claim_state="active",
            lifecycle_version=pending.lifecycle_version,
        )
    )
    await session.flush()

    rows = await CaseMemoryService(CaseMemoryRepository(session)).list_pending_review(tenant_id=tenant_id)

    assert [row.id for row in rows] == [pending.id]


@pytest.mark.asyncio
async def test_duplicate_active_case_memory_write_returns_skipped_existing_memory(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _candidate(seeded_session, run_id=run_id, source_type="llm_candidate")

    first = await service.submit_case_memory_candidate(candidate)
    duplicate = await service.submit_case_memory_candidate(candidate)
    rows = (
        (
            await session.execute(
                select(CaseMemory).where(
                    CaseMemory.tenant_id == candidate.tenant_id,
                    CaseMemory.scope_type == candidate.scope_type,
                    CaseMemory.scope_id == candidate.scope_id,
                    CaseMemory.content_hash == first.content_hash,
                    CaseMemory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    events = await _events(session, run_id)

    assert first.status == "needs_review"
    assert duplicate.status == "skipped"
    assert duplicate.memory_id == first.memory_id
    assert duplicate.review_status == "needs_review"
    assert duplicate.reason_code == "duplicate_exact_identity"
    assert [row.id for row in rows] == [first.memory_id]
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "duplicate_exact_identity"
    assert events[-1].memory_id == first.memory_id


@pytest.mark.asyncio
@pytest.mark.parametrize("pii_classification", ["sensitive", "prohibited"])
async def test_blocked_pii_case_memory_candidate_is_skipped_and_evented(
    session: AsyncSession,
    seeded_session: dict,
    pii_classification: str,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _candidate(
        seeded_session,
        run_id=run_id,
        source_type="human_reviewed",
        summary="Customer phone number is 13800138000.",
        pii_classification=pii_classification,
    )

    result = await service.submit_case_memory_candidate(candidate)
    rows = (
        (
            await session.execute(
                select(CaseMemory).where(
                    CaseMemory.tenant_id == candidate.tenant_id,
                    CaseMemory.scope_type == candidate.scope_type,
                    CaseMemory.scope_id == candidate.scope_id,
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
            expected_lifecycle_version=1,
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
        _case_row(seeded_session, summary="Sensitive must not surface.", pii_classification="sensitive"),
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
async def test_approved_closed_case_candidate_merchant_retrieval_without_embedding_keeps_filters(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime.now(UTC)
    tenant_id = seeded_session["tenant"].id
    merchant_id = str(seeded_session["merchant"].id)
    wrong_merchant_id = str(seeded_session["second_merchant"].id)
    other_tenant_id = seeded_session["other_tenant"].id
    visible = _case_row(
        seeded_session,
        scope_type="merchant",
        scope_id=merchant_id,
        summary="Closed-case CWC candidate precedent for timeout refund.",
        excerpt="closed-case generated timeout refund precedent after gateway verification.",
        source_type="closed_case_cwc_candidate",
        embedding=None,
    )
    filtered_rows = [
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=wrong_merchant_id,
            summary="Wrong merchant closed-case timeout precedent must not surface.",
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Needs-review closed-case timeout precedent must not surface.",
            review_status="needs_review",
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Rejected closed-case timeout precedent must not surface.",
            review_status="rejected",
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Deleted closed-case timeout precedent must not surface.",
            deleted_at=now,
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Expired closed-case timeout precedent must not surface.",
            expires_at=now - timedelta(seconds=1),
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Sensitive closed-case timeout precedent must not surface.",
            pii_classification="sensitive",
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Prohibited closed-case timeout precedent must not surface.",
            pii_classification="prohibited",
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
        _case_row(
            seeded_session,
            tenant_id=other_tenant_id,
            scope_type="merchant",
            scope_id=merchant_id,
            summary="Cross-tenant closed-case timeout precedent must not surface.",
            source_type="closed_case_cwc_candidate",
            embedding=None,
        ),
    ]
    tombstoned = _case_row(
        seeded_session,
        scope_type="merchant",
        scope_id=merchant_id,
        summary="Tombstoned closed-case timeout precedent must not surface.",
        source_type="closed_case_cwc_candidate",
        embedding=None,
    )
    session.add_all([visible, *filtered_rows, tombstoned])
    await session.flush()
    session.add(
        MemoryTombstone(
            tenant_id=tenant_id,
            memory_type=CASE_MEMORY_TYPE,
            scope_type="merchant",
            scope_id=merchant_id,
            content_hash=tombstoned.content_hash,
            source_ref_json={"source_type": "closed_case_cwc_candidate"},
            reason_code="closed_case_deleted",
        )
    )
    await session.flush()

    result = await CaseMemoryService(CaseMemoryRepository(session)).retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="merchant",
            scope_id=merchant_id,
            case_type="refund_dispute",
            policy_family="refund",
            policy_version="v1",
            query="closed-case timeout",
            query_embedding=None,
            limit=10,
            now=now,
        )
    )

    assert [item.case_memory_id for item in result.items] == [str(visible.id)]
    assert result.items[0].source_refs[0]["source_type"] == "closed_case_cwc_candidate"
    assert result.items[0].source_refs[0]["business_object_type"] == "refund_case"


@pytest.mark.asyncio
async def test_approved_closed_case_candidate_exact_case_retrieval_without_embedding(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    case_id = str(seeded_session["refund_case"].id)
    visible = _case_row(
        seeded_session,
        scope_type="case",
        scope_id=case_id,
        summary="Closed-case CWC candidate exact audit precedent.",
        excerpt="exact case-scope closed-case generated audit precedent for refund review.",
        source_type="closed_case_cwc_candidate",
        embedding=None,
    )
    wrong_case = _case_row(
        seeded_session,
        scope_type="case",
        scope_id=str(seeded_session["second_refund_case"].id),
        summary="Wrong exact case-scope closed-case generated audit precedent.",
        source_type="closed_case_cwc_candidate",
        embedding=None,
    )
    session.add_all([visible, wrong_case])
    await session.flush()

    result = await CaseMemoryRepository(session).search_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="case",
            scope_id=case_id,
            case_type="refund_dispute",
            query="exact audit precedent",
            query_embedding=None,
            limit=10,
        )
    )

    assert [item.case_memory_id for item in result.items] == [str(visible.id)]


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
        expected_lifecycle_version=1,
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
