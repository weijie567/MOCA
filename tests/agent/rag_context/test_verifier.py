from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _load_verifier_api():
    from src.agent.rag_context.claims import MaterialClaim
    from src.agent.rag_context.verifier import MaterialClaimVerifier, VerificationOutcome

    return MaterialClaim, MaterialClaimVerifier, VerificationOutcome


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _evidence_ref(
    *,
    text: str = "Delivered orders require verified logistics evidence before compensation.",
    tenant_id: str = TENANT_ID,
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=1,
    )


def _business_fact_ref(resource_id: str = "ORD-1001") -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=TENANT_ID,
        source_system="moca",
        resource_type="order",
        resource_id=resource_id,
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _bundle(
    *,
    evidence: EvidenceRefV1,
    evidence_text: str,
    business_refs: list[BusinessFactRefV1] | None = None,
) -> dict[str, Any]:
    return {
        "trusted_context": {
            "tenant_id": TENANT_ID,
            "scope": {"merchant_ids": ["merchant-001"]},
            "effective_at": "2026-06-19T00:00:00+00:00",
            "run_id": "run-phase22-verifier",
            "thread_id": "thread-phase22-verifier",
        },
        "citation_map": {
            "C1": {
                "citation_id": "C1",
                "evidence_ref": evidence.model_dump(mode="json"),
                "source_evidence_ids": [evidence.evidence_id],
                "snippet": evidence_text,
                "risk_labels": [],
            }
        },
        "verifier_context": {
            "evidence_snippets": [
                {
                    "citation_id": "C1",
                    "evidence_id": evidence.evidence_id,
                    "text": evidence_text,
                }
            ],
            "business_fact_refs": [ref.model_dump(mode="json") for ref in business_refs or []],
        },
    }


