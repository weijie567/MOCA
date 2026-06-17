from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
import uuid

from src.conversation.repository import ConversationRepository
from src.conversation.schemas import (
    ConversationAppendResult,
    ConversationMessageCreate,
    guard_forbidden_message_keys,
)
from src.tools.contracts import ToolResultPromptSummary, ToolResultV2


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
        tool_result_id: str | None = None,
        tool_name: str,
        result: ToolResultV2,
        raw_result_ref: str | None = None,
        raw_result_hash: str | None = None,
        replay_event_id: uuid.UUID | str | None = None,
    ) -> ToolResultPromptSummary:
        if self.repository is None:
            raise RuntimeError("ConversationRepository is required for append operations")
        normalized_result_json = result.data or {}
        business_fact_refs = [ref.model_dump(mode="json") for ref in result.business_fact_refs]
        policy_evidence_refs = [ref.model_dump(mode="json") for ref in result.policy_evidence_refs]
        stored_tool_result_id = tool_result_id or str(uuid.uuid4())
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
            audit_ref=result.audit_ref,
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
            audit_ref=result.audit_ref,
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
    if raw_result_ref:
        parts.append(f"raw result ref: {raw_result_ref}")
    return " | ".join(parts)


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
