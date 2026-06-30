from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from src.approvals.schemas import TargetMerchantBindingV1
from src.business.schemas import BusinessFactResultV1
from src.tools.contracts import BusinessFactRefV1


BUSINESS_MERCHANT = "business_merchant"
POLICY_ONLY = "policy_only"
MERCHANT_NOT_REQUIRED = "merchant_not_required"
UNKNOWN_LEGACY = "unknown_legacy"
AGENT_RUN_SCOPE_CLASSIFICATIONS = {
    BUSINESS_MERCHANT,
    POLICY_ONLY,
    MERCHANT_NOT_REQUIRED,
    UNKNOWN_LEGACY,
}

_BUSINESS_SCOPED_INTENTS = {
    "order_status_inquiry",
    "refund_troubleshooting",
    "compensation_suggestion",
    "ticket_reply_draft",
    "appeal_or_unban",
    "complaint_escalation",
    "action_request",
}
_POLICY_ONLY_INTENTS = {
    "policy_qa",
    "policy_search",
    "rule_inquiry",
}
_DIRECT_RESPONSE_INTENTS = {"small_talk", "unsupported", "out_of_scope", "general_chat"}
_NON_BUSINESS_ROUTES = {"direct_response", "policy_qa", "final" + "_response"}
_TRUSTED_FACT_SOURCES = {
    "business_fact_service",
    "business_tool_service",
    "demo_orders_db",
    "demo_refund_cases_db",
    "demo_tickets_db",
    "tool_platform",
    "tool_result_v2",
}


@dataclass(frozen=True)
class AgentRunScopeFacts:
    scope_classification: str
    target_merchant_id: str | None
    target_merchant_ref: dict[str, Any] | None
    scope_source: str
    scope_reason_codes: list[str]


@dataclass(frozen=True)
class _ScopeCandidate:
    target_merchant_id: str
    target_merchant_ref: dict[str, Any]
    scope_source: str


def classify_agent_run_scope(state: Mapping[str, Any]) -> AgentRunScopeFacts:
    candidates: list[_ScopeCandidate] = []
    reason_codes: list[str] = []

    approval_candidate, approval_errors = _candidate_from_approval_plan(state)
    if approval_candidate is not None:
        candidates.append(approval_candidate)
    reason_codes.extend(approval_errors)

    direct_candidate, direct_errors = _candidate_from_direct_binding(state)
    if direct_candidate is not None:
        candidates.append(direct_candidate)
    reason_codes.extend(direct_errors)

    fact_candidates, fact_errors = _candidates_from_business_fact_results(state)
    candidates.extend(fact_candidates)
    reason_codes.extend(fact_errors)

    context_candidates, context_errors = _candidates_from_business_context(state)
    candidates.extend(context_candidates)
    reason_codes.extend(context_errors)

    target_ids = {candidate.target_merchant_id for candidate in candidates}
    if len(target_ids) == 1 and not _has_hard_failure(reason_codes):
        selected = candidates[0]
        return AgentRunScopeFacts(
            scope_classification=BUSINESS_MERCHANT,
            target_merchant_id=selected.target_merchant_id,
            target_merchant_ref=selected.target_merchant_ref,
            scope_source=selected.scope_source,
            scope_reason_codes=[],
        )

    if len(target_ids) > 1:
        reason_codes.append("mixed_target_merchant_proof")

    if reason_codes or _is_business_scoped_path(state):
        if not reason_codes:
            reason_codes.append("no_authoritative_scope_proof")
        return AgentRunScopeFacts(
            scope_classification=UNKNOWN_LEGACY,
            target_merchant_id=None,
            target_merchant_ref=None,
            scope_source="run_scope_classifier",
            scope_reason_codes=_dedupe(reason_codes),
        )

    if _is_policy_only_path(state):
        return AgentRunScopeFacts(
            scope_classification=POLICY_ONLY,
            target_merchant_id=None,
            target_merchant_ref=None,
            scope_source="intent_policy",
            scope_reason_codes=[],
        )

    return AgentRunScopeFacts(
        scope_classification=MERCHANT_NOT_REQUIRED,
        target_merchant_id=None,
        target_merchant_ref=None,
        scope_source="intent_policy",
        scope_reason_codes=[],
    )


