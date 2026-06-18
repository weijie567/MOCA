from __future__ import annotations

from pathlib import Path

from src.db.models import Base


MIGRATION_PATH = Path("src/db/migrations/versions/014_rag_hybrid_retrieval.py")


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "Phase 20 RAG hybrid migration must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_policy_chunk_has_search_text_and_search_vector_columns() -> None:
    table = Base.metadata.tables["policy_chunks"]

    assert "search_text" in table.c
    assert "search_vector" in table.c


def test_phase20_migration_declares_full_text_and_trgm_indexes() -> None:
    source = _migration_source()

    assert 'revision: str = "014_rag_hybrid_retrieval"' in source
    assert 'down_revision: str | None = "013_long_term_case_memory"' in source
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in source
    assert "ix_policy_chunks_search_vector_gin" in source
    assert "ix_policy_chunks_search_text_trgm" in source
    assert "gin_trgm_ops" in source
    assert "ix_policy_chunks_retrieval_scope" in source


def test_phase20_migration_does_not_create_deferred_ingestion_or_verifier_tables() -> None:
    source = _migration_source().lower()

    for forbidden in ("documentblock", "ocr", "material_claim", "vespa", "opensearch"):
        assert forbidden not in source


def test_phase20_migration_downgrade_drops_search_columns_after_indexes() -> None:
    source = _migration_source()

    vector_index_pos = source.index("DROP INDEX IF EXISTS ix_policy_chunks_search_vector_gin")
    trgm_index_pos = source.index("DROP INDEX IF EXISTS ix_policy_chunks_search_text_trgm")
    search_vector_pos = source.index('op.drop_column("policy_chunks", "search_vector")')
    search_text_pos = source.index('op.drop_column("policy_chunks", "search_text")')

    assert vector_index_pos < search_vector_pos
    assert trgm_index_pos < search_text_pos
    assert search_vector_pos < search_text_pos
