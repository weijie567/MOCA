from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.knowledge.config import MAX_EVIDENCE_TEXT_CHARS, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.text_hash import evidence_text_hash
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


def _evidence(
    *,
    tenant_id: str = "tenant",
    chunk_id: str = "chunk_001",
    text: str = "退款超时时，客服应核实支付通道和退款状态。",
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id=chunk_id,
        policy_version="v1",
        text=text,
        retrieved_at="2026-06-07T02:30:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.8,
        rank=1,
    )


def _retrieval_state(*, evidence: list[EvidenceRefV1] | None = None) -> dict:
    evidence = evidence or [_evidence()]
    return {
        "retrieved_evidence": {
            "schema_version": "knowledge_search_result.v2",
            "evidence_refs": [item.model_dump() for item in evidence],
        },
    }


def _with_repo(monkeypatch, contents):
    calls = []

    class FakeRepo:
        def __init__(self, session):
            assert session is not None

        async def get_contents_by_evidence_keys(self, tenant_id, keys):
            calls.append((tenant_id, keys))
            return contents

    monkeypatch.setattr(generate_recommendation_module, "PolicyChunkRepository", FakeRepo)
    return calls


def _config():
    return {"configurable": {"session": object()}}


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
        {**base_state, **_retrieval_state()}
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
        {**base_state, **_retrieval_state()}
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
        {**base_state, **_retrieval_state()}
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "Allowed citation objects" in prompt
    assert _evidence().evidence_id in prompt
    assert "For each material claim" in prompt


@pytest.mark.asyncio
async def test_prompt_includes_bounded_policy_text(monkeypatch, base_state):
    full_text = "A" * MAX_EVIDENCE_TEXT_CHARS + "NOT_IN_PROMPT"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=full_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    calls = _with_repo(monkeypatch, {(evidence.doc_key, evidence.chunk_id): full_text})

    await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "A" * MAX_EVIDENCE_TEXT_CHARS in prompt
    assert "NOT_IN_PROMPT" not in prompt
    assert len(calls) == 1
    assert calls[0][1] == [(evidence.doc_key, evidence.chunk_id)]


@pytest.mark.asyncio
async def test_hash_mismatch_content_is_not_grounded(monkeypatch, base_state):
    distinctive_rule = "RULE-ONLY-IN-DB: refund must be reviewed within 17 minutes"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=distinctive_rule)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_repo(monkeypatch, {(evidence.doc_key, evidence.chunk_id): distinctive_rule + " changed"})

    await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert distinctive_rule not in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_policy_text_never_persisted(monkeypatch, base_state):
    policy_text = "node local policy body"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=policy_text)
    retrieval_state = _retrieval_state(evidence=[evidence])
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_draft()))
    _with_repo(monkeypatch, {(evidence.doc_key, evidence.chunk_id): policy_text})

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **retrieval_state},
        _config(),
    )

    assert policy_text not in str(retrieval_state["retrieved_evidence"])
    assert policy_text not in str(result)
    assert all("text" not in item for item in result["evidence_refs"])
    assert all("text" not in item for item in result["trace_steps"][-1]["evidence_refs"])


@pytest.mark.asyncio
async def test_text_hash_uses_full_content_not_truncated(monkeypatch, base_state):
    full_text = "B" * (MAX_EVIDENCE_TEXT_CHARS + 200)
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=full_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_repo(monkeypatch, {(evidence.doc_key, evidence.chunk_id): full_text})

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert result["evidence_refs"][0]["text_hash"] == evidence_text_hash(full_text)
    assert full_text not in fake_llm.messages[-1]["content"]
    assert "B" * MAX_EVIDENCE_TEXT_CHARS in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_missing_session_completes_without_grounded_text(monkeypatch, base_state):
    policy_text = "must not reach prompt without a session"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=policy_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        {},
    )

    assert result["recommendation_draft"]["recommended_action"] == "建议退款"
    assert policy_text not in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_cross_tenant_ref_is_not_grounded(monkeypatch, base_state):
    policy_text = "cross tenant policy body"
    evidence = _evidence(text=policy_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_repo(monkeypatch, {(evidence.doc_key, evidence.chunk_id): policy_text})

    await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert policy_text not in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_mixed_citations_revalidated_to_valid(monkeypatch, base_state):
    mixed_draft = _draft()
    mixed_draft["evidence_refs"].append(
        {
            "doc_key": "policy_refund_timeout",
            "chunk_id": "missing",
            "title": "missing",
            "section": "missing",
        }
    )
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(mixed_draft))

    result = await generate_recommendation_module.generate_recommendation({**base_state, **_retrieval_state()})

    draft = result["recommendation_draft"]
    assert [item["chunk_id"] for item in draft["evidence_refs"]] == ["chunk_001"]
    assert draft["recommended_action"] == mixed_draft["recommended_action"]
    assert draft["citation_validation"]["is_valid"] is True


class RaisingLLM:
    def __init__(self, error: Exception):
        self.error = error

    def with_structured_output(self, schema):
        error = self.error

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                raise error

        return _Wrapper()


@pytest.mark.asyncio
async def test_programming_error_propagates(monkeypatch, base_state):
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: RaisingLLM(KeyError("bug")))

    with pytest.raises(KeyError, match="bug"):
        await generate_recommendation_module.generate_recommendation({**base_state, **_retrieval_state()})


@pytest.mark.asyncio
async def test_expected_error_retries_then_falls_back(monkeypatch, base_state):
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: RaisingLLM(ValueError("invalid")))

    result = await generate_recommendation_module.generate_recommendation({**base_state, **_retrieval_state()})

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["node_errors"][0]["retry_count"] == 2