def _candidate_from_approval_plan(state: Mapping[str, Any]) -> tuple[_ScopeCandidate | None, list[str]]:
    plan = state.get("approval_plan")
    if not isinstance(plan, Mapping):
        return None, []

    plan_id = _non_empty_str(plan.get("target_merchant_id"))
    state_id = _non_empty_str(state.get("target_merchant_id"))
    if plan_id is None and state_id is None and plan.get("target_merchant_ref") is None:
        return None, []
    if plan_id is None or state_id is None or plan_id != state_id:
        return None, ["mixed_target_merchant_proof"]
    if plan.get("target_merchant_ref") != state.get("target_merchant_ref"):
        return None, ["mixed_target_merchant_proof"]

    candidate, reason = _candidate_from_binding_payload(
        target_id=plan_id,
        payload=plan.get("target_merchant_ref"),
        source="approval_plan_target_merchant_binding_v1",
    )
    return candidate, [reason] if reason else []


def _candidate_from_direct_binding(state: Mapping[str, Any]) -> tuple[_ScopeCandidate | None, list[str]]:
    target_id = _non_empty_str(state.get("target_merchant_id"))
    payload = state.get("target_merchant_ref")
    if target_id is None and payload is None:
        return None, []

    candidate, reason = _candidate_from_binding_payload(
        target_id=target_id,
        payload=payload,
        source="target_merchant_binding_v1",
    )
    return candidate, [reason] if reason else []


def _candidate_from_binding_payload(
    *,
    target_id: str | None,
    payload: Any,
    source: str,
) -> tuple[_ScopeCandidate | None, str | None]:
    if target_id is None or payload is None:
        return None, "malformed_target_merchant_ref"
    try:
        binding = TargetMerchantBindingV1.model_validate(payload)
    except ValidationError:
        return None, "malformed_target_merchant_ref"

    if binding.target_merchant_id != target_id:
        return None, "mixed_target_merchant_proof"

    return (
        _ScopeCandidate(
            target_merchant_id=binding.target_merchant_id,
            target_merchant_ref=binding.model_dump(mode="json"),
            scope_source=source,
        ),
        None,
    )


def _candidates_from_business_fact_results(state: Mapping[str, Any]) -> tuple[list[_ScopeCandidate], list[str]]:
    candidates: list[_ScopeCandidate] = []
    reason_codes: list[str] = []
    for payload in _candidate_result_payloads(state):
        try:
            result = BusinessFactResultV1.model_validate(payload)
        except ValidationError:
            reason_codes.append("malformed_business_fact_result")
            continue
        if not _is_authoritative_result(result):
            continue

        merchant_id = _non_empty_str(result.fact.get("merchant_id") if isinstance(result.fact, Mapping) else None)
        if merchant_id is None:
            reason_codes.append("missing_business_fact_merchant_id")
            continue
        if not result.business_fact_refs:
            reason_codes.append("missing_business_fact_ref")
            continue

        candidates.append(
            _ScopeCandidate(
                target_merchant_id=merchant_id,
                target_merchant_ref=TargetMerchantBindingV1(
                    target_merchant_id=merchant_id,
                    source="business_fact_result",
                    business_fact_ref=result.business_fact_refs[0].model_dump(mode="json"),
                ).model_dump(mode="json"),
                scope_source="business_fact_result_v1",
            )
        )
    return candidates, reason_codes


