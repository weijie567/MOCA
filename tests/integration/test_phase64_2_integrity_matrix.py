from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import (
    CaseMemory,
    CaseMemoryIdentityClaim,
    CaseMemoryLineageLink,
    EvidenceIdentityRollout,
    PolicyDocument,
    Tenant,
)
from src.db.pre_token_corpus_models import (
    PreTokenPolicyChunkVersion as PolicyChunkVersion,
    PreTokenPolicyDocumentVersion as PolicyDocumentVersion,
)
from src.knowledge.evidence_identity import (
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
)
from src.knowledge.schemas import EvidenceRefV1
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.case_precedent import (
    ClosedCasePrecedentGenerationInput,
    _project_closed_case_candidate,
)
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextObservationV1,
)
from src.memory.fact_promotion import FactPromotionCandidateV1, promote_verified_fact
from src.memory.schemas import CaseMemoryProvenanceV1, CaseMemoryReviewDecision, MemorySourceRefV1
from src.rag.ingestion import IngestionService
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from src.tools.contracts import BusinessFactRefV1
from tests.memory.test_case_memory_provenance import _insert_run
from tests.replay.test_production_evidence_binding import (
    test_replay_resolves_retained_original_through_lifecycle_changes_and_blocks_purge as _assert_retained_replay,
)


_COVERAGE_GROUPS: dict[str, frozenset[str]] = {
    "promotion": frozenset(
        {
            "test_reviewed_memory_preserves_source_authority_through_lifecycle",
            "test_phase64_2_negative_authority_and_scope_matrix",
        }
    ),
    "identity": frozenset(
        {
            "test_phase64_2_exact_scope_serialization_storage_and_hash_material",
            "test_old_run_resolves_original_after_reingestion",
        }
    ),
    "replay": frozenset({"test_old_run_resolves_original_after_reingestion"}),
    "memory_identity": frozenset({"test_reviewed_memory_preserves_source_authority_through_lifecycle"}),
    "lifecycle": frozenset({"test_reviewed_memory_preserves_source_authority_through_lifecycle"}),
    "rollout": frozenset(
        {
            "test_staged_024_to_028_upgrade_with_dual_write_activation",
            "test_ingestion_allocates_one_sequence_and_reuses_unchanged_binding",
            "test_unchanged_ingestions_on_both_sides_of_watermark_reconcile_by_binding_parity",
            "test_writer_and_cutover_share_rollout_lock_epoch",
            "test_operational_disable_waits_for_inflight_writer_and_keeps_dual_write",
        }
    ),
    "approval": frozenset(
        {
            "test_create_persists_one_repository_canonical_evidence_list",
            "test_edit_changed_evidence_uses_one_repository_canonical_binding",
            "test_attach_info_changed_evidence_uses_one_repository_canonical_binding",
        }
    ),
    "append": frozenset(
        {
            "test_new_append_rejects_legacy_raw_input_and_mixed_forged_refs_atomically",
            "test_investigate_event_replays_exact_original_evidence",
        }
    ),
    "provenance": frozenset(
        {
            "test_staged_024_to_028_upgrade_with_dual_write_activation",
            "test_resolved_and_legacy_unresolved_provenance_cannot_impersonate_each_other",
            "test_rejected_cwc_observation_never_enters_case_memory",
            "test_migration_backfills_exact_claims_and_survivor_to_many_lineage",
        }
    ),
    "claims": frozenset(
        {
            "test_staged_024_to_028_upgrade_with_dual_write_activation",
            "test_delayed_exact_submit_cannot_revive_terminal_claim",
            "test_equal_content_with_distinct_source_identity_is_not_idempotent",
            "test_review_cas_is_single_winner_and_exact_retry_reuses_event",
        }
    ),
}


_MIGRATION_DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
_HASH_A = "sha256:" + "a" * 64
_HASH_B = "sha256:" + "b" * 64
_HASH_C = "sha256:" + "c" * 64
_HASH_D = "sha256:" + "d" * 64
_HASH_E = "sha256:" + "e" * 64


class _StagedEmbeddingService:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1024 for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [0.0] * 1024


def _migration_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", _MIGRATION_DATABASE_URL)
    config.attributes["database_url"] = _MIGRATION_DATABASE_URL
    return config


