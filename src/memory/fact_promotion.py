"""Fail-closed authority gate for Case Working Context verified facts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1

if TYPE_CHECKING:
    from src.memory.case_working_context_schemas import CaseWorkingContextVerifiedFactV1
    from src.memory.schemas import MemorySourceRefV1


FactAuthorityClass = Literal["business_fact", "policy_evidence", "contextual_only", "unknown"]
FactPromotionDecision = Literal["promote", "observe", "reject"]
FactTransportStatus = Literal[
    "success",
    "denied",
    "unavailable",
    "stale",
    "malformed",
    "partial",
    "partial_success",
    "timeout",
    "error",
    "invalid_request",
    "invalid_response",
    "not_found",
    "legacy_unresolved",
    "conflict",
]
FactCompleteness = Literal["complete", "partial", "unknown"]
FactScopeResult = Literal["valid", "invalid", "unknown"]
FactFreshnessResult = Literal["valid", "stale", "invalid", "unknown"]
FactReferenceValidation = Literal["valid", "invalid", "unknown", "compatibility_only"]
FactPromotionReason = Literal[
    "authoritative_business_fact",
    "authoritative_policy_evidence",
    "contextual_only_non_authoritative",
    "unknown_authority",
    "status_non_promotable",
    "incomplete_result",
    "missing_authoritative_ref",
    "compatibility_only_ref",
    "invalid_authoritative_ref",
    "authoritative_source_unavailable",
    "freshness_not_valid",
    "mixed_authority_refs",
]
FactPromotionInternalReason = Literal[
    "tenant_mismatch",
    "scope_mismatch",
    "unsupported_scope",
    "future_observation",
    "future_retrieval",
    "missing_freshness",
    "mixed_authority_refs",
]


class FactPromotionCandidateV1(BaseModel):
    """Typed observation submitted to the sole CWC authority gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["fact_promotion_candidate.v1"] = "fact_promotion_candidate.v1"
    tenant_id: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)
    authority_class: FactAuthorityClass
    status: FactTransportStatus
    completeness: FactCompleteness
    scope_result: FactScopeResult
    freshness_result: FactFreshnessResult
    reference_validation: FactReferenceValidation
    observed_at: datetime
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    policy_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    scope_internal_reason: FactPromotionInternalReason | None = None

    @field_validator("observed_at")
    @classmethod
    def _require_aware_observation_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class FactPromotionResultV1(BaseModel):
    """Decision result retaining typed refs and bounded internal mismatch detail."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["fact_promotion_result.v1"] = "fact_promotion_result.v1"
    decision: FactPromotionDecision
    reason_code: FactPromotionReason
    internal_reason_code: FactPromotionInternalReason | None = None
    tenant_id: str
    summary: str
    authority_class: FactAuthorityClass
    status: FactTransportStatus
    completeness: FactCompleteness
    scope_result: FactScopeResult
    freshness_result: FactFreshnessResult
    reference_validation: FactReferenceValidation
    observed_at: datetime
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    policy_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_promoted_shape(self) -> FactPromotionResultV1:
        if self.authority_class == "contextual_only" and (
            self.decision != "observe" or self.reason_code != "contextual_only_non_authoritative"
        ):
            raise ValueError("contextual_only authority must remain a contextual observation")
        if self.authority_class == "unknown" and (self.decision != "reject" or self.reason_code != "unknown_authority"):
            raise ValueError("unknown authority must remain rejected")
        if self.decision != "promote":
            if self.reason_code in {"authoritative_business_fact", "authoritative_policy_evidence"}:
                raise ValueError("authoritative promotion reasons require a promote decision")
            return self
        if self.status != "success" or self.completeness != "complete":
            raise ValueError("promoted facts require successful complete results")
        if self.scope_result != "valid" or self.freshness_result != "valid":
            raise ValueError("promoted facts require valid scope and freshness")
        if self.reference_validation != "valid":
            raise ValueError("promoted facts require validated authoritative refs")
        if self.authority_class == "business_fact":
            if not self.business_fact_refs or self.policy_evidence_refs:
                raise ValueError("business fact promotion requires only business fact refs")
        elif self.authority_class == "policy_evidence":
            if not self.policy_evidence_refs or self.business_fact_refs:
                raise ValueError("policy evidence promotion requires only policy evidence refs")
        else:
            raise ValueError("contextual or unknown authority cannot promote")
        return self

    def to_verified_fact(
        self,
        *,
        source_ref: MemorySourceRefV1 | dict[str, Any],
    ) -> CaseWorkingContextVerifiedFactV1:
        if self.decision != "promote":
            raise ValueError("only promote decisions can become verified facts")
        from src.memory.case_working_context_schemas import CaseWorkingContextVerifiedFactV1
        from src.memory.schemas import MemorySourceRefV1

        typed_source_ref = (
            source_ref if isinstance(source_ref, MemorySourceRefV1) else MemorySourceRefV1.model_validate(source_ref)
        )
        return CaseWorkingContextVerifiedFactV1(
            text=self.summary,
            authority_class=self.authority_class,
            status=self.status,
            promotion_reason_code=self.reason_code,
            source_ref=typed_source_ref,
            observed_at=self.observed_at,
            business_fact_refs=self.business_fact_refs,
            policy_evidence_refs=self.policy_evidence_refs,
        )


def promote_verified_fact(candidate: FactPromotionCandidateV1) -> FactPromotionResultV1:
    """Promote only exact authoritative source identities; every other input fails closed."""

    if candidate.authority_class == "contextual_only":
        return _result(candidate, decision="observe", reason="contextual_only_non_authoritative")
    if candidate.authority_class == "unknown":
        return _result(candidate, decision="reject", reason="unknown_authority")
    if candidate.status != "success":
        return _result(candidate, decision="observe", reason="status_non_promotable")
    if candidate.completeness != "complete":
        return _result(candidate, decision="observe", reason="incomplete_result")
    if candidate.reference_validation == "compatibility_only":
        return _result(candidate, decision="observe", reason="compatibility_only_ref")
    if candidate.scope_result != "valid":
        return _result(
            candidate,
            decision="reject",
            reason="authoritative_source_unavailable",
            internal_reason=candidate.scope_internal_reason or "scope_mismatch",
        )
    if candidate.freshness_result != "valid":
        return _result(candidate, decision="observe", reason="freshness_not_valid")
    if candidate.reference_validation != "valid":
        return _result(candidate, decision="observe", reason="invalid_authoritative_ref")

    if candidate.business_fact_refs and candidate.policy_evidence_refs:
        return _result(
            candidate,
            decision="reject",
            reason="mixed_authority_refs",
            internal_reason="mixed_authority_refs",
        )
    if candidate.authority_class == "business_fact":
        if not candidate.business_fact_refs:
            return _result(candidate, decision="observe", reason="missing_authoritative_ref")
        internal_reason = _business_ref_failure(candidate)
        if internal_reason is not None:
            return _result(
                candidate,
                decision="reject",
                reason="authoritative_source_unavailable",
                internal_reason=internal_reason,
            )
        return _result(candidate, decision="promote", reason="authoritative_business_fact")

    if not candidate.policy_evidence_refs:
        return _result(candidate, decision="observe", reason="missing_authoritative_ref")
    internal_reason = _policy_ref_failure(candidate)
    if internal_reason is not None:
        return _result(
            candidate,
            decision="reject",
            reason="authoritative_source_unavailable",
            internal_reason=internal_reason,
        )
    return _result(candidate, decision="promote", reason="authoritative_policy_evidence")


def _business_ref_failure(candidate: FactPromotionCandidateV1) -> FactPromotionInternalReason | None:
    for ref in candidate.business_fact_refs:
        if ref.tenant_id != candidate.tenant_id:
            return "tenant_mismatch"
        if ref.data_freshness_at is None:
            return "missing_freshness"
        if ref.data_freshness_at > candidate.observed_at or ref.retrieved_at > candidate.observed_at:
            return "future_observation"
    return None


def _policy_ref_failure(candidate: FactPromotionCandidateV1) -> FactPromotionInternalReason | None:
    for ref in candidate.policy_evidence_refs:
        if ref.tenant_id != candidate.tenant_id:
            return "tenant_mismatch"
        if ref.scope_type != "tenant_policy":
            return "unsupported_scope"
        if ref.scope_id != candidate.tenant_id:
            return "scope_mismatch"
        if ref.to_canonical_identity() is None:
            return "scope_mismatch"
        try:
            retrieved_at = datetime.fromisoformat(ref.retrieved_at.replace("Z", "+00:00"))
        except ValueError:
            return "future_retrieval"
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None or retrieved_at > candidate.observed_at:
            return "future_retrieval"
    return None


def _result(
    candidate: FactPromotionCandidateV1,
    *,
    decision: FactPromotionDecision,
    reason: FactPromotionReason,
    internal_reason: FactPromotionInternalReason | None = None,
) -> FactPromotionResultV1:
    return FactPromotionResultV1(
        decision=decision,
        reason_code=reason,
        internal_reason_code=internal_reason,
        **candidate.model_dump(exclude={"schema_version", "scope_internal_reason"}),
    )
