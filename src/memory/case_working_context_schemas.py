from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.memory.schemas import MemorySourceRefV1


class CaseWorkingContextClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    verified: bool
    source_ref: MemorySourceRefV1


class CaseWorkingContextVerifiedFactV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    source_ref: MemorySourceRefV1
    observed_at: datetime


class CaseWorkingContextActionTakenV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    source_ref: MemorySourceRefV1


class CaseWorkingContextCommitmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    confirmed_by_staff: bool
    source_ref: MemorySourceRefV1


class CaseWorkingContextPolicyRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    chunk_id: str
    version: str


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
    evidence_refs: list[CaseWorkingContextEvidencePointerV1] = Field(default_factory=list)
    actions_taken: list[CaseWorkingContextActionTakenV1] = Field(default_factory=list)
    policy_refs: list[CaseWorkingContextPolicyRefV1] = Field(default_factory=list)
    agent_recommendations: list[CaseWorkingContextRecommendationV1] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    commitments: list[CaseWorkingContextCommitmentV1] = Field(default_factory=list)
    next_action: CaseWorkingContextNextActionV1 = Field(default_factory=CaseWorkingContextNextActionV1)


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
