from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseWorkingContext
from src.memory.case_precedent import (
    TERMINAL_REFUND_CASE_STATUSES,
    PRECEDENT_CAVEAT_TEXT,
    ClosedCasePrecedentGenerationInput,
    ClosedCasePrecedentGenerationResult,
    ClosedCasePrecedentService,
    _project_closed_case_candidate,
    _resolve_precedent_scope,
)
from src.memory.case_working_context_schemas import (
    CaseWorkingContextActionTakenV1,
    CaseWorkingContextClaimV1,
    CaseWorkingContextCommitmentV1,
    CaseWorkingContextContentV1,
    CaseWorkingContextPolicyRefV1,
    CaseWorkingContextRecommendationV1,
    CaseWorkingContextVerifiedFactV1,
)
from src.memory.schemas import CaseMemoryWriteCandidate


def _request(
    seeded_session: dict,
    *,
    closed_status: str = "closed",
    case_id: uuid.UUID | None = None,
) -> ClosedCasePrecedentGenerationInput:
    refund_case = seeded_session["refund_case"]
    return ClosedCasePrecedentGenerationInput(
        tenant_id=refund_case.tenant_id,
        case_id=case_id or refund_case.id,
        run_id=uuid.uuid4(),
        closed_status=closed_status,
        close_event_id=f"close-{uuid.uuid4()}",
        closed_at=datetime.now(UTC),
    )


def _content_with_projection_fields(case_id: uuid.UUID) -> CaseWorkingContextContentV1:
    source_ref = {
        "source_type": "run_auto_terminal",
        "agent_run_id": str(uuid.uuid4()),
        "business_object_type": "refund_case",
        "business_object_id": str(case_id),
    }
    return CaseWorkingContextContentV1(
        customer_request="用户要求处理破损商品退款 raw_payload",
        issue_type="refund_dispute",
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


async def _insert_active_cwc(session: AsyncSession, seeded_session: dict) -> CaseWorkingContext:
    refund_case = seeded_session["refund_case"]
    row = CaseWorkingContext(
        id=uuid.uuid4(),
        tenant_id=refund_case.tenant_id,
        case_id=refund_case.id,
        customer_request="用户要求退款",
        issue_type="refund_dispute",
        claims_json=[],
        verified_facts_json=[],
        missing_info_json=[],
        evidence_refs_json=[],
        actions_taken_json=[],
        policy_refs_json=[],
        agent_recommendations_json=[],
        pending_tasks_json=[],
        commitments_json=[],
        next_action_json={},
        source_ref_json={
            "source_type": "run_auto_terminal",
            "business_object_type": "refund_case",
            "business_object_id": str(refund_case.id),
        },
        version=1,
        pii_classification="none",
    )
    session.add(row)
    await session.flush()
    return row


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
async def test_terminal_status_uses_refund_case_order_merchant_scope(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    await _insert_active_cwc(session, seeded_session)
    refund_case = seeded_session["refund_case"]
    service = ClosedCasePrecedentService(session=session)

    result = await service.generate_closed_case_precedent_candidate(_request(seeded_session))

    assert result.status == "needs_review"
    assert result.scope_type == "merchant"
    assert result.scope_id == str(seeded_session["merchant"].id)
    assert result.memory_id is None
    assert result.review_status is None
    assert refund_case.order.merchant_id == seeded_session["merchant"].id


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
    result = _project_closed_case_candidate(
        request=request,
        content=_content_with_projection_fields(request.case_id),
        cwc_row=_cwc_projection_row(pii_classification=pii_classification),
        scope_type="merchant",
        scope_id=str(seeded_session["merchant"].id),
    )

    assert isinstance(result, ClosedCasePrecedentGenerationResult)
    assert result.status == "skipped"
    assert result.reason_code == "pii_blocked"
