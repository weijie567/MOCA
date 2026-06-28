from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.business.schemas import BusinessFactResultV1
from src.knowledge.service import PolicyKnowledgeService
from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    ClaimVerificationResultV1,
    EvidenceRefV1,
    MaterialClaimV1,
)
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _evidence_ref(text: str = "Refund timeout compensation requires verified policy evidence.") -> EvidenceRefV1:
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


def _verified_package(ref: EvidenceRefV1 | None = None) -> dict:
    evidence_ref = ref or _evidence_ref()
    return {
        "schema_version": "verified_evidence_package.v1",
        "package_id": "pkg-verified",
        "status": "verified",
        "evidence_items": [],
        "citation_map": {"C1": [evidence_ref.evidence_id]},
        "evidence_map": {evidence_ref.evidence_id: evidence_ref.model_dump(mode="json")},
        "prompt_projection": {"citations": ["C1"]},
        "verifier_projection": {
            "safe_refs": [evidence_ref.evidence_id],
            "evidence_snippets": [
                {
                    "citation_id": "C1",
                    "evidence_id": evidence_ref.evidence_id,
                    "text": "Refund timeout compensation requires verified policy evidence.",
                }
            ],
            "business_fact_refs": [],
        },
        "replay_snapshot_refs": [evidence_ref.evidence_id],
        "debug_projection": {},
        "stale_refs": [],
        "conflict_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "policy_version": "v3",
        "retrieval_config_version": "retrieval.v3",
    }


def test_material_claim_v1_uses_canonical_claim_type_fields() -> None:
    """APF-14: canonical claim records use claim_type and generated_from_step."""
    ref = _evidence_ref()
    business_ref = _business_fact_ref()

    claim = MaterialClaimV1(
        claim_id="claim-action",
        claim_text="Issue a compensation recommendation only after verified refund facts.",
        claim_type="action_recommendation",
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=[business_ref],
        risk_hints=["refund_compensation"],
        generated_from_step="recommendation_generation",
    )

    assert claim.schema_version == "material_claim.v1"
    assert claim.claim_type == "action_recommendation"
    assert claim.generated_from_step == "recommendation_generation"
    assert claim.business_fact_refs[0].schema_version == "business_fact_ref.v1"


def test_claim_verification_bundle_accepts_exact_status_and_route_literals() -> None:
    """APF-14: bundle status, route, support, and semantic literals are pinned."""
    ref = _evidence_ref()
    business_ref = _business_fact_ref()
    support_statuses = {"supported", "unsupported", "partial", "ambiguous", "not_applicable", "error"}
    semantic_statuses = {"not_needed", "passed", "failed", "ambiguous", "timeout"}

    for support_status in support_statuses:
        for semantic_review_status in semantic_statuses:
            result = ClaimVerificationResultV1(
                claim_id=f"claim-{support_status}-{semantic_review_status}",
                claim_type="business_fact",
                support_status=support_status,
                supporting_evidence_refs=[ref] if support_status == "supported" else [],
                business_fact_refs=[business_ref],
                rule_checks=[{"rule": "business_fact_ref_required", "passed": True}],
                semantic_review_status=semantic_review_status,
                allows_user_visible_claim=support_status == "supported",
                allows_action_recommendation=False,
            )
            assert result.support_status == support_status
            assert result.semantic_review_status == semantic_review_status

    bundle = ClaimVerificationBundleV1(
        overall_status="verified",
        route="continue",
        claim_results=[
            ClaimVerificationResultV1(
                claim_id="claim-business",
                claim_type="business_fact",
                support_status="supported",
                supporting_evidence_refs=[],
                business_fact_refs=[business_ref],
                rule_checks=[{"rule": "business_fact_ref_required", "passed": True}],
                semantic_review_status="not_needed",
                allows_user_visible_claim=True,
                allows_action_recommendation=False,
            )
        ],
        blocked_claims=[],
        safe_support_refs=[ref],
        reason_codes=[],
        verifier_policy_version="claim_verifier.v1",
    )

    assert bundle.schema_version == "claim_verification_bundle.v1"
    assert bundle.overall_status == "verified"
    assert bundle.route == "continue"


def test_claim_verification_bundle_rejects_unknown_route_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ClaimVerificationBundleV1(
            overall_status="verified",
            route="risk_gate",
            claim_results=[],
            blocked_claims=[],
            safe_support_refs=[],
            reason_codes=[],
            verifier_policy_version="claim_verifier.v1",
        )

    with pytest.raises(ValidationError):
        MaterialClaimV1(
            claim_id="claim-extra",
            claim_text="A claim with unowned authority metadata.",
            claim_type="policy",
            cited_evidence_ids=[],
            business_fact_refs=[],
            risk_hints=[],
            generated_from_step="recommendation_generation",
            authority_class="policy_claim",
        )


