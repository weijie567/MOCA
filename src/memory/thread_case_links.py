from __future__ import annotations

from hashlib import sha256
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, ConversationThread, RefundCase, ThreadCaseLink


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

        await self._lock_link_scope(
            tenant_id=tenant_id,
            conversation_thread_id=conversation_thread_id,
            case_id=case_id,
        )
        validated_thread_id = await self._validate_scope(
            tenant_id=tenant_id,
            conversation_thread_id=conversation_thread_id,
            case_id=case_id,
            linked_by_run_id=linked_by_run_id,
        )
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
            thread_id=validated_thread_id,
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

    async def _validate_scope(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation_thread_id: uuid.UUID,
        case_id: uuid.UUID,
        linked_by_run_id: uuid.UUID | None,
    ) -> str:
        thread_result = await self.session.execute(
            select(ConversationThread.thread_id).where(
                ConversationThread.id == conversation_thread_id,
                ConversationThread.tenant_id == tenant_id,
                ConversationThread.deleted_at.is_(None),
            )
        )
        thread_id = thread_result.scalar_one_or_none()
        if thread_id is None:
            raise ValueError("conversation_thread_id does not belong to tenant")

        case_result = await self.session.execute(
            select(RefundCase.id).where(
                RefundCase.id == case_id,
                RefundCase.tenant_id == tenant_id,
            )
        )
        if case_result.scalar_one_or_none() is None:
            raise ValueError("case_id does not belong to tenant")

        if linked_by_run_id is not None:
            run_result = await self.session.execute(
                select(AgentRun.id).where(
                    AgentRun.id == linked_by_run_id,
                    AgentRun.tenant_id == tenant_id,
                )
            )
            if run_result.scalar_one_or_none() is None:
                raise ValueError("linked_by_run_id does not belong to tenant")

        return thread_id

    async def _lock_link_scope(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation_thread_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> None:
        lock_key = _thread_case_link_lock_key(
            tenant_id=tenant_id,
            conversation_thread_id=conversation_thread_id,
            case_id=case_id,
        )
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))


def _thread_case_link_lock_key(
    *,
    tenant_id: uuid.UUID,
    conversation_thread_id: uuid.UUID,
    case_id: uuid.UUID,
) -> int:
    identity = f"thread-case-link:{tenant_id}:{conversation_thread_id}:{case_id}".encode("utf-8")
    unsigned = int.from_bytes(sha256(identity).digest()[:8], "big", signed=False)
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned
