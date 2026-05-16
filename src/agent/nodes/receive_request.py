from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def receive_request(state: AgentState) -> dict:
    """Reset per-turn state so checkpointer memory cannot leak stale context."""
    started_at = _now_iso()
    trace_steps = [
        {
            "node": "receive_request",
            "status": "completed",
            "started_at": started_at,
            "completed_at": _now_iso(),
            "provider_latency_ms": None,
            "retry_count": 0,
            "metrics_json": None,
        }
    ]

    return {
        "user_query": state.get("user_query"),
        "normalized_query": None,
        "current_intent": None,
        "extracted_slots": None,
        "business_context": None,
        "retrieved_evidence": None,
        "recommendation_draft": None,
        "risk_assessment": None,
        "final_response": None,
        "tool_results": [],
        "llm_outputs": {},
        "node_errors": [],
        "retry_count": 0,
        "current_run_id": str(uuid4()),
        "trace_steps": trace_steps,
    }
