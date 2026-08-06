from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import (
    AgentRun,
    Base,
    CaseMemory,
    CaseMemoryIdentityClaim,
    CaseMemoryLineageLink,
    MemoryTombstone,
    MemoryWriteEvent,
)
from src.memory import schemas as memory_schemas
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.schemas import CaseMemoryReviewDecision, CaseMemoryWriteCandidate


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


async def _upgrade_to_previous_revision(cfg: Config) -> None:
    await asyncio.to_thread(command.upgrade, cfg, "025_phase64_2_immutable_evidence")
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            checked_at = datetime.now(UTC).isoformat()
            await conn.execute(
                text(
                    "UPDATE evidence_identity_rollouts SET dual_write_enabled_at = CURRENT_TIMESTAMP, "
                    "audit_counts_json = CAST(:audit AS jsonb) WHERE id = 1"
                ),
                {
                    "audit": json.dumps(
                        {
                            "dual_write_health": "healthy",
                            "dual_write_health_checked_at": checked_at,
                        }
                    )
                },
            )
    finally:
        await engine.dispose()
    await asyncio.to_thread(command.upgrade, cfg, PREVIOUS_REVISION)


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
        await _upgrade_to_previous_revision(cfg)
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
                        "(id, tenant_id, user_id, thread_id, input_query, final_status, scope_classification, "
                        "started_at) VALUES (:id, :tenant_id, :user_id, 'phase64-2', 'migration', 'completed', "
                        "'unknown_legacy', :started_at)"
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
                        text("SELECT review_status FROM case_memories WHERE id = :id"),
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


async def _insert_runtime_run(
    session: AsyncSession,
    seeded_session: dict,
    *,
    thread_id: str,
) -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="case memory lifecycle",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _runtime_candidate(
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    marker: str,
    source_event_id: str | None = None,
    expires_at: datetime | None = None,
    summary: str = "Exact identity case-memory candidate.",
) -> CaseMemoryWriteCandidate:
    case_id = seeded_session["refund_case"].id
    return CaseMemoryWriteCandidate(
        tenant_id=seeded_session["tenant"].id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(case_id),
        case_type="refund_dispute",
        summary=summary,
        excerpt="Reviewed precedent context only.",
        applicability="Comparable refund cases.",
        outcome="Support completed the review.",
        caveats="Not policy or action authority.",
        source_type="llm_candidate",
        source_ref={
            "source_type": "llm_candidate",
            "run_id": str(run_id),
            "agent_run_id": str(run_id),
            "event_id": source_event_id or f"case-memory:{marker}",
            "business_object_type": "refund_case",
            "business_object_id": str(case_id),
            "outcome_id": f"outcome:{marker}",
        },
        pii_classification="none",
        expires_at=expires_at,
    )


async def _claim_for_memory(session: AsyncSession, memory_id: uuid.UUID) -> CaseMemoryIdentityClaim:
    claim = (
        await session.execute(
            select(CaseMemoryIdentityClaim).where(CaseMemoryIdentityClaim.owner_case_memory_id == memory_id)
        )
    ).scalar_one()
    return claim


