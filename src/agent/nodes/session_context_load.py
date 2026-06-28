from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.config import settings
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.memory.context_service import MemoryContextService
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionContextBundle, SessionContextMemory, SessionMemoryView
from src.memory.session_bundle import SessionMemoryBundleService
from src.memory.service import MemoryService

_TARGET_CONTEXT_SCHEMA = "session_context_memory.v1"
_TARGET_CONTEXT_AUTHORITY = "contextual_only"
_CROSS_MERCHANT_FILTER_REASON = "cross_merchant_session_context_filtered"
_MERCHANT_SCOPE_DENIED_REASON = "merchant_scope_denied"
_EXPLICIT_MERCHANT_REASON = "explicit_current_turn_merchant_context_applied"
_EXPLICIT_SLOTS_REASON = "explicit_current_turn_slots_applied"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def session_context_load(
    state: AgentState,
    config: RunnableConfig,
    *,
    node_name: str = "session_context_load",
    settings_obj: Any | None = None,
    memory_service_cls: Any | None = None,
    session_memory_repository_cls: Any | None = None,
    session_memory_bundle_service_cls: Any | None = None,
    conversation_repository_cls: Any | None = None,
    conversation_service_cls: Any | None = None,
    memory_context_service_cls: Any | None = None,
) -> dict:
    """Load same-thread session context through the MemoryContextService facade."""
    started_at = _now_iso()
    configurable = (config.get("configurable") or {}) if config else {}
    settings_ref = settings_obj or settings
    session = configurable.get("session")
    if settings_ref.session_memory_enabled is False:
        return _fallback(
            state,
            started_at,
            node_name=node_name,
            source="disabled",
            fallback_reason="disabled",
        )
    if session is None:
        return _fallback(
            state,
            started_at,
            node_name=node_name,
            source="unavailable",
            fallback_reason="missing_async_session",
        )

    run_id = state.get("current_run_id") or state.get("run_id")
    if not run_id or not hasattr(session, "execute"):
        return _fallback(
            state,
            started_at,
            node_name=node_name,
            source="unavailable",
            fallback_reason="missing_session_memory_bundle",
        )

    try:
        context_service = _context_service(
            configurable,
            session,
            settings_ref=settings_ref,
            memory_service_cls=memory_service_cls or MemoryService,
            session_memory_repository_cls=session_memory_repository_cls or SessionMemoryRepository,
            session_memory_bundle_service_cls=session_memory_bundle_service_cls or SessionMemoryBundleService,
            conversation_repository_cls=conversation_repository_cls or ConversationRepository,
            conversation_service_cls=conversation_service_cls or ConversationService,
            memory_context_service_cls=memory_context_service_cls or MemoryContextService,
        )
        context, status_ref = await context_service.load_session_context_for_intent(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            thread_id=str(state["thread_id"]),
            run_id=run_id,
            current_intent=state.get("primary_intent") or state.get("current_intent"),
        )
        if status_ref.fallback_reason == "session_bundle_unavailable":
            result = _fallback(
                state,
                started_at,
                node_name=node_name,
                source="unavailable",
                fallback_reason="unavailable",
            )
            result["node_errors"] = (state.get("node_errors") or []) + [
                {"node": node_name, "error_code": "SESSION_CONTEXT_UNAVAILABLE"}
            ]
            return result

        filtered_context, filter_reasons = _apply_current_turn_and_merchant_scope(
            context,
            state=state,
            trusted_context=configurable.get("trusted_context"),
        )
        return _context_result(
            state,
            started_at,
            node_name=node_name,
            context=filtered_context,
            status_ref=status_ref.model_dump(mode="json"),
            filter_reasons=filter_reasons,
            include_legacy_bundle=True,
        )
    except Exception:
        result = _fallback(
            state,
            started_at,
            node_name=node_name,
            source="unavailable",
            fallback_reason="unavailable",
        )
        result["node_errors"] = (state.get("node_errors") or []) + [
            {"node": node_name, "error_code": "SESSION_CONTEXT_UNAVAILABLE"}
        ]
        return result


def _context_service(
    configurable: dict[str, Any],
    session: Any,
    *,
    settings_ref: Any,
    memory_service_cls: Any,
    session_memory_repository_cls: Any,
    session_memory_bundle_service_cls: Any,
    conversation_repository_cls: Any,
    conversation_service_cls: Any,
    memory_context_service_cls: Any,
) -> MemoryContextService:
    existing = configurable.get("memory_context_service")
    if existing is not None:
        return existing

    memory_service = memory_service_cls(
        session_memory_repository_cls(session),
        enabled=settings_ref.session_memory_enabled,
    )
    conversation_service = configurable.get("conversation_service")
    if conversation_service is None:
        conversation_service = conversation_service_cls(conversation_repository_cls(session))
    bundle_service = session_memory_bundle_service_cls(
        conversation_service=conversation_service,
        memory_service=memory_service,
    )
    return memory_context_service_cls(session_bundle_service=bundle_service)


