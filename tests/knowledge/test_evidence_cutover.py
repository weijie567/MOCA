from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    EvidenceIdentityRollout,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
    Tenant,
)
from src.rag.ingestion import IngestionService
from src.repositories.evidence_version_repo import (
    EvidenceVersionRepository,
    RolloutEpochMismatch,
)


class _EmbeddingService:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1024 for _ in texts]


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
