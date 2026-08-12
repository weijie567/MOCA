from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import (
    Base,
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocumentVersion,
    RagIngestionJob,
)
from src.knowledge.text_hash import evidence_text_hash
from tests.migration_helpers import upgrade_to_head_with_evidence_cutover


MIGRATION_PATH = Path("src/db/migrations/versions/030_phase64_4_token_corpora.py")
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
MIGRATION_REVISION = "030_phase64_4_token_corpora"

EXPECTED_TABLES = {
    "policy_corpus_versions",
    "policy_corpus_manifest_revisions",
    "policy_corpus_rollouts",
    "policy_corpus_activation_history",
    "corpus_document_bindings",
    "corpus_block_bindings",
    "corpus_chunk_bindings",
}
CURRENT_CHUNK_AUDIT_COLUMNS = {
    "chunking_config_fingerprint",
    "embedding_input_hash",
    "embedding_token_count",
}
IMMUTABLE_DOCUMENT_SOURCE_COLUMNS = {
    "source_checksum",
    "canonical_content_schema_version",
    "canonical_blocks_json",
    "canonical_blocks_hash",
}
IMMUTABLE_CHUNK_AUDIT_COLUMNS = {
    "search_text",
    "embedding",
    *CURRENT_CHUNK_AUDIT_COLUMNS,
}
INGESTION_AUDIT_COLUMNS = {
    "chunking_config_fingerprint",
    "chunk_count",
    "embedding_token_count_min",
    "embedding_token_count_max",
    "embedding_token_count_total",
    "provider_prompt_tokens",
    "provider_total_tokens",
    "provider_usage_status",
}


def _config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    cfg.attributes["database_url"] = DATABASE_URL
    return cfg


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


def _schema_item_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    schema_types = (CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint)
    return {
        item.name
        for item in [*table.constraints, *table.indexes]
        if isinstance(item, schema_types) and item.name is not None
    }


def test_token_corpus_orm_matches_projection_and_audit_contract() -> None:
    assert MIGRATION_PATH.exists()
    assert EXPECTED_TABLES.issubset(Base.metadata.tables)

    assert CURRENT_CHUNK_AUDIT_COLUMNS.issubset(PolicyChunk.__table__.c.keys())
    assert IMMUTABLE_DOCUMENT_SOURCE_COLUMNS.issubset(PolicyDocumentVersion.__table__.c.keys())
    assert IMMUTABLE_CHUNK_AUDIT_COLUMNS.issubset(PolicyChunkVersion.__table__.c.keys())
    assert INGESTION_AUDIT_COLUMNS.issubset(RagIngestionJob.__table__.c.keys())

    assert "corpus_version_id" not in PolicyDocumentVersion.__table__.c
    assert "corpus_version_id" not in PolicyChunkVersion.__table__.c
    assert "corpus_id" not in PolicyDocumentVersion.__table__.c
    assert "corpus_id" not in PolicyChunkVersion.__table__.c

    assert {
        "uq_policy_corpus_versions_id_tenant",
        "uq_policy_corpus_versions_tenant_generation",
        "ck_policy_corpus_versions_config_fingerprint",
        "ck_policy_corpus_versions_state",
    }.issubset(_schema_item_names(PolicyCorpusVersion.__tablename__))
    assert {
        "uq_policy_corpus_rollouts_tenant",
        "fk_policy_corpus_rollouts_active_tenant",
        "ck_policy_corpus_rollouts_epoch_positive",
    }.issubset(_schema_item_names(PolicyCorpusRollout.__tablename__))
    assert {
        "fk_corpus_document_bindings_corpus_tenant",
        "fk_corpus_document_bindings_current_tenant",
        "fk_corpus_document_bindings_immutable_tenant",
    }.issubset(_schema_item_names(CorpusDocumentBinding.__tablename__))
    assert {
        "fk_corpus_block_bindings_corpus_tenant",
        "fk_corpus_block_bindings_current_tenant",
        "fk_corpus_block_bindings_document_version_tenant",
    }.issubset(_schema_item_names(CorpusBlockBinding.__tablename__))
    assert {
        "fk_corpus_chunk_bindings_corpus_tenant",
        "fk_corpus_chunk_bindings_current_tenant",
        "fk_corpus_chunk_bindings_immutable_tenant",
    }.issubset(_schema_item_names(CorpusChunkBinding.__tablename__))


