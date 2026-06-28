from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _load_authority_api():
    from src.agent.rag_context.claims import MaterialClaim
    from src.agent.rag_context.verifier import MaterialClaimVerifier

    return MaterialClaim, MaterialClaimVerifier


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _evidence_ref(tenant_id: str = TENANT_ID) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text="Delivered orders require verified logistics evidence before compensation.",
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=1,
    )


def _business_fact_ref(tenant_id: str = TENANT_ID) -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=tenant_id,
        source_system="moca",
        resource_type="order",
        resource_id="ORD-1001",
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _claim(authority_class: str, **overrides: Any) -> dict[str, Any]:
    evidence = _evidence_ref()
    payload: dict[str, Any] = {
        "claim_id": f"claim-{authority_class}",
        "claim_text": "Order ORD-1001 can receive compensation.",
        "authority_class": authority_class,
        "source_node": "generate_recommendation",
        "risk_level": "high",
        "risk_hints": ["action_boundary"],
        "cited_evidence_ids": [evidence.evidence_id] if authority_class != "business_fact_claim" else [],
        "business_fact_refs": [_business_fact_ref().model_dump(mode="json")]
        if authority_class != "policy_claim"
        else [],
        "dependency_claim_ids": [],
        "verifier_status": None,
    }
    payload.update(overrides)
    return payload


def _context_with_contextual_only_sources() -> dict[str, Any]:
    evidence = _evidence_ref()
    return {
        "trusted_context": {
            "tenant_id": TENANT_ID,
            "run_id": "run-authority-boundary",
            "thread_id": "thread-authority-boundary",
            "effective_at": "2026-06-19T00:00:00+00:00",
            "scope": {"merchant_ids": ["merchant-001"]},
        },
        "citation_map": {},
        "verifier_context": {
            "evidence_snippets": [],
            "business_fact_refs": [],
        },
        "contextual_sources": {
            "session_memory": [
                {
                    "memory_id": "memory-1",
                    "content": "Merchant prefers fast compensation.",
                    "forged_evidence_ref": evidence.model_dump(mode="json"),
                }
            ],
            "case_memory": [
                {
                    "case_memory_id": "case-1",
                    "excerpt": "Prior case used compensation after reviewed evidence.",
                    "policy_refs": [{"doc_key": evidence.doc_key, "chunk_id": evidence.chunk_id}],
                }
            ],
            "model_knowledge": ["Common marketplace practice says compensation is acceptable."],
            "source_provenance": [
                {
                    "source_block_id": "source-block-private",
                    "bbox": [1, 2, 3, 4],
                    "ocr_confidence": 0.42,
                }
            ],
        },
    }


def _context_with_business_fact_substitution_source(source_name: str, payload: Any) -> dict[str, Any]:
    context = _context_with_contextual_only_sources()
    context["contextual_sources"] = {source_name: payload}
    return context


