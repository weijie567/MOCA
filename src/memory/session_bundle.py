from __future__ import annotations

from typing import Any
import uuid

from src.conversation.service import ConversationService, PromptContextWindow
from src.memory.schemas import (
    SessionContextBundle,
    SessionContextMemory,
    SessionMemoryBundle,
    SessionMemoryView,
    SessionRecentMessageView,
    SessionRollingSummaryView,
    SessionToolSummaryView,
)
from src.memory.service import MemoryService

_BUSINESS_HINT_REF_KEYS = ("source_system", "resource_type", "resource_id", "resource_version")
_POLICY_HINT_REF_KEYS = ("doc_key", "chunk_id", "policy_version", "policy_family", "title", "section")
_POLICY_HINT_LIMIT = 8
_PROMPT_SUMMARY_LIMIT = 1200
_HINT_VALUE_LIMIT = 120
_FORBIDDEN_HINT_MARKERS = (
    "raw_payload",
    "raw_tool_output",
    "private_reasoning",
    "approval_authority_body",
    "action_authority_body",
    "action_authorization",
    "debug_blob",
    "debug_trace",
    "replay_debug_blob",
    "replay_event",
    "secret",
    "EvidenceRefV1",
    "ReplayEventV3",
)


class SessionMemoryBundleService:
    def __init__(self, *, conversation_service: ConversationService, memory_service: MemoryService) -> None:
        self.conversation_service = conversation_service
        self.memory_service = memory_service

    async def load_session_memory_bundle(
        self,
        *,
        tenant_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        thread_id: str,
        run_id: uuid.UUID | str,
        current_intent: str | None,
        max_recent_messages: int = 8,
    ) -> SessionMemoryBundle:
        fallback_reasons: dict[str, str] = {}
        try:
            prompt_context = await self.conversation_service.load_prompt_context(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                max_recent_messages=max_recent_messages,
            )
        except Exception:
            prompt_context = None
            fallback_reasons["prompt_context"] = "unavailable"

        try:
            slot_continuity = await self.memory_service.load_session_memory(
                tenant_id,
                user_id,
                thread_id,
                current_intent=current_intent,
            )
        except Exception:
            slot_continuity = _empty_slot_continuity("unavailable")
            fallback_reasons["slot_continuity"] = "unavailable"

        if slot_continuity.fallback_reason:
            fallback_reasons.setdefault("slot_continuity", slot_continuity.fallback_reason)

        tool_summaries = _tool_summary_views(prompt_context)
        return SessionMemoryBundle(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            thread_id=thread_id,
            run_id=str(run_id),
            rolling_summary=_rolling_summary_view(prompt_context),
            recent_messages=_recent_message_views(prompt_context),
            tool_summaries=tool_summaries,
            slot_continuity=slot_continuity,
            policy_topic_hints=_policy_topic_hints(tool_summaries),
            prior_policy_mention_refs=_prior_policy_mention_refs(tool_summaries),
            fallback_reasons=fallback_reasons,
        )


def project_session_context_memory(bundle: SessionMemoryBundle) -> dict[str, Any]:
    context_memory = SessionContextMemory.model_validate(bundle)
    return SessionContextBundle(session_context=context_memory).model_dump(mode="json")


def _rolling_summary_view(prompt_context: PromptContextWindow | None) -> SessionRollingSummaryView | None:
    if prompt_context is None or prompt_context.latest_thread_summary is None:
        return None
    summary = prompt_context.latest_thread_summary
    return SessionRollingSummaryView(
        summary_id=str(getattr(summary, "id", None) or "latest_thread_summary"),
        summary_text=getattr(summary, "summary_text", None) or "",
        source_message_ids=list(getattr(summary, "source_message_ids_json", None) or []),
        source_tool_result_ids=list(getattr(summary, "source_tool_result_ids_json", None) or []),
        created_at=getattr(summary, "created_at", None),
    )


def _recent_message_views(prompt_context: PromptContextWindow | None) -> list[SessionRecentMessageView]:
    if prompt_context is None:
        return []
    return [
        SessionRecentMessageView(
            message_id=str(getattr(message, "id", None) or f"recent_message_{index}"),
            run_id=str(getattr(message, "run_id", None) or getattr(prompt_context, "run_id", None) or "unknown_run"),
            message_index=getattr(message, "message_index", index),
            role=getattr(message, "role", "user"),
            content=getattr(message, "content", ""),
            created_at=getattr(message, "created_at", None),
        )
        for index, message in enumerate(prompt_context.recent_messages)
    ]


