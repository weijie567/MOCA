from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from src.agent.intent_policy import (
    INTENT_POLICY_REGISTRY,
    SLOT_POLICY_REGISTRY,
    PreRouteDecision,
    SlotInheritanceContext,
    confidence_requires_clarification,
)
from src.agent.schemas import RequiredSlotExpression
from src.agent.state import AgentState
from src.knowledge.schemas import RAG_CONTEXT_STATUSES as SCHEMA_RAG_CONTEXT_STATUSES


MIN_EVIDENCE_SCORE = 0.55
_FACT_ONLY_INTENTS = {"order_status_inquiry"}
_ACTION_BOUND_INTENTS = {"action_request", "compensation_suggestion", "complaint_escalation"}
_PERMISSION_CODES = {"FORBIDDEN", "permission_denied"}
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "rag_context_build", "recommendation_generation"}
_RECOMMENDATION_ROUTES = {"claim_verify", "final_response"}
RAG_CONTEXT_STATUSES = set(SCHEMA_RAG_CONTEXT_STATUSES)
_RAG_CONTEXT_UNSAFE_REASON_CODES = {"unauthorized", "stale", "conflict", "invalid_hash", "invalid_scope", "build_error"}
_RAG_CONTEXT_ROUTES = {"recommendation_generation", "clarification_gate", "final_response"}
_CLAIM_VERIFY_ROUTES = {"risk_gate", "final_response"}
SAFETY_ROUTES = {"session_context_load", "clarification_gate", "final_response"}
CONTEXTUAL_INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "slot_resolution_gate"}
INTENT_ROUTES = CONTEXTUAL_INTENT_ROUTES
SLOT_RESOLUTION_ROUTES = {"clarification_gate", "investigate", "memory_context_load"}
SLOT_ROUTES = SLOT_RESOLUTION_ROUTES
BUSINESS_ID_SLOTS = ("order_id", "refund_case_id", "ticket_id")
SLOT_RESOLUTION_TRACE_SCHEMA = "slot_resolution_trace.phase54"
_SLOT_INVALIDATION_TERMS = {
    "order_id": ("订单", "order"),
    "refund_case_id": ("退款单", "退款", "refund"),
    "ticket_id": ("工单", "ticket"),
}
_INVALIDATION_MARKERS = (
    "不是",
    "另一个",
    "另外一个",
    "别的",
    "换成",
    "换为",
    "换个",
    "换一下",
    "different",
    "another",
    "not this",
    "not that",
)
_BROAD_INVALIDATION_MARKERS = (
    "不是这个",
    "不是这一个",
    "另一个",
    "另外一个",
    "换成",
    "换一个",
    "different one",
    "another one",
)


def route_after_contextual_intent(state: AgentState) -> str:
    try:
        route = _route_after_contextual_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in CONTEXTUAL_INTENT_ROUTES else "clarification_gate"


def route_after_safety(state: AgentState) -> str:
    try:
        route = _route_after_safety(state)
    except Exception:
        return "clarification_gate"
    return route if route in SAFETY_ROUTES else "clarification_gate"


def route_after_slot_resolution(state: AgentState) -> str:
    try:
        route = _route_after_slot_resolution(state)
    except Exception:
        return "clarification_gate"
    return route if route in SLOT_RESOLUTION_ROUTES else "clarification_gate"


def missing_required_slots(
    required_slots: dict[str, Any] | RequiredSlotExpression | None,
    resolved_slots: dict[str, Any] | None,
) -> list[dict[str, list[str]]]:
    return SLOT_POLICY_REGISTRY.missing_required_slots(required_slots, resolved_slots)


def resolve_slots_for_completeness(state: AgentState) -> dict[str, Any]:
    resolved, _metadata = resolve_slots_with_metadata(state)
    return resolved


def resolve_slots_with_metadata(state: AgentState) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    result = resolve_slots_with_provenance(state)
    return result["resolved_slots"], result["slot_metadata"]


