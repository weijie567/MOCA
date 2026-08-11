from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    Base,
    EvidenceIdentityRollout,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocument,
    PolicyDocumentVersion,
    Tenant,
)
from src.knowledge.evidence_identity import (
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
)
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import KnowledgeContext
from src.knowledge.service import PolicyKnowledgeService
from src.rag.ingestion import CharacterCompatibilityAssembler, IngestionService
from src.repositories.evidence_version_repo import (
    EvidenceVersionRepository,
    RolloutEpochMismatch,
)

MIGRATION_026 = Path("src/db/migrations/versions/026_phase64_2_evidence_cutover.py")


class _EmbeddingService:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1024 for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [0.0] * 1024


def _write_policy(path: Path, body: str) -> Path:
    source = path / "refund_policy.md"
    source.write_text(f"# 退款政策\n\n{body}\n", encoding="utf-8")
    return source


def _metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "doc_key": "refund_policy",
        "title": "退款政策",
        "doc_type": "refund_rule",
        "risk_level": "high",
    }
    metadata.update(overrides)
    return metadata


async def _seed_inactive_rollout(session) -> UUID:
    tenant_id = uuid4()
    await session.execute(text("CREATE SEQUENCE IF NOT EXISTS evidence_ingestion_write_seq"))
    await session.execute(text("ALTER SEQUENCE evidence_ingestion_write_seq RESTART WITH 1"))
    session.add(Tenant(id=tenant_id, name=f"phase64-2-{tenant_id}", status="active"))
    session.add(EvidenceIdentityRollout(id=1, rollout_version=0, audit_counts_json={}))
    await session.flush()
    manifest_payload = {
        "schema_version": "policy_corpus_source_manifest.v1",
        "tenant_id": str(tenant_id),
        "documents": [],
    }
    encoded = json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest_hash = "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()
    manifest = PolicyCorpusManifestRevision(
        id=uuid4(),
        tenant_id=tenant_id,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json=manifest_payload,
        manifest_hash=manifest_hash,
        document_count=0,
        block_count=0,
        chunk_count=0,
    )
    session.add(manifest)
    await session.flush()
    assembler = CharacterCompatibilityAssembler()
    corpus = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=tenant_id,
        generation_name="character.v1",
        owner_marker="test.phase64_2.fixture",
        run_token=None,
        config_schema_version=assembler.config_version,
        config_json={"schema_version": assembler.config_version},
        config_fingerprint=assembler.config_fingerprint,
        provider_parity_report_hash=None,
        source_manifest_revision_id=manifest.id,
        source_manifest_hash=manifest_hash,
        source_active_corpus_version_id=None,
        source_rollout_epoch=None,
        expected_evidence_rollout_version=None,
        state="complete",
        state_version=1,
        lease_owner=None,
        lease_expires_at=None,
        next_document_index=0,
        bootstrap_counts_json={
            "bound_document_count": 0,
            "bound_block_count": 0,
            "bound_chunk_count": 0,
        },
        validation_proof_json={"fixture": "empty_character_authority"},
        terminal_at=datetime.now(UTC),
    )
    session.add(corpus)
    await session.flush()
    session.add(
        PolicyCorpusRollout(
            id=uuid4(),
            tenant_id=tenant_id,
            active_corpus_version_id=corpus.id,
            previous_corpus_version_id=None,
            rollout_epoch=1,
        )
    )
    await session.commit()
    return tenant_id


