from __future__ import annotations

import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.agent.context import PromptAssembly
from src.agent.nodes import recommendation_generation as recommendation_generation_module
from src.knowledge.config import MAX_EVIDENCE_TEXT_CHARS, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.text_hash import evidence_text_hash
from src.tools.contracts import BusinessFactRefV1
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
VERIFIER_OWNED_STATE_KEYS = {
    "claim_verification_bundle",
    "blocked_claims",
    "safe_support_refs",
    "verifier_status",
    "verification_route",
    "verifier_reason_codes",
}


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
    state = {
        "retrieved_evidence": {
            "schema_version": "knowledge_search_result.v2",
            "evidence_refs": [item.model_dump() for item in evidence],
        },
    }
    if evidence:
        state.update(_verified_package_state(evidence=evidence[0]))
    return state


def _verified_package_state(
    *,
    evidence: EvidenceRefV1,
    snippet: str = "VERIFIED_PACKAGE_POLICY_TEXT: refund timeout requires verified package context.",
    status: str = "verified",
) -> dict:
    package = {
        "schema_version": "verified_evidence_package.v1",
        "package_id": "pkg-generate-recommendation",
        "status": status,
        "evidence_items": [],
        "citation_map": {"C1": [evidence.evidence_id]} if status in {"verified", "partial"} else {},
        "evidence_map": {evidence.evidence_id: evidence.model_dump(mode="json")}
        if status in {"verified", "partial"}
        else {},
        "prompt_projection": {
            "schema_version": "rag_prompt_context.v1",
            "citations": [
                {
                    "citation_id": "C1",
                    "display_label": "退款超时规则",
                    "snippet": snippet,
                    "risk_labels": ["authority_checked"],
                    "metadata": {
                        "doc_key": evidence.doc_key,
                        "chunk_id": evidence.chunk_id,
                        "policy_version": evidence.policy_version,
                    },
                    "merged_from_chunk_ids": [],
                }
            ],
            "risk_labels": ["authority_checked"],
            "trusted_context": {},
        },
        "verifier_projection": {"safe_refs": [evidence.evidence_id], "evidence_snippets": [], "business_fact_refs": []},
        "replay_snapshot_refs": [evidence.evidence_id],
        "debug_projection": {},
        "stale_refs": [],
        "conflict_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "policy_version": evidence.policy_version,
        "retrieval_config_version": evidence.retrieval_config_version,
    }
    return {
        "rag_context_status": status,
        "verified_evidence_package": package,
        "citation_map": package["citation_map"],
        "evidence_map": package["evidence_map"],
    }


def _business_fact_ref_payload(tenant_id: str) -> dict:
    return BusinessFactRefV1(
        tenant_id=tenant_id,
        source_system="moca",
        resource_type="refund_case",
        resource_id="RF-1001",
        resource_version="v1",
        data_freshness_at="2026-06-19T00:00:00Z",
        retrieved_at="2026-06-19T00:00:00Z",
    ).model_dump(mode="json")


