from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, CaseMemory, CaseWorkingContext, MemoryWriteEvent
from src.memory.case_working_context import dehydrate_content
from src.memory.case_precedent import (
    TERMINAL_REFUND_CASE_STATUSES,
    PII_BLOCKED_PRECEDENT_TEXT,
    PRECEDENT_CAVEAT_TEXT,
    ClosedCasePrecedentGenerationInput,
    ClosedCasePrecedentService,
    _project_closed_case_candidate,
    _resolve_precedent_scope,
)
from src.memory.identity import ALLOWED_SOURCE_REF_KEYS
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.case_working_context_schemas import (
    CaseWorkingContextActionTakenV1,
    CaseWorkingContextClaimV1,
    CaseWorkingContextCommitmentV1,
    CaseWorkingContextContentV1,
    CaseWorkingContextPolicyRefV1,
    CaseWorkingContextRecommendationV1,
    CaseWorkingContextVerifiedFactV1,
)
from src.memory.schemas import CaseMemoryReviewDecision, CaseMemorySearchRequest, CaseMemoryWriteCandidate


def _request(
    seeded_session: dict,
    *,
    closed_status: str = "closed",
    case_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    close_event_id: str | None = None,
) -> ClosedCasePrecedentGenerationInput:
    refund_case = seeded_session["refund_case"]
    return ClosedCasePrecedentGenerationInput(
        tenant_id=refund_case.tenant_id,
        case_id=case_id or refund_case.id,
        run_id=run_id or uuid.uuid4(),
        closed_status=closed_status,
        close_event_id=close_event_id or f"close-{uuid.uuid4()}",
        closed_at=datetime.now(UTC),
    )


def _content_with_projection_fields(
    case_id: uuid.UUID,
    *,
    issue_type: str = "refund_dispute",
) -> CaseWorkingContextContentV1:
    source_ref = {
        "source_type": "run_auto_terminal",
        "agent_run_id": str(uuid.uuid4()),
        "business_object_type": "refund_case",
        "business_object_id": str(case_id),
    }
    return CaseWorkingContextContentV1(
        customer_request="用户要求处理破损商品退款 raw_payload",
        issue_type=issue_type,
        claims=[
            CaseWorkingContextClaimV1(
                text="用户称商品破损 raw_tool",
                verified=False,
                source_ref=source_ref,
            )
        ],
        verified_facts=[
            CaseWorkingContextVerifiedFactV1(
                text="物流照片确认外包装破损 policy_body",
                source_ref=source_ref,
                observed_at=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
            )
        ],
        actions_taken=[
            CaseWorkingContextActionTakenV1(
                action="已要求用户补充照片 approval_authority",
                source_ref=source_ref,
            )
        ],
        policy_refs=[CaseWorkingContextPolicyRefV1(doc_id="refund_policy", chunk_id="c-1", version="2026-01")],
        agent_recommendations=[
            CaseWorkingContextRecommendationV1(
                recommended_step="建议同意退款 action_authority",
                staff_decision="主管同意退款 replay_blob",
            )
        ],
        commitments=[
            CaseWorkingContextCommitmentV1(
                text="承诺 24 小时内处理 debug_blob",
                confirmed_by_staff=True,
                source_ref=source_ref,
            )
        ],
    )


def _cwc_projection_row(*, pii_classification: str = "none") -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), version=3, pii_classification=pii_classification)


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str = "case-precedent") -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="generate closed-case precedent",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


async def _insert_active_cwc(
    session: AsyncSession,
    seeded_session: dict,
    *,
    issue_type: str = "refund_dispute",
    pii_classification: str = "none",
    version: int = 1,
) -> CaseWorkingContext:
    refund_case = seeded_session["refund_case"]
    content = _content_with_projection_fields(refund_case.id, issue_type=issue_type)
    dehydrated = dehydrate_content(content)
    row = CaseWorkingContext(
        id=uuid.uuid4(),
        tenant_id=refund_case.tenant_id,
        case_id=refund_case.id,
        customer_request=dehydrated["customer_request"],
        issue_type=dehydrated["issue_type"],
        claims_json=dehydrated["claims"],
        verified_facts_json=dehydrated["verified_facts"],
        missing_info_json=dehydrated["missing_info"],
        evidence_refs_json=dehydrated["evidence_refs"],
        actions_taken_json=dehydrated["actions_taken"],
        policy_refs_json=dehydrated["policy_refs"],
        agent_recommendations_json=dehydrated["agent_recommendations"],
        pending_tasks_json=dehydrated["pending_tasks"],
        commitments_json=dehydrated["commitments"],
        next_action_json=dehydrated["next_action"],
        source_ref_json={
            "source_type": "run_auto_terminal",
            "business_object_type": "refund_case",
            "business_object_id": str(refund_case.id),
        },
        version=version,
        pii_classification=pii_classification,
    )
    session.add(row)
    await session.flush()
    return row


