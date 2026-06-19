from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _load_claim_api():
    from src.agent.rag_context.claims import MaterialClaim, MaterialClaimAuthorityClass

    return MaterialClaim, MaterialClaimAuthorityClass


def _evidence_ref() -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text="Delivered orders require verified logistics evidence before compensation.",
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=1,
    )


def _business_fact_ref() -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=TENANT_ID,
        source_system="moca",
        resource_type="order",
        resource_id="ORD-1001",
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _base_claim_payload(authority_class: str) -> dict:
    evidence = _evidence_ref()
    business_ref = _business_fact_ref()
    return {
        "claim_id": f"claim-{authority_class}",
        "claim_text": "Delivered order ORD-1001 requires policy-backed review before compensation.",
        "authority_class": authority_class,
        "source_node": "generate_recommendation",
        "risk_level": "medium",
        "risk_hints": ["refund_dispute"],
        "cited_evidence_ids": [evidence.evidence_id] if authority_class != "business_fact_claim" else [],
        "business_fact_refs": [business_ref.model_dump(mode="json")] if authority_class != "policy_claim" else [],
        "dependency_claim_ids": ["claim-policy", "claim-business"]
        if authority_class == "action_recommendation_claim"
        else [],
        "verifier_status": None,
    }


def test_material_claim_allows_exact_required_authority_classes() -> None:
    """CLM-01: MaterialClaim supports exactly the three required authority classes."""
    MaterialClaim, MaterialClaimAuthorityClass = _load_claim_api()

    authority_values = {item.value for item in MaterialClaimAuthorityClass}

    assert authority_values == {
        "policy_claim",
        "business_fact_claim",
        "action_recommendation_claim",
    }
    for authority_class in authority_values:
        claim = MaterialClaim.model_validate(_base_claim_payload(authority_class))
        assert claim.authority_class.value == authority_class
        assert claim.claim_id == f"claim-{authority_class}"


def test_material_claim_rejects_unknown_authority_classes_and_extra_fields() -> None:
    """CLM-01: strict validation rejects unknown classes and unowned fields."""
    MaterialClaim, _MaterialClaimAuthorityClass = _load_claim_api()

    with pytest.raises(ValidationError):
        MaterialClaim.model_validate(_base_claim_payload("memory_claim"))

    payload = _base_claim_payload("policy_claim")
    payload["model_confidence_as_authority"] = 0.99
    with pytest.raises(ValidationError):
        MaterialClaim.model_validate(payload)


def test_material_claim_preserves_stable_claim_id_and_typed_authority_refs() -> None:
    """CLM-01/CLM-05: claim IDs are stable and authority refs stay typed/separate."""
    MaterialClaim, _MaterialClaimAuthorityClass = _load_claim_api()

    policy_claim = MaterialClaim.model_validate(_base_claim_payload("policy_claim"))
    business_claim = MaterialClaim.model_validate(_base_claim_payload("business_fact_claim"))
    action_claim = MaterialClaim.model_validate(_base_claim_payload("action_recommendation_claim"))

    assert policy_claim.claim_id == "claim-policy_claim"
    assert policy_claim.cited_evidence_ids == [_evidence_ref().evidence_id]
    assert policy_claim.business_fact_refs == []
    assert business_claim.cited_evidence_ids == []
    assert business_claim.business_fact_refs[0].resource_id == "ORD-1001"
    assert action_claim.dependency_claim_ids == ["claim-policy", "claim-business"]
    assert action_claim.business_fact_refs[0].schema_version == "business_fact_ref.v1"
    assert "memory" not in action_claim.model_dump_json()
