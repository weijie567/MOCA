from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import (
    AgentTraceEvent,
    Base,
    EvidenceIdentityRollout,
    EvidenceSnapshotDependency,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
)

MIGRATION_PATH = Path("src/db/migrations/versions/025_phase64_2_immutable_evidence.py")
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
PREVIOUS_REVISION = "024_phase64_1_resume_attempt_lease"
EXPECTED_TABLES = {
    "policy_document_versions",
    "policy_chunk_versions",
    "evidence_snapshot_dependencies",
    "evidence_identity_rollouts",
}


def _config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    cfg.attributes["database_url"] = DATABASE_URL
    return cfg


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


def _named_schema_items(table_name: str) -> dict[str, object]:
    table = Base.metadata.tables[table_name]
    item_types = (CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint)
    return {
        item.name: item
        for item in [*table.constraints, *table.indexes]
        if isinstance(item, item_types) and item.name is not None
    }


def test_orm_and_migration_define_exact_additive_immutable_foundation() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision: str = "025_phase64_2_immutable_evidence"' in source
    assert f'down_revision: str | None = "{PREVIOUS_REVISION}"' in source
    assert EXPECTED_TABLES <= set(Base.metadata.tables)
    assert EvidenceSnapshotDependency.__tablename__ == "evidence_snapshot_dependencies"
    assert EvidenceIdentityRollout.__tablename__ == "evidence_identity_rollouts"
    assert {"evidence_write_sequence"} <= set(PolicyDocument.__table__.c.keys())
    assert {"evidence_write_sequence"} <= set(PolicyChunk.__table__.c.keys())
    assert {"evidence_snapshot_refs_json"} <= set(AgentTraceEvent.__table__.c.keys())

    document_columns = set(PolicyDocumentVersion.__table__.c.keys())
    chunk_columns = set(PolicyChunkVersion.__table__.c.keys())
    assert {
        "tenant_id",
        "scope_type",
        "scope_id",
        "doc_key",
        "document_version",
        "content",
        "content_hash",
        "source_locator_json",
        "lifecycle_status",
        "retention_until",
        "expired_at",
        "tombstoned_at",
        "supersedes_version_id",
        "corrects_version_id",
    } <= document_columns
    assert {
        "tenant_id",
        "policy_document_version_id",
        "scope_type",
        "scope_id",
        "doc_key",
        "document_version",
        "chunk_id",
        "chunk_version",
        "content",
        "text_hash",
        "source_locator_json",
        "lifecycle_status",
        "retention_until",
        "expired_at",
        "tombstoned_at",
        "supersedes_version_id",
        "corrects_version_id",
    } <= chunk_columns

    document_items = _named_schema_items("policy_document_versions")
    chunk_items = _named_schema_items("policy_chunk_versions")
    dependency_items = _named_schema_items("evidence_snapshot_dependencies")
    rollout_items = _named_schema_items("evidence_identity_rollouts")
    for item_name in (
        "ck_policy_document_versions_tenant_policy_scope",
        "ck_policy_document_versions_document_version_positive",
        "ck_policy_document_versions_content_hash",
        "ck_policy_document_versions_source_locator_allowlist",
        "uq_policy_document_versions_identity",
    ):
        assert item_name in document_items
    for item_name in (
        "ck_policy_chunk_versions_tenant_policy_scope",
        "ck_policy_chunk_versions_versions_positive",
        "ck_policy_chunk_versions_text_hash",
        "ck_policy_chunk_versions_source_locator_allowlist",
        "fk_policy_chunk_versions_document_identity",
        "uq_policy_chunk_versions_identity",
    ):
        assert item_name in chunk_items
    for item_name in (
        "fk_evidence_snapshot_dependencies_event_tenant",
        "fk_evidence_snapshot_dependencies_document_tenant",
        "fk_evidence_snapshot_dependencies_chunk_tenant_document",
        "uq_evidence_snapshot_dependencies_binding",
    ):
        assert item_name in dependency_items
    assert "ck_evidence_identity_rollouts_singleton" in rollout_items
    assert "ck_evidence_identity_rollouts_version_nonnegative" in rollout_items
    assert "'archived'" in str(
        document_items["ck_policy_document_versions_lifecycle_status"].sqltext
    )
    assert "'archived'" in str(chunk_items["ck_policy_chunk_versions_lifecycle_status"].sqltext)
    assert "'archived'" in source.split("_LIFECYCLE_CHECK =", 1)[1].split("\n", 1)[0]

    assert "CREATE SEQUENCE evidence_ingestion_write_seq" in source
    assert "evidence_ingestion_write_seq" in source
    assert "_assert_downgrade_safe" in source
    assert "_install_immutable_evidence_guards" in source