async def _case_memory_rows(session: AsyncSession) -> list[CaseMemory]:
    return list((await session.execute(select(CaseMemory).order_by(CaseMemory.created_at))).scalars().all())


async def _write_events(session: AsyncSession, run_id: uuid.UUID) -> list[MemoryWriteEvent]:
    return list(
        (
            await session.execute(
                select(MemoryWriteEvent).where(MemoryWriteEvent.run_id == run_id).order_by(MemoryWriteEvent.created_at)
            )
        )
        .scalars()
        .all()
    )


class _NoopCaseMemoryService:
    def __init__(self) -> None:
        self.submitted = False

    async def submit_case_memory_candidate(self, candidate):  # pragma: no cover - should not be called in Task 1
        self.submitted = True
        raise AssertionError("Task 1 must not submit case-memory candidates")


class _ExplodingRefundRepository:
    async def get_by_id_with_order(self, case_id: uuid.UUID, tenant_id: uuid.UUID):
        raise AssertionError("non-terminal statuses must skip before refund-case lookup")


class _MissingRefundRepository:
    async def get_by_id_with_order(self, case_id: uuid.UUID, tenant_id: uuid.UUID):
        return None


class _PresentRefundRepository:
    def __init__(self, merchant_id: uuid.UUID | None = None) -> None:
        self.merchant_id = merchant_id or uuid.uuid4()

    async def get_by_id_with_order(self, case_id: uuid.UUID, tenant_id: uuid.UUID):
        return SimpleNamespace(order=SimpleNamespace(merchant_id=self.merchant_id))


class _MissingCwcRepository:
    async def read_active(self, *, tenant_id: uuid.UUID, case_id: uuid.UUID):
        return None


def test_terminal_refund_case_status_allowlist_is_exact() -> None:
    assert TERMINAL_REFUND_CASE_STATUSES == frozenset({"closed", "refunded", "rejected"})


@pytest.mark.asyncio
@pytest.mark.parametrize("closed_status", ["open", "reviewing", "unknown_status"])
async def test_non_terminal_status_skips_before_lookup(seeded_session: dict, closed_status: str) -> None:
    case_memory_service = _NoopCaseMemoryService()
    service = ClosedCasePrecedentService(
        session=None,
        case_memory_service=case_memory_service,
        refund_repository=_ExplodingRefundRepository(),
    )

    result = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, closed_status=closed_status)
    )

    assert result.status == "skipped"
    assert result.reason_code == "non_terminal_status"
    assert case_memory_service.submitted is False


@pytest.mark.asyncio
async def test_terminal_status_with_missing_case_skips_before_cwc(seeded_session: dict) -> None:
    service = ClosedCasePrecedentService(
        session=None,
        refund_repository=_MissingRefundRepository(),
        cwc_repository=_MissingCwcRepository(),
    )

    result = await service.generate_closed_case_precedent_candidate(_request(seeded_session))

    assert result.status == "skipped"
    assert result.reason_code == "case_not_found"


@pytest.mark.asyncio
async def test_terminal_status_with_missing_active_cwc_skips(seeded_session: dict) -> None:
    service = ClosedCasePrecedentService(
        session=None,
        refund_repository=_PresentRefundRepository(),
        cwc_repository=_MissingCwcRepository(),
    )

    result = await service.generate_closed_case_precedent_candidate(_request(seeded_session))

    assert result.status == "skipped"
    assert result.reason_code == "missing_active_cwc"


@pytest.mark.asyncio
async def test_missing_case_and_missing_active_cwc_skip_without_case_memory_rows(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    service = ClosedCasePrecedentService(session=session)

    missing_case = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, case_id=uuid.uuid4(), close_event_id="missing-case")
    )
    missing_cwc = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id="missing-cwc")
    )

    assert missing_case.status == "skipped"
    assert missing_case.reason_code == "case_not_found"
    assert missing_cwc.status == "skipped"
    assert missing_cwc.reason_code == "missing_active_cwc"
    assert await _case_memory_rows(session) == []


