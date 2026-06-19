from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.agent.context import PromptAssembly
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


SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_BUSINESS_CONTEXT = "SHOULD_NOT_APPEAR_BUSINESS_CONTEXT"
SHOULD_NOT_APPEAR_APPROVAL_BODY = "SHOULD_NOT_APPEAR_APPROVAL_BODY"
SHOULD_NOT_APPEAR_NESTED_REPR = "{'nested': ['RAW']}"


def _evidence(
    *,
    tenant_id: str = "tenant",
    chunk_id: str = "chunk_001",
    policy_version: str = "v1",
    text: str = "退款超时时，客服应核实支付通道和退款状态。",
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id=chunk_id,
        policy_version=policy_version,
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


def test_risk_hints_merge_state_and_evidence_labels():
    evidence = _evidence()
    retrieval_state = _retrieval_state(evidence=[evidence])
    retrieval_state["retrieved_evidence"]["evidence_refs"][0]["risk_labels"] = ["ocr_low_confidence"]

    hints = generate_recommendation_module._risk_hints_from_state(
        {
            **retrieval_state,
            "risk_hints": [{"evidence_id": evidence.evidence_id, "labels": ["manual_review_sensitive"]}],
        }
    )

    assert hints == [
        {
            "evidence_id": evidence.evidence_id,
            "labels": ["manual_review_sensitive", "ocr_low_confidence"],
        }
    ]


def _with_knowledge_service(monkeypatch, contents):
    calls = []

    class FakeKnowledgeService:
        def __init__(self, retriever):
            assert retriever is not None

        async def get_verified_evidence_contents(self, *, tenant_id, evidence_refs):
            calls.append((tenant_id, [(ref.doc_key, ref.chunk_id) for ref in evidence_refs]))
            return {
                ref.evidence_id: contents[(ref.doc_key, ref.chunk_id)]
                for ref in evidence_refs
                if (ref.doc_key, ref.chunk_id) in contents
            }

    monkeypatch.setattr(generate_recommendation_module, "PolicyKnowledgeService", FakeKnowledgeService)
    return calls


def _with_canonical_knowledge_service(monkeypatch, rows):
    class FakeKnowledgeService:
        def __init__(self, retriever):
            assert retriever is not None

        async def get_canonical_evidence_rows(self, *, tenant_id, evidence_refs):
            return {
                (ref.doc_key, ref.chunk_id): rows[(ref.doc_key, ref.chunk_id)]
                for ref in evidence_refs
                if (ref.doc_key, ref.chunk_id) in rows
            }

    monkeypatch.setattr(generate_recommendation_module, "PolicyKnowledgeService", FakeKnowledgeService)


def _canonical_row(
    evidence: EvidenceRefV1,
    *,
    content: str,
    current_policy_version: str,
    effective_date: str = "2026-06-01",
) -> dict:
    return {
        "tenant_id": evidence.tenant_id,
        "doc_key": evidence.doc_key,
        "chunk_id": evidence.chunk_id,
        "content": content,
        "policy_document_version": int(current_policy_version.removeprefix("v")),
        "current_policy_version": current_policy_version,
        "effective_date": effective_date,
        "expires_at": None,
        "merchant_ids": [],
        "doc_type": None,
        "risk_level": None,
    }


def _config():
    return {"configurable": {"session": object()}}


class FakeConversationService:
    def __init__(self):
        self.calls = []

    async def load_prompt_context(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            latest_thread_summary=SimpleNamespace(
                summary_text="thread_rolling summary says prior turn discussed ORD-PRIOR-001."
            ),
            recent_messages=[
                SimpleNamespace(role="user", content="recent safe message for ORD-RECENT-001."),
            ],
            tool_prompt_summaries=[
                SimpleNamespace(
                    tool_call_id="tool-call-context",
                    tool_result_id="tool-result-context",
                    tool_name="get_order",
                    status="success",
                    summary="Safe context tool summary.",
                    prompt_summary="Safe tool prompt summary for ORD-TOOL-001.",
                    business_fact_refs_json=[{"resource_type": "order", "resource_id": "ORD-TOOL-001"}],
                    policy_evidence_refs_json=[],
                    raw_result_ref="opaque/ref",
                    audit_ref="audit/ref",
                    normalized_result_json={"secret": SHOULD_NOT_APPEAR_RAW_TOOL_DATA},
                )
            ],
        )


def _spy_context_assembler(monkeypatch):
    assemblies: list[PromptAssembly] = []
    original = generate_recommendation_module.ContextAssembler.assemble

    def spy(self, **kwargs):
        assembly = original(self, **kwargs)
        assemblies.append(assembly)
        return assembly

    monkeypatch.setattr(generate_recommendation_module.ContextAssembler, "assemble", spy)
    return assemblies


def _draft(
    *,
    chunk_id: str = "chunk_001",
    reasoning_summary: str = "退款超时时，客服应核实支付通道和退款状态。",
) -> dict:
    return {
        "recommended_action": "建议退款",
        "reasoning_summary": reasoning_summary,
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
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_draft()))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert result["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert result["evidence_refs"][0]["text_hash"] == evidence.text_hash
    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert result["trace_steps"][-1]["evidence_refs"][0]["evidence_id"] == evidence.evidence_id


@pytest.mark.asyncio
async def test_membership_fail_drops_ref_and_marks_citation_invalid(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_draft(chunk_id="missing")))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    draft = result["recommendation_draft"]
    assert draft["evidence_refs"] == []
    assert draft["recommended_action"] == "citation_invalid"
    assert draft["confidence"] == 0.0
    assert draft["citation_validation"]["is_valid"] is False
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_prompt_lists_evidence_ids_in_allowed_citation_objects(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "Allowed citation objects" in prompt
    assert evidence.evidence_id in prompt
    assert "For each material claim" in prompt


@pytest.mark.asyncio
async def test_prompt_excludes_invalid_candidate_from_allowed_citation_objects(monkeypatch, base_state):
    invalid_text = "invalid candidate body must not be offered as an allowed citation"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=invalid_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {})

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "Allowed citation objects: []" in prompt
    assert invalid_text not in prompt
    assert result["verification_route"] == "insufficient_evidence"
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_prompt_includes_bounded_policy_text(monkeypatch, base_state):
    full_text = "A" * MAX_EVIDENCE_TEXT_CHARS + "NOT_IN_PROMPT"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=full_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    calls = _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): full_text})

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
    _with_knowledge_service(monkeypatch, {})

    await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert distinctive_rule not in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_canonical_latest_invalid_reason_routes_refuse_not_generic_insufficient(monkeypatch, base_state):
    text = "退款超时时，客服应核实支付通道和退款状态。"
    evidence = _evidence(tenant_id=base_state["tenant_id"], policy_version="v1", text=text)
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_draft(reasoning_summary=text)))
    _with_canonical_knowledge_service(
        monkeypatch,
        {
            (evidence.doc_key, evidence.chunk_id): _canonical_row(
                evidence,
                content=text,
                current_policy_version="v2",
            )
        },
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert result["verifier_status"] == "latest_version_invalid"
    assert result["verification_route"] == "refuse"
    assert "latest_version_invalid" in result["verifier_reason_codes"]
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_evidence_ocr_low_confidence_label_routes_manual_review(monkeypatch, base_state):
    text = "扫描件显示可直接补偿 800 元。"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=text)
    retrieval_state = _retrieval_state(evidence=[evidence])
    retrieval_state["retrieved_evidence"]["evidence_refs"][0]["risk_labels"] = ["ocr_low_confidence"]
    draft = _draft(reasoning_summary=text)
    draft["risk_level"] = "high"
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(draft))
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): text})

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **retrieval_state},
        _config(),
    )

    assert result["verifier_status"] == "ocr_low_confidence"
    assert result["verification_route"] == "manual_review"
    assert "ocr_low_confidence" in result["verifier_reason_codes"]
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_policy_text_never_persisted(monkeypatch, base_state):
    policy_text = "node local policy body SHOULD_NOT_PERSIST"
    safe_claim_text = "node local policy body"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=policy_text)
    retrieval_state = _retrieval_state(evidence=[evidence])
    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_draft(reasoning_summary=safe_claim_text)),
    )
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): policy_text})

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
    fake_llm = CapturingLLM(_draft(reasoning_summary="B" * MAX_EVIDENCE_TEXT_CHARS))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): full_text})

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

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["verification_route"] == "insufficient_evidence"
    assert "context_builder_session_missing" in result["verifier_reason_codes"]
    assert policy_text not in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_cross_tenant_ref_is_not_grounded(monkeypatch, base_state):
    policy_text = "cross tenant policy body"
    evidence = _evidence(text=policy_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {})

    await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert policy_text not in fake_llm.messages[-1]["content"]


