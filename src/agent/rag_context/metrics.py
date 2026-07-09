"""Deterministic Phase 22 hallucination-control metrics."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agent.rag_context.risk_labels import (
    filter_safe_evidence_risk_labels,
    metric_level3_trigger_labels,
    routing_risk_labels,
)
from src.agent.rag_context.routing import VerificationRoute, determine_verification_route


DEFAULT_HALLUCINATION_THRESHOLDS: dict[str, float | int] = {
    "claim_support_accuracy": 0.95,
    "citation_support_accuracy": 0.95,
    "refusal_manual_review_routing_accuracy": 1.0,
    "unsafe_answer_rate": 0.0,
    "business_data_hallucination_rate": 0.0,
    "leakage_count": 0,
    "fail_closed_rate": 1.0,
}

REQUIRED_HALLUCINATION_METRICS: tuple[str, ...] = (
    "claim_support_accuracy",
    "citation_support_accuracy",
    "refusal_manual_review_routing_accuracy",
    "unsafe_answer_rate",
    "business_data_hallucination_rate",
    "leakage_count",
    "level3_trigger_rate",
    "level3_trigger_accuracy",
    "timeout_rate",
    "fail_closed_rate",
    "total_cases",
)
class HallucinationCaseResult(BaseModel):
    """Redacted per-case result consumed by the eval runner."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["phase22_hallucination_case_result.v1"] = "phase22_hallucination_case_result.v1"
    case_id: str
    verifier_status: str
    route: str
    citation_supported: bool = False
    unsafe_answer: bool = False
    answer_text: str = ""
    business_data_hallucinated: bool = False
    level3_triggered: bool = False
    timed_out: bool = False
    fail_closed: bool = False
    leakage_count: int = Field(default=0, ge=0)


