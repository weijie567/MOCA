from __future__ import annotations

from typing import Any
import uuid

from src.conversation.repository import ConversationRepository
from src.conversation.schemas import (
    ConversationAppendResult,
    ConversationMessageCreate,
    guard_forbidden_message_keys,
)


class ConversationService:
    def __init__(self, repository: ConversationRepository | None) -> None:
        self.repository = repository

    def validate_safe_message_payload(self, *, content: Any, metadata_json: dict[str, Any] | None = None) -> None:
        guard_forbidden_message_keys({"content": content, "metadata_json": metadata_json or {}})

    async def append_user_message(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        content: str,
        trace_id: str | None = None,
        prompt_template_version: str | None = None,
        prompt_block_hashes_json: list[str] | None = None,
        context_snapshot_ref: str | None = None,
        redacted_prompt_snapshot_ref: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ConversationAppendResult:
        return await self._append_message(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            role="user",
            content=content,
            trace_id=trace_id,
            prompt_template_version=prompt_template_version,
            prompt_block_hashes_json=prompt_block_hashes_json or [],
            context_snapshot_ref=context_snapshot_ref,
            redacted_prompt_snapshot_ref=redacted_prompt_snapshot_ref,
            metadata_json=metadata_json or {},
        )

    async def append_assistant_message(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        content: str,
        trace_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ConversationAppendResult:
        return await self._append_message(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            role="assistant",
            content=content,
            trace_id=trace_id,
            metadata_json=metadata_json or {},
        )

    async def append_tool_summary_message(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        content: str,
        trace_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ConversationAppendResult:
        return await self._append_message(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            role="tool",
            content=content,
            trace_id=trace_id,
            metadata_json=metadata_json or {},
        )

    async def _append_message(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        role: str,
        content: str,
        trace_id: str | None = None,
        prompt_template_version: str | None = None,
        prompt_block_hashes_json: list[str] | None = None,
        context_snapshot_ref: str | None = None,
        redacted_prompt_snapshot_ref: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ConversationAppendResult:
        if self.repository is None:
            raise RuntimeError("ConversationRepository is required for append operations")
        self.validate_safe_message_payload(content=content, metadata_json=metadata_json)
        row = await self.repository.append_message(
            ConversationMessageCreate(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                role=role,
                content=content,
                trace_id=trace_id,
                prompt_template_version=prompt_template_version,
                prompt_block_hashes_json=prompt_block_hashes_json or [],
                context_snapshot_ref=context_snapshot_ref,
                redacted_prompt_snapshot_ref=redacted_prompt_snapshot_ref,
                metadata_json=metadata_json or {},
            )
        )
        return ConversationAppendResult(
            thread_id=row.thread_id,
            conversation_thread_id=row.conversation_thread_id,
            message_id=row.id,
            message_index=row.message_index,
            role=row.role,
        )
