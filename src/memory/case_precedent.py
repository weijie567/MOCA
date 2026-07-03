from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RefundCase
from src.memory.case_memory import CaseMemoryService
from src.memory.case_working_context import CaseWorkingContextRepository, hydrate_content
from src.repositories.refund_repo import RefundRepository


TERMINAL_REFUND_CASE_STATUSES = frozenset({"closed", "refunded", "rejected"})


@dataclass(frozen=True)
class ClosedCasePrecedentGenerationInput:
    tenant_id: uuid.UUID
    case_id: uuid.UUID
    run_id: uuid.UUID
    closed_status: str
    close_event_id: str
    closed_at: datetime
    close_source: str = "trusted_internal"


@dataclass(frozen=True)
class ClosedCasePrecedentGenerationResult:
    status: Literal["needs_review", "skipped", "error"]
    reason_code: str
    memory_id: uuid.UUID | None = None
    review_status: str | None = None
    event_id: uuid.UUID | None = None
    scope_type: str | None = None
    scope_id: str | None = None


class ClosedCasePrecedentService:
    def __init__(
        self,
        *,
        session: AsyncSession | None,
        case_memory_service: CaseMemoryService | None = None,
        cwc_repository: CaseWorkingContextRepository | None = None,
        refund_repository: RefundRepository | None = None,
    ) -> None:
        self.session = session
        self.case_memory_service = case_memory_service
        self.cwc_repository = cwc_repository
        self.refund_repository = refund_repository

    async def generate_closed_case_precedent_candidate(
        self,
        request: ClosedCasePrecedentGenerationInput,
    ) -> ClosedCasePrecedentGenerationResult:
        if request.closed_status not in TERMINAL_REFUND_CASE_STATUSES:
            return ClosedCasePrecedentGenerationResult(
                status="skipped",
                reason_code="non_terminal_status",
            )

        refund_case = await self._refund_repository().get_by_id_with_order(
            case_id=request.case_id,
            tenant_id=request.tenant_id,
        )
        if refund_case is None:
            return ClosedCasePrecedentGenerationResult(
                status="skipped",
                reason_code="case_not_found",
            )

        cwc_row = await self._cwc_repository().read_active(
            tenant_id=request.tenant_id,
            case_id=request.case_id,
        )
        if cwc_row is None:
            return ClosedCasePrecedentGenerationResult(
                status="skipped",
                reason_code="missing_active_cwc",
            )

        hydrate_content(cwc_row)
        scope_type, scope_id = _resolve_precedent_scope(refund_case, case_id=request.case_id)
        return ClosedCasePrecedentGenerationResult(
            status="needs_review",
            reason_code="projection_ready",
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _refund_repository(self) -> RefundRepository:
        if self.refund_repository is None:
            self.refund_repository = _require_session_repository(self.session, RefundRepository)
        return self.refund_repository

    def _cwc_repository(self) -> CaseWorkingContextRepository:
        if self.cwc_repository is None:
            self.cwc_repository = _require_session_repository(self.session, CaseWorkingContextRepository)
        return self.cwc_repository


def _resolve_precedent_scope(refund_case: RefundCase | None, *, case_id: uuid.UUID) -> tuple[str, str]:
    order = getattr(refund_case, "order", None)
    merchant_id = getattr(order, "merchant_id", None)
    if merchant_id is not None:
        return "merchant", str(merchant_id)
    return "case", str(case_id)


def _require_session_repository(session: AsyncSession | None, repository_type):
    if session is None:
        raise ValueError("session is required when repository dependency is not provided")
    return repository_type(session)
