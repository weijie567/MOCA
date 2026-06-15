"""Approval domain schemas and schema version literals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.knowledge.schemas import EvidenceRefV1

ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION = "action_safety_snapshot.v1"
PROPOSED_ACTION_SCHEMA_VERSION = "proposed_action.v1"
APPROVAL_RESULT_SCHEMA_VERSION = "approval_result.v1"

ApprovalDecisionType = Literal["accept", "approve", "edit", "respond", "reject", "ignore"]
ApprovalRequestStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "needs_info",
    "superseded",
    "expired",
    "cancelled",
]


class ApprovalRequestCreateCommand(BaseModel):
    """Trusted server-side input for creating an executable v2 approval request."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    requested_by: UUID
    proposed_action: dict[str, Any]
    action_payload_hash: str | None = None
    approval_policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    risk_rule_ref: str | None = None
    policy_config_version: str = Field(min_length=1)
    risk_config_version: str = Field(min_length=1)
    retrieval_config_version: str = Field(min_length=1)
    evidence_refs: list[EvidenceRefV1] = Field(min_length=1)
    required_role: str = "manager"
    level_mode: Literal["any_one", "all"] = "any_one"
    created_at: datetime
    expires_at: datetime


class ApprovalRequestCreateResult(BaseModel):
    """Creation result with the version/hash refs callers must echo for decisions."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_id: UUID
    level_version: int = Field(ge=1)
    assignment_id: UUID
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    graph_thread_id: str


class ApprovalDecisionCommand(BaseModel):
    """Trusted server-side decision command for one request/level/assignment binding."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    level_id: UUID
    assignment_id: UUID
    actor_id: UUID
    actor_role: str = Field(min_length=1)
    decision_type: ApprovalDecisionType
    expected_request_version: int = Field(ge=1)
    expected_level_version: int = Field(ge=1)
    expected_assignment_version: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    action_payload_hash: str = Field(min_length=1)
    safety_snapshot_hash: str = Field(min_length=1)
    reason: str | None = None
    edited_action: dict[str, Any] | None = None
    response_text: str | None = None

    @model_validator(mode="after")
    def _validate_decision_payload(self) -> ApprovalDecisionCommand:
        if self.decision_type == "edit" and not self.edited_action:
            raise ValueError("edited_action is required for edit decisions")
        if self.decision_type == "respond" and not self.response_text:
            raise ValueError("response_text is required for respond decisions")
        return self


class TrustedApprovalResultV1(BaseModel):
    """Trusted graph resume payload produced only by ApprovalService."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["approval_result.v1"] = APPROVAL_RESULT_SCHEMA_VERSION
    approval_id: UUID
    status: ApprovalRequestStatus
    decision_type: ApprovalDecisionType
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_version: int = Field(ge=1)
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_hash: str


class ApprovalDecisionResult(BaseModel):
    """Domain transition result returned to API/graph callers."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    status: ApprovalRequestStatus
    decision_type: ApprovalDecisionType
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_version: int = Field(ge=1)
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_hash: str
    decision_id: UUID
    event_id: UUID
    resume_payload: dict[str, Any] | None = None
    graph_thread_id: str
