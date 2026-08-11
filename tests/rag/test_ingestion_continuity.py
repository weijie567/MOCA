from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusChunkBinding,
    CorpusDocumentBinding,
    EvidenceIdentityRollout,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusActivationHistory,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocumentVersion,
    Tenant,
)
from src.rag.ingestion import CharacterCompatibilityAssembler, IngestionService
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.policy_reindex import (
    FreshProviderParityClaimV1,
    ImmutableSelectionDecisionFixtureV1,
    PolicyCorpusActivationReason,
    PolicyCorpusActivationRequest,
    PolicyReindexClaimRequest,
    PolicyReindexError,
    PolicyReindexFailureCode,
    PolicyReindexRunIdentity,
    PolicyReindexService,
)


NOW = datetime(2026, 8, 11, 9, 30, tzinfo=UTC)
EVIDENCE_EPOCH = 11
PARITY_HASH = "sha256:" + "4" * 64
SELECTION_HASH = "sha256:" + "5" * 64


class _EmbeddingService:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1)] * 1024 for index, _ in enumerate(texts)]


def _manifest_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


async def _seed_empty_character_authority(
    session: AsyncSession,
) -> tuple[UUID, PolicyCorpusVersion, PolicyCorpusRollout]:
    tenant_id = uuid4()
    session.add(Tenant(id=tenant_id, name=f"continuity-{tenant_id}", status="active"))
    session.add(
        EvidenceIdentityRollout(
            id=1,
            rollout_version=EVIDENCE_EPOCH,
            dual_write_enabled_at=NOW,
            canonical_reads_enabled=True,
            canonical_reads_enabled_at=NOW,
            audit_counts_json={"dual_write_health": "healthy"},
        )
    )
    await session.flush()
    payload = {
        "schema_version": "policy_corpus_source_manifest.v1",
        "tenant_id": str(tenant_id),
        "documents": [],
    }
    manifest = PolicyCorpusManifestRevision(
        tenant_id=tenant_id,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json=payload,
        manifest_hash=_manifest_hash(payload),
        document_count=0,
        block_count=0,
        chunk_count=0,
    )
    session.add(manifest)
    await session.flush()
    assembler = CharacterCompatibilityAssembler()
    corpus = PolicyCorpusVersion(
        tenant_id=tenant_id,
        generation_name="character.v1",
        owner_marker="test.continuity.bootstrap",
        run_token=None,
        config_schema_version=assembler.config_version,
        config_json={"schema_version": assembler.config_version},
        config_fingerprint=assembler.config_fingerprint,
        provider_parity_report_hash=None,
        source_manifest_revision_id=manifest.id,
        source_manifest_hash=manifest.manifest_hash,
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
        terminal_at=NOW,
    )
    session.add(corpus)
    await session.flush()
    rollout = PolicyCorpusRollout(
        tenant_id=tenant_id,
        active_corpus_version_id=corpus.id,
        previous_corpus_version_id=None,
        rollout_epoch=1,
    )
    session.add(rollout)
    await session.commit()
    return tenant_id, corpus, rollout


