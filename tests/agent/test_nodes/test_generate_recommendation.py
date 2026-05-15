from __future__ import annotations

from pydantic import BaseModel
import pytest

from tests.agent.conftest import FakeLLM

from src.agent.nodes import generate_recommendation as generate_recommendation_module


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


def _retrieved_evidence():
    return {
        "status": "success",
        "data": {
            "retrieval_status": "strong_evidence",
            "best_score": 0.8,
            "evidence": [
                {
                    "doc_key": "policy_refund_timeout",
                    "chunk_id": "chunk_001",
                    "title": "退款超时规则",
                    "section": "第一条",
                    "score": 0.8,
                    "text": "退款超时时，客服应核实支付通道和退款状态。",
                }
            ],
        },
        "error": {},
    }


@pytest.mark.asyncio
async def test_skips_llm_when_insufficient_evidence(monkeypatch, base_state):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not be called")

    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: ExplodingLLM())
    state = {**base_state, "recommendation_draft": {"recommended_action": "insufficient_evidence"}}

    result = await generate_recommendation_module.generate_recommendation(state)

    assert "recommendation_draft" not in result
    assert result["trace_steps"][-1]["status"] == "skipped"


@pytest.mark.asyncio
async def test_citation_validator_strips_invalid_refs(monkeypatch, base_state):
    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "recommended_action": "建议退款",
                "reasoning_summary": "根据规则",
                "evidence_refs": [
                    {
                        "doc_key": "policy_refund_timeout",
                        "chunk_id": "chunk_001",
                        "title": "退款超时规则",
                        "section": "第一条",
                    },
                    {
                        "doc_key": "policy_refund_timeout",
                        "chunk_id": "missing_chunk",
                        "title": "退款超时规则",
                        "section": "第二条",
                    },
                ],
                "confidence": 0.85,
                "risk_level": "low",
                "missing_info": [],
            }
        ),
    )
    state = {**base_state, "retrieved_evidence": _retrieved_evidence()}

    result = await generate_recommendation_module.generate_recommendation(state)

    refs = result["recommendation_draft"]["evidence_refs"]
    assert refs == [
        {
            "doc_key": "policy_refund_timeout",
            "chunk_id": "chunk_001",
            "title": "退款超时规则",
            "section": "第一条",
        }
    ]
    assert result["evidence_refs"][0]["chunk_id"] == "chunk_001"
    assert all(ref["chunk_id"] != "missing_chunk" for ref in result["evidence_refs"])
    assert result["trace_steps"][-1]["evidence_refs"][0]["chunk_id"] == "chunk_001"
    assert all(ref["chunk_id"] != "missing_chunk" for ref in result["trace_steps"][-1]["evidence_refs"])


@pytest.mark.asyncio
async def test_generate_recommendation_trace_contains_validated_evidence_refs(monkeypatch, base_state):
    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "recommended_action": "建议退款",
                "reasoning_summary": "根据规则",
                "evidence_refs": [
                    {
                        "doc_key": "policy_refund_timeout",
                        "chunk_id": "chunk_001",
                        "title": "退款超时规则",
                        "section": "第一条",
                    }
                ],
                "confidence": 0.85,
                "risk_level": "low",
                "missing_info": [],
            }
        ),
    )
    state = {**base_state, "retrieved_evidence": _retrieved_evidence()}

    result = await generate_recommendation_module.generate_recommendation(state)

    assert result["evidence_refs"][0]["chunk_id"] == "chunk_001"
    assert result["evidence_refs"][0]["retrieved_at"]
    assert result["trace_steps"][-1]["evidence_refs"][0]["doc_key"] == "policy_refund_timeout"
    assert result["trace_steps"][-1]["evidence_refs"][0]["chunk_id"] == "chunk_001"


@pytest.mark.asyncio
async def test_generate_recommendation_prompt_lists_allowed_citation_objects(monkeypatch, base_state):
    fake_llm = CapturingLLM(
        {
            "recommended_action": "建议退款",
            "reasoning_summary": "根据规则",
            "evidence_refs": [
                {
                    "doc_key": "policy_refund_timeout",
                    "chunk_id": "chunk_001",
                    "title": "退款超时规则",
                    "section": "第一条",
                }
            ],
            "confidence": 0.85,
            "risk_level": "low",
            "missing_info": [],
        }
    )
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    state = {**base_state, "retrieved_evidence": _retrieved_evidence()}

    await generate_recommendation_module.generate_recommendation(state)

    prompt = fake_llm.messages[-1]["content"]
    assert "Allowed citation objects" in prompt
    assert '"chunk_id": "chunk_001"' in prompt
    assert "Do not return strings" in prompt
