"""Request and response schemas for POST /api/v1/agent/chat."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="User's refund/order question")
    thread_id: str = Field(
        min_length=1,
        max_length=128,
        description="Conversation thread ID. Same thread_id means same conversation memory.",
    )


class TraceSummary(BaseModel):
    run_id: str
    intent: str
    nodes_executed: list[str]
    tools_called: list[str]
    evidence_count: int
    risk_level: str
    total_latency_ms: int
    final_status: str
    rag_claim_summary: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    response: str
    trace_summary: TraceSummary