def test_risk_hints_merge_state_and_evidence_labels():
    evidence = _evidence()
    retrieval_state = _retrieval_state(evidence=[evidence])
    retrieval_state["retrieved_evidence"]["evidence_refs"][0]["risk_labels"] = ["ocr_low_confidence"]

    hints = recommendation_generation_module._risk_hints_from_state(
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
    return []


def _with_canonical_knowledge_service(monkeypatch, rows):
    return None


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
    original = recommendation_generation_module.ContextAssembler.assemble

    def spy(self, **kwargs):
        assembly = original(self, **kwargs)
        assemblies.append(assembly)
        return assembly

    monkeypatch.setattr(recommendation_generation_module.ContextAssembler, "assemble", spy)
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


def _assert_no_verifier_owned_state(result: dict) -> None:
    assert VERIFIER_OWNED_STATE_KEYS.isdisjoint(result)


def test_recommendation_generation_canonical_import_is_callable():
    assert callable(recommendation_generation_module.recommendation_generation)


def test_recommendation_generation_module_owns_implementation_without_legacy_import():
    assert hasattr(recommendation_generation_module, "_get_llm")
    assert hasattr(recommendation_generation_module, "_assemble_recommendation_prompt")
    assert hasattr(recommendation_generation_module, "_trace_step")
    assert hasattr(recommendation_generation_module, "_risk_hints_from_state")


@pytest.mark.asyncio
async def test_canonical_recommendation_generation_writes_canonical_identity_only(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: FakeLLM(_draft()))

    result = await recommendation_generation_module.recommendation_generation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert "recommendation_generation" in result["llm_outputs"]
    assert "generate_recommendation" not in result["llm_outputs"]
    assert result["llm_outputs"]["recommendation_generation"] == result["recommendation_draft"]
    assert result["trace_steps"][-1]["node"] == "recommendation_generation"
    assert result["material_claims"][0]["generated_from_step"] == "recommendation_generation"
    _assert_no_verifier_owned_state(result)


@pytest.mark.asyncio
async def test_canonical_recommendation_generation_insufficient_evidence_identity(monkeypatch, base_state):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run without a usable verified evidence package")

    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_verified_package_state(evidence=evidence, status="no_evidence"),
            "routing_hints": {"policy_evidence_required": True},
        },
        _config(),
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert "recommendation_generation" in result["llm_outputs"]
    assert "generate_recommendation" not in result["llm_outputs"]
    assert result["trace_steps"][-1]["node"] == "recommendation_generation"
    _assert_no_verifier_owned_state(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("recommended_action", ["insufficient_evidence", "retrieval_error"])
async def test_skips_llm_for_retrieval_safety_drafts(monkeypatch, base_state, recommended_action):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not be called")

    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())
    state = {**base_state, "recommendation_draft": {"recommended_action": recommended_action}}

    result = await recommendation_generation_module.recommendation_generation(state)

    assert "recommendation_draft" not in result
    assert result["trace_steps"][-1]["status"] == "skipped"


@pytest.mark.asyncio
async def test_membership_pass_keeps_canonical_evidence_ref(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: FakeLLM(_draft()))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await recommendation_generation_module.recommendation_generation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert result["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert result["evidence_refs"][0]["text_hash"] == evidence.text_hash
    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert result["trace_steps"][-1]["evidence_refs"][0]["evidence_id"] == evidence.evidence_id


@pytest.mark.asyncio
async def test_membership_pass_does_not_carry_stale_state_evidence_refs(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    stale_ref = {
        **evidence.model_dump(mode="json"),
        "evidence_id": "stale-policy/stale-chunk@v1",
        "policy_version": "v1",
    }
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: FakeLLM(_draft()))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_retrieval_state(evidence=[evidence]),
            "evidence_refs": [stale_ref],
        },
        _config(),
    )

    assert [ref["evidence_id"] for ref in result["evidence_refs"]] == [evidence.evidence_id]
    assert result["trace_steps"][-1]["evidence_refs"][0]["evidence_id"] == evidence.evidence_id


@pytest.mark.asyncio
async def test_membership_fail_drops_ref_and_marks_citation_invalid(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: FakeLLM(_draft(chunk_id="missing")))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await recommendation_generation_module.recommendation_generation(
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
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    await recommendation_generation_module.recommendation_generation(
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
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_retrieval_state(evidence=[evidence]),
            "retrieved_evidence": {
                "schema_version": "knowledge_search_result.v2",
                "evidence_refs": [{**evidence.model_dump(mode="json"), "text": invalid_text}],
            },
        },
        _config(),
    )

    prompt = fake_llm.messages[-1]["content"]
    assert evidence.evidence_id in prompt
    assert invalid_text not in prompt
    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True


