from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.knowledge.schemas import EvidenceRefV1
from src.memory.fact_promotion import (
    FactAuthorityClass,
    FactCompleteness,
    FactFreshnessResult,
    FactPromotionDecision,
    FactPromotionInternalReason,
    FactPromotionReason,
    FactReferenceValidation,
    FactScopeResult,
    FactTransportStatus,
)
from src.memory.schemas import MemorySourceRefV1
from src.tools.contracts import BusinessFactRefV1

# Compatibility import name only; there is no second/reduced policy-ref model.
CaseWorkingContextPolicyRefV1 = EvidenceRefV1


class CaseWorkingContextClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    verified: bool
    source_ref: MemorySourceRefV1


class CaseWorkingContextVerifiedFactV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    authority_class: Literal["business_fact", "policy_evidence"]
    status: Literal["success"]
    promotion_reason_code: Literal["authoritative_business_fact", "authoritative_policy_evidence"]
    source_ref: MemorySourceRefV1
    observed_at: datetime
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    policy_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_exact_authoritative_refs(self) -> CaseWorkingContextVerifiedFactV1:
        if self.authority_class == "business_fact":
            if self.promotion_reason_code != "authoritative_business_fact":
                raise ValueError("business facts require the business promotion reason")
            if not self.business_fact_refs or self.policy_evidence_refs:
                raise ValueError("business facts require only typed business refs")
            return self
        if self.promotion_reason_code != "authoritative_policy_evidence":
            raise ValueError("policy evidence requires the policy promotion reason")
        if not self.policy_evidence_refs or self.business_fact_refs:
            raise ValueError("policy evidence requires only canonical policy refs")
        if any(ref.to_canonical_identity() is None for ref in self.policy_evidence_refs):
            raise ValueError("policy evidence facts require complete canonical refs")
        return self


class CaseWorkingContextObservationV1(BaseModel):
    """Non-authoritative CWC observation stored in the legacy evidence-pointer JSON slot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["case_working_context_observation.v1"] = "case_working_context_observation.v1"
    summary: str = Field(min_length=1, max_length=500)
    decision: FactPromotionDecision
    authority_class: FactAuthorityClass
    status: FactTransportStatus
    reason_code: FactPromotionReason
    internal_reason_code: FactPromotionInternalReason | None = None
    completeness: FactCompleteness
    scope_result: FactScopeResult
    freshness_result: FactFreshnessResult
    reference_validation: FactReferenceValidation
    source_ref: MemorySourceRefV1
    observed_at: datetime
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    policy_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def _forbid_promoted_observations(self) -> CaseWorkingContextObservationV1:
        if self.decision == "promote":
            raise ValueError("promoted results belong in verified_facts")
        return self


class CaseWorkingContextActionTakenV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    source_ref: MemorySourceRefV1


class CaseWorkingContextCommitmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    confirmed_by_staff: bool
    source_ref: MemorySourceRefV1


class CaseWorkingContextEvidencePointerV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_type: Literal["tool_result", "conversation_message", "business_fact_summary"]
    ref_id: str
    summary: str | None = None
    observed_at: datetime | None = None


class CaseWorkingContextRecommendationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_step: str
    staff_decision: str | None = None


class CaseWorkingContextNextActionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_step: str | None = None
    blocked_by: list[str] = Field(default_factory=list)


class CaseWorkingContextContentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_class: Literal["contextual_only"] = "contextual_only"
    customer_request: str | None = None
    issue_type: str | None = None
    claims: list[CaseWorkingContextClaimV1] = Field(default_factory=list)
    verified_facts: list[CaseWorkingContextVerifiedFactV1] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    evidence_refs: list[CaseWorkingContextObservationV1 | CaseWorkingContextEvidencePointerV1] = Field(
        default_factory=list
    )
    actions_taken: list[CaseWorkingContextActionTakenV1] = Field(default_factory=list)
    policy_refs: list[EvidenceRefV1] = Field(default_factory=list)
    agent_recommendations: list[CaseWorkingContextRecommendationV1] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    commitments: list[CaseWorkingContextCommitmentV1] = Field(default_factory=list)
    next_action: CaseWorkingContextNextActionV1 = Field(default_factory=CaseWorkingContextNextActionV1)

    @property
    def observations(self) -> list[CaseWorkingContextObservationV1]:
        """Typed observations persisted through the pre-existing evidence_refs_json column."""

        return [item for item in self.evidence_refs if isinstance(item, CaseWorkingContextObservationV1)]

    @model_validator(mode="after")
    def _require_canonical_policy_refs(self) -> CaseWorkingContextContentV1:
        if any(ref.to_canonical_identity() is None for ref in self.policy_refs):
            raise ValueError("CWC policy_refs require complete canonical EvidenceRefV1 values")
        return self


class CaseWorkingContextWriteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    case_id: uuid.UUID
    updated_by_run_id: uuid.UUID | None = None
    source_ref: MemorySourceRefV1
    expected_version: int | None = None
    content: CaseWorkingContextContentV1
    pii_classification: Literal["none", "low", "sensitive", "prohibited"] = "none"


def normalize_case_working_context_source_ref(
    source_ref: MemorySourceRefV1,
    *,
    run_id: uuid.UUID | None,
    case_id: uuid.UUID,
) -> MemorySourceRefV1:
    payload = source_ref.model_dump(mode="json", exclude_none=True)
    if run_id is not None:
        payload["run_id"] = str(run_id)
        payload["agent_run_id"] = str(run_id)
    payload["business_object_type"] = "refund_case"
    payload["business_object_id"] = str(case_id)
    return MemorySourceRefV1.model_validate(payload)


def normalize_case_working_context_content_sources(
    content: CaseWorkingContextContentV1,
    *,
    run_id: uuid.UUID | None,
    case_id: uuid.UUID,
) -> CaseWorkingContextContentV1:
    return content.model_copy(
        update={
            "claims": [_with_normalized_source_ref(item, run_id=run_id, case_id=case_id) for item in content.claims],
            "verified_facts": [
                _with_normalized_source_ref(item, run_id=run_id, case_id=case_id) for item in content.verified_facts
            ],
            "evidence_refs": [
                _with_normalized_source_ref(item, run_id=run_id, case_id=case_id)
                if isinstance(item, CaseWorkingContextObservationV1)
                else item
                for item in content.evidence_refs
            ],
            "actions_taken": [
                _with_normalized_source_ref(item, run_id=run_id, case_id=case_id) for item in content.actions_taken
            ],
            "commitments": [
                _with_normalized_source_ref(item, run_id=run_id, case_id=case_id) for item in content.commitments
            ],
        }
    )


def _with_normalized_source_ref(
    item: BaseModel,
    *,
    run_id: uuid.UUID | None,
    case_id: uuid.UUID,
) -> BaseModel:
    return item.model_copy(
        update={
            "source_ref": normalize_case_working_context_source_ref(
                item.source_ref,
                run_id=run_id,
                case_id=case_id,
            )
        }
    )
