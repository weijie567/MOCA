from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: Literal[
        "policy_qa",
        "refund_troubleshooting",
        "compensation_suggestion",
        "approval_request",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SlotExtractionResult(BaseModel):
    order_id: str | None = None
    refund_case_id: str | None = None
    ticket_id: str | None = None
    merchant_id: str | None = None
    customer_id: str | None = None
    issue_type: str | None = None


class EvidenceRefSchema(BaseModel):
    doc_key: str
    chunk_id: str
    title: str
    section: str


class RecommendationDraft(BaseModel):
    recommended_action: str
    reasoning_summary: str
    evidence_refs: list[EvidenceRefSchema] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    missing_info: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_reason: str
    approval_required: bool
    rule_ref: str | None = None


class FinalResponseOutput(BaseModel):
    response_text: str
    evidence_citations: list[str] = Field(default_factory=list)
    final_status: Literal["completed", "insufficient_evidence", "error"]