def resolve_slots_with_provenance(state: AgentState) -> dict[str, Any]:
    extracted = state.get("extracted_slots")
    current_slots = _collect_current_turn_slots(extracted)
    invalidations = detect_slot_invalidations(str(state.get("user_query") or ""))
    session_memory = _session_slot_continuity(state)
    active_slots: dict[str, Any] = {}
    slot_metadata: dict[str, Any] = {}
    if isinstance(session_memory, dict) and session_memory.get("continuity_claimed") is True:
        raw_active_slots = session_memory.get("active_slots")
        raw_slot_metadata = session_memory.get("slot_metadata")
        if isinstance(raw_active_slots, dict) and isinstance(raw_slot_metadata, dict):
            active_slots = raw_active_slots
            slot_metadata = raw_slot_metadata

    resolved: dict[str, Any] = {}
    resolved_metadata: dict[str, dict[str, Any]] = {}
    explicit_current_turn_slots: dict[str, dict[str, Any]] = {}
    inherited_session_slots: dict[str, dict[str, Any]] = {}
    invalidated_slots: dict[str, dict[str, Any]] = {}
    stale_slots: dict[str, dict[str, Any]] = {}
    incompatible_slots: dict[str, dict[str, Any]] = {}
    conflicting_slots: dict[str, dict[str, Any]] = {}
    reason_codes: list[str] = []
    for slot, value in current_slots.items():
        metadata = _current_turn_slot_metadata(
            slot,
            value,
            state,
            active_slots,
            slot_metadata,
            invalidations,
        )
        resolved[slot] = value
        resolved_metadata[slot] = metadata
        explicit_current_turn_slots[slot] = _slot_trace_entry(value, metadata, "explicit_current_turn")
        _append_reason(reason_codes, "explicit_current_turn")
        prior_value = active_slots.get(slot)
        prior_metadata = slot_metadata.get(slot)
        if (
            prior_value not in (None, "")
            and str(prior_value) != str(value)
            and _trusted_session_slot(slot, prior_metadata, state)
        ):
            conflicting_slots[slot] = {
                "current_value": value,
                "inherited_value": prior_value,
                "source": "trusted_session_memory",
                "resolution": "current_turn_replacement",
            }
            _append_reason(reason_codes, "conflicting_slot_replaced_by_current_turn")

    if not isinstance(session_memory, dict) or session_memory.get("continuity_claimed") is not True:
        pass
    elif isinstance(active_slots, dict) and isinstance(slot_metadata, dict):
        inheritance_context = _slot_inheritance_context(state)
        for slot, value in active_slots.items():
            if slot in resolved or value in (None, ""):
                continue
            metadata = slot_metadata.get(slot)
            conflict_marker = _trusted_session_conflict_marker(metadata)
            if conflict_marker is not None:
                conflicting_slots[slot] = {
                    **conflict_marker,
                    "value": value,
                    "reason_code": "unresolved_inherited_slot_conflict",
                }
                _append_reason(reason_codes, "unresolved_inherited_slot_conflict")
                continue
            decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(
                slot,
                metadata if isinstance(metadata, dict) else None,
                inheritance_context,
                invalidation=invalidations.get(slot),
            )
            if decision.accepted:
                resolved_metadata[slot] = {
                    **metadata,
                    "source": "trusted_session_memory",
                    "explicit_current_turn": False,
                }
                resolved[slot] = value
                inherited_session_slots[slot] = _slot_trace_entry(
                    value,
                    resolved_metadata[slot],
                    "accepted_inherited_session_slot",
                )
                _append_reason(reason_codes, "accepted_inherited_session_slot")
            elif decision.reason_code == "slot_invalidated":
                rejected_metadata = _invalidated_slot_metadata(metadata, invalidations[slot])
                resolved_metadata[slot] = rejected_metadata
                invalidated_slots[slot] = _slot_trace_entry(value, rejected_metadata, "slot_invalidated")
                _append_reason(reason_codes, "slot_invalidated")
            elif decision.reason_code == "stale_slot":
                stale_slots[slot] = _slot_trace_entry(value, metadata, "stale_slot")
                _append_reason(reason_codes, "stale_slot")
            elif decision.reason_code == "intent_incompatible":
                incompatible_slots[slot] = _slot_trace_entry(value, metadata, "intent_incompatible")
                _append_reason(reason_codes, "intent_incompatible")
            else:
                _append_reason(reason_codes, decision.reason_code)

    missing, route_decision, route_reason_codes = _slot_resolution_route_decision(state, resolved)
    for reason_code in route_reason_codes:
        _append_reason(reason_codes, reason_code)
    trace = _build_slot_resolution_trace(
        state,
        candidate_slots=_safe_mapping(state.get("candidate_slots")),
        extracted_slots=_safe_mapping(extracted),
        explicit_current_turn_slots=explicit_current_turn_slots,
        inherited_session_slots=inherited_session_slots,
        invalidated_slots=invalidated_slots,
        stale_slots=stale_slots,
        incompatible_slots=incompatible_slots,
        conflicting_slots=conflicting_slots,
        resolved_slots=resolved,
        missing=missing,
        route_decision=route_decision,
        reason_codes=reason_codes,
    )
    return {
        "resolved_slots": resolved,
        "slot_metadata": resolved_metadata,
        "missing_required_slots": missing,
        "slot_resolution_trace": trace,
        "route_decision": route_decision,
    }