@pytest.mark.asyncio
async def test_verify_claims_blocks_business_fact_claim_without_business_fact_authority() -> None:
    """APF-14: RAG evidence cannot replace BusinessFactRefV1 / BusinessFactResultV1 authority."""
    ref = _evidence_ref()
    service = PolicyKnowledgeService(retriever=object())
    business_claim = MaterialClaimV1(
        claim_id="claim-business",
        claim_text="Refund case RF-1001 is eligible for compensation.",
        claim_type="business_fact",
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=[],
        risk_hints=[],
        generated_from_step="recommendation_generation",
    )

    bundle = await service.verify_claims(
        material_claims=[business_claim],
        verified_evidence_package=_verified_package(ref),
        business_context={"business_fact_refs": []},
        proposed_action=None,
    )

    assert bundle.overall_status == "blocked"
    assert bundle.route == "final_response"
    assert bundle.blocked_claims == ["claim-business"]
    assert "business_fact_ref_required" in bundle.reason_codes
    assert bundle.claim_results[0].support_status == "unsupported"
    assert bundle.claim_results[0].semantic_review_status == "not_needed"


@pytest.mark.asyncio
async def test_verify_claims_continues_for_supported_policy_business_and_action_claims() -> None:
    """APF-14: action recommendations require both policy support and merchant-scoped business authority."""
    ref = _evidence_ref()
    business_ref = _business_fact_ref()
    package = _verified_package(ref)
    package["verifier_projection"]["business_fact_refs"] = [business_ref.model_dump(mode="json")]
    service = PolicyKnowledgeService(retriever=object())
    claims = [
        MaterialClaimV1(
            claim_id="claim-policy",
            claim_text="Refund timeout compensation requires verified policy evidence.",
            claim_type="policy",
            cited_evidence_ids=[ref.evidence_id],
            business_fact_refs=[],
            risk_hints=[],
            generated_from_step="recommendation_generation",
        ),
        MaterialClaimV1(
            claim_id="claim-business",
            claim_text="Refund case RF-1001 is merchant scoped.",
            claim_type="business_fact",
            cited_evidence_ids=[],
            business_fact_refs=[business_ref],
            risk_hints=[],
            generated_from_step="recommendation_generation",
        ),
        MaterialClaimV1(
            claim_id="claim-action",
            claim_text="Issue a compensation review for RF-1001.",
            claim_type="action_recommendation",
            cited_evidence_ids=[ref.evidence_id],
            business_fact_refs=[business_ref],
            risk_hints=[],
            generated_from_step="recommendation_generation",
        ),
    ]

    bundle = await service.verify_claims(
        material_claims=claims,
        verified_evidence_package=package,
        business_context={"business_fact_refs": [business_ref.model_dump(mode="json")]},
        proposed_action={"type": "create_compensation_review"},
    )

    assert bundle.overall_status == "verified"
    assert bundle.route == "continue"
    assert bundle.blocked_claims == []
    assert {result.claim_id for result in bundle.claim_results} == {
        "claim-policy",
        "claim-business",
        "claim-action",
    }
    assert all(result.support_status == "supported" for result in bundle.claim_results)
    assert ref in bundle.safe_support_refs


@pytest.mark.asyncio
async def test_verify_claims_preserves_hard_rule_checks_in_claim_results() -> None:
    """APF-14: ClaimVerificationResultV1.rule_checks records hard-gate outcomes."""
    ref = _evidence_ref(text="Merchant is not eligible for compensation.")
    package = _verified_package(ref)
    package["verifier_projection"]["evidence_snippets"] = [
        {
            "citation_id": "C1",
            "evidence_id": ref.evidence_id,
            "text": "Merchant is not eligible for compensation.",
        }
    ]
    claim = MaterialClaimV1(
        claim_id="claim-policy-negation",
        claim_text="Merchant is eligible for compensation.",
        claim_type="policy",
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=[],
        risk_hints=[],
        generated_from_step="recommendation_generation",
    )

    bundle = await PolicyKnowledgeService(retriever=object()).verify_claims(
        material_claims=[claim],
        verified_evidence_package=package,
        business_context={},
        proposed_action=None,
    )

    assert bundle.overall_status == "blocked"
    assert bundle.route == "final_response"
    assert bundle.blocked_claims == ["claim-policy-negation"]
    assert "negation_conflict" in bundle.reason_codes
    assert any(
        check["rule"] == "negation_conflict" and check["passed"] is False
        for check in bundle.claim_results[0].rule_checks
    )