def test_migration_declares_safe_bootstrap_append_only_guards_and_downgrade_refusal() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert f'revision: str = "{MIGRATION_REVISION}"' in source
    assert 'down_revision: str | None = "029_phase64_3_rag_eval_rounds"' in source
    assert "character.v1" in source
    assert "character_compatibility.v1" in source
    assert "SELECT id FROM tenants ORDER BY id" in source
    assert "bootstrap_counts_json" in source
    assert "current_document_count" in source
    assert "bound_document_count" in source
    assert "current_block_count" in source
    assert "bound_block_count" in source
    assert "current_chunk_count" in source
    assert "bound_chunk_count" in source
    assert "guard_policy_corpus_manifest_revision_mutation" in source
    assert "guard_policy_corpus_activation_history_mutation" in source
    assert "guard_corpus_projection_binding_mutation" in source
    assert "refusing downgrade: token-aware corpus or audit dependencies exist" in source


async def _seed_legacy_heads() -> dict[UUID, dict[str, object]]:
    now = datetime.now(UTC)
    retention_until = now + timedelta(days=3650)
    tenant_specs = (
        (uuid4(), "legacy-corpus-a", 2),
        (uuid4(), "legacy-corpus-b", 1),
        (uuid4(), "legacy-corpus-empty", 0),
    )
    expected: dict[UUID, dict[str, object]] = {}
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for tenant_id, tenant_name, document_count in tenant_specs:
                await connection.execute(
                    text("INSERT INTO tenants (id, name, status) VALUES (:tenant_id, :tenant_name, 'active')"),
                    {"tenant_id": tenant_id, "tenant_name": tenant_name},
                )
                document_ids: list[UUID] = []
                block_ids: list[UUID] = []
                chunk_ids: list[UUID] = []
                for index in range(document_count):
                    document_id = uuid4()
                    document_version_id = uuid4()
                    doc_key = f"{tenant_name}-policy-{index}"
                    content = f"{tenant_name} authoritative policy content {index}"
                    source_checksum = f"{index + 1:064x}"
                    document_ids.append(document_id)
                    await connection.execute(
                        text(
                            "INSERT INTO policy_documents "
                            "(id, tenant_id, doc_key, doc_type, title, effective_date, risk_level, version, "
                            "content, source_type, source_checksum, parser_metadata_json, "
                            "policy_version_fingerprint, evidence_write_sequence) "
                            "VALUES (:id, :tenant_id, :doc_key, 'refund_rule', :title, '2026-01-01', "
                            "'medium', 1, :content, 'legacy_fixture', :source_checksum, '{}'::jsonb, "
                            ":fingerprint, :sequence)"
                        ),
                        {
                            "id": document_id,
                            "tenant_id": tenant_id,
                            "doc_key": doc_key,
                            "title": f"Legacy policy {index}",
                            "content": content,
                            "source_checksum": source_checksum,
                            "fingerprint": f"legacy-fingerprint-{index}",
                            "sequence": index + 1,
                        },
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO policy_document_versions "
                            "(id, tenant_id, policy_document_id, scope_type, scope_id, doc_key, "
                            "document_version, content, content_hash, source_locator_json, lifecycle_status, "
                            "retention_until) VALUES (:id, :tenant_id, :document_id, 'tenant_policy', "
                            ":scope_id, :doc_key, 1, :content, :content_hash, "
                            "CAST(:locator AS jsonb), 'active', :retention_until)"
                        ),
                        {
                            "id": document_version_id,
                            "tenant_id": tenant_id,
                            "scope_id": str(tenant_id),
                            "document_id": document_id,
                            "doc_key": doc_key,
                            "content": content,
                            "content_hash": evidence_text_hash(content),
                            "locator": json.dumps(
                                {"source_type": "legacy_fixture", "source_checksum": source_checksum}
                            ),
                            "retention_until": retention_until,
                        },
                    )

                    block_id = uuid4()
                    source_block_id = f"{doc_key}:block:0"
                    block_ids.append(block_id)
                    await connection.execute(
                        text(
                            "INSERT INTO document_blocks "
                            "(id, tenant_id, doc_id, source_block_id, block_index, block_type, text, "
                            "normalized_text, text_hash, bbox_json, table_metadata_json, "
                            "parser_metadata_json, ocr_metadata_json, source_uri) "
                            "VALUES (:id, :tenant_id, :doc_id, :source_block_id, 0, 'paragraph', :content, "
                            ":content, :text_hash, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, NULL)"
                        ),
                        {
                            "id": block_id,
                            "tenant_id": tenant_id,
                            "doc_id": document_id,
                            "source_block_id": source_block_id,
                            "content": content,
                            "text_hash": evidence_text_hash(content),
                        },
                    )

                    current_chunk_id = uuid4()
                    immutable_chunk_id = uuid4()
                    logical_chunk_id = f"{doc_key}#000"
                    chunk_ids.append(current_chunk_id)
                    await connection.execute(
                        text(
                            "INSERT INTO policy_chunks "
                            "(id, tenant_id, doc_id, chunk_id, section, content, search_text, "
                            "source_block_refs_json, ocr_metadata_json, risk_level, effective_date, "
                            "evidence_write_sequence) VALUES (:id, :tenant_id, :doc_id, :chunk_id, "
                            "'intro', :content, :content, CAST(:source_refs AS jsonb), '{}'::jsonb, "
                            "'medium', '2026-01-01', :sequence)"
                        ),
                        {
                            "id": current_chunk_id,
                            "tenant_id": tenant_id,
                            "doc_id": document_id,
                            "chunk_id": logical_chunk_id,
                            "content": content,
                            "source_refs": json.dumps([{"source_block_id": source_block_id}]),
                            "sequence": index + 1,
                        },
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO policy_chunk_versions "
                            "(id, tenant_id, policy_document_version_id, scope_type, scope_id, doc_key, "
                            "document_version, chunk_id, chunk_version, content, text_hash, "
                            "source_locator_json, lifecycle_status, retention_until) "
                            "VALUES (:id, :tenant_id, :document_version_id, 'tenant_policy', "
                            ":scope_id, :doc_key, 1, :chunk_id, 1, :content, :text_hash, "
                            "CAST(:locator AS jsonb), 'active', :retention_until)"
                        ),
                        {
                            "id": immutable_chunk_id,
                            "tenant_id": tenant_id,
                            "scope_id": str(tenant_id),
                            "document_version_id": document_version_id,
                            "doc_key": doc_key,
                            "chunk_id": logical_chunk_id,
                            "content": content,
                            "text_hash": evidence_text_hash(content),
                            "locator": json.dumps(
                                {
                                    "source_type": "legacy_fixture",
                                    "source_block_refs": [{"source_block_id": source_block_id}],
                                }
                            ),
                            "retention_until": retention_until,
                        },
                    )

                    if index == 0:
                        await connection.execute(
                            text(
                                "INSERT INTO rag_ingestion_jobs "
                                "(id, tenant_id, doc_id, doc_key, source_type, source_checksum, parser_name, "
                                "parser_version, stage, status, warnings_json, counts_json, timings_json) "
                                "VALUES (:id, :tenant_id, :doc_id, :doc_key, 'legacy_fixture', "
                                ":source_checksum, 'legacy_parser', '1', 'completed', 'success', "
                                "'[]'::jsonb, '{}'::jsonb, '{}'::jsonb)"
                            ),
                            {
                                "id": uuid4(),
                                "tenant_id": tenant_id,
                                "doc_id": document_id,
                                "doc_key": doc_key,
                                "source_checksum": source_checksum,
                            },
                        )

                expected[tenant_id] = {
                    "document_ids": set(document_ids),
                    "block_ids": set(block_ids),
                    "chunk_ids": set(chunk_ids),
                    "counts": {
                        "current_document_count": len(document_ids),
                        "current_block_count": len(block_ids),
                        "current_chunk_count": len(chunk_ids),
                        "current_job_count": int(document_count > 0),
                    },
                }
    finally:
        await engine.dispose()
    return expected