def _collect_current_turn_slots(extracted: Any) -> dict[str, Any]:
    return {key: value for key, value in (extracted or {}).items() if value not in (None, "")}


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _slot_trace_entry(value: Any, metadata: Any, reason_code: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"value": value, "reason_code": reason_code}
    if isinstance(metadata, Mapping):
        entry["metadata"] = dict(metadata)
    return entry


def _append_reason(reason_codes: list[str], reason_code: str) -> None:
    if reason_code and reason_code not in reason_codes:
        reason_codes.append(reason_code)


def _trusted_session_conflict_marker(metadata: Any) -> dict[str, Any] | None:
    if not isinstance(metadata, Mapping):
        return None
    marker = metadata.get("slot_resolution_conflict")
    if not isinstance(marker, Mapping):
        return None
    values = marker.get("values")
    source = marker.get("source")
    if source != "trusted_session_memory" or not isinstance(values, list) or not values:
        return None
    return {"values": list(values), "source": source}


def _build_slot_resolution_trace(
    state: AgentState,
    *,
    candidate_slots: dict[str, Any],
    extracted_slots: dict[str, Any],
    explicit_current_turn_slots: dict[str, dict[str, Any]],
    inherited_session_slots: dict[str, dict[str, Any]],
    invalidated_slots: dict[str, dict[str, Any]],
    stale_slots: dict[str, dict[str, Any]],
    incompatible_slots: dict[str, dict[str, Any]],
    conflicting_slots: dict[str, dict[str, Any]],
    resolved_slots: dict[str, Any],
    missing: list[dict[str, list[str]]],
    route_decision: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "schema": SLOT_RESOLUTION_TRACE_SCHEMA,
        "policy_owner": "SlotPolicyRegistry",
        "intent": _intent(state),
        "candidate_slots": candidate_slots,
        "extracted_slots": extracted_slots,
        "explicit_current_turn_slots": explicit_current_turn_slots,
        "inherited_session_slots": inherited_session_slots,
        "invalidated_slots": invalidated_slots,
        "stale_slots": stale_slots,
        "incompatible_slots": incompatible_slots,
        "conflicting_slots": conflicting_slots,
        "resolved_slots": dict(resolved_slots),
        "missing_required_slots": missing,
        "route_decision": route_decision,
        "reason_codes": list(reason_codes),
    }


def _session_slot_continuity(state: AgentState) -> dict[str, Any]:
    session_context = state.get("session_context")
    if isinstance(session_context, Mapping):
        slot_continuity = session_context.get("slot_continuity")
        if isinstance(slot_continuity, Mapping):
            return dict(slot_continuity)
        if "continuity_claimed" in session_context:
            return dict(session_context)

    session_memory = state.get("session_memory")
    return dict(session_memory) if isinstance(session_memory, Mapping) else {}


def detect_slot_invalidations(user_query: str) -> dict[str, dict[str, Any]]:
    lowered = user_query.lower()
    if not any(marker in lowered or marker in user_query for marker in _INVALIDATION_MARKERS):
        return {}

    invalidations: dict[str, dict[str, Any]] = {}
    for slot, terms in _SLOT_INVALIDATION_TERMS.items():
        if any(term in lowered or term in user_query for term in terms):
            invalidations[slot] = _slot_invalidation(slot)
    if invalidations:
        return invalidations

    if any(marker in lowered or marker in user_query for marker in _BROAD_INVALIDATION_MARKERS):
        return {slot: _slot_invalidation(slot) for slot in BUSINESS_ID_SLOTS}
    return {}