@pytest.mark.asyncio
async def test_verify_claims_routes_manual_review_for_ambiguous_policy_support() -> None:
    """APF-14: ambiguous support produces manual_review, not continue."""
    ref = _evidence_ref(text="Compensation may require review. Delivery status can affect review.")
    package = _verified_package(ref)
    package["verifier_projection"]["evidence_snippets"] = [
        {
            "citation_id": "C1",
            "evidence_id": ref.evidence_id,
            "text": "Compensation may require review. Delivery status can affect review.",
        }
    ]
    claim = MaterialClaimV1(
        claim_id="claim-policy-ambiguous",
        claim_text="Compensation depends on delivery status and risk controls.",
        claim_type="policy",
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=[],
        risk_hints=[],
        generated_from_step="recommendation_generation",
    )

    bundle = await PolicyKnowledgeService(retriever=object()).verify_claims(
        material_claims=[claim],
        verified_evidence_package=package,
        business_context={},
        proposed_action=None,
    )

    assert bundle.overall_status == "manual_review"
    assert bundle.route == "manual_review"
    assert bundle.blocked_claims == ["claim-policy-ambiguous"]


@pytest.mark.asyncio
async def test_tenant_public_policy_cannot_support_business_fact_without_business_fact_result() -> None:
    """APF-14: tenant public policy evidence cannot replace merchant-scoped BusinessFactRefV1 / BusinessFactResultV1 authority."""
    ref = _evidence_ref(text="Tenant public policy describes refund eligibility rules.")
    unavailable_result = BusinessFactResultV1(
        tenant_id=TENANT_ID,
        status="unavailable",
        fact=None,
        business_fact_refs=[],
        resource_version=None,
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        source_system="moca",
        scope_check_result="allowed",
        missing_required_facts=["refund_case"],
        safe_errors=[],
    )
    claim = MaterialClaimV1(
        claim_id="claim-business-policy-only",
        claim_text="Refund case RF-1001 is eligible for compensation.",
        claim_type="business_fact",
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=[],
        risk_hints=[],
        generated_from_step="recommendation_generation",
    )

    bundle = await PolicyKnowledgeService(retriever=object()).verify_claims(
        material_claims=[claim],
        verified_evidence_package=_verified_package(ref),
        business_context={"business_fact_results": [unavailable_result.model_dump(mode="json")]},
        proposed_action=None,
    )

    assert bundle.route == "final_response"
    assert bundle.blocked_claims == ["claim-business-policy-only"]
    assert "business_fact_ref_required" in bundle.reason_codes


@pytest.mark.asyncio
async def test_tenant_public_policy_cannot_support_action_recommendation_without_action_authority() -> None:
    """APF-14: action_recommendation claims need BusinessFactRefV1 authority; RAG evidence alone is not action-safe."""
    ref = _evidence_ref(text="Tenant public policy describes refund compensation review rules.")
    claim = MaterialClaimV1(
        claim_id="claim-action-policy-only",
        claim_text="Issue a compensation review for refund case RF-1001.",
        claim_type="action_recommendation",
        cited_evidence_ids=[ref.evidence_id],
        business_fact_refs=[],
        risk_hints=[],
        generated_from_step="recommendation_generation",
    )

    bundle = await PolicyKnowledgeService(retriever=object()).verify_claims(
        material_claims=[claim],
        verified_evidence_package=_verified_package(ref),
        business_context={"business_fact_refs": []},
        proposed_action={"type": "create_compensation_review"},
    )

    assert bundle.route == "final_response"
    assert bundle.blocked_claims == ["claim-action-policy-only"]
    assert bundle.safe_support_refs == []
    assert "dependency_claims_required" in bundle.reason_codes
    assert bundle.claim_results[0].allows_action_recommendation is False


@pytest.mark.asyncio
async def test_verify_claims_malformed_input_fails_closed_to_final_response() -> None:
    """APF-14: malformed inputs fail closed to final_response."""
    bundle = await PolicyKnowledgeService(retriever=object()).verify_claims(
        material_claims=[{"claim_id": ""}],
        verified_evidence_package=_verified_package(),
        business_context={},
        proposed_action=None,
    )

    assert bundle.overall_status == "error"
    assert bundle.route == "final_response"
    assert "claim_input_malformed" in bundle.reason_codes
