from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseWorkingContext
from src.memory.case_precedent import (
    TERMINAL_REFUND_CASE_STATUSES,
    ClosedCasePrecedentGenerationInput,
    ClosedCasePrecedentService,
    _resolve_precedent_scope,
)


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
