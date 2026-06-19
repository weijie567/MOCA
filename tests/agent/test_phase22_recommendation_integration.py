from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from tests.agent.conftest import FakeLLM


TENANT_ID = "11111111-1111-1111-1111-111111111111"


class AttrDict(dict[str, Any]):
    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def _evidence_ref(tenant_id: str = TENANT_ID) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v2",
        text="Refund policy requires current evidence and verified business facts before compensation.",
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=1,
    )


def _retrieval_state(evidence: EvidenceRefV1) -> dict[str, Any]:
    return {
        "retrieved_evidence": {
            "schema_version": "knowledge_search_result.v2",
            "evidence_refs": [evidence.model_dump(mode="json")],
        },
        "evidence_refs": [evidence.model_dump(mode="json")],
    }


def _model_draft_with_model_selected_safety_route() -> dict[str, Any]:
    return {
        "recommended_action": "issue_coupon",
        "reasoning_summary": "The model claims this is safe.",
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": "chunk_001",
                "title": "Refund policy",
                "section": "Compensation",
            }
        ],
        "confidence": 0.93,
        "risk_level": "low",
        "missing_info": [],
        "verification_route": "allow",
        "safety_route_selected_by": "model",
    }


class ExplodingNodeLocalPolicyService:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def get_verified_evidence_contents(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        raise AssertionError("generate_recommendation must use the shared ContextBuilder for evidence re-fetch")


class FakeContextBuilder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def build(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        evidence = kwargs["candidate_evidence_refs"][0]
        evidence_payload = evidence.model_dump(mode="json")
        return AttrDict(
            trusted_context=kwargs["trusted_context"],
            prompt_context=AttrDict(
                citations=[
                    AttrDict(
                        citation_id="C1",
                        evidence_id=evidence.evidence_id,
                        display_label=f"{evidence.doc_key} / {evidence.chunk_id}",
                        snippet="Refund policy requires current evidence and verified business facts.",
                    )
                ]
            ),
            verifier_context={
                "evidence_snippets": [
                    {
                        "citation_id": "C1",
                        "evidence_id": evidence.evidence_id,
                        "text": "Refund policy requires current evidence and verified business facts.",
                    }
                ],
                "business_fact_refs": [],
                "safe_refs": [evidence.evidence_id],
            },
            citation_map={
                "C1": AttrDict(
                    citation_id="C1",
                    evidence_ref=evidence_payload,
                    source_evidence_ids=[evidence.evidence_id],
                    snippet="Refund policy requires current evidence and verified business facts.",
                    risk_labels=[],
                )
            },
            final_response_context={"safe_citations": ["C1"]},
            debug_context={"builder_trace_id": "debug-only"},
        )


class FakeMaterialClaimVerifier:
    def __init__(self, route: str = "manual_review", outcome: str = "conflicting") -> None:
        self.route = route
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def verify_recommendation(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            overall_outcome=self.outcome,
            allows_recommendation=self.route == "allow",
            route=SimpleNamespace(
                route=self.route,
                selected_by="backend",
                model_selected=False,
                decision_source="phase22_verifier",
            ),
            material_claims=[
                {
                    "claim_id": "claim-policy-1",
                    "authority_class": "policy_claim",
                    "verifier_status": self.outcome,
                }
            ],
            reason_codes=["conflicting_evidence"],
        )

    async def verify_claims(self, claims: list[Any], context_bundle: Any, **kwargs: Any) -> SimpleNamespace:
        return await self.verify_recommendation(
            claims=claims,
            context_bundle=context_bundle,
            **kwargs,
        )


def _unsupported_action_draft_with_valid_citation() -> dict[str, Any]:
    return {
        "recommended_action": "issue_coupon",
        "reasoning_summary": "The merchant needs no verified facts and should be compensated automatically.",
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": "chunk_001",
                "title": "Refund policy",
                "section": "Compensation",
            }
        ],
        "confidence": 0.93,
        "risk_level": "high",
        "missing_info": [],
    }


