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
            draft_outcome=draft_outcome,
            execution_mode=execution_mode,
            draft_version=draft_version,
            lifecycle_status=lifecycle_status,
            retention_policy=retention_policy,
        )
