from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def clarification_gate(state: AgentState, config: RunnableConfig) -> dict:
    """Minimal safe clarification fallback. Phase 11 owns full logic."""
    del config
    started_at = _now_iso()
    business_context = state.get("business_context") if isinstance(state.get("business_context"), dict) else {}
    missing = _string_list(
        state.get("missing_info")
        or state.get("required_slots")
        or business_context.get("missing_required_facts")
        or []
    )
    step = {
        "node": "clarification_gate",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }
    return {
        "clarification_request": {"reason": "missing_required_information", "missing": missing},
        "final_response": "Could you provide a bit more information so I can help?",
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