@pytest.mark.asyncio
async def test_prompt_includes_bounded_policy_text(monkeypatch, base_state):
    full_text = "A" * MAX_EVIDENCE_TEXT_CHARS + "NOT_IN_PROMPT"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=full_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    calls = _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): full_text})

    await recommendation_generation_module.recommendation_generation(
        {**base_state, **_retrieval_state(evidence=[evidence]), **_verified_package_state(evidence=evidence, snippet=full_text)},
        _config(),
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "A" * (MAX_EVIDENCE_TEXT_CHARS - 20) in prompt
    assert "[truncated]" in prompt
    assert "NOT_IN_PROMPT" not in prompt
    assert calls == []


@pytest.mark.asyncio
async def test_hash_mismatch_content_is_not_grounded(monkeypatch, base_state):
    distinctive_rule = "RULE-ONLY-IN-DB: refund must be reviewed within 17 minutes"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=distinctive_rule)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {})

    await recommendation_generation_module.recommendation_generation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert distinctive_rule not in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_canonical_latest_invalid_reason_routes_refuse_not_generic_insufficient(monkeypatch, base_state):
    text = "退款超时时，客服应核实支付通道和退款状态。"
    evidence = _evidence(tenant_id=base_state["tenant_id"], policy_version="v1", text=text)
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run for stale verified evidence packages")

    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())
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

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_verified_package_state(evidence=evidence, status="stale"),
            "routing_hints": {"policy_evidence_required": True},
        },
        _config(),
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["material_claims"] == []
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_evidence_ocr_low_confidence_label_routes_manual_review(monkeypatch, base_state):
    text = "扫描件显示可直接补偿 800 元。"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=text)
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run for high-risk partial evidence packages")

    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_verified_package_state(evidence=evidence, snippet=text, status="partial"),
            "requested_operation": "draft_action",
        },
        _config(),
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["material_claims"] == []
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocked_case",
    [
        "approval_decision",
        "risk_signals",
        "action_bound_intent",
        "evidence_policy_high_risk",
        "stale_refs",
        "conflict_refs",
        "rejected_candidate_refs",
    ],
)
async def test_partial_package_direct_generation_uses_router_blockers(
    monkeypatch,
    base_state,
    blocked_case: str,
) -> None:
    evidence = _evidence(tenant_id=base_state["tenant_id"])

    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run for router-blocked partial evidence packages")

    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())
    state = {
        **base_state,
        **_verified_package_state(evidence=evidence, status="partial"),
        "primary_intent": "policy_qa",
        "current_intent": "policy_qa",
        "requested_operation": "advise",
        "risk_tier": "low",
    }
    package = state["verified_evidence_package"]
    evidence_payload = evidence.model_dump(mode="json")
    if blocked_case == "approval_decision":
        state["requested_operation"] = "approval_decision"
    elif blocked_case == "risk_signals":
        state["risk_signals"] = ["approval_required"]
    elif blocked_case == "action_bound_intent":
        state["primary_intent"] = "compensation_suggestion"
        state["current_intent"] = "compensation_suggestion"
    elif blocked_case == "evidence_policy_high_risk":
        state["evidence_policy"] = {"evidence_required": True, "risk_level": "approval_required"}
    elif blocked_case == "stale_refs":
        package["stale_refs"] = [evidence_payload]
    elif blocked_case == "conflict_refs":
        package["conflict_refs"] = [evidence_payload]
    elif blocked_case == "rejected_candidate_refs":
        package["rejected_candidate_refs"] = [evidence_payload]
        package["reason_codes"] = ["invalid_hash"]

    result = await recommendation_generation_module.recommendation_generation(state, _config())

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["material_claims"] == []
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_policy_text_never_persisted(monkeypatch, base_state):
    policy_text = "node local policy body SHOULD_NOT_PERSIST"
    safe_claim_text = "node local policy body"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=policy_text)
    retrieval_state = _retrieval_state(evidence=[evidence])
    monkeypatch.setattr(
        recommendation_generation_module,
        "_get_llm",
        lambda: FakeLLM(_draft(reasoning_summary=safe_claim_text)),
    )
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): policy_text})

    result = await recommendation_generation_module.recommendation_generation(
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
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): full_text})

    result = await recommendation_generation_module.recommendation_generation(
        {**base_state, **_retrieval_state(evidence=[evidence]), **_verified_package_state(evidence=evidence, snippet=full_text)},
        _config(),
    )

    assert result["evidence_refs"][0]["text_hash"] == evidence_text_hash(full_text)
    assert full_text not in fake_llm.messages[-1]["content"]
    assert "B" * (MAX_EVIDENCE_TEXT_CHARS - 20) in fake_llm.messages[-1]["content"]
    assert "[truncated]" in fake_llm.messages[-1]["content"]


