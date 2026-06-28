"""Request and response schemas for run-based agent SSE APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="User query for the agent")
    thread_id: str = Field(min_length=1, max_length=128, description="Conversation thread ID")


class RunStatusResponse(BaseModel):
    run_id: str
    final_status: str
    started_at: datetime
    completed_at: datetime | None = None
    final_response: str | None = None


class SseEventPayload(BaseModel):
    evidence_count: int | None = None
    tool_name: str | None = None
    risk_level: str | None = None
    short_summary: str | None = None
    approval_id: str | None = None
    proposed_action: dict[str, Any] | None = None
    final_response: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    rag_claim_summary: dict[str, Any] | None = None
