from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class ActiveSlots(TypedDict, total=False):
    order_id: str | None
    refund_case_id: str | None
    ticket_id: str | None
    merchant_id: str | None
    customer_id: str | None
    issue_type: str | None


class LastRecommendationSummary(TypedDict, total=False):
    recommended_action: str
    reasoning_summary: str
    confidence: float
    risk_level: str
    approval_required: bool
    created_at: str


class EvidenceRef(TypedDict, total=False):
    doc_key: str
    chunk_id: str
    title: str
    confidence: float
    retrieved_at: str


class LastBusinessContextRefs(TypedDict, total=False):
    order_id: str | None
    refund_case_id: str | None
    ticket_id: str | None
    loaded_at: str


class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""

    # Persistent memory: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    last_intent: str | None
    last_recommendation_summary: LastRecommendationSummary | None
    evidence_refs: list[EvidenceRef]
    last_business_context_refs: LastBusinessContextRefs | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    extracted_slots: dict[str, Any] | None
    business_context: dict[str, Any] | None
    retrieved_evidence: dict[str, Any] | None
    recommendation_draft: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None
    final_response: str | None
    tool_results: list[dict[str, Any]] | None
    llm_outputs: dict[str, Any] | None
    node_errors: list[dict[str, Any]] | None
    retry_count: int | None
    current_run_id: str | None
    trace_steps: list[dict[str, Any]] | None