def test_migration_source_is_expansion_only_and_has_no_backfill_or_cutover() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    upgrade_source = source.split("def upgrade() -> None:", 1)[1].split("def downgrade() -> None:", 1)[0]
    normalized = re.sub(r"\s+", " ", upgrade_source.lower())

    assert "insert into evidence_identity_rollouts" in normalized
    assert "insert into policy_document_versions" not in normalized
    assert "insert into policy_chunk_versions" not in normalized
    assert "insert into evidence_snapshot_dependencies" not in normalized
    assert "insert into policy_documents select" not in normalized
    assert "insert into policy_document_versions select" not in normalized
    assert "insert into policy_chunk_versions select" not in normalized
    assert "update policy_documents" not in normalized
    assert "update policy_chunks" not in normalized
    assert "perform_backfill" not in normalized
    assert "backfill_current_heads" not in normalized
    assert "canonical_reads_enabled" in normalized
    assert 'server_default=sa.text("false")' in upgrade_source


def test_upgrade_performs_no_backfill() -> None:
    tenant_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    document_version_id = uuid.uuid4()
    invalid_document_version_id = uuid.uuid4()
    chunk_version_id = uuid.uuid4()
    run_id = uuid.uuid4()
    event_id = uuid.uuid4()
    dependency_id = uuid.uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    retention_until = now + timedelta(days=30)

    async def exercise() -> None:
        await _reset_schema()
        cfg = _config()
        await asyncio.to_thread(command.upgrade, cfg, PREVIOUS_REVISION)
        engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO tenants (id, name, status) VALUES (:tenant_id, 'phase64-2', 'active')"),
                    {"tenant_id": tenant_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO policy_documents "
                        "(id, tenant_id, doc_key, doc_type, title, effective_date, risk_level, version, content) "
                        "VALUES (:id, :tenant_id, 'refund_policy', 'refund', 'Refund Policy', "
                        "DATE '2026-01-01', 'medium', 3, 'mutable document head')"
                    ),
                    {"id": document_id, "tenant_id": tenant_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO policy_chunks "
                        "(id, tenant_id, doc_id, chunk_id, section, content, search_text, "
                        "source_block_refs_json, ocr_metadata_json, risk_level, effective_date) "
                        "VALUES (:id, :tenant_id, :doc_id, 'refund_001', 'Refund', 'mutable chunk head', "
                        "'mutable chunk head', '[]'::jsonb, '{}'::jsonb, 'medium', DATE '2026-01-01')"
                    ),
                    {"id": chunk_id, "tenant_id": tenant_id, "doc_id": document_id},
                )
        finally:
            await engine.dispose()

        await asyncio.to_thread(command.upgrade, cfg, "025_phase64_2_immutable_evidence")
        engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                assert await conn.scalar(text("SELECT count(*) FROM policy_document_versions")) == 0
                assert await conn.scalar(text("SELECT count(*) FROM policy_chunk_versions")) == 0
                assert await conn.scalar(text("SELECT count(*) FROM evidence_snapshot_dependencies")) == 0
                assert (
                    await conn.scalar(
                        text("SELECT evidence_write_sequence FROM policy_documents WHERE id = :id"),
                        {"id": document_id},
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT evidence_write_sequence FROM policy_chunks WHERE id = :id"),
                        {"id": chunk_id},
                    )
                    is None
                )
                rollout = (
                    await conn.execute(
                        text(
                            "SELECT rollout_version, dual_write_enabled_at, backfill_watermark_sequence, "
                            "reconciled_through_sequence, canonical_reads_enabled, quarantine_reason, audit_counts_json "
                            "FROM evidence_identity_rollouts WHERE id = 1"
                        )
                    )
                ).one()
                assert tuple(rollout[:6]) == (0, None, None, None, False, None)
                assert rollout.audit_counts_json == {}
                first_sequence = await conn.scalar(text("SELECT nextval('evidence_ingestion_write_seq')"))
                second_sequence = await conn.scalar(text("SELECT nextval('evidence_ingestion_write_seq')"))
                assert (first_sequence, second_sequence) == (1, 2)

            async with engine.connect() as conn:
                transaction = await conn.begin()
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text(
                            "INSERT INTO policy_document_versions "
                            "(id, tenant_id, policy_document_id, scope_type, scope_id, doc_key, document_version, "
                            "content, content_hash, source_locator_json, lifecycle_status, retention_until) "
                            "VALUES (:id, :tenant_id, :document_id, 'tenant_policy', 'wrong-scope', "
                            "'refund_policy', 3, 'invalid scope', :content_hash, :locator, 'active', :retention_until)"
                        ),
                        {
                            "id": invalid_document_version_id,
                            "tenant_id": tenant_id,
                            "document_id": document_id,
                            "content_hash": "sha256:" + "a" * 64,
                            "locator": json.dumps({"source_type": "policy_markdown"}),
                            "retention_until": retention_until,
                        },
                    )
                await transaction.rollback()

            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO policy_document_versions "
                        "(id, tenant_id, policy_document_id, scope_type, scope_id, doc_key, document_version, "
                        "content, content_hash, source_locator_json, lifecycle_status, retention_until) "
                        "VALUES (:id, :tenant_id, :document_id, 'tenant_policy', :scope_id, 'refund_policy', 3, "
                        "'retained immutable document', :content_hash, :locator, 'tombstoned', :retention_until)"
                    ),
                    {
                        "id": document_version_id,
                        "tenant_id": tenant_id,
                        "document_id": document_id,
                        "scope_id": str(tenant_id),
                        "content_hash": "sha256:" + "a" * 64,
                        "locator": json.dumps({"source_type": "policy_markdown", "source_uri": "policies/refund.md"}),
                        "retention_until": retention_until,
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO policy_chunk_versions "
                        "(id, tenant_id, policy_document_version_id, scope_type, scope_id, doc_key, "
                        "document_version, chunk_id, chunk_version, content, text_hash, source_locator_json, "
                        "lifecycle_status, retention_until, tombstoned_at) "
                        "VALUES (:id, :tenant_id, :document_version_id, 'tenant_policy', :scope_id, "
                        "'refund_policy', 3, 'refund_001', 2, 'retained immutable chunk', :text_hash, "
                        ":locator, 'tombstoned', :retention_until, :now)"
                    ),
                    {
                        "id": chunk_version_id,
                        "tenant_id": tenant_id,
                        "document_version_id": document_version_id,
                        "scope_id": str(tenant_id),
                        "text_hash": "sha256:" + "b" * 64,
                        "locator": json.dumps(
                            {
                                "source_type": "policy_markdown",
                                "source_uri": "policies/refund.md",
                                "source_block_refs": ["block-1"],
                            }
                        ),
                        "retention_until": retention_until,
                        "now": now,
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO agent_runs "
                        "(id, thread_id, tenant_id, user_id, input_query, final_status, scope_classification, started_at) "
                        "VALUES (:id, 'thread-64-2', :tenant_id, :user_id, 'test', 'completed', 'policy_only', :now)"
                    ),
                    {"id": run_id, "tenant_id": tenant_id, "user_id": uuid.uuid4(), "now": now},
                )
                await conn.execute(
                    text(
                        "INSERT INTO agent_trace_events "
                        "(event_id, run_id, sequence, tenant_id, thread_id, event_type, schema_version, occurred_at, "
                        "actor, resource_refs, redaction_policy_version, redacted_payload, evidence_snapshot_refs_json) "
                        "VALUES (:event_id, :run_id, 1, :tenant_id, 'thread-64-2', 'rag_retrieval_completed', "
                        "'replay_event.v3', :now, CAST(:actor AS jsonb), '{}'::jsonb, "
                        "'redaction.v1', '{}'::jsonb, '[\"sha256:snapshot\"]'::jsonb)"
                    ),
                    {
                        "event_id": event_id,
                        "run_id": run_id,
                        "tenant_id": tenant_id,
                        "now": now,
                        "actor": json.dumps({"type": "agent", "id": None}),
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO evidence_snapshot_dependencies "
                        "(id, tenant_id, event_id, document_version_id, chunk_version_id, retention_until) "
                        "VALUES (:id, :tenant_id, :event_id, :document_version_id, :chunk_version_id, :retention_until)"
                    ),
                    {
                        "id": dependency_id,
                        "tenant_id": tenant_id,
                        "event_id": event_id,
                        "document_version_id": document_version_id,
                        "chunk_version_id": chunk_version_id,
                        "retention_until": retention_until,
                    },
                )
                await conn.execute(
                    text(
                        "UPDATE policy_document_versions SET lifecycle_status = 'archived' WHERE id = :id"
                    ),
                    {"id": document_version_id},
                )
                await conn.execute(
                    text("UPDATE policy_chunk_versions SET lifecycle_status = 'archived' WHERE id = :id"),
                    {"id": chunk_version_id},
                )

            async with engine.connect() as conn:
                retained = (
                    await conn.execute(
                        text(
                            "SELECT content, text_hash, source_locator_json, lifecycle_status "
                            "FROM policy_chunk_versions WHERE id = :id"
                        ),
                        {"id": chunk_version_id},
                    )
                ).one()
                assert retained.content == "retained immutable chunk"
                assert retained.text_hash == "sha256:" + "b" * 64
                assert retained.source_locator_json["source_uri"] == "policies/refund.md"
                assert retained.lifecycle_status == "archived"

            async with engine.connect() as conn:
                transaction = await conn.begin()
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text("UPDATE policy_chunk_versions SET content = 'mutated' WHERE id = :id"),
                        {"id": chunk_version_id},
                    )
                await transaction.rollback()

            async with engine.connect() as conn:
                transaction = await conn.begin()
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text("DELETE FROM policy_chunk_versions WHERE id = :id"),
                        {"id": chunk_version_id},
                    )
                await transaction.rollback()

            with pytest.raises(RuntimeError, match="immutable evidence history"):
                await asyncio.to_thread(command.downgrade, cfg, PREVIOUS_REVISION)
        finally:
            await engine.dispose()
            await _reset_schema()

    asyncio.run(exercise())