def _route_after_safety(state: AgentState) -> str:
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    raw_pre_route = state.get("pre_route_decision")
    if hasattr(raw_pre_route, "model_dump"):
        raw_pre_route = raw_pre_route.model_dump(mode="python")
    pre_route = raw_pre_route if isinstance(raw_pre_route, dict) else {}
    disposition = pre_route.get("disposition") or routing_hints.get("pre_route_disposition") or "none"
    requires_clarification = bool(pre_route.get("requires_clarification")) or (
        routing_hints.get("requires_clarification") is True
    )

    if state.get("requested_operation") == "approval_decision":
        return "clarification_gate"
    if disposition in {"approval_chat_not_trusted", "multi_target_request"}:
        return "clarification_gate"
    if routing_hints.get("clarification_reason") == "approval_chat_not_trusted":
        return "clarification_gate"
    if requires_clarification:
        return "clarification_gate"
    if disposition in {"none", "safety_sensitive"}:
        return "session_context_load"
    return "clarification_gate"


def _slot_invalidation(slot: str) -> dict[str, Any]:
    return {
        "slot": slot,
        "source": "current_query",
        "reason": "negated_or_switched_context",
    }


def _current_turn_slot_metadata(
    slot: str,
    value: Any,
    state: AgentState,
    active_slots: dict[str, Any],
    slot_metadata: dict[str, Any],
    invalidations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": "current_turn",
        "provenance_source": "current_query",
        "explicit_current_turn": True,
    }
    observed_at = state.get("run_started_at")
    if isinstance(observed_at, str) and observed_at:
        metadata["observed_at"] = observed_at

    prior_value = active_slots.get(slot)
    prior_metadata = slot_metadata.get(slot)
    if (
        prior_value not in (None, "")
        and str(prior_value) != str(value)
        and _trusted_session_slot(slot, prior_metadata, state)
    ):
        metadata["previous_trusted_session_value"] = prior_value
    if slot in invalidations:
        metadata["slot_invalidation"] = invalidations[slot]
        metadata["invalidates_prior_slot"] = True
    return metadata


def _invalidated_slot_metadata(metadata: Any, invalidation: dict[str, Any]) -> dict[str, Any]:
    base = dict(metadata) if isinstance(metadata, dict) else {}
    return {
        **base,
        "source": "invalidated_trusted_session_memory",
        "explicit_current_turn": False,
        "invalidated_by_current_query": True,
        "slot_invalidation": invalidation,
    }


def _route_after_intent(state: AgentState) -> str:
    return _route_after_contextual_intent(state)


def _route_after_contextual_intent(state: AgentState) -> str:
    intent = _intent(state)
    requested_operation = state.get("requested_operation") or "advise"
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if requested_operation == "approval_decision":
        return "clarification_gate"
    if routing_hints.get("pre_route_disposition") == "approval_chat_not_trusted":
        return "clarification_gate"
    if routing_hints.get("clarification_reason") == "approval_chat_not_trusted":
        return "clarification_gate"
    pre_route = PreRouteDecision(
        disposition=routing_hints.get("pre_route_disposition", "none")
        if routing_hints.get("pre_route_disposition")
        in {"none", "approval_chat_not_trusted", "safety_sensitive", "multi_target_request"}
        else "none",
        requested_operation=requested_operation
        if requested_operation in {"read_status", "advise", "draft_reply", "draft_action", "execute_action", "escalate"}
        else None,
        reason_codes=[],
        requires_clarification=bool(routing_hints.get("requires_clarification")),
    )
    if confidence_requires_clarification(intent, requested_operation, state.get("intent_confidence"), pre_route):
        return "clarification_gate"
    if INTENT_POLICY_REGISTRY.is_direct_response_intent(intent):
        return "final_response"
    route = INTENT_POLICY_REGISTRY.route_for_intent(intent)
    if route is None:
        return "clarification_gate"
    policy = SLOT_POLICY_REGISTRY.required_slots_for(intent)
    if policy.all_of or policy.any_of:
        return "slot_resolution_gate"
    return route


def _route_after_slot_resolution(state: AgentState) -> str:
    trace = state.get("slot_resolution_trace")
    if isinstance(trace, Mapping):
        reason_codes = trace.get("reason_codes")
        if isinstance(reason_codes, list) and "llm_slot_extraction_error" in reason_codes:
            return "clarification_gate"

    result = resolve_slots_with_provenance(state)
    route = result.get("route_decision")
    return route if isinstance(route, str) else "clarification_gate"


