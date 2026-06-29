from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import ValidationError

from src.agent.merchant_context import project_target_merchant_context
from src.business.schemas import BusinessFactResultV1
from src.tools.contracts import BusinessFactRefV1


ReplayAuthorizationProofStatus = Literal[
    "resolved",
    "unknown",
    "mixed",
    "denied",
    "invalid",
    "cross_merchant",
    "not_applicable",
]
ReplayAuthorizationProofSource = Literal[
    "business_fact_refs",
    "business_fact_results",
    "target_merchant_context",
    "combined",
    "none",
]

SCHEMA_VERSION = "replay_authorization_proof.v1"

_BUSINESS_SCOPED_INTENTS = {
    "order_status_inquiry",
    "refund_troubleshooting",
    "compensation_suggestion",
    "ticket_reply_draft",
    "appeal_or_unban",
    "complaint_escalation",
    "action_request",
}
_DIRECT_RESPONSE_INTENTS = {"small_talk", "unsupported", "out_of_scope", "general_chat"}

_MISSING_REASON = "REPLAY_AUTHORIZATION_PROOF_MISSING"
_DENIED_REASON = "REPLAY_AUTHORIZATION_PROOF_DENIED"
_INVALID_REASON = "REPLAY_AUTHORIZATION_PROOF_INVALID"
_MIXED_TENANTS_REASON = "REPLAY_AUTHORIZATION_PROOF_MIXED_TENANTS"
_MIXED_DECISION_REASON = "REPLAY_AUTHORIZATION_PROOF_MIXED_DECISIONS"
_TARGET_CONFLICT_REASON = "REPLAY_AUTHORIZATION_PROOF_TARGET_CONFLICT"
_UNTRUSTED_STATUS_REASON = "REPLAY_AUTHORIZATION_PROOF_UNTRUSTED_STATUS"
TRUSTED_BUSINESS_FACT_SOURCES = {
    "business_fact_service",
    "business_tool_service",
    "demo_orders_db",
    "demo_refund_cases_db",
    "demo_tickets_db",
    "tool_platform",
    "tool_result_v2",
}


