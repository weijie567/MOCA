from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
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
        payload: dict[str, Any],
    ) -> tuple[ActionDraft, bool]:
        stmt = select(ActionDraft).where(ActionDraft.idempotency_key == idempotency_key)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            if existing.tenant_id != tenant_id:
                raise ValueError("idempotency_key_conflict")
            return existing, False

        draft = ActionDraft(
            run_id=run_id,
            tenant_id=tenant_id,
            approval_request_id=approval_request_id,
            idempotency_key=idempotency_key,
            action_type=action_type,
            status="draft_created",
            payload=payload,
            created_by_agent_run=run_id,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft, True

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