def _write_policy(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "policy-a.md"
    path.write_text(f"# Policy A\n\n{body}\n", encoding="utf-8")
    return path


def _metadata() -> dict[str, object]:
    return {
        "doc_key": "policy-a",
        "title": "Policy A",
        "doc_type": "policy",
        "risk_level": "high",
    }


async def _ingest(session: AsyncSession, *, tenant_id: UUID, source: Path):
    return await IngestionService(
        session=session,
        embedder=_EmbeddingService(),
        tenant_id=tenant_id,
    ).ingest_document(
        source,
        _metadata(),
        expected_rollout_version=EVIDENCE_EPOCH,
    )


async def _active_rollout(session: AsyncSession, *, tenant_id: UUID) -> PolicyCorpusRollout:
    return (
        await session.execute(select(PolicyCorpusRollout).where(PolicyCorpusRollout.tenant_id == tenant_id))
    ).scalar_one()


async def _active_corpus(session: AsyncSession, *, tenant_id: UUID) -> PolicyCorpusVersion:
    rollout = await _active_rollout(session, tenant_id=tenant_id)
    corpus = await session.get(PolicyCorpusVersion, rollout.active_corpus_version_id)
    assert corpus is not None
    return corpus


async def _active_chunk_contents(session: AsyncSession, *, tenant_id: UUID) -> set[str]:
    return set(
        (
            await session.execute(
                select(PolicyChunk.content)
                .join(CorpusChunkBinding, CorpusChunkBinding.policy_chunk_id == PolicyChunk.id)
                .join(
                    PolicyCorpusRollout,
                    (PolicyCorpusRollout.tenant_id == tenant_id)
                    & (PolicyCorpusRollout.active_corpus_version_id == CorpusChunkBinding.corpus_version_id),
                )
                .where(CorpusChunkBinding.tenant_id == tenant_id)
            )
        ).scalars()
    )


async def _complete_candidate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    assembler: PolicyEmbeddingInputAssembler | CharacterCompatibilityAssembler,
    generation_name: str,
) -> tuple[PolicyReindexService, PolicyReindexRunIdentity]:
    rollout = await _active_rollout(session, tenant_id=tenant_id)
    source = await session.get(PolicyCorpusVersion, rollout.active_corpus_version_id)
    assert source is not None
    manifest = (
        await session.execute(
            select(PolicyCorpusManifestRevision)
            .where(PolicyCorpusManifestRevision.tenant_id == tenant_id)
            .order_by(PolicyCorpusManifestRevision.revision.desc())
            .limit(1)
        )
    ).scalar_one()
    config = getattr(assembler, "config", None)
    config_fingerprint = config.config_fingerprint if config is not None else assembler.config_fingerprint
    config_schema_version = config.schema_version if config is not None else assembler.config_version
    service = PolicyReindexService(session)
    owner = await service.claim(
        PolicyReindexClaimRequest(
            tenant_id=tenant_id,
            run_token=uuid4(),
            generation_name=generation_name,
            lease_owner="continuity-worker",
            lease_expires_at=NOW + timedelta(hours=1),
            config_schema_version=config_schema_version,
            config_json={"schema_version": config_schema_version},
            config_fingerprint=config_fingerprint,
            parity=FreshProviderParityClaimV1(
                report_hash=PARITY_HASH,
                config_fingerprint=config_fingerprint,
                captured_at=NOW - timedelta(minutes=1),
                status="passed",
            ),
            source_manifest_revision_id=manifest.id,
            source_manifest_revision=manifest.revision,
            source_manifest_hash=manifest.manifest_hash,
            source_active_corpus_version_id=source.id,
            source_rollout_epoch=rollout.rollout_epoch,
            expected_evidence_rollout_version=EVIDENCE_EPOCH,
        ),
        now=NOW,
    )
    current = await service.resume(owner, now=NOW)
    while current.state == "building":
        current = await service.build_next_document(
            current,
            assembler=assembler,
            embedder=_EmbeddingService(),
            now=NOW,
        )
    assert current.state == "built"
    complete = await service.validate_candidate(current, assembler=assembler, now=NOW)
    return service, complete


def _selection(owner: PolicyReindexRunIdentity) -> ImmutableSelectionDecisionFixtureV1:
    return ImmutableSelectionDecisionFixtureV1(
        schema_version="rag_token_chunk_selection_fixture.v1",
        selection_decision_sha256=SELECTION_HASH,
        outcome="selected_pass",
        tenant_id=owner.tenant_id,
        candidate_corpus_version_id=owner.corpus_version_id,
        run_token=owner.run_token,
        lease_owner=owner.lease_owner,
        config_fingerprint=owner.config_fingerprint,
        provider_parity_report_hash=owner.provider_parity_report_hash,
        source_manifest_hash=owner.source_manifest_hash,
        expected_evidence_rollout_version=owner.expected_evidence_rollout_version,
    )


