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

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from pydantic import ValidationError

from src.agent.nodes.assess_risk_and_approval import assess_risk_and_approval
from src.agent.nodes.approval_gate import approval_gate
from src.agent.nodes.action_draft import action_draft
from src.agent.nodes.classify_intent import classify_intent
from src.agent.nodes.clarification_gate import clarification_gate
from src.agent.nodes.extract_slots import extract_slots
from src.agent.nodes.final_response import final_response
from src.agent.nodes.generate_recommendation import generate_recommendation
from src.agent.nodes.investigate import investigate
from src.agent.nodes.long_term_memory_retrieve import long_term_memory_retrieve
from src.agent.nodes.receive_request import receive_request
from src.agent.nodes.session_memory_load import session_memory_load
from src.agent.routing import route_after_intent, route_after_investigate, route_after_slots
from src.agent.state import AgentState
from src.approvals.schemas import TrustedApprovalResultV1

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
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed:
        return "final_response"
    if not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    if risk.get("approval_required"):
        return "approval_gate"
    # Phase 14 has no durable auto-allowed binding, so no-approval actions fail closed.
    return "final_response"


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
        and result.resume_route == "assess_risk_and_approval"
        and result.new_action_payload_hash
    ):
        return "assess_risk_and_approval"
    if decision_type in {"accept", "approve"} and status == "approved":
        return "action_draft"
    if decision_type in {"accept", "approve"} and status == "pending":
        return "approval_gate"
    return "final_response"


def _snapshot_binding_ready(state: AgentState) -> bool:
    return all(
        bool(state.get(field))
        for field in ("action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash")
    )


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
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("session_memory_load", session_memory_load)
    builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
    builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)
    builder.add_node("investigate", investigate)
    builder.add_node("generate_recommendation", generate_recommendation, retry_policy=_llm_retry)
    builder.add_node("assess_risk_and_approval", assess_risk_and_approval, retry_policy=_llm_retry)
    builder.add_node("clarification_gate", clarification_gate)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("action_draft", action_draft)
    builder.add_node("final_response", final_response, retry_policy=_llm_retry)

    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
            "investigate": "investigate",
            "session_memory_load": "session_memory_load",
        },
    )
    builder.add_edge("session_memory_load", "extract_slots")
    builder.add_conditional_edges(
        "extract_slots",
        route_after_slots,
        {
            "clarification_gate": "clarification_gate",
            "investigate": "investigate",
            "long_term_memory_retrieve": "long_term_memory_retrieve",
        },
    )
    builder.add_edge("long_term_memory_retrieve", "investigate")
    builder.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {
            "final_response": "final_response",
            "clarification_gate": "clarification_gate",
            "recommendation_generation": "generate_recommendation",
        },
    )
    builder.add_edge("clarification_gate", "final_response")
    builder.add_edge("generate_recommendation", "assess_risk_and_approval")
    builder.add_conditional_edges(
        "assess_risk_and_approval",
        route_after_risk,
        {
            "assess_risk_and_approval": "assess_risk_and_approval",
            "approval_gate": "approval_gate",
            "final_response": "final_response",
        },
    )
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "approval_gate": "approval_gate",
            "assess_risk_and_approval": "assess_risk_and_approval",
            "action_draft": "action_draft",
            "final_response": "final_response",
        },
    )
    builder.add_edge("action_draft", "final_response")
    builder.add_edge("final_response", END)

    return builder.compile(checkpointer=checkpointer)