@pytest.mark.asyncio
async def test_dual_write_activation_is_cas_guarded_and_precedes_backfill(session) -> None:
    await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)

    activated = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()

    assert activated.rollout_version == 1
    assert activated.dual_write_enabled_at is not None
    assert activated.backfill_watermark_sequence is None
    assert activated.reconciled_through_sequence is None
    assert activated.canonical_reads_enabled is False
    assert activated.audit_counts_json["dual_write_health"] == "healthy"
    assert await session.scalar(select(func.count()).select_from(PolicyDocumentVersion)) == 0
    assert await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) == 0

    with pytest.raises(RolloutEpochMismatch):
        await repository.activate_dual_write(
            expected_rollout_version=0,
            health_checked_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_ingestion_allocates_one_sequence_and_reuses_unchanged_binding(session, tmp_path: Path) -> None:
    tenant_id = await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)
    rollout = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()
    service = IngestionService(session=session, embedder=_EmbeddingService(), tenant_id=tenant_id)

    source = _write_policy(tmp_path, "首次内容")
    first = await service.ingest_document(
        source,
        _metadata(),
        expected_rollout_version=rollout.rollout_version,
    )
    assert first.status == "success"
    assert first.evidence_write_sequence == 1

    first_document_version = (
        await session.execute(select(PolicyDocumentVersion).where(PolicyDocumentVersion.tenant_id == tenant_id))
    ).scalar_one()
    first_chunk_versions = list(
        (
            await session.execute(
                select(PolicyChunkVersion)
                .where(PolicyChunkVersion.tenant_id == tenant_id)
                .order_by(PolicyChunkVersion.chunk_id)
            )
        ).scalars()
    )
    first_binding = (first_document_version.id, tuple(row.id for row in first_chunk_versions))
    first_hashes = (first_document_version.content_hash, tuple(row.text_hash for row in first_chunk_versions))

    unchanged = await service.ingest_document(
        source,
        _metadata(),
        expected_rollout_version=rollout.rollout_version,
    )
    assert unchanged.status == "success"
    assert unchanged.evidence_write_sequence == 2
    assert await session.scalar(select(func.count()).select_from(PolicyDocumentVersion)) == 1
    assert await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) == len(first_chunk_versions)

    document = (await session.execute(select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id))).scalar_one()
    chunks = list((await session.execute(select(PolicyChunk).where(PolicyChunk.tenant_id == tenant_id))).scalars())
    reused_document_version = (
        await session.execute(select(PolicyDocumentVersion).where(PolicyDocumentVersion.tenant_id == tenant_id))
    ).scalar_one()
    reused_chunk_versions = list(
        (
            await session.execute(
                select(PolicyChunkVersion)
                .where(PolicyChunkVersion.tenant_id == tenant_id)
                .order_by(PolicyChunkVersion.chunk_id)
            )
        ).scalars()
    )
    assert document.evidence_write_sequence == 2
    assert {chunk.evidence_write_sequence for chunk in chunks} == {2}
    assert (reused_document_version.id, tuple(row.id for row in reused_chunk_versions)) == first_binding
    assert (reused_document_version.content_hash, tuple(row.text_hash for row in reused_chunk_versions)) == first_hashes
    assert reused_document_version.scope_type == "tenant_policy"
    assert reused_document_version.scope_id == str(tenant_id)
    assert {row.scope_type for row in reused_chunk_versions} == {"tenant_policy"}
    assert {row.scope_id for row in reused_chunk_versions} == {str(tenant_id)}


