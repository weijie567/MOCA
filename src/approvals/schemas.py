"""Approval domain schemas and schema version literals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1

ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION = "action_safety_snapshot.v1"
PROPOSED_ACTION_SCHEMA_VERSION = "proposed_action.v1"
APPROVAL_RESULT_SCHEMA_VERSION = "approval_result.v1"
RISK_DECISION_SCHEMA_VERSION = "risk_decision.v1"
AUTO_ALLOWED_ACTION_BINDING_SCHEMA_VERSION = "auto_allowed_action_binding.v1"
APPROVAL_DECISION_CONTEXT_SCHEMA_VERSION = "approval_decision_context.v1"

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

APPROVAL_ALLOWED_DECISION_TYPES: tuple[ApprovalDecisionType, ...] = (
    "accept",
    "approve",
    "edit",
    "respond",
    "reject",
    "ignore",
)


class ApprovalDecisionContextV1(BaseModel):
    """Complete immutable binding a client must echo when deciding."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["approval_decision_context.v1"] = APPROVAL_DECISION_CONTEXT_SCHEMA_VERSION
    approval_id: UUID
    tenant_ref: str = Field(min_length=1)
    run_id: UUID
    thread_id: str = Field(min_length=1)
    status: ApprovalRequestStatus
    allowed_decision_types: list[ApprovalDecisionType] = Field(min_length=1)
    level_id: UUID
    assignment_id: UUID
    request_version: int = Field(ge=1)
    level_version: int = Field(ge=1)
    assignment_version: int = Field(ge=1)
    revision: int = Field(ge=1)
    action_payload_hash: str = Field(min_length=1)
    safety_snapshot_ref: str = Field(min_length=1)
    safety_snapshot_hash: str = Field(min_length=1)
    proposed_action: dict[str, Any]
    risk_level: str = Field(min_length=1)
    risk_rule_ref: str | None = None
    risk_reason: str | None = None
    expires_at: datetime
    created_at: datetime


class RiskDecisionV1(BaseModel):
    """Risk-gate decision bound to an exact proposed action payload hash."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["risk_decision.v1"] = RISK_DECISION_SCHEMA_VERSION
    tenant_id: str
    run_id: str
    action_id: str
    action_payload_hash: str
    risk_level: str
    reason_codes: list[str]
    policy_config_version: str
    risk_config_version: str
    approval_required: bool
    evaluated_at: str
    risk_rule_ref: str | None = None
    risk_reason: str | None = None


class TargetMerchantBindingV1(BaseModel):
    """Target merchant derived from scoped business fact authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["target_merchant_binding.v1"] = "target_merchant_binding.v1"
    target_merchant_id: str
    source: Literal["business_fact_ref", "business_fact_result"]
    business_fact_ref: dict[str, Any]


class AutoAllowedActionBindingV1(BaseModel):
    """Durable no-approval binding required before any auto-draft path."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["auto_allowed_action_binding.v1"] = AUTO_ALLOWED_ACTION_BINDING_SCHEMA_VERSION
    tenant_id: str
    run_id: str
    target_merchant_id: str
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    risk_decision_ref: str
    idempotency_key: str
    business_fact_refs: list[BusinessFactRefV1]
    verified_evidence_refs: list[EvidenceRefV1]
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None


class ApprovalRequestCreateCommand(BaseModel):
    """Trusted server-side input for creating an executable v2 approval request."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    requested_by: UUID
    proposed_action: dict[str, Any]
    action_payload_hash: str | None = None
    safety_snapshot_ref: str | None = None
    safety_snapshot_hash: str | None = None
    approval_policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    risk_rule_ref: str | None = None
    risk_reason: str | None = None
    policy_config_version: str = Field(min_length=1)
    risk_config_version: str = Field(min_length=1)
    retrieval_config_version: str = Field(min_length=1)
    evidence_refs: list[EvidenceRefV1] = Field(min_length=1)
    target_merchant_id: str | None = None
    target_merchant_ref: TargetMerchantBindingV1 | dict[str, Any] | None = None
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    verified_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None
    risk_decision_ref: str | None = None
    risk_decision: RiskDecisionV1 | dict[str, Any] | None = None
    approval_idempotency_key: str | None = None
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
    target_merchant_id: str | None = None
    target_merchant_ref: TargetMerchantBindingV1 | dict[str, Any] | None = None
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    verified_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None
    risk_decision_ref: str | None = None
    risk_decision: RiskDecisionV1 | dict[str, Any] | None = None
    approval_idempotency_key: str | None = None
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


class ApprovalInfoCommand(BaseModel):
    """Trusted server-side attachment of user/agent info to a needs_info approval."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    clarification_request_id: str = Field(min_length=1)
    tenant_id: UUID
    actor_id: UUID
    actor_role: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    expected_request_version: int = Field(ge=1)
    expected_level_version: int = Field(ge=1)
    expected_assignment_version: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    info_payload: dict[str, Any] = Field(min_length=1)


class TrustedApprovalResultV1(BaseModel):
    """Trusted graph resume payload produced only by ApprovalService."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["approval_result.v1"] = APPROVAL_RESULT_SCHEMA_VERSION
    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    status: ApprovalRequestStatus
    decision_type: ApprovalDecisionType
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_version: int = Field(ge=1)
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    target_merchant_id: str | None = None
    target_merchant_ref: TargetMerchantBindingV1 | dict[str, Any] | None = None
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    verified_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None
    risk_decision_ref: str | None = None
    risk_decision: RiskDecisionV1 | dict[str, Any] | None = None
    approval_idempotency_key: str | None = None
    decided_by: UUID
    decided_at: datetime
    reason: str | None = None
    clarification_request_id: str | None = None
    superseded_by_request_id: UUID | None = None
    new_action_payload_hash: str | None = None
    edited_action: dict[str, Any] | None = None
    resume_route: str | None = None


class ApprovalDecisionResult(BaseModel):
    """Domain transition result returned to API/graph callers."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    status: ApprovalRequestStatus
    decision_type: ApprovalDecisionType
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_version: int = Field(ge=1)
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    target_merchant_id: str | None = None
    target_merchant_ref: TargetMerchantBindingV1 | dict[str, Any] | None = None
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    verified_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None
    risk_decision_ref: str | None = None
    risk_decision: RiskDecisionV1 | dict[str, Any] | None = None
    approval_idempotency_key: str | None = None
    decided_by: UUID
    decided_at: datetime
    decision_id: UUID
    event_id: UUID
    reason: str | None = None
    clarification_request_id: str | None = None
    superseded_by_request_id: UUID | None = None
    new_action_payload_hash: str | None = None
    edited_action: dict[str, Any] | None = None
    resume_payload: dict[str, Any] | None = None
    graph_thread_id: str


class ApprovalInfoResult(BaseModel):
    """Result of attaching info to a needs_info approval revision."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    status: ApprovalRequestStatus
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_id: UUID
    level_version: int = Field(ge=1)
    assignment_id: UUID
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    clarification_request_id: str
    superseded_request_id: UUID | None = None
    superseded_by_request_id: UUID | None = None
    new_action_payload_hash: str | None = None
    resume_payload: dict[str, Any] | None = None
    graph_thread_id: str