def _route_after_slots(state: AgentState) -> str:
    return _route_after_slot_resolution(state)


def _slot_resolution_route_decision(
    state: AgentState,
    resolved_slots: dict[str, Any],
) -> tuple[list[dict[str, list[str]]], str, list[str]]:
    intent = _intent(state)
    if not INTENT_POLICY_REGISTRY.is_known_intent(intent):
        return [], "clarification_gate", ["unknown_intent"]
    policy = SLOT_POLICY_REGISTRY.required_slots_for(intent)
    state_required = state.get("required_slots")
    if state_required not in (None, {}):
        try:
            if _required_expression(state_required).model_dump() != policy.model_dump():
                return [], "clarification_gate", ["required_slot_policy_mismatch"]
        except Exception:
            return [], "clarification_gate", ["malformed_required_slots"]
    missing = missing_required_slots(policy, resolved_slots)
    if missing:
        return missing, "clarification_gate", ["missing_required_slots"]
    if _needs_reviewed_memory_context(state):
        return [], "memory_context_load", []
    return [], "investigate", []


def _needs_reviewed_memory_context(state: AgentState) -> bool:
    routing_hints = state.get("routing_hints")
    return isinstance(routing_hints, dict) and (
        routing_hints.get("needs_reviewed_memory_context") is True
        or routing_hints.get("needs_long_term_memory") is True
    )


def route_after_investigate(state: AgentState) -> str:
    """Route after the merged investigate node using state only."""
    try:
        route = _route_after_investigate(state)
    except Exception:
        return "final_response"
    if route in _INVESTIGATE_ROUTES:
        return route
    return "final_response"


def route_after_recommendation(state: AgentState) -> str:
    """Route after Phase 22 recommendation verification using state only."""
    try:
        route = _route_after_recommendation(state)
    except Exception:
        return "final_response"
    if route in _RECOMMENDATION_ROUTES:
        return route
    return "final_response"


def route_after_rag_context(state: AgentState) -> str:
    """Route after deterministic RAG context package construction."""
    try:
        route = _route_after_rag_context(state)
    except Exception:
        return "final_response"
    if route in _RAG_CONTEXT_ROUTES:
        return route
    return "final_response"


def route_after_claim_verify(state: AgentState) -> str:
    """Route only from claim bundle state to registered graph node keys."""
    try:
        route = _route_after_claim_verify(state)
    except Exception:
        return "final_response"
    if route in _CLAIM_VERIFY_ROUTES:
        return route
    return "final_response"


def _route_after_rag_context(state: AgentState) -> str:
    status = _rag_context_status(state)
    if status not in RAG_CONTEXT_STATUSES:
        return "final_response"
    if status in {
        "no_evidence",
        "unauthorized",
        "stale",
        "conflict",
        "invalid_hash",
        "invalid_scope",
        "build_error",
    }:
        return "final_response"
    if _missing_required_validation_inputs(state):
        return "clarification_gate"
    if status == "verified":
        return "recommendation_generation"
    if status == "not_required":
        return "recommendation_generation" if not _policy_evidence_required(state) else "final_response"
    if status == "partial":
        return "recommendation_generation" if _partial_rag_context_can_generate(state) else "final_response"
    return "final_response"


def _route_after_recommendation(state: AgentState) -> str:
    if _recommendation_missing_info(state):
        return "final_response"
    route = _recommendation_verification_route(state)
    if route is not None and route != "allow":
        return "final_response"
    if _has_material_claims(state) or _has_proposed_action(state) or _has_user_visible_claims(state):
        return "claim_verify"
    return "final_response"


def _route_after_claim_verify(state: AgentState) -> str:
    if _claim_verify_has_blocked_claims(state):
        return "final_response"
    bundle = _claim_verification_bundle(state)
    if not bundle:
        return "final_response"
    route = bundle.get("route")
    overall_status = bundle.get("overall_status")
    if route != "continue" or overall_status not in {"verified", "not_required"}:
        return "final_response"
    if _has_proposed_action(state):
        return "risk_gate" if _has_verified_action_recommendation(state) else "final_response"
    if _has_verified_action_recommendation(state) or _has_risk_signal(state):
        return "risk_gate"
    return "final_response"


