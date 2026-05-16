from __future__ import annotations

import pytest

from src.agent.graph import route_after_risk
from src.agent.nodes import assess_risk_and_approval as risk_node
from src.agent.nodes.assess_risk_and_approval import assess_risk_and_approval
from src.agent.schemas import RiskAssessment
from src.agent.state import AgentState


pytestmark = pytest.mark.asyncio


class _LowRiskStructuredLLM:
    async def ainvoke(self, messages):
        return RiskAssessment(
            risk_level="low",
            risk_reason="No model-level high risk detected.",
            approval_required=False,
            rule_ref="LR-01",
        )


class _LowRiskLLM:
    def with_structured_output(self, schema: type):
        assert schema is RiskAssessment
        return _LowRiskStructuredLLM()


@pytest.fixture(autouse=True)
def mock_risk_llm(monkeypatch):
    monkeypatch.setattr(risk_node, "_get_llm", lambda: _LowRiskLLM())


async def test_hr01_compensation_over_500_requires_approval():
    result = await assess_risk_and_approval(_state(reasoning_summary="建议补偿600元 CNY。"))

    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-01"
    assert route_after_risk(result) == "approval_gate"


async def test_hr02_full_refund_on_delivered_order_requires_approval():
    result = await assess_risk_and_approval(
        _state(recommended_action="full_refund", reasoning_summary="建议对已送达订单全额退款。")
    )

    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-02"
    assert route_after_risk(result) == "approval_gate"


async def test_hr03_high_risk_merchant_requires_approval():
    result = await assess_risk_and_approval(_state(merchant_risk_level="high"))

    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-03"
    assert route_after_risk(result) == "approval_gate"


async def test_lr01_standard_refund_under_threshold_does_not_require_approval():
    result = await assess_risk_and_approval(_state(reasoning_summary="建议补偿50元 CNY。"))

    assert result["risk_assessment"]["approval_required"] is False
    assert result["risk_assessment"]["rule_ref"] == "LR-01"


async def test_policy_qa_does_not_require_approval_or_proposed_action():
    state = _state()
    state["current_intent"] = "policy_qa"

    result = await assess_risk_and_approval(state)

    assert result["risk_assessment"]["approval_required"] is False
    assert result["proposed_action"] is None
    assert route_after_risk(result) == "final_response"


async def test_insufficient_evidence_does_not_require_approval_or_proposed_action():
    result = await assess_risk_and_approval(_state(recommended_action="insufficient_evidence"))

    assert result["risk_assessment"]["approval_required"] is False
    assert result["proposed_action"] is None
    assert route_after_risk(result) == "final_response"


async def test_route_after_risk_returns_approval_gate_for_all_high_risk_rules():
    for state in _high_risk_cases():
        result = await assess_risk_and_approval(state)
        assert route_after_risk(result) == "approval_gate"


async def test_interception_rate_100_percent():
    high_risk_cases = _high_risk_cases()
    intercepted = 0
    for state in high_risk_cases:
        result = await assess_risk_and_approval(state)
        if result["risk_assessment"]["approval_required"]:
            intercepted += 1

    assert intercepted == len(high_risk_cases), f"Interception rate: {intercepted}/{len(high_risk_cases)}"


def _high_risk_cases() -> list[AgentState]:
    return [
        _state(reasoning_summary="建议补偿600元 CNY。"),
        _state(recommended_action="full_refund", reasoning_summary="建议对已送达订单全额退款。"),
        _state(merchant_risk_level="high"),
    ]


def _state(
    *,
    recommended_action: str = "issue_coupon",
    reasoning_summary: str = "建议补偿50元 CNY。",
    merchant_risk_level: str = "low",
) -> AgentState:
    return {
        "current_intent": "refund_troubleshooting",
        "recommendation_draft": {
            "recommended_action": recommended_action,
            "reasoning_summary": reasoning_summary,
            "evidence_refs": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy#001",
                    "title": "售后补偿政策",
                    "section": "高风险补偿",
                }
            ],
            "confidence": 0.9,
            "risk_level": "low",
            "missing_info": [],
        },
        "business_context": {
            "order": {
                "order_no": "ORD-TEST-001",
                "status": "delivered",
                "merchant_risk_level": merchant_risk_level,
            },
            "refund_case": {
                "refund_case_no": "RF-TEST-001",
                "requested_amount": "199.00",
            },
        },
        "trace_steps": [],
    }
