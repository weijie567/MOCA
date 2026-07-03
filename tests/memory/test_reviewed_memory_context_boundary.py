from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, CaseMemory, LongTermMemory, MemoryTombstone
from src.memory.case_memory import CASE_MEMORY_TYPE, CaseMemoryRepository, CaseMemoryService
from src.memory.identity import canonical_memory_content_hash, canonical_source_identity_hash
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LONG_TERM_MEMORY_TYPE, LongTermMemoryRepository
from src.memory.schemas import CaseMemorySearchRequest, CaseMemoryWriteCandidate, LongTermMemoryWriteCandidate
from src.platform.trusted_context import MerchantScopeV1, TrustedContext


async def _insert_run(session: AsyncSession, seeded_session: dict, *, thread_id: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="reviewed memory boundary",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _trusted_context(seeded_session: dict, *, merchant_ids: list[str]) -> TrustedContext:
    user = seeded_session["users"]["cs_zhang"]
    return TrustedContext(
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        role=user.role,
        permissions=["tool:get_order", "tool:get_refund_case"],
        merchant_scope=MerchantScopeV1(merchant_ids=merchant_ids),
        thread_id="thread-reviewed-memory-boundary",
        run_id=str(uuid.uuid4()),
        trace_id="trace-reviewed-memory-boundary",
    )


def _context_service(session: AsyncSession):
    from src.memory.context_service import MemoryContextService

    return MemoryContextService(
        long_term_memory_service=LongTermMemoryService(LongTermMemoryRepository(session)),
        case_memory_service=CaseMemoryService(CaseMemoryRepository(session)),
    )


def _bundle_dict(bundle: Any) -> dict[str, Any]:
    if hasattr(bundle, "model_dump"):
        return bundle.model_dump(mode="json")
    return dict(bundle)


def _write_outcome_dict(outcome: Any, *, status: str | None = None) -> dict[str, Any]:
    if hasattr(outcome, "model_dump"):
        return outcome.model_dump(mode="json")
    return {
        "status": status or ("skipped" if outcome.decision in {"delete", "tombstone", "skip"} else "written"),
        "memory_id": str(outcome.memory_id) if outcome.memory_id is not None else None,
        "decision": outcome.decision,
        "reason_code": outcome.reason_code,
        "pii_classification": outcome.pii_classification,
        "candidate_hash": outcome.candidate_hash,
        "event_id": str(outcome.id),
    }


def _memory_write_decision(
    session: AsyncSession,
    outcome: Any,
    *,
    memory_type: str,
    scope: dict[str, Any],
    status: str | None = None,
) -> dict[str, Any]:
    decision = _context_service(session).project_memory_write_decision(
        _write_outcome_dict(outcome, status=status),
        memory_type=memory_type,
        authority_class="contextual_only",
        scope=scope,
    )
    return _bundle_dict(decision)


def _long_term_candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    merchant_id: str,
    content: str,
    source_type: str = "human_reviewed",
) -> LongTermMemoryWriteCandidate:
    return LongTermMemoryWriteCandidate(
        tenant_id=seeded_session["tenant"].id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=merchant_id,
        memory_kind="preference",
        content=content,
        source_type=source_type,
        source_ref={
            "source_type": source_type,
            "run_id": str(run_id),
            "business_object_type": "merchant",
            "business_object_id": merchant_id,
        },
        pii_classification="none",
    )


def _case_candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    merchant_id: str,
    summary: str,
    source_type: str = "human_reviewed",
) -> CaseMemoryWriteCandidate:
    return CaseMemoryWriteCandidate(
        tenant_id=seeded_session["tenant"].id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=merchant_id,
        case_type="refund_dispute",
        summary=summary,
        excerpt=f"{summary} excerpt.",
        applicability="Applies only to the scoped merchant.",
        outcome="Contextual precedent only.",
        caveats="Not policy evidence or current business fact authority.",
        source_type=source_type,
        source_ref={
            "source_type": source_type,
            "run_id": str(run_id),
            "business_object_type": "merchant",
            "business_object_id": merchant_id,
        },
        pii_classification="none",
    )


def _long_term_row(
    *,
    tenant_id: uuid.UUID,
    merchant_id: str,
    content: str,
    review_status: str = "approved",
    is_current: bool = True,
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
    pii_classification: str = "none",
) -> LongTermMemory:
    return LongTermMemory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        scope_type="merchant",
        scope_id=merchant_id,
        memory_kind="preference",
        content=content,
        content_hash=canonical_memory_content_hash(memory_type=LONG_TERM_MEMORY_TYPE, content=content),
        source_type="human_reviewed",
        source_ref_json={"source_type": "human_reviewed", "business_object_id": merchant_id},
        source_identity_hash=None,
        confidence=Decimal("0.9000"),
        pii_classification=pii_classification,
        review_status=review_status,
        is_current=is_current,
        expires_at=expires_at,
        deleted_at=deleted_at,
    )


