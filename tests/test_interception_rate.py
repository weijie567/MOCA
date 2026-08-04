from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.agent.graph import route_after_risk
from src.agent.nodes import risk_gate as risk_gate_module
from src.agent.nodes.risk_gate import risk_gate
from src.agent.schemas import RiskAssessment
from src.agent.state import AgentState


pytestmark = pytest.mark.asyncio


async def test_phase58_interception_rate_patches_canonical_risk_gate_module() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    legacy_alias = "".join(("risk_", "node"))

    assert legacy_alias not in source
    assert "from src.agent.nodes import risk_gate as risk_gate_module" in source


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
    monkeypatch.setattr(risk_gate_module, "_get_llm", lambda: _LowRiskLLM())


async def test_hr01_compensation_over_500_requires_approval():
    result = await _assess(_state(reasoning_summary="建议补偿600元 CNY。"))

    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-01"
    assert result["proposed_action"]["action_type"] == "issue_coupon"
    assert route_after_risk(result) == "approval_gate"


async def test_hr02_full_refund_on_delivered_order_requires_approval():
    result = await _assess(_state(recommended_action="full_refund", reasoning_summary="建议对已送达订单全额退款。"))

    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-02"
    assert route_after_risk(result) == "approval_gate"


async def test_hr03_high_risk_merchant_requires_approval():
    result = await _assess(_state(merchant_risk_level="high"))

    assert result["risk_assessment"]["approval_required"] is True
    assert result["risk_assessment"]["rule_ref"] == "HR-03"
    assert route_after_risk(result) == "approval_gate"


async def test_lr01_standard_refund_under_threshold_does_not_require_approval():
    result = await _assess(_state(reasoning_summary="建议补偿50元 CNY。"))

    assert result["risk_assessment"]["approval_required"] is False
    assert result["risk_assessment"]["rule_ref"] == "LR-01"


async def test_policy_qa_does_not_require_approval_or_proposed_action():
    state = _state()
    state["current_intent"] = "policy_qa"

    result = await _assess(state)

    assert result["risk_assessment"]["approval_required"] is False
    assert result["proposed_action"] is None
    assert route_after_risk(result) == "final_response"


async def test_insufficient_evidence_does_not_require_approval_or_proposed_action():
    result = await _assess(_state(recommended_action="insufficient_evidence"))

    assert result["risk_assessment"]["approval_required"] is False
    assert result["proposed_action"] is None
    assert route_after_risk(result) == "final_response"


async def test_live_freeform_rejection_action_type_is_canonical():
    result = await _assess(
        _state(
            recommended_action="拒绝600元补偿请求。根据补偿规则，订单实付金额599元对应的最高体验补偿标准为50元。",
            reasoning_summary="用户请求补偿600元 CNY。",
        )
    )

    assert result["risk_assessment"]["risk_disposition"] == "manual_review"
    assert result["risk_assessment"]["approval_required"] is False
    assert result["proposed_action"] is None
    assert route_after_risk(result) == "final_response"


async def test_route_after_risk_returns_approval_gate_for_all_high_risk_rules():
    for state in _high_risk_cases():
        result = await _assess(state)
        assert route_after_risk(result) == "approval_gate"


async def test_interception_rate_100_percent():
    high_risk_cases = _high_risk_cases()
    intercepted = 0
    for state in high_risk_cases:
        result = await _assess(state)
        if result["risk_assessment"]["approval_required"]:
            intercepted += 1

    assert intercepted == len(high_risk_cases), f"Interception rate: {intercepted}/{len(high_risk_cases)}"


async def _assess(state: AgentState) -> AgentState:
    result = await risk_gate(state)
    return {**state, **result}


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
    tenant_id = "tenant-001"
    fact_ref = _business_fact_ref(tenant_id)
    evidence_ref = _evidence_ref(tenant_id)
    return {
        "tenant_id": tenant_id,
        "user_id": "user-001",
        "thread_id": "thread-001",
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
                "merchant_id": "merchant-001",
            },
            "refund_case": {
                "id": "RF-TEST-001",
                "refund_case_no": "RF-TEST-001",
                "requested_amount": "199.00",
                "merchant_id": "merchant-001",
            },
            "business_fact_refs": [fact_ref],
        },
        "claim_verification_bundle": _allowing_claim_bundle(evidence_ref, fact_ref),
        "trace_steps": [],
    }


def _evidence_ref(tenant_id: str) -> dict:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": tenant_id,
        "evidence_id": "refund-policy/chunk-001@v3",
        "doc_key": "refund-policy",
        "chunk_id": "chunk-001",
        "policy_version": "v3",
        "text_hash": "sha256:" + "a" * 64,
        "retrieved_at": "2026-06-29T00:00:00.000Z",
        "retrieval_config_version": "retrieval.v1",
        "score": 0.91,
        "rank": 1,
    }


def _business_fact_ref(tenant_id: str) -> dict:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": tenant_id,
        "source_system": "moca_demo",
        "resource_type": "refund_case",
        "resource_id": "RF-TEST-001",
        "resource_version": "v1",
        "data_freshness_at": datetime(2026, 6, 29, 0, 0, tzinfo=UTC).isoformat(),
        "retrieved_at": datetime(2026, 6, 29, 0, 1, tzinfo=UTC).isoformat(),
    }


def _allowing_claim_bundle(evidence_ref: dict, fact_ref: dict) -> dict:
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": "verified",
        "route": "continue",
        "claim_results": [
            {
                "schema_version": "claim_verification_result.v1",
                "claim_id": "claim-action-1",
                "claim_type": "action_recommendation",
                "support_status": "supported",
                "supporting_evidence_refs": [evidence_ref],
                "business_fact_refs": [fact_ref],
                "rule_checks": [],
                "semantic_review_status": "not_needed",
                "allows_user_visible_claim": True,
                "allows_action_recommendation": True,
            }
        ],
        "blocked_claims": [],
        "safe_support_refs": [evidence_ref],
        "reason_codes": ["verified_claim"],
        "verifier_policy_version": "claim-verifier.v1",
    }
