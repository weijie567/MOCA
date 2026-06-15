"""Approval SLA scanner kept feature-disabled until Phase 15 replay gates pass."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.events import approval_revision_ref, validate_approval_event_payload
from src.approvals.service import ApprovalService
from src.config import settings
from src.db.models import ApprovalAssignment, ApprovalLevel, ApprovalRequest


SLA_EVENT_SHAPE_TYPES = {"approval_sla_reminder", "approval_sla_escalation", "approval_expired"}


@dataclass(frozen=True)
class ApprovalSlaScanResult:
    status: Literal["disabled", "completed"]
    expired_count: int
    event_count: int


class ApprovalSlaScanner:
    """Feature-disabled Phase 13 scanner; approval_sla_scanner_enabled is a Phase 15 gate."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        service: ApprovalService | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.session = session
        self.enabled = settings.approval_sla_scanner_enabled if enabled is None else enabled
        self.service = service or ApprovalService(session)

    async def scan(self, *, now: datetime | None = None) -> ApprovalSlaScanResult:
        """Expire due approvals only when Phase 15 explicitly enables the scanner."""
        if not self.enabled:
            return ApprovalSlaScanResult(status="disabled", expired_count=0, event_count=0)

        current_time = now or datetime.now(UTC)
        rows = (
            await self.session.execute(
                select(ApprovalRequest)
                .where(
                    ApprovalRequest.schema_version == "approval_request.v2",
                    ApprovalRequest.legacy_non_executable.is_(False),
                    ApprovalRequest.status == "pending",
                    ApprovalRequest.expires_at <= current_time,
                )
                .order_by(ApprovalRequest.expires_at.asc())
            )
        ).scalars().all()

        expired_count = 0
        for request in rows:
            expired = await self.service.expire_due_request(
                request.id,
                request.tenant_id,
                now=current_time,
            )
            if expired is not None:
                expired_count += 1
        return ApprovalSlaScanResult(status="completed", expired_count=expired_count, event_count=expired_count)


def build_sla_event_shape(
    *,
    event_type: str,
    request: ApprovalRequest,
    level: ApprovalLevel | None = None,
    assignment: ApprovalAssignment | None = None,
    reason: str,
) -> dict[str, dict[str, Any]]:
    """Build safe reminder/escalation/expire refs without writing events.

    Phase 15 owns enabling active scanner scheduling after replay coverage and allocator
    concurrency gates pass. Phase 13 exposes this dry-run shape for tests only.
    """
    if event_type not in SLA_EVENT_SHAPE_TYPES:
        raise ValueError(f"unsupported SLA event shape {event_type!r}")

    metadata: dict[str, Any] = {
        "reason": reason,
        "phase_15_owner": "SLA scanner enablement",
    }
    resource_refs: dict[str, Any] = {
        "request_ref": f"approval_request:{request.id}:r{request.revision}",
        "revision_ref": approval_revision_ref(request),
        "request_version": request.version,
        "action_payload_hash": request.action_payload_hash,
        "safety_snapshot_ref": request.safety_snapshot_ref,
        "safety_snapshot_hash": request.safety_snapshot_hash,
    }
    if level is not None:
        resource_refs["level_ref"] = f"approval_level:{level.id}:v{level.version}"
        resource_refs["level_version"] = level.version
    if assignment is not None:
        resource_refs["assignment_ref"] = f"approval_assignment:{assignment.id}:v{assignment.version}"
        resource_refs["assignment_version"] = assignment.version
    redacted_payload = {
        "event_type": event_type,
        "status": request.status,
        "reason": reason,
    }
    validate_approval_event_payload(
        metadata=metadata,
        resource_refs=resource_refs,
        redacted_payload=redacted_payload,
    )
    return {
        "metadata": metadata,
        "resource_refs": resource_refs,
        "redacted_payload": redacted_payload,
    }