def project_replay_authorization_proof(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project replay-safe proof status for future same-merchant authorization."""
    target_proof = _project_target_proof(state)
    ref_evidence = _inspect_business_fact_refs(state)
    result_evidence = _inspect_business_fact_results(state)
    scope_check_results = _scope_check_results(result_evidence.scope_check_results)

    has_ref_input = ref_evidence.seen
    has_result_input = result_evidence.seen
    has_allowed_refs = bool(ref_evidence.allowed_refs)
    has_allowed_results = bool(result_evidence.allowed_results)
    has_allowed = has_allowed_refs or has_allowed_results
    has_denied = ref_evidence.denied or result_evidence.denied

    reason_codes: list[str] = []
    if ref_evidence.invalid or result_evidence.invalid:
        status: ReplayAuthorizationProofStatus = "invalid"
        reason_codes.append(_INVALID_REASON)
    elif has_denied and has_allowed:
        status = "mixed"
        reason_codes.append(_MIXED_DECISION_REASON)
    elif has_denied:
        status = "denied"
        reason_codes.append(_DENIED_REASON)
    elif ref_evidence.mixed_tenants or result_evidence.mixed_tenants:
        status = "mixed"
        reason_codes.append(_MIXED_TENANTS_REASON)
    elif _target_conflicts_with_allowed_proof(state, target_proof=target_proof, has_allowed=has_allowed):
        status = "cross_merchant"
        reason_codes.append(_TARGET_CONFLICT_REASON)
    elif has_allowed:
        status = "resolved"
    elif ref_evidence.untrusted or result_evidence.untrusted:
        status = "unknown"
        reason_codes.append(_UNTRUSTED_STATUS_REASON)
    elif _business_scoped_path(state):
        status = "unknown"
        reason_codes.append(_MISSING_REASON)
    else:
        status = "not_applicable"

    return _projection(
        status=status,
        source=_proof_source(
            status=status,
            has_ref_input=has_ref_input,
            has_result_input=has_result_input,
            target_proof=target_proof,
        ),
        target_proof=target_proof,
        business_fact_ref_count=len(ref_evidence.allowed_refs) + result_evidence.allowed_ref_count,
        business_fact_result_count=len(result_evidence.allowed_results),
        scope_check_results=scope_check_results,
        reason_codes=reason_codes,
    )


class _RefEvidence:
    def __init__(
        self,
        *,
        seen: bool = False,
        allowed_refs: list[BusinessFactRefV1] | None = None,
        invalid: bool = False,
        denied: bool = False,
        mixed_tenants: bool = False,
        untrusted: bool = False,
    ) -> None:
        self.seen = seen
        self.allowed_refs = allowed_refs or []
        self.invalid = invalid
        self.denied = denied
        self.mixed_tenants = mixed_tenants
        self.untrusted = untrusted


class _ResultEvidence:
    def __init__(
        self,
        *,
        seen: bool = False,
        allowed_results: list[BusinessFactResultV1] | None = None,
        allowed_ref_count: int = 0,
        scope_check_results: list[str] | None = None,
        invalid: bool = False,
        denied: bool = False,
        mixed_tenants: bool = False,
        untrusted: bool = False,
    ) -> None:
        self.seen = seen
        self.allowed_results = allowed_results or []
        self.allowed_ref_count = allowed_ref_count
        self.scope_check_results = scope_check_results or []
        self.invalid = invalid
        self.denied = denied
        self.mixed_tenants = mixed_tenants
        self.untrusted = untrusted


def _inspect_business_fact_refs(state: Mapping[str, Any]) -> _RefEvidence:
    state_tenant = _non_empty_str(state.get("tenant_id"))
    refs: list[BusinessFactRefV1] = []
    seen = False
    invalid = False
    mixed_tenants = False
    untrusted = False

    for payload in _candidate_ref_payloads(state):
        seen = True
        try:
            ref = BusinessFactRefV1.model_validate(payload)
        except ValidationError:
            invalid = True
            continue
        if not _non_empty_str(ref.resource_id):
            invalid = True
            continue
        if not _is_trusted_business_fact_source(ref.source_system):
            untrusted = True
            continue
        if state_tenant and ref.tenant_id != state_tenant:
            mixed_tenants = True
        refs.append(ref)

    return _RefEvidence(
        seen=seen,
        allowed_refs=refs if not invalid else [],
        invalid=invalid,
        mixed_tenants=mixed_tenants,
        untrusted=untrusted,
    )


def _inspect_business_fact_results(state: Mapping[str, Any]) -> _ResultEvidence:
    state_tenant = _non_empty_str(state.get("tenant_id"))
    seen = False
    invalid = False
    denied = False
    mixed_tenants = False
    untrusted = False
    allowed_results: list[BusinessFactResultV1] = []
    allowed_ref_count = 0
    scope_check_results: list[str] = []

    for payload in _candidate_result_payloads(state):
        seen = True
        try:
            result = BusinessFactResultV1.model_validate(payload)
        except ValidationError:
            invalid = True
            continue
        scope_check_results.append(result.scope_check_result)
        if not _is_trusted_business_fact_source(result.source_system):
            untrusted = True
            continue
        if state_tenant and result.tenant_id != state_tenant:
            mixed_tenants = True
        if result.status == "permission_denied" or result.scope_check_result == "denied":
            denied = True
            continue
        if result.status not in {"ok", "partial"} or result.scope_check_result != "allowed":
            untrusted = True
            continue
        if not result.business_fact_refs:
            invalid = True
            continue
        result_refs_valid = True
        for ref in result.business_fact_refs:
            if not _non_empty_str(ref.resource_id):
                invalid = True
                result_refs_valid = False
                break
            if not _is_trusted_business_fact_source(ref.source_system):
                untrusted = True
                result_refs_valid = False
                break
            if state_tenant and ref.tenant_id != state_tenant:
                mixed_tenants = True
        if not result_refs_valid:
            continue
        allowed_results.append(result)
        allowed_ref_count += len(result.business_fact_refs)

    return _ResultEvidence(
        seen=seen,
        allowed_results=allowed_results if not invalid else [],
        allowed_ref_count=allowed_ref_count if not invalid else 0,
        scope_check_results=scope_check_results,
        invalid=invalid,
        denied=denied,
        mixed_tenants=mixed_tenants,
        untrusted=untrusted,
    )


def _candidate_ref_payloads(state: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield from _mapping_items(state.get("business_fact_refs"))

    last_refs = state.get("last_business_context_refs")
    if isinstance(last_refs, Mapping):
        yield from _mapping_items(last_refs.get("business_fact_refs"))

    business_context = state.get("business_context")
    if isinstance(business_context, Mapping):
        yield from _mapping_items(business_context.get("business_fact_refs"))
        for tool_result in _mapping_items(business_context.get("tool_results")):
            yield from _mapping_items(tool_result.get("business_fact_refs"))


def _candidate_result_payloads(state: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield from _mapping_items(state.get("business_fact_results"))

    last_refs = state.get("last_business_context_refs")
    if isinstance(last_refs, Mapping):
        yield from _mapping_items(last_refs.get("business_fact_results"))

    business_context = state.get("business_context")
    if isinstance(business_context, Mapping):
        yield from _mapping_items(business_context.get("business_fact_results"))
        for item in _mapping_items(business_context.get("tool_results")):
            if item.get("schema_version") == "business_fact_result.v1" or "scope_check_result" in item:
                yield item


def _is_trusted_business_fact_source(source_system: Any) -> bool:
    return isinstance(source_system, str) and source_system in TRUSTED_BUSINESS_FACT_SOURCES


def _project_target_proof(state: Mapping[str, Any]) -> dict[str, Any]:
    target = project_target_merchant_context(state)
    return {
        "status": target.get("status"),
        "source": target.get("source"),
        "reason_codes": _reason_codes(target.get("reason_codes")),
    }


def _target_conflicts_with_allowed_proof(
    state: Mapping[str, Any],
    *,
    target_proof: Mapping[str, Any],
    has_allowed: bool,
) -> bool:
    if not has_allowed:
        return False
    explicit = state.get("target_merchant_context")
    if not isinstance(explicit, Mapping):
        return False
    return target_proof.get("status") in {"deferred", "unavailable"}


def _proof_source(
    *,
    status: ReplayAuthorizationProofStatus,
    has_ref_input: bool,
    has_result_input: bool,
    target_proof: Mapping[str, Any],
) -> ReplayAuthorizationProofSource:
    if status == "not_applicable" and target_proof.get("status") == "not_applicable":
        return "target_merchant_context"
    if has_ref_input and has_result_input:
        return "combined"
    if status == "cross_merchant":
        return "combined"
    if has_result_input:
        return "business_fact_results"
    if has_ref_input:
        return "business_fact_refs"
    return "none"


def _projection(
    *,
    status: ReplayAuthorizationProofStatus,
    source: ReplayAuthorizationProofSource,
    target_proof: dict[str, Any],
    business_fact_ref_count: int,
    business_fact_result_count: int,
    scope_check_results: list[str],
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proof_status": status,
        "proof_source": source,
        "target_merchant_proof": target_proof,
        "business_fact_ref_count": business_fact_ref_count,
        "business_fact_result_count": business_fact_result_count,
        "scope_check_results": scope_check_results,
        "reason_codes": _reason_codes(reason_codes),
    }


def _business_scoped_path(state: Mapping[str, Any]) -> bool:
    intent = _non_empty_str(state.get("current_intent") or state.get("primary_intent") or state.get("last_intent"))
    if intent in _BUSINESS_SCOPED_INTENTS:
        return True
    if intent in _DIRECT_RESPONSE_INTENTS:
        return False
    route = _non_empty_str(state.get("next_route") or state.get("route") or state.get("requested_operation"))
    if route and route not in {"direct_response", "final_response", "policy_qa"}:
        return True
    for field in ("business_context", "last_business_context_refs"):
        if isinstance(state.get(field), Mapping):
            return True
    return False


def _mapping_items(value: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _scope_check_results(values: list[str]) -> list[str]:
    allowed = {"allowed", "denied", "not_applicable", "unknown"}
    results: list[str] = []
    for value in values:
        if value in allowed and value not in results:
            results.append(value)
    return results


def _reason_codes(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    codes: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value.isascii() and value.replace("_", "").isalnum():
            codes.append(value)
    return codes


def _non_empty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
