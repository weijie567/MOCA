from __future__ import annotations

from hashlib import sha256
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.schemas import ConversationMessageCreate
from src.db.models import ConversationMessage, ConversationThread


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_thread(self, *, tenant_id: uuid.UUID, thread_id: str) -> ConversationThread | None:
        result = await self.session.execute(
            select(ConversationThread).where(
                ConversationThread.tenant_id == tenant_id,
                ConversationThread.thread_id == thread_id,
                ConversationThread.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_thread(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        case_id: str | None = None,
    ) -> ConversationThread:
        thread = await self.get_thread(tenant_id=tenant_id, thread_id=thread_id)
        if thread is not None:
            return thread
        thread = ConversationThread(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            case_id=case_id,
            status="active",
        )
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def append_message(self, message: ConversationMessageCreate) -> ConversationMessage:
        thread = await self.get_or_create_thread(
            tenant_id=message.tenant_id,
            user_id=message.user_id,
            thread_id=message.thread_id,
        )
        next_index = await self._next_message_index(tenant_id=message.tenant_id, thread_id=message.thread_id)
        row = ConversationMessage(
            id=uuid.uuid4(),
            conversation_thread_id=thread.id,
            tenant_id=message.tenant_id,
            thread_id=message.thread_id,
            run_id=message.run_id,
            trace_id=message.trace_id,
            message_index=next_index,
            role=message.role,
            content=message.content,
            content_hash=_content_hash(message.content),
            prompt_template_version=message.prompt_template_version,
            prompt_block_hashes_json=list(message.prompt_block_hashes_json),
            context_snapshot_ref=message.context_snapshot_ref,
            redacted_prompt_snapshot_ref=message.redacted_prompt_snapshot_ref,
            metadata_json=dict(message.metadata_json),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_messages(
        self,
        *,
        tenant_id: uuid.UUID,
        thread_id: str,
        limit: int | None = None,
    ) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(
                and_(
                    ConversationMessage.tenant_id == tenant_id,
                    ConversationMessage.thread_id == thread_id,
                    ConversationMessage.deleted_at.is_(None),
                )
            )
            .order_by(ConversationMessage.message_index)
        )
        if limit is not None:
            stmt = stmt.limit(max(limit, 1))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _next_message_index(self, *, tenant_id: uuid.UUID, thread_id: str) -> int:
        result = await self.session.execute(
            select(func.max(ConversationMessage.message_index)).where(
                ConversationMessage.tenant_id == tenant_id,
                ConversationMessage.thread_id == thread_id,
                ConversationMessage.deleted_at.is_(None),
            )
        )
        return int(result.scalar_one_or_none() or 0) + 1


def _content_hash(content: str) -> str:
    return f"sha256:{sha256(content.encode('utf-8')).hexdigest()}"
