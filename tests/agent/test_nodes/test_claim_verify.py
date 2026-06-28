from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    ClaimVerificationResultV1,
    EvidenceRefV1,
    MaterialClaimV1,
)
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _ref(text: str = "Refund timeout compensation requires verified policy evidence.") -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=1,
    )


def _business_fact_ref() -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=TENANT_ID,
        source_system="moca",
        resource_type="refund_case",
        resource_id="RF-1001",
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _package(ref: EvidenceRefV1) -> dict[str, Any]:
    return {
        "schema_version": "verified_evidence_package.v1",
        "package_id": "pkg-verified",
        "status": "verified",
        "evidence_items": [],
        "citation_map": {"C1": [ref.evidence_id]},
        "evidence_map": {ref.evidence_id: ref.model_dump(mode="json")},
        "prompt_projection": {"citations": [{"citation_id": "C1"}]},
        "verifier_projection": {
            "safe_refs": [ref.evidence_id],
            "evidence_snippets": [
                {
                    "citation_id": "C1",
                    "evidence_id": ref.evidence_id,
                    "text": "Refund timeout compensation requires verified policy evidence.",
                }
            ],
            "business_fact_refs": [],
        },
        "replay_snapshot_refs": [ref.evidence_id],
        "debug_projection": {},
        "stale_refs": [],
        "conflict_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "policy_version": "v3",
        "retrieval_config_version": "retrieval.v3",
    }


def _claim(
    claim_id: str,
    claim_type: str,
    ref: EvidenceRefV1,
    *,
    business_fact_refs: list[BusinessFactRefV1] | None = None,
) -> MaterialClaimV1:
    return MaterialClaimV1(
        claim_id=claim_id,
        claim_text="Refund compensation is supported by verified policy and merchant facts.",
        claim_type=claim_type,
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=business_fact_refs or [],
        risk_hints=[],
        generated_from_step="recommendation_generation",
    )


def _bundle(
    *,
    ref: EvidenceRefV1,
    route: str = "continue",
    overall_status: str = "verified",
    blocked_claims: list[str] | None = None,
    claim_results: list[ClaimVerificationResultV1] | None = None,
    reason_codes: list[str] | None = None,
    safe_support_refs: list[EvidenceRefV1] | None = None,
) -> ClaimVerificationBundleV1:
    return ClaimVerificationBundleV1(
        overall_status=overall_status,
        route=route,
        claim_results=claim_results or [],
        blocked_claims=blocked_claims or [],
        safe_support_refs=safe_support_refs if safe_support_refs is not None else [ref],
        reason_codes=reason_codes or [],
        verifier_policy_version="material_claim_verifier.v1",
    )


class RecordingClaimService:
    def __init__(self, bundle: ClaimVerificationBundleV1) -> None:
        self.bundle = bundle
        self.calls: list[dict[str, Any]] = []

    async def verify_claims(self, **kwargs: Any) -> ClaimVerificationBundleV1:
        self.calls.append(kwargs)
        return self.bundle


class RaisingClaimService:
    async def verify_claims(self, **kwargs: Any) -> ClaimVerificationBundleV1:
        raise RuntimeError("claim verifier unavailable")


def _config(service: Any) -> dict[str, Any]:
    return {"configurable": {"policy_knowledge_service": service}}


@pytest.mark.asyncio
async def test_claim_verify_calls_knowledge_service_and_writes_only_claim_fields() -> None:
    from src.agent.nodes.claim_verify import claim_verify

    ref = _ref()
    business_ref = _business_fact_ref()
    bundle = _bundle(ref=ref)
    service = RecordingClaimService(bundle)
    material_claims = [
        _claim("claim-policy", "policy", ref),
        _claim("claim-business", "business_fact", ref, business_fact_refs=[business_ref]),
        _claim("claim-action", "action_recommendation", ref, business_fact_refs=[business_ref]),
    ]
    state = {
        "material_claims": [claim.model_dump(mode="json") for claim in material_claims],
        "verified_evidence_package": _package(ref),
        "business_context": {"business_fact_refs": [business_ref.model_dump(mode="json")]},
        "proposed_action": {"type": "create_compensation_review"},
        "trace_steps": [{"node": "recommendation_generation", "status": "completed"}],
        "rag_context_status": "verified",
        "risk_assessment": {"risk_level": "high"},
        "action_draft": {"id": "draft-should-not-be-touched"},
    }

    result = await claim_verify(state, _config(service))

    assert set(result) == {
        "claim_verification_bundle",
        "blocked_claims",
        "safe_support_refs",
        "verifier_status",
        "verification_route",
        "verifier_reason_codes",
        "verifier_safe_citation_refs",
        "trace_steps",
    }
    assert len(service.calls) == 1
    call = service.calls[0]
    assert [claim["claim_id"] for claim in call["material_claims"]] == [
        "claim-policy",
        "claim-business",
        "claim-action",
    ]
    assert call["verified_evidence_package"]["package_id"] == "pkg-verified"
    assert call["business_context"]["business_fact_refs"][0]["resource_id"] == "RF-1001"
    assert call["proposed_action"]["type"] == "create_compensation_review"
    assert result["claim_verification_bundle"]["route"] == "continue"
    assert result["blocked_claims"] == []
    assert result["safe_support_refs"] == [ref.model_dump(mode="json")]
    assert result["verifier_status"] == "verified"
    assert result["verification_route"] == "allow"
    assert result["verifier_safe_citation_refs"] == [ref.evidence_id]
    assert [step["node"] for step in result["trace_steps"]] == [
        "recommendation_generation",
        "claim_verify",
    ]

    for forbidden_key in (
        "rag_context_status",
        "verified_evidence_package",
        "citation_map",
        "evidence_map",
        "material_claims",
        "proposed_action",
        "risk_assessment",
        "approval_plan",
        "action_draft",
    ):
        assert forbidden_key not in result


