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
        payload: dict[str, Any],
    ) -> tuple[ActionDraft, bool]:
        return await self.repository.create_or_get(
            run_id=run_id,
            tenant_id=tenant_id,
            approval_request_id=approval_request_id,
            idempotency_key=idempotency_key,
            action_type=action_type,
            payload=payload,
        )
