from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import Base


MIGRATION_PATH = Path("src/db/migrations/versions/028_phase64_2_memory_lifecycle.py")
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
PREVIOUS_REVISION = "027_phase64_2_memory_provenance"
_HASH_A = "sha256:" + "a" * 64
_HASH_B = "sha256:" + "b" * 64
_HASH_C = "sha256:" + "c" * 64
_HASH_D = "sha256:" + "d" * 64
_HASH_E = "sha256:" + "e" * 64


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


def _named_items(table_name: str) -> dict[str, object]:
    table = Base.metadata.tables[table_name]
    supported = (CheckConstraint, ForeignKeyConstraint, UniqueConstraint)
    return {
        item.name: item
        for item in [*table.constraints, *table.indexes]
        if isinstance(item, supported) and item.name is not None
    }


def test_orm_and_migration_define_durable_exact_identity_claims() -> None:
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "case_memory_identity_claims" in Base.metadata.tables
    claim_table = Base.metadata.tables["case_memory_identity_claims"]
    assert {
        "identity_algorithm_version",
        "tenant_id",
        "scope_type",
        "scope_id",
        "candidate_hash",
        "content_hash",
        "source_identity_hash",
        "owner_case_memory_id",
        "claim_state",
        "terminal_status",
        "terminal_reason",
        "terminal_at",
        "lifecycle_version",
    } <= set(claim_table.c.keys())
    assert all(
        not claim_table.c[column].nullable
        for column in (
            "identity_algorithm_version",
            "tenant_id",
            "scope_type",
            "scope_id",
            "candidate_hash",
            "content_hash",
            "source_identity_hash",
            "owner_case_memory_id",
            "claim_state",
            "lifecycle_version",
        )
    )

    items = _named_items("case_memory_identity_claims")
    exact_unique = items["uq_case_memory_identity_claims_exact_identity"]
    assert isinstance(exact_unique, UniqueConstraint)
    assert [column.name for column in exact_unique.columns] == [
        "identity_algorithm_version",
        "tenant_id",
        "scope_type",
        "scope_id",
        "candidate_hash",
        "content_hash",
        "source_identity_hash",
    ]
    assert "ck_case_memory_identity_claims_state" in items
    assert "ck_case_memory_identity_claims_terminal_fields" in items
    assert "ck_case_memory_identity_claims_lifecycle_version_positive" in items
    owner_fk = items["fk_case_memory_identity_claims_owner_tenant"]
    assert isinstance(owner_fk, ForeignKeyConstraint)
    assert all(element.ondelete == "RESTRICT" for element in owner_fk.elements)

    assert 'revision: str = "028_phase64_2_memory_lifecycle"' in source
    assert f'down_revision: str | None = "{PREVIOUS_REVISION}"' in source
    assert "_classify_identity_rows" in source
    assert "identity_resolution_status IN ('canonical', 'legacy_resolved')" in source
    assert "phase64_2_exact_identity_duplicate" in source
    assert "_assert_downgrade_safe" in source
    assert "cannot downgrade while case-memory claim or lineage history is retained" in source


def _resolved_provenance(
    *,
    tenant_id: uuid.UUID,
    scope_id: str,
    run_id: uuid.UUID,
    candidate_hash: str,
    content_hash: str,
    source_identity_hash: str,
) -> dict[str, object]:
    return {
        "schema_version": "case_memory_provenance.v1",
        "resolution_status": "canonical",
        "tenant_id": str(tenant_id),
        "scope_type": "case",
        "scope_id": scope_id,
        "memory_authority_class": "contextual_only",
        "source_authorities": [],
        "source_run_id": str(run_id),
        "evidence_refs": [],
        "business_fact_refs": [],
        "identity_algorithm_version": "memory_identity.v1",
        "identity_profile": "nfc_selective_v2",
        "candidate_hash": candidate_hash,
        "content_hash": content_hash,
        "source_identity_hash": source_identity_hash,
    }


