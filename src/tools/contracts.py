"""Unified tool contracts shared by all graph-facing capabilities."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.knowledge.schemas import EvidenceRefV1


class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_context.v2"] = "tool_context.v2"
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: dict[str, Any] | list[str]
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str
    request_id: str
    tool_call_id: str
    caller_node: str
    deadline_at: datetime | None = None
    effective_at: str | None = None
    attempt: int = 1
    max_attempts: int = 1
    idempotency_key: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
    policy_snapshot_ref: str | None = None


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_request.v2"] = "tool_request.v2"
    tool_name: str
    arguments: dict[str, Any]
    argument_hash: str
    redaction_policy_version: str


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    safe_message: str
    retryable: bool
    source: Literal["caller", "tool", "adapter", "upstream", "policy"]


class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"
    tenant_id: str
    source_system: str
    resource_type: Literal["order", "refund_case", "ticket", "logistics", "merchant_risk"]
    resource_id: str
    resource_version: str | None
    data_freshness_at: datetime | None
    retrieved_at: datetime


class ToolResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_result.v2"] = "tool_result.v2"
    status: Literal[
        "success",
        "partial_success",
        "not_found",
        "permission_denied",
        "timeout",
        "unavailable",
        "conflict",
        "invalid_request",
        "invalid_response",
        "error",
    ]
    data: dict[str, Any] | None
    summary: str
    source_system: str
    data_freshness_at: datetime | None
    policy_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    error: ToolError | None = None
    retryable: bool = False
    retry_after_ms: int | None = None
    latency_ms: int
    audit_ref: str | None = None


class ToolArgumentSummaryV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_argument_summary.v1"] = "tool_argument_summary.v1"
    tool_call_id: str
    tool_name: str
    argument_summary_json: dict[str, Any]
    argument_hash: str
    redaction_policy_version: str


class ToolResultStorageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_result_storage.v1"] = "tool_result_storage.v1"
    tool_call_id: str
    tool_result_id: str
    tool_name: str
    status: str
    source_system: str
    raw_result_ref: str | None = None
    raw_result_hash: str | None = None
    normalized_result_json: dict[str, Any] = Field(default_factory=dict)
    summary: str
    prompt_summary: str
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    policy_evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    audit_ref: str | None = None


class ToolResultPromptSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    tool_result_id: str
    tool_name: str
    status: str
    summary: str
    prompt_summary: str
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    policy_evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    raw_result_ref: str | None = None
    audit_ref: str | None = None


class ToolViewV1(BaseModel):
    """Prompt-safe planner capability view derived from a ToolDescriptor.

    Exposes exactly five prompt-visible fields; descriptor/policy/runtime
    metadata must not leak through this contract.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, Any]
    safe_usage_notes: list[str]
    result_contract_version: Literal["tool_result.v2"] = "tool_result.v2"


class ToolPolicyDecision(BaseModel):
    """Domain-level tool policy decision object.

    This is NOT a replay event envelope; it must not contain event_id,
    sequence, occurred_at, run_id, or tenant_id.  It is persisted through
    DecisionEventEnvelopeV1 / emit_decision_event as a redacted_payload
    sub-object.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_policy_decision.v1"] = "tool_policy_decision.v1"
    tool_name: str
    caller: str
    decision_stage: Literal["visibility", "runtime_auth"]
    decision: Literal["visible", "hidden", "allowed", "denied"]
    reason_codes: list[str]
    required_scopes: list[str]
    matched_scope: str | None = None
    policy_version: str
    data_classification: Literal["public", "internal", "sensitive", "restricted"]
    resource_scope_binding: dict[str, Any] | None = None
    runtime_available: bool | None = None
    availability_summary: str | None = None

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, codes: list[str]) -> list[str]:
        from src.tools.policy import validate_tool_policy_reason_codes

        validate_tool_policy_reason_codes(codes)
        return codes

    @model_validator(mode="after")
    def _visibility_forbids_runtime_only_codes(self) -> "ToolPolicyDecision":
        from src.tools.policy import TOOL_POLICY_RUNTIME_ONLY_REASON_CODES

        if self.decision_stage == "visibility":
            runtime_leaked = set(self.reason_codes) & TOOL_POLICY_RUNTIME_ONLY_REASON_CODES
            if runtime_leaked:
                raise ValueError(
                    f"visibility-stage decision must not carry runtime-only reason codes: "
                    f"{runtime_leaked}"
                )
        return self


class ToolResultProjectionV1(BaseModel):
    """Projected tool result surfaces for graph, prompt, and audit consumption."""

    model_config = ConfigDict(extra="forbid")

    normalized_result: dict[str, Any]
    prompt_projection: dict[str, Any]
    text_for_prompt: str
    audit_refs: list[Any]
    resource_refs: list[Any]
    debug_projection: dict[str, Any]
    raw_artifact_ref: str | None = None
    raw_artifact_hash: str | None = None


class ToolInvocationOutcome(BaseModel):
    """Complete outcome of a tool invocation including result, projection, and policy decision."""

    model_config = ConfigDict(extra="forbid")

    tool_result: ToolResultV2
    projection: ToolResultProjectionV1
    policy_decision: ToolPolicyDecision
    policy_event_id: str | None = None


ToolResult = ToolResultV2
