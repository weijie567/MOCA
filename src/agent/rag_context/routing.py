"""Deterministic verifier route mapping for Phase 22."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VerificationRoute(StrEnum):
    ALLOW = "allow"
    REGENERATE_ROUTE = "regenerate_route"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REFUSE = "refuse"
    MANUAL_REVIEW = "manual_review"


class VerificationRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["verification_route_decision.v1"] = "verification_route_decision.v1"
    route: VerificationRoute
    overall_outcome: str
    reason_codes: list[str] = Field(default_factory=list)
    safe_citation_refs: list[str] = Field(default_factory=list)
    metrics: dict[str, int | float | bool | str] = Field(default_factory=dict)
    selected_by: Literal["backend"] = "backend"
    model_selected: bool = False
    decision_source: Literal["phase22_backend_route_map"] = "phase22_backend_route_map"
    allow_recommendation: bool = False
    allow_proposed_action: bool = False
    allow_approval_request: bool = False
    allow_action_draft: bool = False
    allow_action_safety_snapshot_evidence: bool = False
    regeneration_attempt_started: bool = False
    regeneration_attempt_count: int = 0
    next_backend_action: str


_ROUTE_REFUSE_REASONS = {
    "unauthorized_evidence",
    "scope_invalid",
    "merchant_scope_invalid",
    "doc_type_invalid",
    "risk_level_invalid",
    "text_hash_mismatch",
    "hash_mismatch",
    "latest_version_invalid",
    "tenant_scope_invalid",
}
_ROUTE_MANUAL_REVIEW_REASONS = {
    "conflicting_evidence",
    "conflict",
    "manual_review_sensitive",
    "semantic_ambiguous",
    "semantic_provider_timeout",
    "semantic_provider_error",
    "semantic_provider_malformed",
    "semantic_budget_claim_count_exceeded",
    "semantic_budget_evidence_count_exceeded",
    "semantic_budget_input_chars_exceeded",
    "needs_semantic_review",
    "level2_partial_overlap_ambiguous",
}
_ROUTE_STALE_OR_OCR_REASONS = {"stale_evidence", "freshness_invalid", "effective_date_invalid", "ocr_low_confidence"}
_ROUTE_INSUFFICIENT_REASONS = {
    "business_fact_missing",
    "business_fact_ref_required",
    "missing_citation",
    "policy_evidence_required",
    "policy_dependency_required",
    "business_dependency_required",
    "insufficient_evidence",
    "evidence_text_required",
    "canonical_content_missing",
}
_ROUTE_REGENERATE_REASONS = {
    "unsupported",
    "cited_but_unsupported",
    "citation_membership_not_support",
    "missing_citation",
}
_SUPPORTED_OUTCOMES = {"supported", "allow"}
_MANUAL_REVIEW_OUTCOMES = {"manual_review", "needs_manual_review", "ambiguous", "fail_closed", "conflict", "stale"}
_INSUFFICIENT_OUTCOMES = {"insufficient", "business_fact_missing"}
_REFUSE_OUTCOMES = {"unauthorized", "scope_invalid", "hash_mismatch", "latest_version_invalid"}
_UNSUPPORTED_OUTCOMES = {"unsupported", "ocr_low_confidence"}


def determine_verification_route(verifier_state: Mapping[str, Any] | Any) -> VerificationRouteDecision:
    """Map a typed verifier outcome to a backend-owned safety route."""

    try:
        state = _as_mapping(verifier_state)
        reason_codes = _string_list(state.get("reason_codes"))
        outcome = _normalized(state.get("overall_outcome") or state.get("outcome") or state.get("verifier_status"))
        route = _determine_route(state, outcome, set(reason_codes))
        return _decision(
            route=route,
            overall_outcome=outcome or "unknown",
            reason_codes=reason_codes,
            safe_citation_refs=_safe_refs(state),
            metrics=_safe_metrics(state),
        )
    except Exception:
        return _decision(
            route=VerificationRoute.MANUAL_REVIEW,
            overall_outcome="unknown",
            reason_codes=["route_map_exception"],
        )


def _determine_route(state: Mapping[str, Any], outcome: str, reasons: set[str]) -> VerificationRoute:
    if outcome in _SUPPORTED_OUTCOMES and not _has_blocking_reason(reasons):
        return VerificationRoute.ALLOW
    if _ROUTE_REFUSE_REASONS & reasons or outcome in _REFUSE_OUTCOMES:
        return VerificationRoute.REFUSE
    if _ROUTE_MANUAL_REVIEW_REASONS & reasons or outcome in _MANUAL_REVIEW_OUTCOMES:
        return VerificationRoute.MANUAL_REVIEW
    if _ROUTE_STALE_OR_OCR_REASONS & reasons:
        return VerificationRoute.MANUAL_REVIEW if _high_risk_or_action(state) else VerificationRoute.INSUFFICIENT_EVIDENCE
    if _regenerate_enabled(state) and (_ROUTE_REGENERATE_REASONS & reasons or outcome in _UNSUPPORTED_OUTCOMES):
        return VerificationRoute.REGENERATE_ROUTE
    if _ROUTE_INSUFFICIENT_REASONS & reasons or outcome in _INSUFFICIENT_OUTCOMES | _UNSUPPORTED_OUTCOMES:
        return VerificationRoute.INSUFFICIENT_EVIDENCE
    return VerificationRoute.MANUAL_REVIEW


def _decision(
    *,
    route: VerificationRoute,
    overall_outcome: str,
    reason_codes: Sequence[str],
    safe_citation_refs: Sequence[str] = (),
    metrics: Mapping[str, Any] | None = None,
) -> VerificationRouteDecision:
    allow = route == VerificationRoute.ALLOW
    return VerificationRouteDecision(
        route=route,
        overall_outcome=overall_outcome,
        reason_codes=list(dict.fromkeys(str(code) for code in reason_codes if str(code))),
        safe_citation_refs=list(dict.fromkeys(str(ref) for ref in safe_citation_refs if str(ref))),
        metrics=dict(metrics or {}),
        allow_recommendation=allow,
        allow_proposed_action=allow,
        allow_approval_request=allow,
        allow_action_draft=allow,
        allow_action_safety_snapshot_evidence=allow,
        next_backend_action=route.value,
    )


def _as_mapping(value: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _normalized(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _regenerate_enabled(state: Mapping[str, Any]) -> bool:
    return state.get("regenerate_route_enabled") is True


def _high_risk_or_action(state: Mapping[str, Any]) -> bool:
    return _normalized(state.get("risk_level")) in {"high", "critical", "manual_review"} or _normalized(
        state.get("authority_class")
    ) == "action_recommendation_claim"


def _has_blocking_reason(reasons: set[str]) -> bool:
    return bool(
        reasons
        & (
            _ROUTE_REFUSE_REASONS
            | _ROUTE_MANUAL_REVIEW_REASONS
            | _ROUTE_STALE_OR_OCR_REASONS
            | _ROUTE_INSUFFICIENT_REASONS
            | _ROUTE_REGENERATE_REASONS
        )
    )


def _safe_refs(state: Mapping[str, Any]) -> list[str]:
    for key in ("safe_citation_refs", "safe_support_refs", "safe_refs"):
        refs = _string_list(state.get(key))
        if refs:
            return refs
    return []


def _safe_metrics(state: Mapping[str, Any]) -> dict[str, int | float | bool | str]:
    metrics = state.get("metrics")
    if not isinstance(metrics, Mapping):
        return {}
    safe: dict[str, int | float | bool | str] = {}
    for key, value in metrics.items():
        if isinstance(key, str) and isinstance(value, int | float | bool | str):
            safe[key] = value
    return safe


__all__ = [
    "VerificationRoute",
    "VerificationRouteDecision",
    "determine_verification_route",
]
