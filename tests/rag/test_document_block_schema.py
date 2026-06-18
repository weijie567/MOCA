from __future__ import annotations

from src.db.models import Base
from tests.rag.phase21_xfail_inventory import xfail_for


@xfail_for("21-01a-01/source-block-schema")
def test_document_block_schema_is_tenant_and_document_scoped() -> None:
    table = Base.metadata.tables["document_blocks"]

    assert {
        "id",
        "tenant_id",
        "doc_id",
        "source_block_id",
        "block_index",
        "block_type",
        "text_hash",
        "page_number",
        "bbox_json",
        "table_metadata_json",
        "parser_metadata_json",
        "ocr_metadata_json",
    }.issubset(set(table.c.keys()))


@xfail_for("21-01a-01/ingestion-job-schema")
def test_rag_ingestion_job_schema_records_safe_trace_fields() -> None:
    table = Base.metadata.tables["rag_ingestion_jobs"]

    assert {
        "id",
        "tenant_id",
        "doc_id",
        "source_checksum",
        "parser_versions_json",
        "stage",
        "status",
        "warnings_json",
        "counts_json",
        "timings_json",
        "failure_code",
        "failure_reason",
    }.issubset(set(table.c.keys()))


@xfail_for("21-01a-01/chunk-source-block-refs")
def test_policy_chunk_and_document_schema_names_include_provenance_fields() -> None:
    policy_chunks = Base.metadata.tables["policy_chunks"]
    policy_documents = Base.metadata.tables["policy_documents"]

    assert "source_block_refs_json" in policy_chunks.c
    assert "parser_metadata_json" in policy_documents.c
    assert "policy_version_fingerprint" in policy_documents.c

