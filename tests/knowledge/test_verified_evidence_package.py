from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.knowledge.schemas import (
    EvidenceItemV1,
    EvidenceRefV1,
    KnowledgeContext,
    VerifiedEvidencePackageV1,
)
from src.knowledge.service import PolicyKnowledgeService


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


def _evidence_item() -> EvidenceItemV1:
    ref = _evidence_ref()
    return EvidenceItemV1(
        ref=ref,
        snippet="Refund timeout compensation requires verified policy evidence.",
        text_hash=ref.text_hash,
        doc_version="v3",
        policy_version=ref.policy_version,
        effective_date_result="valid",
        tenant_scope_result="valid",
        authority_level="tenant_policy",
        source_locator={"page": 1, "block_id": "b1"},
        captured_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _knowledge_context() -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=TENANT_ID,
        user_id="user-001",
        role="support",
        merchant_scope=["merchant-001"],
        run_id="run-phase33-package",
        trace_id="trace-phase33-package",
        locale="zh-CN",
        effective_at="2026-06-19T00:00:00+00:00",
    )


def _canonical_row(ref: EvidenceRefV1, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tenant_id": ref.tenant_id,
        "doc_key": ref.doc_key,
        "chunk_id": ref.chunk_id,
        "content": "Refund timeout compensation requires verified policy evidence.",
        "policy_document_version": 3,
        "current_policy_version": "v3",
        "effective_date": "2026-06-01",
        "expires_at": None,
        "doc_type": "refund_rule",
        "risk_level": "medium",
        "merchant_ids": ["merchant-001"],
        "source_locator": {"page": 1, "block_id": "b1"},
    }
    row.update(overrides)
    return row


class FakeCanonicalRetriever:
    def __init__(self, rows: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.rows = rows

    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        return {key: row for key, row in self.rows.items() if key in keys and row["tenant_id"] == str(tenant_id)}


def test_verified_evidence_package_accepts_exact_rag_context_status_literals() -> None:
    """APF-13: target package status is pinned to the contract spellings."""
    ref = _evidence_ref()
    item = _evidence_item()
    statuses = {
        "not_required",
        "verified",
        "partial",
        "no_evidence",
        "unauthorized",
        "stale",
        "conflict",
        "invalid_hash",
        "invalid_scope",
        "build_error",
    }

    for status in statuses:
        package = VerifiedEvidencePackageV1(
            package_id=f"pkg-{status}",
            status=status,
            evidence_items=[item] if status in {"verified", "partial"} else [],
            citation_map={"C1": [ref.evidence_id]} if status in {"verified", "partial"} else {},
            evidence_map={ref.evidence_id: ref} if status in {"verified", "partial"} else {},
            prompt_projection={"citations": ["C1"]},
            verifier_projection={"safe_refs": [ref.evidence_id]},
            replay_snapshot_refs=[ref.evidence_id],
            debug_projection={"reason_codes": []},
            stale_refs=[ref] if status == "stale" else [],
            conflict_refs=[ref] if status == "conflict" else [],
            rejected_candidate_refs=[ref] if status not in {"verified", "partial"} else [],
            reason_codes=[status],
            policy_version="policy.v3",
            retrieval_config_version="retrieval.v3",
        )

        assert package.schema_version == "verified_evidence_package.v1"
        assert package.status == status


def test_verified_evidence_package_rejects_unknown_status_and_extra_fields() -> None:
    """APF-13: strict DTOs fail closed for unknown status or unowned payload."""
    ref = _evidence_ref()
    item = _evidence_item()

    with pytest.raises(ValidationError):
        VerifiedEvidencePackageV1(
            package_id="pkg-unsafe",
            status="hash_warning",
            evidence_items=[item],
            citation_map={"C1": [ref.evidence_id]},
            evidence_map={ref.evidence_id: ref},
            prompt_projection={},
            verifier_projection={},
            replay_snapshot_refs=[],
            debug_projection={},
            stale_refs=[],
            conflict_refs=[],
            rejected_candidate_refs=[],
            reason_codes=["hash_warning"],
            policy_version="policy.v3",
            retrieval_config_version="retrieval.v3",
        )

    payload = {
        "package_id": "pkg-extra",
        "status": "verified",
        "evidence_items": [item.model_dump(mode="python")],
        "citation_map": {"C1": [ref.evidence_id]},
        "evidence_map": {ref.evidence_id: ref.model_dump(mode="python")},
        "prompt_projection": {},
        "verifier_projection": {},
        "replay_snapshot_refs": [],
        "debug_projection": {},
        "stale_refs": [],
        "conflict_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "policy_version": "policy.v3",
        "retrieval_config_version": "retrieval.v3",
        "raw_ocr_debug": "SHOULD_NOT_ENTER_PROMPT",
    }
    with pytest.raises(ValidationError):
        VerifiedEvidencePackageV1.model_validate(payload)


@pytest.mark.asyncio
async def test_build_verified_context_constructs_verified_package_from_context_builder() -> None:
    """APF-13: KnowledgeService builds the target package from validated candidate refs."""
    ref = _evidence_ref()
    service = PolicyKnowledgeService(FakeCanonicalRetriever({(ref.doc_key, ref.chunk_id): _canonical_row(ref)}))

    package = await service.build_verified_context(
        candidate_evidence_refs=[ref],
        business_fact_refs=[],
        knowledge_context=_knowledge_context(),
        evidence_policy={"doc_type": "refund_rule", "risk_level": "medium", "evidence_required": True},
    )

    assert package.schema_version == "verified_evidence_package.v1"
    assert package.status == "verified"
    assert package.evidence_items[0].ref == ref
    assert package.citation_map == {"C1": [ref.evidence_id]}
    assert package.evidence_map == {ref.evidence_id: ref}
    assert package.prompt_projection != package.debug_projection
    assert package.verifier_projection["safe_refs"] == [ref.evidence_id]
    assert package.policy_version == "v3"
    assert package.retrieval_config_version == "retrieval.v3"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("row_overrides", "expected_status", "expected_reason"),
    [
        ({"content": "Mutated canonical text."}, "invalid_hash", "text_hash_mismatch"),
        ({"current_policy_version": "v4"}, "stale", "latest_version_invalid"),
        ({"merchant_ids": ["merchant-denied"]}, "invalid_scope", "merchant_scope_invalid"),
    ],
)
async def test_build_verified_context_maps_hard_gate_failures_to_status(
    row_overrides: dict[str, Any],
    expected_status: str,
    expected_reason: str,
) -> None:
    ref = _evidence_ref()
    row = _canonical_row(ref, **row_overrides)
    service = PolicyKnowledgeService(FakeCanonicalRetriever({(ref.doc_key, ref.chunk_id): row}))

    package = await service.build_verified_context(
        candidate_evidence_refs=[ref],
        business_fact_refs=[],
        knowledge_context=_knowledge_context(),
        evidence_policy={"doc_type": "refund_rule", "risk_level": "medium", "evidence_required": True},
    )

    assert package.status == expected_status
    assert expected_reason in package.reason_codes
    assert ref in package.rejected_candidate_refs or ref in package.stale_refs
