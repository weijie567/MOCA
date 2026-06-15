from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: Literal["accept", "approve", "edit", "respond", "reject", "ignore"]
    expected_request_version: int = Field(ge=1)
    expected_level_version: int = Field(ge=1)
    expected_assignment_version: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    action_payload_hash: str = Field(min_length=1)
    safety_snapshot_hash: str = Field(min_length=1)
    reason: str | None = None
    edited_action: dict[str, Any] | None = None
    response_text: str | None = None


class ApprovalResponse(BaseModel):
    id: str
    run_id: str
    status: str
    revision: int | None
    request_version: int | None
    action_payload_hash: str | None
    safety_snapshot_ref: str | None
    safety_snapshot_hash: str | None
    requested_by: str
    proposed_action: dict[str, Any]
    risk_level: str
    risk_rule_ref: str | None
    risk_reason: str | None
    decision: str | None
    reason: str | None
    decided_by: str | None
    decided_at: datetime | None
    expires_at: datetime
    created_at: datetime


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalResponse]
    total: int


class TraceResponse(BaseModel):
    run_id: str
    thread_id: str
    final_status: str
    started_at: datetime
    completed_at: datetime | None
    total_latency_ms: int | None
    steps: list[dict[str, Any]]
    approvals: list[ApprovalResponse]
    action_drafts: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
