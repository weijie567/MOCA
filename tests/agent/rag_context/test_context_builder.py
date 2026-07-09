from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _load_context_api():
    from src.agent.rag_context.builder import ContextBuilder
    from src.agent.rag_context.schemas import RagContextBundle

    return ContextBuilder, RagContextBundle


def _evidence_ref(
    *,
    doc_key: str = "policy_refund_timeout",
    chunk_id: str = "chunk_001",
    policy_version: str = "v3",
    text: str = "Delivered orders require verified logistics evidence before compensation.",
    tenant_id: str = TENANT_ID,
    rank: int | None = 1,
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=rank,
    )


def _business_fact_ref(
    *,
    resource_type: str = "order",
    resource_id: str = "ORD-1001",
) -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=TENANT_ID,
        source_system="moca",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _trusted_context() -> dict[str, Any]:
    return {
        "tenant_id": TENANT_ID,
        "run_id": "run-phase22-001",
        "thread_id": "thread-phase22-001",
        "effective_at": "2026-06-19T00:00:00+00:00",
        "scope": {"merchant_ids": ["merchant-001"]},
    }


class FakePolicyKnowledgeService:
    def __init__(
        self,
        contents: dict[str, str],
        *,
        latest_versions: dict[str, str] | None = None,
        authorized_evidence_ids: set[str] | None = None,
    ) -> None:
        self.contents = contents
        self.latest_versions = latest_versions or {}
        self.authorized_evidence_ids = authorized_evidence_ids
        self.content_lookup_calls: list[tuple[str, tuple[str, ...]]] = []

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, str]:
        self.content_lookup_calls.append((tenant_id, tuple(ref.evidence_id for ref in evidence_refs)))
        return {
            ref.evidence_id: self.contents[ref.evidence_id]
            for ref in evidence_refs
            if ref.tenant_id == tenant_id
            and ref.evidence_id in self.contents
            and (self.authorized_evidence_ids is None or ref.evidence_id in self.authorized_evidence_ids)
            and self.latest_versions.get(ref.doc_key, ref.policy_version) == ref.policy_version
        }


def _json_text(value: Any) -> str:
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


@pytest.mark.asyncio
async def test_context_builder_returns_separate_prompt_verifier_debug_and_final_projections() -> None:
    """CTX-01: build a bundle with separate prompt/verifier/debug/final projections."""
    ContextBuilder, RagContextBundle = _load_context_api()
    evidence = _evidence_ref()
    business_ref = _business_fact_ref()
    service = FakePolicyKnowledgeService(
        {
            evidence.evidence_id: (
                "Delivered orders require verified logistics evidence before compensation. "
                "High-risk compensation must keep policy and business authority separate."
            )
        }
    )

    bundle = await ContextBuilder(policy_service=service, max_snippet_chars=180).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[business_ref],
        trusted_context=_trusted_context(),
        risk_hints=[{"evidence_id": evidence.evidence_id, "labels": ["high_risk", "provenance_available"]}],
    )

    assert isinstance(bundle, RagContextBundle)
    assert bundle.prompt_context is not None
    assert bundle.verifier_context is not None
    assert bundle.debug_context is not None
    assert bundle.final_response_context is not None
    assert bundle.prompt_context != bundle.debug_context
    assert evidence.evidence_id in bundle.citation_map["C1"].evidence_ref.evidence_id
    assert business_ref.resource_id in _json_text(bundle.verifier_context)
    assert "source_block_id" not in _json_text(bundle.prompt_context)
    assert "text_hash" not in _json_text(bundle.prompt_context)
    assert service.content_lookup_calls == [(TENANT_ID, (evidence.evidence_id,))]