def _claim_payload(authority_class: str, **overrides: Any) -> dict[str, Any]:
    evidence = _evidence_ref()
    payload: dict[str, Any] = {
        "claim_id": f"claim-{authority_class}",
        "claim_text": "Delivered orders require verified logistics evidence before compensation.",
        "authority_class": authority_class,
        "source_node": "generate_recommendation",
        "risk_level": "medium",
        "risk_hints": [],
        "cited_evidence_ids": [evidence.evidence_id] if authority_class == "policy_claim" else [],
        "business_fact_refs": [_business_fact_ref().model_dump(mode="json")]
        if authority_class == "business_fact_claim"
        else [],
        "dependency_claim_ids": [],
        "verifier_status": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_policy_claim_membership_is_not_semantic_support() -> None:
    """CLM-02/VER-02: citation membership is necessary but never sufficient."""
    MaterialClaim, MaterialClaimVerifier, VerificationOutcome = _load_verifier_api()
    evidence = _evidence_ref(text="This evidence discusses refund timing only.")
    claim = MaterialClaim.model_validate(
        _claim_payload(
            "policy_claim",
            claim_text="The merchant receives an automatic free vacation.",
            cited_evidence_ids=[evidence.evidence_id],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_bundle(evidence=evidence, evidence_text="This evidence discusses refund timing only."),
    )

    assert result.level1.membership_passed is True
    assert _value(result.outcome) == VerificationOutcome.UNSUPPORTED.value
    assert _value(result.level2.outcome) == "unsupported"
    assert "citation_membership_not_support" in result.reason_codes
    assert result.allows_claim is False


@pytest.mark.asyncio
async def test_level1_gates_run_before_any_supported_outcome() -> None:
    """VER-01: Level 1 gates run before support can be treated as supported."""
    MaterialClaim, MaterialClaimVerifier, VerificationOutcome = _load_verifier_api()
    wrong_tenant = _evidence_ref(
        text="Delivered orders require verified logistics evidence before compensation.",
        tenant_id="22222222-2222-2222-2222-222222222222",
    )
    claim = MaterialClaim.model_validate(_claim_payload("policy_claim", cited_evidence_ids=[wrong_tenant.evidence_id]))

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_bundle(
            evidence=wrong_tenant,
            evidence_text="Delivered orders require verified logistics evidence before compensation.",
        ),
    )

    assert result.level1.gates_run == [
        "bundle_membership",
        "tenant_scope",
        "text_hash",
        "freshness",
        "latest_policy_version",
        "authority_compatibility",
    ]
    assert _value(result.outcome) == VerificationOutcome.UNAUTHORIZED.value
    assert result.level2 is None
    assert result.allows_claim is False


@pytest.mark.parametrize(
    ("claim_text", "evidence_text", "expected_outcome"),
    [
        (
            "Delivered orders require verified logistics evidence before compensation.",
            "Delivered orders require verified logistics evidence before compensation.",
            "supported",
        ),
        (
            "The platform must issue a no-evidence coupon immediately.",
            "Delivered orders require verified logistics evidence before compensation.",
            "unsupported",
        ),
        (
            "Compensation may be available.",
            "",
            "insufficient",
        ),
        (
            "Compensation depends on delivery status and risk controls.",
            "Compensation may require review. Delivery status can affect review.",
            "ambiguous",
        ),
        (
            "High-risk compensation should proceed despite conflicting policy.",
            "Policy conflict detected between current and legacy sources.",
            "needs_semantic_review",
        ),
    ],
)
def test_level2_returns_typed_support_outcomes(
    claim_text: str,
    evidence_text: str,
    expected_outcome: str,
) -> None:
    """VER-03: Level 2 support checks return typed outcomes."""
    _MaterialClaim, MaterialClaimVerifier, _VerificationOutcome = _load_verifier_api()

    result = MaterialClaimVerifier().check_level2_support(
        claim_text=claim_text,
        evidence_snippets=[{"citation_id": "C1", "text": evidence_text}],
        risk_hints=["conflict"] if expected_outcome == "needs_semantic_review" else [],
    )

    assert _value(result.outcome) == expected_outcome


@pytest.mark.asyncio
async def test_business_fact_claim_requires_current_tool_system_refs() -> None:
    """CLM-03/CLM-05: policy evidence cannot satisfy business authority."""
    MaterialClaim, MaterialClaimVerifier, VerificationOutcome = _load_verifier_api()
    evidence = _evidence_ref()
    claim = MaterialClaim.model_validate(
        _claim_payload(
            "business_fact_claim",
            claim_text="Order ORD-1001 was delivered.",
            business_fact_refs=[],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_bundle(
            evidence=evidence,
            evidence_text="Policy says delivered orders need logistics evidence.",
            business_refs=[],
        ),
    )

    assert _value(result.outcome) == VerificationOutcome.BUSINESS_FACT_MISSING.value
    assert "business_fact_ref_required" in result.reason_codes
    assert result.allows_claim is False


@pytest.mark.asyncio
async def test_action_recommendation_requires_supported_policy_and_business_dependencies() -> None:
    """CLM-04: action recommendation claims fail closed on missing or unsupported dependencies."""
    MaterialClaim, MaterialClaimVerifier, VerificationOutcome = _load_verifier_api()
    evidence = _evidence_ref()
    claim = MaterialClaim.model_validate(
        _claim_payload(
            "action_recommendation_claim",
            claim_id="claim-action-1",
            claim_text="Issue a compensation coupon for ORD-1001.",
            dependency_claim_ids=["claim-policy-1", "claim-business-1"],
            business_fact_refs=[_business_fact_ref().model_dump(mode="json")],
            cited_evidence_ids=[evidence.evidence_id],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_bundle(
            evidence=evidence,
            evidence_text="Delivered orders require verified logistics evidence before compensation.",
            business_refs=[_business_fact_ref()],
        ),
        dependency_results=[
            {"claim_id": "claim-policy-1", "outcome": "supported"},
            {"claim_id": "claim-business-1", "outcome": "unsupported"},
        ],
    )

    assert _value(result.outcome) == VerificationOutcome.UNSUPPORTED.value
    assert "unsupported_business_dependency" in result.reason_codes
    assert result.allows_claim is False
    assert result.allows_action_recommendation is False