def _apply_current_turn_and_merchant_scope(
    context: SessionContextMemory,
    *,
    state: AgentState,
    trusted_context: Any | None,
) -> tuple[SessionContextMemory, list[str]]:
    explicit_slots = _current_turn_slots(state)
    explicit_merchant_id = explicit_slots.get("merchant_id")
    trusted_merchant_ids = _trusted_merchant_ids(trusted_context)
    effective_merchant_id = explicit_merchant_id or (trusted_merchant_ids[0] if len(trusted_merchant_ids) == 1 else None)
    inherited_slots = dict(context.slot_continuity.active_slots)
    inherited_merchant_id = inherited_slots.get("merchant_id")
    filter_reasons: list[str] = []

    cross_merchant = bool(
        effective_merchant_id
        and inherited_merchant_id
        and str(inherited_merchant_id) != str(effective_merchant_id)
    )
    denied_by_trusted_scope = bool(
        inherited_merchant_id
        and trusted_merchant_ids
        and str(inherited_merchant_id) not in {str(merchant_id) for merchant_id in trusted_merchant_ids}
    )

    if cross_merchant or denied_by_trusted_scope:
        replacement_slots = explicit_slots or (
            {"merchant_id": str(effective_merchant_id)} if effective_merchant_id else {}
        )
        filter_reasons.append(_CROSS_MERCHANT_FILTER_REASON)
        if denied_by_trusted_scope:
            filter_reasons.append(_MERCHANT_SCOPE_DENIED_REASON)
        if explicit_merchant_id:
            filter_reasons.append(_EXPLICIT_MERCHANT_REASON)
        return _filtered_context(context, replacement_slots=replacement_slots, filter_reasons=filter_reasons), filter_reasons

    if explicit_slots:
        merged_slots = {**inherited_slots, **explicit_slots}
        filter_reasons.append(_EXPLICIT_SLOTS_REASON)
        if explicit_merchant_id:
            filter_reasons.append(_EXPLICIT_MERCHANT_REASON)
        return _context_with_slots(context, active_slots=merged_slots, explicit_slots=explicit_slots), filter_reasons

    return context, filter_reasons


def _filtered_context(
    context: SessionContextMemory,
    *,
    replacement_slots: dict[str, str],
    filter_reasons: list[str],
) -> SessionContextMemory:
    return _context_with_slots(
        context.model_copy(
            update={
                "rolling_summary": None,
                "recent_messages": [],
                "tool_summaries": [],
                "fallback_reasons": {
                    **context.fallback_reasons,
                    "merchant_scope": ",".join(filter_reasons),
                },
            }
        ),
        active_slots=replacement_slots,
        explicit_slots=replacement_slots,
        clear_loaded_details=True,
    )


def _context_with_slots(
    context: SessionContextMemory,
    *,
    active_slots: dict[str, str],
    explicit_slots: dict[str, str],
    clear_loaded_details: bool = False,
) -> SessionContextMemory:
    inherited_metadata = {} if clear_loaded_details else dict(context.slot_continuity.slot_metadata)
    slot_metadata = {
        **inherited_metadata,
        **{
            slot_name: {
                "source": "explicit_current_turn",
                "authority_class": _TARGET_CONTEXT_AUTHORITY,
                "merge_rule": "explicit_current_turn_overrides_session_context",
            }
            for slot_name in explicit_slots
        },
    }
    slot_continuity = context.slot_continuity.model_copy(
        update={
            "continuity_claimed": bool(active_slots),
            "active_slots": active_slots,
            "slot_metadata": slot_metadata,
            "session_summary": None if clear_loaded_details else context.slot_continuity.session_summary,
            "unresolved_questions": [] if clear_loaded_details else context.slot_continuity.unresolved_questions,
            "last_business_context_refs": {}
            if clear_loaded_details
            else context.slot_continuity.last_business_context_refs,
            "fallback_reason": None if clear_loaded_details else context.slot_continuity.fallback_reason,
        }
    )
    return context.model_copy(update={"slot_continuity": slot_continuity})


def _current_turn_slots(state: AgentState) -> dict[str, str]:
    slots: dict[str, str] = {}
    for field in ("candidate_slots", "extracted_slots"):
        mapping = state.get(field)
        if not isinstance(mapping, dict):
            continue
        for slot_name, value in mapping.items():
            if value is None or isinstance(value, (dict, list, tuple, set)):
                continue
            value_str = str(value).strip()
            if value_str:
                slots[slot_name] = value_str
    return slots


