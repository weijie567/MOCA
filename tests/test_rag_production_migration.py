from __future__ import annotations

from pathlib import Path


MIGRATION_PATH = Path("src/db/migrations/versions/015_rag_production_ingestion_ocr.py")


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "Phase 21 production ingestion migration must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_phase21_migration_declares_expected_revision_chain() -> None:
    source = _migration_source()

    assert 'revision: str = "015_rag_production_ingestion_ocr"' in source
    assert 'down_revision: str | None = "014_rag_hybrid_retrieval"' in source
    assert "document_blocks" in source
    assert "rag_ingestion_jobs" in source
    assert "source_block_refs_json" in source


def test_phase21_migration_creates_tenant_doc_scoped_tables_and_indexes() -> None:
    source = _migration_source()

    assert 'op.create_table(\n        "document_blocks"' in source
    assert 'op.create_table(\n        "rag_ingestion_jobs"' in source
    assert '"tenant_id", postgresql.UUID(as_uuid=True), nullable=False' in source
    assert '"doc_id", postgresql.UUID(as_uuid=True), nullable=False' in source
    assert '"doc_id", postgresql.UUID(as_uuid=True), nullable=True' in source
    assert "uq_document_blocks_tenant_doc_source_block" in source
    assert "ix_document_blocks_tenant_doc_index" in source
    assert "ix_document_blocks_tenant_doc_source_block" in source
    assert "ix_rag_ingestion_jobs_tenant_doc" in source
    assert "ix_rag_ingestion_jobs_tenant_doc_key" in source


def test_phase21_migration_adds_jsonb_provenance_without_persistent_fake_defaults() -> None:
    source = _migration_source()

    assert 'sa.Column("source_block_refs_json", postgresql.JSONB(), nullable=True)' in source
    assert 'sa.Column("ocr_metadata_json", postgresql.JSONB(), nullable=True)' in source
    assert "SET source_block_refs_json = '[]'::jsonb" in source
    assert "SET ocr_metadata_json = '{}'::jsonb" in source
    assert 'op.alter_column("policy_chunks", "source_block_refs_json", nullable=False)' in source
    assert 'op.alter_column("policy_chunks", "ocr_metadata_json", nullable=False)' in source
    for line in source.splitlines():
        if "source_block_refs_json" in line or "ocr_metadata_json" in line:
            assert "server_default" not in line


def test_phase21_migration_keeps_policy_fingerprint_as_dedicated_document_field() -> None:
    source = _migration_source()

    fingerprint_pos = source.index('sa.Column("policy_version_fingerprint"')
    parser_metadata_pos = source.index('sa.Column("parser_metadata_json"')

    assert fingerprint_pos != parser_metadata_pos
    assert "policy_version_fingerprint" in source
    assert "parser_metadata_json" in source


def test_phase21_migration_downgrade_drops_provenance_in_dependency_order() -> None:
    source = _migration_source()

    job_index_pos = source.index('op.drop_index("ix_rag_ingestion_jobs_tenant_status"')
    block_index_pos = source.index('op.drop_index("ix_document_blocks_tenant_doc_source_block"')
    chunk_ocr_pos = source.index('op.drop_column("policy_chunks", "ocr_metadata_json")')
    chunk_refs_pos = source.index('op.drop_column("policy_chunks", "source_block_refs_json")')
    ingestion_jobs_pos = source.index('op.drop_table("rag_ingestion_jobs")')
    document_blocks_pos = source.index('op.drop_table("document_blocks")')
    document_fingerprint_pos = source.index('op.drop_column("policy_documents", "policy_version_fingerprint")')

    assert job_index_pos < ingestion_jobs_pos
    assert block_index_pos < document_blocks_pos
    assert chunk_ocr_pos < chunk_refs_pos < ingestion_jobs_pos < document_blocks_pos < document_fingerprint_pos


def test_phase21_migration_omits_deferred_phase22_23_and_rag5_surfaces() -> None:
    source = _migration_source()

    for forbidden in (
        "MaterialClaim",
        "semantic_verifier",
        "SemanticVerifier",
        "QueryRewriteService",
        "query_rewriter",
        "rewrite_query(",
        "CrossEncoderReranker",
        "ExternalRerankClient",
        "Vespa",
        "OpenSearch",
        "SearchBackend",
    ):
        assert forbidden not in source
