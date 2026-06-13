from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Empty session-memory adapter. Phase 12 owns persisted memory with CAS."""
    del config
    started_at = _now_iso()
    step = {
        "node": "session_memory_load",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }
    return {
        "session_memory": {"active_slots": {}, "source": "empty_adapter", "continuity_claimed": False},
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }
