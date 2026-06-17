from __future__ import annotations

from dataclasses import dataclass
import json
import re
from hashlib import sha256
from typing import Any
import uuid

from src.conversation.repository import ConversationRepository
from src.db.models import ConversationMessage, ConversationSummary, ToolResultRecord


THREAD_ROLLING_SUMMARY_TYPE = "thread_rolling"
THREAD_SUMMARY_MODEL = "deterministic-thread-summary.v1"
THREAD_SUMMARY_PROMPT_VERSION = "thread_summary.v1"
_SUMMARY_TEXT_LIMIT = 4000
_RAW_REF_PREFIX = "raw result ref:"
_FORBIDDEN_RAW_KEYS = {
    "raw",
    "raw_payload",
    "raw_tool_output",
    "raw_policy_text",
    "approval_authority_body",
    "action_authority_body",
}
_BUSINESS_ID_RE = re.compile(r"\b(?:ORD|RF|TK|MER|REFUND|ORDER)-[A-Z0-9-]+\b")
_DECISION_MARKERS = ("关键决策", "决策", "decision")
_QUESTION_MARKERS = ("开放问题", "问题", "question", "?")
_CONSTRAINT_MARKERS = ("约束", "限制", "不能", "constraint", "unresolved constraint")


@dataclass(frozen=True)
class ThreadSummaryUpdateInput:
    old_summary: ConversationSummary | None
    new_messages: list[ConversationMessage]
    important_tool_results: list[ToolResultRecord]


@dataclass(frozen=True)
class DerivedThreadSummary:
    summary_text: str
    summary_json: dict[str, Any]
    summary_hash: str


class ThreadRollingSummaryService:
    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository

    async def build_update_input(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        since_message_id: uuid.UUID | None = None,
    ) -> ThreadSummaryUpdateInput:
        old_summary = await self.repository.get_latest_thread_summary(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
        )
        effective_since = since_message_id
        if effective_since is None and old_summary is not None:
            effective_since = old_summary.source_end_message_id
        new_messages = await self.repository.list_messages_after(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            since_message_id=effective_since,
        )
        tool_results = await self.repository.list_tool_results_after_summary(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            previous_summary=old_summary,
        )
        return ThreadSummaryUpdateInput(
            old_summary=old_summary,
            new_messages=new_messages,
            important_tool_results=tool_results,
        )

    def derive_summary(
        self,
        old_summary: ConversationSummary | None,
        new_messages: list[ConversationMessage],
        important_tool_results: list[ToolResultRecord],
    ) -> DerivedThreadSummary:
        lines: list[str] = []
        if old_summary is not None and old_summary.summary_text:
            lines.extend(_split_summary_lines(_sanitize_text(old_summary.summary_text)))

        for message in new_messages:
            content = _sanitize_text(message.content)
            if content:
                lines.append(f"{message.role}: {content}")

        for result in important_tool_results:
            summary = _safe_tool_summary(result)
            if summary:
                tool_ref = result.tool_result_id or str(result.id)
                lines.append(f"tool {tool_ref}: {summary}")

        deduped_lines = _dedupe_preserving_order(lines)
        summary_text = _bounded_text("\n".join(deduped_lines), _SUMMARY_TEXT_LIMIT)
        summary_json = _summary_json(summary_text, new_messages, important_tool_results)
        summary_hash = _stable_hash({"summary_text": summary_text, "summary_json": summary_json})
        return DerivedThreadSummary(
            summary_text=summary_text,
            summary_json=summary_json,
            summary_hash=summary_hash,
        )

    async def persist_thread_summary(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID | None = None,
        since_message_id: uuid.UUID | None = None,
    ) -> ConversationSummary | None:
        del run_id
        update_input = await self.build_update_input(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            since_message_id=since_message_id,
        )
        if not update_input.new_messages:
            return None

        derived = self.derive_summary(
            update_input.old_summary,
            update_input.new_messages,
            update_input.important_tool_results,
        )
        source_message_ids = [str(message.id) for message in update_input.new_messages]
        source_tool_result_ids = [str(result.id) for result in update_input.important_tool_results]
        return await self.repository.insert_thread_summary(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            source_start_message_id=update_input.new_messages[0].id,
            source_end_message_id=update_input.new_messages[-1].id,
            source_message_ids_json=source_message_ids,
            source_tool_result_ids_json=source_tool_result_ids,
            summary_text=derived.summary_text,
            summary_json=derived.summary_json,
            summary_model=THREAD_SUMMARY_MODEL,
            summary_prompt_version=THREAD_SUMMARY_PROMPT_VERSION,
            summary_hash=derived.summary_hash,
        )


def _safe_tool_summary(result: ToolResultRecord) -> str:
    candidates = [result.prompt_summary, result.summary]
    for candidate in candidates:
        sanitized = _sanitize_text(candidate or "")
        if sanitized:
            return sanitized
    return ""


def _sanitize_text(value: str) -> str:
    compact = " ".join(value.split())
    if not compact:
        return ""
    segments = [segment.strip() for segment in compact.split(" | ") if segment.strip()]
    kept_segments = [segment for segment in segments if not segment.lower().startswith(_RAW_REF_PREFIX)]
    sanitized = " | ".join(kept_segments) if kept_segments else compact
    for key in sorted(_FORBIDDEN_RAW_KEYS, key=len, reverse=True):
        sanitized = re.sub(rf"\b{re.escape(key)}\b\s*[:=]?", "[redacted]", sanitized, flags=re.IGNORECASE)
    return sanitized


def _split_summary_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _dedupe_preserving_order(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _summary_json(
    summary_text: str,
    messages: list[ConversationMessage],
    tool_results: list[ToolResultRecord],
) -> dict[str, Any]:
    lines = _split_summary_lines(summary_text)
    return {
        "schema_version": "thread_rolling_summary.v1",
        "confirmed_business_ids": _extract_business_ids(summary_text),
        "key_decisions": _lines_with_markers(lines, _DECISION_MARKERS),
        "open_questions": _lines_with_markers(lines, _QUESTION_MARKERS),
        "unresolved_constraints": _lines_with_markers(lines, _CONSTRAINT_MARKERS),
        "source_message_count": len(messages),
        "source_tool_result_count": len(tool_results),
    }


def _extract_business_ids(value: str) -> list[str]:
    return sorted(set(_BUSINESS_ID_RE.findall(value)))


def _lines_with_markers(lines: list[str], markers: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for line in lines:
        lowered = line.lower()
        if any(marker.lower() in lowered for marker in markers):
            matched.append(line)
    return matched[:10]


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 24]}\n[summary_truncated]"


def _stable_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"