@pytest.mark.asyncio
async def test_missing_session_completes_without_grounded_text(monkeypatch, base_state):
    policy_text = "must not reach prompt without a session"
    evidence = _evidence(tenant_id=base_state["tenant_id"], text=policy_text)
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run without a required verified evidence package")

    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            "retrieved_evidence": {
                "schema_version": "knowledge_search_result.v2",
                "evidence_refs": [{**evidence.model_dump(mode="json"), "text": policy_text}],
            },
            "routing_hints": {"policy_evidence_required": True},
        },
        {},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["material_claims"] == []


@pytest.mark.asyncio
async def test_cross_tenant_ref_is_not_grounded(monkeypatch, base_state):
    policy_text = "cross tenant policy body"
    evidence = _evidence(text=policy_text)
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {})

    await recommendation_generation_module.recommendation_generation(
        {**base_state, **_retrieval_state(evidence=[evidence])},
        _config(),
    )

    assert policy_text not in fake_llm.messages[-1]["content"]


def test_recommendation_generation_does_not_import_policy_chunk_repository():
    assert not hasattr(recommendation_generation_module, "PolicyChunkRepository")


def test_recommendation_generation_static_boundary_does_not_own_verification():
    source = inspect.getsource(recommendation_generation_module)

    forbidden_generation_owners = (
        "ContextBuilder",
        "MaterialClaimVerifier",
        "PolicyKnowledgeService",
        "PolicyRetrievalEngine",
        "RagContextBudget",
        "determine_verification_route",
        "_verify_recommendation_with_shared_kernel",
    )

    for forbidden in forbidden_generation_owners:
        assert forbidden not in source


@pytest.mark.asyncio
async def test_generation_consumes_verified_package_prompt_projection_and_emits_material_claim_v1(
    monkeypatch, base_state
):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    package_text = "VERIFIED_PACKAGE_POLICY_TEXT: refund timeout requires verified package context."
    fake_llm = CapturingLLM(_draft(reasoning_summary=package_text))
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_verified_package_state(evidence=evidence, snippet=package_text),
            "business_context": {"business_fact_refs": [_business_fact_ref_payload(base_state["tenant_id"])]},
            "retrieved_evidence": {
                "schema_version": "knowledge_search_result.v2",
                "evidence_refs": [
                    {
                        **evidence.model_dump(mode="json"),
                        "evidence_id": "candidate-only-id",
                        "text": "UNVERIFIED_CANDIDATE_TEXT_SHOULD_NOT_ENTER_PROMPT",
                    }
                ],
            },
        },
        {},
    )

    prompt = fake_llm.messages[-1]["content"]
    assert package_text in prompt
    assert "UNVERIFIED_CANDIDATE_TEXT_SHOULD_NOT_ENTER_PROMPT" not in prompt

    claim = result["material_claims"][0]
    assert claim["schema_version"] == "material_claim.v1"
    assert claim["claim_type"] == "policy"
    assert claim["generated_from_step"] == "recommendation_generation"
    assert claim["cited_evidence_ids"] == [evidence.evidence_id]
    assert "authority_class" not in claim
    assert "source_node" not in claim
    assert result["recommendation_draft"]["material_claims"] == result["material_claims"]


@pytest.mark.asyncio
async def test_generation_fails_closed_when_required_verified_package_is_not_usable(monkeypatch, base_state):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run without a usable verified evidence package")

    evidence = _evidence(tenant_id=base_state["tenant_id"])
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            **_verified_package_state(evidence=evidence, status="no_evidence"),
            "routing_hints": {"policy_evidence_required": True},
            "requested_operation": "draft_action",
        },
        {},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["recommendation_draft"]["evidence_refs"] == []
    assert result["material_claims"] == []