@pytest.mark.asyncio
async def test_changed_and_corrected_ingestion_link_immutable_history_and_roll_back_together(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)
    rollout = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()
    service = IngestionService(session=session, embedder=_EmbeddingService(), tenant_id=tenant_id)

    source = _write_policy(tmp_path, "首次内容")
    first = await service.ingest_document(
        source,
        _metadata(),
        expected_rollout_version=rollout.rollout_version,
    )
    assert first.evidence_write_sequence == 1
    original = (
        await session.execute(select(PolicyDocumentVersion).where(PolicyDocumentVersion.tenant_id == tenant_id))
    ).scalar_one()

    source = _write_policy(tmp_path, "修订内容")
    corrected = await service.ingest_document(
        source,
        _metadata(correction_of_document_version_id=str(original.id)),
        expected_rollout_version=rollout.rollout_version,
    )
    assert corrected.evidence_write_sequence == 2
    latest = (
        (
            await session.execute(
                select(PolicyDocumentVersion)
                .where(PolicyDocumentVersion.tenant_id == tenant_id)
                .order_by(PolicyDocumentVersion.document_version.desc())
            )
        )
        .scalars()
        .first()
    )
    assert latest is not None
    assert latest.supersedes_version_id == original.id
    assert latest.corrects_version_id == original.id

    before_document_count = await session.scalar(select(func.count()).select_from(PolicyDocumentVersion))
    before_chunk_count = await session.scalar(select(func.count()).select_from(PolicyChunkVersion))
    before_document = (
        await session.execute(select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id))
    ).scalar_one()
    before_projection = (before_document.version, before_document.content, before_document.evidence_write_sequence)

    async def fail_after_current_projection(**_: object) -> object:
        raise RuntimeError("immutable append failed")

    monkeypatch.setattr(service.evidence_repo, "append_immutable_version", fail_after_current_projection)
    source = _write_policy(tmp_path, "不得提交的内容")
    failed = await service.ingest_document(
        source,
        _metadata(),
        expected_rollout_version=rollout.rollout_version,
    )
    assert failed.status == "failed"
    assert failed.evidence_write_sequence is None
    assert await session.scalar(select(func.count()).select_from(PolicyDocumentVersion)) == before_document_count
    assert await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) == before_chunk_count
    after_document = (
        await session.execute(select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id))
    ).scalar_one()
    assert (after_document.version, after_document.content, after_document.evidence_write_sequence) == before_projection


@pytest.mark.asyncio
async def test_concurrent_changed_ingestions_serialize_under_one_rollout_epoch(test_engine, tmp_path: Path) -> None:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as setup_session:
        tenant_id = await _seed_inactive_rollout(setup_session)
        rollout = await EvidenceVersionRepository(setup_session).activate_dual_write(
            expected_rollout_version=0,
            health_checked_at=datetime.now(UTC),
        )
        await setup_session.commit()
        expected_epoch = rollout.rollout_version

    first_dir = tmp_path / "writer-one"
    second_dir = tmp_path / "writer-two"
    first_dir.mkdir()
    second_dir.mkdir()
    first_source = _write_policy(first_dir, "并发版本一")
    second_source = _write_policy(second_dir, "并发版本二")

    async def ingest(source: Path) -> int | None:
        async with session_factory() as writer_session:
            service = IngestionService(
                session=writer_session,
                embedder=_EmbeddingService(),
                tenant_id=tenant_id,
            )
            result = await service.ingest_document(
                source,
                _metadata(),
                expected_rollout_version=expected_epoch,
            )
            assert result.status == "success"
            return result.evidence_write_sequence

    sequences = await asyncio.gather(ingest(first_source), ingest(second_source))

    async with session_factory() as verify_session:
        versions = list(
            (
                await verify_session.execute(
                    select(PolicyDocumentVersion.document_version)
                    .where(PolicyDocumentVersion.tenant_id == tenant_id)
                    .order_by(PolicyDocumentVersion.document_version)
                )
            ).scalars()
        )
        rollout_version = await verify_session.scalar(
            select(EvidenceIdentityRollout.rollout_version).where(EvidenceIdentityRollout.id == 1)
        )
    assert sorted(sequences) == [1, 2]
    assert versions == [1, 2]
    assert rollout_version == expected_epoch


def test_migration_026_declares_staged_health_watermark_reconciliation_and_guarded_downgrade() -> None:
    source = MIGRATION_026.read_text(encoding="utf-8")
    normalized = " ".join(source.split()).lower()

    assert 'revision: str = "026_phase64_2_evidence_cutover"' in source
    assert 'down_revision: str | none = "025_phase64_2_immutable_evidence"' in normalized
    assert "dual_write_enabled_at is null" in normalized
    assert "dual_write_health_checked_at" in normalized
    assert "nextval('evidence_ingestion_write_seq')" in normalized
    assert "backfill_watermark_sequence" in normalized
    assert "legacy_unresolved" in normalized
    assert "reconciled_through_sequence" in normalized
    assert "canonical_reads_enabled = true" in normalized
    assert "rollout_version = rollout_version + 1" in normalized
    assert "refusing downgrade" in normalized