def _tool_summary_views(prompt_context: PromptContextWindow | None) -> list[SessionToolSummaryView]:
    if prompt_context is None:
        return []
    views: list[SessionToolSummaryView] = []
    for record in prompt_context.tool_prompt_summaries:
        raw_prompt_summary = getattr(record, "prompt_summary", None)
        if not raw_prompt_summary:
            continue
        prompt_summary = _safe_prompt_summary(raw_prompt_summary) or "Tool result summary unavailable."
        record_id = (
            getattr(record, "id", None)
            or getattr(record, "tool_result_id", None)
            or getattr(record, "tool_call_id", None)
            or f"tool_summary_{len(views)}"
        )
        views.append(
            SessionToolSummaryView(
                tool_result_record_id=str(record_id),
                tool_result_id=getattr(record, "tool_result_id", None),
                run_id=str(getattr(record, "run_id", None)) if getattr(record, "run_id", None) is not None else None,
                tool_call_id=getattr(record, "tool_call_id", None),
                tool_name=_tool_name_for_record(record),
                status=getattr(record, "status", "success"),
                prompt_summary=prompt_summary,
                business_fact_refs=_prompt_safe_refs(
                    getattr(record, "business_fact_refs_json", None),
                    allowed_keys=_BUSINESS_HINT_REF_KEYS,
                ),
                policy_evidence_refs=_prompt_safe_refs(
                    getattr(record, "policy_evidence_refs_json", None),
                    allowed_keys=_POLICY_HINT_REF_KEYS,
                ),
                audit_ref=getattr(record, "audit_ref", None),
                created_at=getattr(record, "created_at", None),
            )
        )
    return views


def _tool_name_for_record(record) -> str | None:
    tool_call = getattr(record, "tool_call", None)
    return getattr(tool_call, "tool_name", None) or getattr(record, "tool_name", None)


def _policy_topic_hints(tool_summaries: list[SessionToolSummaryView]) -> list[str]:
    hints: list[str] = []
    for summary in tool_summaries:
        for ref in summary.policy_evidence_refs:
            hint = _policy_topic_hint(ref)
            if hint and hint not in hints:
                hints.append(hint)
            if len(hints) >= _POLICY_HINT_LIMIT:
                return hints
    return hints


def _policy_topic_hint(ref: dict[str, Any]) -> str | None:
    policy_family = _safe_hint_value(ref.get("policy_family"))
    if policy_family:
        return policy_family
    doc_key = _safe_hint_value(ref.get("doc_key"))
    policy_version = _safe_hint_value(ref.get("policy_version"))
    if doc_key and policy_version:
        return f"{doc_key}@{policy_version}"
    if doc_key:
        return doc_key
    title = _safe_hint_value(ref.get("title"))
    if title:
        return title[:80]
    section = _safe_hint_value(ref.get("section"))
    return section[:80] if section else None


def _prior_policy_mention_refs(tool_summaries: list[SessionToolSummaryView]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for summary in tool_summaries:
        for ref in summary.policy_evidence_refs:
            mention = {
                key: value
                for key in _POLICY_HINT_REF_KEYS
                if (value := _safe_hint_value(ref.get(key))) is not None
            }
            tool_result_id = _safe_hint_value(summary.tool_result_id)
            if tool_result_id is not None:
                mention["tool_result_id"] = tool_result_id
            if not mention:
                continue
            identity = tuple(sorted(mention.items()))
            if identity in seen:
                continue
            seen.add(identity)
            refs.append(mention)
            if len(refs) >= _POLICY_HINT_LIMIT:
                return refs
    return refs


def _prompt_safe_refs(value: Any, *, allowed_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        ref = {key: safe_value for key in allowed_keys if (safe_value := _safe_hint_value(item.get(key))) is not None}
        if ref:
            refs.append(ref)
    return refs


def _safe_hint_value(value: Any) -> str | None:
    return _safe_bundle_text(value, max_chars=_HINT_VALUE_LIMIT)


def _safe_prompt_summary(value: Any) -> str | None:
    return _safe_bundle_text(value, max_chars=_PROMPT_SUMMARY_LIMIT)


def _safe_bundle_text(value: Any, *, max_chars: int) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        text = str(value)
    elif isinstance(value, str):
        text = " ".join(value.split())
    else:
        return None
    for marker in _FORBIDDEN_HINT_MARKERS:
        text = text.replace(marker, "")
    text = " ".join(text.split())
    return text[:max_chars] if text else None


def _empty_slot_continuity(reason: str) -> SessionMemoryView:
    return SessionMemoryView(
        source="empty_adapter",
        continuity_claimed=False,
        active_slots={},
        slot_metadata={},
        fallback_reason=reason,
    )
