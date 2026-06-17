from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.schemas import ConversationMessageCreate
from src.db.models import ConversationMessage, ConversationThread, ToolCallRecord, ToolResultRecord


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

    async def append_tool_call(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        trace_id: str | None,
        tool_call_id: str,
        tool_name: str,
        caller_node: str,
        operation_id: uuid.UUID | None,
        attempt: int,
        argument_summary_json: dict[str, Any],
        argument_hash: str,
        redaction_policy_version: str,
        status: str = "started",
        conversation_message_id: uuid.UUID | None = None,
    ) -> ToolCallRecord:
        thread = await self.get_or_create_thread(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)
        row = ToolCallRecord(
            id=uuid.uuid4(),
            conversation_thread_id=thread.id,
            conversation_message_id=conversation_message_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            run_id=run_id,
            trace_id=trace_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            caller_node=caller_node,
            operation_id=operation_id,
            attempt=attempt,
            argument_summary_json=dict(argument_summary_json),
            argument_hash=argument_hash,
            redaction_policy_version=redaction_policy_version,
            status=status,
            started_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def append_tool_result(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        trace_id: str | None,
        operation_id: uuid.UUID | None,
        tool_call_id: str,
        tool_call_record_id: uuid.UUID | None,
        tool_result_id: str,
        status: str,
        source_system: str,
        data_freshness_at: datetime | None,
        latency_ms: int | None,
        raw_result_ref: str | None,
        raw_result_hash: str | None,
        normalized_result_json: dict[str, Any],
        summary: str,
        prompt_summary: str,
        business_fact_refs_json: list[dict[str, Any]],
        policy_evidence_refs_json: list[dict[str, Any]],
        audit_ref: str | None,
        conversation_message_id: uuid.UUID | None = None,
        replay_event_id: uuid.UUID | None = None,
    ) -> ToolResultRecord:
        thread = await self.get_or_create_thread(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)
        row = ToolResultRecord(
            id=uuid.uuid4(),
            conversation_thread_id=thread.id,
            tool_call_record_id=tool_call_record_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            run_id=run_id,
            trace_id=trace_id,
            operation_id=operation_id,
            conversation_message_id=conversation_message_id,
            tool_call_id=tool_call_id,
            tool_result_id=tool_result_id,
            status=status,
            source_system=source_system,
            data_freshness_at=data_freshness_at,
            latency_ms=latency_ms,
            raw_result_ref=raw_result_ref,
            raw_result_hash=raw_result_hash,
            normalized_result_json=dict(normalized_result_json),
            summary=summary,
            prompt_summary=prompt_summary,
            business_fact_refs_json=list(business_fact_refs_json),
            policy_evidence_refs_json=list(policy_evidence_refs_json),
            audit_ref=audit_ref,
            replay_event_id=replay_event_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

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
