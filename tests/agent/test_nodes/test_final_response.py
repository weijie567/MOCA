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
