from __future__ import annotations

import pytest

from src.agent.nodes.final_response import final_response


FORBIDDEN_DEMO_SUCCESS_PHRASES = (
    "waiting for final issuance",
    "coupon issued",
    "refund completed",
    "ticket closed",
    "issued coupon",
    "refunded",
    "closed ticket",
    "external success",
    "等待最终发放",
    "已发券",
    "已发放",
    "已退款",
    "已关闭工单",
    "执行成功",
)
FALSE_EVIDENCE_CLAIM_PHRASES = (
    "建议按已检索到的政策依据处理",
    "根据已检索到的政策依据",
    "已根据当前知识库证据",
    "依据：",
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


def _assert_no_false_evidence_claim(text: str) -> None:
    assert not any(phrase in text for phrase in FALSE_EVIDENCE_CLAIM_PHRASES)


def _metric_fact(
    *,
    metric_id: str = "refund_case_count",
    status: str = "ok",
    display_value: str = "3",
    value: float | None = 3,
    rate: float | None = None,
    numerator: int | None = None,
    denominator: int | None = None,
    unit: str = "count",
    formula: str = "count refund cases by created_at in authorized merchant scope",
    caveats: list[str] | None = None,
    no_leak_status: str = "not_applicable",
) -> dict:
    return {
        "metric_id": metric_id,
        "status": status,
        "value": value,
        "rate": rate,
        "numerator": numerator,
        "denominator": denominator,
        "unit": unit,
        "display_value": display_value,
        "scope": {
            "tenant_id": "TENANT-SHOULD-NOT-LEAK",
            "merchant_ids": ["MERCHANT-SHOULD-NOT-LEAK"],
            "scope_label": "当前权限范围",
        },
        "time_range": {
            "start_at": "2026-07-09T00:00:00+08:00",
            "end_at": "2026-07-10T00:00:00+08:00",
            "preset": "today",
            "timezone": "Asia/Shanghai",
        },
        "filters": {"merchant_id": None, "status_filter": ["requested"]},
        "freshness": {
            "data_freshness_at": "2026-07-09T04:00:00+00:00",
            "computed_at": "2026-07-09T04:01:00+00:00",
            "source_system": "business_fact_service",
        },
        "formula": formula,
        "caveats": caveats or [],
        "no_leak_status": no_leak_status,
    }


def _metric_state(base_state: dict, metric: dict) -> dict:
    return {
        **base_state,
        "primary_intent": "business_metric_query",
        "current_intent": "business_metric_query",
        "requested_operation": "read_status",
        "business_context": {
            "facts": {"business_metric": metric},
            "status": "complete",
            "business_fact_refs": [{"resource_type": "business_metric", "resource_id": metric["metric_id"]}],
            "missing_required_facts": [],
            "errors": [],
        },
        "recommendation_draft": None,
    }


def _state_with_deferred(state: dict) -> dict:
    return {
        **state,
        "deferred_steps": [
            {
                "step_id": "s2",
                "intent": "policy_qa",
                "operation": "read_status",
                "entities": {"raw": "must-not-render"},
                "depends_on": [],
                "relation": "parallel",
            },
            {
                "step_id": "s3",
                "intent": "ticket_reply_draft",
                "operation": "draft_reply",
                "entities": {"ticket_id": "TKT-SECRET"},
                "depends_on": ["s1"],
                "relation": "dependency",
            },
        ],
    }


def _assert_deferred_visible(result: dict) -> None:
    assert "我还注意到你想继续处理" in result["final_response"]
    assert "政策问题查询（查询）" in result["final_response"]
    assert "工单回复草稿（拟回复）" in result["final_response"]
    assert "要我接着做哪一项吗" in result["final_response"]
    assert "TKT-SECRET" not in result["final_response"]
    final_output = (result.get("llm_outputs") or {}).get("final_response")
    if final_output is not None:
        assert result["final_response"] == final_output["response_text"]


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
async def test_final_response_trusts_allowed_claim_bundle_over_legacy_allow_fields(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "符合补偿规则。",
            "evidence_refs": [],
        },
        "risk_assessment": {"approval_required": True, "risk_reason": "Compensation amount exceeds threshold"},
        "claim_verification_bundle": {
            "overall_status": "verified",
            "route": "continue",
            "blocked_claims": [],
            "reason_codes": [],
        },
        "blocked_claims": [],
        "verification_route": "allow",
        "verifier_status": "verified",
        "verifier_reason_codes": [],
        "approval_result": {"decision": "approve"},
        "action_draft": {"draft_id": "draft-compat-001", "status": "draft_created"},
        "draft_outcome": _draft_outcome("draft-compat-001"),
        "action_result": {"status": "draft_created", "data": {"draft_id": "draft-compat-001"}, "error": {}},
    }

    result = await final_response(state)

    assert "人工复核" not in result["final_response"]
    _assert_draft_created_not_executed(result["final_response"], "draft-compat-001")
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"


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
    _assert_no_false_evidence_claim(result["final_response"])
    assert result["llm_outputs"]["final_response"]["evidence_citations"] == []
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"