@pytest.mark.asyncio
async def test_policy_hints_in_memory_context_do_not_satisfy_policy_gate(monkeypatch, base_state):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("LLM should not run when only memory hints exist")

    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: ExplodingLLM())

    result = await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            "routing_hints": {"policy_evidence_required": True},
            "requested_operation": "draft_action",
            "current_run_id": str(uuid4()),
            "memory_context_bundle": {
                "schema_version": "memory_context_bundle.v1",
                "authority_class": "contextual_only",
                "session_context": {
                    "schema_version": "session_context_memory.v1",
                    "authority_class": "contextual_only",
                    "tenant_id": base_state["tenant_id"],
                    "user_id": base_state["user_id"],
                    "thread_id": base_state["thread_id"],
                    "run_id": "run-hint-only",
                    "slot_continuity": {
                        "source": "postgres_session_memory",
                        "continuity_claimed": True,
                        "active_slots": {"order_id": "ORD-HINT-ONLY"},
                    },
                    "policy_topic_hints": ["refund_policy@v1"],
                    "prior_policy_mention_refs": [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}],
                },
                "long_term_items": [],
                "case_items": [],
            },
        },
        {},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["recommendation_draft"]["missing_info"] == [
        "Verified policy evidence is required before recommendation generation.",
        "RAG context status blocked generation: verified_evidence_package_required",
    ]
    assert result["evidence_refs"] == []
    assert "proposed_action" not in result
    assert "claim_verification_bundle" not in result
    assert "safe_support_refs" not in result


def test_policy_evidence_required_for_generation_consumes_intent_registry(monkeypatch):
    calls: list[str] = []

    class FakeIntentRegistry:
        def requires_evidence(self, intent: str) -> bool:
            calls.append(intent)
            return intent == "order_status_inquiry"

    monkeypatch.setattr(recommendation_generation_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry())

    assert (
        recommendation_generation_module._policy_evidence_required_for_generation(
            {"primary_intent": "order_status_inquiry"}
        )
        is True
    )
    assert (
        recommendation_generation_module._policy_evidence_required_for_generation({"primary_intent": "small_talk"})
        is False
    )
    assert calls == ["order_status_inquiry", "small_talk"]


@pytest.mark.parametrize("requested_operation", ["draft_action", "execute_action", "escalate"])
def test_policy_evidence_required_for_generation_forces_executable_operations(
    requested_operation: str,
) -> None:
    assert (
        recommendation_generation_module._policy_evidence_required_for_generation(
            {
                "primary_intent": "small_talk",
                "requested_operation": requested_operation,
                "evidence_policy": {"evidence_required": False},
                "routing_hints": {"policy_evidence_required": False},
            }
        )
        is True
    )


def test_policy_evidence_required_for_generation_fails_closed_on_registry_error(monkeypatch):
    class RaisingIntentRegistry:
        def requires_evidence(self, intent: str) -> bool:
            raise RuntimeError(f"registry unavailable for {intent}")

    monkeypatch.setattr(recommendation_generation_module, "INTENT_POLICY_REGISTRY", RaisingIntentRegistry())

    assert recommendation_generation_module._policy_evidence_required_for_generation({"primary_intent": "policy_qa"})


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
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: FakeLLM(mixed_draft))
    _with_knowledge_service(
        monkeypatch, {(evidence.doc_key, evidence.chunk_id): "退款超时时，客服应核实支付通道和退款状态。"}
    )

    result = await recommendation_generation_module.recommendation_generation(
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
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: RaisingLLM(KeyError("bug")))

    with pytest.raises(KeyError, match="bug"):
        await recommendation_generation_module.recommendation_generation({**base_state, **_retrieval_state()})


@pytest.mark.asyncio
async def test_expected_error_retries_then_falls_back(monkeypatch, base_state):
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: RaisingLLM(ValueError("invalid")))

    result = await recommendation_generation_module.recommendation_generation({**base_state, **_retrieval_state()})

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["node_errors"][0]["retry_count"] == 2