def test_generate_recommendation_does_not_import_policy_chunk_repository():
    assert not hasattr(generate_recommendation_module, "PolicyChunkRepository")


@pytest.mark.asyncio
async def test_mixed_citations_revalidated_to_valid(monkeypatch, base_state):
    mixed_draft = _draft()
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    mixed_draft["evidence_refs"].append(
        {
            "doc_key": "policy_refund_timeout",
            "chunk_id": "missing",
            "title": "missing",
            "section": "missing",
        }
    )
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(mixed_draft))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

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


@pytest.mark.asyncio
async def test_generate_recommendation_prompt_uses_context_assembly_and_excludes_raw_payloads(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    fake_llm = CapturingLLM(_draft())
    fake_conversation = FakeConversationService()
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): "Allowed verified policy text."})

    await generate_recommendation_module.generate_recommendation(
        {
            **base_state,
            "current_run_id": str(uuid4()),
            **_retrieval_state(evidence=[evidence]),
            "business_context": {
                "order": {"order_id": "ORD-001", "status": "paid"},
                "facts": {
                    "marker": SHOULD_NOT_APPEAR_BUSINESS_CONTEXT,
                    "nested": ["RAW"],
                },
                "raw_payload": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
                "approval_authority_body": SHOULD_NOT_APPEAR_APPROVAL_BODY,
            },
            "tool_results": [
                {
                    "tool_call_id": "tool-call-state",
                    "tool_result_id": "tool-result-state",
                    "tool_name": "get_refund",
                    "status": "success",
                    "summary": "Safe state tool summary.",
                    "prompt_summary": "Safe state tool prompt summary for RF-001.",
                    "business_fact_refs": [{"resource_type": "refund_case", "resource_id": "RF-001"}],
                    "policy_evidence_refs": [],
                    "data": {"secret": SHOULD_NOT_APPEAR_RAW_TOOL_DATA},
                }
            ],
        },
        {"configurable": {"session": object(), "conversation_service": fake_conversation}},
    )

    assert assemblies
    assert fake_llm.messages == assemblies[-1].to_messages()
    prompt = fake_llm.messages[-1]["content"]
    assert "thread_rolling_summary" in prompt
    assert "recent safe message" in prompt
    assert "Safe tool prompt summary" in prompt
    assert "Safe state tool prompt summary" in prompt
    assert "Allowed citation objects" in prompt
    assert "PromptAssembly" in PromptAssembly.__name__
    assert fake_conversation.calls
    assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
    assert SHOULD_NOT_APPEAR_BUSINESS_CONTEXT not in prompt
    assert SHOULD_NOT_APPEAR_APPROVAL_BODY not in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt
