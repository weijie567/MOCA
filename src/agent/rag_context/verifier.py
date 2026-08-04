"""Material-claim verifier tiers for Phase 22."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.agent.rag_context.claims import MaterialClaim
from src.agent.rag_context.domain_rules import DomainRuleVerifier, failed_rule_reason_codes
from src.agent.rag_context.risk_labels import requires_semantic_review_for_risk_hints
from src.agent.rag_context.schemas import MaterialClaimAuthorityClass, RagContextBundle
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1, ToolResultV2

_CONTEXTUAL_MEMORY_SCHEMA_VERSIONS = frozenset(
    {
        "session_context_ref.v1",
        "reviewed_memory_ref.v1",
        "session_context_load_status.v1",
        "reviewed_memory_context_retrieve_status.v1",
        "memory_write_decision.v2",
    }
)
_CONTEXTUAL_MEMORY_REF_ID_KEYS = ("ref_id", "memory_id", "candidate_hash", "source_identity_hash")


class VerificationOutcome(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"
    UNAUTHORIZED = "unauthorized"
    BUSINESS_FACT_MISSING = "business_fact_missing"
    MANUAL_REVIEW = "manual_review"
    FAIL_CLOSED = "fail_closed"


class Level2SupportOutcome(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"
    NEEDS_SEMANTIC_REVIEW = "needs_semantic_review"


class Level1VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "level1_verification_result.v1"
    gates_run: list[str] = Field(default_factory=list)
    upstream_gates_observed: list[str] = Field(default_factory=list)
    membership_passed: bool = False
    authority_passed: bool = False
    tenant_scope_passed: bool = False
    reason_codes: list[str] = Field(default_factory=list)


class Level2VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "level2_verification_result.v1"
    outcome: Level2SupportOutcome
    reason_codes: list[str] = Field(default_factory=list)
    matched_citation_ids: list[str] = Field(default_factory=list)
    support_score: float = 0.0


class MaterialClaimVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "material_claim_verification_result.v1"
    claim_id: str
    outcome: VerificationOutcome
    reason_codes: list[str] = Field(default_factory=list)
    level1: Level1VerificationResult
    level2: Level2VerificationResult | None = None
    rule_checks: list[dict[str, Any]] = Field(default_factory=list)
    allows_claim: bool = False
    allows_action_recommendation: bool = False
    blocks_proposed_action: bool = True
    safe_support_refs: list[str] = Field(default_factory=list)
    metrics: dict[str, int | float | bool | str] = Field(default_factory=dict)


class SemanticVerificationOutcome(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"
    FAIL_CLOSED = "fail_closed"


class SemanticVerifierConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_claims_per_run: int = Field(default=6, ge=1)
    max_evidence_snippets_per_claim: int = Field(default=3, ge=1)
    max_input_chars_per_run: int = Field(default=12_000, ge=1)
    timeout_seconds: float = Field(default=15, gt=0)
    provider_retries: int = Field(default=0, ge=0)
    config_version: str = "semantic_verifier.v1"


class SemanticVerifierRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "semantic_verifier_request.v1"
    config_version: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    safe_refs: list[str] = Field(default_factory=list)
    total_input_chars: int = 0


class SemanticProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: SemanticVerificationOutcome
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)


class SemanticVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "semantic_verification_result.v1"
    outcome: SemanticVerificationOutcome
    reason_codes: list[str] = Field(default_factory=list)
    allows_claims: bool = False
    provider_retries_attempted: int = 0
    claims_checked: int = 0
    evidence_snippets_checked: int = 0
    input_chars: int = 0
    config_version: str
    safe_refs: list[str] = Field(default_factory=list)


class SemanticSupportVerifier:
    """Budgeted semantic verifier wrapper around a deterministic provider."""

    def __init__(self, *, provider: Any, config: SemanticVerifierConfig | None = None) -> None:
        self.provider = provider
        self.config = config or SemanticVerifierConfig()

    async def verify_claims(
        self,
        claims: Sequence[Mapping[str, Any]],
        *,
        context_bundle: Mapping[str, Any] | RagContextBundle,
    ) -> SemanticVerificationResult:
        context = _context_dict(context_bundle)
        budget_result = self._budget_result_if_exceeded(claims, context)
        if budget_result is not None:
            return budget_result
        request = self._request(claims, context)
        if self.provider is None or not hasattr(self.provider, "verify"):
            return self._fail_closed(
                "semantic_provider_missing",
                claims_checked=len(claims),
                evidence_snippets_checked=_evidence_snippet_count(claims),
                input_chars=request.total_input_chars,
                safe_refs=request.safe_refs,
            )
        try:
            raw_response = await asyncio.wait_for(
                self.provider.verify(request),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError:
            return self._fail_closed(
                "semantic_provider_timeout",
                claims_checked=len(claims),
                evidence_snippets_checked=_evidence_snippet_count(claims),
                input_chars=request.total_input_chars,
                safe_refs=request.safe_refs,
            )
        except Exception:
            return self._fail_closed(
                "semantic_provider_error",
                claims_checked=len(claims),
                evidence_snippets_checked=_evidence_snippet_count(claims),
                input_chars=request.total_input_chars,
                safe_refs=request.safe_refs,
            )
        try:
            parsed = SemanticProviderResponse.model_validate(raw_response)
        except (TypeError, ValueError, ValidationError):
            return self._fail_closed(
                "semantic_provider_malformed",
                claims_checked=len(claims),
                evidence_snippets_checked=_evidence_snippet_count(claims),
                input_chars=request.total_input_chars,
                safe_refs=request.safe_refs,
            )
        return SemanticVerificationResult(
            outcome=parsed.outcome,
            reason_codes=_unique(parsed.reason_codes),
            allows_claims=parsed.outcome == SemanticVerificationOutcome.SUPPORTED,
            provider_retries_attempted=0,
            claims_checked=len(claims),
            evidence_snippets_checked=_evidence_snippet_count(claims),
            input_chars=request.total_input_chars,
            config_version=self.config.config_version,
            safe_refs=request.safe_refs,
        )

    def _budget_result_if_exceeded(
        self,
        claims: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
    ) -> SemanticVerificationResult | None:
        if len(claims) > self.config.max_claims_per_run:
            return self._fail_closed("semantic_budget_claim_count_exceeded", claims_checked=len(claims))
        if any(_claim_evidence_count(claim) > self.config.max_evidence_snippets_per_claim for claim in claims):
            return self._fail_closed(
                "semantic_budget_evidence_count_exceeded",
                claims_checked=len(claims),
                evidence_snippets_checked=_evidence_snippet_count(claims),
            )
        input_chars = _semantic_input_chars(claims)
        if input_chars > self.config.max_input_chars_per_run:
            return self._fail_closed(
                "semantic_budget_input_chars_exceeded",
                claims_checked=len(claims),
                evidence_snippets_checked=_evidence_snippet_count(claims),
                input_chars=input_chars,
                safe_refs=_semantic_safe_refs(context),
            )
        return None

    def _request(self, claims: Sequence[Mapping[str, Any]], context: Mapping[str, Any]) -> SemanticVerifierRequest:
        return SemanticVerifierRequest(
            config_version=self.config.config_version,
            claims=[_redacted_semantic_claim(claim, self.config.max_evidence_snippets_per_claim) for claim in claims],
            safe_refs=_semantic_safe_refs(context),
            total_input_chars=_semantic_input_chars(claims),
        )

    def _fail_closed(
        self,
        reason_code: str,
        *,
        claims_checked: int = 0,
        evidence_snippets_checked: int = 0,
        input_chars: int = 0,
        safe_refs: Sequence[str] = (),
    ) -> SemanticVerificationResult:
        return SemanticVerificationResult(
            outcome=SemanticVerificationOutcome.FAIL_CLOSED,
            reason_codes=[reason_code],
            allows_claims=False,
            provider_retries_attempted=0,
            claims_checked=claims_checked,
            evidence_snippets_checked=evidence_snippets_checked,
            input_chars=input_chars,
            config_version=self.config.config_version,
            safe_refs=list(safe_refs),
        )


class MaterialClaimVerifier:
    """Verify claim authority and deterministic text support."""

    _LEVEL1_LOCAL_GATES = [
        "bundle_membership",
        "tenant_scope",
        "authority_compatibility",
        "business_fact_authority",
    ]
    _UPSTREAM_CANONICAL_EVIDENCE_GATES = [
        "canonical_bundle_filtering",
        "duplicate_key",
        "text_hash",
        "freshness",
        "latest_policy_version",
        "scope",
    ]

    async def verify_claim(
        self,
        claim: MaterialClaim,
        *,
        context_bundle: RagContextBundle | Mapping[str, Any],
        dependency_results: Sequence[Mapping[str, Any]] | None = None,
    ) -> MaterialClaimVerificationResult:
        context = _context_dict(context_bundle)
        level1 = self._check_level1(claim, context)
        rule_checks = self._check_domain_rules(claim, context)
        reason_codes = list(level1.reason_codes)
        hard_rule_reason_codes = failed_rule_reason_codes(rule_checks)
        reason_codes.extend(hard_rule_reason_codes)

        if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
            return self._verify_business_fact_claim(claim, context, level1, reason_codes, rule_checks)

        if claim.authority_class == MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM:
            if hard_rule_reason_codes:
                return self._result(
                    claim,
                    VerificationOutcome.UNSUPPORTED,
                    level1=level1,
                    reason_codes=reason_codes,
                    rule_checks=rule_checks,
                )
            return self._verify_action_recommendation_claim(
                claim,
                context,
                level1,
                reason_codes,
                dependency_results or [],
                rule_checks,
            )

        if not level1.authority_passed:
            outcome = (
                VerificationOutcome.UNAUTHORIZED
                if "tenant_scope_invalid" in reason_codes
                else VerificationOutcome.INSUFFICIENT
            )
            return self._result(
                claim,
                outcome,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )

        if hard_rule_reason_codes:
            return self._result(
                claim,
                VerificationOutcome.UNSUPPORTED,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )

        snippets = _claim_evidence_snippets(claim, context)
        level2 = self.check_level2_support(
            claim_text=claim.claim_text,
            evidence_snippets=snippets,
            risk_hints=[*claim.risk_hints, *_snippet_risk_labels(claim, context)],
        )
        reason_codes.extend(level2.reason_codes)
        if level2.outcome == Level2SupportOutcome.SUPPORTED:
            return self._result(
                claim,
                VerificationOutcome.SUPPORTED,
                level1=level1,
                level2=level2,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
                safe_support_refs=_safe_support_refs(claim, context),
                allows_claim=True,
            )
        if level2.outcome == Level2SupportOutcome.INSUFFICIENT:
            outcome = VerificationOutcome.INSUFFICIENT
        elif level2.outcome == Level2SupportOutcome.AMBIGUOUS:
            outcome = VerificationOutcome.AMBIGUOUS
        else:
            outcome = VerificationOutcome.UNSUPPORTED
        return self._result(
            claim,
            outcome,
            level1=level1,
            level2=level2,
            reason_codes=reason_codes,
            rule_checks=rule_checks,
        )

    def check_level2_support(
        self,
        *,
        claim_text: str,
        evidence_snippets: Sequence[Mapping[str, Any]],
        risk_hints: Sequence[str] | None = None,
    ) -> Level2VerificationResult:
        if requires_semantic_review_for_risk_hints(risk_hints or []):
            return Level2VerificationResult(
                outcome=Level2SupportOutcome.NEEDS_SEMANTIC_REVIEW,
                reason_codes=["level2_semantic_trigger_hint"],
            )

        texts = [
            str(snippet.get("text") or "") for snippet in evidence_snippets if str(snippet.get("text") or "").strip()
        ]
        if not texts:
            return Level2VerificationResult(
                outcome=Level2SupportOutcome.INSUFFICIENT,
                reason_codes=["evidence_text_required"],
            )

        normalized_claim = _normalize_text(claim_text)
        normalized_evidence = _normalize_text("\n".join(texts))
        if normalized_claim and normalized_claim in normalized_evidence:
            return Level2VerificationResult(
                outcome=Level2SupportOutcome.SUPPORTED,
                reason_codes=["lexical_span_supported"],
                matched_citation_ids=_citation_ids(evidence_snippets),
                support_score=1.0,
            )

        claim_tokens = _meaningful_tokens(claim_text)
        evidence_tokens = _meaningful_tokens("\n".join(texts))
        if not claim_tokens or not evidence_tokens:
            return Level2VerificationResult(
                outcome=Level2SupportOutcome.INSUFFICIENT,
                reason_codes=["insufficient_normalized_text"],
            )

        overlap = len(claim_tokens & evidence_tokens) / max(len(claim_tokens), 1)
        if overlap >= 0.85:
            return Level2VerificationResult(
                outcome=Level2SupportOutcome.SUPPORTED,
                reason_codes=["lexical_token_supported"],
                matched_citation_ids=_citation_ids(evidence_snippets),
                support_score=round(overlap, 3),
            )
        if overlap >= 0.25:
            return Level2VerificationResult(
                outcome=Level2SupportOutcome.AMBIGUOUS,
                reason_codes=["level2_partial_overlap_ambiguous"],
                matched_citation_ids=_citation_ids(evidence_snippets),
                support_score=round(overlap, 3),
            )
        return Level2VerificationResult(
            outcome=Level2SupportOutcome.UNSUPPORTED,
            reason_codes=["citation_membership_not_support"],
            support_score=round(overlap, 3),
        )

    def _check_level1(self, claim: MaterialClaim, context: Mapping[str, Any]) -> Level1VerificationResult:
        reason_codes: list[str] = []
        trusted_tenant = str(_trusted_context(context).get("tenant_id") or "")
        cited_refs = _cited_evidence_refs(claim, context)
        membership_passed = bool(claim.cited_evidence_ids) and set(claim.cited_evidence_ids).issubset(
            set(_active_source_evidence_ids(context))
        )

        if claim.authority_class in {
            MaterialClaimAuthorityClass.POLICY_CLAIM,
            MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM,
        }:
            if not membership_passed:
                reason_codes.append("policy_evidence_required")
            if any(ref.tenant_id != trusted_tenant for ref in cited_refs):
                reason_codes.append("tenant_scope_invalid")
        if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
            if claim.cited_evidence_ids:
                reason_codes.append("policy_evidence_not_business_authority")
        if claim.authority_class in {
            MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM,
            MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM,
        }:
            if not trusted_tenant:
                reason_codes.append("tenant_scope_invalid")
            elif any(ref.tenant_id != trusted_tenant for ref in claim.business_fact_refs):
                reason_codes.append("tenant_scope_invalid")

        reason_codes.extend(_contextual_source_reason_codes(claim.authority_class, context))
        business_authority = _business_authority_passed(claim, context)
        if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM and not business_authority:
            reason_codes.append("business_fact_ref_required")

        if claim.authority_class == MaterialClaimAuthorityClass.POLICY_CLAIM:
            authority_passed = membership_passed and "tenant_scope_invalid" not in reason_codes
        elif claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
            authority_passed = business_authority and "policy_evidence_not_business_authority" not in reason_codes
        else:
            authority_passed = "tenant_scope_invalid" not in reason_codes

        return Level1VerificationResult(
            gates_run=list(self._LEVEL1_LOCAL_GATES),
            upstream_gates_observed=list(self._UPSTREAM_CANONICAL_EVIDENCE_GATES),
            membership_passed=membership_passed,
            authority_passed=authority_passed,
            tenant_scope_passed="tenant_scope_invalid" not in reason_codes,
            reason_codes=_unique(reason_codes),
        )

    def _verify_business_fact_claim(
        self,
        claim: MaterialClaim,
        context: Mapping[str, Any],
        level1: Level1VerificationResult,
        reason_codes: list[str],
        rule_checks: list[dict[str, Any]],
    ) -> MaterialClaimVerificationResult:
        if not _business_authority_passed(claim, context):
            if "business_fact_ref_required" not in reason_codes:
                reason_codes.append("business_fact_ref_required")
            return self._result(
                claim,
                VerificationOutcome.BUSINESS_FACT_MISSING,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )
        return self._result(
            claim,
            VerificationOutcome.SUPPORTED,
            level1=level1,
            reason_codes=reason_codes,
            rule_checks=rule_checks,
            safe_support_refs=[_business_ref_key(ref) for ref in claim.business_fact_refs],
            allows_claim=True,
        )

    def _verify_action_recommendation_claim(
        self,
        claim: MaterialClaim,
        context: Mapping[str, Any],
        level1: Level1VerificationResult,
        reason_codes: list[str],
        dependency_results: Sequence[Mapping[str, Any]],
        rule_checks: list[dict[str, Any]],
    ) -> MaterialClaimVerificationResult:
        dependency_reason_codes = _action_dependency_reason_codes(claim, dependency_results)
        reason_codes.extend(dependency_reason_codes)
        if not level1.tenant_scope_passed or "tenant_scope_invalid" in reason_codes:
            if not _business_authority_passed(claim, context) and "business_fact_ref_required" not in reason_codes:
                reason_codes.append("business_fact_ref_required")
            return self._result(
                claim,
                VerificationOutcome.UNAUTHORIZED,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )
        if not level1.membership_passed:
            if "policy_evidence_required" not in reason_codes:
                reason_codes.append("policy_evidence_required")
            return self._result(
                claim,
                VerificationOutcome.INSUFFICIENT,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )
        if dependency_reason_codes:
            return self._result(
                claim,
                VerificationOutcome.UNSUPPORTED,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )
        if not _business_authority_passed(claim, context):
            reason_codes.append("business_fact_ref_required")
            return self._result(
                claim,
                VerificationOutcome.BUSINESS_FACT_MISSING,
                level1=level1,
                reason_codes=reason_codes,
                rule_checks=rule_checks,
            )
        return self._result(
            claim,
            VerificationOutcome.SUPPORTED,
            level1=level1,
            reason_codes=reason_codes,
            rule_checks=rule_checks,
            safe_support_refs=[
                *_safe_support_refs(claim, context),
                *[_business_ref_key(ref) for ref in claim.business_fact_refs],
            ],
            allows_claim=True,
            allows_action_recommendation=True,
            blocks_proposed_action=False,
        )

    def _result(
        self,
        claim: MaterialClaim,
        outcome: VerificationOutcome,
        *,
        level1: Level1VerificationResult,
        reason_codes: Sequence[str],
        level2: Level2VerificationResult | None = None,
        rule_checks: Sequence[Mapping[str, Any]] = (),
        safe_support_refs: Sequence[str] = (),
        allows_claim: bool = False,
        allows_action_recommendation: bool = False,
        blocks_proposed_action: bool = True,
    ) -> MaterialClaimVerificationResult:
        return MaterialClaimVerificationResult(
            claim_id=claim.claim_id,
            outcome=outcome,
            reason_codes=_unique(reason_codes),
            level1=level1,
            level2=level2,
            rule_checks=[dict(check) for check in rule_checks],
            allows_claim=allows_claim and outcome == VerificationOutcome.SUPPORTED,
            allows_action_recommendation=allows_action_recommendation and outcome == VerificationOutcome.SUPPORTED,
            blocks_proposed_action=blocks_proposed_action or outcome != VerificationOutcome.SUPPORTED,
            safe_support_refs=list(dict.fromkeys(str(ref) for ref in safe_support_refs if str(ref))),
            metrics={
                "level1_ran": True,
                "level2_ran": level2 is not None,
                "reason_count": len(_unique(reason_codes)),
            },
        )

    def _check_domain_rules(self, claim: MaterialClaim, context: Mapping[str, Any]) -> list[dict[str, Any]]:
        return DomainRuleVerifier().verify(
            claim_text=claim.claim_text,
            evidence_snippets=_claim_evidence_snippets(claim, context),
            claim_metadata=_claim_domain_rule_metadata(claim, context),
        )


def _context_dict(context_bundle: RagContextBundle | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(context_bundle, RagContextBundle):
        return context_bundle.model_dump(mode="python")
    return context_bundle


def _trusted_context(context: Mapping[str, Any]) -> Mapping[str, Any]:
    value = context.get("trusted_context")
    return value if isinstance(value, Mapping) else {}


def _verifier_context(context: Mapping[str, Any]) -> Mapping[str, Any]:
    value = context.get("verifier_context")
    return value if isinstance(value, Mapping) else {}


def _claim_domain_rule_metadata(claim: MaterialClaim, context: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = _verifier_context(context).get("domain_rule_metadata")
    if not isinstance(metadata, Mapping):
        return {}
    claim_specific = metadata.get(claim.claim_id)
    if isinstance(claim_specific, Mapping):
        return claim_specific
    return metadata


def _citation_entries(context: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    citation_map = context.get("citation_map")
    if isinstance(citation_map, Mapping):
        return [entry for entry in citation_map.values() if isinstance(entry, Mapping)]
    return []


def _entry_is_contextual_memory(entry: Mapping[str, Any]) -> bool:
    evidence_ref = entry.get("evidence_ref")
    return isinstance(evidence_ref, Mapping) and _is_contextual_memory_ref_or_status(evidence_ref)


def _contextual_memory_authority_ids(context: Mapping[str, Any]) -> list[str]:
    ref_ids = set(_contextual_memory_ref_ids(context))
    for entry in _citation_entries(context):
        if not _entry_is_contextual_memory(entry):
            continue
        ref_ids.update(str(value) for value in entry.get("source_evidence_ids") or [] if str(value))
        citation_id = str(entry.get("citation_id") or "")
        if citation_id:
            ref_ids.add(citation_id)
        evidence_ref = entry.get("evidence_ref")
        if isinstance(evidence_ref, Mapping):
            for key in (*_CONTEXTUAL_MEMORY_REF_ID_KEYS, "evidence_id", "citation_id"):
                raw = evidence_ref.get(key)
                if raw:
                    ref_ids.add(str(raw))
    return _unique(ref_ids)


def _active_source_evidence_ids(context: Mapping[str, Any]) -> list[str]:
    evidence_ids: list[str] = []
    contextual_memory_ref_ids = set(_contextual_memory_authority_ids(context))
    for entry in _citation_entries(context):
        if _entry_is_contextual_memory(entry):
            continue
        evidence_ids.extend(str(value) for value in entry.get("source_evidence_ids") or [] if str(value))
        evidence_ref = entry.get("evidence_ref")
        if isinstance(evidence_ref, Mapping) and evidence_ref.get("evidence_id"):
            evidence_ids.append(str(evidence_ref["evidence_id"]))
    safe_refs = _verifier_context(context).get("safe_refs")
    if isinstance(safe_refs, list):
        evidence_ids.extend(str(value) for value in safe_refs if str(value))
    return _unique(ref for ref in evidence_ids if ref not in contextual_memory_ref_ids)


def _cited_evidence_refs(claim: MaterialClaim, context: Mapping[str, Any]) -> list[EvidenceRefV1]:
    refs: list[EvidenceRefV1] = []
    cited = set(claim.cited_evidence_ids)
    for entry in _citation_entries(context):
        source_ids = {str(value) for value in entry.get("source_evidence_ids") or []}
        evidence_ref = entry.get("evidence_ref")
        if not isinstance(evidence_ref, Mapping):
            continue
        if _is_contextual_memory_ref_or_status(evidence_ref):
            continue
        if cited & (source_ids | {str(evidence_ref.get("evidence_id") or "")}):
            try:
                refs.append(EvidenceRefV1(**evidence_ref))
            except Exception:
                continue
    return refs


def _claim_evidence_snippets(claim: MaterialClaim, context: Mapping[str, Any]) -> list[dict[str, Any]]:
    cited = set(claim.cited_evidence_ids)
    contextual_memory_ref_ids = set(_contextual_memory_authority_ids(context))
    snippets: list[dict[str, Any]] = []
    raw_snippets = _verifier_context(context).get("evidence_snippets")
    if isinstance(raw_snippets, list):
        for snippet in raw_snippets:
            if not isinstance(snippet, Mapping):
                continue
            snippet_ids = {str(snippet.get("evidence_id") or ""), str(snippet.get("citation_id") or "")}
            if snippet_ids & contextual_memory_ref_ids:
                continue
            if snippet_ids & cited:
                snippets.append(dict(snippet))
    if snippets:
        return snippets
    for entry in _citation_entries(context):
        if _entry_is_contextual_memory(entry):
            continue
        source_ids = {str(value) for value in entry.get("source_evidence_ids") or []}
        safe_source_ids = source_ids - contextual_memory_ref_ids
        matching_ids = cited & safe_source_ids
        if matching_ids:
            snippets.append(
                {
                    "citation_id": str(entry.get("citation_id") or ""),
                    "evidence_id": next(iter(matching_ids), ""),
                    "text": str(entry.get("snippet") or ""),
                }
            )
    return snippets


def _snippet_risk_labels(claim: MaterialClaim, context: Mapping[str, Any]) -> list[str]:
    cited = set(claim.cited_evidence_ids)
    labels: list[str] = []
    for entry in _citation_entries(context):
        if cited & {str(value) for value in entry.get("source_evidence_ids") or []}:
            labels.extend(str(label) for label in entry.get("risk_labels") or [] if str(label))
    return _unique(labels)


def _safe_support_refs(claim: MaterialClaim, context: Mapping[str, Any]) -> list[str]:
    return [ref for ref in _active_source_evidence_ids(context) if ref in set(claim.cited_evidence_ids)]


def _business_authority_passed(claim: MaterialClaim, context: Mapping[str, Any]) -> bool:
    trusted_tenant = str(_trusted_context(context).get("tenant_id") or "")
    if not trusted_tenant:
        return False
    if not claim.business_fact_refs:
        return False
    if any(ref.tenant_id != trusted_tenant for ref in claim.business_fact_refs):
        return False
    context_refs = [ref for ref in _context_business_refs(context) if ref.tenant_id == trusted_tenant]
    context_keys = {_business_ref_key(ref) for ref in context_refs}
    return all(_business_ref_key(ref) in context_keys for ref in claim.business_fact_refs)


def _context_business_refs(context: Mapping[str, Any]) -> list[BusinessFactRefV1]:
    raw_refs = _verifier_context(context).get("business_fact_refs")
    refs: list[BusinessFactRefV1] = []
    if isinstance(raw_refs, list):
        for item in raw_refs:
            if isinstance(item, Mapping) and _is_contextual_memory_ref_or_status(item):
                continue
            try:
                refs.append(BusinessFactRefV1(**item))
            except Exception:
                continue
    for item in _raw_tool_results(context):
        try:
            result = ToolResultV2.model_validate(item)
        except Exception:
            continue
        if result.status in {"success", "partial_success"}:
            refs.extend(result.business_fact_refs)
    return refs


def _raw_tool_results(context: Mapping[str, Any]) -> list[Any]:
    candidates: list[Any] = []
    verifier_tool_results = _verifier_context(context).get("tool_results")
    if isinstance(verifier_tool_results, list):
        candidates.extend(verifier_tool_results)
    top_level_tool_results = context.get("tool_results")
    if isinstance(top_level_tool_results, list):
        candidates.extend(top_level_tool_results)
    business_context = context.get("business_context")
    if isinstance(business_context, Mapping) and isinstance(business_context.get("tool_results"), list):
        candidates.extend(business_context["tool_results"])
    return candidates


def _business_ref_key(ref: BusinessFactRefV1) -> str:
    return f"{ref.tenant_id}:{ref.source_system}:{ref.resource_type}:{ref.resource_id}:{ref.resource_version or ''}"


def _contextual_source_reason_codes(
    authority_class: MaterialClaimAuthorityClass,
    context: Mapping[str, Any],
) -> list[str]:
    contextual = context.get("contextual_sources")
    contextual = contextual if isinstance(contextual, Mapping) else {}
    reason_codes: list[str] = []
    has_contextual_memory_ref = _has_contextual_memory_ref_or_status(contextual) or any(
        _entry_is_contextual_memory(entry) for entry in _citation_entries(context)
    )
    has_memory = bool(
        contextual.get("session_memory")
        or contextual.get("case_memory")
        or contextual.get("prior_summaries")
        or contextual.get("session_context_refs")
        or contextual.get("reviewed_memory_refs")
        or contextual.get("memory_status_refs")
    )
    has_model = bool(contextual.get("model_knowledge"))
    has_provenance = bool(
        contextual.get("source_provenance") or contextual.get("parser_ocr") or contextual.get("provenance")
    )
    has_prompt_summary = bool(
        contextual.get("prompt_summaries")
        or contextual.get("prompt_summary")
        or contextual.get("tool_prompt_summaries")
    )
    has_raw_repository_rows = bool(
        contextual.get("raw_repository_rows") or contextual.get("repository_rows") or contextual.get("raw_rows")
    )
    if authority_class == MaterialClaimAuthorityClass.POLICY_CLAIM:
        if has_memory:
            reason_codes.append("memory_not_policy_authority")
        if has_contextual_memory_ref:
            reason_codes.append("memory_contextual_ref_not_policy_authority")
        if has_model:
            reason_codes.append("model_knowledge_not_policy_authority")
    if authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
        if has_memory:
            reason_codes.append("memory_not_business_authority")
        if has_contextual_memory_ref:
            reason_codes.append("memory_contextual_ref_not_business_authority")
        if has_model:
            reason_codes.append("model_knowledge_not_business_authority")
        if has_provenance:
            reason_codes.append("provenance_not_business_authority")
        if has_prompt_summary:
            reason_codes.append("prompt_summary_not_business_authority")
        if has_raw_repository_rows:
            reason_codes.append("raw_repository_row_not_business_authority")
    return reason_codes


def _has_contextual_memory_ref_or_status(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _is_contextual_memory_ref_or_status(value):
            return True
        return any(_has_contextual_memory_ref_or_status(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_has_contextual_memory_ref_or_status(item) for item in value)
    return False


def _is_contextual_memory_ref_or_status(value: Mapping[str, Any]) -> bool:
    schema_version = str(value.get("schema_version") or "")
    authority_class = str(value.get("authority_class") or "")
    return authority_class == "contextual_only" or schema_version in _CONTEXTUAL_MEMORY_SCHEMA_VERSIONS


def _contextual_memory_ref_ids(context: Mapping[str, Any]) -> list[str]:
    contextual = context.get("contextual_sources")
    if not isinstance(contextual, Mapping):
        return []
    ref_ids: list[str] = []
    _collect_contextual_memory_ref_ids(contextual, ref_ids)
    return _unique(ref_ids)


def _collect_contextual_memory_ref_ids(value: Any, ref_ids: list[str]) -> None:
    if isinstance(value, Mapping):
        if _is_contextual_memory_ref_or_status(value):
            for key in _CONTEXTUAL_MEMORY_REF_ID_KEYS:
                raw = value.get(key)
                if raw:
                    ref_ids.append(str(raw))
        for item in value.values():
            _collect_contextual_memory_ref_ids(item, ref_ids)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _collect_contextual_memory_ref_ids(item, ref_ids)


def _action_dependency_reason_codes(
    claim: MaterialClaim,
    dependency_results: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not claim.dependency_claim_ids:
        return ["dependency_claims_required"]
    dependencies = {
        str(item.get("claim_id")): {
            "claim_type": str(item.get("claim_type") or ""),
            "outcome": str(item.get("outcome") or ""),
        }
        for item in dependency_results
        if item.get("claim_id")
    }
    if not dependencies:
        return ["dependency_results_required"]
    reason_codes: list[str] = []
    for dependency_id in claim.dependency_claim_ids:
        dependency = dependencies.get(str(dependency_id))
        if dependency is None:
            reason_codes.append("dependency_result_missing")
            continue
        outcome = dependency["outcome"]
        role = _action_dependency_role(str(dependency_id), dependency["claim_type"])
        if role == "policy":
            if outcome != VerificationOutcome.SUPPORTED.value:
                if outcome in {"supported_by_memory", "supported_by_model_knowledge"}:
                    reason_codes.append("policy_dependency_not_evidence_supported")
                else:
                    reason_codes.append("unsupported_policy_dependency")
        elif role == "business":
            if outcome != VerificationOutcome.SUPPORTED.value:
                if outcome in {"supported_by_memory", "supported_by_model_knowledge"}:
                    reason_codes.append("business_dependency_not_tool_supported")
                else:
                    reason_codes.append("unsupported_business_dependency")
        elif outcome != VerificationOutcome.SUPPORTED.value:
            reason_codes.append("unsupported_dependency")
    required_roles = set()
    for dependency_id in claim.dependency_claim_ids:
        dependency = dependencies.get(str(dependency_id))
        if dependency is None:
            continue
        role = _action_dependency_role(str(dependency_id), dependency["claim_type"])
        if role in {"policy", "business"}:
            required_roles.add(role)
    if "policy" not in required_roles:
        reason_codes.append("policy_dependency_required")
    if "business" not in required_roles:
        reason_codes.append("business_dependency_required")
    return _unique(reason_codes)


def _action_dependency_role(dependency_id: str, claim_type: str) -> str | None:
    if claim_type == "policy":
        return "policy"
    if claim_type == "business_fact":
        return "business"
    if claim_type:
        return None
    lowered = dependency_id.lower()
    if "policy" in lowered:
        return "policy"
    if "business" in lowered:
        return "business"
    return None


def _citation_ids(snippets: Sequence[Mapping[str, Any]]) -> list[str]:
    return _unique(
        str(snippet.get("citation_id") or "") for snippet in snippets if str(snippet.get("citation_id") or "")
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _meaningful_tokens(value: str) -> set[str]:
    ascii_tokens = set(re.findall(r"[a-z0-9]+", value.casefold()))
    cjk_tokens = {char for char in value if "\u4e00" <= char <= "\u9fff"}
    return {token for token in ascii_tokens if token not in _STOPWORDS} | cjk_tokens


def _unique(values: Sequence[str] | Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "before",
    "by",
    "for",
    "in",
    "is",
    "it",
    "of",
    "or",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def should_run_level3_semantic_verification(case: Mapping[str, Any]) -> bool:
    authority_class = str(case.get("authority_class") or "")
    risk_level = str(case.get("risk_level") or "").casefold()
    risk_hints = [str(hint) for hint in case.get("risk_hints") or []]
    level2_outcome = str(case.get("level2_outcome") or "")
    if authority_class == MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM.value:
        return True
    if risk_level in {"high", "critical"}:
        return True
    if level2_outcome in {
        Level2SupportOutcome.AMBIGUOUS.value,
        Level2SupportOutcome.NEEDS_SEMANTIC_REVIEW.value,
    }:
        return True
    return requires_semantic_review_for_risk_hints(risk_hints)


def _redacted_semantic_claim(claim: Mapping[str, Any], max_evidence: int) -> dict[str, Any]:
    snippets = [
        {
            "citation_id": str(snippet.get("citation_id") or ""),
            "evidence_id": str(snippet.get("evidence_id") or ""),
            "text": _bounded_semantic_text(str(snippet.get("text") or "")),
        }
        for snippet in list(claim.get("evidence_snippets") or [])[:max_evidence]
        if isinstance(snippet, Mapping)
    ]
    return {
        "claim_id": str(claim.get("claim_id") or ""),
        "claim_text": _bounded_semantic_text(str(claim.get("claim_text") or "")),
        "authority_class": str(claim.get("authority_class") or ""),
        "risk_level": str(claim.get("risk_level") or ""),
        "risk_hints": [str(hint) for hint in claim.get("risk_hints") or [] if str(hint)],
        "level2_outcome": str(claim.get("level2_outcome") or ""),
        "evidence_snippets": snippets,
    }


def _bounded_semantic_text(value: str, limit: int = 1_500) -> str:
    safe = " ".join(value.split())
    if len(safe) <= limit:
        return safe
    return safe[: limit - 12].rstrip() + " [truncated]"


def _claim_evidence_count(claim: Mapping[str, Any]) -> int:
    snippets = claim.get("evidence_snippets")
    return len(snippets) if isinstance(snippets, list) else 0


def _evidence_snippet_count(claims: Sequence[Mapping[str, Any]]) -> int:
    return sum(_claim_evidence_count(claim) for claim in claims)


def _semantic_input_chars(claims: Sequence[Mapping[str, Any]]) -> int:
    total = 0
    for claim in claims:
        total += len(str(claim.get("claim_text") or ""))
        snippets = claim.get("evidence_snippets")
        if isinstance(snippets, list):
            total += sum(len(str(snippet.get("text") or "")) for snippet in snippets if isinstance(snippet, Mapping))
    return total


def _semantic_safe_refs(context: Mapping[str, Any]) -> list[str]:
    safe_refs = _verifier_context(context).get("safe_refs")
    if isinstance(safe_refs, list):
        return _unique(str(ref) for ref in safe_refs if str(ref))
    return []


__all__ = [
    "Level1VerificationResult",
    "Level2SupportOutcome",
    "Level2VerificationResult",
    "MaterialClaimVerificationResult",
    "MaterialClaimVerifier",
    "SemanticSupportVerifier",
    "SemanticVerificationOutcome",
    "SemanticVerificationResult",
    "SemanticVerifierConfig",
    "SemanticVerifierRequest",
    "VerificationOutcome",
    "should_run_level3_semantic_verification",
]