async def _activate_selected(
    service: PolicyReindexService,
    owner: PolicyReindexRunIdentity,
    *,
    session: AsyncSession,
) -> None:
    rollout = await _active_rollout(session, tenant_id=owner.tenant_id)
    await service.activate_corpus(
        PolicyCorpusActivationRequest(
            tenant_id=owner.tenant_id,
            target_corpus_version_id=owner.corpus_version_id,
            expected_active_corpus_version_id=rollout.active_corpus_version_id,
            expected_rollout_epoch=rollout.rollout_epoch,
            expected_evidence_rollout_version=EVIDENCE_EPOCH,
            actor="operator.continuity.fixture",
            reason=PolicyCorpusActivationReason.SELECTED_CUTOVER,
            selection=_selection(owner),
        ),
        now=NOW,
    )


@pytest.mark.asyncio
async def test_create_update_delete_use_cow_and_retain_all_prior_projection_and_evidence(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    tenant_id, bootstrap, _ = await _seed_empty_character_authority(session)
    first = await _ingest(
        session,
        tenant_id=tenant_id,
        source=_write_policy(tmp_path / "first", "first authoritative content"),
    )
    assert first.status == "success"
    rollout = await _active_rollout(session, tenant_id=tenant_id)
    assert rollout.rollout_epoch == 2
    assert rollout.active_corpus_version_id != bootstrap.id
    await session.refresh(bootstrap)
    assert bootstrap.state == "source_stale"
    assert await _active_chunk_contents(session, tenant_id=tenant_id) == {
        "Policy A",
        "first authoritative content",
    }
    first_binding_count = int(await session.scalar(select(func.count()).select_from(CorpusChunkBinding)) or 0)

    changed = await _ingest(
        session,
        tenant_id=tenant_id,
        source=_write_policy(tmp_path / "changed", "changed authoritative content"),
    )
    assert changed.status == "success"
    rollout = await _active_rollout(session, tenant_id=tenant_id)
    assert rollout.rollout_epoch == 3
    assert await _active_chunk_contents(session, tenant_id=tenant_id) == {
        "Policy A",
        "changed authoritative content",
    }
    assert int(await session.scalar(select(func.count()).select_from(CorpusChunkBinding)) or 0) > first_binding_count
    assert await session.scalar(select(func.count()).select_from(PolicyDocumentVersion)) == 2
    assert await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) == 4

    evidence_before_delete = int(await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) or 0)
    deleted = await IngestionService(
        session=session,
        embedder=_EmbeddingService(),
        tenant_id=tenant_id,
    ).delete_document("policy-a", expected_rollout_version=EVIDENCE_EPOCH)
    assert deleted.status == "success"
    rollout = await _active_rollout(session, tenant_id=tenant_id)
    assert rollout.rollout_epoch == 4
    assert await _active_chunk_contents(session, tenant_id=tenant_id) == set()
    assert (
        await session.scalar(
            select(func.count())
            .select_from(CorpusDocumentBinding)
            .where(CorpusDocumentBinding.corpus_version_id == rollout.active_corpus_version_id)
        )
        == 0
    )
    assert (
        int(await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) or 0) == evidence_before_delete
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(PolicyCorpusActivationHistory)
            .where(PolicyCorpusActivationHistory.tenant_id == tenant_id)
        )
        == 3
    )


