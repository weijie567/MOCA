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
    assert request["questions"] == ["我需要退款单号或订单号来定位具体售后对象；请提供退款单号或订单号中的至少一个。"]
    assert {"investigate", "action_draft"} <= set(request["blocked_nodes"])
    assert request["resume_policy"] == "same_thread_only"
    assert "routing_hints" not in result["final_response"]
    assert "blocked_nodes" not in result["final_response"]
    assert "investigate" not in result["final_response"]


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
    assert result["clarification_request"]["questions"] == [
        "我需要订单号或退款单号来定位具体售后对象；请提供订单号或退款单号中的至少一个。"
    ]


@pytest.mark.asyncio
async def test_order_identifier_clarification_lists_all_accepted_identifier_types(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "primary_intent": "order_status_inquiry",
            "current_intent": "order_status_inquiry",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id", "ticket_id"]], "optional": []},
            "extracted_slots": {},
            "session_memory": {"continuity_claimed": False, "active_slots": {}},
        },
        {},
    )

    question = result["clarification_request"]["questions"][0]
    assert "我需要" in question
    assert "定位具体售后对象" in question
    assert "订单号、退款单号或工单号" in question
    assert result["final_response"] == question


@pytest.mark.asyncio
async def test_metric_time_range_clarification_lists_supported_options_without_policy_internals(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "primary_intent": "business_metric_query",
            "routing_hints": {
                "clarification_reason": "missing_required_slots",
                "missing_required_slots": [{"all_of": ["metric_time_range"]}],
            },
            "missing_required_slots": [{"all_of": ["metric_time_range"]}],
        },
        {},
    )

    question = result["clarification_request"]["questions"][0]
    assert "时间范围" in question
    for option in ("今天", "本周", "本月", "本季度", "今年", "起止时间"):
        assert option in question
    assert "metric_time_range" not in result["final_response"]
    assert "routing_hints" not in result["final_response"]
    assert "slot" not in result["final_response"].lower()


@pytest.mark.asyncio
async def test_metric_id_clarification_lists_supported_metric_labels(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "primary_intent": "business_metric_query",
            "missing_required_slots": [{"all_of": ["metric_id"]}],
        },
        {},
    )

    question = result["clarification_request"]["questions"][0]
    for label in ("订单数", "退款单数", "待处理工单数", "补偿券记录数", "商户退款率"):
        assert label in question
    assert "business_metric_query" not in question
    assert "metric_id" not in question


@pytest.mark.asyncio
async def test_metric_merchant_filter_clarification_is_user_readable(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "primary_intent": "business_metric_query",
            "missing_required_slots": [{"all_of": ["merchant_filter"]}],
        },
        {},
    )

    question = result["clarification_request"]["questions"][0]
    assert "商家" in question
    assert "当前权限范围" in question
    assert "merchant_filter" not in question


@pytest.mark.asyncio
async def test_metric_scope_denial_does_not_confirm_unauthorized_merchant(base_state):
    result = await clarification_gate(
        {
            **base_state,
            "primary_intent": "business_metric_query",
            "routing_hints": {
                "clarification_reason": "unsupported_or_ambiguous",
                "safe_reason": "metric_scope_denied",
                "merchant_id": "merchant-secret-404",
            },
            "active_slots": {"merchant_id": "merchant-secret-404"},
        },
        {},
    )

    response = result["final_response"]
    assert "当前权限范围内无法提供该商户指标" in response
    assert "merchant-secret-404" not in response
    assert "存在" not in response
    assert "不存在" not in response


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
