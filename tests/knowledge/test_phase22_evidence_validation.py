from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest

from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.service import PolicyKnowledgeService


TENANT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT_ID = "22222222-2222-2222-2222-222222222222"


def _load_context_api():
    from src.agent.rag_context.builder import ContextBuilder

    return ContextBuilder


def _evidence_ref(
    *,
    tenant_id: str = TENANT_ID,
    doc_key: str = "policy_refund_timeout",
    chunk_id: str = "chunk_001",
    policy_version: str = "v2",
    text: str = "Current refund policy text.",
    rank: int = 1,
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=rank,
    )


def _trusted_context(**overrides: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "run_id": "run-phase22-evidence-validation",
        "thread_id": "thread-phase22-evidence-validation",
        "effective_at": "2026-06-19T00:00:00+00:00",
        "merchant_scope": ["merchant-001"],
        "scope": {
            "merchant_ids": ["merchant-001"],
            "doc_types": ["refund_rule"],
            "risk_levels": ["high"],
        },
        "filters": {
            "doc_type": "refund_rule",
            "risk_level": "high",
        },
    }
    context.update(overrides)
    return context


def _canonical_row(ref: EvidenceRefV1, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tenant_id": ref.tenant_id,
        "doc_key": ref.doc_key,
        "chunk_id": ref.chunk_id,
        "content": "Current refund policy text.",
        "policy_document_version": 2,
        "current_policy_version": "v2",
        "effective_date": "2026-06-01",
        "expires_at": None,
        "doc_type": "refund_rule",
        "risk_level": "high",
        "merchant_ids": ["merchant-001"],
    }
    row.update(overrides)
    return row


