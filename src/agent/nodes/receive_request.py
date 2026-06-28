from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.agent.intent_policy import REQUIRED_SLOT_POLICY
from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _project_active_flow_state(state: AgentState) -> dict[str, Any] | None:
    clarification = state.get("clarification_request")
    if not isinstance(clarification, dict) or clarification.get("reason") != "missing_required_slots":
        return None

    intent = state.get("primary_intent") or state.get("current_intent") or state.get("last_intent")
    if not isinstance(intent, str) or intent not in REQUIRED_SLOT_POLICY:
        return None

    required_slots = state.get("required_slots")
    if not isinstance(required_slots, dict) or required_slots == {"all_of": [], "any_of": [], "optional": []}:
        required_slots = REQUIRED_SLOT_POLICY[intent].model_dump()
    if required_slots == {"all_of": [], "any_of": [], "optional": []}:
        return None

    operation = state.get("requested_operation")
    candidate_slots = state.get("candidate_slots") if isinstance(state.get("candidate_slots"), dict) else {}
    blocked_nodes = clarification.get("blocked_nodes") if isinstance(clarification.get("blocked_nodes"), list) else []
    return {
        "kind": "pending_required_slot",
        "reason": "missing_required_slots",
        "last_effective_intent": intent,
        "last_requested_operation": operation if isinstance(operation, str) else "advise",
        "required_slots": required_slots,
        "candidate_slots": candidate_slots,
        "clarification_request_id": clarification.get("clarification_request_id"),
        "blocked_nodes": blocked_nodes,
    }


async def receive_request(state: AgentState) -> dict:
    """Reset per-turn state so checkpointed graph context cannot leak stale context."""
    started_at = _now_iso()
    active_flow_state = _project_active_flow_state(state)
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
        "risk_tier": None,
        "classification_trace": None,
        "target_merchant_context": None,
        "active_flow_state": active_flow_state,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [], "optional": []},
        "candidate_slots": {},
        "routing_hints": {},
        "extracted_slots": None,
        "active_slots": {},
        "active_slot_metadata": {},
        "last_business_context_refs": None,
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
        "rag_context_bundle": None,
        "rag_verification": None,
        "verifier_status": None,
        "verification_route": None,
        "verifier_reason_codes": None,
        "verifier_safe_citation_refs": None,
        "verifier_metrics": None,
        "session_context": None,
        "session_context_bundle": None,
        "session_context_load_status": None,
        "session_memory": None,
        "session_memory_bundle": None,
        "memory_context": None,
        "memory_context_bundle": None,
        "reviewed_memory_context_retrieve_status": None,
        "memory_write_candidates": None,
        "memory_write_result": None,
        "memory_write_decision": None,
        "long_term_memory": None,
        "proposed_action": None,
        "approval_result": None,
        # Action-phase bindings use None as the unbound sentinel, including this list-typed field.
        "approval_revision_refs": None,
        "action_payload_hash": None,
        "safety_snapshot_ref": None,
        "safety_snapshot_hash": None,
        "safety_snapshot_verified": None,
        "policy_config_version": None,
        "risk_config_version": None,
        "retrieval_config_version": None,
        "auto_allowed": None,
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
