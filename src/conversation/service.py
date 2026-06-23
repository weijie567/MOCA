from __future__ import annotations

from dataclasses import dataclass
import json
from hashlib import sha256
from typing import Any
import uuid

from sqlalchemy.exc import IntegrityError

from src.conversation.repository import ConversationRepository
from src.conversation.schemas import (
    ConversationAppendResult,
    ConversationMessageCreate,
    guard_forbidden_message_keys,
)
from src.db.models import ConversationMessage, ConversationSummary, ToolResultRecord
from src.tools.contracts import ToolResultPromptSummary, ToolResultV2


@dataclass(frozen=True)
class PromptContextWindow:
    thread_id: str
    run_id: uuid.UUID
    latest_thread_summary: ConversationSummary | None
    recent_messages: list[ConversationMessage]
    tool_prompt_summaries: list[ToolResultRecord]


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

    async def append_or_get_user_message_for_run(
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
        return await self._append_or_get_message_for_run(
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

    async def append_or_get_assistant_message_for_run(
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
        return await self._append_or_get_message_for_run(
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

    async def append_tool_call(
        self,
        *,
        tenant_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        thread_id: str,
        run_id: uuid.UUID | str,
        trace_id: str | None,
        tool_call_id: str,
        tool_name: str,
        caller_node: str,
        operation_id: uuid.UUID | str | None,
        attempt: int,
        arguments: dict[str, Any],
        argument_summary_json: dict[str, Any],
        redaction_policy_version: str,
        conversation_message_id: uuid.UUID | str | None = None,
    ):
        if self.repository is None:
            raise RuntimeError("ConversationRepository is required for append operations")
        argument_hash = _stable_hash(arguments)
        return await self.repository.append_tool_call(
            tenant_id=_coerce_uuid(tenant_id),
            user_id=_coerce_uuid(user_id),
            thread_id=thread_id,
            run_id=_coerce_uuid(run_id),
            trace_id=trace_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            caller_node=caller_node,
            operation_id=_coerce_optional_uuid(operation_id),
            attempt=attempt,
            argument_summary_json=argument_summary_json,
            argument_hash=argument_hash,
            redaction_policy_version=redaction_policy_version,
            conversation_message_id=_coerce_optional_uuid(conversation_message_id),
        )

    async def append_tool_result(
        self,
        *,
        tenant_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        thread_id: str,
        run_id: uuid.UUID | str,
        trace_id: str | None,
        operation_id: uuid.UUID | str | None,
        tool_call_id: str,
        tool_call_record_id: uuid.UUID | str | None,
        conversation_message_id: uuid.UUID | str | None = None,
        tool_result_id: str | None = None,
        tool_name: str,
        result: ToolResultV2,
        raw_result_ref: str | None = None,
        raw_result_hash: str | None = None,
        replay_event_id: uuid.UUID | str | None = None,
        projection: Any | None = None,
    ) -> ToolResultPromptSummary:
        if self.repository is None:
            raise RuntimeError("ConversationRepository is required for append operations")

        # Use projection data when available; otherwise create one.
        if projection is None:
            from src.tools.projection import ToolResultProjector
            projection = ToolResultProjector().project(
                tool_name=tool_name, result=result, tool_call_id=tool_call_id,
            )
        normalized_result_json = getattr(projection, "normalized_result", {}) or {}
        prompt_proj = getattr(projection, "prompt_projection", {}) or {}
        prompt_text = getattr(projection, "text_for_prompt", "") or ""
        business_fact_refs = prompt_proj.get("business_fact_refs", [])
        policy_evidence_refs = prompt_proj.get("policy_candidate_refs", [])
        audit_ref = result.audit_ref
        if getattr(projection, "audit_refs", None):
            for ref in projection.audit_refs:
                if ref:
                    audit_ref = ref
                    break

        stored_tool_result_id = tool_result_id or str(uuid.uuid4())
        if prompt_text:
            prompt_summary = prompt_text
        else:
            prompt_summary = _build_prompt_summary(
                tool_name=tool_name,
                status=result.status,
                summary=result.summary,
                source_system=result.source_system,
                business_fact_refs=business_fact_refs,
                policy_evidence_refs=policy_evidence_refs,
                raw_result_ref=raw_result_ref,
            )
        await self.repository.append_tool_result(
            tenant_id=_coerce_uuid(tenant_id),
            user_id=_coerce_uuid(user_id),
            thread_id=thread_id,
            run_id=_coerce_uuid(run_id),
            trace_id=trace_id,
            operation_id=_coerce_optional_uuid(operation_id),
            tool_call_id=tool_call_id,
            tool_call_record_id=_coerce_optional_uuid(tool_call_record_id),
            conversation_message_id=_coerce_optional_uuid(conversation_message_id),
            tool_result_id=stored_tool_result_id,
            status=result.status,
            source_system=result.source_system,
            data_freshness_at=result.data_freshness_at,
            latency_ms=result.latency_ms,
            raw_result_ref=raw_result_ref,
            raw_result_hash=raw_result_hash,
            normalized_result_json=normalized_result_json,
            summary=result.summary,
            prompt_summary=prompt_summary,
            business_fact_refs_json=business_fact_refs,
            policy_evidence_refs_json=policy_evidence_refs,
            audit_ref=audit_ref,
            replay_event_id=_coerce_optional_uuid(replay_event_id),
        )
        return ToolResultPromptSummary(
            tool_call_id=tool_call_id,
            tool_result_id=stored_tool_result_id,
            tool_name=tool_name,
            status=result.status,
            summary=result.summary,
            prompt_summary=prompt_summary,
            business_fact_refs=business_fact_refs,
            policy_evidence_refs=policy_evidence_refs,
            raw_result_ref=raw_result_ref,
            audit_ref=audit_ref,
        )

    async def load_prompt_context(
        self,
        *,
        tenant_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        thread_id: str,
        run_id: uuid.UUID | str,
        max_recent_messages: int = 8,
    ) -> PromptContextWindow:
        """Return latest committed prior-turn thread_rolling summary plus recent conversation_messages.

        The current turn stays visible through recent conversation_messages and tool prompt_summary rows,
        not by treating a same-run summary as already committed prior context.
        """
        if self.repository is None:
            raise RuntimeError("ConversationRepository is required for prompt context reads")
        tenant_uuid = _coerce_uuid(tenant_id)
        user_uuid = _coerce_uuid(user_id)
        run_uuid = _coerce_uuid(run_id)
        recent_messages = await self.repository.list_recent_messages(
            tenant_id=tenant_uuid,
            user_id=user_uuid,
            thread_id=thread_id,
            limit=max_recent_messages,
        )
        tool_prompt_summaries = await self.repository.list_recent_tool_prompt_summaries(
            tenant_id=tenant_uuid,
            user_id=user_uuid,
            thread_id=thread_id,
            limit=max_recent_messages,
        )
        latest_prior_summary = await self._latest_prior_thread_summary(
            tenant_id=tenant_uuid,
            user_id=user_uuid,
            thread_id=thread_id,
            current_run_id=run_uuid,
        )
        return PromptContextWindow(
            thread_id=thread_id,
            run_id=run_uuid,
            latest_thread_summary=latest_prior_summary,
            recent_messages=recent_messages,
            tool_prompt_summaries=tool_prompt_summaries,
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

    async def _append_or_get_message_for_run(
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
        if role not in {"user", "assistant"}:
            raise ValueError("run-role helper only supports user and assistant messages")
        if self.repository is None:
            raise RuntimeError("ConversationRepository is required for append operations")
        metadata = metadata_json or {}
        self.validate_safe_message_payload(content=content, metadata_json=metadata)
        existing = await self.repository.get_message_by_run_role(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            role=role,
        )
        if existing is not None:
            return _append_result_from_message(existing)

        try:
            async with self.repository.session.begin_nested():
                return await self._append_message(
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
                    metadata_json=metadata,
                )
        except IntegrityError:
            existing = await self.repository.get_message_by_run_role(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                role=role,
            )
            if existing is None:
                raise
            return _append_result_from_message(existing)

    async def _latest_prior_thread_summary(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        current_run_id: uuid.UUID,
    ) -> ConversationSummary | None:
        assert self.repository is not None
        summaries = await self.repository.list_thread_summaries(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            limit=10,
        )
        for summary in summaries:
            source_message_ids = [_coerce_uuid(message_id) for message_id in summary.source_message_ids_json]
            source_messages = await self.repository.list_messages_by_ids(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                message_ids=source_message_ids,
            )
            if all(message.run_id != current_run_id for message in source_messages):
                return summary
        return None


def _stable_hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def _build_prompt_summary(
    *,
    tool_name: str,
    status: str,
    summary: str,
    source_system: str,
    business_fact_refs: list[dict[str, Any]],
    policy_evidence_refs: list[dict[str, Any]],
    raw_result_ref: str | None,
) -> str:
    business_refs = [
        f"{ref.get('resource_type')}:{ref.get('resource_id')}"
        for ref in business_fact_refs
        if ref.get("resource_type") and ref.get("resource_id")
    ]
    evidence_refs = [str(ref.get("evidence_id")) for ref in policy_evidence_refs if ref.get("evidence_id")]
    parts = [
        f"{tool_name} {status} from {source_system}",
        _bounded_text(summary, 240),
    ]
    if business_refs:
        parts.append(f"business refs: {', '.join(business_refs[:5])}")
    if evidence_refs:
        parts.append(f"policy refs: {', '.join(evidence_refs[:5])}")
    return " | ".join(parts)


def _append_result_from_message(row: ConversationMessage) -> ConversationAppendResult:
    return ConversationAppendResult(
        thread_id=row.thread_id,
        conversation_thread_id=row.conversation_thread_id,
        message_id=row.id,
        message_index=row.message_index,
        role=row.role,
    )


def _bounded_text(value: str, limit: int) -> str:
    stripped = " ".join(value.split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 3]}..."


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _coerce_optional_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    return _coerce_uuid(value)