@pytest.mark.asyncio
async def test_prompt_citation_ids_map_to_canonical_refs_with_bounded_prompt_safe_metadata() -> None:
    """CTX-03: prompt citations preserve canonical refs while exposing bounded safe metadata."""
    ContextBuilder, _RagContextBundle = _load_context_api()
    long_text = " ".join(
        [
            "Delivered orders require verified logistics evidence before compensation.",
            "Raw provenance and OCR metadata must not be exposed in prompts.",
            "This extra sentence should be clipped from the prompt snippet when the bound is low.",
        ]
    )
    evidence = _evidence_ref(text=long_text)
    service = FakePolicyKnowledgeService({evidence.evidence_id: long_text})

    bundle = await ContextBuilder(policy_service=service, max_snippet_chars=96).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[{"evidence_id": evidence.evidence_id, "labels": ["ocr_low_confidence"]}],
    )

    citation = bundle.prompt_context.citations[0]
    map_entry = bundle.citation_map[citation.citation_id]

    assert citation.citation_id == "C1"
    assert citation.display_label == "policy_refund_timeout / chunk_001"
    assert citation.snippet.endswith("[truncated]")
    assert len(citation.snippet) <= 110
    assert citation.risk_labels == ["ocr_low_confidence"]
    assert citation.metadata == {
        "doc_key": evidence.doc_key,
        "chunk_id": evidence.chunk_id,
        "policy_version": evidence.policy_version,
    }
    assert map_entry.evidence_ref == evidence
    assert map_entry.source_evidence_ids == [evidence.evidence_id]


@pytest.mark.asyncio
async def test_manual_review_sensitive_survives_prompt_safe_risk_label_projection() -> None:
    """Phase 64: manual-review labels must not be filtered from safe RAG projections."""
    ContextBuilder, _RagContextBundle = _load_context_api()
    text = "Manual review sensitive policy evidence must stay visible to safe projections."
    evidence = _evidence_ref(text=text)
    service = FakePolicyKnowledgeService({evidence.evidence_id: text})

    bundle = await ContextBuilder(policy_service=service, max_snippet_chars=180).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[
            {
                "evidence_id": evidence.evidence_id,
                "labels": ["manual_review_sensitive", "raw_debug_secret"],
            }
        ],
    )

    assert bundle.prompt_context.citations[0].risk_labels == ["manual_review_sensitive"]
    assert bundle.citation_map["C1"].risk_labels == ["manual_review_sensitive"]
    assert bundle.prompt_context.risk_labels == ["manual_review_sensitive"]
    assert bundle.final_response_context.risk_labels == ["manual_review_sensitive"]
    assert bundle.memory_context.risk_labels == ["manual_review_sensitive"]
    assert bundle.replay_context.risk_labels == ["manual_review_sensitive"]
    assert bundle.business_fact_context.risk_labels == ["manual_review_sensitive"]
    assert bundle.action_snapshot_context.risk_labels == ["manual_review_sensitive"]

    safe_surfaces = {
        "prompt_context": bundle.prompt_context,
        "final_response_context": bundle.final_response_context,
        "memory_context": bundle.memory_context,
        "replay_context": bundle.replay_context,
        "business_fact_context": bundle.business_fact_context,
        "action_snapshot_context": bundle.action_snapshot_context,
        "citation_map": bundle.citation_map,
    }
    assert "raw_debug_secret" not in _json_text(safe_surfaces)


@pytest.mark.asyncio
async def test_duplicate_and_adjacent_evidence_merge_projection_without_rewriting_identity() -> None:
    """CTX-04: dedupe and projection-only merging cannot rewrite EvidenceRefV1 identity."""
    ContextBuilder, _RagContextBundle = _load_context_api()
    first = _evidence_ref(chunk_id="chunk_001", text="Rule part one: verify delivery before compensation.", rank=1)
    duplicate = _evidence_ref(chunk_id="chunk_001", text="Rule part one: verify delivery before compensation.", rank=2)
    adjacent = _evidence_ref(chunk_id="chunk_002", text="Rule part two: approvals remain required.", rank=3)
    service = FakePolicyKnowledgeService(
        {
            first.evidence_id: "Rule part one: verify delivery before compensation.",
            duplicate.evidence_id: "Rule part one: verify delivery before compensation.",
            adjacent.evidence_id: "Rule part two: approvals remain required.",
        }
    )

    bundle = await ContextBuilder(policy_service=service, merge_adjacent_chunks=True).build(
        candidate_evidence_refs=[first, duplicate, adjacent],
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[],
    )

    assert list(bundle.citation_map) == ["C1"]
    assert bundle.citation_map["C1"].source_evidence_ids == [first.evidence_id, adjacent.evidence_id]
    assert bundle.citation_map["C1"].evidence_ref.evidence_id == first.evidence_id
    assert first.evidence_id != adjacent.evidence_id
    assert "chunk_001" in bundle.prompt_context.citations[0].display_label
    assert "chunk_002" in bundle.prompt_context.citations[0].merged_from_chunk_ids
    assert bundle.debug_context.included_evidence[0].reason_code == "included"
    assert bundle.debug_context.truncated_or_excluded_evidence[0].reason_code == "duplicate_evidence_key"