@pytest.mark.asyncio
async def test_terminal_status_uses_refund_case_order_merchant_scope(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    cwc_row = await _insert_active_cwc(session, seeded_session)
    refund_case = seeded_session["refund_case"]
    service = ClosedCasePrecedentService(session=session)
    close_event_id = "close-event-task1"

    result = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id=close_event_id)
    )
    rows = list((await session.execute(select(CaseMemory))).scalars().all())

    assert result.status == "needs_review"
    assert result.reason_code == "requires_review"
    assert result.memory_id is not None
    assert result.review_status == "needs_review"
    assert result.event_id is not None
    assert result.scope_type == "merchant"
    assert result.scope_id == str(seeded_session["merchant"].id)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == result.memory_id
    assert row.review_status == "needs_review"
    assert row.embedding is None
    assert set(row.source_ref_json) <= ALLOWED_SOURCE_REF_KEYS
    assert row.source_ref_json["source_type"] == "closed_case_cwc_candidate"
    assert row.source_ref_json == {
        "source_type": "closed_case_cwc_candidate",
        "run_id": str(run_id),
        "agent_run_id": str(run_id),
        "event_id": f"refund-case-close:{refund_case.id}:{close_event_id}",
        "business_object_type": "refund_case",
        "business_object_id": str(refund_case.id),
        "outcome_id": f"cwc:{cwc_row.id}:v{cwc_row.version}",
        "policy_version": "2026-01",
    }
    assert row.policy_refs_json == [{"doc_key": "refund_policy", "chunk_id": "c-1", "policy_version": "2026-01"}]
    event = await session.get(MemoryWriteEvent, result.event_id)
    assert event is not None
    assert event.memory_id == result.memory_id
    assert event.source_ref_json == row.source_ref_json
    assert refund_case.order.merchant_id == seeded_session["merchant"].id


@pytest.mark.asyncio
async def test_duplicate_closed_case_generation_uses_existing_duplicate_handling(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    await _insert_active_cwc(session, seeded_session)
    service = ClosedCasePrecedentService(session=session)
    request = _request(seeded_session, run_id=run_id, close_event_id="duplicate-active")

    first = await service.generate_closed_case_precedent_candidate(request)
    duplicate = await service.generate_closed_case_precedent_candidate(request)
    rows = await _case_memory_rows(session)
    events = await _write_events(session, run_id)

    assert first.status == "needs_review"
    assert duplicate.status == "skipped"
    assert duplicate.memory_id == first.memory_id
    assert duplicate.reason_code.startswith("duplicate_active")
    assert [row.id for row in rows] == [first.memory_id]
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == duplicate.reason_code


@pytest.mark.asyncio
async def test_different_close_event_with_same_content_dedupes_by_content_hash_reason(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    await _insert_active_cwc(session, seeded_session)
    service = ClosedCasePrecedentService(session=session)

    first = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id="same-content-a")
    )
    duplicate = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id="same-content-b")
    )

    assert first.status == "needs_review"
    assert duplicate.status == "skipped"
    assert duplicate.memory_id == first.memory_id
    assert duplicate.reason_code == "duplicate_active_identity"


@pytest.mark.asyncio
async def test_different_cwc_version_with_changed_content_creates_new_candidate(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    cwc_row = await _insert_active_cwc(session, seeded_session)
    service = ClosedCasePrecedentService(session=session)

    first = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id="changed-cwc-a")
    )
    cwc_row.issue_type = "refund_followup_dispute"
    cwc_row.version = 2
    await session.flush()
    second = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id="changed-cwc-b")
    )
    rows = await _case_memory_rows(session)

    assert first.status == "needs_review"
    assert second.status == "needs_review"
    assert first.memory_id != second.memory_id
    assert [row.id for row in rows] == [first.memory_id, second.memory_id]


@pytest.mark.asyncio
@pytest.mark.parametrize("pii_classification", ["sensitive", "prohibited"])
async def test_pii_blocked_closed_case_generation_uses_existing_service_skip_event(
    session: AsyncSession,
    seeded_session: dict,
    pii_classification: str,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    cwc_row = await _insert_active_cwc(session, seeded_session, pii_classification=pii_classification)
    refund_case = seeded_session["refund_case"]
    service = ClosedCasePrecedentService(session=session)
    close_event_id = f"pii-blocked-{pii_classification}"

    result = await service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id=close_event_id)
    )
    rows = await _case_memory_rows(session)
    events = await _write_events(session, run_id)

    assert result.status == "skipped"
    assert result.reason_code == "pii_blocked"
    assert result.memory_id is None
    assert result.event_id is not None
    assert rows == []
    assert events[-1].id == result.event_id
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "pii_blocked"
    assert events[-1].pii_classification == pii_classification
    assert events[-1].source_ref_json["event_id"] == f"refund-case-close:{refund_case.id}:{close_event_id}"
    assert events[-1].source_ref_json["outcome_id"] == f"cwc:{cwc_row.id}:v{cwc_row.version}"


