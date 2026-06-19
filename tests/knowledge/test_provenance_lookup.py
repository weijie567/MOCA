from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.provenance import EvidenceProvenance, EvidenceProvenanceLookupResult, SourceLocator
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.service import PolicyKnowledgeService
from src.repositories import policy_chunk_repo as policy_chunk_repo_module
from src.repositories.policy_chunk_repo import PolicyChunkRepository


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


def _provenance(ref: EvidenceRefV1) -> EvidenceProvenance:
    return EvidenceProvenance(
        evidence_id=ref.evidence_id,
        doc_key=ref.doc_key,
        chunk_id=ref.chunk_id,
        source_locators=[
            SourceLocator(
                source_block_id="block-001",
                block_index=1,
                block_type="table",
                page_number=2,
                bbox={"x0": 10, "y0": 20, "x1": 180, "y1": 240, "unit": "pdf_point"},
                table={"row_index": 3, "col_index": 1, "headers": ["场景", "审核要求"]},
                parser={
                    "source_type": "policy_pdf",
                    "parser_name": "pdfplumber",
                    "parser_version": "0.11.10",
                    "warning_codes": ["ocr_confidence_review_needed"],
                },
                ocr={"average_confidence": 86, "confidence_status": "accepted", "language": "chi_sim+eng"},
            )
        ],
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


@pytest.mark.asyncio
async def test_valid_refs_return_page_bbox_table_and_ocr_locators_after_hash_validation() -> None:
    tenant_id = str(uuid4())
    evidence = _evidence(tenant_id=tenant_id, text="真实政策正文")
    provenance = _provenance(evidence)
    retriever = SimpleNamespace(
        get_contents_by_evidence_keys=AsyncMock(return_value={(evidence.doc_key, evidence.chunk_id): "真实政策正文"}),
        get_provenance_by_evidence_keys=AsyncMock(return_value={(evidence.doc_key, evidence.chunk_id): provenance}),
    )
    service = PolicyKnowledgeService(retriever)

    result = await service.get_verified_evidence_provenance(
        tenant_id=tenant_id,
        evidence_refs=[evidence],
    )

    assert result == {evidence.evidence_id: provenance}
    locator = result[evidence.evidence_id].source_locators[0]
    assert locator.page_number == 2
    assert locator.bbox["unit"] == "pdf_point"
    assert locator.table["headers"] == ["场景", "审核要求"]
    assert locator.parser == {
        "source_type": "policy_pdf",
        "parser_name": "pdfplumber",
        "parser_version": "0.11.10",
        "warning_codes": ["ocr_confidence_review_needed"],
    }
    assert locator.ocr["average_confidence"] == 86
    assert EvidenceProvenanceLookupResult(items=result).items[evidence.evidence_id] == provenance


@pytest.mark.asyncio
async def test_provenance_lookup_does_not_expand_source_blocks_until_hash_and_tenant_match() -> None:
    tenant_id = str(uuid4())
    wrong_hash = _evidence(tenant_id=tenant_id, text="旧正文")
    wrong_tenant = _evidence(tenant_id=str(uuid4()), chunk_id="chunk-2", text="跨租户正文")
    get_provenance = AsyncMock()
    retriever = SimpleNamespace(
        get_contents_by_evidence_keys=AsyncMock(
            return_value={
                (wrong_hash.doc_key, wrong_hash.chunk_id): "新正文",
                (wrong_tenant.doc_key, wrong_tenant.chunk_id): "跨租户正文",
            }
        ),
        get_provenance_by_evidence_keys=get_provenance,
    )
    service = PolicyKnowledgeService(retriever)

    result = await service.get_verified_evidence_provenance(
        tenant_id=tenant_id,
        evidence_refs=[wrong_hash, wrong_tenant],
    )

    assert result == {}
    get_provenance.assert_not_awaited()


@pytest.mark.asyncio
async def test_provenance_lookup_duplicate_key_malformed_tenant_missing_blocks_and_errors_return_empty() -> None:
    tenant_id = str(uuid4())
    first = _evidence(tenant_id=tenant_id, chunk_id="same", text="正文一")
    second = _evidence(tenant_id=tenant_id, chunk_id="same", text="正文二")
    duplicate_retriever = SimpleNamespace(
        get_contents_by_evidence_keys=AsyncMock(),
        get_provenance_by_evidence_keys=AsyncMock(),
    )
    duplicate_service = PolicyKnowledgeService(duplicate_retriever)

    assert (
        await duplicate_service.get_verified_evidence_provenance(
            tenant_id=tenant_id,
            evidence_refs=[first, second],
        )
        == {}
    )
    duplicate_retriever.get_contents_by_evidence_keys.assert_not_awaited()
    duplicate_retriever.get_provenance_by_evidence_keys.assert_not_awaited()

    malformed_service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=AsyncMock()))
    assert (
        await malformed_service.get_verified_evidence_provenance(
            tenant_id="not-a-uuid",
            evidence_refs=[first],
        )
        == {}
    )

    missing_blocks_retriever = SimpleNamespace(
        get_contents_by_evidence_keys=AsyncMock(return_value={(first.doc_key, first.chunk_id): "正文一"}),
        get_provenance_by_evidence_keys=AsyncMock(return_value={}),
    )
    missing_blocks_service = PolicyKnowledgeService(missing_blocks_retriever)
    assert (
        await missing_blocks_service.get_verified_evidence_provenance(
            tenant_id=tenant_id,
            evidence_refs=[first],
        )
        == {}
    )

    error_retriever = SimpleNamespace(
        get_contents_by_evidence_keys=AsyncMock(return_value={(first.doc_key, first.chunk_id): "正文一"}),
        get_provenance_by_evidence_keys=AsyncMock(side_effect=RuntimeError("raw repository error")),
    )
    error_service = PolicyKnowledgeService(error_retriever)
    assert (
        await error_service.get_verified_evidence_provenance(
            tenant_id=tenant_id,
            evidence_refs=[first],
        )
        == {}
    )


