from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Empty long-term/case memory adapter. Phase 16 owns real retrieval."""
    del config
    started_at = _now_iso()
    step = {
        "node": "long_term_memory_retrieve",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {"source": "empty_adapter", "continuity_claimed": False},
    }
    return {
        "long_term_memory": [],
        "case_memory": [],
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "long_term_memory_retrieve": {
                "source": "empty_adapter",
                "continuity_claimed": False,
                "retrieved": 0,
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }
