from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ActionDraft


class ActionDraftRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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
        insert_stmt = (
            insert(ActionDraft)
            .values(
                run_id=run_id,
                tenant_id=tenant_id,
                approval_request_id=approval_request_id,
                idempotency_key=idempotency_key,
                schema_version="action_draft.v2",
                target_id=target_id,
                approval_revision_ref=approval_revision_ref,
                action_payload_hash=action_payload_hash,
                safety_snapshot_ref=safety_snapshot_ref,
                safety_snapshot_hash=safety_snapshot_hash,
                target_merchant_id=target_merchant_id,
                target_merchant_ref=target_merchant_ref,
                business_fact_refs=business_fact_refs,
                verified_evidence_refs=verified_evidence_refs,
                claim_verification_ref=claim_verification_ref,
                claim_verification_summary=claim_verification_summary,
                risk_decision_ref=risk_decision_ref,
                risk_decision=risk_decision,
                auto_allowed_binding_ref=auto_allowed_binding_ref,
                action_type=action_type,
                status="draft_created",
                payload=payload,
                draft_outcome=draft_outcome,
                execution_mode=execution_mode,
                draft_version=draft_version,
                lifecycle_status=lifecycle_status,
                retention_policy=retention_policy,
                created_by_agent_run=run_id,
            )
            .on_conflict_do_nothing(
                constraint="uq_action_drafts_tenant_idempotency_key",
            )
            .returning(ActionDraft.id)
        )
        inserted_id = (await self.session.execute(insert_stmt)).scalar_one_or_none()

        draft = (
            await self.session.execute(
                select(ActionDraft).where(
                    ActionDraft.tenant_id == tenant_id,
                    ActionDraft.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if draft is None:
            raise ValueError("idempotency_key_conflict")
        if not _same_binding(
            draft,
            run_id=run_id,
            tenant_id=tenant_id,
            action_type=action_type,
            target_id=target_id,
            action_payload_hash=action_payload_hash,
            safety_snapshot_ref=safety_snapshot_ref,
            safety_snapshot_hash=safety_snapshot_hash,
            target_merchant_id=target_merchant_id,
            target_merchant_ref=target_merchant_ref,
            business_fact_refs=business_fact_refs,
            verified_evidence_refs=verified_evidence_refs,
            claim_verification_ref=claim_verification_ref,
            claim_verification_summary=claim_verification_summary,
            risk_decision_ref=risk_decision_ref,
            risk_decision=risk_decision,
            auto_allowed_binding_ref=auto_allowed_binding_ref,
        ):
            raise ValueError("idempotency_binding_conflict")
        return draft, inserted_id is not None

    async def get_by_run(self, run_id: UUID, tenant_id: UUID) -> list[ActionDraft]:
        stmt = select(ActionDraft).where(
            ActionDraft.run_id == run_id,
            ActionDraft.tenant_id == tenant_id,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def mark_failed(self, draft_id: UUID, tenant_id: UUID, error: str) -> None:
        stmt = select(ActionDraft).where(
            ActionDraft.id == draft_id,
            ActionDraft.tenant_id == tenant_id,
        )
        draft = (await self.session.execute(stmt)).scalar_one_or_none()
        if draft:
            draft.status = "failed"
            await self.session.flush()


def _same_binding(
    draft: ActionDraft,
    *,
    run_id: UUID,
    tenant_id: UUID,
    action_type: str,
    target_id: str,
    action_payload_hash: str,
    safety_snapshot_ref: str,
    safety_snapshot_hash: str,
    target_merchant_id: str | None,
    target_merchant_ref: dict[str, Any] | None,
    business_fact_refs: list[dict[str, Any]],
    verified_evidence_refs: list[dict[str, Any]],
    claim_verification_ref: str | None,
    claim_verification_summary: dict[str, Any] | None,
    risk_decision_ref: str | None,
    risk_decision: dict[str, Any] | None,
    auto_allowed_binding_ref: str | None,
) -> bool:
    return (
        draft.tenant_id == tenant_id
        and draft.run_id == run_id
        and draft.action_type == action_type
        and draft.target_id == target_id
        and draft.action_payload_hash == action_payload_hash
        and draft.safety_snapshot_ref == safety_snapshot_ref
        and draft.safety_snapshot_hash == safety_snapshot_hash
        and draft.target_merchant_id == target_merchant_id
        and draft.target_merchant_ref == target_merchant_ref
        and list(draft.business_fact_refs or []) == business_fact_refs
        and list(draft.verified_evidence_refs or []) == verified_evidence_refs
        and draft.claim_verification_ref == claim_verification_ref
        and draft.claim_verification_summary == claim_verification_summary
        and draft.risk_decision_ref == risk_decision_ref
        and draft.risk_decision == risk_decision
        and draft.auto_allowed_binding_ref == auto_allowed_binding_ref
    )