@pytest.mark.asyncio
async def test_memory_case_memory_and_model_knowledge_cannot_support_policy_claims() -> None:
    """CLM-05/BND-04: contextual memory and model knowledge cannot satisfy policy authority."""
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    claim = MaterialClaim.model_validate(
        _claim(
            "policy_claim",
            claim_text="Compensation is always allowed.",
            cited_evidence_ids=[],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_context_with_contextual_only_sources(),
    )

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert {
        "policy_evidence_required",
        "memory_not_policy_authority",
        "model_knowledge_not_policy_authority",
    } <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_policy_evidence_and_provenance_cannot_support_business_fact_claims() -> None:
    """CLM-03/CLM-05/BND-03: business facts require current Tool System refs."""
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    evidence = _evidence_ref()
    context = _context_with_contextual_only_sources()
    context["citation_map"] = {
        "C1": {
            "citation_id": "C1",
            "evidence_ref": evidence.model_dump(mode="json"),
            "source_evidence_ids": [evidence.evidence_id],
            "snippet": "Policy evidence is not a business fact.",
        }
    }
    context["verifier_context"]["evidence_snippets"] = [
        {"citation_id": "C1", "evidence_id": evidence.evidence_id, "text": "Policy evidence is not a business fact."}
    ]
    claim = MaterialClaim.model_validate(
        _claim(
            "business_fact_claim",
            claim_text="Order ORD-1001 was delivered.",
            cited_evidence_ids=[evidence.evidence_id],
            business_fact_refs=[],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(claim, context_bundle=context)

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert {
        "business_fact_ref_required",
        "policy_evidence_not_business_authority",
        "provenance_not_business_authority",
    } <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_business_fact_claim_rejects_wrong_tenant_business_ref() -> None:
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    wrong_tenant_ref = _business_fact_ref(tenant_id="22222222-2222-2222-2222-222222222222")
    context = _context_with_contextual_only_sources()
    context["verifier_context"]["business_fact_refs"] = [wrong_tenant_ref.model_dump(mode="json")]
    claim = MaterialClaim.model_validate(
        _claim(
            "business_fact_claim",
            claim_text="Order ORD-1001 was delivered.",
            business_fact_refs=[wrong_tenant_ref.model_dump(mode="json")],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(claim, context_bundle=context)

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert result.level1.tenant_scope_passed is False
    assert {"tenant_scope_invalid", "business_fact_ref_required"} <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_business_fact_claim_rejects_missing_trusted_tenant_even_when_refs_match() -> None:
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    other_tenant_ref = _business_fact_ref(tenant_id="22222222-2222-2222-2222-222222222222")
    context = _context_with_contextual_only_sources()
    context["trusted_context"] = {}
    context["verifier_context"]["business_fact_refs"] = [other_tenant_ref.model_dump(mode="json")]
    claim = MaterialClaim.model_validate(
        _claim(
            "business_fact_claim",
            claim_text="Order ORD-1001 was delivered.",
            business_fact_refs=[other_tenant_ref.model_dump(mode="json")],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(claim, context_bundle=context)

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert result.level1.tenant_scope_passed is False
    assert {"tenant_scope_invalid", "business_fact_ref_required"} <= set(result.reason_codes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_name", "payload", "expected_reason"),
    [
        (
            "session_memory",
            [{"memory_id": "mem-raw-order", "content": "Order ORD-1001 was delivered."}],
            "memory_not_business_authority",
        ),
        (
            "model_knowledge",
            ["Model knowledge says order ORD-1001 was delivered."],
            "model_knowledge_not_business_authority",
        ),
        (
            "prompt_summaries",
            [{"tool_name": "get_order", "prompt_summary": "Order ORD-1001 was delivered."}],
            "prompt_summary_not_business_authority",
        ),
        (
            "raw_repository_rows",
            [{"order_no": "ORD-1001", "status": "delivered", "merchant_id": "merchant-001"}],
            "raw_repository_row_not_business_authority",
        ),
    ],
)
async def test_memory_model_prompt_summary_and_raw_repository_rows_cannot_support_business_fact_claims(
    source_name: str,
    payload: Any,
    expected_reason: str,
) -> None:
    """APF-08: current business fact claims require BusinessFactRefV1 authority."""
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    claim = MaterialClaim.model_validate(
        _claim(
            "business_fact_claim",
            claim_text="Order ORD-1001 was delivered.",
            business_fact_refs=[],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_context_with_business_fact_substitution_source(source_name, payload),
    )

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert {"business_fact_ref_required", expected_reason} <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_contextual_only_memory_refs_and_status_refs_have_explicit_non_authority_reasons() -> None:
    """APF-10: typed contextual-only memory refs/status refs are never authority refs."""
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    contextual_sources = {
        "session_context_refs": [
            {
                "schema_version": "session_context_ref.v1",
                "authority_class": "contextual_only",
                "tenant_id": TENANT_ID,
                "user_id": "user-authority-boundary",
                "thread_id": "thread-authority-boundary",
                "run_id": "run-authority-boundary",
                "source": "session_context_load",
                "ref_id": "session-context-ref-authority-boundary",
            }
        ],
        "reviewed_memory_refs": [
            {
                "schema_version": "reviewed_memory_ref.v1",
                "authority_class": "contextual_only",
                "tenant_id": TENANT_ID,
                "memory_type": "long_term",
                "scope_type": "merchant",
                "scope_id": "merchant-authority-boundary",
                "memory_id": "reviewed-memory-ref-authority-boundary",
                "review_status": "approved",
                "prompt_safe": True,
            }
        ],
        "memory_status_refs": [
            {
                "schema_version": "memory_write_decision.v2",
                "authority_class": "contextual_only",
                "status": "written",
                "decision": "write",
                "memory_type": "session",
                "scope": {"scope_type": "thread", "thread_id": "thread-authority-boundary"},
                "pii_classification": "none",
                "review_status": "not_applicable",
                "reason_code": "eligible",
            }
        ],
    }
    context = _context_with_contextual_only_sources()
    context["contextual_sources"] = contextual_sources
    policy_claim = MaterialClaim.model_validate(
        _claim(
            "policy_claim",
            claim_id="claim-contextual-memory-policy-ref",
            cited_evidence_ids=["session-context-ref-authority-boundary"],
        )
    )
    business_claim = MaterialClaim.model_validate(
        _claim(
            "business_fact_claim",
            claim_id="claim-contextual-memory-business-ref",
            business_fact_refs=[],
        )
    )

    policy_result = await MaterialClaimVerifier().verify_claim(policy_claim, context_bundle=context)
    business_result = await MaterialClaimVerifier().verify_claim(business_claim, context_bundle=context)

    assert _value(policy_result.outcome) != "supported"
    assert "memory_contextual_ref_not_policy_authority" in policy_result.reason_codes
    assert policy_result.safe_support_refs == []
    assert _value(business_result.outcome) != "supported"
    assert {
        "business_fact_ref_required",
        "memory_contextual_ref_not_business_authority",
    } <= set(business_result.reason_codes)
    assert business_result.safe_support_refs == []


@pytest.mark.asyncio
async def test_contextual_memory_citation_map_entry_cannot_support_policy_claim() -> None:
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    contextual_ref = {
        "schema_version": "reviewed_memory_ref.v1",
        "authority_class": "contextual_only",
        "tenant_id": TENANT_ID,
        "memory_type": "long_term",
        "scope_type": "merchant",
        "scope_id": "merchant-authority-boundary",
        "memory_id": "mem-ref-1",
        "review_status": "approved",
        "prompt_safe": True,
    }
    context = {
        "trusted_context": {
            "tenant_id": TENANT_ID,
            "run_id": "run-authority-boundary",
            "thread_id": "thread-authority-boundary",
        },
        "citation_map": {
            "C1": {
                "citation_id": "C1",
                "evidence_ref": contextual_ref,
                "source_evidence_ids": ["mem-ref-1"],
                "snippet": "Refund policy allows compensation.",
            }
        },
        "verifier_context": {
            "business_fact_refs": [],
            "evidence_snippets": [
                {
                    "citation_id": "C1",
                    "evidence_id": "mem-ref-1",
                    "text": "Refund policy allows compensation.",
                }
            ],
            "safe_refs": ["mem-ref-1"],
        },
        "contextual_sources": {},
    }
    claim = MaterialClaim.model_validate(
        _claim(
            "policy_claim",
            claim_id="claim-contextual-citation-not-policy-evidence",
            claim_text="Refund policy allows compensation.",
            cited_evidence_ids=["mem-ref-1"],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(claim, context_bundle=context)

    assert _value(result.outcome) != "supported"
    assert result.safe_support_refs == []
    assert {
        "policy_evidence_required",
        "memory_contextual_ref_not_policy_authority",
    } <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_action_recommendation_rejects_memory_or_model_supported_dependencies() -> None:
    """CLM-04/CLM-05: action recommendations need supported policy and business dependencies."""
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    evidence = _evidence_ref()
    claim = MaterialClaim.model_validate(
        _claim(
            "action_recommendation_claim",
            claim_id="claim-action-memory-only",
            claim_text="Issue a coupon based on memory and model knowledge.",
            cited_evidence_ids=[evidence.evidence_id],
            business_fact_refs=[_business_fact_ref().model_dump(mode="json")],
            dependency_claim_ids=["claim-policy-memory", "claim-business-model"],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_context_with_contextual_only_sources(),
        dependency_results=[
            {"claim_id": "claim-policy-memory", "outcome": "supported_by_memory"},
            {"claim_id": "claim-business-model", "outcome": "supported_by_model_knowledge"},
        ],
    )

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert result.allows_action_recommendation is False
    assert result.blocks_proposed_action is True
    assert {
        "policy_dependency_not_evidence_supported",
        "business_dependency_not_tool_supported",
    } <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_action_recommendation_rejects_missing_policy_evidence_even_with_supported_dependencies() -> None:
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    business_ref = _business_fact_ref()
    context = _context_with_contextual_only_sources()
    context["verifier_context"]["business_fact_refs"] = [business_ref.model_dump(mode="json")]
    claim = MaterialClaim.model_validate(
        _claim(
            "action_recommendation_claim",
            claim_id="claim-action-no-policy-evidence",
            claim_text="Issue compensation for order ORD-1001.",
            cited_evidence_ids=[],
            business_fact_refs=[business_ref.model_dump(mode="json")],
            dependency_claim_ids=["claim-policy-1", "claim-business-1"],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=context,
        dependency_results=[
            {"claim_id": "claim-policy-1", "outcome": "supported"},
            {"claim_id": "claim-business-1", "outcome": "supported"},
        ],
    )

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert result.allows_action_recommendation is False
    assert result.blocks_proposed_action is True
    assert result.level1.membership_passed is False
    assert "policy_evidence_required" in result.reason_codes


@pytest.mark.asyncio
async def test_action_recommendation_rejects_wrong_tenant_business_ref() -> None:
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    evidence = _evidence_ref()
    wrong_tenant_ref = _business_fact_ref(tenant_id="22222222-2222-2222-2222-222222222222")
    context = _context_with_contextual_only_sources()
    context["citation_map"] = {
        "C1": {
            "citation_id": "C1",
            "evidence_ref": evidence.model_dump(mode="json"),
            "source_evidence_ids": [evidence.evidence_id],
            "snippet": "Delivered orders require verified logistics evidence before compensation.",
        }
    }
    context["verifier_context"]["evidence_snippets"] = [
        {
            "citation_id": "C1",
            "evidence_id": evidence.evidence_id,
            "text": "Delivered orders require verified logistics evidence before compensation.",
        }
    ]
    context["verifier_context"]["business_fact_refs"] = [wrong_tenant_ref.model_dump(mode="json")]
    claim = MaterialClaim.model_validate(
        _claim(
            "action_recommendation_claim",
            claim_id="claim-action-wrong-tenant",
            claim_text="Issue compensation for order ORD-1001.",
            cited_evidence_ids=[evidence.evidence_id],
            business_fact_refs=[wrong_tenant_ref.model_dump(mode="json")],
            dependency_claim_ids=["claim-policy-1", "claim-business-1"],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=context,
        dependency_results=[
            {"claim_id": "claim-policy-1", "outcome": "supported"},
            {"claim_id": "claim-business-1", "outcome": "supported"},
        ],
    )

    assert _value(result.outcome) != "supported"
    assert result.allows_claim is False
    assert result.allows_action_recommendation is False
    assert result.blocks_proposed_action is True
    assert result.level1.tenant_scope_passed is False
    assert {"tenant_scope_invalid", "business_fact_ref_required"} <= set(result.reason_codes)


@pytest.mark.asyncio
async def test_action_recommendation_rejects_wrong_tenant_policy_evidence_with_valid_business_ref() -> None:
    MaterialClaim, MaterialClaimVerifier = _load_authority_api()
    wrong_tenant_evidence = _evidence_ref(tenant_id="22222222-2222-2222-2222-222222222222")
    business_ref = _business_fact_ref()
    context = _context_with_contextual_only_sources()
    context["citation_map"] = {
        "C1": {
            "citation_id": "C1",
            "evidence_ref": wrong_tenant_evidence.model_dump(mode="json"),
            "source_evidence_ids": [wrong_tenant_evidence.evidence_id],
            "snippet": "Delivered orders require verified logistics evidence before compensation.",
        }
    }
    context["verifier_context"]["evidence_snippets"] = [
        {
            "citation_id": "C1",
            "evidence_id": wrong_tenant_evidence.evidence_id,
            "text": "Delivered orders require verified logistics evidence before compensation.",
        }
    ]
    context["verifier_context"]["business_fact_refs"] = [business_ref.model_dump(mode="json")]
    claim = MaterialClaim.model_validate(
        _claim(
            "action_recommendation_claim",
            claim_id="claim-action-wrong-tenant-policy",
            claim_text="Issue compensation for order ORD-1001.",
            cited_evidence_ids=[wrong_tenant_evidence.evidence_id],
            business_fact_refs=[business_ref.model_dump(mode="json")],
            dependency_claim_ids=["claim-policy-1", "claim-business-1"],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=context,
        dependency_results=[
            {"claim_id": "claim-policy-1", "outcome": "supported"},
            {"claim_id": "claim-business-1", "outcome": "supported"},
        ],
    )

    assert _value(result.outcome) == "unauthorized"
    assert result.allows_claim is False
    assert result.allows_action_recommendation is False
    assert result.blocks_proposed_action is True
    assert result.level1.tenant_scope_passed is False
    assert "tenant_scope_invalid" in result.reason_codes