@pytest.mark.asyncio
async def test_wrong_tenant_duplicate_cannot_discard_valid_tenant_evidence() -> None:
    """CTX-02/CTX-04: duplicate collapse must not run across tenant boundaries."""
    ContextBuilder, _RagContextBundle = _load_context_api()
    text = "Tenant-valid policy evidence should survive wrong-tenant duplicates."
    wrong_tenant = _evidence_ref(
        text=text,
        tenant_id="22222222-2222-2222-2222-222222222222",
        rank=1,
    )
    valid = _evidence_ref(text=text, tenant_id=TENANT_ID, rank=2)
    service = FakePolicyKnowledgeService({valid.evidence_id: text})

    bundle = await ContextBuilder(policy_service=service).build(
        candidate_evidence_refs=[wrong_tenant, valid],
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[],
    )

    exclusion_codes = {
        (entry.evidence_id, entry.reason_code) for entry in bundle.debug_context.truncated_or_excluded_evidence
    }

    assert bundle.citation_map["C1"].evidence_ref == valid
    assert bundle.citation_map["C1"].source_evidence_ids == [valid.evidence_id]
    assert (wrong_tenant.evidence_id, "tenant_mismatch") in exclusion_codes
    assert (valid.evidence_id, "duplicate_evidence_key") not in exclusion_codes


@pytest.mark.asyncio
async def test_invalid_evidence_is_excluded_before_prompt_or_claim_support() -> None:
    """CTX-01/CTX-03: invalid evidence is excluded before prompt or support projections."""
    ContextBuilder, _RagContextBundle = _load_context_api()
    valid = _evidence_ref()
    wrong_tenant = _evidence_ref(
        chunk_id="chunk_wrong_tenant",
        text="Wrong tenant policy must not enter the bundle.",
        tenant_id="22222222-2222-2222-2222-222222222222",
        rank=2,
    )
    latest_invalid = _evidence_ref(
        doc_key="policy_legacy",
        chunk_id="chunk_legacy",
        policy_version="v1",
        text="Legacy policy must not support current claims.",
        rank=3,
    )
    unauthorized = _evidence_ref(
        chunk_id="chunk_scope_invalid",
        text="Scope-invalid evidence must not enter prompts.",
        rank=4,
    )
    service = FakePolicyKnowledgeService(
        {
            valid.evidence_id: "Valid policy evidence for current tenant and scope.",
            wrong_tenant.evidence_id: "Wrong tenant policy must not enter the bundle.",
            latest_invalid.evidence_id: "Legacy policy must not support current claims.",
            unauthorized.evidence_id: "Scope-invalid evidence must not enter prompts.",
        },
        latest_versions={"policy_legacy": "v3"},
        authorized_evidence_ids={valid.evidence_id, wrong_tenant.evidence_id, latest_invalid.evidence_id},
    )

    bundle = await ContextBuilder(policy_service=service).build(
        candidate_evidence_refs=[valid, wrong_tenant, latest_invalid, unauthorized],
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[],
    )

    prompt_text = _json_text(bundle.prompt_context)
    verifier_text = _json_text(bundle.verifier_context)
    exclusion_codes = {entry.reason_code for entry in bundle.debug_context.truncated_or_excluded_evidence}

    assert valid.evidence_id in bundle.citation_map["C1"].source_evidence_ids
    assert wrong_tenant.evidence_id not in prompt_text
    assert latest_invalid.evidence_id not in prompt_text
    assert unauthorized.evidence_id not in prompt_text
    assert wrong_tenant.evidence_id not in verifier_text
    assert latest_invalid.evidence_id not in verifier_text
    assert unauthorized.evidence_id not in verifier_text
    assert {"tenant_mismatch", "latest_version_invalid", "scope_invalid"} <= exclusion_codes