@pytest.mark.asyncio
async def test_unchanged_ingestions_on_both_sides_of_watermark_reconcile_by_binding_parity(
    session,
    tmp_path: Path,
) -> None:
    tenant_id = await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)
    rollout = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()
    source = _write_policy(tmp_path, "watermark 内容")
    service = IngestionService(session=session, embedder=_EmbeddingService(), tenant_id=tenant_id)
    first = await service.ingest_document(source, _metadata(), expected_rollout_version=rollout.rollout_version)
    before = await service.ingest_document(source, _metadata(), expected_rollout_version=rollout.rollout_version)
    immutable_ids = tuple(
        (
            await session.execute(
                select(PolicyChunkVersion.id)
                .where(PolicyChunkVersion.tenant_id == tenant_id)
                .order_by(PolicyChunkVersion.id)
            )
        ).scalars()
    )

    watermark = await repository.reserve_backfill_watermark(expected_rollout_version=rollout.rollout_version)
    await session.commit()
    after = await service.ingest_document(source, _metadata(), expected_rollout_version=rollout.rollout_version)
    activated = await repository.reconcile_and_enable_canonical_reads(
        expected_rollout_version=rollout.rollout_version,
    )
    await session.commit()

    final_ids = tuple(
        (
            await session.execute(
                select(PolicyChunkVersion.id)
                .where(PolicyChunkVersion.tenant_id == tenant_id)
                .order_by(PolicyChunkVersion.id)
            )
        ).scalars()
    )
    assert (first.evidence_write_sequence, before.evidence_write_sequence) == (1, 2)
    assert watermark == 3
    assert after.evidence_write_sequence == 4
    assert final_ids == immutable_ids
    assert activated.canonical_reads_enabled is True
    assert activated.reconciled_through_sequence == 4
    assert activated.audit_counts_json["binding_reused_after_watermark"] == 1
    assert activated.audit_counts_json["unresolved_count"] == 0