@pytest.mark.asyncio
async def test_recommendation_generation_prompt_uses_context_assembly_and_excludes_raw_payloads(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    fake_llm = CapturingLLM(_draft())
    fake_conversation = FakeConversationService()
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): "Allowed verified policy text."})

    await recommendation_generation_module.recommendation_generation(
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


@pytest.mark.asyncio
async def test_recommendation_generation_prompt_uses_existing_session_memory_bundle_first(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    run_id = str(uuid4())
    fake_llm = CapturingLLM(_draft())
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): "Allowed verified policy text."})

    class ExplodingConversationService:
        async def load_prompt_context(self, **kwargs):
            raise AssertionError("existing session_memory_bundle should be used before conversation service")

    await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            "current_run_id": run_id,
            **_retrieval_state(evidence=[evidence]),
            "session_memory_bundle": {
                "schema_version": "session_memory_bundle.v1",
                "source": "session_memory_bundle",
                "tenant_id": base_state["tenant_id"],
                "user_id": base_state["user_id"],
                "thread_id": base_state["thread_id"],
                "run_id": run_id,
                "rolling_summary": {
                    "summary_id": "summary-existing-bundle",
                    "summary_text": "existing bundle rolling summary for ORD-BUNDLE-PROMPT",
                },
                "recent_messages": [
                    {
                        "message_id": "message-existing-bundle",
                        "run_id": run_id,
                        "message_index": 1,
                        "role": "user",
                        "content": "existing bundle recent message for ORD-BUNDLE-PROMPT",
                    }
                ],
                "tool_summaries": [
                    {
                        "tool_result_record_id": "record-existing-bundle",
                        "tool_result_id": "tool-result-existing-bundle",
                        "run_id": run_id,
                        "tool_call_id": "tool-call-existing-bundle",
                        "tool_name": "get_order",
                        "status": "success",
                        "prompt_summary": "get_order success from bundle source | existing bundle tool summary",
                        "business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-BUNDLE-PROMPT"}],
                        "policy_evidence_refs": [],
                        "audit_ref": "audit/existing-bundle",
                    }
                ],
                "slot_continuity": {
                    "source": "postgres_session_memory",
                    "continuity_claimed": False,
                    "active_slots": {},
                    "slot_metadata": {},
                },
                "fallback_reasons": {},
            },
        },
        {"configurable": {"session": object(), "conversation_service": ExplodingConversationService()}},
    )

    assert assemblies
    prompt = fake_llm.messages[-1]["content"]
    assert "existing bundle rolling summary" in prompt
    assert "existing bundle recent message" in prompt
    assert "existing bundle tool summary" in prompt
    assert "tool=get_order" in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt


@pytest.mark.asyncio
async def test_recommendation_generation_prompt_ignores_mismatched_session_memory_bundle(monkeypatch, base_state):
    evidence = _evidence(tenant_id=base_state["tenant_id"])
    run_id = str(uuid4())
    fake_llm = CapturingLLM(_draft())
    monkeypatch.setattr(recommendation_generation_module, "_get_llm", lambda: fake_llm)
    _with_knowledge_service(monkeypatch, {(evidence.doc_key, evidence.chunk_id): "Allowed verified policy text."})

    await recommendation_generation_module.recommendation_generation(
        {
            **base_state,
            "current_run_id": run_id,
            **_retrieval_state(evidence=[evidence]),
            "session_memory_bundle": {
                "schema_version": "session_memory_bundle.v1",
                "source": "session_memory_bundle",
                "tenant_id": base_state["tenant_id"],
                "user_id": base_state["user_id"],
                "thread_id": "other-thread",
                "run_id": str(uuid4()),
                "rolling_summary": {
                    "summary_id": "summary-wrong-scope",
                    "summary_text": "SHOULD_NOT_USE_MISMATCHED_BUNDLE_SUMMARY",
                },
                "recent_messages": [],
                "tool_summaries": [],
                "slot_continuity": {
                    "source": "postgres_session_memory",
                    "continuity_claimed": True,
                    "active_slots": {"order_id": "ORD-WRONG-BUNDLE"},
                    "slot_metadata": {"order_id": {"source": "trusted_session_memory"}},
                },
                "fallback_reasons": {},
            },
        },
        {},
    )

    prompt = fake_llm.messages[-1]["content"]
    assert "SHOULD_NOT_USE_MISMATCHED_BUNDLE_SUMMARY" not in prompt
    assert "ORD-WRONG-BUNDLE" not in prompt