async def _insert_case_memory(
    conn,
    *,
    memory_id: uuid.UUID,
    tenant_id: uuid.UUID,
    scope_id: str,
    run_id: uuid.UUID,
    created_at: datetime,
    candidate_hash: str | None,
    content_hash: str,
    source_identity_hash: str | None,
    resolution_status: str,
    review_status: str = "needs_review",
) -> None:
    provenance: dict[str, object]
    if resolution_status == "legacy_unresolved":
        provenance = {
            "schema_version": "case_memory_provenance_legacy_unresolved.v1",
            "resolution_status": "legacy_unresolved",
            "tenant_id": str(tenant_id),
            "case_memory_id": str(memory_id),
            "legacy_content_hash": content_hash,
            "legacy_source_identity_hash": source_identity_hash,
            "legacy_source_ref": {"source_type": "legacy", "event_id": str(memory_id)},
            "legacy_policy_refs": [],
            "unresolved_reasons": ["pre_027_provenance_unavailable"],
        }
    else:
        assert candidate_hash is not None
        assert source_identity_hash is not None
        provenance = _resolved_provenance(
            tenant_id=tenant_id,
            scope_id=scope_id,
            run_id=run_id,
            candidate_hash=candidate_hash,
            content_hash=content_hash,
            source_identity_hash=source_identity_hash,
        )
    await conn.execute(
        text(
            "INSERT INTO case_memories "
            "(id, tenant_id, scope_type, scope_id, case_type, summary, excerpt, content_hash, "
            "policy_refs_json, source_ref_json, source_identity_hash, identity_algorithm_version, "
            "candidate_hash, identity_resolution_status, provenance_json, lifecycle_version, "
            "review_status, pii_classification, created_by_run_id, created_at, updated_at) "
            "VALUES (:id, :tenant_id, 'case', :scope_id, 'refund_dispute', :summary, :excerpt, "
            ":content_hash, '[]'::jsonb, CAST(:source_ref AS jsonb), :source_identity_hash, "
            ":identity_algorithm_version, :candidate_hash, :resolution_status, CAST(:provenance AS jsonb), "
            "1, :review_status, 'none', :run_id, :created_at, :created_at)"
        ),
        {
            "id": memory_id,
            "tenant_id": tenant_id,
            "scope_id": scope_id,
            "summary": f"memory-{memory_id}",
            "excerpt": f"excerpt-{memory_id}",
            "content_hash": content_hash,
            "source_ref": json.dumps({"source_type": "closed_case_cwc_candidate", "event_id": str(memory_id)}),
            "source_identity_hash": source_identity_hash,
            "identity_algorithm_version": "memory_identity.v1" if resolution_status != "legacy_unresolved" else None,
            "candidate_hash": candidate_hash,
            "resolution_status": resolution_status,
            "provenance": json.dumps(provenance),
            "review_status": review_status,
            "run_id": run_id,
            "created_at": created_at,
        },
    )