def _case_row(
    *,
    tenant_id: uuid.UUID,
    merchant_id: str,
    summary: str,
    review_status: str = "approved",
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
    pii_classification: str = "none",
    source_identity_hash: str | None = None,
) -> CaseMemory:
    return CaseMemory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        scope_type="merchant",
        scope_id=merchant_id,
        case_type="refund_dispute",
        summary=summary,
        excerpt=f"{summary} excerpt.",
        applicability="Applies only to reviewed merchant precedents.",
        outcome="Contextual only.",
        caveats="Not authority.",
        content_hash=canonical_memory_content_hash(memory_type=CASE_MEMORY_TYPE, content=summary),
        policy_refs_json=[],
        source_ref_json={"source_type": "human_reviewed", "business_object_id": merchant_id},
        source_identity_hash=source_identity_hash,
        review_status=review_status,
        pii_classification=pii_classification,
        expires_at=expires_at,
        deleted_at=deleted_at,
    )


@pytest.mark.asyncio
async def test_reviewed_memory_context_excludes_cross_merchant_long_term_and_case_memory(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    merchant_a = str(seeded_session["merchant"].id)
    merchant_b = str(seeded_session["second_merchant"].id)
    run_id = await _insert_run(session, seeded_session, thread_id="cross-merchant-reviewed-memory")
    await LongTermMemoryService(LongTermMemoryRepository(session)).write_memory(
        _long_term_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_b,
            content="Merchant B long-term memory must not enter merchant A prompt context.",
        )
    )
    await CaseMemoryService(CaseMemoryRepository(session)).submit_case_memory_candidate(
        _case_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_b,
            summary="Merchant B case memory must not enter merchant A prompt context.",
        )
    )

    bundle = await _context_service(session).load_reviewed_memory_context(
        trusted_context=_trusted_context(seeded_session, merchant_ids=[merchant_a]),
        current_slots={"merchant_id": merchant_b},
        trusted_business_context={"merchant_id": merchant_b},
        query="refund merchant B",
        case_type="refund_dispute",
    )

    memory_context = _bundle_dict(bundle)
    status_ref = memory_context["status_ref"]
    assert memory_context["long_term_items"] == []
    assert memory_context["case_items"] == []
    assert any(reason.startswith("merchant_scope_denied") for reason in status_ref["filter_reasons"])