@pytest.mark.asyncio
async def test_writer_and_cutover_share_rollout_lock_epoch(test_engine, tmp_path: Path) -> None:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def reset_and_seed(label: str) -> tuple[UUID, int, Path]:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        async with session_factory() as setup_session:
            tenant_id = await _seed_inactive_rollout(setup_session)
            rollout = await EvidenceVersionRepository(setup_session).activate_dual_write(
                expected_rollout_version=0,
                health_checked_at=datetime.now(UTC),
            )
            await setup_session.commit()
            source_dir = tmp_path / label
            source_dir.mkdir()
            source = _write_policy(source_dir, f"{label} initial")
            service = IngestionService(
                session=setup_session,
                embedder=_EmbeddingService(),
                tenant_id=tenant_id,
            )
            initial = await service.ingest_document(
                source,
                _metadata(),
                expected_rollout_version=rollout.rollout_version,
            )
            assert initial.evidence_write_sequence == 1
            await EvidenceVersionRepository(setup_session).reserve_backfill_watermark(
                expected_rollout_version=rollout.rollout_version
            )
            await setup_session.commit()
            return tenant_id, rollout.rollout_version, source_dir

    # Activator first: it keeps the rollout lock after the final zero-gap scan,
    # so the writer cannot allocate a sequence until activation commits.
    tenant_id, epoch, source_dir = await reset_and_seed("activator-first")
    zero_gap_checked = asyncio.Event()
    release_activation = asyncio.Event()

    async def pause_after_zero_gap() -> None:
        zero_gap_checked.set()
        await release_activation.wait()

    async def activate_first() -> int:
        async with session_factory() as activation_session:
            state = await EvidenceVersionRepository(activation_session).reconcile_and_enable_canonical_reads(
                expected_rollout_version=epoch,
                after_zero_gap=pause_after_zero_gap,
            )
            await activation_session.commit()
            return state.rollout_version

    async def write_after_activation() -> object:
        async with session_factory() as writer_session:
            writer = IngestionService(
                session=writer_session,
                embedder=_EmbeddingService(),
                tenant_id=tenant_id,
            )
            changed = _write_policy(source_dir, "activator-first changed")
            return await writer.ingest_document(changed, _metadata())

    activation_task = asyncio.create_task(activate_first())
    await asyncio.wait_for(zero_gap_checked.wait(), timeout=2)
    writer_task = asyncio.create_task(write_after_activation())
    await asyncio.sleep(0.1)
    assert writer_task.done() is False
    async with test_engine.connect() as observer:
        assert await observer.scalar(text("SELECT last_value FROM evidence_ingestion_write_seq")) == 2
    release_activation.set()
    activated_epoch, writer_result = await asyncio.gather(activation_task, writer_task)
    assert activated_epoch == epoch + 1
    assert writer_result.status == "success"
    assert writer_result.rollout_version == activated_epoch
    assert writer_result.evidence_write_sequence == 3

    # Writer first: the activator waits on the same rollout row and must include
    # the committed writer sequence in its continuously locked reconciliation.
    tenant_id, epoch, source_dir = await reset_and_seed("writer-first")
    writer_has_lock = asyncio.Event()
    release_writer = asyncio.Event()

    async with session_factory() as writer_session:
        writer = IngestionService(
            session=writer_session,
            embedder=_EmbeddingService(),
            tenant_id=tenant_id,
        )
        original_allocate = writer.evidence_repo.allocate_ingestion_sequence

        async def pause_before_sequence() -> int:
            writer_has_lock.set()
            await release_writer.wait()
            return await original_allocate()

        writer.evidence_repo.allocate_ingestion_sequence = pause_before_sequence  # type: ignore[method-assign]
        changed = _write_policy(source_dir, "writer-first changed")
        held_writer = asyncio.create_task(writer.ingest_document(changed, _metadata()))
        await asyncio.wait_for(writer_has_lock.wait(), timeout=2)

        async def activate_after_writer() -> tuple[int, int | None]:
            async with session_factory() as activation_session:
                state = await EvidenceVersionRepository(activation_session).reconcile_and_enable_canonical_reads(
                    expected_rollout_version=epoch,
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
    assert writer_result.evidence_write_sequence == 3
    assert activated_epoch == epoch + 1
    assert reconciled_through == writer_result.evidence_write_sequence


@pytest.mark.asyncio
async def test_current_retrieval_is_canonical_and_fails_closed_while_operationally_disabled(
    session,
    tmp_path: Path,
) -> None:
    tenant_id = await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)
    rollout = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()
    source = _write_policy(tmp_path, "canonical current 内容")
    service = IngestionService(session=session, embedder=_EmbeddingService(), tenant_id=tenant_id)
    ingested = await service.ingest_document(
        source,
        _metadata(effective_date=date(2026, 8, 5)),
        expected_rollout_version=rollout.rollout_version,
    )
    await repository.reserve_backfill_watermark(expected_rollout_version=rollout.rollout_version)
    activated = await repository.reconcile_and_enable_canonical_reads(
        expected_rollout_version=rollout.rollout_version,
    )
    await session.commit()

    document = (await session.execute(select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id))).scalar_one()
    chunk = (await session.execute(select(PolicyChunk).where(PolicyChunk.tenant_id == tenant_id))).scalar_one()
    chunk.document = document
    engine = PolicyRetrievalEngine(session, embedder=_EmbeddingService())

    async def dense_search(**_: object) -> list[tuple[PolicyChunk, float]]:
        return [(chunk, 0.95)]

    async def empty_search(**_: object) -> list[tuple[PolicyChunk, float]]:
        return []

    engine.chunk_repo.search_similar = dense_search  # type: ignore[method-assign]
    engine.chunk_repo.search_sparse = empty_search  # type: ignore[method-assign]
    engine.chunk_repo.search_fuzzy = empty_search  # type: ignore[method-assign]
    context = KnowledgeContext(
        tenant_id=str(tenant_id),
        user_id="user-001",
        role="support",
        merchant_scope=[],
        run_id="run-001",
        trace_id="trace-001",
        effective_at="2026-08-05T00:00:00Z",
    )

    status, refs, _ = await engine.retrieve(query="退款政策", context=context, max_results=1)
    assert status == "strong_evidence"
    assert len(refs) == 1
    assert refs[0].scope_type == "tenant_policy"
    assert refs[0].scope_id == str(tenant_id)
    assert refs[0].document_version_id is not None
    assert refs[0].chunk_version_id is not None
    assert refs[0].evidence_id.startswith("sha256:")

    activated_epoch = activated.rollout_version
    disabled = await repository.disable_canonical_reads(
        expected_rollout_version=activated_epoch,
        reason="operator_gap_investigation",
    )
    await session.commit()
    assert disabled.canonical_reads_enabled is False
    assert disabled.dual_write_enabled_at is not None
    assert disabled.quarantine_reason == "operator_gap_investigation"
    disabled_epoch = disabled.rollout_version

    disabled_status, disabled_refs, _ = await engine.retrieve(query="退款政策", context=context, max_results=1)
    assert disabled_status == "error"
    assert disabled_refs == []

    changed = _write_policy(tmp_path, "canonical current disabled 期间的新内容")
    write_while_disabled = await service.ingest_document(
        changed,
        _metadata(effective_date=date(2026, 8, 5)),
        expected_rollout_version=disabled_epoch,
    )
    assert write_while_disabled.status == "success"
    assert write_while_disabled.evidence_write_sequence == (ingested.evidence_write_sequence or 0) + 2

    with pytest.raises(RolloutEpochMismatch):
        await repository.disable_canonical_reads(
            expected_rollout_version=activated_epoch,
            reason="stale_operator",
        )
    await session.rollback()

    reenabled = await repository.reconcile_and_enable_canonical_reads(
        expected_rollout_version=disabled_epoch,
    )
    await session.commit()
    assert reenabled.canonical_reads_enabled is True
    assert reenabled.quarantine_reason is None
    assert reenabled.reconciled_through_sequence == write_while_disabled.evidence_write_sequence