async def _assert_bootstrap(expected: Mapping[UUID, Mapping[str, object]]) -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            corpus_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT id, tenant_id, generation_name, config_schema_version, "
                            "config_fingerprint, state, bootstrap_counts_json "
                            "FROM policy_corpus_versions ORDER BY tenant_id"
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert len(corpus_rows) == len(expected)
            corpus_by_tenant = {row["tenant_id"]: row for row in corpus_rows}
            assert set(corpus_by_tenant) == set(expected)

            for tenant_id, tenant_expected in expected.items():
                corpus = corpus_by_tenant[tenant_id]
                assert corpus["generation_name"] == "character.v1"
                assert corpus["config_schema_version"] == "character_compatibility.v1"
                assert str(corpus["config_fingerprint"]).startswith("sha256:")
                assert corpus["state"] == "complete"
                counts = dict(corpus["bootstrap_counts_json"])
                assert {key: counts[key] for key in tenant_expected["counts"]} == tenant_expected["counts"]
                assert counts["bound_document_count"] == counts["current_document_count"]
                assert counts["bound_block_count"] == counts["current_block_count"]
                assert counts["bound_chunk_count"] == counts["current_chunk_count"]
                assert counts["orphan_binding_count"] == 0
                assert counts["duplicate_binding_count"] == 0

                rollout = (
                    (
                        await connection.execute(
                            text(
                                "SELECT active_corpus_version_id, previous_corpus_version_id, rollout_epoch "
                                "FROM policy_corpus_rollouts WHERE tenant_id = :tenant_id"
                            ),
                            {"tenant_id": tenant_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                assert dict(rollout) == {
                    "active_corpus_version_id": corpus["id"],
                    "previous_corpus_version_id": None,
                    "rollout_epoch": 1,
                }

                history_count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM policy_corpus_activation_history "
                        "WHERE tenant_id = :tenant_id AND to_corpus_version_id = :corpus_id "
                        "AND rollout_epoch = 1 AND reason_code = 'bootstrap_character_v1'"
                    ),
                    {"tenant_id": tenant_id, "corpus_id": corpus["id"]},
                )
                assert history_count == 1
                manifest_count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM policy_corpus_manifest_revisions "
                        "WHERE tenant_id = :tenant_id AND revision = 1"
                    ),
                    {"tenant_id": tenant_id},
                )
                assert manifest_count == 1

                binding_specs = (
                    ("corpus_document_bindings", "policy_document_id", "document_ids"),
                    ("corpus_block_bindings", "document_block_id", "block_ids"),
                    ("corpus_chunk_bindings", "policy_chunk_id", "chunk_ids"),
                )
                for table_name, id_column, expected_key in binding_specs:
                    bound_ids = {
                        row[0]
                        for row in await connection.execute(
                            text(
                                f"SELECT {id_column} FROM {table_name} "
                                "WHERE tenant_id = :tenant_id AND corpus_version_id = :corpus_id"
                            ),
                            {"tenant_id": tenant_id, "corpus_id": corpus["id"]},
                        )
                    }
                    assert bound_ids == tenant_expected[expected_key]

            active_visibility = {
                (row["tenant_id"], row["policy_chunk_id"])
                for row in (
                    await connection.execute(
                        text(
                            "SELECT b.tenant_id, b.policy_chunk_id FROM corpus_chunk_bindings b "
                            "JOIN policy_corpus_rollouts r ON r.tenant_id = b.tenant_id "
                            "AND r.active_corpus_version_id = b.corpus_version_id"
                        )
                    )
                ).mappings()
            }
            expected_visibility = {
                (tenant_id, chunk_id)
                for tenant_id, tenant_expected in expected.items()
                for chunk_id in tenant_expected["chunk_ids"]
            }
            assert active_visibility == expected_visibility
    finally:
        await engine.dispose()