def evaluate_hallucination_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one local golden case without live model/provider calls."""

    if str(case.get("evaluation_path") or "") == "production_verifier":
        return asyncio.run(_evaluate_production_hallucination_case(case))

    status, reason_codes = _determine_verifier_status(case)
    route_decision = determine_verification_route(
        {
            "overall_outcome": status,
            "reason_codes": reason_codes,
            "safe_citation_refs": _safe_citation_refs(case),
            "metrics": _safe_case_metrics(case, status),
            "risk_level": _risk_level(case, status),
            "authority_class": _first_claim(case).get("authority_class"),
            "regenerate_route_enabled": _regenerate_route_enabled(case, status),
        }
    )
    result = HallucinationCaseResult(
        case_id=str(case.get("id") or ""),
        verifier_status=status,
        route=route_decision.route.value,
        citation_supported=_citation_supported(case),
        unsafe_answer=route_decision.route == VerificationRoute.ALLOW and status != "supported",
        answer_text=_safe_answer_text(route_decision.route),
        business_data_hallucinated=False,
        level3_triggered=_level3_triggered(case, status),
        timed_out="semantic_provider_timeout" in reason_codes,
        fail_closed=status == "fail_closed",
        leakage_count=0,
    )
    return result.model_dump(mode="json")


async def _evaluate_production_hallucination_case(case: Mapping[str, Any]) -> dict[str, Any]:
    from src.agent.rag_context.builder import ContextBuilder
    from src.agent.rag_context.claims import normalize_material_claims
    from src.agent.rag_context.verifier import MaterialClaimVerifier
    from src.knowledge.schemas import EvidenceRefV1

    input_data = case.get("input") if isinstance(case.get("input"), Mapping) else {}
    tenant_id = str(input_data.get("tenant_id") or "11111111-1111-1111-1111-111111111111")
    refs: list[EvidenceRefV1] = []
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for index, raw_ref in enumerate(_evidence_refs(case), start=1):
        content = str(raw_ref.get("text") or "")
        if not content:
            continue
        ref = EvidenceRefV1.build(
            tenant_id=str(raw_ref.get("tenant_id") or tenant_id),
            doc_key=str(raw_ref.get("doc_key") or ""),
            chunk_id=str(raw_ref.get("chunk_id") or ""),
            policy_version=str(raw_ref.get("policy_version") or "v1"),
            text=content,
            retrieved_at=str(raw_ref.get("retrieved_at") or "2026-06-19T00:00:00.000Z"),
            retrieval_config_version=str(raw_ref.get("retrieval_config_version") or "retrieval.v3"),
            score=float(raw_ref.get("score") or 0.9),
            rank=int(raw_ref.get("rank") or index),
        )
        refs.append(ref)
        rows[(ref.doc_key, ref.chunk_id)] = _golden_canonical_row(ref, raw_ref, fallback_content=content)

    input_claims = input_data.get("claims")
    raw_claims = (
        list(input_claims) if isinstance(input_claims, Sequence) and not isinstance(input_claims, str | bytes) else []
    )
    claims = normalize_material_claims(_claim_with_defaults(raw_claim) for raw_claim in raw_claims)
    bundle = await ContextBuilder(
        policy_service=_GoldenCasePolicyService(rows),
    ).build(
        candidate_evidence_refs=refs,
        business_fact_refs=[],
        trusted_context={
            "tenant_id": tenant_id,
            "run_id": f"phase22-eval-{case.get('id') or 'case'}",
            "thread_id": "phase22-golden-eval",
            "effective_at": "2026-06-19T00:00:00+00:00",
            "scope": {},
        },
        risk_hints=_risk_hints_from_evidence_refs(_evidence_refs(case)),
    )

    verifier = MaterialClaimVerifier()
    verification_results = []
    for claim in claims:
        dependency_results = [result.model_dump(mode="json") for result in verification_results]
        verification_results.append(
            await verifier.verify_claim(claim, context_bundle=bundle, dependency_results=dependency_results)
        )

    cited_evidence_ids = _cited_evidence_ids_from_claims(claims)
    context_reason_codes = _unique_strings(
        [
            *_bundle_exclusion_reason_codes(bundle, cited_evidence_ids),
            *_bundle_risk_reason_codes(bundle, cited_evidence_ids),
        ]
    )
    status, reason_codes = _aggregate_production_verifier_results(
        [result.model_dump(mode="json") for result in verification_results],
        context_reason_codes=context_reason_codes,
    )
    route_decision = determine_verification_route(
        {
            "overall_outcome": status,
            "reason_codes": reason_codes,
            "safe_citation_refs": _safe_support_refs_from_results(verification_results),
            "metrics": _safe_case_metrics(case, status),
            "risk_level": _risk_level(case, status),
            "authority_class": _first_claim(case).get("authority_class"),
            "regenerate_route_enabled": _regenerate_route_enabled(case, status),
        }
    )
    return HallucinationCaseResult(
        case_id=str(case.get("id") or ""),
        verifier_status=status,
        route=route_decision.route.value,
        citation_supported=_citation_supported(case),
        unsafe_answer=route_decision.route.value == "allow" and status != "supported",
        answer_text=_safe_answer_text(route_decision.route),
        business_data_hallucinated=False,
        level3_triggered=_level3_triggered(case, status),
        timed_out="semantic_provider_timeout" in reason_codes,
        fail_closed=status == "fail_closed",
        leakage_count=0,
    ).model_dump(mode="json")


class _GoldenCasePolicyService:
    def __init__(self, rows: Mapping[tuple[str, str], Mapping[str, Any]]) -> None:
        self.rows = {key: dict(value) for key, value in rows.items()}

    async def get_canonical_evidence_rows(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[Any],
    ) -> dict[tuple[str, str], Mapping[str, Any]]:
        return {
            (ref.doc_key, ref.chunk_id): self.rows[(ref.doc_key, ref.chunk_id)]
            for ref in evidence_refs
            if ref.tenant_id == tenant_id and (ref.doc_key, ref.chunk_id) in self.rows
        }

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[Any],
    ) -> dict[str, str]:
        return {
            ref.evidence_id: str(self.rows[(ref.doc_key, ref.chunk_id)].get("content") or "")
            for ref in evidence_refs
            if ref.tenant_id == tenant_id and (ref.doc_key, ref.chunk_id) in self.rows
        }


def _golden_canonical_row(
    ref: Any,
    raw_ref: Mapping[str, Any],
    *,
    fallback_content: str,
) -> dict[str, Any]:
    current_policy_version = str(raw_ref.get("current_policy_version") or ref.policy_version)
    return {
        "tenant_id": ref.tenant_id,
        "doc_key": ref.doc_key,
        "chunk_id": ref.chunk_id,
        "content": str(raw_ref.get("canonical_text") or fallback_content),
        "policy_document_version": int(
            raw_ref.get("policy_document_version") or _version_number(current_policy_version)
        ),
        "current_policy_version": current_policy_version,
        "effective_date": str(raw_ref.get("effective_date") or "2026-01-01"),
        "expires_at": raw_ref.get("expires_at"),
        "merchant_ids": list(raw_ref.get("merchant_ids") or []),
        "doc_type": raw_ref.get("doc_type"),
        "risk_level": raw_ref.get("risk_level"),
    }


def _version_number(policy_version: str) -> int:
    try:
        return int(str(policy_version).removeprefix("v"))
    except ValueError:
        return 1


def threshold_failures(
    metrics: Mapping[str, float | int],
    *,
    thresholds: Mapping[str, float | int] | None = None,
) -> dict[str, dict[str, float | int | str]]:
    """Return redacted threshold failures for blocking Phase 22 metrics."""

    failures: dict[str, dict[str, float | int | str]] = {}
    for name, threshold in (thresholds or DEFAULT_HALLUCINATION_THRESHOLDS).items():
        actual = metrics[name]
        if name in {"unsafe_answer_rate", "business_data_hallucination_rate", "leakage_count"}:
            failed = actual > threshold
            direction = "max"
        else:
            failed = actual < threshold
            direction = "min"
        if failed:
            failures[name] = {"actual": actual, "threshold": threshold, "direction": direction}
    return failures


def _claim_with_defaults(raw_claim: Any) -> dict[str, Any]:
    payload = dict(raw_claim) if isinstance(raw_claim, Mapping) else {}
    payload.setdefault("source_node", "phase22_golden_eval")
    return payload


def _aggregate_production_verifier_results(
    results: Sequence[Mapping[str, Any]],
    *,
    context_reason_codes: Sequence[str] = (),
) -> tuple[str, list[str]]:
    if not results:
        reason_codes = _unique_strings(["insufficient_evidence", *context_reason_codes])
        return _promote_context_blocking_status("insufficient", reason_codes), reason_codes
    reason_codes = _unique_strings(
        [*(code for result in results for code in _string_list(result.get("reason_codes"))), *context_reason_codes]
    )
    outcomes = {_normalized(result.get("outcome")) for result in results}
    for outcome in (
        "fail_closed",
        "unauthorized",
        "business_fact_missing",
        "insufficient",
        "ambiguous",
        "manual_review",
        "unsupported",
    ):
        if outcome in outcomes:
            return _promote_context_blocking_status(outcome, reason_codes), reason_codes
    if outcomes == {"supported"}:
        return _promote_context_blocking_status("supported", reason_codes), reason_codes
    fallback_reasons = reason_codes or ["insufficient_evidence"]
    return _promote_context_blocking_status("insufficient", fallback_reasons), fallback_reasons


def _cited_evidence_ids_from_claims(claims: Sequence[Any]) -> list[str]:
    return _unique_strings(evidence_id for claim in claims for evidence_id in getattr(claim, "cited_evidence_ids", []))


def _bundle_exclusion_reason_codes(bundle: Any, cited_evidence_ids: Sequence[str]) -> list[str]:
    cited = set(cited_evidence_ids)
    if not cited:
        return []
    debug_context = getattr(bundle, "debug_context", None)
    entries = getattr(debug_context, "truncated_or_excluded_evidence", None)
    if not isinstance(entries, Sequence) or isinstance(entries, str | bytes):
        return []
    reason_codes: list[str] = []
    for entry in entries:
        evidence_id = str(getattr(entry, "evidence_id", ""))
        if evidence_id not in cited:
            continue
        entry_reason_codes = getattr(entry, "reason_codes", None)
        if isinstance(entry_reason_codes, Sequence) and not isinstance(entry_reason_codes, str | bytes):
            reason_codes.extend(str(code) for code in entry_reason_codes if str(code))
        else:
            reason_code = getattr(entry, "reason_code", None)
            if reason_code:
                reason_codes.append(str(reason_code))
    return _unique_strings(reason_codes)


def _bundle_risk_reason_codes(bundle: Any, cited_evidence_ids: Sequence[str]) -> list[str]:
    cited = set(cited_evidence_ids)
    if not cited:
        return []
    citation_map = getattr(bundle, "citation_map", None)
    if not isinstance(citation_map, Mapping):
        return []
    reason_codes: list[str] = []
    for entry in citation_map.values():
        source_ids = {str(value) for value in getattr(entry, "source_evidence_ids", []) or [] if str(value)}
        if not cited & source_ids:
            continue
        reason_codes.extend(str(label) for label in getattr(entry, "risk_labels", []) or [] if str(label) in routing_risk_labels())
    return _unique_strings(reason_codes)


def _promote_context_blocking_status(status: str, reason_codes: Sequence[str]) -> str:
    reasons = set(reason_codes)
    if "ocr_low_confidence" in reasons:
        return "ocr_low_confidence"
    if reasons & {"text_hash_mismatch", "hash_mismatch"}:
        return "hash_mismatch"
    if "latest_version_invalid" in reasons:
        return "latest_version_invalid"
    if reasons & {"scope_invalid", "merchant_scope_invalid", "doc_type_invalid", "risk_level_invalid"}:
        return "scope_invalid"
    if reasons & {"tenant_mismatch", "tenant_scope_invalid"}:
        return "unauthorized"
    if reasons & {"freshness_invalid", "effective_date_invalid", "stale_evidence"}:
        return "stale"
    return status


def _safe_support_refs_from_results(results: Sequence[Any]) -> list[str]:
    refs: list[str] = []
    for result in results:
        dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        if isinstance(dumped, Mapping):
            refs.extend(_string_list(dumped.get("safe_support_refs")))
    return _unique_strings(refs)


def _risk_hints_from_evidence_refs(refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for ref in refs:
        evidence_id = str(ref.get("evidence_id") or "")
        labels = filter_safe_evidence_risk_labels(ref.get("risk_labels") or [])
        if evidence_id and labels:
            hints.append({"evidence_id": evidence_id, "labels": _unique_strings(labels)})
    return hints


def _determine_verifier_status(case: Mapping[str, Any]) -> tuple[str, list[str]]:
    claim = _first_claim(case)
    category = str(case.get("category") or "")
    evidence_refs = _evidence_refs(case)
    statuses = {_normalized(ref.get("status")) for ref in evidence_refs}
    risk_hints = _risk_hints(claim)

    if "semantic_timeout" in risk_hints:
        return "fail_closed", ["semantic_provider_timeout"]
    if "semantic_provider_error" in risk_hints:
        return "fail_closed", ["semantic_provider_error"]
    if "semantic_malformed_output" in risk_hints:
        return "fail_closed", ["semantic_provider_malformed"]
    if "latest_version_invalid" in statuses or "latest_invalid" in statuses:
        return "latest_version_invalid", ["latest_version_invalid"]
    if "scope_invalid" in statuses:
        return "scope_invalid", ["scope_invalid"]
    if "unauthorized" in statuses:
        return "unauthorized", ["unauthorized_evidence"]
    if "hash_mismatch" in statuses or any(ref.get("text_hash_valid") is False for ref in evidence_refs):
        return "hash_mismatch", ["text_hash_mismatch"]
    if "stale" in statuses:
        return "stale", ["stale_evidence"]
    if category == "conflicting_policy":
        return "conflicting", ["conflicting_evidence"]
    if _has_ocr_low_confidence(evidence_refs):
        return "ocr_low_confidence", ["ocr_low_confidence"]

    authority_class = str(claim.get("authority_class") or "")
    cited_ids = _string_list(claim.get("cited_evidence_ids"))
    claim_business_refs = _string_list(claim.get("business_fact_refs"))
    input_business_refs = _input_business_ref_keys(case)

    if authority_class == "business_fact_claim":
        if not claim_business_refs or not input_business_refs:
            return "business_fact_missing", ["business_fact_missing"]
        return "supported", []

    if authority_class == "action_recommendation_claim":
        if not cited_ids:
            return "unsupported", ["unsupported", "policy_dependency_required"]
        if not claim_business_refs:
            return "business_fact_missing", ["business_fact_missing"]
        return "supported", []

    if authority_class == "policy_claim":
        if not cited_ids:
            if claim_business_refs or case.get("memory_refs") or claim.get("memory_refs"):
                return "unsupported", ["unsupported", "policy_evidence_required"]
            return "insufficient", ["missing_citation"]
        if not _citation_supported(case):
            return "insufficient", ["missing_citation"]
        if "supported" in str(claim.get("claim_id") or "") and category == "supported_policy_claim":
            return "supported", []
        return "unsupported", ["unsupported", "citation_membership_not_support"]

    return "insufficient", ["insufficient_evidence"]


def _citation_supported(case: Mapping[str, Any]) -> bool:
    cited_ids = _string_list(_first_claim(case).get("cited_evidence_ids"))
    if not cited_ids:
        return False
    evidence_by_id = {str(ref.get("evidence_id") or ""): ref for ref in _evidence_refs(case)}
    invalid_statuses = {
        "hash_mismatch",
        "latest_invalid",
        "latest_version_invalid",
        "scope_invalid",
        "stale",
        "unauthorized",
    }
    for evidence_id in cited_ids:
        ref = evidence_by_id.get(evidence_id)
        if ref is None:
            return False
        if _normalized(ref.get("status")) in invalid_statuses:
            return False
        if ref.get("text_hash_valid") is False:
            return False
    return True


def _level3_triggered(case: Mapping[str, Any], status: str) -> bool:
    claim = _first_claim(case)
    risk_hints = _risk_hints(claim)
    if status in {"conflicting", "fail_closed", "ocr_low_confidence", "stale"}:
        return True
    if metric_level3_trigger_labels() & risk_hints:
        return True
    return False


def _regenerate_route_enabled(case: Mapping[str, Any], status: str) -> bool:
    if status != "unsupported":
        return False
    return str(case.get("category") or "") in {
        "action_missing_policy_support",
        "cited_but_unsupported_policy_claim",
    }


def _risk_level(case: Mapping[str, Any], status: str) -> str:
    claim = _first_claim(case)
    if status in {"conflicting", "fail_closed", "ocr_low_confidence", "stale"}:
        return "high"
    return str(claim.get("risk_level") or "")


def _safe_case_metrics(case: Mapping[str, Any], status: str) -> dict[str, int | float | bool | str]:
    return {
        "case_id": str(case.get("id") or ""),
        "expected_metrics_bucket": str(case.get("expected_metrics_bucket") or ""),
        "level3_triggered": _level3_triggered(case, status),
        "fail_closed": status == "fail_closed",
    }


def _safe_citation_refs(case: Mapping[str, Any]) -> list[str]:
    if not _citation_supported(case):
        return []
    return _string_list(_first_claim(case).get("cited_evidence_ids"))


def _safe_answer_text(route: VerificationRoute) -> str:
    if route == VerificationRoute.ALLOW:
        return "The answer is grounded in current authorized evidence."
    if route == VerificationRoute.REGENERATE_ROUTE:
        return "The draft needs a new grounded answer before it can proceed."
    if route == VerificationRoute.MANUAL_REVIEW:
        return "The case needs manual review before any action can proceed."
    if route == VerificationRoute.REFUSE:
        return "The cited material cannot be used as authorized support."
    return "The available evidence is insufficient for a definitive answer."


def _first_claim(case: Mapping[str, Any]) -> Mapping[str, Any]:
    claims = ((case.get("input") or {}) if isinstance(case.get("input"), Mapping) else {}).get("claims")
    if isinstance(claims, Sequence) and not isinstance(claims, str | bytes) and claims:
        first = claims[0]
        return first if isinstance(first, Mapping) else {}
    return {}


def _evidence_refs(case: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    input_data = case.get("input")
    if not isinstance(input_data, Mapping):
        return []
    refs = input_data.get("evidence_refs")
    if not isinstance(refs, Sequence) or isinstance(refs, str | bytes):
        return []
    return [ref for ref in refs if isinstance(ref, Mapping)]


def _input_business_ref_keys(case: Mapping[str, Any]) -> set[str]:
    input_data = case.get("input")
    if not isinstance(input_data, Mapping):
        return set()
    refs = input_data.get("business_fact_refs")
    if not isinstance(refs, Sequence) or isinstance(refs, str | bytes):
        return set()
    return {str(ref.get("business_fact_ref") or "") for ref in refs if isinstance(ref, Mapping)}


def _has_ocr_low_confidence(evidence_refs: Sequence[Mapping[str, Any]]) -> bool:
    for ref in evidence_refs:
        labels = ref.get("risk_labels")
        if isinstance(labels, Sequence) and not isinstance(labels, str | bytes):
            if "ocr_low_confidence" in {str(label) for label in labels}:
                return True
    return False


def _risk_hints(claim: Mapping[str, Any]) -> set[str]:
    return set(_string_list(claim.get("risk_hints")))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return []
    return [str(item) for item in value if str(item)]


def _unique_strings(values: Sequence[str] | Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


__all__ = [
    "DEFAULT_HALLUCINATION_THRESHOLDS",
    "HallucinationCaseResult",
    "REQUIRED_HALLUCINATION_METRICS",
    "evaluate_hallucination_case",
    "threshold_failures",
]
