from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    INTENT_ROUTE_POLICY,
    REQUIRED_SLOT_POLICY,
    PreRouteDecision,
    confidence_requires_clarification,
)
from src.agent.schemas import RequiredSlotExpression
from src.agent.state import AgentState


MIN_EVIDENCE_SCORE = 0.55
_FACT_ONLY_INTENTS = {"order_status_inquiry"}
_PERMISSION_CODES = {"FORBIDDEN", "permission_denied"}
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "recommendation_generation"}
_RECOMMENDATION_ROUTES = {"assess_risk_and_approval", "final_response"}
INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "session_memory_load"}
SLOT_ROUTES = {"clarification_gate", "investigate", "long_term_memory_retrieve"}
BUSINESS_ID_SLOTS = ("order_id", "refund_case_id", "ticket_id")
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


def route_after_intent(state: AgentState) -> str:
    try:
        route = _route_after_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in INTENT_ROUTES else "clarification_gate"


def route_after_slots(state: AgentState) -> str:
    try:
        route = _route_after_slots(state)
    except Exception:
        return "clarification_gate"
    return route if route in SLOT_ROUTES else "clarification_gate"


def missing_required_slots(
    required_slots: dict[str, Any] | RequiredSlotExpression | None,
    resolved_slots: dict[str, Any] | None,
) -> list[dict[str, list[str]]]:
    expression = _required_expression(required_slots)
    slots = {key: value for key, value in (resolved_slots or {}).items() if value not in (None, "")}
    missing: list[dict[str, list[str]]] = []
    for slot in expression.all_of:
        if slot not in slots:
            missing.append({"all_of": [slot]})
    for group in expression.any_of:
        if group and not any(slot in slots for slot in group):
            missing.append({"any_of": list(group)})
    return missing


def resolve_slots_for_completeness(state: AgentState) -> dict[str, Any]:
    resolved, _metadata = resolve_slots_with_metadata(state)
    return resolved


def resolve_slots_with_metadata(state: AgentState) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    extracted = state.get("extracted_slots")
    current_slots = {key: value for key, value in (extracted or {}).items() if value not in (None, "")}
    invalidations = detect_slot_invalidations(str(state.get("user_query") or ""))
    session_memory = state.get("session_memory")
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
    for slot, value in current_slots.items():
        resolved[slot] = value
        resolved_metadata[slot] = _current_turn_slot_metadata(
            slot,
            value,
            state,
            active_slots,
            slot_metadata,
            invalidations,
        )

    if not isinstance(session_memory, dict) or session_memory.get("continuity_claimed") is not True:
        return resolved, resolved_metadata
    if not isinstance(active_slots, dict) or not isinstance(slot_metadata, dict):
        return resolved, resolved_metadata
    for slot, value in active_slots.items():
        if slot in resolved or value in (None, ""):
            continue
        metadata = slot_metadata.get(slot)
        if _trusted_session_slot(metadata, state):
            if slot in invalidations:
                resolved_metadata[slot] = _invalidated_slot_metadata(metadata, invalidations[slot])
                continue
            resolved[slot] = value
            resolved_metadata[slot] = {
                **metadata,
                "source": "trusted_session_memory",
                "explicit_current_turn": False,
            }
    return resolved, resolved_metadata


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
        and _trusted_session_slot(prior_metadata, state)
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
    if intent in DIRECT_RESPONSE_INTENTS:
        return "final_response"
    if intent not in INTENT_ROUTE_POLICY:
        return "clarification_gate"
    policy = REQUIRED_SLOT_POLICY.get(intent)
    if policy is not None and not policy.all_of and not policy.any_of:
        return "investigate"
    return "session_memory_load"


def _route_after_slots(state: AgentState) -> str:
    intent = _intent(state)
    policy = REQUIRED_SLOT_POLICY.get(intent)
    if policy is None:
        return "clarification_gate"
    state_required = state.get("required_slots")
    if state_required not in (None, {}):
        try:
            if _required_expression(state_required).model_dump() != policy.model_dump():
                return "clarification_gate"
        except Exception:
            return "clarification_gate"
    missing = missing_required_slots(policy, resolve_slots_for_completeness(state))
    if missing:
        return "clarification_gate"
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if routing_hints.get("needs_long_term_memory") is True:
        return "long_term_memory_retrieve"
    return "investigate"


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


def _route_after_recommendation(state: AgentState) -> str:
    route = _recommendation_verification_route(state)
    if route is None or route == "allow":
        return "assess_risk_and_approval"
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


def _trusted_session_slot(metadata: Any, state: AgentState) -> bool:
    if not isinstance(metadata, dict):
        return False
    if metadata.get("source") != "trusted_session_memory":
        return False
    for key in ("tenant_id", "user_id", "thread_id"):
        if str(metadata.get(key)) != str(state.get(key)):
            return False
    expires_at = metadata.get("expires_at")
    if isinstance(expires_at, str):
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        if parsed <= datetime.now(UTC):
            return False
    elif metadata.get("fresh") is not True:
        return False
    compatible = metadata.get("intent_compatible")
    compatible_intents = metadata.get("compatible_intents")
    if compatible is True:
        return True
    if isinstance(compatible_intents, list) and _intent(state) in compatible_intents:
        return True
    return False


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
