from __future__ import annotations

from typing import Any

import pytest

from src.knowledge.schemas import RAG_CONTEXT_STATUSES


FINITE_RAG_CONTEXT_ROUTES = {"recommendation_generation", "clarification_gate", "final_response"}


@pytest.mark.parametrize("status", RAG_CONTEXT_STATUSES)
def test_route_after_rag_context_is_total_over_all_statuses(status: str) -> None:
    from src.agent.routing import route_after_rag_context

    state: dict[str, Any] = {
        "rag_context_status": status,
        "verified_evidence_package": {"status": status},
        "primary_intent": "policy_qa",
        "requested_operation": "advise",
        "risk_tier": "low",
        "evidence_policy": {"evidence_required": status != "not_required"},
    }
    if status == "partial":
        state["verified_evidence_package"] = {"status": status, "evidence_map": {"policy#1": {}}}

    route = route_after_rag_context(state)

    assert route in FINITE_RAG_CONTEXT_ROUTES


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"rag_context_status": "verified"}, "recommendation_generation"),
        (
            {
                "rag_context_status": "not_required",
                "primary_intent": "order_status_inquiry",
                "requested_operation": "read_status",
                "evidence_policy": {"evidence_required": False},
            },
            "recommendation_generation",
        ),
        (
            {
                "rag_context_status": "not_required",
                "primary_intent": "compensation_suggestion",
                "requested_operation": "draft_action",
                "evidence_policy": {"evidence_required": True},
            },
            "final_response",
        ),
        (
            {
                "rag_context_status": "partial",
                "primary_intent": "policy_qa",
                "requested_operation": "advise",
                "risk_tier": "low",
                "verified_evidence_package": {"status": "partial", "evidence_map": {"policy#1": {}}},
            },
            "recommendation_generation",
        ),
        (
            {
                "rag_context_status": "partial",
                "primary_intent": "compensation_suggestion",
                "requested_operation": "draft_action",
                "risk_tier": "high",
                "proposed_action": {"action_type": "issue_coupon"},
            },
            "final_response",
        ),
        (
            {
                "rag_context_status": "no_evidence",
                "business_context": {"missing_required_facts": ["refund_case"]},
            },
            "clarification_gate",
        ),
        ({"rag_context_status": "unauthorized"}, "final_response"),
        ({"rag_context_status": "stale"}, "final_response"),
        ({"rag_context_status": "conflict"}, "final_response"),
        ({"rag_context_status": "invalid_hash"}, "final_response"),
        ({"rag_context_status": "invalid_scope"}, "final_response"),
        ({"rag_context_status": "build_error"}, "final_response"),
        ({"rag_context_status": "unknown"}, "final_response"),
        ({"verified_evidence_package": {"status": "verified"}}, "recommendation_generation"),
        ({"verified_evidence_package": {"status": 123}}, "final_response"),
    ],
)
def test_route_after_rag_context_matrix(state: dict[str, Any], expected: str) -> None:
    from src.agent.routing import route_after_rag_context

    assert route_after_rag_context(state) == expected


@pytest.mark.parametrize(
    "state",
    [
        {"retrieval_status": "strong_evidence", "best_score": 0.9, "policy_evidence": [{"evidence_id": "p1"}]},
        {
            "retrieval_status": "partial_evidence",
            "best_score": 0.72,
            "retrieved_evidence": {"evidence_refs": [{"evidence_id": "p1"}]},
        },
        {
            "primary_intent": "compensation_suggestion",
            "requested_operation": "draft_action",
            "retrieval_status": "strong_evidence",
            "best_score": 0.91,
            "policy_evidence": [{"evidence_id": "p1"}],
        },
    ],
)
def test_route_after_investigate_sends_policy_candidates_to_rag_context_build(state: dict[str, Any]) -> None:
    from src.agent.routing import route_after_investigate

    assert route_after_investigate(state) == "rag_context_build"


def test_route_after_investigate_preserves_fact_only_final_route() -> None:
    from src.agent.routing import route_after_investigate

    state = {
        "primary_intent": "order_status_inquiry",
        "requested_operation": "read_status",
        "business_context": {"facts": {"order": {"order_no": "ORD-1"}}, "missing_required_facts": []},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "final_response"