def test_postgresql_bootstrap_preserves_exact_visibility_and_refuses_token_downgrade() -> None:
    async def exercise() -> None:
        await _reset_schema()
        cfg = _config()
        await upgrade_to_head_with_evidence_cutover(
            cfg,
            database_url=DATABASE_URL,
            target_revision="029_phase64_3_rag_eval_rounds",
        )
        expected = await _seed_legacy_heads()
        await asyncio.to_thread(command.upgrade, cfg, MIGRATION_REVISION)
        await _assert_bootstrap(expected)

        engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE policy_chunks SET chunking_config_fingerprint = :fingerprint, "
                        "embedding_input_hash = :input_hash, embedding_token_count = 17 "
                        "WHERE id = (SELECT id FROM policy_chunks ORDER BY id LIMIT 1)"
                    ),
                    {
                        "fingerprint": "sha256:" + "a" * 64,
                        "input_hash": "sha256:" + "b" * 64,
                    },
                )
        finally:
            await engine.dispose()

        with pytest.raises(RuntimeError, match="token-aware corpus or audit dependencies exist"):
            await asyncio.to_thread(command.downgrade, cfg, "029_phase64_3_rag_eval_rounds")

        await _reset_schema()
        await upgrade_to_head_with_evidence_cutover(cfg, database_url=DATABASE_URL)

    asyncio.run(exercise())