@pytest.mark.asyncio
async def test_chunk_repository_expands_ordered_source_refs_through_document_blocks(monkeypatch) -> None:
    tenant_id = uuid4()
    block = SimpleNamespace(
        source_block_id="block-001",
        block_index=7,
        block_type="table",
        page_number=4,
        bbox_json={"x0": 1, "y0": 2, "x1": 30, "y1": 40, "unit": "pdf_point"},
        table_metadata_json={"row_index": 2, "col_index": 1, "headers": ["场景", "审核"]},
        parser_metadata_json={
            "source_type": "policy_pdf",
            "parser_name": "pdfplumber",
            "parser_version": "0.11.10",
            "warning_codes": ["hidden_text_stripped"],
            "parser_dump": "must not project",
        },
        ocr_metadata_json={"average_confidence": 88, "language": "chi_sim+eng", "local_path": "/Users/ming/raw.png"},
    )

    class _Result:
        def all(self):
            return [
                (
                    "refund-policy",
                    3,
                    "chunk-1",
                    uuid4(),
                    [{"source_block_id": "block-001", "ignored": "safe but irrelevant"}],
                )
            ]

    class _Session:
        async def execute(self, stmt):
            return _Result()

    class _BlockRepo:
        def __init__(self, session) -> None:
            self.session = session

        async def get_by_source_block_ids(self, *, tenant_id, document_id, source_block_ids):
            return [block]

    monkeypatch.setattr(policy_chunk_repo_module, "DocumentBlockRepository", _BlockRepo)

    result = await PolicyChunkRepository(_Session()).get_provenance_by_evidence_keys(
        tenant_id,
        [("refund-policy", "chunk-1")],
    )

    provenance = result[("refund-policy", "chunk-1")]
    assert provenance.evidence_id == "refund-policy/chunk-1@v3"
    locator = provenance.source_locators[0]
    assert locator.source_block_id == "block-001"
    assert locator.page_number == 4
    assert locator.table["headers"] == ["场景", "审核"]
    assert locator.parser == {
        "source_type": "policy_pdf",
        "parser_name": "pdfplumber",
        "parser_version": "0.11.10",
        "warning_codes": ["hidden_text_stripped"],
    }
    assert locator.ocr == {"average_confidence": 88, "language": "chi_sim+eng"}
    assert "parser_dump" not in repr(locator)
    assert "/Users/ming" not in repr(locator)


@pytest.mark.asyncio
async def test_chunk_repository_returns_empty_for_missing_or_ambiguous_block_rows(monkeypatch) -> None:
    tenant_id = uuid4()
    block = SimpleNamespace(
        source_block_id="block-001",
        block_index=0,
        block_type="paragraph",
        page_number=None,
        bbox_json={},
        table_metadata_json={},
        parser_metadata_json={},
        ocr_metadata_json={},
    )

    class _Result:
        def all(self):
            return [("refund-policy", 1, "chunk-1", uuid4(), [{"source_block_id": "block-001"}])]

    class _Session:
        async def execute(self, stmt):
            return _Result()

    class _MissingBlockRepo:
        def __init__(self, session) -> None:
            self.session = session

        async def get_by_source_block_ids(self, *, tenant_id, document_id, source_block_ids):
            return []

    monkeypatch.setattr(policy_chunk_repo_module, "DocumentBlockRepository", _MissingBlockRepo)
    assert (
        await PolicyChunkRepository(_Session()).get_provenance_by_evidence_keys(
            tenant_id,
            [("refund-policy", "chunk-1")],
        )
        == {}
    )

    class _AmbiguousBlockRepo:
        def __init__(self, session) -> None:
            self.session = session

        async def get_by_source_block_ids(self, *, tenant_id, document_id, source_block_ids):
            return [block, block]

    monkeypatch.setattr(policy_chunk_repo_module, "DocumentBlockRepository", _AmbiguousBlockRepo)
    assert (
        await PolicyChunkRepository(_Session()).get_provenance_by_evidence_keys(
            tenant_id,
            [("refund-policy", "chunk-1")],
        )
        == {}
    )


def test_provenance_lookup_does_not_change_evidence_ref_v1_identity_shape() -> None:
    evidence = _evidence(tenant_id=str(uuid4()))
    fields = set(evidence.model_dump())

    assert "page_number" not in fields
    assert "bbox" not in fields
    assert "source_block_id" not in fields
    assert "source_block_refs_json" not in fields
    assert "parser_metadata_json" not in fields
    assert "ocr_metadata_json" not in fields
