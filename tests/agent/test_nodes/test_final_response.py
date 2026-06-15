from __future__ import annotations

import pytest

from src.agent.nodes.final_response import final_response


@pytest.mark.asyncio
async def test_final_response_uses_deterministic_citation_template(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "解释退款超时规则",
            "reasoning_summary": "商家需要在规定时效内处理退款。",
            "evidence_refs": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_006",
                    "title": "退款规则",
                    "section": "超时自动退款",
                }
            ],
        },
        "risk_assessment": {
            "risk_level": "low",
            "risk_reason": "Policy explanation only.",
            "approval_required": False,
            "rule_ref": "LR-01",
        },
    }

    result = await final_response(state)

    assert "根据 refund_policy / refund_policy_006" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"
    assert result["trace_steps"][-1]["model_name"] == "deterministic-template"


@pytest.mark.asyncio
async def test_final_response_mentions_approved_action_draft(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": True, "risk_reason": "Compensation amount exceeds threshold"},
        "approval_result": {"decision": "approve"},
        "action_result": {"status": "success", "data": {"draft_id": "draft-001"}, "error": {}},
    }

    result = await final_response(state)

    assert "审批结果" in result["final_response"]
    assert "draft-001" in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_mentions_rejection_reason(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": True, "risk_reason": "Compensation amount exceeds threshold"},
        "approval_result": {"decision": "reject", "reason": "证据不足"},
        "action_result": None,
    }

    result = await final_response(state)

    assert "拒绝" in result["final_response"]
    assert "证据不足" in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_mentions_action_failure_after_approval(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": True, "risk_reason": "Compensation amount exceeds threshold"},
        "approval_result": {"decision": "approve"},
        "action_result": {"status": "error", "data": {}, "error": {"message": "draft write failed"}},
    }

    result = await final_response(state)

    assert "执行失败" in result["final_response"]
    assert "draft write failed" in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_mentions_direct_action_without_approval(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": False},
        "approval_result": None,
        "action_result": {"status": "success", "data": {"draft_id": "draft-002"}, "error": {}},
    }

    result = await final_response(state)

    assert "无需审批" in result["final_response"]
    assert "draft-002" in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_preserves_snapshot_fail_closed_message(base_state):
    response_text = "操作需要人工复核，当前未创建可执行审批或动作草稿。"
    state = {
        **base_state,
        "final_response": response_text,
        "safety_snapshot_verified": False,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {
            "risk_level": "manual_review",
            "approval_required": False,
            "risk_reason": "Action safety snapshot could not be verified.",
        },
    }

    result = await final_response(state)

    assert result["final_response"] == response_text
    assert result["llm_outputs"]["final_response"]["final_status"] == "error"
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_final_response_preserves_order_facts_when_policy_evidence_is_missing(base_state):
    state = {
        **base_state,
        "business_context": {
            "order": {
                "order_no": "ORD-2024-001",
                "status": "delivered",
                "item_name": "测试商品",
                "amount": "199.00",
                "currency": "CNY",
                "relation_hints": {
                    "has_active_refund": True,
                    "has_open_ticket": False,
                },
            }
        },
        "recommendation_draft": {
            "recommended_action": "insufficient_evidence",
            "reasoning_summary": "No policy evidence.",
            "evidence_refs": [],
            "confidence": 0.0,
            "risk_level": "low",
            "missing_info": ["No relevant policy found"],
        },
    }

    result = await final_response(state)

    assert "已查询到订单信息" in result["final_response"]
    assert "ORD-2024-001" in result["final_response"]
    assert "测试商品" in result["final_response"]
    assert "关于退款风险" in result["final_response"]
    assert "没有找到足够证据" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_final_response_preserves_clarification_response(base_state):
    result = await final_response(
        {
            **base_state,
            "clarification_request": {
                "reason": "missing_required_information",
                "missing": ["case_identifier"],
            },
            "final_response": "Could you provide a bit more information so I can help?",
        }
    )

    assert result["final_response"] == "Could you provide a bit more information so I can help?"
    assert result["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_final_response_builds_safe_clarification_from_request(base_state):
    result = await final_response(
        {
            **base_state,
            "clarification_request": {
                "reason": "missing_required_slots",
                "questions": ["请提供订单号或退款单号。"],
                "blocked_nodes": ["investigate", "action_draft"],
                "resume_policy": "same_thread_only",
            },
            "approval_result": {"decision": "approve"},
            "action_result": {"status": "error", "error": {"message": "permission_denied"}},
            "node_errors": [{"error": "FORBIDDEN stack trace"}],
        }
    )

    assert result["final_response"] == "请提供订单号或退款单号。"
    assert "permission_denied" not in result["final_response"]
    assert "FORBIDDEN" not in result["final_response"]
    assert "审批结果" not in result["final_response"]