def _recommendation_verification_route(state: AgentState) -> str | None:
    route_value = state.get("verification_route")
    if isinstance(route_value, str) and route_value:
        return route_value

    rag_verification = state.get("rag_verification")
    if isinstance(rag_verification, dict):
        route = rag_verification.get("route")
        if isinstance(route, dict):
            route = route.get("route")
        if isinstance(route, str) and route:
            return route

    draft = state.get("recommendation_draft")
    if isinstance(draft, dict):
        draft_route = draft.get("verification_route")
        if isinstance(draft_route, str) and draft_route:
            return draft_route
    return None


def _recommendation_missing_info(state: AgentState) -> bool:
    missing_info = state.get("missing_info")
    if isinstance(missing_info, list) and missing_info:
        return True
    draft = state.get("recommendation_draft")
    if isinstance(draft, dict):
        draft_missing = draft.get("missing_info")
        return isinstance(draft_missing, list) and bool(draft_missing)
    return False


def _has_material_claims(state: AgentState) -> bool:
    if _non_empty_sequence(state.get("material_claims")):
        return True
    draft = state.get("recommendation_draft")
    if isinstance(draft, dict):
        return _non_empty_sequence(draft.get("material_claims"))
    return False


def _has_proposed_action(state: AgentState) -> bool:
    proposed = state.get("proposed_action")
    return isinstance(proposed, dict) and bool(proposed)


def _has_allowed_action_recommendation(bundle: Mapping[str, Any] | dict[str, Any]) -> bool:
    for raw_result in bundle.get("claim_results") or []:
        result = raw_result.model_dump(mode="python") if hasattr(raw_result, "model_dump") else raw_result
        if not isinstance(result, dict):
            continue
        claim_type = result.get("claim_type") or result.get("authority_class")
        if claim_type == "action_recommendation" and result.get("allows_action_recommendation") is True:
            return True
    return False


def _has_verified_action_recommendation(state: AgentState) -> bool:
    return _has_allowed_action_recommendation(_claim_verification_bundle(state))


def _has_user_visible_claims(state: AgentState) -> bool:
    draft = state.get("recommendation_draft")
    if not isinstance(draft, dict):
        return False
    claim_keys = (
        "user_visible_claims",
        "policy_claims",
        "business_claims",
        "business_fact_claims",
        "action_claims",
        "action_recommendation_claims",
    )
    return any(_non_empty_sequence(draft.get(key)) or _non_empty_mapping(draft.get(key)) for key in claim_keys)


def _has_risk_signal(state: AgentState) -> bool:
    if _non_empty_sequence(state.get("risk_signals")):
        return True
    for risk_value in (state.get("risk_tier"), state.get("risk_level")):
        if isinstance(risk_value, str) and risk_value.lower() in {"high", "critical", "approval_required"}:
            return True
    draft = state.get("recommendation_draft")
    if isinstance(draft, dict):
        draft_risk = draft.get("risk_level")
        return isinstance(draft_risk, str) and draft_risk.lower() in {"high", "critical"}
    return False


def _claim_verify_has_blocked_claims(state: AgentState) -> bool:
    blocked_claims = state.get("blocked_claims")
    if isinstance(blocked_claims, list) and blocked_claims:
        return True
    bundle = _claim_verification_bundle(state)
    return bool(bundle and _non_empty_sequence(bundle.get("blocked_claims")))


def _claim_verification_bundle(state: AgentState) -> dict[str, Any]:
    bundle = state.get("claim_verification_bundle")
    if (
        isinstance(bundle, dict)
        and isinstance(bundle.get("route"), str)
        and isinstance(bundle.get("overall_status"), str)
    ):
        return bundle
    return {}


def _non_empty_sequence(value: Any) -> bool:
    return isinstance(value, list | tuple) and bool(value)