@pytest.mark.asyncio
async def test_pending_expiry_terminalizes_claim_and_emits_one_transition(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    run_id = await _insert_runtime_run(session, seeded_session, thread_id="case-memory-expiry")
    service = CaseMemoryService(CaseMemoryRepository(session))
    written = await service.submit_case_memory_candidate(
        _runtime_candidate(
            seeded_session,
            run_id=run_id,
            marker="expiry",
            expires_at=now + timedelta(seconds=1),
        ),
        now=now,
    )

    pending = await service.list_pending_review(
        tenant_id=seeded_session["tenant"].id,
        now=now + timedelta(seconds=2),
    )
    row = await session.get(CaseMemory, written.memory_id)
    claim = await _claim_for_memory(session, written.memory_id)
    expiry_events = list(
        (
            await session.execute(
                select(MemoryWriteEvent).where(
                    MemoryWriteEvent.memory_id == written.memory_id,
                    MemoryWriteEvent.reason_code == "pending_review_expired",
                )
            )
        ).scalars()
    )

    assert pending == []
    assert row is not None
    assert row.review_status == "superseded"
    assert row.lifecycle_version == 2
    assert claim.claim_state == "terminal"
    assert claim.terminal_status == "superseded"
    assert claim.terminal_reason == "pending_review_expired"
    assert claim.lifecycle_version == 2
    assert len(expiry_events) == 1


@pytest.mark.asyncio
async def test_review_cas_is_single_winner_and_exact_retry_reuses_event(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_runtime_run(session, seeded_session, thread_id="case-memory-review-cas")
    service = CaseMemoryService(CaseMemoryRepository(session))
    written = await service.submit_case_memory_candidate(
        _runtime_candidate(seeded_session, run_id=run_id, marker="review-cas")
    )
    reviewer = seeded_session["users"]["admin_user"]
    decision = CaseMemoryReviewDecision(
        tenant_id=seeded_session["tenant"].id,
        run_id=run_id,
        case_memory_id=written.memory_id,
        reviewer_user_id=reviewer.id,
        expected_lifecycle_version=1,
        reason_code="approved",
        review_reason="exact provenance approved",
    )

    first_event = await service.approve_case_memory(decision)
    retry_event = await service.approve_case_memory(decision)
    row = await session.get(CaseMemory, written.memory_id)
    claim = await _claim_for_memory(session, written.memory_id)
    event_count = await session.scalar(
        select(func.count())
        .select_from(MemoryWriteEvent)
        .where(
            MemoryWriteEvent.memory_id == written.memory_id,
            MemoryWriteEvent.reason_code == "approved",
        )
    )
    with pytest.raises(ValueError, match="case memory conflict"):
        await service.reject_case_memory(
            decision.model_copy(update={"reason_code": "rejected", "review_reason": "competing rejection"})
        )

    assert row is not None
    assert row.review_status == "approved"
    assert row.lifecycle_version == 2
    assert claim.claim_state == "active"
    assert claim.lifecycle_version == 2
    assert retry_event.id == first_event.id
    assert event_count == 1


@pytest.mark.asyncio
async def test_equal_content_with_distinct_source_identity_is_not_idempotent(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_runtime_run(session, seeded_session, thread_id="case-memory-source-distinct")
    service = CaseMemoryService(CaseMemoryRepository(session))
    first = await service.submit_case_memory_candidate(
        _runtime_candidate(
            seeded_session,
            run_id=run_id,
            marker="source-a",
            source_event_id="source-a",
        )
    )
    second = await service.submit_case_memory_candidate(
        _runtime_candidate(
            seeded_session,
            run_id=run_id,
            marker="source-b",
            source_event_id="source-b",
        )
    )
    claims = list((await session.execute(select(CaseMemoryIdentityClaim))).scalars())

    assert first.status == second.status == "needs_review"
    assert first.memory_id != second.memory_id
    assert first.content_hash == second.content_hash
    assert first.source_identity_hash != second.source_identity_hash
    assert len(claims) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "terminal_status"),
    [("delete", "deleted"), ("forget", "tombstoned")],
)
async def test_terminal_delete_or_tombstone_retains_claim_and_blocks_delayed_submit(
    session: AsyncSession,
    seeded_session: dict,
    action: str,
    terminal_status: str,
) -> None:
    run_id = await _insert_runtime_run(session, seeded_session, thread_id=f"case-memory-{action}")
    service = CaseMemoryService(CaseMemoryRepository(session))
    candidate = _runtime_candidate(seeded_session, run_id=run_id, marker=action)
    written = await service.submit_case_memory_candidate(candidate)
    transition = service.delete_case_memory if action == "delete" else service.forget_case_memory

    await transition(
        tenant_id=candidate.tenant_id,
        case_memory_id=written.memory_id,
        run_id=run_id,
        expected_lifecycle_version=1,
        reason_code=f"case_{action}",
    )
    delayed = await service.submit_case_memory_candidate(candidate)
    claim = await _claim_for_memory(session, written.memory_id)
    tombstones = list(
        (
            await session.execute(select(MemoryTombstone).where(MemoryTombstone.tenant_id == candidate.tenant_id))
        ).scalars()
    )
    rows = list(
        (
            await session.execute(
                select(CaseMemory).where(
                    CaseMemory.candidate_hash == written.candidate_hash,
                    CaseMemory.tenant_id == candidate.tenant_id,
                )
            )
        ).scalars()
    )

    assert delayed.status == "error"
    assert delayed.memory_id is None
    assert delayed.reason_code == "identity_conflict"
    assert claim.claim_state == "terminal"
    assert claim.terminal_status == terminal_status
    assert len(tombstones) == 1
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_correction_terminalizes_old_claim_and_records_direct_and_association_lineage(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    run_id = await _insert_runtime_run(session, seeded_session, thread_id="case-memory-correction")
    service = CaseMemoryService(CaseMemoryRepository(session))
    written = await service.submit_case_memory_candidate(
        _runtime_candidate(seeded_session, run_id=run_id, marker="correction-old")
    )
    reviewer = seeded_session["users"]["admin_user"]
    correction = memory_schemas.CaseMemoryCorrection(
        tenant_id=seeded_session["tenant"].id,
        run_id=run_id,
        case_memory_id=written.memory_id,
        reviewer_user_id=reviewer.id,
        expected_lifecycle_version=1,
        reason_code="corrected",
        review_reason="corrected after source review",
        summary="Corrected exact identity case-memory candidate.",
        excerpt="Corrected reviewed precedent context only.",
    )

    event = await service.correct_case_memory(correction)
    old_row = await session.get(CaseMemory, written.memory_id)
    new_row = await session.get(CaseMemory, event.memory_id)
    old_claim = await _claim_for_memory(session, written.memory_id)
    new_claim = await _claim_for_memory(session, event.memory_id)
    links = list(
        (
            await session.execute(
                select(CaseMemoryLineageLink).where(CaseMemoryLineageLink.survivor_case_memory_id == event.memory_id)
            )
        ).scalars()
    )

    assert old_row is not None and new_row is not None
    assert old_row.review_status == "superseded"
    assert old_claim.claim_state == "terminal"
    assert old_claim.terminal_status == "superseded"
    assert new_claim.claim_state == "active"
    assert new_claim.candidate_hash != old_claim.candidate_hash
    assert new_row.corrects_case_memory_id == old_row.id
    assert new_row.supersedes_case_memory_id == old_row.id
    assert [(link.related_case_memory_id, link.relation, link.ordinal) for link in links] == [
        (old_row.id, "correction", 1)
    ]
