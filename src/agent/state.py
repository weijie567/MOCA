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


# Canonical EvidenceRefV1 projection owned by src/knowledge/schemas.py, consumed by Phases 13/15.
class EvidenceRef(TypedDict, total=False):
    schema_version: str
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float
    rank: int


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
    active_slot_metadata: dict[str, Any] | None
    last_intent: str | None
    last_recommendation_summary: LastRecommendationSummary | None
    evidence_refs: list[EvidenceRef]
    last_business_context_refs: LastBusinessContextRefs | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    intent_confidence: float | None
    secondary_intents: list[str]
    required_slots: dict[str, Any]
    candidate_slots: dict[str, Any]
    routing_hints: dict[str, Any]
    extracted_slots: dict[str, Any] | None
    business_context: dict[str, Any] | None
    retrieved_evidence: dict[str, Any] | None
    recommendation_draft: dict[str, Any] | None
    clarification_request: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None

    # Phase 10: §10.1 canonical ephemeral fields reset each turn by receive_request.
    primary_intent: str | None
    requested_operation: str | None
    retrieval_status: str | None
    best_score: float | None
    termination_reason: str | None
    policy_evidence: list[dict[str, Any]] | None
    case_memory: list[dict[str, Any]] | None
    claim_dependency_map: list[dict[str, Any]] | None
    session_memory: dict[str, Any] | None
    memory_write_candidates: list[dict[str, Any]] | None
    memory_write_result: dict[str, Any] | None
    long_term_memory: list[dict[str, Any]] | None

    # Phase 4: approval workflow fields.
    proposed_action: dict[str, Any] | None
    approval_result: dict[str, Any] | None
    action_result: dict[str, Any] | None

    # Phase 7: dormant investigation contracts for future bounded investigator phases.
    investigation_result: dict[str, Any] | None
    investigation_steps: list[dict[str, Any]] | None
    investigation_trigger_reason: str | None
    investigation_path: str | None

    final_response: str | None
    tool_results: list[dict[str, Any]] | None
    llm_outputs: dict[str, Any] | None
    node_errors: list[dict[str, Any]] | None
    retry_count: int | None
    current_run_id: str | None
    run_started_at: str | None
    trace_steps: list[dict[str, Any]] | None
