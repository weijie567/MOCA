from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DecideRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reason: str | None = None


class ApprovalResponse(BaseModel):
    id: str
    run_id: str
    status: str
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
