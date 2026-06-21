from __future__ import annotations

import uuid

from src.conversation.service import ConversationService, PromptContextWindow
from src.memory.schemas import (
    SessionMemoryBundle,
    SessionMemoryView,
    SessionRecentMessageView,
    SessionRollingSummaryView,
    SessionToolSummaryView,
)
from src.memory.service import MemoryService


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

        return SessionMemoryBundle(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            thread_id=thread_id,
            run_id=str(run_id),
            rolling_summary=_rolling_summary_view(prompt_context),
            recent_messages=_recent_message_views(prompt_context),
            tool_summaries=_tool_summary_views(prompt_context),
            slot_continuity=slot_continuity,
            fallback_reasons=fallback_reasons,
        )


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
        prompt_summary = getattr(record, "prompt_summary", None)
        if not prompt_summary:
            continue
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
                business_fact_refs=list(getattr(record, "business_fact_refs_json", None) or []),
                policy_evidence_refs=list(getattr(record, "policy_evidence_refs_json", None) or []),
                audit_ref=getattr(record, "audit_ref", None),
                created_at=getattr(record, "created_at", None),
            )
        )
    return views


def _tool_name_for_record(record) -> str | None:
    tool_call = getattr(record, "tool_call", None)
    return getattr(tool_call, "tool_name", None) or getattr(record, "tool_name", None)


def _empty_slot_continuity(reason: str) -> SessionMemoryView:
    return SessionMemoryView(
        source="empty_adapter",
        continuity_claimed=False,
        active_slots={},
        slot_metadata={},
        fallback_reason=reason,
    )