@pytest.mark.asyncio
async def test_reviewed_memory_context_rejects_global_or_tenant_scope_without_allowlist(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    merchant_a = str(seeded_session["merchant"].id)

    bundle = await _context_service(session).load_reviewed_memory_context(
        trusted_context=_trusted_context(seeded_session, merchant_ids=[merchant_a]),
        current_slots={},
        requested_scopes=[{"scope_type": "tenant", "scope_id": str(seeded_session["tenant"].id)}],
        query="tenant global memory",
    )

    memory_context = _bundle_dict(bundle)
    assert memory_context["long_term_items"] == []
    assert memory_context["case_items"] == []
    assert memory_context["status_ref"]["fallback_reason"] == "tenant_global_memory_unsupported"


@pytest.mark.asyncio
async def test_reviewed_memory_context_excludes_deleted_expired_rejected_superseded_needs_review_and_non_prompt_safe_pii(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime.now(UTC)
    tenant_id = seeded_session["tenant"].id
    merchant_a = str(seeded_session["merchant"].id)
    visible_long_term = _long_term_row(
        tenant_id=tenant_id,
        merchant_id=merchant_a,
        content="Visible reviewed merchant A long-term memory.",
    )
    visible_case = _case_row(
        tenant_id=tenant_id,
        merchant_id=merchant_a,
        summary="Visible reviewed merchant A case memory.",
    )
    tombstoned_long_term = _long_term_row(
        tenant_id=tenant_id,
        merchant_id=merchant_a,
        content="Tombstoned long-term memory must not surface.",
    )
    source_hash = canonical_source_identity_hash({"source_type": "human_reviewed", "event_id": "case-source-delete"})
    tombstoned_case = _case_row(
        tenant_id=tenant_id,
        merchant_id=merchant_a,
        summary="Tombstoned case memory must not surface.",
        source_identity_hash=source_hash,
    )
    session.add_all(
        [
            visible_long_term,
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Deleted long-term memory must not surface.",
                deleted_at=now,
            ),
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Expired long-term memory must not surface.",
                expires_at=now - timedelta(seconds=1),
            ),
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Rejected long-term memory must not surface.",
                review_status="rejected",
            ),
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Superseded long-term memory must not surface.",
                review_status="superseded",
                is_current=False,
            ),
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Needs-review long-term memory must not surface.",
                review_status="needs_review",
            ),
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Sensitive long-term memory must not surface.",
                pii_classification="sensitive",
            ),
            _long_term_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                content="Prohibited long-term memory must not surface.",
                pii_classification="prohibited",
            ),
            tombstoned_long_term,
            visible_case,
            _case_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                summary="Deleted case memory must not surface.",
                deleted_at=now,
            ),
            _case_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                summary="Expired case memory must not surface.",
                expires_at=now - timedelta(seconds=1),
            ),
            _case_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                summary="Rejected case memory must not surface.",
                review_status="rejected",
            ),
            _case_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                summary="Needs-review case memory must not surface.",
                review_status="needs_review",
            ),
            _case_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                summary="Sensitive case memory must not surface.",
                pii_classification="sensitive",
            ),
            _case_row(
                tenant_id=tenant_id,
                merchant_id=merchant_a,
                summary="Prohibited case memory must not surface.",
                pii_classification="prohibited",
            ),
            tombstoned_case,
        ]
    )
    await session.flush()
    session.add_all(
        [
            MemoryTombstone(
                tenant_id=tenant_id,
                memory_type=LONG_TERM_MEMORY_TYPE,
                scope_type="merchant",
                scope_id=merchant_a,
                content_hash=tombstoned_long_term.content_hash,
                source_ref_json={},
                reason_code="deleted",
            ),
            MemoryTombstone(
                tenant_id=tenant_id,
                memory_type=CASE_MEMORY_TYPE,
                scope_type="merchant",
                scope_id=merchant_a,
                content_hash=None,
                source_ref_json={"source_type": "human_reviewed", "event_id": "case-source-delete"},
                source_identity_hash=source_hash,
                reason_code="deleted",
            ),
        ]
    )
    await session.flush()

    bundle = await _context_service(session).load_reviewed_memory_context(
        trusted_context=_trusted_context(seeded_session, merchant_ids=[merchant_a]),
        current_slots={"merchant_id": merchant_a},
        trusted_business_context={"merchant_id": merchant_a},
        query="reviewed merchant A",
        case_type="refund_dispute",
        now=now,
    )

    memory_context = _bundle_dict(bundle)
    serialized = str(memory_context["long_term_items"]) + str(memory_context["case_items"])
    assert "Visible reviewed merchant A long-term memory." in serialized
    assert "Visible reviewed merchant A case memory." in serialized
    for forbidden in (
        "Deleted",
        "Expired",
        "Rejected",
        "Superseded",
        "Needs-review",
        "Sensitive",
        "Prohibited",
        "Tombstoned",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_memory_write_decision_projection_marks_needs_review_and_excludes_from_prompt_context(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    merchant_a = str(seeded_session["merchant"].id)
    run_id = await _insert_run(session, seeded_session, thread_id="needs-review-write-decision")
    long_term_service = LongTermMemoryService(LongTermMemoryRepository(session))
    case_service = CaseMemoryService(CaseMemoryRepository(session))

    long_term_result = await long_term_service.write_memory(
        _long_term_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_a,
            content="Needs-review long-term memory must stay out of reviewed prompt context.",
            source_type="llm_candidate",
        )
    )
    case_result = await case_service.submit_case_memory_candidate(
        _case_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_a,
            summary="Needs-review case memory must stay out of reviewed prompt context.",
            source_type="llm_candidate",
        )
    )

    long_term_decision = _memory_write_decision(
        session,
        long_term_result,
        memory_type=LONG_TERM_MEMORY_TYPE,
        scope={"tenant_id": str(tenant_id), "scope_type": "merchant", "scope_id": merchant_a},
    )
    case_decision = _memory_write_decision(
        session,
        case_result,
        memory_type=CASE_MEMORY_TYPE,
        scope={"tenant_id": str(tenant_id), "scope_type": "merchant", "scope_id": merchant_a},
    )
    retrieved_long_term = await long_term_service.retrieve_profile_memory(
        tenant_id=tenant_id,
        scope_type="merchant",
        scope_id=merchant_a,
    )
    retrieved_cases = await case_service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="merchant",
            scope_id=merchant_a,
            case_type="refund_dispute",
            query="Needs-review case memory",
        )
    )

    assert long_term_decision["schema_version"] == "memory_write_decision.v2"
    assert long_term_decision["authority_class"] == "contextual_only"
    assert long_term_decision["status"] == "needs_review"
    assert long_term_decision["decision"] == "needs_review"
    assert long_term_decision["review_status"] == "needs_review"
    assert case_decision["schema_version"] == "memory_write_decision.v2"
    assert case_decision["status"] == "needs_review"
    assert case_decision["review_status"] == "needs_review"
    assert retrieved_long_term == []
    assert retrieved_cases.items == []