@pytest.mark.asyncio
async def test_unselected_complete_candidate_never_activates_and_becomes_source_stale(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    tenant_id, _, _ = await _seed_empty_character_authority(session)
    assert (
        await _ingest(
            session,
            tenant_id=tenant_id,
            source=_write_policy(tmp_path / "source", "candidate source"),
        )
    ).status == "success"
    _, candidate = await _complete_candidate(
        session,
        tenant_id=tenant_id,
        assembler=PolicyEmbeddingInputAssembler(),
        generation_name=f"token.unselected:{uuid4()}",
    )
    pointer_before = await _active_rollout(session, tenant_id=tenant_id)
    assert pointer_before.active_corpus_version_id != candidate.corpus_version_id

    assert (
        await _ingest(
            session,
            tenant_id=tenant_id,
            source=_write_policy(tmp_path / "drift", "source drift after failed selection"),
        )
    ).status == "success"
    candidate_row = await session.get(PolicyCorpusVersion, candidate.corpus_version_id)
    assert candidate_row is not None
    assert candidate_row.state == "source_stale"
    active = await _active_corpus(session, tenant_id=tenant_id)
    assert active.config_schema_version == CharacterCompatibilityAssembler.config_version


@pytest.mark.asyncio
async def test_post_token_ingestion_refuses_obsolete_rollback_then_rebuilds_current_source_under_prior_config(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    tenant_id, _, _ = await _seed_empty_character_authority(session)
    assert (
        await _ingest(
            session,
            tenant_id=tenant_id,
            source=_write_policy(tmp_path / "character", "character active source"),
        )
    ).status == "success"
    service, token = await _complete_candidate(
        session,
        tenant_id=tenant_id,
        assembler=PolicyEmbeddingInputAssembler(),
        generation_name=f"token.selected:{uuid4()}",
    )
    await _activate_selected(service, token, session=session)
    assert (await _active_rollout(session, tenant_id=tenant_id)).active_corpus_version_id == token.corpus_version_id

    assert (
        await _ingest(
            session,
            tenant_id=tenant_id,
            source=_write_policy(tmp_path / "token", "token post-cutover source"),
        )
    ).status == "success"
    token_row = await session.get(PolicyCorpusVersion, token.corpus_version_id)
    assert token_row is not None
    assert token_row.state == "source_stale"
    active_token_cow = await _active_corpus(session, tenant_id=tenant_id)
    assert active_token_cow.config_fingerprint == PolicyEmbeddingInputAssembler().config.config_fingerprint
    assert {
        value
        for value in (
            await session.execute(
                select(PolicyChunk.chunking_config_fingerprint)
                .join(CorpusChunkBinding, CorpusChunkBinding.policy_chunk_id == PolicyChunk.id)
                .where(CorpusChunkBinding.corpus_version_id == active_token_cow.id)
            )
        ).scalars()
    } == {active_token_cow.config_fingerprint}

    rollout = await _active_rollout(session, tenant_id=tenant_id)
    with pytest.raises(PolicyReindexError) as obsolete:
        await service.activate_corpus(
            PolicyCorpusActivationRequest(
                tenant_id=tenant_id,
                target_corpus_version_id=token.corpus_version_id,
                expected_active_corpus_version_id=rollout.active_corpus_version_id,
                expected_rollout_epoch=rollout.rollout_epoch,
                expected_evidence_rollout_version=EVIDENCE_EPOCH,
                actor="operator.obsolete.rollback",
                reason=PolicyCorpusActivationReason.ROLLBACK_PRIOR,
                selection=None,
            ),
            now=NOW,
        )
    assert obsolete.value.code is PolicyReindexFailureCode.OBSOLETE_SOURCE

    rebuild_service, rebuilt_character = await _complete_candidate(
        session,
        tenant_id=tenant_id,
        assembler=CharacterCompatibilityAssembler(),
        generation_name=f"character.rebuilt:{uuid4()}",
    )
    await _activate_selected(rebuild_service, rebuilt_character, session=session)
    rebuilt = await _active_corpus(session, tenant_id=tenant_id)
    assert rebuilt.id == rebuilt_character.corpus_version_id
    assert rebuilt.config_fingerprint == CharacterCompatibilityAssembler().config_fingerprint
    assert await _active_chunk_contents(session, tenant_id=tenant_id) == {
        "Policy A",
        "token post-cutover source",
    }

    assert (
        await _ingest(
            session,
            tenant_id=tenant_id,
            source=_write_policy(tmp_path / "post-rollback", "prior config write remains available"),
        )
    ).status == "success"
    post_rollback = await _active_corpus(session, tenant_id=tenant_id)
    assert post_rollback.config_fingerprint == CharacterCompatibilityAssembler().config_fingerprint
    assert await _active_chunk_contents(session, tenant_id=tenant_id) == {
        "Policy A",
        "prior config write remains available",
    }