def _non_empty_mapping(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _route_after_investigate(state: AgentState) -> str:
    bc_value = state.get("business_context")
    business_context = bc_value if isinstance(bc_value, dict) else {}
    missing = _string_list(business_context.get("missing_required_facts"))
    errors = business_context.get("errors") if isinstance(business_context.get("errors"), list) else []
    facts = _facts_from_business_context(business_context)
    retrieval_status = state.get("retrieval_status")
    best_score = state.get("best_score")
    claim_dependency_map = state.get("claim_dependency_map") or []
    intent = _intent(state)

    denied = [
        error
        for error in errors
        if isinstance(error, dict) and (error.get("error_code") or error.get("code")) in _PERMISSION_CODES
    ]
    if denied:
        denied_resources = {
            token
            for error in denied
            for token in (error.get("resource"), error.get("resource_id"))
            if isinstance(token, str)
        }
        if _denial_blocks_required_claims(
            denied_resources, claim_dependency_map, missing, facts, retrieval_status, intent
        ):
            return "final_response"

    if missing:
        return "clarification_gate"

    if intent in _FACT_ONLY_INTENTS and facts:
        return "final_response"

    if retrieval_status in {"error", "no_evidence", None}:
        return "final_response"
    if isinstance(best_score, (int, float)) and best_score < MIN_EVIDENCE_SCORE:
        return "final_response"

    if _policy_evidence_required(state) or _has_policy_candidate_refs(state):
        return "rag_context_build"

    return "recommendation_generation"


def _intent(state: AgentState) -> str:
    value = state.get("primary_intent") or state.get("current_intent")
    return value if isinstance(value, str) else "unknown"


def _required_expression(value: dict[str, Any] | RequiredSlotExpression | None) -> RequiredSlotExpression:
    if isinstance(value, RequiredSlotExpression):
        return value
    if isinstance(value, dict):
        return RequiredSlotExpression.model_validate(value)
    return RequiredSlotExpression()


def _trusted_session_slot(slot: str, metadata: Any, state: AgentState) -> bool:
    decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(
        slot,
        metadata if isinstance(metadata, dict) else None,
        _slot_inheritance_context(state),
    )
    return decision.accepted


def _slot_inheritance_context(state: AgentState) -> SlotInheritanceContext:
    return SlotInheritanceContext(
        tenant_id=str(state.get("tenant_id")) if state.get("tenant_id") is not None else None,
        user_id=str(state.get("user_id")) if state.get("user_id") is not None else None,
        thread_id=str(state.get("thread_id")) if state.get("thread_id") is not None else None,
        intent=_intent(state),
        max_age_seconds=3600,
        current_time=_state_current_time(state),
    )


def _state_current_time(state: AgentState) -> datetime | None:
    value = state.get("run_started_at")
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _facts_from_business_context(business_context: dict[str, Any]) -> dict[str, Any]:
    facts = business_context.get("facts")
    if isinstance(facts, dict):
        return facts
    ignored = {"missing_required_facts", "errors", "status", "schema_version", "tool_results", "business_fact_refs"}
    return {key: value for key, value in business_context.items() if key not in ignored}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _rag_context_status(state: AgentState) -> str | None:
    status = state.get("rag_context_status")
    if isinstance(status, str) and status:
        return status
    return None


def _missing_required_validation_inputs(state: AgentState) -> bool:
    business_context = state.get("business_context")
    if isinstance(business_context, dict) and _string_list(business_context.get("missing_required_facts")):
        return True
    missing_info = state.get("missing_info")
    if isinstance(missing_info, list) and missing_info:
        return True
    required_slots = state.get("required_slots")
    if required_slots in (None, {}, {"all_of": [], "any_of": [], "optional": []}):
        return False
    try:
        return bool(missing_required_slots(_required_expression(required_slots), resolve_slots_for_completeness(state)))
    except Exception:
        return True


def _policy_evidence_required(state: AgentState) -> bool:
    evidence_policy = state.get("evidence_policy")
    if isinstance(evidence_policy, dict) and isinstance(evidence_policy.get("evidence_required"), bool):
        return bool(evidence_policy["evidence_required"])
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if isinstance(routing_hints.get("policy_evidence_required"), bool):
        return bool(routing_hints["policy_evidence_required"])
    requested_operation = state.get("requested_operation")
    if requested_operation in {"draft_action", "execute_action", "escalate"}:
        return True
    intent = _intent(state)
    return intent in {
        "policy_qa",
        "refund_troubleshooting",
        "compensation_suggestion",
        "ticket_reply_draft",
        "appeal_or_unban",
        "complaint_escalation",
        "action_request",
    }


def _has_policy_candidate_refs(state: AgentState) -> bool:
    return bool(_candidate_ref_items(state.get("policy_evidence"))) or bool(
        _candidate_ref_items(_retrieved_evidence_refs_value(state))
    )


def _retrieved_evidence_refs_value(state: AgentState) -> Any:
    retrieved = state.get("retrieved_evidence")
    if isinstance(retrieved, dict):
        return retrieved.get("evidence_refs") or retrieved.get("policy_refs")
    return retrieved


def _candidate_ref_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict) and item.get("evidence_id")]
    if isinstance(value, dict) and value.get("evidence_id"):
        return [value]
    return []


