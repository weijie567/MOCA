from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ThreadCaseLink


ALLOWED_THREAD_CASE_LINK_SOURCES = frozenset({"run_auto", "staff_manual", "import"})


class ThreadCaseLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def link_thread_to_case(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation_thread_id: uuid.UUID,
        thread_id: str,
        case_id: uuid.UUID,
        link_source: str,
        linked_by_run_id: uuid.UUID | None = None,
    ) -> ThreadCaseLink:
        if link_source not in ALLOWED_THREAD_CASE_LINK_SOURCES:
            raise ValueError(f"link_source must be one of {sorted(ALLOWED_THREAD_CASE_LINK_SOURCES)}")

        existing = await self._get_active_link(
            tenant_id=tenant_id,
            conversation_thread_id=conversation_thread_id,
            case_id=case_id,
        )
        if existing is not None:
            return existing

        link = ThreadCaseLink(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            conversation_thread_id=conversation_thread_id,
            thread_id=thread_id,
            case_id=case_id,
            link_source=link_source,
            linked_by_run_id=linked_by_run_id,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def list_cases_for_thread(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation_thread_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        result = await self.session.execute(
            select(ThreadCaseLink.case_id)
            .where(
                ThreadCaseLink.tenant_id == tenant_id,
                ThreadCaseLink.conversation_thread_id == conversation_thread_id,
                ThreadCaseLink.deleted_at.is_(None),
            )
            .order_by(ThreadCaseLink.created_at, ThreadCaseLink.id)
        )
        return list(result.scalars().all())

    async def list_threads_for_case(
        self,
        *,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> list[ThreadCaseLink]:
        result = await self.session.execute(
            select(ThreadCaseLink)
            .where(
                ThreadCaseLink.tenant_id == tenant_id,
                ThreadCaseLink.case_id == case_id,
                ThreadCaseLink.deleted_at.is_(None),
            )
            .order_by(ThreadCaseLink.created_at, ThreadCaseLink.id)
        )
        return list(result.scalars().all())

    async def _get_active_link(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation_thread_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> ThreadCaseLink | None:
        result = await self.session.execute(
            select(ThreadCaseLink).where(
                ThreadCaseLink.tenant_id == tenant_id,
                ThreadCaseLink.conversation_thread_id == conversation_thread_id,
                ThreadCaseLink.case_id == case_id,
                ThreadCaseLink.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