async def _reset_migration_schema() -> None:
    engine = create_async_engine(_MIGRATION_DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


def _write_staged_policy(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "refund_policy.md"
    source.write_text(f"# 退款政策\n\n{body}\n", encoding="utf-8")
    return source


def _staged_metadata() -> dict[str, object]:
    return {
        "doc_key": "phase64_2_staged_refund_policy",
        "title": "Phase 64.2 staged refund policy",
        "doc_type": "refund_rule",
        "risk_level": "high",
    }


def build_integrity_coverage_matrix() -> dict[str, frozenset[str]]:
    """Map every locked requirement/threat/review finding to executable tests."""

    groups = {
        "SC-64.2-1": ("promotion", "provenance"),
        "SC-64.2-2": ("identity", "approval", "append"),
        "SC-64.2-3": ("identity", "replay", "rollout"),
        "SC-64.2-4": ("memory_identity", "provenance", "claims"),
        "SC-64.2-5": ("claims",),
        "T64.2-01": ("identity", "approval"),
        "T64.2-02": ("replay", "append"),
        "T64.2-03": ("identity", "provenance"),
        "T64.2-04": ("memory_identity",),
        "T64.2-05": ("claims",),
        "T64.2-06": ("claims",),
        "T64.2-07": ("promotion", "provenance"),
        "T64.2-08": ("identity", "approval", "replay", "provenance"),
        "CLAUDE-01": ("identity", "approval", "append"),
        "CLAUDE-02": ("append", "replay"),
        "CLAUDE-03": ("rollout",),
        "CLAUDE-04": ("replay", "rollout"),
        "CLAUDE-05": ("provenance",),
        "CLAUDE-06": ("promotion",),
        "CLAUDE-07": ("claims",),
        "CLAUDE-08": ("provenance", "claims"),
        "CLAUDE-09": ("provenance", "claims"),
        "CLAUDE-10": ("rollout", "replay"),
        "CLAUDE-11": ("identity", "memory_identity", "replay"),
        "CLAUDE-12": ("identity", "rollout"),
        "CLAUDE-R2-01": ("rollout",),
        "CLAUDE-R2-02": ("rollout", "append"),
        "CLAUDE-R2-03": ("approval", "provenance"),
        "CLAUDE-R2-04": ("claims", "replay"),
    }
    return {
        requirement: frozenset().union(*(_COVERAGE_GROUPS[group] for group in group_names))
        for requirement, group_names in groups.items()
    }


def _canonical_policy_ref(tenant_id: uuid.UUID, *, observed_at: datetime) -> EvidenceRefV1:
    material = PersistedEvidenceIdentityMaterialV1(
        tenant_id=str(tenant_id),
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        document_version_id=str(uuid.uuid4()),
        chunk_version_id=str(uuid.uuid4()),
        doc_key="phase64-2-integration-policy",
        document_version=2,
        chunk_id="phase64-2-integration-policy#1",
        chunk_version=1,
        text_hash=f"sha256:{'a' * 64}",
    )
    result = mint_canonical_evidence_identity(
        material,
        expected_tenant_id=str(tenant_id),
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert result.identity is not None
    return EvidenceRefV1.from_canonical_identity(
        result.identity,
        retrieved_at=observed_at.isoformat(),
        retrieval_config_version="retrieval.v3",
        rank=1,
    )


def test_phase64_2_matrix_maps_every_locked_requirement() -> None:
    matrix = build_integrity_coverage_matrix()

    assert set(matrix) == {
        *(f"SC-64.2-{index}" for index in range(1, 6)),
        *(f"T64.2-{index:02d}" for index in range(1, 9)),
        *(f"CLAUDE-{index:02d}" for index in range(1, 13)),
        *(f"CLAUDE-R2-{index:02d}" for index in range(1, 5)),
    }
    assert all(test_names for test_names in matrix.values())


def test_unresolved_cutover_remains_at_025_and_is_retryable(tmp_path: Path) -> None:
    """A failed preflight persists quarantine state without stamping revision 026."""

    tenant_id = uuid.uuid4()

    async def exercise() -> None:
        await _reset_migration_schema()
        config = _migration_config()
        engine = create_async_engine(_MIGRATION_DATABASE_URL, future=True, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await asyncio.to_thread(command.upgrade, config, "025_phase64_2_immutable_evidence")

            async with session_factory() as setup_session:
                setup_session.add(Tenant(id=tenant_id, name="phase64-2-cutover-retry", status="active"))
                await setup_session.commit()
                activated = await EvidenceVersionRepository(setup_session).activate_dual_write(
                    expected_rollout_version=0,
                    health_checked_at=datetime.now(UTC),
                )
                await setup_session.commit()
                source = _write_staged_policy(tmp_path / "cutover-retry", "retryable policy")
                result = await IngestionService(
                    session=setup_session,
                    embedder=_StagedEmbeddingService(),
                    tenant_id=tenant_id,
                ).ingest_document(
                    source,
                    _staged_metadata(),
                    expected_rollout_version=activated.rollout_version,
                )
                assert result.status == "success"
                document = (
                    await setup_session.execute(select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id))
                ).scalar_one()
                valid_fingerprint = document.policy_version_fingerprint
                document.policy_version_fingerprint = None
                await setup_session.commit()

            with pytest.raises(
                RuntimeError,
                match="canonical evidence cutover blocked: unresolved legacy heads remain",
            ):
                await asyncio.to_thread(command.upgrade, config, "026_phase64_2_evidence_cutover")

            async with engine.begin() as connection:
                assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "025_phase64_2_immutable_evidence"
                )
                rollout = (
                    await connection.execute(
                        text(
                            "SELECT canonical_reads_enabled, quarantine_reason, audit_counts_json "
                            "FROM evidence_identity_rollouts WHERE id = 1"
                        )
                    )
                ).one()
                assert rollout.canonical_reads_enabled is False
                assert rollout.quarantine_reason == "legacy_unresolved"
                assert rollout.audit_counts_json["unresolved_count"] == 1

                await connection.execute(
                    text(
                        "UPDATE policy_documents SET policy_version_fingerprint = :fingerprint "
                        "WHERE tenant_id = :tenant_id"
                    ),
                    {"fingerprint": valid_fingerprint, "tenant_id": tenant_id},
                )

            await asyncio.to_thread(command.upgrade, config, "026_phase64_2_evidence_cutover")

            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "026_phase64_2_evidence_cutover"
                )
                rollout = (
                    await connection.execute(
                        text(
                            "SELECT canonical_reads_enabled, quarantine_reason "
                            "FROM evidence_identity_rollouts WHERE id = 1"
                        )
                    )
                ).one()
                assert rollout.canonical_reads_enabled is True
                assert rollout.quarantine_reason is None
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_staged_024_to_028_upgrade_with_dual_write_activation(tmp_path: Path) -> None:
    """Exercise the deploy gate as staged migrations, never as a direct 024→028 claim."""

    tenant_id = uuid.uuid4()
    legacy_memory_id = uuid.uuid4()
    duplicate_ids = [uuid.UUID(int=value) for value in range(201, 204)]
    terminal_id = uuid.UUID(int=204)

    async def exercise() -> None:
        await _reset_migration_schema()
        config = _migration_config()
        engine = create_async_engine(_MIGRATION_DATABASE_URL, future=True, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await asyncio.to_thread(command.upgrade, config, "024_phase64_1_resume_attempt_lease")
            await asyncio.to_thread(command.upgrade, config, "025_phase64_2_immutable_evidence")

            async with session_factory() as setup_session:
                rollout = await setup_session.get(EvidenceIdentityRollout, 1)
                assert rollout is not None
                assert (
                    rollout.rollout_version,
                    rollout.dual_write_enabled_at,
                    rollout.backfill_watermark_sequence,
                    rollout.reconciled_through_sequence,
                    rollout.canonical_reads_enabled,
                    rollout.quarantine_reason,
                ) == (0, None, None, None, False, None)
                assert await setup_session.scalar(select(func.count()).select_from(PolicyDocumentVersion)) == 0
                assert await setup_session.scalar(select(func.count()).select_from(PolicyChunkVersion)) == 0

                setup_session.add(Tenant(id=tenant_id, name="phase64-2-staged", status="active"))
                await setup_session.commit()
                activated = await EvidenceVersionRepository(setup_session).activate_dual_write(
                    expected_rollout_version=0,
                    health_checked_at=datetime.now(UTC),
                )
                await setup_session.commit()
                assert activated.rollout_version == 1
                assert activated.audit_counts_json["dual_write_health"] == "healthy"

                source = _write_staged_policy(tmp_path / "pre-026", "staged immutable policy")
                writer = IngestionService(
                    session=setup_session,
                    embedder=_StagedEmbeddingService(),
                    tenant_id=tenant_id,
                )
                first = await writer.ingest_document(
                    source,
                    _staged_metadata(),
                    expected_rollout_version=activated.rollout_version,
                )
                unchanged_before = await writer.ingest_document(
                    source,
                    _staged_metadata(),
                    expected_rollout_version=activated.rollout_version,
                )
                assert (first.status, first.evidence_write_sequence) == ("success", 1)
                assert (unchanged_before.status, unchanged_before.evidence_write_sequence) == ("success", 2)
                document_versions = tuple(
                    (
                        await setup_session.execute(
                            select(PolicyDocumentVersion).where(PolicyDocumentVersion.tenant_id == tenant_id)
                        )
                    ).scalars()
                )
                chunk_versions = tuple(
                    (
                        await setup_session.execute(
                            select(PolicyChunkVersion)
                            .where(PolicyChunkVersion.tenant_id == tenant_id)
                            .order_by(PolicyChunkVersion.chunk_id)
                        )
                    ).scalars()
                )
                assert len(document_versions) == 1
                assert chunk_versions
                immutable_binding = (
                    document_versions[0].id,
                    tuple(row.id for row in chunk_versions),
                    document_versions[0].content_hash,
                    tuple(row.text_hash for row in chunk_versions),
                )
                assert document_versions[0].scope_type == "tenant_policy"
                assert document_versions[0].scope_id == str(tenant_id)
                assert {row.scope_type for row in chunk_versions} == {"tenant_policy"}
                assert {row.scope_id for row in chunk_versions} == {str(tenant_id)}

            # Migration 026 consumes the fresh health proof written by the real
            # repository owner, reserves the watermark, reconciles, and enables reads.
            await asyncio.to_thread(command.upgrade, config, "026_phase64_2_evidence_cutover")

            async with session_factory() as post_cutover_session:
                rollout = await post_cutover_session.get(EvidenceIdentityRollout, 1)
                assert rollout is not None
                assert rollout.rollout_version == 2
                assert rollout.backfill_watermark_sequence == 3
                assert rollout.reconciled_through_sequence == rollout.backfill_watermark_sequence
                assert rollout.canonical_reads_enabled is True
                assert rollout.quarantine_reason is None
                writer = IngestionService(
                    session=post_cutover_session,
                    embedder=_StagedEmbeddingService(),
                    tenant_id=tenant_id,
                )
                unchanged_after = await writer.ingest_document(
                    source,
                    _staged_metadata(),
                    expected_rollout_version=rollout.rollout_version,
                )
                assert unchanged_after.evidence_write_sequence == 4
                after_documents = tuple(
                    (
                        await post_cutover_session.execute(
                            select(PolicyDocumentVersion).where(PolicyDocumentVersion.tenant_id == tenant_id)
                        )
                    ).scalars()
                )
                after_chunks = tuple(
                    (
                        await post_cutover_session.execute(
                            select(PolicyChunkVersion)
                            .where(PolicyChunkVersion.tenant_id == tenant_id)
                            .order_by(PolicyChunkVersion.chunk_id)
                        )
                    ).scalars()
                )
                assert (
                    after_documents[0].id,
                    tuple(row.id for row in after_chunks),
                    after_documents[0].content_hash,
                    tuple(row.text_hash for row in after_chunks),
                ) == immutable_binding

            # Activator first: the zero-gap callback holds the rollout row until
            # commit, so the real writer cannot allocate its sequence early.
            zero_gap_checked = asyncio.Event()
            release_activation = asyncio.Event()

            async def pause_after_zero_gap() -> None:
                zero_gap_checked.set()
                await release_activation.wait()

            async def activate_first() -> int:
                async with session_factory() as activation_session:
                    state = await EvidenceVersionRepository(activation_session).reconcile_and_enable_canonical_reads(
                        expected_rollout_version=2,
                        after_zero_gap=pause_after_zero_gap,
                    )
                    await activation_session.commit()
                    return state.rollout_version

            async def write_after_activation() -> object:
                async with session_factory() as writer_session:
                    return await IngestionService(
                        session=writer_session,
                        embedder=_StagedEmbeddingService(),
                        tenant_id=tenant_id,
                    ).ingest_document(
                        _write_staged_policy(tmp_path / "activator-first", "activator-first changed"),
                        _staged_metadata(),
                    )

            activation_task = asyncio.create_task(activate_first())
            await asyncio.wait_for(zero_gap_checked.wait(), timeout=2)
            writer_task = asyncio.create_task(write_after_activation())
            await asyncio.sleep(0.1)
            assert writer_task.done() is False
            release_activation.set()
            activated_epoch, writer_result = await asyncio.gather(activation_task, writer_task)
            assert activated_epoch == 3
            assert writer_result.status == "success"
            assert writer_result.rollout_version == activated_epoch
            assert writer_result.evidence_write_sequence == 5

            # Writer first: the activator waits on the same row and its locked
            # reconciliation must include the writer's committed sequence.
            writer_has_lock = asyncio.Event()
            release_writer = asyncio.Event()
            async with session_factory() as writer_session:
                writer = IngestionService(
                    session=writer_session,
                    embedder=_StagedEmbeddingService(),
                    tenant_id=tenant_id,
                )
                original_allocate = writer.evidence_repo.allocate_ingestion_sequence

                async def pause_before_sequence() -> int:
                    writer_has_lock.set()
                    await release_writer.wait()
                    return await original_allocate()

                writer.evidence_repo.allocate_ingestion_sequence = pause_before_sequence  # type: ignore[method-assign]
                held_writer = asyncio.create_task(
                    writer.ingest_document(
                        _write_staged_policy(tmp_path / "writer-first", "writer-first changed"),
                        _staged_metadata(),
                        expected_rollout_version=activated_epoch,
                    )
                )
                await asyncio.wait_for(writer_has_lock.wait(), timeout=2)

                async def activate_after_writer() -> tuple[int, int | None]:
                    async with session_factory() as activation_session:
                        state = await EvidenceVersionRepository(
                            activation_session
                        ).reconcile_and_enable_canonical_reads(
                            expected_rollout_version=activated_epoch,
                        )
                        await activation_session.commit()
                        return state.rollout_version, state.reconciled_through_sequence

                waiting_activator = asyncio.create_task(activate_after_writer())
                await asyncio.sleep(0.1)
                assert waiting_activator.done() is False
                release_writer.set()
                writer_result, (activated_epoch, reconciled_through) = await asyncio.gather(
                    held_writer,
                    waiting_activator,
                )
            assert writer_result.status == "success"
            assert writer_result.evidence_write_sequence == 6
            assert activated_epoch == 4
            assert reconciled_through == writer_result.evidence_write_sequence

            async with session_factory() as rollback_session:
                repository = EvidenceVersionRepository(rollback_session)
                disabled = await repository.disable_canonical_reads(
                    expected_rollout_version=activated_epoch,
                    reason="phase64_2_staged_quarantine",
                )
                await rollback_session.commit()
                disabled_epoch = disabled.rollout_version
                assert disabled.canonical_reads_enabled is False
                assert disabled.dual_write_enabled_at is not None
                assert disabled.quarantine_reason == "phase64_2_staged_quarantine"
                continued = await IngestionService(
                    session=rollback_session,
                    embedder=_StagedEmbeddingService(),
                    tenant_id=tenant_id,
                ).ingest_document(
                    _write_staged_policy(tmp_path / "rollback", "dual-write continues while reads are disabled"),
                    _staged_metadata(),
                    expected_rollout_version=disabled_epoch,
                )
                assert continued.status == "success"
                assert continued.evidence_write_sequence == 7
                reenabled = await repository.reconcile_and_enable_canonical_reads(
                    expected_rollout_version=disabled_epoch,
                )
                await rollback_session.commit()
                assert reenabled.rollout_version == 6
                assert reenabled.canonical_reads_enabled is True
                assert reenabled.quarantine_reason is None
                assert reenabled.reconciled_through_sequence == continued.evidence_write_sequence

            async with engine.connect() as connection:
                chunk_version_id = await connection.scalar(
                    select(PolicyChunkVersion.id)
                    .where(PolicyChunkVersion.tenant_id == tenant_id)
                    .order_by(PolicyChunkVersion.document_version)
                )

            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text("DELETE FROM policy_chunk_versions WHERE id = :id"),
                        {"id": chunk_version_id},
                    )
                await transaction.rollback()

            with pytest.raises(RuntimeError, match="refusing downgrade"):
                await asyncio.to_thread(command.downgrade, config, "025_phase64_2_immutable_evidence")

            async with engine.begin() as connection:
                assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "026_phase64_2_evidence_cutover"
                )
                await connection.execute(
                    text(
                        "INSERT INTO case_memories "
                        "(id, tenant_id, scope_type, scope_id, case_type, summary, excerpt, content_hash, "
                        "policy_refs_json, source_ref_json, source_identity_hash, review_status, "
                        "pii_classification, created_at, updated_at) VALUES "
                        "(:id, :tenant_id, 'case', 'legacy-case', 'refund_dispute', 'legacy summary', "
                        "'legacy excerpt', :content_hash, '[]'::jsonb, CAST(:source_ref AS jsonb), "
                        ":source_identity_hash, 'needs_review', 'none', :created_at, :created_at)"
                    ),
                    {
                        "id": legacy_memory_id,
                        "tenant_id": tenant_id,
                        "content_hash": _HASH_A,
                        "source_identity_hash": _HASH_B,
                        "source_ref": json.dumps({"source_type": "legacy", "event_id": "legacy-event"}),
                        "created_at": datetime(2026, 8, 5, 9, 0, tzinfo=UTC),
                    },
                )

            await asyncio.to_thread(command.upgrade, config, "027_phase64_2_memory_provenance")
            async with engine.begin() as connection:
                legacy = (
                    await connection.execute(
                        text(
                            "SELECT identity_resolution_status, provenance_json, lifecycle_version "
                            "FROM case_memories WHERE id = :id"
                        ),
                        {"id": legacy_memory_id},
                    )
                ).one()
                assert legacy.identity_resolution_status == "legacy_unresolved"
                assert legacy.provenance_json["schema_version"] == ("case_memory_provenance_legacy_unresolved.v1")
                assert legacy.lifecycle_version == 1

                now = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
                run_id = uuid.uuid4()
                for ordinal, memory_id in enumerate([*duplicate_ids, terminal_id]):
                    is_terminal = memory_id == terminal_id
                    candidate_hash = _HASH_E if is_terminal else _HASH_C
                    content_hash = _HASH_D if is_terminal else _HASH_A
                    source_hash = _HASH_E if is_terminal else _HASH_B
                    provenance = {
                        "schema_version": "case_memory_provenance.v1",
                        "resolution_status": "canonical",
                        "tenant_id": str(tenant_id),
                        "scope_type": "case",
                        "scope_id": "staged-case",
                        "memory_authority_class": "contextual_only",
                        "source_authorities": [],
                        "source_run_id": str(run_id),
                        "evidence_refs": [],
                        "business_fact_refs": [],
                        "identity_algorithm_version": "memory_identity.v1",
                        "identity_profile": "nfc_selective_v2",
                        "candidate_hash": candidate_hash,
                        "content_hash": content_hash,
                        "source_identity_hash": source_hash,
                    }
                    await connection.execute(
                        text(
                            "INSERT INTO case_memories "
                            "(id, tenant_id, scope_type, scope_id, case_type, summary, excerpt, content_hash, "
                            "policy_refs_json, source_ref_json, source_identity_hash, identity_algorithm_version, "
                            "candidate_hash, identity_resolution_status, provenance_json, lifecycle_version, "
                            "review_status, pii_classification, created_at, updated_at) VALUES "
                            "(:id, :tenant_id, 'case', 'staged-case', 'refund_dispute', :summary, :excerpt, "
                            ":content_hash, '[]'::jsonb, CAST(:source_ref AS jsonb), :source_identity_hash, "
                            "'memory_identity.v1', :candidate_hash, 'canonical', CAST(:provenance AS jsonb), "
                            "1, :review_status, 'none', :created_at, :created_at)"
                        ),
                        {
                            "id": memory_id,
                            "tenant_id": tenant_id,
                            "summary": f"staged-memory-{ordinal}",
                            "excerpt": f"staged-excerpt-{ordinal}",
                            "content_hash": content_hash,
                            "source_ref": json.dumps(
                                {"source_type": "closed_case_cwc_candidate", "event_id": str(memory_id)}
                            ),
                            "source_identity_hash": source_hash,
                            "candidate_hash": candidate_hash,
                            "provenance": json.dumps(provenance),
                            "review_status": "rejected" if is_terminal else "needs_review",
                            "created_at": now.replace(second=ordinal),
                        },
                    )

            await asyncio.to_thread(command.upgrade, config, "028_phase64_2_memory_lifecycle")
            async with session_factory() as final_session:
                duplicate_rows = tuple(
                    (
                        await final_session.execute(
                            select(CaseMemory)
                            .where(CaseMemory.id.in_(duplicate_ids))
                            .order_by(CaseMemory.created_at, CaseMemory.id)
                        )
                    ).scalars()
                )
                assert duplicate_rows[0].review_status == "needs_review"
                assert [row.review_status for row in duplicate_rows[1:]] == ["superseded", "superseded"]
                lineage = tuple(
                    (
                        await final_session.execute(
                            select(CaseMemoryLineageLink)
                            .where(CaseMemoryLineageLink.survivor_case_memory_id == duplicate_ids[0])
                            .order_by(CaseMemoryLineageLink.ordinal)
                        )
                    ).scalars()
                )
                assert [row.related_case_memory_id for row in lineage] == duplicate_ids[1:]
                assert [row.ordinal for row in lineage] == [1, 2]
                claims = tuple(
                    (
                        await final_session.execute(
                            select(CaseMemoryIdentityClaim).order_by(CaseMemoryIdentityClaim.owner_case_memory_id)
                        )
                    ).scalars()
                )
                assert len(claims) == 2
                active_claim = next(row for row in claims if row.owner_case_memory_id == duplicate_ids[0])
                terminal_claim = next(row for row in claims if row.owner_case_memory_id == terminal_id)
                assert active_claim.claim_state == "active"
                assert terminal_claim.claim_state == "terminal"
                assert terminal_claim.terminal_status == "rejected"
                assert not any(row.owner_case_memory_id == legacy_memory_id for row in claims)

            with pytest.raises(RuntimeError, match="claim or lineage history is retained"):
                await asyncio.to_thread(command.downgrade, config, "027_phase64_2_memory_provenance")
        finally:
            await engine.dispose()
            await _reset_migration_schema()

    asyncio.run(exercise())


