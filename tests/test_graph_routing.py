from __future__ import annotations

from src.agent.graph import route_after_approval, route_after_risk


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
