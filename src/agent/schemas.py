from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


IntentLiteral = Literal[
    "policy_qa",
    "order_status_inquiry",
    "refund_troubleshooting",
    "compensation_suggestion",
    "ticket_reply_draft",
    "appeal_or_unban",
    "complaint_escalation",
    "action_request",
    "business_metric_query",
    "small_talk",
    "unsupported",
]

MetricIdLiteral = Literal[
    "order_count",
    "refund_case_count",
    "pending_ticket_count",
    "coupon_record_count",
    "merchant_refund_rate",
]

MetricResourceTypeLiteral = Literal[
    "order",
    "refund_case",
    "ticket",
    "action_draft",
    "merchant_metric",
]

MetricTimePresetLiteral = Literal[
    "today",
    "this_week",
    "this_month",
    "this_quarter",
    "this_year",
    "current_snapshot",
]

RequestedOperationLiteral = Literal[
    "read_status",
    "advise",
    "draft_reply",
    "draft_action",
    "execute_action",
    "escalate",
]

RiskTierLiteral = Literal[
    "read_only",
    "draft_only",
    "suggest_action",
    "approval_required",
    "forbidden_in_chat",
]


class RequiredSlotExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_of: list[str] = Field(default_factory=list)
    any_of: list[list[str]] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal[
        "missing_required_slots",
        "low_confidence",
        "unsupported_or_ambiguous",
        "multi_target_request",
        "approval_chat_not_trusted",
    ]
    clarification_request_id: str
    questions: list[str]
    blocked_nodes: list[str]
    resume_policy: Literal["same_thread_only"] = "same_thread_only"


class IntentResultV3(BaseModel):
    """Strict ordinary-chat intent output.

    `primary_intent` captures the domain semantics while `requested_operation`
    captures the requested read/write/escalation mode. This keeps action-like
    wording from overwriting the most specific domain intent.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["intent_result.v3"] = "intent_result.v3"
    primary_intent: IntentLiteral
    requested_operation: RequestedOperationLiteral
    confidence: float = Field(ge=0.0, le=1.0)
    calibrated_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    secondary_intents: list[IntentLiteral] = Field(default_factory=list)
    required_slots: RequiredSlotExpression = Field(default_factory=RequiredSlotExpression)
    candidate_slots: dict[str, Any] = Field(default_factory=dict)
    routing_hints: dict[str, Any] = Field(default_factory=dict)
    classifier_version: str = "intent_classifier.v2"
    calibration_version: str = "calibration.unverified"
    reason_codes: list[str] = Field(default_factory=list)


class SlotExtractionResult(BaseModel):
    order_id: str | None = None
    refund_case_id: str | None = None
    ticket_id: str | None = None
    merchant_id: str | None = None
    customer_id: str | None = None
    issue_type: str | None = None
    action_type: str | None = None
    metric_id: MetricIdLiteral | str | None = None
    resource_type: MetricResourceTypeLiteral | str | None = None
    metric_time_preset: MetricTimePresetLiteral | str | None = None
    metric_time_range_start: str | None = None
    metric_time_range_end: str | None = None
    status_filter: str | list[str] | None = None


class EvidenceRefSchema(BaseModel):
    doc_key: str = Field(description="Exact doc_key copied from one retrieved evidence item.")
    chunk_id: str = Field(description="Exact chunk_id copied from the same retrieved evidence item.")
    title: str = Field(description="Exact title copied from the same retrieved evidence item.")
    section: str = Field(description="Exact section copied from the same retrieved evidence item.")


class RecommendationDraft(BaseModel):
    recommended_action: str
    reasoning_summary: str
    evidence_refs: list[EvidenceRefSchema] = Field(
        min_length=1,
        description=(
            "At least one citation object copied from retrieved evidence. "
            "Do not return strings, doc_key-only values, or chunk_id-only values."
        ),
    )
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
    final_status: Literal["completed", "insufficient_evidence", "manual_review", "refused", "error"]


class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"] = "v1"
    facts: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRefSchema] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    candidate_action: dict[str, Any] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    stop_reason: Literal[
        "sufficient_evidence",
        "insufficient_evidence",
        "unsafe_tool_request",
        "tool_error",
        "iteration_budget_exhausted",
    ]
    safety_notes: list[str] = Field(default_factory=list)