def test_phase64_2_exact_scope_serialization_storage_and_hash_material() -> None:
    tenant_id = uuid.uuid4()
    ref = _canonical_policy_ref(tenant_id, observed_at=datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    identity = ref.to_canonical_identity()

    assert identity is not None
    assert ref.model_dump(mode="json")["scope_type"] == "tenant_policy"
    assert ref.model_dump(mode="json")["scope_id"] == str(tenant_id)
    assert identity.hash_material()["scope_type"] == "tenant_policy"
    assert identity.hash_material()["scope_id"] == str(tenant_id)
    assert ref.evidence_id == identity.evidence_id


@pytest.mark.asyncio
async def test_old_run_resolves_original_after_reingestion(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    """Key link: canonical retrieval/emitter binding retains the old replay bytes."""

    await _assert_retained_replay(
        session,
        seeded_session,
    )


@pytest.mark.asyncio
async def test_reviewed_memory_preserves_source_authority_through_lifecycle(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    """Key link: typed observation promotion survives review and terminal lifecycle."""

    tenant_id = seeded_session["tenant"].id
    case_id = seeded_session["refund_case"].id
    run_id = await _insert_run(session, seeded_session, thread_id="phase64-2-integrity-memory")
    observed_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="refund_service",
        resource_type="refund_case",
        resource_id=str(case_id),
        resource_version="v9",
        data_freshness_at=observed_at,
        retrieved_at=observed_at,
    )
    evidence_ref = _canonical_policy_ref(tenant_id, observed_at=observed_at)
    source_ref = MemorySourceRefV1(
        source_type="run_auto_terminal",
        run_id=str(run_id),
        agent_run_id=str(run_id),
        event_id="phase64-2-integrity-close",
        business_object_type="refund_case",
        business_object_id=str(case_id),
    )
    business = promote_verified_fact(
        FactPromotionCandidateV1(
            tenant_id=str(tenant_id),
            summary="Refund case is closed.",
            authority_class="business_fact",
            status="success",
            completeness="complete",
            scope_result="valid",
            freshness_result="valid",
            reference_validation="valid",
            observed_at=observed_at,
            business_fact_refs=[business_ref],
        )
    )
    policy = promote_verified_fact(
        FactPromotionCandidateV1(
            tenant_id=str(tenant_id),
            summary="Canonical policy evidence applies.",
            authority_class="policy_evidence",
            status="success",
            completeness="complete",
            scope_result="valid",
            freshness_result="valid",
            reference_validation="valid",
            observed_at=observed_at,
            policy_evidence_refs=[evidence_ref],
        )
    )
    rejected_marker = "REJECTED-PHASE64-2-INTEGRATION-OBSERVATION"
    content = CaseWorkingContextContentV1(
        issue_type="refund_dispute",
        verified_facts=[
            business.to_verified_fact(source_ref=source_ref),
            policy.to_verified_fact(source_ref=source_ref),
        ],
        evidence_refs=[
            CaseWorkingContextObservationV1(
                summary=rejected_marker,
                decision="reject",
                authority_class="unknown",
                status="error",
                reason_code="unknown_authority",
                completeness="partial",
                scope_result="unknown",
                freshness_result="unknown",
                reference_validation="invalid",
                source_ref=source_ref,
                observed_at=observed_at,
            )
        ],
    )
    candidate = _project_closed_case_candidate(
        request=ClosedCasePrecedentGenerationInput(
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            closed_status="closed",
            close_event_id="phase64-2-integrity-close",
            closed_at=observed_at,
        ),
        content=content,
        cwc_row=SimpleNamespace(id=uuid.uuid4(), version=4, pii_classification="none"),
        scope_type="case",
        scope_id=str(case_id),
    )
    service = CaseMemoryService(CaseMemoryRepository(session))
    written = await service.submit_case_memory_candidate(candidate, now=observed_at)
    assert written.memory_id is not None
    row = await session.get(CaseMemory, written.memory_id)
    assert row is not None
    before = CaseMemoryProvenanceV1.model_validate(row.provenance_json)
    reviewer = seeded_session["users"]["admin_user"]

    await service.approve_case_memory(
        CaseMemoryReviewDecision(
            tenant_id=tenant_id,
            run_id=run_id,
            case_memory_id=row.id,
            reviewer_user_id=reviewer.id,
            expected_lifecycle_version=1,
            reason_code="approved",
            review_reason="source authority verified",
        ),
        now=observed_at,
    )
    await service.delete_case_memory(
        tenant_id=tenant_id,
        case_memory_id=row.id,
        run_id=run_id,
        expected_lifecycle_version=2,
        reason_code="integrity_closeout",
        now=observed_at,
    )
    await session.refresh(row)
    after = CaseMemoryProvenanceV1.model_validate(row.provenance_json)

    assert [item.source_authority_class for item in after.source_authorities] == [
        "business_fact",
        "policy_evidence",
    ]
    assert after.source_authorities == before.source_authorities
    assert after.memory_authority_class == "contextual_only"
    assert row.review_status == "deleted" and row.lifecycle_version == 3
    assert rejected_marker not in str(row.provenance_json)


def test_phase64_2_negative_authority_and_scope_matrix() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="refund_service",
        resource_type="refund_case",
        resource_id="RF-NEGATIVE",
        resource_version="v1",
        data_freshness_at=observed_at,
        retrieved_at=observed_at,
    )
    for authority, expected in (("contextual_only", "observe"), ("unknown", "reject")):
        result = promote_verified_fact(
            FactPromotionCandidateV1(
                tenant_id=str(tenant_id),
                summary="must remain non-authoritative",
                authority_class=authority,
                status="success",
                completeness="complete",
                scope_result="valid",
                freshness_result="valid",
                reference_validation="valid",
                observed_at=observed_at,
                business_fact_refs=[business_ref],
            )
        )
        assert result.decision == expected

    for status in (
        "denied",
        "unavailable",
        "stale",
        "malformed",
        "partial",
        "partial_success",
        "timeout",
        "error",
        "invalid_request",
        "invalid_response",
        "not_found",
        "legacy_unresolved",
        "conflict",
    ):
        result = promote_verified_fact(
            FactPromotionCandidateV1(
                tenant_id=str(tenant_id),
                summary=status,
                authority_class="business_fact",
                status=status,
                completeness="complete",
                scope_result="valid",
                freshness_result="valid",
                reference_validation="valid",
                observed_at=observed_at,
                business_fact_refs=[business_ref],
            )
        )
        assert result.decision != "promote"
