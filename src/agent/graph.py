"""LangGraph StateGraph assembly for MOCA refund agent.

Graph lifecycle:
  - build_graph(checkpointer) -> compiled graph (call once at startup)
  - graph.ainvoke(input, config) -> per-request invocation

Deterministic routing per D-02: all edges are fixed add_edge(), no conditional edges in Phase 3.
LLM nodes use RetryPolicy(max_attempts=2) per D-10a.
"""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from src.agent.nodes.assess_risk_and_approval import assess_risk_and_approval
from src.agent.nodes.classify_intent import classify_intent
from src.agent.nodes.extract_slots import extract_slots
from src.agent.nodes.final_response import final_response
from src.agent.nodes.generate_recommendation import generate_recommendation
from src.agent.nodes.load_business_context import load_business_context
from src.agent.nodes.receive_request import receive_request
from src.agent.nodes.retrieve_policy_evidence import retrieve_policy_evidence
from src.agent.state import AgentState

# 1 retry = 2 total attempts per D-10a.
_llm_retry = RetryPolicy(max_attempts=2)


def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
    builder.add_node("load_business_context", load_business_context)
    builder.add_node("retrieve_policy_evidence", retrieve_policy_evidence)
    builder.add_node("generate_recommendation", generate_recommendation, retry_policy=_llm_retry)
    builder.add_node("assess_risk_and_approval", assess_risk_and_approval, retry_policy=_llm_retry)
    builder.add_node("final_response", final_response, retry_policy=_llm_retry)

    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "classify_intent")
    builder.add_edge("classify_intent", "extract_slots")
    builder.add_edge("extract_slots", "load_business_context")
    builder.add_edge("load_business_context", "retrieve_policy_evidence")
    builder.add_edge("retrieve_policy_evidence", "generate_recommendation")
    builder.add_edge("generate_recommendation", "assess_risk_and_approval")
    builder.add_edge("assess_risk_and_approval", "final_response")
    builder.add_edge("final_response", END)

    return builder.compile(checkpointer=checkpointer)
