from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal


TargetMerchantContextStatus = Literal["resolved", "deferred", "unavailable", "not_applicable"]

SCHEMA_VERSION = "target_merchant_context.v1"
DEFERRED_REASON = "TARGET_MERCHANT_CONTEXT_DEFERRED_UNTIL_BUSINESS_FACT_REF"
UNAVAILABLE_REASON = "TARGET_MERCHANT_CONTEXT_UNAVAILABLE"

_VALID_STATUSES = {"resolved", "deferred", "unavailable", "not_applicable"}
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
_TRUSTED_REF_SOURCES = {
    "business_fact_service",
    "business_tool_service",
    "tool_platform",
    "tool_result_v2",
}


def project_target_merchant_context(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project safe target merchant-context status metadata from agent state."""
    explicit = state.get("target_merchant_context")
    if isinstance(explicit, Mapping):
        explicit_status = explicit.get("status")
        if explicit_status in {"deferred", "unavailable", "not_applicable"}:
            return _status(
                explicit_status,
                source=_safe_source(explicit.get("source"), fallback="explicit_state"),
                reason_codes=_safe_reason_codes(explicit.get("reason_codes")),
            )

    approved_refs = _service_approved_business_fact_refs(state)
    if approved_refs:
        return _status(
            "resolved",
            source="business_fact_refs",
            reason_codes=[],
            business_fact_ref_count=len(approved_refs),
        )

    if _has_malformed_or_denied_business_context(state):
        return _status("unavailable", source="business_fact_refs", reason_codes=[UNAVAILABLE_REASON])

    if _is_business_scoped_path(state):
        return _status("deferred", source="business_fact_refs", reason_codes=[DEFERRED_REASON])

    return _status("not_applicable", source="intent_policy", reason_codes=[])


def _service_approved_business_fact_refs(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    tenant_id = _non_empty_str(state.get("tenant_id"))
    refs: list[Mapping[str, Any]] = []
    for ref in _candidate_business_fact_refs(state):
        if _is_service_approved_business_fact_ref(ref, tenant_id=tenant_id):
            refs.append(ref)
    return refs


def _candidate_business_fact_refs(state: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    last_refs = state.get("last_business_context_refs")
    if isinstance(last_refs, Mapping):
        yield from _mapping_items(last_refs.get("business_fact_refs"))

    business_context = state.get("business_context")
    if not isinstance(business_context, Mapping):
        return

    yield from _mapping_items(business_context.get("business_fact_refs"))
    for tool_result in _mapping_items(business_context.get("tool_results")):
        if tool_result.get("schema_version") == "tool_result.v2":
            yield from _mapping_items(tool_result.get("business_fact_refs"))


def _mapping_items(value: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _is_service_approved_business_fact_ref(ref: Mapping[str, Any], *, tenant_id: str | None) -> bool:
    if ref.get("schema_version") not in {None, "business_fact_ref.v1"}:
        return False
    if not _non_empty_str(ref.get("resource_type")) or not _non_empty_str(ref.get("resource_id")):
        return False
    if tenant_id and ref.get("tenant_id") != tenant_id:
        return False
    if not _non_empty_str(ref.get("tenant_id")):
        return False
    if ref.get("source_system") not in _TRUSTED_REF_SOURCES:
        return False
    return True


def _has_malformed_or_denied_business_context(state: Mapping[str, Any]) -> bool:
    for container_name in ("last_business_context_refs", "business_context"):
        container = state.get(container_name)
        if not isinstance(container, Mapping):
            continue
        status = str(container.get("status") or "").lower()
        if status in {"permission_denied", "forbidden", "unauthorized", "no_authority"}:
            return True
        reason_codes = container.get("reason_codes")
        if isinstance(reason_codes, list) and any("NO_AUTHORITY" in str(code) for code in reason_codes):
            return True
        if container.get("business_fact_refs") is not None and not any(
            _is_service_approved_business_fact_ref(ref, tenant_id=_non_empty_str(state.get("tenant_id")))
            for ref in _mapping_items(container.get("business_fact_refs"))
        ):
            return True
    return False


def _is_business_scoped_path(state: Mapping[str, Any]) -> bool:
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


def _status(
    status: TargetMerchantContextStatus | str,
    *,
    source: str,
    reason_codes: list[str],
    business_fact_ref_count: int | None = None,
) -> dict[str, Any]:
    normalized_status = status if status in _VALID_STATUSES else "unavailable"
    projected: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": normalized_status,
        "source": source,
        "reason_codes": reason_codes,
    }
    if normalized_status == "resolved" and business_fact_ref_count is not None:
        projected["business_fact_ref_count"] = business_fact_ref_count
    return projected


def _safe_source(value: Any, *, fallback: str) -> str:
    source = _non_empty_str(value)
    return source if source else fallback


def _safe_reason_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(code) for code in value if isinstance(code, str) and code]


def _non_empty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
