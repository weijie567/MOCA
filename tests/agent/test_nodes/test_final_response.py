from __future__ import annotations

import pytest

from src.agent.nodes.final_response import final_response


FORBIDDEN_DEMO_SUCCESS_PHRASES = (
    "waiting for final issuance",
    "issued coupon",
    "refunded",
    "closed ticket",
    "external success",
    "等待最终发放",
    "已发放",
    "已退款",
    "已关闭工单",
    "执行成功",
)


def _draft_outcome(draft_id: str, *, external_side_effect: bool = False) -> dict:
    return {
        "schema_version": "draft_outcome.v1",
        "draft_id": draft_id,
        "status": "not_executed_demo",
        "external_side_effect": external_side_effect,
    }


def _assert_draft_created_not_executed(text: str, draft_id: str) -> None:
    assert draft_id in text
    assert "草稿" in text
    assert "未执行" in text
    assert "优惠券" in text
    assert "退款" in text
    assert "工单" in text
    assert "外部动作" in text
    assert not any(phrase in text for phrase in FORBIDDEN_DEMO_SUCCESS_PHRASES)


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
                    "raw_provider_payload": {"private": "do-not-expose"},
                }
            ],
        },
        "evidence_refs": [
            {
                "evidence_id": "refund_policy/refund_policy_006@v1",
                "doc_key": "refund_policy",
                "chunk_id": "refund_policy_006",
                "title": "退款规则",
                "section": "超时自动退款",
                "score": 0.91,
                "tenant_id": "tenant-should-not-expose",
            }
        ],
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
    assert result["trace_steps"][-1]["evidence_refs"] == [
        {
            "evidence_id": "refund_policy/refund_policy_006@v1",
            "doc_key": "refund_policy",
            "chunk_id": "refund_policy_006",
            "title": "退款规则",
            "section": "超时自动退款",
            "score": 0.91,
        }
    ]


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
        "action_draft": {"draft_id": "draft-001", "status": "draft_created"},
        "draft_outcome": _draft_outcome("draft-001"),
        "action_result": {"status": "draft_created", "data": {"draft_id": "draft-001"}, "error": {}},
    }

    result = await final_response(state)

    assert "审批结果" in result["final_response"]
    _assert_draft_created_not_executed(result["final_response"], "draft-001")
    assert result["llm_outputs"]["final_response"]["approval_context"] is not None


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

    assert "草稿创建失败" in result["final_response"]
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
        "action_draft": {"draft_id": "draft-002", "status": "draft_created"},
        "draft_outcome": _draft_outcome("draft-002"),
        "action_result": {"status": "draft_created", "data": {"draft_id": "draft-002"}, "error": {}},
    }

    result = await final_response(state)

    assert "无需审批" in result["final_response"]
    _assert_draft_created_not_executed(result["final_response"], "draft-002")


@pytest.mark.asyncio
async def test_final_response_does_not_treat_action_result_success_without_draft_outcome_as_success(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": True, "risk_reason": "Compensation amount exceeds threshold"},
        "approval_result": {"decision": "approve"},
        "action_result": {"status": "success", "data": {"draft_id": "legacy-success"}, "error": {}},
    }

    result = await final_response(state)

    assert "legacy-success" not in result["final_response"]
    assert "草稿已创建" not in result["final_response"]
    assert FORBIDDEN_DEMO_SUCCESS_PHRASES[5] not in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_rejects_side_effecting_draft_outcome_as_success(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": False},
        "approval_result": None,
        "action_draft": {"draft_id": "draft-side-effect", "status": "draft_created"},
        "draft_outcome": _draft_outcome("draft-side-effect", external_side_effect=True),
        "action_result": {"status": "success", "data": {"draft_id": "draft-side-effect"}, "error": {}},
    }

    result = await final_response(state)

    assert "draft-side-effect" not in result["final_response"]
    assert "草稿已创建" not in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_demo_draft_paths_have_no_external_success_wording(base_state):
    states = [
        {
            **base_state,
            "recommendation_draft": {
                "recommended_action": "issue_coupon",
                "reasoning_summary": "符合补偿规则。",
                "evidence_refs": [],
            },
            "risk_assessment": {"approval_required": True},
            "approval_result": {"decision": "approve"},
            "action_draft": {"draft_id": "draft-approved", "status": "draft_created"},
            "draft_outcome": _draft_outcome("draft-approved"),
            "action_result": {"status": "draft_created", "data": {"draft_id": "draft-approved"}, "error": {}},
        },
        {
            **base_state,
            "recommendation_draft": {
                "recommended_action": "issue_coupon",
                "reasoning_summary": "符合补偿规则。",
                "evidence_refs": [],
            },
            "risk_assessment": {"approval_required": False},
            "approval_result": None,
            "action_draft": {"draft_id": "draft-auto", "status": "draft_created"},
            "draft_outcome": _draft_outcome("draft-auto"),
            "action_result": {"status": "draft_created", "data": {"draft_id": "draft-auto"}, "error": {}},
        },
    ]

    for state in states:
        result = await final_response(state)

        assert not any(phrase in result["final_response"] for phrase in FORBIDDEN_DEMO_SUCCESS_PHRASES)


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
            "facts": {
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
async def test_final_response_renders_order_status_business_fact_response_without_default_recommendation(base_state):
    state = {
        **base_state,
        "primary_intent": "order_status_inquiry",
        "current_intent": "order_status_inquiry",
        "requested_operation": "read_status",
        "business_context": {
            "facts": {
                "order": {
                    "order_no": "ORD-2024-001",
                    "status": "pending",
                    "item_name": "蓝牙降噪耳机 Pro",
                    "amount": "599.00",
                    "currency": "CNY",
                    "relation_hints": {
                        "has_active_refund": True,
                        "has_open_ticket": True,
                    },
                }
            },
            "status": "complete",
            "missing_required_facts": [],
            "errors": [],
        },
        "recommendation_draft": None,
    }

    result = await final_response(state)

    assert "当前查询结果" in result["final_response"]
    assert "ORD-2024-001" in result["final_response"]
    assert "状态 pending" in result["final_response"]
    assert "蓝牙降噪耳机 Pro" in result["final_response"]
    assert "存在关联退款" in result["final_response"]
    assert "存在未关闭工单" in result["final_response"]
    assert "建议按已检索到的政策依据处理" not in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"


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