@pytest.mark.asyncio
async def test_reviewed_memory_context_returns_approved_closed_case_candidate_without_embedding(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    merchant_a = str(seeded_session["merchant"].id)
    run_id = await _insert_run(session, seeded_session, thread_id="approved-generated-case-context")
    case_service = CaseMemoryService(CaseMemoryRepository(session))
    write_result = await case_service.submit_case_memory_candidate(
        _case_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_a,
            summary="Approved closed-case generated precedent for payment timeout.",
            source_type="closed_case_cwc_candidate",
        )
    )
    await case_service.approve_case_memory(
        CaseMemoryReviewDecision(
            tenant_id=seeded_session["tenant"].id,
            run_id=run_id,
            case_memory_id=write_result.memory_id,
            reviewer_user_id=seeded_session["users"]["approval_manager"].id,
            reason_code="approved",
            review_reason="approved generated precedent",
        )
    )

    bundle = await _context_service(session).load_reviewed_memory_context(
        trusted_context=_trusted_context(seeded_session, merchant_ids=[merchant_a]),
        current_slots={"merchant_id": merchant_a},
        trusted_business_context={"merchant_id": merchant_a},
        query="payment timeout",
        case_type="refund_dispute",
    )

    memory_context = _bundle_dict(bundle)
    assert [item["case_memory_id"] for item in memory_context["case_items"]] == [str(write_result.memory_id)]
    assert memory_context["case_items"][0]["excerpt"].startswith("Approved closed-case generated precedent")


@pytest.mark.asyncio
async def test_memory_write_decision_projection_tombstone_blocks_same_content_and_source_identity(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    merchant_a = str(seeded_session["merchant"].id)
    run_id = await _insert_run(session, seeded_session, thread_id="tombstone-write-decision")
    case_service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _case_candidate(
        seeded_session,
        run_id=run_id,
        merchant_id=merchant_a,
        summary="Tombstoned case memory must never return to reviewed prompt context.",
    )
    write_result = await case_service.submit_case_memory_candidate(candidate)
    tombstone_event = await case_service.forget_case_memory(
        tenant_id=tenant_id,
        case_memory_id=write_result.memory_id,
        run_id=run_id,
        reason_code="user_forget_case_memory",
    )

    tombstone_decision = _memory_write_decision(
        session,
        tombstone_event,
        memory_type=CASE_MEMORY_TYPE,
        scope={"tenant_id": str(tenant_id), "scope_type": "merchant", "scope_id": merchant_a},
    )
    rewrite_result = await case_service.submit_case_memory_candidate(candidate)
    reviewed_cases = await case_service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=tenant_id,
            scope_type="merchant",
            scope_id=merchant_a,
            case_type="refund_dispute",
            query="Tombstoned case memory",
        )
    )

    assert tombstone_decision["schema_version"] == "memory_write_decision.v2"
    assert tombstone_decision["decision"] in {"tombstone", "delete"}
    assert rewrite_result.status == "skipped"
    assert rewrite_result.reason_code == "tombstone_match"
    assert reviewed_cases.items == []


@pytest.mark.asyncio
async def test_memory_write_decision_projection_supersede_keeps_one_current_prompt_facing_memory(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    merchant_a = str(seeded_session["merchant"].id)
    run_id = await _insert_run(session, seeded_session, thread_id="supersede-write-decision")
    long_term_service = LongTermMemoryService(LongTermMemoryRepository(session))
    original_result = await long_term_service.write_memory(
        _long_term_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_a,
            content="Superseded preference must not remain prompt-facing.",
        )
    )
    replacement_result = await long_term_service.supersede_memory(
        tenant_id=tenant_id,
        memory_id=original_result.memory_id,
        run_id=run_id,
        replacement_candidate=_long_term_candidate(
            seeded_session,
            run_id=run_id,
            merchant_id=merchant_a,
            content="Superseding preference is the only current prompt-facing memory.",
        ),
        reason_code="user_correction",
    )

    supersede_decision = _memory_write_decision(
        session,
        replacement_result,
        memory_type=LONG_TERM_MEMORY_TYPE,
        scope={"tenant_id": str(tenant_id), "scope_type": "merchant", "scope_id": merchant_a},
    )
    current_rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == tenant_id,
                    LongTermMemory.scope_type == "merchant",
                    LongTermMemory.scope_id == merchant_a,
                    LongTermMemory.is_current.is_(True),
                    LongTermMemory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    prompt_items = await long_term_service.retrieve_profile_memory(
        tenant_id=tenant_id,
        scope_type="merchant",
        scope_id=merchant_a,
    )

    assert supersede_decision["schema_version"] == "memory_write_decision.v2"
    assert supersede_decision["decision"] == "supersede"
    assert supersede_decision["status"] == "written"
    assert len(current_rows) == 1
    assert current_rows[0].id == replacement_result.memory_id
    assert [item.memory_id for item in prompt_items] == [str(replacement_result.memory_id)]