class FakeCanonicalPolicyService:
    def __init__(self, rows: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.rows = rows
        self.content_lookup_calls: list[tuple[str, tuple[str, ...]]] = []
        self.canonical_lookup_calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    async def get_canonical_evidence_rows(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        keys = tuple((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
        self.canonical_lookup_calls.append((tenant_id, keys))
        return {key: row for key, row in self.rows.items() if row["tenant_id"] == tenant_id}

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, str]:
        self.content_lookup_calls.append((tenant_id, tuple(ref.evidence_id for ref in evidence_refs)))
        result: dict[str, str] = {}
        for ref in evidence_refs:
            row = self.rows.get((ref.doc_key, ref.chunk_id))
            if row is not None and row["tenant_id"] == tenant_id:
                result[ref.evidence_id] = row["content"]
        return result


class FakeCanonicalRetriever:
    def __init__(self, rows: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id: Any,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        self.calls.append((str(tenant_id), tuple(keys)))
        return {key: row for key, row in self.rows.items() if key in keys}


def _json_text(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, default=str, sort_keys=True)
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _get(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field)


def _reason_codes(entry: Any) -> set[str]:
    explicit_codes = _get(entry, "reason_codes") if hasattr(entry, "reason_codes") or isinstance(entry, dict) else None
    if explicit_codes:
        return set(explicit_codes)
    return {_get(entry, "reason_code")}


@pytest.mark.asyncio
async def test_policy_knowledge_service_verified_details_rejects_current_row_version_mismatch() -> None:
    """Task 2: current-row PolicyDocument.version=2 rejects incoming policy_version='v1'."""
    tenant_id = str(uuid4())
    text = "Current refund policy text with matching hash and valid effective date."
    stale_version_ref = _evidence_ref(tenant_id=tenant_id, policy_version="v1", text=text)
    row = _canonical_row(
        stale_version_ref,
        tenant_id=tenant_id,
        content=text,
        policy_document_version=2,
        current_policy_version="v2",
        effective_date="2026-06-01",
    )
    service = PolicyKnowledgeService(
        FakeCanonicalRetriever({(stale_version_ref.doc_key, stale_version_ref.chunk_id): row})
    )

    result = await service.get_verified_evidence_details(
        tenant_id=tenant_id,
        evidence_refs=[stale_version_ref],
        effective_at="2026-06-19T00:00:00+00:00",
        merchant_scope=["merchant-001"],
        doc_type="refund_rule",
        risk_level="high",
    )

    assert result.included == {}
    assert len(result.excluded) == 1
    reason_codes = set(result.excluded[0].reason_codes)
    assert "latest_version_invalid" in reason_codes
    assert "text_hash_mismatch" not in reason_codes
    assert "freshness_invalid" not in reason_codes


def _excluded_by_evidence_id(bundle: Any) -> dict[str, Any]:
    debug_context = bundle.debug_context
    entries = getattr(debug_context, "truncated_or_excluded_evidence", None)
    if entries is None and isinstance(debug_context, dict):
        entries = debug_context.get("truncated_or_excluded_evidence")
    return {_get(entry, "evidence_id"): entry for entry in entries or []}


@pytest.mark.asyncio
async def test_canonical_refetch_excludes_malformed_tenant_wrong_tenant_duplicate_and_text_hash_mismatch() -> None:
    """CTX-02/VER-01: Level 1 evidence gates exclude invalid refs before prompt inclusion."""
    ContextBuilder = _load_context_api()
    valid = _evidence_ref(text="Current refund policy text.", rank=1)
    malformed_tenant = _evidence_ref(
        tenant_id="not-a-uuid",
        chunk_id="chunk_malformed_tenant",
        text="Malformed tenant policy text.",
        rank=2,
    )
    wrong_tenant = _evidence_ref(
        tenant_id=OTHER_TENANT_ID,
        chunk_id="chunk_wrong_tenant",
        text="Wrong tenant policy text.",
        rank=3,
    )
    duplicate_a = _evidence_ref(chunk_id="chunk_duplicate", text="Duplicate policy text A.", rank=4)
    duplicate_b = _evidence_ref(chunk_id="chunk_duplicate", text="Duplicate policy text B.", rank=5)
    hash_mismatch = _evidence_ref(chunk_id="chunk_hash", text="Old policy text.", rank=6)
    service = FakeCanonicalPolicyService(
        {
            (valid.doc_key, valid.chunk_id): _canonical_row(valid, content="Current refund policy text."),
            (malformed_tenant.doc_key, malformed_tenant.chunk_id): _canonical_row(
                malformed_tenant,
                tenant_id=TENANT_ID,
                content="Malformed tenant policy text.",
            ),
            (wrong_tenant.doc_key, wrong_tenant.chunk_id): _canonical_row(
                wrong_tenant,
                tenant_id=TENANT_ID,
                content="Wrong tenant policy text.",
            ),
            (duplicate_a.doc_key, duplicate_a.chunk_id): _canonical_row(
                duplicate_a,
                content="Duplicate policy text A.",
            ),
            (hash_mismatch.doc_key, hash_mismatch.chunk_id): _canonical_row(
                hash_mismatch,
                content="Current replacement text.",
            ),
        }
    )

    bundle = await ContextBuilder(policy_service=service).build(
        candidate_evidence_refs=[valid, malformed_tenant, wrong_tenant, duplicate_a, duplicate_b, hash_mismatch],
        business_fact_refs=[],
        trusted_context=_trusted_context(),
        risk_hints=[],
    )

    prompt_text = _json_text(bundle.prompt_context)
    exclusions = _excluded_by_evidence_id(bundle)

    assert valid.evidence_id in bundle.citation_map["C1"].source_evidence_ids
    assert malformed_tenant.evidence_id not in prompt_text
    assert wrong_tenant.evidence_id not in prompt_text
    assert duplicate_a.evidence_id not in prompt_text
    assert duplicate_b.evidence_id not in prompt_text
    assert hash_mismatch.evidence_id not in prompt_text
    assert "tenant_id_malformed" in _reason_codes(exclusions[malformed_tenant.evidence_id])
    assert "tenant_mismatch" in _reason_codes(exclusions[wrong_tenant.evidence_id])
    assert "duplicate_evidence_key" in _reason_codes(exclusions[duplicate_a.evidence_id])
    assert "duplicate_evidence_key" in _reason_codes(exclusions[duplicate_b.evidence_id])
    assert "text_hash_mismatch" in _reason_codes(exclusions[hash_mismatch.evidence_id])


@pytest.mark.asyncio
async def test_latest_current_policy_version_mismatch_isolated_from_hash_and_effective_date_failures() -> None:
    """CTX-02/VER-01: PolicyDocument.version=2 excludes EvidenceRefV1.policy_version='v1'."""
    ContextBuilder = _load_context_api()
    text = "Current refund policy text with matching hash and valid effective date."
    stale_version_ref = _evidence_ref(policy_version="v1", text=text)
    service = FakeCanonicalPolicyService(
        {
            (stale_version_ref.doc_key, stale_version_ref.chunk_id): _canonical_row(
                stale_version_ref,
                content=text,
                policy_document_version=2,
                current_policy_version="v2",
                effective_date="2026-06-01",
            )
        }
    )

    bundle = await ContextBuilder(policy_service=service).build(
        candidate_evidence_refs=[stale_version_ref],
        business_fact_refs=[],
        trusted_context=_trusted_context(effective_at="2026-06-19T00:00:00+00:00"),
        risk_hints=[],
    )

    exclusions = _excluded_by_evidence_id(bundle)
    reason_codes = _reason_codes(exclusions[stale_version_ref.evidence_id])

    assert stale_version_ref.policy_version == "v1"
    assert service.rows[(stale_version_ref.doc_key, stale_version_ref.chunk_id)]["policy_document_version"] == 2
    assert stale_version_ref.text_hash == _evidence_ref(policy_version="v2", text=text).text_hash
    assert "latest_version_invalid" in reason_codes
    assert "text_hash_mismatch" not in reason_codes
    assert "freshness_invalid" not in reason_codes
    assert "effective_date_invalid" not in reason_codes
    assert stale_version_ref.evidence_id not in _json_text(bundle.prompt_context)


@pytest.mark.asyncio
async def test_stale_or_not_yet_effective_evidence_is_excluded_separately_from_latest_version() -> None:
    """CTX-02/VER-01: effective-date freshness gates are distinct from current-version gates."""
    ContextBuilder = _load_context_api()
    current_but_future = _evidence_ref(policy_version="v2", text="Current refund policy text.")
    service = FakeCanonicalPolicyService(
        {
            (current_but_future.doc_key, current_but_future.chunk_id): _canonical_row(
                current_but_future,
                content="Current refund policy text.",
                policy_document_version=2,
                current_policy_version="v2",
                effective_date="2026-07-01",
            )
        }
    )

    bundle = await ContextBuilder(policy_service=service).build(
        candidate_evidence_refs=[current_but_future],
        business_fact_refs=[],
        trusted_context=_trusted_context(effective_at="2026-06-19T00:00:00+00:00"),
        risk_hints=[],
    )

    reason_codes = _reason_codes(_excluded_by_evidence_id(bundle)[current_but_future.evidence_id])

    assert {"freshness_invalid", "effective_date_invalid"} & reason_codes
    assert "latest_version_invalid" not in reason_codes
    assert "text_hash_mismatch" not in reason_codes


@pytest.mark.asyncio
async def test_wrong_scope_uses_merchant_scope_doc_type_and_risk_level_surfaces() -> None:
    """CTX-02/VER-01: scope checks bind to merchant_scope, retrieval doc_type, and risk_level."""
    ContextBuilder = _load_context_api()
    wrong_merchant = _evidence_ref(chunk_id="chunk_wrong_merchant", text="Merchant scoped policy.", rank=1)
    wrong_doc_type = _evidence_ref(chunk_id="chunk_wrong_doc_type", text="Internal doc type policy.", rank=2)
    wrong_risk_level = _evidence_ref(chunk_id="chunk_wrong_risk_level", text="Low risk policy.", rank=3)
    service = FakeCanonicalPolicyService(
        {
            (wrong_merchant.doc_key, wrong_merchant.chunk_id): _canonical_row(
                wrong_merchant,
                content="Merchant scoped policy.",
                merchant_ids=["merchant-denied"],
            ),
            (wrong_doc_type.doc_key, wrong_doc_type.chunk_id): _canonical_row(
                wrong_doc_type,
                content="Internal doc type policy.",
                doc_type="internal_policy",
            ),
            (wrong_risk_level.doc_key, wrong_risk_level.chunk_id): _canonical_row(
                wrong_risk_level,
                content="Low risk policy.",
                risk_level="low",
            ),
        }
    )

    bundle = await ContextBuilder(policy_service=service).build(
        candidate_evidence_refs=[wrong_merchant, wrong_doc_type, wrong_risk_level],
        business_fact_refs=[],
        trusted_context=_trusted_context(
            merchant_scope=["merchant-001"],
            scope={
                "merchant_ids": ["merchant-001"],
                "doc_types": ["refund_rule"],
                "risk_levels": ["high"],
            },
            filters={"doc_type": "refund_rule", "risk_level": "high"},
        ),
        risk_hints=[],
    )

    exclusions = _excluded_by_evidence_id(bundle)
    merchant_reasons = _reason_codes(exclusions[wrong_merchant.evidence_id])
    doc_type_reasons = _reason_codes(exclusions[wrong_doc_type.evidence_id])
    risk_level_reasons = _reason_codes(exclusions[wrong_risk_level.evidence_id])

    assert {"scope_invalid", "merchant_scope_invalid"} <= merchant_reasons
    assert {"scope_invalid", "doc_type_invalid"} <= doc_type_reasons
    assert {"scope_invalid", "risk_level_invalid"} <= risk_level_reasons
    assert wrong_merchant.evidence_id not in _json_text(bundle.prompt_context)
    assert wrong_doc_type.evidence_id not in _json_text(bundle.verifier_context)
    assert wrong_risk_level.evidence_id not in _json_text(bundle.verifier_context)