@pytest.mark.asyncio
async def test_claim_verify_verifier_error_fails_closed_to_final_response() -> None:
    from src.agent.nodes.claim_verify import claim_verify

    ref = _ref()
    result = await claim_verify(
        {
            "material_claims": [_claim("claim-policy", "policy", ref).model_dump(mode="json")],
            "verified_evidence_package": _package(ref),
            "business_context": {},
            "proposed_action": None,
            "trace_steps": [],
        },
        _config(RaisingClaimService()),
    )

    assert result["claim_verification_bundle"]["overall_status"] == "error"
    assert result["claim_verification_bundle"]["route"] == "final_response"
    assert result["blocked_claims"] == []
    assert result["safe_support_refs"] == []
    assert result["verifier_status"] == "error"
    assert result["verification_route"] == "refuse"
    assert "claim_verify_error" in result["verifier_reason_codes"]
    assert result["trace_steps"][-1]["node"] == "claim_verify"
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_claim_verify_preserves_business_fact_and_action_authority_blocks() -> None:
    from src.agent.nodes.claim_verify import claim_verify

    ref = _ref(text="Tenant public policy describes refund eligibility rules.")
    business_result = ClaimVerificationResultV1(
        claim_id="claim-business",
        claim_type="business_fact",
        support_status="unsupported",
        supporting_evidence_refs=[],
        business_fact_refs=[],
        rule_checks=[{"rule": "business_fact_ref_required", "passed": False}],
        semantic_review_status="not_needed",
        allows_user_visible_claim=False,
        allows_action_recommendation=False,
    )
    action_result = ClaimVerificationResultV1(
        claim_id="claim-action",
        claim_type="action_recommendation",
        support_status="unsupported",
        supporting_evidence_refs=[],
        business_fact_refs=[],
        rule_checks=[{"rule": "business_dependency_required", "passed": False}],
        semantic_review_status="not_needed",
        allows_user_visible_claim=False,
        allows_action_recommendation=False,
    )
    service = RecordingClaimService(
        _bundle(
            ref=ref,
            route="final_response",
            overall_status="blocked",
            blocked_claims=["claim-business", "claim-action"],
            claim_results=[business_result, action_result],
            reason_codes=["business_fact_ref_required", "business_dependency_required"],
            safe_support_refs=[],
        )
    )

    result = await claim_verify(
        {
            "material_claims": [
                _claim("claim-business", "business_fact", ref).model_dump(mode="json"),
                _claim("claim-action", "action_recommendation", ref).model_dump(mode="json"),
            ],
            "verified_evidence_package": _package(ref),
            "business_context": {"business_fact_refs": []},
            "proposed_action": {"type": "create_compensation_review"},
            "trace_steps": [],
        },
        _config(service),
    )

    assert result["claim_verification_bundle"]["route"] == "final_response"
    assert result["blocked_claims"] == ["claim-business", "claim-action"]
    assert result["safe_support_refs"] == []
    assert result["verification_route"] == "refuse"
    assert result["verifier_status"] == "blocked"
    assert "business_fact_ref_required" in result["verifier_reason_codes"]
    assert "business_dependency_required" in result["verifier_reason_codes"]
    assert all(
        claim_result["allows_action_recommendation"] is False
        for claim_result in result["claim_verification_bundle"]["claim_results"]
    )
