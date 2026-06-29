from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.agent.context import PromptAssembly
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.approvals.schemas import AutoAllowedActionBindingV1, RiskDecisionV1
from src.tools.contracts import BusinessFactRefV1
from tests.agent.conftest import FakeLLM


SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_APPROVAL_BODY = "SHOULD_NOT_APPEAR_APPROVAL_BODY"
SHOULD_NOT_APPEAR_NESTED_REPR = "{'nested': ['RAW']}"


def _allowing_claim_bundle() -> dict[str, Any]:
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
                "supporting_evidence_refs": [],
                "business_fact_refs": [],
                "rule_checks": [],
                "semantic_review_status": "not_needed",
                "allows_user_visible_claim": True,
                "allows_action_recommendation": True,
            }
        ],
        "blocked_claims": [],
        "safe_support_refs": [],
        "reason_codes": [],
        "verifier_policy_version": "claim-verifier.v1",
    }


def _business_fact_ref_payload(
    tenant_id: str,
    *,
    resource_type: str = "refund_case",
    resource_id: str = "RF-1001",
) -> dict[str, Any]:
    return BusinessFactRefV1(
        tenant_id=tenant_id,
        source_system="moca_demo",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 29, 0, 0, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 29, 0, 1, tzinfo=UTC),
    ).model_dump(mode="json")


def _evidence_ref_payload(tenant_id: str, *, evidence_id: str = "refund-policy/chunk-001@v3") -> dict[str, Any]:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": tenant_id,
        "evidence_id": evidence_id,
        "doc_key": "refund-policy",
        "chunk_id": "chunk-001",
        "policy_version": "v3",
        "text_hash": "sha256:" + "a" * 64,
        "retrieved_at": "2026-06-29T00:00:00.000Z",
        "retrieval_config_version": "retrieval.v1",
        "score": 0.91,
        "rank": 1,
    }


def _claim_bundle_with_safe_refs(tenant_id: str) -> dict[str, Any]:
    fact_ref = _business_fact_ref_payload(tenant_id)
    evidence_ref = _evidence_ref_payload(tenant_id)
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
        "reason_codes": ["coupon_amount", "verified_claim"],
        "verifier_policy_version": "claim-verifier.v1",
    }


def _phase34_business_context(tenant_id: str, *, merchant_id: str | None = "merchant-1") -> dict[str, Any]:
    fact_ref = _business_fact_ref_payload(tenant_id)
    refund_case: dict[str, Any] = {"id": "RF-1001", "status": "open"}
    if merchant_id is not None:
        refund_case["merchant_id"] = merchant_id
    return {
        "refund_case": refund_case,
        "business_fact_refs": [fact_ref],
        "business_fact_results": [{"business_fact_refs": [fact_ref]}],
    }


class RaisingLLM:
    def __init__(self, error: Exception):
        self.error = error

    def with_structured_output(self, schema):
        error = self.error

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                raise error

        return _Wrapper()


class CapturingLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def with_structured_output(self, schema):
        llm = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                llm.messages = messages
                if issubclass(schema, BaseModel):
                    return schema.model_validate(llm.response)
                return llm.response

        return _Wrapper()


class FakeConversationService:
    async def load_prompt_context(self, **kwargs):
        return SimpleNamespace(
            latest_thread_summary=SimpleNamespace(summary_text="thread_rolling risk context includes ORD-RISK-PRIOR."),
            recent_messages=[SimpleNamespace(role="assistant", content="recent risk-safe assistant note.")],
            tool_prompt_summaries=[
                SimpleNamespace(
                    tool_call_id="tool-call-risk",
                    tool_result_id="tool-result-risk",
                    tool_name="get_order",
                    status="success",
                    summary="Risk-safe tool summary.",
                    prompt_summary="Risk-safe tool prompt summary for ORD-RISK-TOOL.",
                    business_fact_refs_json=[{"resource_type": "order", "resource_id": "ORD-RISK-TOOL"}],
                    policy_evidence_refs_json=[],
                    raw_result_ref="opaque/risk/ref",
                    audit_ref="audit/risk/ref",
                    normalized_result_json={"secret": SHOULD_NOT_APPEAR_RAW_TOOL_DATA},
                )
            ],
        )


