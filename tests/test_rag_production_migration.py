from __future__ import annotations

from pathlib import Path

from tests.rag.phase21_xfail_inventory import xfail_for


MIGRATION_PATH = Path("src/db/migrations/versions/015_rag_production_ingestion_ocr.py")


@xfail_for("21-01a-01/migration-rollback")
def test_phase21_migration_declares_expected_revision_chain() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "015_rag_production_ingestion_ocr"' in source
    assert 'down_revision: str | None = "014_rag_hybrid_retrieval"' in source
    assert "document_blocks" in source
    assert "rag_ingestion_jobs" in source
    assert "source_block_refs_json" in source


@xfail_for("21-01a-01/migration-rollback")
def test_phase21_migration_downgrade_drops_provenance_in_dependency_order() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    chunk_refs_pos = source.index('op.drop_column("policy_chunks", "source_block_refs_json")')
    document_blocks_pos = source.index('op.drop_table("document_blocks")')
    ingestion_jobs_pos = source.index('op.drop_table("rag_ingestion_jobs")')

    assert chunk_refs_pos < document_blocks_pos < ingestion_jobs_pos

