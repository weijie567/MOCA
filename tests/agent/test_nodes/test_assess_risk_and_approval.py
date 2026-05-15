from __future__ import annotations

import pytest

from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from tests.agent.conftest import FakeLLM


@pytest.mark.asyncio
async def test_chinese_full_refund_delivered_order_matches_high_risk(monkeypatch, base_state):
    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "low",
                "risk_reason": "llm missed deterministic rule",
                "approval_required": False,
                "rule_ref": "LR-01",
            }
        ),
    )
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "建议全额退款",
            "reasoning_summary": "用户已签收后申请全额退款。",
            "evidence_refs": [],
            "confidence": 0.8,
            "risk_level": "low",
            "missing_info": [],
        },
        "business_context": {"order": {"status": "delivered"}},
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["risk_assessment"]["risk_level"] == "high"
    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-02"


@pytest.mark.asyncio
async def test_policy_qa_does_not_treat_rule_threshold_as_compensation_amount(monkeypatch, base_state):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("policy_qa should use deterministic low-risk assessment")

    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingLLM())
    state = {
        **base_state,
        "current_intent": "policy_qa",
        "recommendation_draft": {
            "recommended_action": "解释规则：金额超过3000元进入人工复核",
            "reasoning_summary": "这是规则说明，不是本次补偿或退款动作。",
            "evidence_refs": [],
            "confidence": 0.95,
            "risk_level": "low",
            "missing_info": [],
        },
        "business_context": {"order": {"status": "delivered"}},
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["risk_assessment"]["risk_level"] == "low"
    assert result["risk_assessment"]["approval_required"] is False
