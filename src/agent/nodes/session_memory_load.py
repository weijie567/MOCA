from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.config import settings
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.memory.repository import SessionMemoryRepository
from src.memory.session_bundle import SessionMemoryBundleService
from src.memory.service import MemoryService


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Load same-thread session memory through the PostgreSQL-authoritative service."""
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    if settings.session_memory_enabled is False:
        return _fallback(state, started_at, source="disabled", fallback_reason="disabled")
    if session is None:
        return _fallback(state, started_at, source="unavailable", fallback_reason="missing_async_session")

    try:
        service = MemoryService(SessionMemoryRepository(session), enabled=settings.session_memory_enabled)
        bundle = await _load_bundle(state, configurable, session, service)
        if bundle is None:
            return _fallback(state, started_at, source="unavailable", fallback_reason="missing_session_memory_bundle")
        memory = bundle.slot_continuity.model_dump(mode="json")
        bundle_dump = bundle.model_dump(mode="json")
        step = _trace_step(started_at, memory)
        result = {
            "session_memory": memory,
            "trace_steps": (state.get("trace_steps") or []) + [step],
        }
        if bundle_dump is not None:
            result["session_memory_bundle"] = bundle_dump
        return result
    except Exception:
        result = _fallback(state, started_at, source="unavailable", fallback_reason="unavailable")
        result["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "session_memory_load", "error_code": "SESSION_MEMORY_UNAVAILABLE"}
        ]
        return result


async def _load_bundle(state: AgentState, configurable: dict[str, Any], session: Any, service: MemoryService):
    run_id = state.get("current_run_id") or state.get("run_id")
    if not run_id or not hasattr(session, "execute"):
        return None
    conversation_service = configurable.get("conversation_service")
    if conversation_service is None:
        conversation_service = ConversationService(ConversationRepository(session))
    return await SessionMemoryBundleService(
        conversation_service=conversation_service,
        memory_service=service,
    ).load_session_memory_bundle(
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        thread_id=str(state["thread_id"]),
        run_id=run_id,
        current_intent=state.get("primary_intent") or state.get("current_intent"),
    )


def _fallback(state: AgentState, started_at: str, *, source: str, fallback_reason: str) -> dict[str, Any]:
    memory = {
        "active_slots": {},
        "slot_metadata": {},
        "source": source,
        "continuity_claimed": False,
        "fallback_reason": fallback_reason,
    }
    return {
        "session_memory": memory,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, memory)],
    }


def _trace_step(started_at: str, memory: dict[str, Any]) -> dict[str, Any]:
    active_slots = memory.get("active_slots") if isinstance(memory.get("active_slots"), dict) else {}
    step = {
        "node": "session_memory_load",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "source": memory.get("source"),
            "continuity_claimed": memory.get("continuity_claimed") is True,
            "fallback_reason": memory.get("fallback_reason"),
            "slot_count": len(active_slots),
            "version": memory.get("version"),
        },
    }
    return step
