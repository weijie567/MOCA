"""Canonical knowledge contracts.

Spec Consistency Finding: ``policy_version`` is ``v{PolicyDocument.version}``
and evidence identity uses the ``@v3`` form, rather than the date-like
``policy_version`` shown in the EvidenceRefV1 JSON example. Effective dates
are reserved for effective-time filtering and do not determine identity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.knowledge.text_hash import evidence_text_hash


class KnowledgeContext(BaseModel):
    """TrustedContext projection fields plus run-derived effective_at."""

    tenant_id: str
    user_id: str
    role: str
    merchant_scope: list[str] | None = None
    run_id: str
    trace_id: str
    locale: str | None = None
    effective_at: str


class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)

    @classmethod
    def build(
        cls,
        *,
        tenant_id: str,
        doc_key: str,
        chunk_id: str,
        policy_version: str,
        text: str,
        retrieved_at: str,
        retrieval_config_version: str,
        score: float | None = None,
        rank: int | None = None,
    ) -> EvidenceRefV1:
        return cls(
            tenant_id=tenant_id,
            evidence_id=f"{doc_key}/{chunk_id}@{policy_version}",
            doc_key=doc_key,
            chunk_id=chunk_id,
            policy_version=policy_version,
            text_hash=evidence_text_hash(text),
            retrieved_at=retrieved_at,
            retrieval_config_version=retrieval_config_version,
            score=score,
            rank=rank,
        )


RAG_CONTEXT_STATUSES = (
    "not_required",
    "verified",
    "partial",
    "no_evidence",
    "unauthorized",
    "stale",
    "conflict",
    "invalid_hash",
    "invalid_scope",
    "build_error",
)
CLAIM_TYPES = ("policy", "business_fact", "action_recommendation")
CLAIM_SUPPORT_STATUSES = ("supported", "unsupported", "partial", "ambiguous", "not_applicable", "error")
SEMANTIC_REVIEW_STATUSES = ("not_needed", "passed", "failed", "ambiguous", "timeout")
CLAIM_BUNDLE_OVERALL_STATUSES = ("verified", "blocked", "manual_review", "not_required", "error")
CLAIM_BUNDLE_ROUTES = ("continue", "final_response", "manual_review")

RagContextStatus = Literal[
    "not_required",
    "verified",
    "partial",
    "no_evidence",
    "unauthorized",
    "stale",
    "conflict",
    "invalid_hash",
    "invalid_scope",
    "build_error",
]
MaterialClaimType = Literal["policy", "business_fact", "action_recommendation"]
ClaimSupportStatus = Literal["supported", "unsupported", "partial", "ambiguous", "not_applicable", "error"]
SemanticReviewStatus = Literal["not_needed", "passed", "failed", "ambiguous", "timeout"]
ClaimBundleOverallStatus = Literal["verified", "blocked", "manual_review", "not_required", "error"]
ClaimBundleRoute = Literal["continue", "final_response", "manual_review"]


class EvidenceItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evidence_item.v1"] = "evidence_item.v1"
    ref: EvidenceRefV1
    snippet: str
    text_hash: str
    doc_version: str | None = None
    policy_version: str
    effective_date_result: Literal["valid", "expired", "not_yet_effective", "unknown"]
    tenant_scope_result: Literal["valid", "invalid", "unknown"]
    authority_level: Literal["tenant_policy", "global_policy", "sop", "faq", "unknown"]
    source_locator: dict[str, Any]
    captured_at: datetime


class VerifiedEvidencePackageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["verified_evidence_package.v1"] = "verified_evidence_package.v1"
    package_id: str
    status: RagContextStatus
    evidence_items: list[EvidenceItemV1] = Field(default_factory=list)
    citation_map: dict[str, list[str]] = Field(default_factory=dict)
    evidence_map: dict[str, EvidenceRefV1] = Field(default_factory=dict)
    prompt_projection: dict[str, Any] = Field(default_factory=dict)
    verifier_projection: dict[str, Any] = Field(default_factory=dict)
    replay_snapshot_refs: list[str] = Field(default_factory=list)
    debug_projection: dict[str, Any] = Field(default_factory=dict)
    stale_refs: list[EvidenceRefV1] = Field(default_factory=list)
    conflict_refs: list[EvidenceRefV1] = Field(default_factory=list)
    rejected_candidate_refs: list[EvidenceRefV1] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    policy_version: str
    retrieval_config_version: str


class MaterialClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["material_claim.v1"] = "material_claim.v1"
    claim_id: str
    claim_text: str
    claim_type: MaterialClaimType
    cited_evidence_ids: list[str] = Field(default_factory=list)
    business_fact_refs: list[Any] = Field(default_factory=list)
    risk_hints: list[str] = Field(default_factory=list)
    generated_from_step: str

    @field_validator("business_fact_refs", mode="before")
    @classmethod
    def _validate_business_fact_refs(cls, value: Any) -> list[Any]:
        return _coerce_business_fact_refs(value)


class ClaimVerificationResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["claim_verification_result.v1"] = "claim_verification_result.v1"
    claim_id: str
    claim_type: MaterialClaimType
    support_status: ClaimSupportStatus
    supporting_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    business_fact_refs: list[Any] = Field(default_factory=list)
    rule_checks: list[dict[str, Any]] = Field(default_factory=list)
    semantic_review_status: SemanticReviewStatus
    allows_user_visible_claim: bool
    allows_action_recommendation: bool

    @field_validator("business_fact_refs", mode="before")
    @classmethod
    def _validate_business_fact_refs(cls, value: Any) -> list[Any]:
        return _coerce_business_fact_refs(value)


class ClaimVerificationBundleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["claim_verification_bundle.v1"] = "claim_verification_bundle.v1"
    overall_status: ClaimBundleOverallStatus
    route: ClaimBundleRoute
    claim_results: list[ClaimVerificationResultV1] = Field(default_factory=list)
    blocked_claims: list[str] = Field(default_factory=list)
    safe_support_refs: list[EvidenceRefV1] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    verifier_policy_version: str


def _coerce_business_fact_refs(value: Any) -> list[Any]:
    if value is None:
        return []
    from src.tools.contracts import BusinessFactRefV1

    items = value if isinstance(value, list) else [value]
    return [item if isinstance(item, BusinessFactRefV1) else BusinessFactRefV1.model_validate(item) for item in items]


class ClaimResult(BaseModel):
    claim_id: str
    claim_text: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    is_member: bool
    missing_evidence_ids: list[str] = Field(default_factory=list)


class CitationValidationResult(BaseModel):
    validator_version: str = "citation_validator.v2"
    claim_results: list[ClaimResult] = Field(default_factory=list)
    is_valid: bool = True


class KnowledgeSearchFilters(BaseModel):
    tenant_id: str
    merchant_id: str | None = None
    policy_types: list[str] | None = None
    effective_at: str | None = None
    locale: str | None = None


class KnowledgeSearchRequest(BaseModel):
    schema_version: Literal["knowledge_search_request.v2"] = "knowledge_search_request.v2"
    query: str
    primary_intent: str | None = None
    business_context_refs: list[dict] = Field(default_factory=list)
    filters: KnowledgeSearchFilters
    retrieval_config_version: str
    rerank_config_version: str
    max_results: int = 5
    allow_partial_evidence: bool = True


class KnowledgeSearchResult(BaseModel):
    schema_version: Literal["knowledge_search_result.v2"] = "knowledge_search_result.v2"
    status: Literal["strong_evidence", "partial_evidence", "no_evidence", "error"]
    query_rewrite: str | None = None
    retrieval_config_version: str
    rerank_config_version: str
    best_score: float
    threshold: float
    evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    citation_validation: CitationValidationResult = Field(default_factory=CitationValidationResult)
    summary: str | None = None
    error: dict | None = None


def canonical_evidence_projection(refs: list[EvidenceRefV1]) -> list[dict]:
    """Strip score and deterministically sort the producer-side hash projection."""
    items = []
    for ref in refs:
        item = ref.model_dump()
        item.pop("score", None)
        items.append(item)

    all_ranked = all(item.get("rank") is not None for item in items) and len(items) > 0
    if all_ranked:
        items.sort(key=lambda item: (item["rank"], item["evidence_id"], item["text_hash"]))
    else:
        items.sort(key=lambda item: (item["evidence_id"], item["text_hash"]))
    return items
