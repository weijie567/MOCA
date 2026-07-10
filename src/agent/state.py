from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from typing_extensions import TypedDict

from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    EvidenceRefV1,
    MaterialClaimV1,
    VerifiedEvidencePackageV1,
)


class ActiveSlots(TypedDict, total=False):
    order_id: str | None
    refund_case_id: str | None
    ticket_id: str | None
    merchant_id: str | None
    customer_id: str | None
    issue_type: str | None
    metric_id: str | None
    resource_type: str | None
    metric_time_preset: str | None
    metric_time_range_start: str | None
    metric_time_range_end: str | None
    status_filter: str | list[str] | None
    business_query_spec: dict[str, Any] | None


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

    # Durable graph/checkpoint context: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    business_query_context_binding: str | None
    active_slots: ActiveSlots
    active_slot_metadata: dict[str, Any] | None
    last_intent: str | None
    last_recommendation_summary: LastRecommendationSummary | None
    evidence_refs: list[EvidenceRef]
    last_business_context_refs: LastBusinessContextRefs | None
    last_query_spec: dict[str, Any] | None
    last_answer_context: dict[str, Any] | None
    result_cursor: dict[str, Any] | None
    expected_slot_type: str | None
    expected_slot_context: dict[str, Any] | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    intent_confidence: float | None
    risk_tier: str | None
    classification_trace: dict[str, Any] | None
    slot_resolution_trace: dict[str, Any] | None
    missing_required_slots: list[dict[str, list[str]]]
    task_plan: dict[str, Any] | None
    deferred_steps: list[dict[str, Any]]
    target_merchant_context: dict[str, Any] | None
    pre_route_decision: dict[str, Any] | None
    safety_flags: dict[str, Any]
    active_flow_state: dict[str, Any] | None
    secondary_intents: list[str]
    required_slots: dict[str, Any]
    candidate_slots: dict[str, Any]
    routing_hints: dict[str, Any]
    extracted_slots: dict[str, Any] | None
    business_context: dict[str, Any] | None
    retrieved_evidence: dict[str, Any] | None
    recommendation_draft: dict[str, Any] | None
    canonical_action: dict[str, Any] | None
    clarification_request: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None
    risk_signals: list[str] | None

    # Phase 10: §10.1 canonical ephemeral fields reset each turn by receive_request.
    primary_intent: str | None
    requested_operation: str | None
    retrieval_status: str | None
    best_score: float | None
    termination_reason: str | None
    policy_evidence: list[dict[str, Any]] | None
    case_memory: list[dict[str, Any]] | None
    claim_dependency_map: list[dict[str, Any]] | None
    rag_context_status: str | None
    verified_evidence_package: VerifiedEvidencePackageV1 | dict[str, Any] | None
    citation_map: dict[str, list[str]]
    evidence_map: dict[str, EvidenceRefV1 | dict[str, Any]]
    material_claims: list[MaterialClaimV1 | dict[str, Any]]
    claim_verification_bundle: ClaimVerificationBundleV1 | dict[str, Any] | None
    blocked_claims: list[str]
    safe_support_refs: list[EvidenceRefV1 | dict[str, Any] | str]
    rag_context_bundle: dict[str, Any] | None
    rag_verification: dict[str, Any] | None
    verifier_status: str | None
    verification_route: str | None
    verifier_reason_codes: list[str] | None
    verifier_safe_citation_refs: list[str] | None
    verifier_metrics: dict[str, int | float | bool | str] | None
    session_context: dict[str, Any] | None
    session_context_bundle: dict[str, Any] | None
    session_context_load_status: dict[str, Any] | None
    session_memory: dict[str, Any] | None
    session_memory_bundle: dict[str, Any] | None
    memory_context: dict[str, Any] | None
    memory_context_bundle: dict[str, Any] | None
    reviewed_memory_context_retrieve_status: dict[str, Any] | None
    case_working_context: dict[str, Any] | None
    case_working_context_lifecycle_status: dict[str, Any] | None
    memory_write_candidates: list[dict[str, Any]] | None
    memory_write_result: dict[str, Any] | None
    memory_write_decision: dict[str, Any] | None
    long_term_memory: list[dict[str, Any]] | None

    # Phase 4: approval workflow fields.
    proposed_action: dict[str, Any] | None
    approval_result: dict[str, Any] | None
    approval_revision_refs: list[dict[str, Any]] | None
    action_payload_hash: str | None
    safety_snapshot_ref: str | None
    safety_snapshot_hash: str | None
    safety_snapshot_verified: bool | None
    policy_config_version: str | None
    risk_config_version: str | None
    retrieval_config_version: str | None
    auto_allowed: bool | None
    approval_plan: dict[str, Any] | None
    risk_decision: dict[str, Any] | None
    risk_decision_ref: str | None
    target_merchant_id: str | None
    target_merchant_ref: dict[str, Any] | None
    scope_classification: str | None
    scope_source: str | None
    scope_reason_codes: list[str] | None
    business_fact_refs: list[dict[str, Any]]
    verified_evidence_refs: list[dict[str, Any]]
    claim_verification_ref: str | None
    claim_verification_summary: dict[str, Any] | None
    approval_idempotency_key: str | None
    auto_action_capability: dict[str, Any] | None
    auto_allowed_binding: dict[str, Any] | None
    action_draft: dict[str, Any] | None
    draft_outcome: dict[str, Any] | None
    execution_mode: str | None
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


def business_query_context_binding(state: Mapping[str, Any]) -> str:
    """Fingerprint trusted identity/scope fields without storing raw authority values."""
    payload = {
        "tenant_id": _binding_value(state.get("tenant_id")),
        "user_id": _binding_value(state.get("user_id")),
        "role": _binding_value(state.get("role")),
        "thread_id": _binding_value(state.get("thread_id")),
        "session_id": _binding_value(state.get("session_id")),
        "merchant_scope": _binding_value(state.get("merchant_scope")),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def business_query_context_binding_from_trusted_context(trusted_context: Any) -> str:
    """Fingerprint canonical TrustedContext identity/scope without exposing raw values in AgentState."""

    payload = {
        "tenant_id": _binding_value(_trusted_context_value(trusted_context, "tenant_id")),
        "user_id": _binding_value(_trusted_context_value(trusted_context, "user_id")),
        "role": _binding_value(_trusted_context_value(trusted_context, "role")),
        "thread_id": _binding_value(_trusted_context_value(trusted_context, "thread_id")),
        "session_id": _binding_value(_trusted_context_value(trusted_context, "session_id")),
        "merchant_scope": _binding_value(_trusted_context_value(trusted_context, "merchant_scope")),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def trusted_business_query_context_binding(state: Mapping[str, Any]) -> str | None:
    """Return the trusted per-turn binding hash carried in AgentState, if present."""

    binding = state.get("business_query_context_binding")
    if isinstance(binding, str) and binding.startswith("sha256:"):
        return binding
    return None


def _trusted_context_value(trusted_context: Any, key: str) -> Any:
    if isinstance(trusted_context, Mapping):
        return trusted_context.get(key)
    return getattr(trusted_context, key, None)


def _binding_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _binding_value(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(key): _binding_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set, frozenset)):
        return sorted(_binding_value(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
