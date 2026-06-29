from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ActionDraft
from src.repositories.action_draft_repo import ActionDraftRepository


class ActionDraftStore:
    """Persistence adapter for durable action drafts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ActionDraftRepository(session)

    async def create_or_get(
        self,
        *,
        run_id: UUID,
        tenant_id: UUID,
        approval_request_id: UUID | None,
        idempotency_key: str,
        action_type: str,
        target_id: str,
        approval_revision_ref: str | None,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
        payload: dict[str, Any],
        target_merchant_id: str | None,
        target_merchant_ref: dict[str, Any] | None,
        business_fact_refs: list[dict[str, Any]],
        verified_evidence_refs: list[dict[str, Any]],
        claim_verification_ref: str | None,
        claim_verification_summary: dict[str, Any] | None,
        risk_decision_ref: str | None,
        risk_decision: dict[str, Any] | None,
        auto_allowed_binding_ref: str | None,
        draft_outcome: dict[str, Any],
        execution_mode: str,
        draft_version: int,
        lifecycle_status: str,
        retention_policy: str,
    ) -> tuple[ActionDraft, bool]:
        return await self.repository.create_or_get(
            run_id=run_id,
            tenant_id=tenant_id,
            approval_request_id=approval_request_id,
            idempotency_key=idempotency_key,
            action_type=action_type,
            target_id=target_id,
            approval_revision_ref=approval_revision_ref,
            action_payload_hash=action_payload_hash,
            safety_snapshot_ref=safety_snapshot_ref,
            safety_snapshot_hash=safety_snapshot_hash,
            payload=payload,
            target_merchant_id=target_merchant_id,
            target_merchant_ref=target_merchant_ref,
            business_fact_refs=business_fact_refs,
            verified_evidence_refs=verified_evidence_refs,
            claim_verification_ref=claim_verification_ref,
            claim_verification_summary=claim_verification_summary,
            risk_decision_ref=risk_decision_ref,
            risk_decision=risk_decision,
            auto_allowed_binding_ref=auto_allowed_binding_ref,
            draft_outcome=draft_outcome,
            execution_mode=execution_mode,
            draft_version=draft_version,
            lifecycle_status=lifecycle_status,
            retention_policy=retention_policy,
        )
