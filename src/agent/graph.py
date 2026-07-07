"""LangGraph StateGraph assembly for MOCA refund agent.

Graph lifecycle:
  - build_graph(checkpointer) -> compiled graph (call once at startup)
  - graph.ainvoke(input, config) -> per-request invocation

Approval workflow routing:
  - high-risk proposed actions interrupt at approval_gate
  - approved actions create durable action drafts
  - rejected actions resume directly to final_response
LLM nodes use RetryPolicy(max_attempts=2) per D-10a.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from pydantic import ValidationError

from src.agent.nodes.approval_gate import approval_gate
from src.agent.nodes.action_draft import action_draft
from src.agent.nodes.clarification_gate import clarification_gate
from src.agent.nodes.claim_verify import claim_verify
from src.agent.nodes.contextual_intent_resolve import contextual_intent_resolve
from src.agent.nodes.final_response import final_response
from src.agent.nodes.investigate import investigate
from src.agent.nodes.memory_context_load import memory_context_load
from src.agent.nodes.rag_context_build import rag_context_build
from src.agent.nodes.recommendation_generation import recommendation_generation
from src.agent.nodes.receive_request import receive_request
from src.agent.nodes.risk_gate import risk_gate
from src.agent.nodes.safety_pre_route import safety_pre_route
from src.agent.nodes.session_context_load import session_context_load
from src.agent.nodes.slot_resolution_gate import slot_resolution_gate
from src.agent.routing import (
    _has_allowed_action_recommendation,
    route_after_claim_verify,
    route_after_contextual_intent,
    route_after_investigate,
    route_after_rag_context,
    route_after_recommendation,
    route_after_safety,
    route_after_slot_resolution,
)
from src.agent.state import AgentState
from src.approvals.schemas import AutoAllowedActionBindingV1
from src.approvals.schemas import TrustedApprovalResultV1
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1

# 1 retry = 2 total attempts per D-10a.
_llm_retry = RetryPolicy(max_attempts=2)
APPROVAL_RESULT_REQUIRED_FIELDS = (
    "approval_id",
    "tenant_id",
    "run_id",
    "revision",
    "request_version",
    "level_version",
    "assignment_version",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
)


def route_after_risk(state: AgentState) -> str:
    """Route based on risk assessment and proposed action."""
    if not _verification_allows_action_path(state):
        return "final_response"
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed:
        return "final_response"
    if not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    approval_plan = state.get("approval_plan") if isinstance(state.get("approval_plan"), dict) else {}
    if risk.get("blocked") is True or approval_plan.get("route") == "blocked":
        return "final_response"
    if risk.get("approval_required") is True:
        return "approval_gate" if _approval_plan_ready(state, approval_plan) else "final_response"
    if risk.get("approval_required") is False:
        return "action_draft" if _auto_allowed_binding_ready(state) else "final_response"
    return "final_response"


def _verification_allows_action_path(state: AgentState) -> bool:
    route = state.get("verification_route")
    rag_verification = state.get("rag_verification")
    if isinstance(rag_verification, dict):
        route_value = rag_verification.get("route")
        if isinstance(route_value, dict):
            route = route_value.get("route")
    if route is not None and route != "allow":
        return False
    return not _claim_bundle_blocks_action_path(state)


def _claim_bundle_blocks_action_path(state: AgentState) -> bool:
    if not state.get("proposed_action"):
        return False
    bundle = _bundle_mapping(state.get("claim_verification_bundle"))
    if bundle is None:
        return True
    if bundle.get("route") != "continue":
        return True
    if bundle.get("overall_status") not in {"verified", "not_required"}:
        return True
    if _non_empty_list(state.get("blocked_claims")) or _non_empty_list(bundle.get("blocked_claims")):
        return True
    return not _has_allowed_action_recommendation(bundle)


def _bundle_mapping(raw_bundle: Any) -> dict[str, Any] | None:
    if isinstance(raw_bundle, dict):
        return raw_bundle
    if hasattr(raw_bundle, "model_dump"):
        dumped = raw_bundle.model_dump(mode="python")
        return dumped if isinstance(dumped, dict) else None
    return None


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def route_after_approval(state: AgentState) -> str:
    """Route after a trusted ApprovalService resume result."""
    result = _trusted_approval_result(state)
    if result is None:
        return "final_response"
    decision_type = result.decision_type
    status = result.status
    if (
        decision_type == "edit"
        and status == "superseded"
        and result.resume_route == "risk_gate"
        and result.new_action_payload_hash
    ):
        return "risk_gate"
    if decision_type in {"accept", "approve"} and status == "approved":
        return "action_draft"
    if decision_type in {"accept", "approve"} and status == "pending":
        return "approval_gate"
    return "final_response"


def _snapshot_binding_ready(state: AgentState) -> bool:
    return all(
        bool(state.get(field)) for field in ("action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash")
    )


def _approval_plan_ready(state: AgentState, approval_plan: dict[str, Any]) -> bool:
    if not approval_plan or approval_plan.get("approval_required") is not True:
        return False
    scalar_fields = (
        "target_merchant_id",
        "risk_decision_ref",
        "approval_idempotency_key",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
    )
    if any(not approval_plan.get(field) for field in scalar_fields):
        return False
    if not _non_empty_list(approval_plan.get("business_fact_refs")):
        return False
    if not _non_empty_list(approval_plan.get("verified_evidence_refs")):
        return False
    if not approval_plan.get("risk_decision") and not state.get("risk_decision"):
        return False
    for field in (
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "target_merchant_id",
        "risk_decision_ref",
        "business_fact_refs",
        "verified_evidence_refs",
    ):
        if not state.get(field) or approval_plan.get(field) != state.get(field):
            return False
    return True


def _auto_allowed_binding_ready(state: AgentState) -> bool:
    raw_binding = state.get("auto_allowed_binding")
    if not raw_binding:
        return False
    try:
        binding = AutoAllowedActionBindingV1.model_validate(raw_binding)
    except ValidationError:
        return False
    if not binding.target_merchant_id or not binding.business_fact_refs or not binding.verified_evidence_refs:
        return False
    expected = {
        "tenant_id": str(state.get("tenant_id") or ""),
        "run_id": str(state.get("current_run_id") or ""),
        "target_merchant_id": str(state.get("target_merchant_id") or ""),
        "action_payload_hash": str(state.get("action_payload_hash") or ""),
        "safety_snapshot_ref": str(state.get("safety_snapshot_ref") or ""),
        "safety_snapshot_hash": str(state.get("safety_snapshot_hash") or ""),
        "risk_decision_ref": str(state.get("risk_decision_ref") or ""),
    }
    actual = {
        "tenant_id": binding.tenant_id,
        "run_id": binding.run_id,
        "target_merchant_id": binding.target_merchant_id,
        "action_payload_hash": binding.action_payload_hash,
        "safety_snapshot_ref": binding.safety_snapshot_ref,
        "safety_snapshot_hash": binding.safety_snapshot_hash,
        "risk_decision_ref": binding.risk_decision_ref,
    }
    if actual != expected:
        return False
    if [ref.model_dump(mode="json") for ref in binding.business_fact_refs] != _canonical_business_fact_refs(state):
        return False
    if [ref.model_dump(mode="json") for ref in binding.verified_evidence_refs] != _canonical_evidence_refs(state):
        return False
    return True


def _canonical_business_fact_refs(state: AgentState) -> list[dict[str, Any]]:
    try:
        return [
            BusinessFactRefV1.model_validate(ref).model_dump(mode="json")
            for ref in state.get("business_fact_refs") or []
        ]
    except ValidationError:
        return []


def _canonical_evidence_refs(state: AgentState) -> list[dict[str, Any]]:
    try:
        return [EvidenceRefV1.model_validate(ref).model_dump(mode="json") for ref in state.get("verified_evidence_refs") or []]
    except ValidationError:
        return []


def _trusted_approval_result(state: AgentState) -> TrustedApprovalResultV1 | None:
    result = state.get("approval_result") or {}
    if any(not result.get(field) for field in APPROVAL_RESULT_REQUIRED_FIELDS):
        return None
    try:
        trusted = TrustedApprovalResultV1.model_validate(result)
    except ValidationError:
        return None
    if str(trusted.tenant_id) != str(state.get("tenant_id") or ""):
        return None
    if str(trusted.run_id) != str(state.get("current_run_id") or ""):
        return None
    if (
        trusted.action_payload_hash != state.get("action_payload_hash")
        or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
        or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
    ):
        return None
    return trusted


def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("safety_pre_route", safety_pre_route)
    builder.add_node("session_context_load", session_context_load)
    builder.add_node("contextual_intent_resolve", contextual_intent_resolve, retry_policy=_llm_retry)
    builder.add_node("slot_resolution_gate", slot_resolution_gate, retry_policy=_llm_retry)
    builder.add_node("memory_context_load", memory_context_load)
    builder.add_node("investigate", investigate)
    builder.add_node("rag_context_build", rag_context_build)
    builder.add_node("recommendation_generation", recommendation_generation, retry_policy=_llm_retry)
    builder.add_node("claim_verify", claim_verify)
    builder.add_node("risk_gate", risk_gate, retry_policy=_llm_retry)
    builder.add_node("clarification_gate", clarification_gate)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("action_draft", action_draft)
    builder.add_node("final_response", final_response, retry_policy=_llm_retry)

    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "safety_pre_route")
    builder.add_conditional_edges(
        "safety_pre_route",
        route_after_safety,
        {
            "session_context_load": "session_context_load",
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
        },
    )
    builder.add_edge("session_context_load", "contextual_intent_resolve")
    builder.add_conditional_edges(
        "contextual_intent_resolve",
        route_after_contextual_intent,
        {
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
            "investigate": "investigate",
            "slot_resolution_gate": "slot_resolution_gate",
        },
    )
    builder.add_conditional_edges(
        "slot_resolution_gate",
        route_after_slot_resolution,
        {
            "clarification_gate": "clarification_gate",
            "investigate": "investigate",
            "memory_context_load": "memory_context_load",
        },
    )
    builder.add_edge("memory_context_load", "investigate")
    builder.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {
            "final_response": "final_response",
            "clarification_gate": "clarification_gate",
            "rag_context_build": "rag_context_build",
            "recommendation_generation": "recommendation_generation",
        },
    )
    builder.add_conditional_edges(
        "rag_context_build",
        route_after_rag_context,
        {
            "recommendation_generation": "recommendation_generation",
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
        },
    )
    builder.add_edge("clarification_gate", "final_response")
    builder.add_conditional_edges(
        "recommendation_generation",
        route_after_recommendation,
        {
            "claim_verify": "claim_verify",
            "final_response": "final_response",
        },
    )
    builder.add_conditional_edges(
        "claim_verify",
        route_after_claim_verify,
        {
            "risk_gate": "risk_gate",
            "final_response": "final_response",
        },
    )
    builder.add_conditional_edges(
        "risk_gate",
        route_after_risk,
        {
            "approval_gate": "approval_gate",
            "action_draft": "action_draft",
            "final_response": "final_response",
        },
    )
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "approval_gate": "approval_gate",
            "risk_gate": "risk_gate",
            "action_draft": "action_draft",
            "final_response": "final_response",
        },
    )
    builder.add_edge("action_draft", "final_response")
    builder.add_edge("final_response", END)

    return builder.compile(checkpointer=checkpointer)