def _spy_context_assembler(monkeypatch):
    assemblies: list[PromptAssembly] = []
    original = assess_risk_module.ContextAssembler.assemble

    def spy(self, **kwargs):
        assembly = original(self, **kwargs)
        assemblies.append(assembly)
        return assembly

    monkeypatch.setattr(assess_risk_module.ContextAssembler, "assemble", spy)
    return assemblies


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "recommended_action",
    ["insufficient_evidence", "citation_invalid", "retrieval_error"],
)
async def test_no_action_recommendations_never_propose_action(monkeypatch, base_state, recommended_action):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("no-action recommendation should not call the LLM")

    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingLLM())
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": recommended_action,
            "reasoning_summary": "No deterministic action is safe.",
        },
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["proposed_action"] is None


@pytest.mark.asyncio
async def test_actionable_recommendation_still_proposes_action(monkeypatch, base_state):
    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "low",
                "risk_reason": "standard compensation",
                "approval_required": False,
                "rule_ref": "LR-01",
            }
        ),
    )
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(base_state["tenant_id"]),
        "business_context": _phase34_business_context(base_state["tenant_id"]),
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["proposed_action"]["action_type"] == "issue_coupon"


@pytest.mark.asyncio
async def test_missing_claim_bundle_for_actionable_recommendation_withholds_action(monkeypatch, base_state):
    """APF-14: proposed actions require a claim_verification_bundle from claim_verify."""

    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("missing claim bundle must block before risk LLM or action proposal")

    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingLLM())
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "business_context": {"order": {"id": "order-1", "status": "paid"}},
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["proposed_action"] is None
    assert result.get("action_payload_hash") is None
    assert result.get("safety_snapshot_ref") is None
    assert result.get("safety_snapshot_hash") is None
    assert result.get("safety_snapshot_verified") is False


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
        "claim_verification_bundle": _claim_bundle_with_safe_refs(base_state["tenant_id"]),
        "business_context": {
            **_phase34_business_context(base_state["tenant_id"]),
            "order": {"status": "delivered"},
        },
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


@pytest.mark.asyncio
async def test_phase34_approval_required_writes_risk_gate_bindings(monkeypatch, base_state):
    tenant_id = base_state["tenant_id"]
    evidence_ref = _evidence_ref_payload(tenant_id)
    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "high",
                "risk_reason": "Coupon amount requires manager approval.",
                "approval_required": True,
                "rule_ref": "HR-COUPON",
            }
        ),
    )
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a 50 CNY coupon for the refund delay.",
            "compensation_amount": 50,
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(tenant_id),
        "business_context": _phase34_business_context(tenant_id),
        "retrieved_evidence": {
            "candidate_refs": [
                {
                    **_evidence_ref_payload(tenant_id, evidence_id="candidate-only/chunk-999@v1"),
                    "doc_key": "candidate-only",
                    "chunk_id": "chunk-999",
                }
            ]
        },
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["target_merchant_id"] == "merchant-1"
    assert result["target_merchant_ref"]["target_merchant_id"] == "merchant-1"
    assert result["business_fact_refs"][0]["resource_id"] == "RF-1001"
    assert result["verified_evidence_refs"] == [evidence_ref]
    assert result["claim_verification_summary"] == {
        "overall_status": "verified",
        "route": "continue",
        "safe_support_ref_count": 1,
        "blocked_claim_count": 0,
        "reason_codes": ["coupon_amount", "verified_claim"],
    }
    assert result["risk_decision_ref"] == f"risk_decision::{result['action_payload_hash']}"
    RiskDecisionV1.model_validate(result["risk_decision"])
    plan = result["approval_plan"]
    assert plan["schema_version"] == "approval_plan.v1"
    assert plan["approval_required"] is True
    assert plan["action_payload_hash"] == result["action_payload_hash"]
    assert plan["safety_snapshot_ref"] == result["safety_snapshot_ref"]
    assert plan["safety_snapshot_hash"] == result["safety_snapshot_hash"]
    assert plan["risk_decision_ref"] == result["risk_decision_ref"]
    assert plan["approval_idempotency_key"] == result["approval_idempotency_key"]
    assert "candidate-only/chunk-999@v1" not in {
        ref["evidence_id"] for ref in result["verified_evidence_refs"]
    }
    assert result.get("auto_allowed_binding") is None