def test_migration_backfills_exact_claims_and_survivor_to_many_lineage() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    scope_id = str(uuid.uuid4())
    duplicate_ids = [uuid.UUID(int=value) for value in range(101, 105)]
    source_distinct_id = uuid.UUID(int=105)
    unresolved_id = uuid.UUID(int=106)
    terminal_id = uuid.UUID(int=107)
    started_at = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)

    async def exercise() -> None:
        await _reset_schema()
        cfg = _config()
        await asyncio.to_thread(command.upgrade, cfg, PREVIOUS_REVISION)
        engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO tenants (id, name, status) VALUES (:id, 'phase64-2-memory', 'active')"),
                    {"id": tenant_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO users (id, tenant_id, username, password_hash, role, is_active) "
                        "VALUES (:id, :tenant_id, 'phase64-2-user', 'test', 'admin', true)"
                    ),
                    {"id": user_id, "tenant_id": tenant_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO agent_runs "
                        "(id, tenant_id, user_id, thread_id, input_query, final_status, started_at) "
                        "VALUES (:id, :tenant_id, :user_id, 'phase64-2', 'migration', 'completed', :started_at)"
                    ),
                    {"id": run_id, "tenant_id": tenant_id, "user_id": user_id, "started_at": started_at},
                )
                for ordinal, memory_id in enumerate(duplicate_ids):
                    await _insert_case_memory(
                        conn,
                        memory_id=memory_id,
                        tenant_id=tenant_id,
                        scope_id=scope_id,
                        run_id=run_id,
                        created_at=started_at + timedelta(seconds=ordinal),
                        candidate_hash=_HASH_C,
                        content_hash=_HASH_A,
                        source_identity_hash=_HASH_B,
                        resolution_status="canonical",
                    )
                await _insert_case_memory(
                    conn,
                    memory_id=source_distinct_id,
                    tenant_id=tenant_id,
                    scope_id=scope_id,
                    run_id=run_id,
                    created_at=started_at + timedelta(seconds=10),
                    candidate_hash=_HASH_E,
                    content_hash=_HASH_A,
                    source_identity_hash=_HASH_D,
                    resolution_status="canonical",
                )
                await _insert_case_memory(
                    conn,
                    memory_id=unresolved_id,
                    tenant_id=tenant_id,
                    scope_id=scope_id,
                    run_id=run_id,
                    created_at=started_at + timedelta(seconds=11),
                    candidate_hash=None,
                    content_hash=_HASH_A,
                    source_identity_hash=None,
                    resolution_status="legacy_unresolved",
                )
                await _insert_case_memory(
                    conn,
                    memory_id=terminal_id,
                    tenant_id=tenant_id,
                    scope_id=scope_id,
                    run_id=run_id,
                    created_at=started_at + timedelta(seconds=12),
                    candidate_hash=_HASH_D,
                    content_hash=_HASH_D,
                    source_identity_hash=_HASH_E,
                    resolution_status="canonical",
                    review_status="rejected",
                )
        finally:
            await engine.dispose()

        await asyncio.to_thread(command.upgrade, cfg, "028_phase64_2_memory_lifecycle")
        engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                duplicate_rows = (
                    await conn.execute(
                        text(
                            "SELECT id, review_status, review_reason, lifecycle_version "
                            "FROM case_memories WHERE id = ANY(:ids) ORDER BY created_at, id"
                        ),
                        {"ids": duplicate_ids},
                    )
                ).all()
                assert duplicate_rows[0].id == duplicate_ids[0]
                assert duplicate_rows[0].review_status == "needs_review"
                assert [row.review_status for row in duplicate_rows[1:]] == ["superseded"] * 3
                assert all("phase64_2_exact_identity_duplicate" in row.review_reason for row in duplicate_rows[1:])
                assert [row.lifecycle_version for row in duplicate_rows] == [1, 2, 2, 2]

                links = (
                    await conn.execute(
                        text(
                            "SELECT survivor_case_memory_id, related_case_memory_id, relation, ordinal "
                            "FROM case_memory_lineage_links WHERE survivor_case_memory_id = :owner "
                            "ORDER BY ordinal"
                        ),
                        {"owner": duplicate_ids[0]},
                    )
                ).all()
                assert [row.related_case_memory_id for row in links] == duplicate_ids[1:]
                assert [row.ordinal for row in links] == [1, 2, 3]
                assert {row.relation for row in links} == {"duplicate"}

                claims = (
                    await conn.execute(
                        text(
                            "SELECT owner_case_memory_id, candidate_hash, content_hash, source_identity_hash, "
                            "claim_state, terminal_status, terminal_reason, terminal_at, lifecycle_version "
                            "FROM case_memory_identity_claims ORDER BY owner_case_memory_id"
                        )
                    )
                ).all()
                assert len(claims) == 3
                duplicate_claim = next(row for row in claims if row.candidate_hash == _HASH_C)
                assert duplicate_claim.owner_case_memory_id == duplicate_ids[0]
                assert duplicate_claim.claim_state == "active"
                assert duplicate_claim.terminal_status is None
                distinct_claim = next(row for row in claims if row.owner_case_memory_id == source_distinct_id)
                assert distinct_claim.content_hash == _HASH_A
                assert distinct_claim.source_identity_hash == _HASH_D
                terminal_claim = next(row for row in claims if row.owner_case_memory_id == terminal_id)
                assert terminal_claim.claim_state == "terminal"
                assert terminal_claim.terminal_status == "rejected"
                assert terminal_claim.terminal_reason == "migration_backfill_terminal"
                assert terminal_claim.terminal_at is not None

                unresolved = (
                    await conn.execute(
                        text(
                            "SELECT review_status FROM case_memories WHERE id = :id"
                        ),
                        {"id": unresolved_id},
                    )
                ).one()
                assert unresolved.review_status == "needs_review"
                unresolved_claims = await conn.scalar(
                    text("SELECT count(*) FROM case_memory_identity_claims WHERE owner_case_memory_id = :id"),
                    {"id": unresolved_id},
                )
                unresolved_links = await conn.scalar(
                    text(
                        "SELECT count(*) FROM case_memory_lineage_links "
                        "WHERE survivor_case_memory_id = :id OR related_case_memory_id = :id"
                    ),
                    {"id": unresolved_id},
                )
                assert unresolved_claims == 0
                assert unresolved_links == 0

            async with engine.connect() as conn:
                transaction = await conn.begin()
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text(
                            "INSERT INTO case_memory_identity_claims "
                            "(id, identity_algorithm_version, tenant_id, scope_type, scope_id, candidate_hash, "
                            "content_hash, source_identity_hash, owner_case_memory_id, claim_state, lifecycle_version) "
                            "VALUES (:id, 'memory_identity.v1', :tenant_id, 'case', :scope_id, :candidate_hash, "
                            ":content_hash, :source_hash, :owner, 'active', 1)"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "tenant_id": tenant_id,
                            "scope_id": scope_id,
                            "candidate_hash": _HASH_C,
                            "content_hash": _HASH_A,
                            "source_hash": _HASH_B,
                            "owner": duplicate_ids[0],
                        },
                    )
                await transaction.rollback()

            with pytest.raises(RuntimeError, match="claim or lineage history"):
                await asyncio.to_thread(command.downgrade, cfg, PREVIOUS_REVISION)
        finally:
            await engine.dispose()

    asyncio.run(exercise())