@pytest.mark.asyncio
async def test_current_historical_and_legacy_resolution_are_separate_and_scope_bound(
    session,
    tmp_path: Path,
) -> None:
    tenant_id = await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)
    rollout = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()
    service = IngestionService(session=session, embedder=_EmbeddingService(), tenant_id=tenant_id)
    source = _write_policy(tmp_path, "historical v1 内容")
    await service.ingest_document(source, _metadata(), expected_rollout_version=rollout.rollout_version)
    old_chunk = (
        await session.execute(
            select(PolicyChunkVersion)
            .where(PolicyChunkVersion.tenant_id == tenant_id)
            .order_by(PolicyChunkVersion.document_version)
        )
    ).scalar_one()
    old_resolution = await repository.mint_for_chunk_version(
        old_chunk,
        expected_tenant_id=tenant_id,
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert old_resolution.identity is not None
    old_identity = old_resolution.identity

    source = _write_policy(tmp_path, "historical v2 当前内容")
    await service.ingest_document(source, _metadata(), expected_rollout_version=rollout.rollout_version)
    await repository.reserve_backfill_watermark(expected_rollout_version=rollout.rollout_version)
    await repository.reconcile_and_enable_canonical_reads(expected_rollout_version=rollout.rollout_version)
    await session.commit()
    engine = PolicyRetrievalEngine(session, embedder=_EmbeddingService())
    knowledge = PolicyKnowledgeService(engine)
    old_ref = repository.evidence_ref_from_identity(
        old_identity,
        retrieved_at="2026-08-05T00:00:00Z",
    )

    current = await knowledge.validate_current_evidence(
        tenant_id=str(tenant_id),
        evidence_refs=[old_ref],
        effective_at="2026-08-05T00:00:00Z",
    )
    assert current.included == {}
    assert current.excluded[0].reason_code == "evidence_unavailable"

    historical = await knowledge.resolve_immutable_evidence(
        tenant_id=str(tenant_id),
        candidate=old_identity,
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
    )
    assert historical.identity == old_identity
    assert historical.external_reason is None

    legacy = await knowledge.resolve_legacy_alias(
        tenant_id=str(tenant_id),
        alias=f"{old_identity.doc_key}/{old_identity.chunk_id}@v{old_identity.document_version}",
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
    )
    assert legacy.identity == old_identity
    assert legacy.external_reason is None

    wrong_scope = await knowledge.resolve_immutable_evidence(
        tenant_id=str(tenant_id),
        candidate=old_identity,
        scope_type="tenant_policy",
        scope_id="merchant-001",
    )
    assert wrong_scope.identity is None
    assert wrong_scope.external_reason is not None


@pytest.mark.asyncio
async def test_verified_context_rejects_forged_immutable_ids_for_real_current_logical_head(
    session,
    tmp_path: Path,
) -> None:
    tenant_id = await _seed_inactive_rollout(session)
    repository = EvidenceVersionRepository(session)
    rollout = await repository.activate_dual_write(
        expected_rollout_version=0,
        health_checked_at=datetime.now(UTC),
    )
    await session.commit()
    source = _write_policy(tmp_path, "verified current immutable content")
    await IngestionService(session=session, embedder=_EmbeddingService(), tenant_id=tenant_id).ingest_document(
        source,
        _metadata(),
        expected_rollout_version=rollout.rollout_version,
    )
    await repository.reserve_backfill_watermark(expected_rollout_version=rollout.rollout_version)
    await repository.reconcile_and_enable_canonical_reads(expected_rollout_version=rollout.rollout_version)
    await session.commit()

    persisted = (
        await session.execute(select(PolicyChunkVersion).where(PolicyChunkVersion.tenant_id == tenant_id))
    ).scalar_one()
    forged = mint_canonical_evidence_identity(
        PersistedEvidenceIdentityMaterialV1(
            tenant_id=str(tenant_id),
            scope_type=persisted.scope_type,
            scope_id=persisted.scope_id,
            document_version_id=str(uuid4()),
            chunk_version_id=str(uuid4()),
            doc_key=persisted.doc_key,
            document_version=persisted.document_version,
            chunk_id=persisted.chunk_id,
            chunk_version=persisted.chunk_version,
            text_hash=persisted.text_hash,
        ),
        expected_tenant_id=str(tenant_id),
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert forged.identity is not None
    forged_ref = repository.evidence_ref_from_identity(
        forged.identity,
        retrieved_at="2026-08-05T00:00:00Z",
    )
    knowledge = PolicyKnowledgeService(PolicyRetrievalEngine(session, embedder=_EmbeddingService()))

    package = await knowledge.build_verified_context(
        candidate_evidence_refs=[forged_ref],
        business_fact_refs=[],
        knowledge_context=KnowledgeContext(
            tenant_id=str(tenant_id),
            user_id="phase64-2-review",
            role="support",
            run_id="run-forged-immutable-context",
            trace_id="trace-forged-immutable-context",
            effective_at="2026-08-05T00:00:00Z",
        ),
        evidence_policy={"evidence_required": True},
    )

    assert package.status == "no_evidence"
    assert package.reason_codes == ["evidence_unavailable"]
    assert package.evidence_items == []
    assert package.evidence_map == {}
    assert package.citation_map == {}
    assert package.prompt_projection["citations"] == []
    assert package.verifier_projection["safe_refs"] == []
    assert package.rejected_candidate_refs == [forged_ref]


@pytest.mark.asyncio
async def test_operational_disable_waits_for_inflight_writer_and_keeps_dual_write(
    test_engine,
    tmp_path: Path,
) -> None:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as setup_session:
        tenant_id = await _seed_inactive_rollout(setup_session)
        repository = EvidenceVersionRepository(setup_session)
        rollout = await repository.activate_dual_write(
            expected_rollout_version=0,
            health_checked_at=datetime.now(UTC),
        )
        await setup_session.commit()
        source = _write_policy(tmp_path, "disable race initial")
        initial = await IngestionService(
            session=setup_session,
            embedder=_EmbeddingService(),
            tenant_id=tenant_id,
        ).ingest_document(source, _metadata(), expected_rollout_version=rollout.rollout_version)
        assert initial.status == "success"
        await repository.reserve_backfill_watermark(expected_rollout_version=rollout.rollout_version)
        activated = await repository.reconcile_and_enable_canonical_reads(
            expected_rollout_version=rollout.rollout_version,
        )
        await setup_session.commit()
        activated_epoch = activated.rollout_version

    writer_has_lock = asyncio.Event()
    release_writer = asyncio.Event()

    async def inflight_writer() -> object:
        async with session_factory() as writer_session:
            writer = IngestionService(
                session=writer_session,
                embedder=_EmbeddingService(),
                tenant_id=tenant_id,
            )
            original_allocate = writer.evidence_repo.allocate_ingestion_sequence

            async def pause_before_sequence() -> int:
                writer_has_lock.set()
                await release_writer.wait()
                return await original_allocate()

            writer.evidence_repo.allocate_ingestion_sequence = pause_before_sequence  # type: ignore[method-assign]
            changed = _write_policy(tmp_path, "disable race writer")
            return await writer.ingest_document(
                changed,
                _metadata(),
                expected_rollout_version=activated_epoch,
            )

    async def disable_after_writer() -> tuple[int, bool, str | None]:
        async with session_factory() as disable_session:
            state = await EvidenceVersionRepository(disable_session).disable_canonical_reads(
                expected_rollout_version=activated_epoch,
                reason="operator_gap_investigation",
            )
            await disable_session.commit()
            return state.rollout_version, state.dual_write_enabled_at is not None, state.quarantine_reason

    writer_task = asyncio.create_task(inflight_writer())
    await asyncio.wait_for(writer_has_lock.wait(), timeout=2)
    disable_task = asyncio.create_task(disable_after_writer())
    await asyncio.sleep(0.1)
    assert disable_task.done() is False
    release_writer.set()
    writer_result, (disabled_epoch, dual_write_still_on, quarantine_reason) = await asyncio.gather(
        writer_task,
        disable_task,
    )
    assert writer_result.status == "success"
    assert disabled_epoch == activated_epoch + 1
    assert dual_write_still_on is True
    assert quarantine_reason == "operator_gap_investigation"

    async with session_factory() as disabled_session:
        continued = await IngestionService(
            session=disabled_session,
            embedder=_EmbeddingService(),
            tenant_id=tenant_id,
        ).ingest_document(
            _write_policy(tmp_path, "disable race continued dual-write"),
            _metadata(),
            expected_rollout_version=disabled_epoch,
        )
        assert continued.status == "success"
        reenabled = await EvidenceVersionRepository(disabled_session).reconcile_and_enable_canonical_reads(
            expected_rollout_version=disabled_epoch,
        )
        await disabled_session.commit()
        assert reenabled.canonical_reads_enabled is True
        assert reenabled.reconciled_through_sequence == continued.evidence_write_sequence
