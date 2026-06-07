from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from tests.agent.conftest import FakeLLM


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


def _evidence() -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id="tenant",
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v1",
        text="退款超时时，客服应核实支付通道和退款状态。",
        retrieved_at="2026-06-07T02:30:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.8,
        rank=1,
    )


def _retrieved_evidence() -> dict:
    return {"schema_version": "knowledge_search_result.v2", "evidence_refs": [_evidence().model_dump()]}


def _draft(*, chunk_id: str = "chunk_001") -> dict:
    return {
        "recommended_action": "建议退款",
        "reasoning_summary": "根据规则",
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": chunk_id,
                "title": "退款超时规则",
                "section": "第一条",
            }
        ],
        "confidence": 0.85,
        "risk_level": "low",
        "missing_info": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("recommended_action", ["insufficient_evidence", "retrieval_error"])
async def test_skips_llm_for_retrieval_safety_drafts(monkeypatch, base_state, recommended_action):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not be called")

    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: ExplodingLLM())
    state = {**base_state, "recommendation_draft": {"recommended_action": recommended_action}}

    result = await generate_recommendation_module.generate_recommendation(state)

    assert "recommendation_draft" not in result
    assert result["trace_steps"][-1]["status"] == "skipped"


@pytest.mark.asyncio
async def test_membership_pass_keeps_canonical_evidence_ref(monkeypatch, base_state):
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_draft()))

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, "retrieved_evidence": _retrieved_evidence()}
    )

    evidence = _evidence()
    assert result["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert result["evidence_refs"][0]["text_hash"] == evidence.text_hash
    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert result["trace_steps"][-1]["evidence_refs"][0]["evidence_id"] == evidence.evidence_id


@pytest.mark.asyncio
async def test_membership_fail_drops_ref_and_marks_citation_invalid(monkeypatch, base_state):
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_draft(chunk_id="missing")))

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, "retrieved_evidence": _retrieved_evidence()}
    )

    draft = result["recommendation_draft"]
    assert draft["evidence_refs"] == []
    assert draft["recommended_action"] == "citation_invalid"
    assert draft["confidence"] == 0.0
    assert draft["citation_validation"]["is_valid"] is False
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_prompt_lists_evidence_ids_in_allowed_citation_objects(monkeypatch, base_state):
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)

    await generate_recommendation_module.generate_recommendation(
        {**base_state, "retrieved_evidence": _retrieved_evidence()}
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "Allowed citation objects" in prompt
    assert _evidence().evidence_id in prompt
    assert "For each material claim" in prompt
