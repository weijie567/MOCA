from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def receive_request(state: AgentState) -> dict:
    """Reset per-turn state so checkpointed graph context cannot leak stale context."""
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
        "intent_confidence": None,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [], "optional": []},
        "candidate_slots": {},
        "routing_hints": {},
        "extracted_slots": None,
        "active_slots": {},
        "active_slot_metadata": {},
        "business_context": None,
        "retrieved_evidence": None,
        "recommendation_draft": None,
        "clarification_request": None,
        "risk_assessment": None,
        "primary_intent": None,
        "requested_operation": None,
        "retrieval_status": None,
        "best_score": None,
        "termination_reason": None,
        "policy_evidence": None,
        "case_memory": None,
        "claim_dependency_map": None,
        "session_memory": None,
        "memory_write_candidates": None,
        "memory_write_result": None,
        "long_term_memory": None,
        "proposed_action": None,
        "approval_result": None,
        "action_draft": None,
        "draft_outcome": None,
        "execution_mode": None,
        "action_result": None,
        "investigation_result": None,
        "investigation_steps": None,
        "investigation_trigger_reason": None,
        "investigation_path": None,
        "final_response": None,
        "tool_results": [],
        "llm_outputs": {},
        "node_errors": [],
        "retry_count": 0,
        "current_run_id": state.get("current_run_id") or str(uuid4()),
        "run_started_at": started_at,
        "trace_steps": trace_steps,
    }
