from __future__ import annotations

import inspect
from uuid import uuid4

import pytest

from src.db.models import Base, DocumentBlock, RagIngestionJob
from src.repositories.document_block_repo import (
    MAX_DOCUMENT_BLOCK_TEXT_LENGTH,
    DocumentBlockRepository,
    validate_document_block,
)
from src.repositories.rag_ingestion_job_repo import (
    RagIngestionJobRepository,
    validate_rag_ingestion_job,
)


def test_document_block_schema_is_tenant_and_document_scoped() -> None:
    table = Base.metadata.tables["document_blocks"]

    assert {
        "id",
        "tenant_id",
        "doc_id",
        "source_block_id",
        "block_index",
        "block_type",
        "text",
        "normalized_text",
        "text_hash",
        "page_number",
        "bbox_json",
        "table_metadata_json",
        "parser_metadata_json",
        "ocr_metadata_json",
        "source_uri",
    }.issubset(set(table.c.keys()))
    assert table.c.tenant_id.nullable is False
    assert table.c.doc_id.nullable is False
    assert table.c.text.nullable is False
    assert table.c.normalized_text.nullable is False


def test_rag_ingestion_job_schema_records_safe_trace_fields() -> None:
    table = Base.metadata.tables["rag_ingestion_jobs"]

    assert {
        "id",
        "tenant_id",
        "doc_id",
        "doc_key",
        "source_type",
        "source_checksum",
        "parser_name",
        "parser_version",
        "ocr_engine",
        "stage",
        "status",
        "error_code",
        "safe_message",
        "warnings_json",
        "counts_json",
        "timings_json",
        "started_at",
        "completed_at",
    }.issubset(set(table.c.keys()))
    assert table.c.tenant_id.nullable is False
    assert table.c.doc_id.nullable is False


def test_policy_chunk_and_document_schema_names_include_provenance_fields() -> None:
    policy_chunks = Base.metadata.tables["policy_chunks"]
    policy_documents = Base.metadata.tables["policy_documents"]

    assert "source_block_refs_json" in policy_chunks.c
    assert "ocr_metadata_json" in policy_chunks.c
    assert policy_chunks.c.source_block_refs_json.nullable is False
    assert policy_chunks.c.ocr_metadata_json.nullable is False
    assert "source_type" in policy_documents.c
    assert "source_checksum" in policy_documents.c
    assert "parser_metadata_json" in policy_documents.c
    assert "policy_version_fingerprint" in policy_documents.c


def test_policy_version_fingerprint_is_not_parser_metadata() -> None:
    policy_documents = Base.metadata.tables["policy_documents"]

    assert "policy_version_fingerprint" in policy_documents.c
    assert policy_documents.c.policy_version_fingerprint.name != policy_documents.c.parser_metadata_json.name


def test_document_block_repository_queries_are_tenant_scoped() -> None:
    source = inspect.getsource(DocumentBlockRepository)

    assert "DocumentBlock.tenant_id == tenant_id" in source
    assert "DocumentBlock.doc_id == document_id" in source
    assert ".commit(" not in source


def test_rag_ingestion_job_repository_queries_are_tenant_scoped() -> None:
    source = inspect.getsource(RagIngestionJobRepository)

    assert "RagIngestionJob.tenant_id == tenant_id" in source
    assert "RagIngestionJob.doc_id == document_id" in source
    assert ".commit(" not in source


def _document_block(**overrides) -> DocumentBlock:
    data = {
        "tenant_id": uuid4(),
        "doc_id": uuid4(),
        "source_block_id": "refund_policy:markdown:synthetic:0000",
        "block_index": 0,
        "block_type": "paragraph",
        "text": "visible policy text",
        "normalized_text": "visible policy text",
        "text_hash": "sha256:" + "1" * 64,
        "parser_metadata_json": {"warning_codes": ["hidden_text_stripped"]},
        "ocr_metadata_json": {"confidence_avg": 0.98},
    }
    data.update(overrides)
    return DocumentBlock(**data)


def test_document_block_validation_rejects_overlong_visible_text() -> None:
    block = _document_block(text="x" * (MAX_DOCUMENT_BLOCK_TEXT_LENGTH + 1))

    with pytest.raises(ValueError, match="document_block_text_too_long"):
        validate_document_block(block)


def test_document_block_validation_rejects_control_characters_and_raw_parser_metadata() -> None:
    with pytest.raises(ValueError, match="document_block_text_control_chars"):
        validate_document_block(_document_block(text="visible\x00policy"))

    with pytest.raises(ValueError, match="safe warning codes"):
        validate_document_block(_document_block(parser_metadata_json={"raw_parser_dump": "full dump"}))


def test_rag_ingestion_job_validation_rejects_raw_paths_stacks_and_dumps() -> None:
    job = RagIngestionJob(
        tenant_id=uuid4(),
        doc_id=uuid4(),
        doc_key="refund_policy",
        source_type="markdown",
        source_checksum="sha256:" + "a" * 64,
        parser_name="markdown",
        parser_version="phase21.parser.v1",
        stage="parsing",
        status="failed",
        error_code="parse_failed",
        safe_message="/Users/alice/private/source.pdf failed",
        warnings_json=[],
        counts_json={},
        timings_json={},
    )

    with pytest.raises(ValueError, match="safe_message_not_sanitized"):
        validate_rag_ingestion_job(job)
