from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ApprovalRequest, ApprovalStep


class ApprovalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        run_id: UUID,
        tenant_id: UUID,
        requested_by: UUID,
        proposed_action: dict[str, Any],
        risk_level: str,
        risk_rule_ref: str | None,
        risk_reason: str | None,
        expires_at: datetime,
        thread_id: str,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            run_id=run_id,
            tenant_id=tenant_id,
            requested_by=requested_by,
            proposed_action=proposed_action,
            risk_level=risk_level,
            risk_rule_ref=risk_rule_ref,
            risk_reason=risk_reason,
            expires_at=expires_at,
            thread_id=thread_id,
            status="pending",
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def get_by_id(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_for_update(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_pending_by_tenant(self, tenant_id: UUID) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.tenant_id == tenant_id,
                ApprovalRequest.status == "pending",
                ApprovalRequest.expires_at > datetime.now(UTC),
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def decide(
        self,
        approval_id: UUID,
        tenant_id: UUID,
        *,
        decision: str,
        reason: str | None,
        decided_by: UUID,
    ) -> ApprovalRequest:
        if decision not in {"approve", "reject"}:
            raise ValueError("invalid_decision")

        approval = await self.get_by_id_for_update(approval_id, tenant_id)
        if not approval:
            raise ValueError("not_found")

        if approval.status == "expired":
            raise ValueError("expired")
        if approval.status == "approved":
            if decision == "approve":
                return approval
            raise ValueError("conflict: already approved")
        if approval.status == "rejected":
            if decision == "reject":
                return approval
            raise ValueError("conflict: already rejected")

        approval.status = "approved" if decision == "approve" else "rejected"
        approval.decision = decision
        approval.reason = reason
        approval.decided_by = decided_by
        approval.decided_at = datetime.now(UTC)
        await self.session.flush()
        return approval

    async def mark_expired(self, approval_id: UUID, tenant_id: UUID) -> None:
        approval = await self.get_by_id_for_update(approval_id, tenant_id)
        if approval and approval.status == "pending":
            approval.status = "expired"
            await self.session.flush()

    async def add_step(
        self,
        approval_request_id: UUID,
        event_type: str,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalStep:
        step = ApprovalStep(
            approval_request_id=approval_request_id,
            event_type=event_type,
            actor_id=actor_id,
            metadata_json=metadata or {},
        )
        self.session.add(step)
        await self.session.flush()
        return step