def _candidates_from_business_context(state: Mapping[str, Any]) -> tuple[list[_ScopeCandidate], list[str]]:
    context = state.get("business_context")
    if not isinstance(context, Mapping):
        return [], []

    facts = context.get("facts")
    if not isinstance(facts, Mapping):
        return [], []

    tenant_id = _non_empty_str(state.get("tenant_id"))
    refs_by_resource_type: dict[str, BusinessFactRefV1] = {}
    for raw_ref in _list_items(context.get("business_fact_refs")):
        try:
            ref = BusinessFactRefV1.model_validate(raw_ref)
        except ValidationError:
            return [], ["malformed_business_fact_ref"]
        if (
            tenant_id is not None
            and ref.tenant_id == tenant_id
            and ref.source_system in _TRUSTED_FACT_SOURCES
            and ref.resource_type not in refs_by_resource_type
        ):
            refs_by_resource_type[ref.resource_type] = ref

    candidates: list[_ScopeCandidate] = []
    reason_codes: list[str] = []
    for resource_type, fact in facts.items():
        if not isinstance(resource_type, str):
            continue

        merchant_id = _non_empty_str(fact.get("merchant_id") if isinstance(fact, Mapping) else None)
        if merchant_id is None:
            continue

        ref = refs_by_resource_type.get(resource_type)
        if ref is None:
            reason_codes.append("missing_business_fact_ref")
            continue

        candidates.append(
            _ScopeCandidate(
                target_merchant_id=merchant_id,
                target_merchant_ref=TargetMerchantBindingV1(
                    target_merchant_id=merchant_id,
                    source="business_fact_ref",
                    business_fact_ref=ref.model_dump(mode="json"),
                ).model_dump(mode="json"),
                scope_source="business_context_business_fact_ref_v1",
            )
        )
    return candidates, reason_codes


def _candidate_result_payloads(state: Mapping[str, Any]) -> Iterable[Any]:
    yield from _list_items(state.get("business_fact_results"))

    prior_context = state.get("last_business_context_refs")
    if isinstance(prior_context, Mapping):
        yield from _list_items(prior_context.get("business_fact_results"))

    context = state.get("business_context")
    if isinstance(context, Mapping):
        yield from _list_items(context.get("business_fact_results"))
        for item in _list_items(context.get("tool_results")):
            if isinstance(item, Mapping) and (
                item.get("schema_version") == "business_fact_result.v1" or "scope_check_result" in item
            ):
                yield item


def _is_authoritative_result(result: BusinessFactResultV1) -> bool:
    return (
        result.source_system in _TRUSTED_FACT_SOURCES
        and result.status in {"ok", "partial"}
        and result.scope_check_result == "allowed"
        and isinstance(result.fact, Mapping)
    )


def _is_business_scoped_path(state: Mapping[str, Any]) -> bool:
    intent = _non_empty_str(state.get("current_intent") or state.get("primary_intent") or state.get("last_intent"))
    if intent in _BUSINESS_SCOPED_INTENTS:
        return True
    if intent in _DIRECT_RESPONSE_INTENTS or intent in _POLICY_ONLY_INTENTS:
        return False

    route = _non_empty_str(state.get("next_route") or state.get("route") or state.get("requested_operation"))
    if route and route not in _NON_BUSINESS_ROUTES:
        return True

    return any(
        bool(state.get(field))
        for field in (
            "business_context",
            "last_business_context_refs",
            "business_fact_results",
        )
    )


def _is_policy_only_path(state: Mapping[str, Any]) -> bool:
    intent = _non_empty_str(state.get("current_intent") or state.get("primary_intent") or state.get("last_intent"))
    if intent in _POLICY_ONLY_INTENTS:
        return True
    route = _non_empty_str(state.get("next_route") or state.get("route") or state.get("requested_operation"))
    return route == "policy_qa"


def _has_hard_failure(reason_codes: list[str]) -> bool:
    hard_failures = {
        "malformed_target_merchant_ref",
        "mixed_target_merchant_proof",
        "malformed_business_fact_result",
    }
    return any(reason in hard_failures for reason in reason_codes)


def _list_items(value: Any) -> Iterable[Any]:
    if not isinstance(value, list):
        return []
    return list(value)


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _non_empty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
