from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    ClaimVerificationResultV1,
    EvidenceRefV1,
    MaterialClaimV1,
)
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _evidence_ref() -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text="Refund timeout compensation requires verified policy evidence.",
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

