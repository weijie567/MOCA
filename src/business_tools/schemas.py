"""Canonical business-tool facade contracts.

Spec Consistency Finding SCF-1: no canonical TrustedContext or
MerchantScopeV1 implementation exists yet. ToolCallContext therefore inlines
the trusted identity and scope projection while Phase 10 owns convergence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.knowledge.schemas import EvidenceRefV1


class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_context.v2"] = "tool_context.v2"
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: dict[str, Any]  # SCF-1 defers MerchantScopeV1 validation to Phase 10.
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str
    request_id: str
    tool_call_id: str
    caller_node: str
    deadline_at: datetime | None = None
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


class BusinessContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_context.v1"] = "business_context.v1"
    tenant_id: str
    status: Literal["complete", "partial", "insufficient", "error"]
    facts: dict[str, Any]
    business_fact_refs: list[BusinessFactRefV1]
    tool_results: list[ToolResultV2]
    missing_required_facts: list[str]
    errors: list[ToolError]
    data_freshness_at: datetime | None