@pytest.mark.asyncio
async def test_metric_count_response_is_number_first_with_scope_time_filter_freshness(base_state):
    state = _metric_state(base_state, _metric_fact())
    state["recommendation_draft"] = {
        "recommended_action": "insufficient_evidence",
        "missing_info": ["No relevant policy found"],
        "evidence_refs": [],
    }

    result = await final_response(state)

    assert result["final_response"].startswith("3")
    assert "范围：当前权限范围" in result["final_response"]
    assert "时间：today" in result["final_response"]
    assert "筛选：status=requested" in result["final_response"]
    assert "新鲜度：2026-07-09T04:00:00+00:00" in result["final_response"]
    _assert_no_false_evidence_claim(result["final_response"])
    output = result["llm_outputs"]["final_response"]
    assert output["response_kind"] == "metric_answer"
    assert output["metric"]["metric_id"] == "refund_case_count"
    assert output["metric"]["metric_label"] == "退款单数"
    assert output["metric"]["display_value"] == "3"
    assert output["metric"]["scope_label"] == "当前权限范围"
    assert "TENANT-SHOULD-NOT-LEAK" not in str(output["metric"])
    assert "MERCHANT-SHOULD-NOT-LEAK" not in str(output["metric"])


@pytest.mark.asyncio
async def test_metric_refund_rate_response_shows_percentage_and_formula(base_state):
    metric = _metric_fact(
        metric_id="merchant_refund_rate",
        display_value="12.5%",
        value=None,
        rate=0.125,
        numerator=1,
        denominator=8,
        unit="percentage",
        formula="orders with refund cases / total orders",
    )

    result = await final_response(_metric_state(base_state, metric))

    assert result["final_response"].startswith("12.5%")
    assert "1/8" in result["final_response"]
    assert "orders with refund cases / total orders" in result["final_response"]
    _assert_no_false_evidence_claim(result["final_response"])


@pytest.mark.asyncio
async def test_metric_coupon_count_discloses_demo_record_caveat(base_state):
    metric = _metric_fact(
        metric_id="coupon_record_count",
        display_value="2",
        value=2,
        caveats=["MOCA demo action draft records, not external delivery success."],
    )

    result = await final_response(_metric_state(base_state, metric))

    assert result["final_response"].startswith("2")
    assert "MOCA 演示系统" in result["final_response"]
    assert "不是外部优惠券实际发放成功数" in result["final_response"]


@pytest.mark.asyncio
async def test_metric_permission_denied_uses_no_existence_leak_wording(base_state):
    metric = _metric_fact(
        status="permission_denied",
        display_value="不可提供",
        value=None,
        no_leak_status="scope_denied_no_existence_leak",
    )
    metric["filters"]["merchant_id"] = "MERCHANT-SHOULD-NOT-LEAK"

    result = await final_response(_metric_state(base_state, metric))

    assert result["final_response"] == "当前权限范围内无法提供该商户指标。"
    assert "MERCHANT-SHOULD-NOT-LEAK" not in result["final_response"]
    output = result["llm_outputs"]["final_response"]
    assert output["response_kind"] == "metric_answer"
    assert output["metric"]["safe_reason"] == "scope_denied_no_existence_leak"
    assert "MERCHANT-SHOULD-NOT-LEAK" not in str(output["metric"])


@pytest.mark.asyncio
async def test_metric_refund_rate_zero_denominator_is_non_computable_not_zero_percent(base_state):
    metric = _metric_fact(
        metric_id="merchant_refund_rate",
        status="non_computable",
        display_value="N/A",
        value=None,
        rate=None,
        numerator=0,
        denominator=0,
        unit="percentage",
        formula="orders with refund cases / total orders",
    )

    result = await final_response(_metric_state(base_state, metric))

    assert result["final_response"].startswith("暂无可计算退款率")
    assert "所选权限范围和时间范围内没有订单" in result["final_response"]
    assert "0%" not in result["final_response"]


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