@pytest.mark.asyncio
async def test_generate_recommendation_uses_shared_context_builder_and_verifier_not_node_local_refetch(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-03: recommendation generation uses shared Phase 22 kernel output."""
    evidence = _evidence_ref(base_state["tenant_id"])
    builder = FakeContextBuilder()
    verifier = FakeMaterialClaimVerifier(route="manual_review", outcome="conflicting")

    monkeypatch.setattr(generate_recommendation_module, "ContextBuilder", lambda **kwargs: builder)
    monkeypatch.setattr(generate_recommendation_module, "MaterialClaimVerifier", lambda **kwargs: verifier)
    monkeypatch.setattr(generate_recommendation_module, "PolicyKnowledgeService", ExplodingNodeLocalPolicyService)
    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_model_draft_with_model_selected_safety_route()),
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence)},
        {"configurable": {"session": object()}},
    )

    assert builder.calls
    assert builder.calls[0]["candidate_evidence_refs"] == [evidence]
    assert verifier.calls
    assert verifier.calls[0]["context_bundle"].citation_map["C1"].evidence_ref["evidence_id"] == evidence.evidence_id
    assert result["rag_context_bundle"]["citation_map"]["C1"]["source_evidence_ids"] == [evidence.evidence_id]
    assert result["rag_verification"]["overall_outcome"] == "conflicting"
    assert result["rag_verification"]["route"]["route"] == "manual_review"
    assert result["rag_verification"]["route"]["selected_by"] == "backend"
    assert result["rag_verification"]["route"]["model_selected"] is False
    assert result["recommendation_draft"]["material_claims"][0]["authority_class"] == "policy_claim"


@pytest.mark.asyncio
async def test_model_never_selects_safety_route_when_verifier_returns_backend_route(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-03/RTE-04: model-supplied allow routes are ignored in favor of backend verifier output."""
    evidence = _evidence_ref(base_state["tenant_id"])
    builder = FakeContextBuilder()
    verifier = FakeMaterialClaimVerifier(route="insufficient_evidence", outcome="unsupported")

    monkeypatch.setattr(generate_recommendation_module, "ContextBuilder", lambda **kwargs: builder)
    monkeypatch.setattr(generate_recommendation_module, "MaterialClaimVerifier", lambda **kwargs: verifier)
    monkeypatch.setattr(
        generate_recommendation_module, "_get_llm", lambda: FakeLLM(_model_draft_with_model_selected_safety_route())
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence)},
        {"configurable": {"session": object()}},
    )

    assert result["rag_verification"]["route"]["route"] == "insufficient_evidence"
    assert result["rag_verification"]["route"]["selected_by"] == "backend"
    assert result["rag_verification"]["route"]["model_selected"] is False
    assert result["recommendation_draft"]["verification_route"] != "allow"
    assert result["recommendation_draft"]["recommended_action"] in {
        "insufficient_evidence",
        "manual_review",
        "refuse",
        "regenerate_route",
    }


@pytest.mark.asyncio
async def test_valid_citation_membership_does_not_allow_unsupported_action_recommendation(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """CLM-03/RTE-04: citation membership is not semantic support for an action recommendation."""
    evidence = _evidence_ref(base_state["tenant_id"])
    builder = FakeContextBuilder()

    monkeypatch.setattr(generate_recommendation_module, "ContextBuilder", lambda **kwargs: builder)
    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_unsupported_action_draft_with_valid_citation()),
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence)},
        {"configurable": {"session": object()}},
    )

    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert result["verification_route"] != "allow"
    assert result["recommendation_draft"]["recommended_action"] in {
        "insufficient_evidence",
        "manual_review",
        "refuse",
        "regenerate_route",
    }
    claims = result["recommendation_draft"]["material_claims"]
    assert any(claim["authority_class"] == "policy_claim" for claim in claims)
    assert any(claim["authority_class"] == "action_recommendation_claim" for claim in claims)
