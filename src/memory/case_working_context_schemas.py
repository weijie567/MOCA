from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
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
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
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
