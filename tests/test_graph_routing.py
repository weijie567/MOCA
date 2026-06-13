from __future__ import annotations

import pytest

from src.agent.graph import route_after_approval, route_after_risk
from src.agent.routing import route_after_investigate


VALID_INVESTIGATE_KEYS = {"final_response", "clarification_gate", "recommendation_generation"}


def test_route_after_risk_returns_final_response_for_policy_qa_no_action():
    state = {
        "current_intent": "policy_qa",
        "risk_assessment": {"approval_required": False},
        "proposed_action": None,
    }

    assert route_after_risk(state) == "final_response"


def test_route_after_risk_returns_approval_gate_when_approval_required():
    state = {
        "risk_assessment": {"approval_required": True},
        "proposed_action": {"action_type": "issue_coupon"},
    }

    assert route_after_risk(state) == "approval_gate"


def test_route_after_risk_returns_execute_action_for_low_risk_proposed_action():
    state = {
        "risk_assessment": {"approval_required": False},
        "proposed_action": {"action_type": "issue_coupon"},
    }

    assert route_after_risk(state) == "execute_action"


def test_route_after_approval_returns_execute_action_on_approve():
    assert route_after_approval({"approval_result": {"decision": "approve"}}) == "execute_action"


def test_route_after_approval_returns_final_response_on_reject():
    assert route_after_approval({"approval_result": {"decision": "reject"}}) == "final_response"


def test_route_after_approval_returns_final_response_when_empty():
    assert route_after_approval({"approval_result": None}) == "final_response"


def test_missing_required_facts_to_clarification():
    state = {"business_context": {"missing_required_facts": ["order_id"]}}

    assert route_after_investigate(state) == "clarification_gate"


def test_fact_only_intent_with_facts_to_final():
    state = {
        "primary_intent": "order_status_inquiry",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
    }

    assert route_after_investigate(state) == "final_response"


@pytest.mark.parametrize(
    "state",
    [
        {"retrieval_status": "no_evidence"},
        {"retrieval_status": "partial_evidence", "best_score": 0.3},
    ],
)
def test_insufficient_evidence_to_final(state):
    assert route_after_investigate(state) == "final_response"


def test_sufficient_context_to_recommendation():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "recommendation_generation"


def test_permission_denied_required_blocks():
    state = {
        "business_context": {
            "missing_required_facts": ["merchant_risk"],
            "errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}],
        },
        "claim_dependency_map": [
            {
                "claim_id": "risk_claim",
                "depends_on_refs": [{"resource_type": "merchant_risk", "resource_id": "merchant-1"}],
            }
        ],
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "final_response"


@pytest.mark.parametrize(
    "claim_dependency_map",
    [
        None,
        [],
        [{"claim_id": "risk_claim", "depends_on_refs": [{"resource_type": "merchant_risk"}]}],
    ],
)
def test_permission_denied_dependency_map_fail_closed(claim_dependency_map):
    state = {
        "business_context": {
            "facts": {"order": {"status": "delivered"}},
            "errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}],
        },
        "claim_dependency_map": claim_dependency_map,
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "final_response"


def test_permission_denied_nonrequired_preserved():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {
            "facts": {"order": {"status": "delivered"}},
            "errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}],
        },
        "claim_dependency_map": [
            {
                "claim_id": "order_status",
                "depends_on_refs": [{"resource_type": "order", "resource_id": "ORD-001"}],
            }
        ],
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "recommendation_generation"


def test_max_iterations_does_not_force_insufficient():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
        "termination_reason": "max_iterations_reached",
    }

    assert route_after_investigate(state) == "recommendation_generation"


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"primary_intent": "order_status_inquiry"},
        {"business_context": {"missing_required_facts": ["order_id"]}},
        {"business_context": {"errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}]}},
        {"retrieval_status": "error"},
        {"best_score": 0.1},
        {"primary_intent": 123, "business_context": "not-a-dict", "retrieval_status": object()},
    ],
)
def test_route_after_investigate_totality(state):
    assert route_after_investigate(state) in VALID_INVESTIGATE_KEYS


def test_empty_state_safe_default():
    assert route_after_investigate({}) == "final_response"