@pytest.mark.asyncio
async def test_final_response_preserves_clarification_text_without_internal_debug_fields(base_state):
    question = "我需要订单号、退款单号或工单号来定位具体售后对象；请提供其中至少一个。"
    result = await final_response(
        {
            **base_state,
            "clarification_request": {
                "reason": "missing_required_slots",
                "questions": [question],
                "blocked_nodes": ["investigate", "slot_resolution_gate", "approval_gate"],
                "resume_policy": "same_thread_only",
            },
            "routing_hints": {
                "clarification_reason": "missing_required_slots",
                "blocked_nodes": ["investigate", "debug_trace"],
            },
            "node_errors": [{"node": "slot_resolution_gate", "error": "permission_denied debug_trace"}],
        }
    )

    assert result["final_response"] == question
    assert "investigate" not in result["final_response"]
    assert "slot_resolution_gate" not in result["final_response"]
    assert "routing_hints" not in result["final_response"]
    assert "debug_trace" not in result["final_response"]
    assert "permission_denied" not in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_decorates_clarification_branch(base_state):
    result = await final_response(
        _state_with_deferred(
            {
                **base_state,
                "clarification_request": {
                    "reason": "missing_required_slots",
                    "questions": ["请提供订单号或退款单号。"],
                },
            }
        )
    )

    assert result["final_response"].startswith("请提供订单号或退款单号。")
    assert result["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"
    _assert_deferred_visible(result)


@pytest.mark.asyncio
async def test_final_response_decorates_manual_review_branch(base_state):
    result = await final_response(
        _state_with_deferred(
            {
                **base_state,
                "recommendation_draft": {
                    "recommended_action": "issue_coupon",
                    "reasoning_summary": "需要补偿。",
                    "missing_info": ["缺少政策证据"],
                    "evidence_refs": [],
                },
                "rag_verification": {
                    "overall_outcome": "blocked",
                    "route": {"route": "manual_review", "selected_by": "backend", "model_selected": False},
                    "reason_codes": ["missing_citation"],
                },
            }
        )
    )

    assert "人工复核" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "manual_review"
    _assert_deferred_visible(result)


@pytest.mark.asyncio
async def test_final_response_decorates_retrieval_error_branch_without_llm_output(base_state):
    result = await final_response(
        _state_with_deferred(
            {
                **base_state,
                "recommendation_draft": {
                    "recommended_action": "retrieval_error",
                    "missing_info": ["vector store timeout"],
                },
            }
        )
    )

    assert "系统暂时无法检索政策依据" in result["final_response"]
    assert "final_response" not in (result.get("llm_outputs") or {})
    _assert_deferred_visible(result)


@pytest.mark.asyncio
async def test_final_response_decorates_safety_snapshot_blocked_branch(base_state):
    result = await final_response(
        _state_with_deferred(
            {
                **base_state,
                "final_response": "操作需要人工复核，当前未创建可执行审批或动作草稿。",
                "safety_snapshot_verified": False,
                "recommendation_draft": {
                    "recommended_action": "issue_coupon",
                    "reasoning_summary": "符合补偿规则。",
                    "evidence_refs": [],
                },
                "risk_assessment": {"risk_level": "manual_review", "approval_required": False},
            }
        )
    )

    assert result["final_response"].startswith("操作需要人工复核")
    assert result["llm_outputs"]["final_response"]["final_status"] == "error"
    _assert_deferred_visible(result)


@pytest.mark.asyncio
async def test_final_response_decorates_business_fact_branch(base_state):
    result = await final_response(
        _state_with_deferred(
            {
                **base_state,
                "primary_intent": "order_status_inquiry",
                "requested_operation": "read_status",
                "business_context": {
                    "facts": {
                        "order": {
                            "order_no": "ORD-2024-001",
                            "status": "pending",
                            "item_name": "蓝牙降噪耳机 Pro",
                        }
                    }
                },
                "recommendation_draft": None,
            }
        )
    )

    assert "当前查询结果" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"
    _assert_deferred_visible(result)


@pytest.mark.asyncio
async def test_final_response_decorates_completed_response_branch(base_state):
    result = await final_response(
        _state_with_deferred(
            {
                **base_state,
                "recommendation_draft": {
                    "recommended_action": "解释退款规则",
                    "reasoning_summary": "商家需要在规定时效内处理退款。",
                    "evidence_refs": [],
                },
                "risk_assessment": {"approval_required": False},
            }
        )
    )

    assert "建议：解释退款规则" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"
    _assert_deferred_visible(result)


@pytest.mark.asyncio
async def test_final_response_complaint_folded_note_visible_without_deferred_steps(base_state):
    result = await final_response(
        {
            **base_state,
            "recommendation_draft": {
                "recommended_action": "解释补偿规则",
                "reasoning_summary": "按当前证据给出建议。",
                "evidence_refs": [],
            },
            "risk_assessment": {"approval_required": False},
            "deferred_steps": [],
            "classification_trace": {
                "plan_normalization": ["modifier_folded:complaint_as_severity"]
            },
        }
    )

    assert "投诉情绪" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["response_text"] == result["final_response"]


@pytest.mark.asyncio
async def test_final_response_handles_small_talk_without_default_policy_template(base_state):
    result = await final_response(
        {
            **base_state,
            "primary_intent": "small_talk",
            "requested_operation": "advise",
            "recommendation_draft": None,
        }
    )

    assert "你好" in result["final_response"]
    assert "订单号、退款单号或工单号" in result["final_response"]
    _assert_no_false_evidence_claim(result["final_response"])
    assert "政策证据" not in result["final_response"]
    assert result["llm_outputs"]["final_response"]["evidence_citations"] == []
    assert result["llm_outputs"]["final_response"]["direct_response_intent"] == "small_talk"


@pytest.mark.asyncio
async def test_final_response_handles_legacy_aggregate_order_query_as_time_clarification(base_state):
    result = await final_response(
        {
            **base_state,
            "primary_intent": "unsupported",
            "requested_operation": "advise",
            "routing_hints": {"unsupported_reason": "aggregate_order_query"},
            "recommendation_draft": None,
        }
    )

    assert "要统计订单数" in result["final_response"]
    assert "今天、本周、本月、本季度、今年" in result["final_response"]
    assert "不支持统计订单总数" not in result["final_response"]
    assert "具体订单号" not in result["final_response"]
    _assert_no_false_evidence_claim(result["final_response"])
    assert result["llm_outputs"]["final_response"]["evidence_citations"] == []
    assert result["llm_outputs"]["final_response"]["direct_response_intent"] == "unsupported"


@pytest.mark.asyncio
async def test_final_response_handles_generic_unsupported_without_irrelevant_identifier_prompt(base_state):
    result = await final_response(
        {
            **base_state,
            "primary_intent": "unsupported",
            "requested_operation": "advise",
            "recommendation_draft": None,
        }
    )

    assert "当前只支持商家售后相关" in result["final_response"]
    assert "政策问答" in result["final_response"]
    assert "订单/退款/工单查询" in result["final_response"]
    assert "补偿建议" in result["final_response"]
    assert "请提供订单号" not in result["final_response"]
    _assert_no_false_evidence_claim(result["final_response"])
    assert result["llm_outputs"]["final_response"]["evidence_citations"] == []
    assert result["llm_outputs"]["final_response"]["direct_response_intent"] == "unsupported"


@pytest.mark.asyncio
async def test_clarification_and_business_fact_only_paths_do_not_claim_policy_evidence(base_state):
    states = [
        {
            **base_state,
            "clarification_request": {
                "reason": "missing_required_slots",
                "questions": ["我需要订单号、退款单号或工单号来定位具体售后对象；请提供其中至少一个。"],
            },
        },
        {
            **base_state,
            "primary_intent": "order_status_inquiry",
            "requested_operation": "read_status",
            "business_context": {
                "facts": {
                    "order": {
                        "order_no": "ORD-2024-001",
                        "status": "pending",
                    }
                }
            },
            "recommendation_draft": None,
        },
    ]

    for state in states:
        result = await final_response(state)

        _assert_no_false_evidence_claim(result["final_response"])
        assert result["llm_outputs"]["final_response"]["evidence_citations"] == []


@pytest.mark.asyncio
async def test_completed_response_without_evidence_refs_uses_neutral_reasoning(base_state):
    result = await final_response(
        {
            **base_state,
            "recommendation_draft": {
                "recommended_action": "先核对退款诉求和订单状态",
                "evidence_refs": [],
            },
            "risk_assessment": {"approval_required": False},
        }
    )

    assert "建议：先核对退款诉求和订单状态" in result["final_response"]
    _assert_no_false_evidence_claim(result["final_response"])
    assert result["llm_outputs"]["final_response"]["evidence_citations"] == []