def _trusted_merchant_ids(trusted_context: Any | None) -> list[str]:
    if isinstance(trusted_context, Mapping):
        merchant_scope = trusted_context.get("merchant_scope")
    else:
        merchant_scope = getattr(trusted_context, "merchant_scope", None)

    if isinstance(merchant_scope, Mapping):
        merchant_ids = merchant_scope.get("merchant_ids")
    else:
        merchant_ids = getattr(merchant_scope, "merchant_ids", None)

    if not merchant_ids:
        return []
    return [str(merchant_id) for merchant_id in merchant_ids if str(merchant_id) != "*"]


def _context_result(
    state: AgentState,
    started_at: str,
    *,
    node_name: str,
    context: SessionContextMemory,
    status_ref: dict[str, Any],
    filter_reasons: list[str],
    include_legacy_bundle: bool,
) -> dict[str, Any]:
    session_memory = context.slot_continuity.model_dump(mode="json")
    session_context = {
        "schema_version": _TARGET_CONTEXT_SCHEMA,
        "authority_class": _TARGET_CONTEXT_AUTHORITY,
        **session_memory,
    }
    status = _status_dump(context, status_ref=status_ref, filter_reasons=filter_reasons)
    result = {
        "session_context": session_context,
        "session_context_bundle": SessionContextBundle(session_context=context).model_dump(mode="json"),
        "session_context_load_status": status,
        "session_memory": session_memory,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, node_name, session_memory, status)],
    }
    if include_legacy_bundle:
        result["session_memory_bundle"] = _legacy_session_memory_bundle_dump(context)
    return result


def _status_dump(
    context: SessionContextMemory,
    *,
    status_ref: dict[str, Any],
    filter_reasons: list[str],
) -> dict[str, Any]:
    status = dict(status_ref)
    status["slot_count"] = len(context.slot_continuity.active_slots)
    status["recent_message_count"] = len(context.recent_messages)
    status["tool_summary_count"] = len(context.tool_summaries)
    if filter_reasons:
        status["filter_reasons"] = list(dict.fromkeys(filter_reasons))
    else:
        status.setdefault("filter_reasons", [])
    return status


def _legacy_session_memory_bundle_dump(context: SessionContextMemory) -> dict[str, Any]:
    return {
        "schema_version": "session_memory_bundle.v1",
        "source": "session_memory_bundle",
        "tenant_id": context.tenant_id,
        "user_id": context.user_id,
        "thread_id": context.thread_id,
        "run_id": context.run_id,
        "rolling_summary": context.rolling_summary.model_dump(mode="json") if context.rolling_summary else None,
        "recent_messages": [message.model_dump(mode="json") for message in context.recent_messages],
        "tool_summaries": [summary.model_dump(mode="json") for summary in context.tool_summaries],
        "slot_continuity": context.slot_continuity.model_dump(mode="json"),
        "fallback_reasons": dict(context.fallback_reasons),
    }


def _fallback(
    state: AgentState,
    started_at: str,
    *,
    node_name: str,
    source: str,
    fallback_reason: str,
) -> dict[str, Any]:
    memory = {
        "active_slots": {},
        "slot_metadata": {},
        "source": source,
        "continuity_claimed": False,
        "fallback_reason": fallback_reason,
    }
    tenant_id = str(state.get("tenant_id") or "unknown_tenant")
    user_id = str(state.get("user_id") or "unknown_user")
    thread_id = str(state.get("thread_id") or "unknown_thread")
    run_id = str(state.get("current_run_id") or state.get("run_id") or "unknown_run")
    context = SessionContextMemory(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        slot_continuity=SessionMemoryView(**memory),
        fallback_reasons={"session_context": fallback_reason},
    )
    status = {
        "schema_version": "session_context_load_status.v1",
        "status": "skipped" if fallback_reason in {"disabled", "missing_async_session"} else "unavailable",
        "source": source,
        "authority_class": _TARGET_CONTEXT_AUTHORITY,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "run_id": run_id,
        "loaded_refs": [],
        "fallback_reason": fallback_reason,
        "slot_count": 0,
        "recent_message_count": 0,
        "tool_summary_count": 0,
        "filter_reasons": [],
    }
    return {
        "session_context": {
            "schema_version": _TARGET_CONTEXT_SCHEMA,
            "authority_class": _TARGET_CONTEXT_AUTHORITY,
            **memory,
        },
        "session_context_bundle": SessionContextBundle(session_context=context).model_dump(mode="json"),
        "session_context_load_status": status,
        "session_memory": memory,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, node_name, memory, status)],
    }


def _trace_step(started_at: str, node_name: str, memory: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    active_slots = memory.get("active_slots") if isinstance(memory.get("active_slots"), dict) else {}
    return {
        "node": node_name,
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "source": memory.get("source"),
            "continuity_claimed": memory.get("continuity_claimed") is True,
            "fallback_reason": memory.get("fallback_reason") or status.get("fallback_reason"),
            "filter_reasons": list(status.get("filter_reasons") or []),
            "slot_count": len(active_slots),
            "version": memory.get("version"),
        },
    }
