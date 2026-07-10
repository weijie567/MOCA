from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from src.agent.intent_policy import INTENT_POLICY_REGISTRY, SLOT_POLICY_REGISTRY
from src.agent.state import (
    AgentState,
    business_query_context_binding_from_trusted_context,
    trusted_business_query_context_binding,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _project_active_flow_state(state: AgentState) -> dict[str, Any] | None:
    clarification = state.get("clarification_request")
    if not isinstance(clarification, dict) or clarification.get("reason") != "missing_required_slots":
        return None

    intent = state.get("primary_intent") or state.get("current_intent") or state.get("last_intent")
    if not isinstance(intent, str) or not INTENT_POLICY_REGISTRY.is_known_intent(intent):
        return None

    required_slots = state.get("required_slots")
    if not isinstance(required_slots, dict) or required_slots == {"all_of": [], "any_of": [], "optional": []}:
        required_slots = SLOT_POLICY_REGISTRY.required_slots_for(intent).model_dump()
    if required_slots == {"all_of": [], "any_of": [], "optional": []}:
        return None

    operation = state.get("requested_operation")
    candidate_slots = state.get("candidate_slots") if isinstance(state.get("candidate_slots"), dict) else {}
    resolved_slots = _resolved_slots_from_state(state)
    blocked_nodes = clarification.get("blocked_nodes") if isinstance(clarification.get("blocked_nodes"), list) else []
    flow_state = {
        "kind": "pending_required_slot",
        "reason": "missing_required_slots",
        "last_effective_intent": intent,
        "last_requested_operation": operation if isinstance(operation, str) else "advise",
        "required_slots": required_slots,
        "candidate_slots": candidate_slots,
        "clarification_request_id": clarification.get("clarification_request_id"),
        "blocked_nodes": blocked_nodes,
    }
    if resolved_slots:
        flow_state["resolved_slots"] = resolved_slots
    return flow_state


def _resolved_slots_from_state(state: AgentState) -> dict[str, Any]:
    active_slots = state.get("active_slots") if isinstance(state.get("active_slots"), dict) else {}
    if active_slots:
        return {key: value for key, value in active_slots.items() if value not in (None, "", [])}
    trace = state.get("slot_resolution_trace") if isinstance(state.get("slot_resolution_trace"), dict) else {}
    trace_slots = trace.get("resolved_slots") if isinstance(trace.get("resolved_slots"), dict) else {}
    return {key: value for key, value in trace_slots.items() if value not in (None, "", [])}


def _project_business_query_drilldown_context(state: AgentState, current_binding: str | None) -> dict[str, Any]:
    """Preserve only same-context safe answer metadata for possible drilldown.

    Invalidation table:
    - Same thread/session/user/tenant/role/scope fingerprint: preserve as drilldown context only.
    - User, tenant, role, authorized scope, session, or thread fingerprint mismatch: clear.
    - Permission-denied business_query results: investigate clears before this node sees the next turn.
    - Unsupported, unrelated, small-talk, approval/action, or ordinary clarification turns: keep as
      non-current drilldown context here; contextual intent resolution decides whether to use it.
    """
    if not isinstance(state.get("last_query_spec"), dict) or not isinstance(state.get("last_answer_context"), dict):
        return _clear_business_query_drilldown_context()
    expected_context = state.get("expected_slot_context")
    if not isinstance(expected_context, dict):
        return _clear_business_query_drilldown_context()
    if expected_context.get("purpose") != "business_query_drilldown":
        return _clear_business_query_drilldown_context()
    if current_binding is None or expected_context.get("context_binding") != current_binding:
        return _clear_business_query_drilldown_context()
    return {
        "last_query_spec": state.get("last_query_spec"),
        "last_answer_context": state.get("last_answer_context"),
        "result_cursor": state.get("result_cursor") if isinstance(state.get("result_cursor"), dict) else None,
        "expected_slot_type": state.get("expected_slot_type") if isinstance(state.get("expected_slot_type"), str) else None,
        "expected_slot_context": expected_context,
    }


def _business_query_context_binding_from_config(config: RunnableConfig | None) -> str | None:
    configurable = (config or {}).get("configurable") or {}
    trusted_context = configurable.get("trusted_context")
    if trusted_context is None:
        return None
    return business_query_context_binding_from_trusted_context(trusted_context)


def _clear_business_query_drilldown_context() -> dict[str, Any]:
    return {
        "last_query_spec": None,
        "last_answer_context": None,
        "result_cursor": None,
        "expected_slot_type": None,
        "expected_slot_context": None,
    }


async def receive_request(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Reset per-turn state so checkpointed graph context cannot leak stale context."""
    started_at = _now_iso()
    active_flow_state = _project_active_flow_state(state)
    current_binding = _business_query_context_binding_from_config(config) or trusted_business_query_context_binding(state)
    drilldown_context = _project_business_query_drilldown_context(state, current_binding)
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
        "business_query_context_binding": current_binding,
        "normalized_query": None,
        "current_intent": None,
        "intent_confidence": None,
        "risk_tier": None,
        "classification_trace": None,
        "slot_resolution_trace": None,
        "missing_required_slots": [],
        "task_plan": None,
        "deferred_steps": [],
        "target_merchant_context": None,
        "pre_route_decision": None,
        "safety_flags": {},
        "active_flow_state": active_flow_state,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [], "optional": []},
        "candidate_slots": {},
        "routing_hints": {},
        "extracted_slots": None,
        "active_slots": {},
        "active_slot_metadata": {},
        "last_business_context_refs": None,
        **drilldown_context,
        "business_context": None,
        "retrieved_evidence": None,
        "recommendation_draft": None,
        "canonical_action": None,
        "clarification_request": None,
        "risk_assessment": None,
        "risk_signals": [],
        "primary_intent": None,
        "requested_operation": None,
        "retrieval_status": None,
        "best_score": None,
        "termination_reason": None,
        "policy_evidence": None,
        "case_memory": None,
        "claim_dependency_map": None,
        "rag_context_status": None,
        "verified_evidence_package": None,
        "citation_map": {},
        "evidence_map": {},
        "material_claims": [],
        "claim_verification_bundle": None,
        "blocked_claims": [],
        "safe_support_refs": [],
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
        "case_working_context": None,
        "case_working_context_lifecycle_status": None,
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
        "approval_plan": None,
        "risk_decision": None,
        "risk_decision_ref": None,
        "target_merchant_id": None,
        "target_merchant_ref": None,
        "scope_classification": None,
        "scope_source": None,
        "scope_reason_codes": None,
        "business_fact_refs": [],
        "verified_evidence_refs": [],
        "claim_verification_ref": None,
        "claim_verification_summary": None,
        "approval_idempotency_key": None,
        "auto_action_capability": None,
        "auto_allowed_binding": None,
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