@pytest.mark.asyncio
async def test_phase34_missing_target_merchant_fails_closed_without_approval_plan(monkeypatch, base_state):
    tenant_id = base_state["tenant_id"]
    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "high",
                "risk_reason": "Coupon amount requires manager approval.",
                "approval_required": True,
                "rule_ref": "HR-COUPON",
            }
        ),
    )
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a 50 CNY coupon for the refund delay.",
            "compensation_amount": 50,
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(tenant_id),
        "business_context": _phase34_business_context(tenant_id, merchant_id=None),
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["proposed_action"] is None
    assert result["approval_plan"] is None
    assert result["auto_allowed_binding"] is None
    assert result["final_response"] == "操作需要人工复核，当前未创建可执行审批或动作草稿。"
    assert result["risk_assessment"]["risk_level"] == "manual_review"


@pytest.mark.asyncio
async def test_phase34_auto_allowed_path_validates_durable_binding(monkeypatch, base_state):
    tenant_id = base_state["tenant_id"]
    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "low",
                "risk_reason": "Small coupon is auto-allowed.",
                "approval_required": False,
                "rule_ref": "LR-01",
            }
        ),
    )
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a 10 CNY coupon for the delay.",
            "compensation_amount": 10,
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(tenant_id),
        "business_context": _phase34_business_context(tenant_id),
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    binding = AutoAllowedActionBindingV1.model_validate(result["auto_allowed_binding"])
    assert binding.target_merchant_id == "merchant-1"
    assert binding.action_payload_hash == result["action_payload_hash"]
    assert binding.safety_snapshot_ref == result["safety_snapshot_ref"]
    assert binding.safety_snapshot_hash == result["safety_snapshot_hash"]
    assert binding.risk_decision_ref == result["risk_decision_ref"]
    assert binding.idempotency_key != result["approval_idempotency_key"]
    assert binding.business_fact_refs[0].resource_id == "RF-1001"
    assert binding.verified_evidence_refs[0].evidence_id == "refund-policy/chunk-001@v3"


@pytest.mark.asyncio
async def test_programming_error_propagates(monkeypatch, base_state):
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: RaisingLLM(KeyError("bug")))
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(base_state["tenant_id"]),
        "business_context": _phase34_business_context(base_state["tenant_id"]),
    }

    with pytest.raises(KeyError, match="bug"):
        await assess_risk_module.assess_risk_and_approval(state)


@pytest.mark.asyncio
async def test_expected_error_retries_then_falls_back(monkeypatch, base_state):
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: RaisingLLM(ValueError("invalid")))
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(base_state["tenant_id"]),
        "business_context": _phase34_business_context(base_state["tenant_id"]),
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["risk_assessment"]["risk_level"] == "low"
    assert result["node_errors"][0]["retry_count"] == 2


@pytest.mark.asyncio
async def test_assess_risk_prompt_uses_context_assembly_and_excludes_raw_payloads(monkeypatch, base_state):
    fake_llm = CapturingLLM(
        {
            "risk_level": "low",
            "risk_reason": "standard guidance",
            "approval_required": False,
            "rule_ref": "LR-01",
        }
    )
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: fake_llm)
    state = {
        **base_state,
        "current_run_id": str(uuid4()),
        "recommendation_draft": {
            "recommended_action": "provide_guidance",
            "reasoning_summary": "Explain the refund status.",
            "evidence_refs": [{"doc_key": "policy_refund_timeout", "chunk_id": "chunk_001"}],
        },
        "business_context": {
            "order": {"order_id": "ORD-RISK-001", "status": "paid"},
            "facts": {"nested": ["RAW"]},
            "raw_payload": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
            "approval_authority_body": SHOULD_NOT_APPEAR_APPROVAL_BODY,
        },
    }

    await assess_risk_module.assess_risk_and_approval(
        state,
        {"configurable": {"session": object(), "conversation_service": FakeConversationService()}},
    )

    assert assemblies
    assert fake_llm.messages == assemblies[-1].to_messages()
    prompt = fake_llm.messages[-1]["content"]
    assert "thread_rolling" in prompt
    assert "Risk rules summary" in prompt
    assert "Recommendation summary" in prompt
    assert "Risk-safe tool prompt summary" in prompt
    assert "ORD-RISK-001" in prompt
    assert "PromptAssembly" in PromptAssembly.__name__
    assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
    assert SHOULD_NOT_APPEAR_APPROVAL_BODY not in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt
