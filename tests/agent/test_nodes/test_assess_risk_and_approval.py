from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.agent.context import PromptAssembly
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from tests.agent.conftest import FakeLLM


SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_APPROVAL_BODY = "SHOULD_NOT_APPEAR_APPROVAL_BODY"
SHOULD_NOT_APPEAR_NESTED_REPR = "{'nested': ['RAW']}"


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
        "business_context": {"order": {"id": "order-1", "status": "paid"}},
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


@pytest.mark.asyncio
async def test_programming_error_propagates(monkeypatch, base_state):
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: RaisingLLM(KeyError("bug")))
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "business_context": {},
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
        "business_context": {},
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
