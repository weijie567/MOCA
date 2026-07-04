from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from pydantic import ValidationError

from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionContextBundle, SessionMemoryBundle, SessionMemoryView, SessionToolSummaryView
from src.memory.service import MemoryService
from src.memory.session_bundle import SessionMemoryBundleService
from src.tools.contracts import ToolResultPromptSummary

EMPTY_SESSION_PROMPT_CONTEXT: dict[str, Any] = {
    "thread_rolling_summary": "",
    "recent_messages": [],
    "tool_result_summaries": [],
}
_TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$")


async def load_session_prompt_context(state: Mapping[str, Any], config: Mapping[str, Any] | None) -> dict[str, Any]:
    bundle = await load_session_memory_bundle_for_state(state, config)
    if bundle is None:
        return dict(EMPTY_SESSION_PROMPT_CONTEXT)
    return project_session_memory_bundle_for_prompt(bundle)


async def load_session_memory_bundle_for_state(
    state: Mapping[str, Any],
    config: Mapping[str, Any] | None,
    *,
    max_recent_messages: int = 8,
) -> SessionMemoryBundle | None:
    existing = session_context_bundle_from_state(state)
    if existing is not None:
        return existing

    existing = session_memory_bundle_from_state(state)
    if existing is not None:
        return existing

    configurable = ((config or {}).get("configurable") or {}) if config else {}
    session = configurable.get("session")
    conversation_service = configurable.get("conversation_service")
    if conversation_service is None:
        if not hasattr(session, "execute"):
            return None
        conversation_service = ConversationService(ConversationRepository(session))

    memory_service = configurable.get("memory_service")
    if memory_service is None:
        if hasattr(session, "execute"):
            memory_service = MemoryService(SessionMemoryRepository(session))
        else:
            memory_service = _StateSlotContinuityMemoryService(state)

    run_id = state.get("current_run_id") or state.get("run_id")
    if not state.get("tenant_id") or not state.get("user_id") or not state.get("thread_id") or not run_id:
        return None

    try:
        return await SessionMemoryBundleService(
            conversation_service=conversation_service,
            memory_service=memory_service,
        ).load_session_memory_bundle(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            thread_id=str(state["thread_id"]),
            run_id=run_id,
            current_intent=state.get("primary_intent") or state.get("current_intent"),
            max_recent_messages=max_recent_messages,
        )
    except Exception:
        return None


def session_context_bundle_from_state(state: Mapping[str, Any]) -> SessionMemoryBundle | None:
    raw = state.get("session_context_bundle")
    if isinstance(raw, SessionContextBundle):
        context = raw.session_context
    elif isinstance(raw, dict):
        try:
            context = SessionContextBundle.model_validate(raw).session_context
        except ValidationError:
            return None
    else:
        return None

    bundle = SessionMemoryBundle(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        thread_id=context.thread_id,
        run_id=context.run_id,
        rolling_summary=context.rolling_summary,
        recent_messages=list(context.recent_messages),
        tool_summaries=list(context.tool_summaries),
        slot_continuity=context.slot_continuity,
        policy_topic_hints=list(context.policy_topic_hints),
        prior_policy_mention_refs=[dict(ref) for ref in context.prior_policy_mention_refs],
        fallback_reasons=dict(context.fallback_reasons),
    )
    return bundle if _bundle_matches_state(bundle, state) else None


def session_memory_bundle_from_state(state: Mapping[str, Any]) -> SessionMemoryBundle | None:
    raw = state.get("session_memory_bundle")
    if isinstance(raw, SessionMemoryBundle):
        bundle = raw
    elif isinstance(raw, dict):
        try:
            bundle = SessionMemoryBundle.model_validate(raw)
        except ValidationError:
            return None
    else:
        return None
    return bundle if _bundle_matches_state(bundle, state) else None


def _bundle_matches_state(bundle: SessionMemoryBundle, state: Mapping[str, Any]) -> bool:
    run_id = state.get("current_run_id") or state.get("run_id")
    required = {
        "tenant_id": state.get("tenant_id"),
        "user_id": state.get("user_id"),
        "thread_id": state.get("thread_id"),
        "run_id": run_id,
    }
    if any(value in (None, "") for value in required.values()):
        return False
    return (
        bundle.tenant_id == str(required["tenant_id"])
        and bundle.user_id == str(required["user_id"])
        and bundle.thread_id == str(required["thread_id"])
        and bundle.run_id == str(required["run_id"])
    )


def project_session_memory_bundle_for_prompt(bundle: SessionMemoryBundle) -> dict[str, Any]:
    return {
        "thread_rolling_summary": bundle.rolling_summary.summary_text if bundle.rolling_summary else "",
        "recent_messages": [
            {"role": message.role, "content": message.content}
            for message in bundle.recent_messages
            if message.content
        ],
        "tool_result_summaries": [
            summary for summary in (_tool_prompt_summary_from_bundle(view) for view in bundle.tool_summaries) if summary
        ],
    }


def _tool_prompt_summary_from_bundle(view: SessionToolSummaryView) -> ToolResultPromptSummary | None:
    prompt_summary = view.prompt_summary or ""
    payload = {
        "tool_call_id": view.tool_call_id or view.tool_result_record_id,
        "tool_result_id": view.tool_result_id or view.tool_result_record_id,
        "tool_name": view.tool_name or _infer_tool_name(prompt_summary),
        "status": view.status,
        "summary": prompt_summary,
        "prompt_summary": prompt_summary,
        "business_fact_refs": list(view.business_fact_refs),
        "policy_evidence_refs": list(view.policy_evidence_refs),
        "raw_result_ref": None,
        "audit_ref": view.audit_ref,
    }
    try:
        return ToolResultPromptSummary.model_validate(payload)
    except ValidationError:
        return None


def _infer_tool_name(prompt_summary: str) -> str:
    first_token = prompt_summary.split(" ", 1)[0].strip()
    if _TOOL_NAME_RE.fullmatch(first_token):
        return first_token
    return "tool"


class _StateSlotContinuityMemoryService:
    def __init__(self, state: Mapping[str, Any]) -> None:
        self.state = state

    async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent) -> SessionMemoryView:
        raw = self.state.get("session_memory")
        if isinstance(raw, SessionMemoryView):
            return raw
        if isinstance(raw, dict):
            try:
                return SessionMemoryView.model_validate(raw)
            except ValidationError:
                pass
        return SessionMemoryView(
            source="empty_adapter",
            continuity_claimed=False,
            active_slots={},
            slot_metadata={},
            fallback_reason="missing_memory_service",
        )
