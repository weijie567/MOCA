from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import ClaimVerificationBundleV1, ClaimVerificationResultV1, EvidenceRefV1
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


def _verified_package_state(evidence: EvidenceRefV1) -> dict[str, Any]:
    package = {
        "schema_version": "verified_evidence_package.v1",
        "package_id": "pkg-phase22-compat",
        "status": "verified",
        "evidence_items": [],
        "citation_map": {"C1": [evidence.evidence_id]},
        "evidence_map": {evidence.evidence_id: evidence.model_dump(mode="json")},
        "prompt_projection": {
            "schema_version": "rag_prompt_context.v1",
            "citations": [
                {
                    "citation_id": "C1",
                    "display_label": f"{evidence.doc_key} / {evidence.chunk_id}",
                    "snippet": "Refund policy requires current evidence and verified business facts.",
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
        "verifier_projection": {
            "safe_refs": [evidence.evidence_id],
            "evidence_snippets": [],
            "business_fact_refs": [],
        },
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
        "rag_context_status": "verified",
        "verified_evidence_package": package,
        "citation_map": package["citation_map"],
        "evidence_map": package["evidence_map"],
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


class RecordingClaimVerifyService:
    def __init__(self, bundle: ClaimVerificationBundleV1) -> None:
        self.bundle = bundle
        self.calls: list[dict[str, Any]] = []

    async def verify_claims(self, **kwargs: Any) -> ClaimVerificationBundleV1:
        self.calls.append(kwargs)
        return self.bundle


def _claim_result(
    *,
    claim_id: str,
    claim_type: str,
    support_status: str = "unsupported",
    allows_action_recommendation: bool = False,
    allows_user_visible_claim: bool = False,
) -> ClaimVerificationResultV1:
    return ClaimVerificationResultV1(
        claim_id=claim_id,
        claim_type=claim_type,
        support_status=support_status,
        supporting_evidence_refs=[],
        business_fact_refs=[],
        rule_checks=[{"rule": "phase33_integration_guard", "passed": support_status == "supported"}],
        semantic_review_status="not_needed",
        allows_user_visible_claim=allows_user_visible_claim,
        allows_action_recommendation=allows_action_recommendation,
    )


def _claim_bundle(
    *,
    route: str = "final_response",
    overall_status: str = "blocked",
    blocked_claims: list[str] | None = None,
    reason_codes: list[str] | None = None,
    claim_results: list[ClaimVerificationResultV1] | None = None,
) -> ClaimVerificationBundleV1:
    return ClaimVerificationBundleV1(
        overall_status=overall_status,
        route=route,
        claim_results=claim_results or [],
        blocked_claims=blocked_claims or [],
        safe_support_refs=[],
        reason_codes=reason_codes or [],
        verifier_policy_version="material_claim_verifier.v1",
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


def _supported_policy_action_draft_missing_business_support() -> dict[str, Any]:
    return {
        "recommended_action": "issue_coupon",
        "reasoning_summary": "Refund policy requires current evidence and verified business facts.",
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
async def test_generate_recommendation_consumes_verified_package_and_does_not_node_local_refetch(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-03: recommendation generation consumes Phase 33 package output only."""
    evidence = _evidence_ref(base_state["tenant_id"])

    assert not hasattr(generate_recommendation_module, "ContextBuilder")
    assert not hasattr(generate_recommendation_module, "MaterialClaimVerifier")
    assert not hasattr(generate_recommendation_module, "PolicyKnowledgeService")
    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_model_draft_with_model_selected_safety_route()),
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence), **_verified_package_state(evidence)},
        {"configurable": {"session": object()}},
    )

    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert result["recommendation_draft"]["material_claims"][0]["claim_type"] == "policy"
    assert result["recommendation_draft"]["material_claims"][0]["generated_from_step"] == "recommendation_generation"
    assert "rag_context_bundle" not in result
    assert "rag_verification" not in result
    assert "claim_verification_bundle" not in result


@pytest.mark.asyncio
async def test_model_selected_safety_route_is_ignored_until_backend_claim_verify(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-03/RTE-04: model-supplied allow routes are ignored in favor of backend verifier output."""
    from src.agent.nodes.claim_verify import claim_verify

    evidence = _evidence_ref(base_state["tenant_id"])
    service = RecordingClaimVerifyService(
        _claim_bundle(
            route="manual_review",
            overall_status="manual_review",
            reason_codes=["semantic_review_required"],
        )
    )

    monkeypatch.setattr(
        generate_recommendation_module, "_get_llm", lambda: FakeLLM(_model_draft_with_model_selected_safety_route())
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence), **_verified_package_state(evidence)},
        {"configurable": {"session": object()}},
    )
    verify_result = await claim_verify(
        {**base_state, **_verified_package_state(evidence), **result},
        {"configurable": {"policy_knowledge_service": service}},
    )

    assert "verification_route" not in result["recommendation_draft"]
    assert service.calls
    assert verify_result["claim_verification_bundle"]["route"] == "manual_review"
    assert verify_result["verification_route"] == "manual_review"
    assert "semantic_review_required" in verify_result["verifier_reason_codes"]


@pytest.mark.asyncio
async def test_valid_citation_membership_does_not_allow_unsupported_action_recommendation(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """CLM-03/RTE-04: citation membership is not semantic support for an action recommendation."""
    from src.agent.nodes.claim_verify import claim_verify

    evidence = _evidence_ref(base_state["tenant_id"])
    service = RecordingClaimVerifyService(
        _claim_bundle(
            blocked_claims=["claim-action-1"],
            reason_codes=["business_dependency_required"],
            claim_results=[
                _claim_result(
                    claim_id="claim-action-1",
                    claim_type="action_recommendation",
                    allows_action_recommendation=False,
                )
            ],
        )
    )

    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_unsupported_action_draft_with_valid_citation()),
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence), **_verified_package_state(evidence)},
        {"configurable": {"session": object()}},
    )
    verify_result = await claim_verify(
        {**base_state, **_verified_package_state(evidence), **result},
        {"configurable": {"policy_knowledge_service": service}},
    )

    assert result["recommendation_draft"]["citation_validation"]["is_valid"] is True
    claims = result["recommendation_draft"]["material_claims"]
    assert any(claim["claim_type"] == "policy" for claim in claims)
    assert any(claim["claim_type"] == "action_recommendation" for claim in claims)
    assert verify_result["verification_route"] == "refuse"
    assert verify_result["blocked_claims"] == ["claim-action-1"]
    assert "business_dependency_required" in verify_result["verifier_reason_codes"]


@pytest.mark.asyncio
async def test_supported_policy_claim_does_not_mask_failed_action_dependency(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """CLM-04/RTE-04: a supported policy claim cannot mask missing action dependencies."""
    from src.agent.nodes.claim_verify import claim_verify

    evidence = _evidence_ref(base_state["tenant_id"])
    service = RecordingClaimVerifyService(
        _claim_bundle(
            blocked_claims=["claim-action-1"],
            reason_codes=["dependency_result_missing"],
            claim_results=[
                _claim_result(
                    claim_id="claim-policy-1",
                    claim_type="policy",
                    support_status="supported",
                    allows_user_visible_claim=True,
                ),
                _claim_result(
                    claim_id="claim-action-1",
                    claim_type="action_recommendation",
                    allows_action_recommendation=False,
                ),
            ],
        )
    )

    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_supported_policy_action_draft_missing_business_support()),
    )

    result = await generate_recommendation_module.generate_recommendation(
        {**base_state, **_retrieval_state(evidence), **_verified_package_state(evidence)},
        {"configurable": {"session": object()}},
    )
    verify_result = await claim_verify(
        {**base_state, **_verified_package_state(evidence), **result},
        {"configurable": {"policy_knowledge_service": service}},
    )

    assert any(claim["claim_type"] == "policy" for claim in result["material_claims"])
    assert any(claim["claim_type"] == "action_recommendation" for claim in result["material_claims"])
    assert verify_result["claim_verification_bundle"]["overall_status"] == "blocked"
    assert verify_result["verification_route"] == "refuse"
    assert "dependency_result_missing" in verify_result["verifier_reason_codes"]


@pytest.mark.asyncio
async def test_missing_verified_package_fails_closed_instead_of_allowing_membership_only(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
) -> None:
    """RTE-04: required evidence cannot fall back to citation membership without a verified package."""
    evidence = _evidence_ref(base_state["tenant_id"])

    monkeypatch.setattr(
        generate_recommendation_module,
        "_get_llm",
        lambda: FakeLLM(_supported_policy_action_draft_missing_business_support()),
    )

    result = await generate_recommendation_module.generate_recommendation(
        {
            **base_state,
            **_retrieval_state(evidence),
            "routing_hints": {"policy_evidence_required": True},
        },
        {},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["material_claims"] == []
    assert "verified_evidence_package_required" in " ".join(result["recommendation_draft"]["missing_info"])
