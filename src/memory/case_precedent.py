from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RefundCase
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.case_working_context import CaseWorkingContextRepository, hydrate_content
from src.memory.case_working_context_schemas import CaseWorkingContextContentV1
from src.memory.schemas import CaseMemoryWriteCandidate, MemorySourceRefV1
from src.repositories.refund_repo import RefundRepository


TERMINAL_REFUND_CASE_STATUSES = frozenset({"closed", "refunded", "rejected"})
PRECEDENT_CAVEAT_TEXT = (
    "Contextual precedent only; not policy evidence, current business fact authority, approval authorization, "
    "action authorization, action outcome truth, audit truth, or replay truth."
)
_FORBIDDEN_OUTPUT_MARKERS = (
    "raw_payload",
    "raw_tool",
    "policy_body",
    "approval_authority",
    "action_authority",
    "replay_blob",
    "debug_blob",
)
_PII_BLOCKING_CLASSIFICATIONS = {"sensitive", "prohibited"}


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

        scope_type, scope_id = _resolve_precedent_scope(refund_case, case_id=request.case_id)
        projected = _project_closed_case_candidate(
            request=request,
            content=hydrate_content(cwc_row),
            cwc_row=cwc_row,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if isinstance(projected, ClosedCasePrecedentGenerationResult):
            return projected

        write_result = await self._case_memory_service().submit_case_memory_candidate(projected)
        status: Literal["needs_review", "skipped", "error"]
        if write_result.status == "needs_review":
            status = "needs_review"
        elif write_result.status == "skipped":
            status = "skipped"
        else:
            status = "error"
        return ClosedCasePrecedentGenerationResult(
            status=status,
            reason_code=write_result.reason_code,
            memory_id=write_result.memory_id,
            review_status=write_result.review_status,
            event_id=write_result.event_id,
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

    def _case_memory_service(self) -> CaseMemoryService:
        if self.case_memory_service is None:
            repository = _require_session_repository(self.session, CaseMemoryRepository)
            self.case_memory_service = CaseMemoryService(repository)
        return self.case_memory_service


def _resolve_precedent_scope(refund_case: RefundCase | None, *, case_id: uuid.UUID) -> tuple[str, str]:
    order = getattr(refund_case, "order", None)
    merchant_id = getattr(order, "merchant_id", None)
    if merchant_id is not None:
        return "merchant", str(merchant_id)
    return "case", str(case_id)


def _project_closed_case_candidate(
    *,
    request: ClosedCasePrecedentGenerationInput,
    content: CaseWorkingContextContentV1,
    cwc_row: Any,
    scope_type: str,
    scope_id: str,
) -> CaseMemoryWriteCandidate | ClosedCasePrecedentGenerationResult:
    pii_classification = str(getattr(cwc_row, "pii_classification", "none") or "none")
    if pii_classification in _PII_BLOCKING_CLASSIFICATIONS:
        return ClosedCasePrecedentGenerationResult(
            status="skipped",
            reason_code="pii_blocked",
            scope_type=scope_type,
            scope_id=scope_id,
        )

    policy_refs = _project_policy_refs(content)
    policy_family = policy_refs[0]["doc_key"] if policy_refs else None
    policy_version = policy_refs[0]["policy_version"] if policy_refs else None
    case_type = _bounded_text(content.issue_type, 64) or "refund"
    summary = _bounded_text(f"Closed refund case precedent: {case_type}.", 4000)
    excerpt = _bounded_text("\n".join(_projection_excerpt_lines(content)), 1500)
    outcome = _bounded_text(
        " ".join(_projection_outcome_parts(request=request, content=content)),
        1500,
    )

    return CaseMemoryWriteCandidate(
        tenant_id=request.tenant_id,
        run_id=request.run_id,
        scope_type=scope_type,  # type: ignore[arg-type]
        scope_id=scope_id,
        case_type=case_type,
        summary=summary or "Closed refund case precedent.",
        excerpt=excerpt or "Closed case CWC snapshot has contextual precedent details.",
        applicability=_bounded_text(
            f"Use only as reviewed precedent for similar refund cases within {scope_type} scope.",
            1500,
        ),
        outcome=outcome,
        caveats=PRECEDENT_CAVEAT_TEXT,
        source_type="closed_case_cwc_candidate",
        source_ref=_closed_case_source_ref(request=request, cwc_row=cwc_row, policy_version=policy_version),
        policy_family=policy_family,
        policy_version=policy_version,
        policy_refs=policy_refs,
        embedding=None,
        pii_classification=pii_classification,  # type: ignore[arg-type]
    )


def _project_policy_refs(content: CaseWorkingContextContentV1) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for ref in content.policy_refs:
        key = (ref.doc_id, ref.chunk_id, ref.version)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "doc_key": ref.doc_id,
                "chunk_id": ref.chunk_id,
                "policy_version": ref.version,
            }
        )
    return refs


def _projection_excerpt_lines(content: CaseWorkingContextContentV1) -> list[str]:
    lines: list[str] = []
    _append_labeled_line(lines, "Customer request:", content.customer_request)
    for claim in content.claims:
        _append_labeled_line(lines, "Customer claim:", claim.text)
    for fact in content.verified_facts:
        _append_labeled_line(lines, "Verified fact:", fact.text)
    for action in content.actions_taken:
        _append_labeled_line(lines, "Action taken:", action.action)
    for recommendation in content.agent_recommendations:
        _append_labeled_line(lines, "Agent recommendation:", recommendation.recommended_step)
        _append_labeled_line(lines, "Staff decision:", recommendation.staff_decision)
    for commitment in content.commitments:
        _append_labeled_line(lines, "Commitment:", commitment.text)
    return lines


def _projection_outcome_parts(
    *,
    request: ClosedCasePrecedentGenerationInput,
    content: CaseWorkingContextContentV1,
) -> list[str]:
    parts = [
        f"Trusted close status: {request.closed_status}.",
        f"Closed at: {request.closed_at.isoformat()}.",
    ]
    for recommendation in content.agent_recommendations:
        decision = _bounded_text(recommendation.staff_decision, 240)
        if decision:
            parts.append(f"Staff decision: {decision}.")
    for commitment in content.commitments:
        commitment = _bounded_text(commitment.text, 240)
        if commitment:
            parts.append(f"Commitment: {commitment}.")
    return parts


def _append_labeled_line(lines: list[str], label: str, value: str | None) -> None:
    text = _bounded_text(value, 280)
    if text is not None:
        lines.append(f"{label} {text}")


def _closed_case_source_ref(
    *,
    request: ClosedCasePrecedentGenerationInput,
    cwc_row: Any,
    policy_version: str | None,
) -> MemorySourceRefV1:
    row_id = getattr(cwc_row, "id", None)
    row_version = getattr(cwc_row, "version", None)
    return MemorySourceRefV1(
        source_type="closed_case_cwc_candidate",
        run_id=str(request.run_id),
        event_id=f"refund-case-close:{request.case_id}:{request.close_event_id}",
        agent_run_id=str(request.run_id),
        business_object_type="refund_case",
        business_object_id=str(request.case_id),
        policy_version=policy_version,
        outcome_id=f"cwc:{row_id}:v{row_version}" if row_id is not None and row_version is not None else None,
    )


def _bounded_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = value
    for marker in _FORBIDDEN_OUTPUT_MARKERS:
        text = text.replace(marker, "")
    text = " ".join(text.split())
    if not text:
        return None
    return text[:limit]


def _require_session_repository(session: AsyncSession | None, repository_type):
    if session is None:
        raise ValueError("session is required when repository dependency is not provided")
    return repository_type(session)
