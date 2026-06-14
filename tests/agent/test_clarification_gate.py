from __future__ import annotations

import pytest

from src.agent.nodes.clarification_gate import clarification_gate


@pytest.mark.asyncio
async def test_missing_required_slots_builds_minimal_clarification(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "current_run_id": "run-1",
            "routing_hints": {
                "clarification_reason": "missing_required_slots",
                "missing_required_slots": [{"any_of": ["refund_case_id", "order_id"]}],
            },
            "missing_required_slots": [{"any_of": ["refund_case_id", "order_id"]}],
        },
        {},
    )

    request = result["clarification_request"]
    assert request["reason"] == "missing_required_slots"
    assert request["clarification_request_id"] == "clarify_run-1"
    assert request["questions"] == ["请提供退款单号或订单号。"]
    assert {"investigate", "action_draft"} <= set(request["blocked_nodes"])
    assert request["resume_policy"] == "same_thread_only"


@pytest.mark.asyncio
async def test_missing_required_slots_are_recomputed_from_policy_when_router_is_pure(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "primary_intent": "refund_troubleshooting",
            "current_intent": "refund_troubleshooting",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "extracted_slots": {},
            "session_memory": {"continuity_claimed": False, "active_slots": {}},
        },
        {},
    )

    assert result["clarification_request"]["reason"] == "missing_required_slots"
    assert result["clarification_request"]["questions"] == ["请提供订单号或退款单号。"]


@pytest.mark.asyncio
async def test_low_confidence_and_errors_do_not_leak(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "intent_confidence": 0.4,
            "node_errors": [{"error": "FORBIDDEN stack trace denied resource secret"}],
            "routing_hints": {"clarification_reason": "low_confidence"},
        },
        {},
    )

    assert result["clarification_request"]["reason"] == "low_confidence"
    assert "FORBIDDEN" not in result["final_response"]
    assert "stack trace" not in result["final_response"]
    assert "denied" not in result["final_response"]


@pytest.mark.asyncio
async def test_approval_chat_not_trusted_ignores_contaminated_state(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "routing_hints": {"clarification_reason": "approval_chat_not_trusted"},
            "approval_result": {"decision": "approve"},
            "approval_revision_refs": {"revision": 2},
            "trusted_approval_result": {"decision": "approve"},
            "resume": {"decision": "approve"},
            "approval_version": 3,
        },
        {},
    )

    request = result["clarification_request"]
    assert request["reason"] == "approval_chat_not_trusted"
    assert {"investigate", "action_draft", "approval_gate", "execute_action"} <= set(request["blocked_nodes"])
    assert "approval_result" not in result
    assert "trusted_approval_result" not in str(request)
    assert "resume" not in result
    assert "decision" not in str(request)
    assert "审批操作需要通过审批入口处理" in result["final_response"]
