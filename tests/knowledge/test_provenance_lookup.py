from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.service import PolicyKnowledgeService
from tests.rag.phase21_xfail_inventory import xfail_for


def _evidence(*, tenant_id: str, chunk_id: str = "chunk-1", text: str = "退款规则正文") -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="refund-policy",
        chunk_id=chunk_id,
        policy_version="v1",
        text=text,
        retrieved_at="2026-06-18T00:00:00Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.8,
        rank=1,
    )


@pytest.mark.asyncio
async def test_verified_evidence_content_malformed_tenant_returns_empty() -> None:
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=AsyncMock()))

    result = await service.get_verified_evidence_contents(
        tenant_id="not-a-uuid",
        evidence_refs=[_evidence(tenant_id=str(uuid4()))],
    )

    assert result == {}


@pytest.mark.asyncio
async def test_verified_evidence_content_duplicate_doc_key_chunk_id_returns_empty() -> None:
    tenant_id = str(uuid4())
    first = _evidence(tenant_id=tenant_id, chunk_id="same", text="正文一")
    second = _evidence(tenant_id=tenant_id, chunk_id="same", text="正文二")
    get_contents = AsyncMock(return_value={(first.doc_key, first.chunk_id): "正文一"})
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=get_contents))

    result = await service.get_verified_evidence_contents(tenant_id=tenant_id, evidence_refs=[first, second])

    assert result == {}
    get_contents.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_evidence_content_wrong_tenant_or_hash_returns_empty() -> None:
    tenant_id = str(uuid4())
    wrong_tenant = _evidence(tenant_id=str(uuid4()), chunk_id="chunk-wrong-tenant", text="正文一")
    wrong_hash = _evidence(tenant_id=tenant_id, chunk_id="chunk-wrong-hash", text="旧正文")
    get_contents = AsyncMock(
        return_value={
            (wrong_tenant.doc_key, wrong_tenant.chunk_id): "正文一",
            (wrong_hash.doc_key, wrong_hash.chunk_id): "新正文",
        }
    )
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=get_contents))

    result = await service.get_verified_evidence_contents(
        tenant_id=tenant_id,
        evidence_refs=[wrong_tenant, wrong_hash],
    )

    assert result == {}


@pytest.mark.asyncio
async def test_verified_evidence_content_repository_errors_return_empty() -> None:
    tenant_id = str(uuid4())
    evidence = _evidence(tenant_id=tenant_id)
    service = PolicyKnowledgeService(
        SimpleNamespace(get_contents_by_evidence_keys=AsyncMock(side_effect=RuntimeError("db unavailable")))
    )

    result = await service.get_verified_evidence_contents(tenant_id=tenant_id, evidence_refs=[evidence])

    assert result == {}


@xfail_for("21-04-01/provenance-lookup")
@pytest.mark.asyncio
async def test_valid_refs_return_page_bbox_table_and_ocr_locators_after_hash_validation() -> None:
    tenant_id = str(uuid4())
    evidence = _evidence(tenant_id=tenant_id, text="真实政策正文")
    retriever = SimpleNamespace(
        get_contents_by_evidence_keys=AsyncMock(return_value={(evidence.doc_key, evidence.chunk_id): "真实政策正文"}),
        get_source_locations_by_evidence_keys=AsyncMock(
            return_value={
                (evidence.doc_key, evidence.chunk_id): {
                    "page_number": 2,
                    "bbox": {"x0": 10, "y0": 20, "x1": 180, "y1": 240, "unit": "pdf_point"},
                    "table": {"row_index": 3, "col_index": 1, "headers": ["场景", "审核要求"]},
                    "ocr": {"average_confidence": 86, "language": "chi_sim+eng"},
                }
            }
        ),
    )
    service = PolicyKnowledgeService(retriever)

    result = await service.get_verified_evidence_provenance(
        tenant_id=tenant_id,
        evidence_refs=[evidence],
    )

    assert result[evidence.evidence_id]["page_number"] == 2
    assert result[evidence.evidence_id]["bbox"]["unit"] == "pdf_point"
    assert result[evidence.evidence_id]["table"]["headers"] == ["场景", "审核要求"]
    assert result[evidence.evidence_id]["ocr"]["average_confidence"] == 86


def test_provenance_lookup_does_not_change_evidence_ref_v1_identity_shape() -> None:
    evidence = _evidence(tenant_id=str(uuid4()))
    fields = set(evidence.model_dump())

    assert "page_number" not in fields
    assert "bbox" not in fields
    assert "source_block_id" not in fields
    assert "source_block_refs_json" not in fields
    assert "parser_metadata_json" not in fields
    assert "ocr_metadata_json" not in fields
