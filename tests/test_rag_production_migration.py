from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


MIGRATION_PATH = Path("src/db/migrations/versions/015_rag_production_ingestion_ocr.py")
PHASE20_MIGRATION_PATH = Path("src/db/migrations/versions/014_rag_hybrid_retrieval.py")

PHASE21_TABLES = {"document_blocks", "rag_ingestion_jobs"}
PHASE21_DOCUMENT_COLUMNS = {
    "source_type",
    "source_checksum",
    "parser_metadata_json",
    "policy_version_fingerprint",
}
PHASE21_CHUNK_COLUMNS = {"source_block_refs_json", "ocr_metadata_json"}
PHASE20_HYBRID_COLUMNS = {"search_text", "search_vector"}
PHASE20_HYBRID_INDEXES = {
    "ix_policy_chunks_search_vector_gin",
    "ix_policy_chunks_search_text_trgm",
    "ix_policy_chunks_retrieval_scope",
}


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "Phase 21 production ingestion migration must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _phase20_migration_source() -> str:
    assert PHASE20_MIGRATION_PATH.exists(), "Phase 20 hybrid migration must exist"
    return PHASE20_MIGRATION_PATH.read_text(encoding="utf-8")


def _alembic_config(database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)

    import src.config as config_module

    config_module.settings.database_url = database_url
    config_module.get_settings.cache_clear()
    return cfg


async def _reset_database(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            return {row[0] for row in result}
    finally:
        await engine.dispose()


async def _column_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            )
            return {row[0] for row in result}
    finally:
        await engine.dispose()


async def _index_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = :table_name
                    """
                ),
                {"table_name": table_name},
            )
            return {row[0] for row in result}
    finally:
        await engine.dispose()


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


def test_phase21_migration_adds_document_and_chunk_provenance_columns() -> None:
    source = _migration_source()

    for column_name in PHASE21_DOCUMENT_COLUMNS:
        assert f'sa.Column("{column_name}"' in source
        assert f'op.drop_column("policy_documents", "{column_name}")' in source
    for column_name in PHASE21_CHUNK_COLUMNS:
        assert f'sa.Column("{column_name}", postgresql.JSONB(), nullable=True)' in source
        assert f'op.drop_column("policy_chunks", "{column_name}")' in source


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
    assert chunk_ocr_pos < ingestion_jobs_pos
    assert chunk_refs_pos < ingestion_jobs_pos
    assert chunk_ocr_pos < document_blocks_pos
    assert chunk_refs_pos < document_blocks_pos
    assert ingestion_jobs_pos < document_fingerprint_pos
    assert document_blocks_pos < document_fingerprint_pos


def test_phase21_downgrade_does_not_drop_phase20_hybrid_retrieval_structures() -> None:
    source = _migration_source()
    phase20_source = _phase20_migration_source()

    downgrade_source = source.split("def downgrade() -> None:", 1)[1]
    for column_name in PHASE20_HYBRID_COLUMNS:
        assert f'op.drop_column("policy_chunks", "{column_name}")' not in downgrade_source
        assert f'"{column_name}"' in phase20_source
    for index_name in PHASE20_HYBRID_INDEXES:
        assert index_name not in downgrade_source
        assert index_name in phase20_source


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


def test_phase21_migration_live_downgrade_round_trip_when_configured() -> None:
    database_url = os.environ.get("MOCA_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MOCA_TEST_DATABASE_URL not set; skipping optional live DB migration round trip")

    asyncio.run(_reset_database(database_url))
    cfg = _alembic_config(database_url)

    command.upgrade(cfg, "head")
    upgraded_tables = asyncio.run(_table_names(database_url))
    upgraded_policy_document_columns = asyncio.run(_column_names(database_url, "policy_documents"))
    upgraded_policy_chunk_columns = asyncio.run(_column_names(database_url, "policy_chunks"))
    upgraded_policy_chunk_indexes = asyncio.run(_index_names(database_url, "policy_chunks"))

    assert PHASE21_TABLES.issubset(upgraded_tables)
    assert PHASE21_DOCUMENT_COLUMNS.issubset(upgraded_policy_document_columns)
    assert PHASE21_CHUNK_COLUMNS.issubset(upgraded_policy_chunk_columns)
    assert PHASE20_HYBRID_COLUMNS.issubset(upgraded_policy_chunk_columns)
    assert PHASE20_HYBRID_INDEXES.issubset(upgraded_policy_chunk_indexes)

    command.downgrade(cfg, "014_rag_hybrid_retrieval")
    downgraded_tables = asyncio.run(_table_names(database_url))
    downgraded_policy_document_columns = asyncio.run(_column_names(database_url, "policy_documents"))
    downgraded_policy_chunk_columns = asyncio.run(_column_names(database_url, "policy_chunks"))
    downgraded_policy_chunk_indexes = asyncio.run(_index_names(database_url, "policy_chunks"))

    assert downgraded_tables.isdisjoint(PHASE21_TABLES)
    assert downgraded_policy_document_columns.isdisjoint(PHASE21_DOCUMENT_COLUMNS)
    assert downgraded_policy_chunk_columns.isdisjoint(PHASE21_CHUNK_COLUMNS)
    assert PHASE20_HYBRID_COLUMNS.issubset(downgraded_policy_chunk_columns)
    assert PHASE20_HYBRID_INDEXES.issubset(downgraded_policy_chunk_indexes)

    command.upgrade(cfg, "head")
    reupgraded_tables = asyncio.run(_table_names(database_url))
    reupgraded_policy_document_columns = asyncio.run(_column_names(database_url, "policy_documents"))
    reupgraded_policy_chunk_columns = asyncio.run(_column_names(database_url, "policy_chunks"))

    assert PHASE21_TABLES.issubset(reupgraded_tables)
    assert PHASE21_DOCUMENT_COLUMNS.issubset(reupgraded_policy_document_columns)
    assert PHASE21_CHUNK_COLUMNS.issubset(reupgraded_policy_chunk_columns)