def _partial_rag_context_can_generate(state: AgentState) -> bool:
    if state.get("proposed_action") is not None:
        return False
    if _action_bound_or_high_risk(state):
        return False
    if _partial_rag_has_unsafe_evidence_indicator(state):
        return False
    requested_operation = state.get("requested_operation")
    intent = _intent(state)
    if intent == "policy_qa":
        return requested_operation in {None, "advise", "draft_reply"}
    if intent in _FACT_ONLY_INTENTS:
        return requested_operation in {None, "advise", "read_status"}
    return False


def _action_bound_or_high_risk(state: AgentState) -> bool:
    requested_operation = state.get("requested_operation")
    if requested_operation in {"approval_decision", "draft_action", "execute_action", "escalate"}:
        return True
    if _intent(state) in _ACTION_BOUND_INTENTS:
        return True
    if _non_empty_sequence(state.get("risk_signals")):
        return True
    for risk_value in (state.get("risk_tier"), state.get("risk_level")):
        if isinstance(risk_value, str) and risk_value.lower() in {"high", "critical", "approval_required"}:
            return True
    evidence_policy = state.get("evidence_policy")
    if isinstance(evidence_policy, Mapping):
        for policy_risk in (evidence_policy.get("risk_tier"), evidence_policy.get("risk_level")):
            if isinstance(policy_risk, str) and policy_risk.lower() in {"high", "critical", "approval_required"}:
                return True
    draft = state.get("recommendation_draft")
    if isinstance(draft, dict):
        draft_risk = draft.get("risk_level")
        if isinstance(draft_risk, str) and draft_risk.lower() in {"high", "critical", "approval_required"}:
            return True
    return False


def _partial_rag_has_unsafe_evidence_indicator(state: AgentState) -> bool:
    package = state.get("verified_evidence_package")
    if not isinstance(package, Mapping):
        return False
    if _non_empty_sequence(package.get("stale_refs")) or _non_empty_sequence(package.get("conflict_refs")):
        return True
    if _non_empty_sequence(package.get("rejected_candidate_refs")):
        reason_codes = package.get("reason_codes")
        return not isinstance(reason_codes, list) or any(
            isinstance(code, str) and code in _RAG_CONTEXT_UNSAFE_REASON_CODES for code in reason_codes
        )
    return False


def _denial_blocks_required_claims(
    denied_resources: set[str],
    claim_dependency_map: Any,
    missing: list[str],
    facts: dict[str, Any],
    retrieval_status: Any,
    intent: str,
) -> bool:
    if not denied_resources:
        return False
    if not _valid_claim_dependency_map(claim_dependency_map):
        return True

    denied_ref_tokens = _denied_dependency_tokens(denied_resources, claim_dependency_map)
    if not denied_ref_tokens:
        return False

    if set(missing) & denied_ref_tokens:
        return True

    has_independent_facts = bool(facts)
    has_independent_policy_evidence = retrieval_status in {"strong_evidence", "partial_evidence"}
    if intent in _FACT_ONLY_INTENTS:
        return not has_independent_facts
    return not (has_independent_facts or has_independent_policy_evidence)


def _valid_claim_dependency_map(claim_dependency_map: Any) -> bool:
    if not isinstance(claim_dependency_map, list) or not claim_dependency_map:
        return False
    for entry in claim_dependency_map:
        if not isinstance(entry, dict):
            return False
        if not isinstance(entry.get("claim_id"), str):
            return False
        refs = entry.get("depends_on_refs")
        if not isinstance(refs, list):
            return False
        for ref in refs:
            if not isinstance(ref, dict):
                return False
            if not isinstance(ref.get("resource_type"), str) or not isinstance(ref.get("resource_id"), str):
                return False
    return True


def _denied_dependency_tokens(denied_resources: set[str], claim_dependency_map: list[dict[str, Any]]) -> set[str]:
    denied_tokens: set[str] = set()
    for entry in claim_dependency_map:
        for ref in entry["depends_on_refs"]:
            resource_type = ref["resource_type"]
            resource_id = ref["resource_id"]
            if resource_type in denied_resources or resource_id in denied_resources:
                denied_tokens.update({resource_type, resource_id})
    return denied_tokens