@pytest.mark.asyncio
async def test_generated_candidate_pending_review_hidden_until_approval_with_policy_refs(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_run(session, seeded_session)
    await _insert_active_cwc(session, seeded_session)
    case_memory_service = CaseMemoryService(CaseMemoryRepository(session))
    precedent_service = ClosedCasePrecedentService(
        session=session,
        case_memory_service=case_memory_service,
    )

    generated = await precedent_service.generate_closed_case_precedent_candidate(
        _request(seeded_session, run_id=run_id, close_event_id="approval-gate")
    )
    assert generated.memory_id is not None
    assert generated.scope_type is not None
    assert generated.scope_id is not None
    pending = await case_memory_service.list_pending_review(tenant_id=seeded_session["tenant"].id)
    hidden = await case_memory_service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=seeded_session["tenant"].id,
            scope_type=generated.scope_type,
            scope_id=generated.scope_id,
            case_type="refund_dispute",
            query="破损商品",
            limit=10,
        )
    )
    assert generated.status == "needs_review"
    assert [row.id for row in pending] == [generated.memory_id]
    assert pending[0].review_status == "needs_review"
    assert hidden.items == []

    approve_event = await case_memory_service.approve_case_memory(
        CaseMemoryReviewDecision(
            tenant_id=seeded_session["tenant"].id,
            run_id=run_id,
            case_memory_id=generated.memory_id,
            reviewer_user_id=seeded_session["users"]["approval_manager"].id,
            reason_code="approved",
            review_reason="closed-case precedent approved",
        )
    )
    visible = await case_memory_service.retrieve_reviewed(
        CaseMemorySearchRequest(
            tenant_id=seeded_session["tenant"].id,
            scope_type=generated.scope_type,
            scope_id=generated.scope_id,
            case_type="refund_dispute",
            query="破损商品",
            limit=10,
        )
    )

    assert approve_event.decision == "write"
    assert [item.case_memory_id for item in visible.items] == [str(generated.memory_id)]
    assert visible.items[0].policy_refs == [{"doc_key": "refund_policy", "chunk_id": "c-1", "policy_version": "2026-01"}]


def test_unresolved_merchant_falls_back_to_exact_case_scope(seeded_session: dict) -> None:
    case_id = seeded_session["refund_case"].id

    assert _resolve_precedent_scope(SimpleNamespace(order=None), case_id=case_id) == (
        "case",
        str(case_id),
    )
    assert _resolve_precedent_scope(None, case_id=case_id) == ("case", str(case_id))


def test_projection_separates_claims_verified_facts_and_maps_policy_refs(seeded_session: dict) -> None:
    request = _request(seeded_session)
    candidate = _project_closed_case_candidate(
        request=request,
        content=_content_with_projection_fields(request.case_id),
        cwc_row=_cwc_projection_row(),
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
    )

    assert isinstance(candidate, CaseMemoryWriteCandidate)
    assert candidate.source_type == "closed_case_cwc_candidate"
    assert candidate.embedding is None
    assert candidate.summary.startswith("Closed refund case precedent:")
    assert "Customer request:" in candidate.excerpt
    assert "Customer claim:" in candidate.excerpt
    assert "Verified fact:" in candidate.excerpt
    assert candidate.policy_refs == [{"doc_key": "refund_policy", "chunk_id": "c-1", "policy_version": "2026-01"}]
    assert candidate.policy_family == "refund_policy"
    assert candidate.policy_version == "2026-01"


def test_projection_uses_fixed_caveat_and_excludes_raw_payload_markers(seeded_session: dict) -> None:
    request = _request(seeded_session)
    candidate = _project_closed_case_candidate(
        request=request,
        content=_content_with_projection_fields(request.case_id),
        cwc_row=_cwc_projection_row(),
        scope_type="case",
        scope_id=str(request.case_id),
    )

    assert isinstance(candidate, CaseMemoryWriteCandidate)
    assert candidate.caveats == PRECEDENT_CAVEAT_TEXT
    rendered = " ".join(
        [
            candidate.summary,
            candidate.excerpt,
            candidate.applicability or "",
            candidate.outcome or "",
            candidate.caveats or "",
            str(candidate.policy_refs),
        ]
    )
    for marker in (
        "raw_payload",
        "raw_tool",
        "policy_body",
        "approval_authority",
        "action_authority",
        "replay_blob",
        "debug_blob",
    ):
        assert marker not in rendered


@pytest.mark.parametrize("pii_classification", ["sensitive", "prohibited"])
def test_projection_blocks_sensitive_or_prohibited_cwc_pii(seeded_session: dict, pii_classification: str) -> None:
    request = _request(seeded_session)
    candidate = _project_closed_case_candidate(
        request=request,
        content=_content_with_projection_fields(request.case_id),
        cwc_row=_cwc_projection_row(pii_classification=pii_classification),
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
    )

    assert isinstance(candidate, CaseMemoryWriteCandidate)
    assert candidate.summary == PII_BLOCKED_PRECEDENT_TEXT
    assert candidate.excerpt == PII_BLOCKED_PRECEDENT_TEXT
    assert candidate.pii_classification == pii_classification
