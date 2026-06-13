from __future__ import annotations

from typing import Any

from src.agent.state import AgentState


MIN_EVIDENCE_SCORE = 0.55
_FACT_ONLY_INTENTS = {"order_status_inquiry"}
_PERMISSION_CODES = {"FORBIDDEN", "permission_denied"}
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "recommendation_generation"}


def route_after_investigate(state: AgentState) -> str:
    """Route after the merged investigate node using state only."""
    try:
        route = _route_after_investigate(state)
    except Exception:
        return "final_response"
    if route in _INVESTIGATE_ROUTES:
        return route
    return "final_response"


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
        if _denial_blocks_required_claims(denied_resources, claim_dependency_map, missing, facts, retrieval_status, intent):
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
