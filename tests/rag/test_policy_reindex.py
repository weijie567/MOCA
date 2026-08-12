from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    DocumentBlock,
    EvidenceIdentityRollout,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusActivationHistory,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocument,
    Tenant,
)
from src.rag.parsers.base import ParsedBlock
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.policy_reindex_artifacts import build_policy_reindex_recovery_descriptor
from src.rag.policy_reindex import (
    POLICY_REINDEX_STATES,
    FreshProviderParityClaimV1,
    ImmutableSelectionDecisionFixtureV1,
    ImmutableSelectionDecisionV1,
    PolicyCorpusActivationReason,
    PolicyCorpusActivationRequest,
    PolicyReindexClaimRequest,
    PolicyReindexError,
    PolicyReindexFailureCode,
    PolicyReindexRunIdentity,
    PolicyReindexService,
)
from src.repositories.document_block_repo import build_canonical_document_content
from src.repositories.evidence_version_repo import EvidenceVersionRepository


NOW = datetime(2026, 8, 11, 8, 30, tzinfo=UTC)
TOKEN_CONFIG_FINGERPRINT = "sha256:" + "1" * 64
PARITY_REPORT_HASH = "sha256:" + "2" * 64
SELECTION_DECISION_HASH = "sha256:" + "3" * 64


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


async def _seed_source_authority(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    doc_keys: tuple[str, ...] = ("policy-a", "policy-b"),
) -> tuple[UUID, PolicyCorpusManifestRevision, PolicyCorpusVersion, PolicyCorpusRollout]:
    resolved_tenant_id = tenant_id or uuid4()
    session.add(Tenant(id=resolved_tenant_id, name=f"tenant-{resolved_tenant_id}", status="active"))
    await session.flush()
    manifest_payload = {
        "schema_version": "policy_corpus_source_manifest.v1",
        "tenant_id": str(resolved_tenant_id),
        "documents": [
            {
                "policy_document_id": str(uuid4()),
                "policy_document_version_id": str(uuid4()),
                "doc_key": doc_key,
                "document_version": 1,
                "source_type": "markdown",
                "source_checksum": _sha256({"doc_key": doc_key}),
                "source_block_ids": [f"{doc_key}:0"],
                "chunk_ids": [f"{doc_key}_0"],
            }
            for doc_key in doc_keys
        ],
    }
    manifest = PolicyCorpusManifestRevision(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json=manifest_payload,
        manifest_hash=_sha256(manifest_payload),
        document_count=len(doc_keys),
        block_count=len(doc_keys),
        chunk_count=len(doc_keys),
    )
    source = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        generation_name="character.v1",
        owner_marker="moca.phase64_4.bootstrap",
        run_token=None,
        config_schema_version="character_compatibility.v1",
        config_json={"schema_version": "character_compatibility.v1"},
        config_fingerprint="sha256:" + "0" * 64,
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
        next_document_index=len(doc_keys),
        bootstrap_counts_json={
            "bound_document_count": 0,
            "bound_block_count": 0,
            "bound_chunk_count": 0,
        },
        validation_proof_json={},
        terminal_at=NOW,
    )
    rollout = PolicyCorpusRollout(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        active_corpus_version_id=source.id,
        previous_corpus_version_id=None,
        rollout_epoch=7,
    )
    session.add(manifest)
    await session.flush()
    session.add(source)
    await session.flush()
    session.add(rollout)
    await session.flush()
    return resolved_tenant_id, manifest, source, rollout


def _claim_request(
    *,
    tenant_id: UUID,
    manifest: PolicyCorpusManifestRevision,
    source: PolicyCorpusVersion,
    rollout: PolicyCorpusRollout,
    run_token: UUID | None = None,
    lease_owner: str = "worker-a",
    lease_expires_at: datetime = NOW + timedelta(minutes=15),
    config_fingerprint: str = TOKEN_CONFIG_FINGERPRINT,
    config_json: dict[str, object] | None = None,
) -> PolicyReindexClaimRequest:
    return PolicyReindexClaimRequest(
        tenant_id=tenant_id,
        run_token=run_token or uuid4(),
        generation_name=f"token.v1:{run_token or uuid4()}",
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        config_schema_version="embedding_tokenizer.v1",
        config_json=config_json
        or {
            "schema_version": "embedding_tokenizer.v1",
            "max_embedding_tokens": 512,
            "target_embedding_tokens": 384,
            "overlap_tokens": 48,
        },
        config_fingerprint=config_fingerprint,
        parity=FreshProviderParityClaimV1(
            report_hash=PARITY_REPORT_HASH,
            config_fingerprint=config_fingerprint,
            captured_at=NOW - timedelta(minutes=5),
            status="passed",
        ),
        source_manifest_revision_id=manifest.id,
        source_manifest_revision=manifest.revision,
        source_manifest_hash=manifest.manifest_hash,
        source_active_corpus_version_id=source.id,
        source_rollout_epoch=rollout.rollout_epoch,
        expected_evidence_rollout_version=11,
    )


def _parsed_block(doc_key: str, *, block_index: int = 0, text: str | None = None) -> ParsedBlock:
    resolved_text = text or f"{doc_key} authoritative database policy text"
    return ParsedBlock(
        source_block_id=f"{doc_key}:{block_index}",
        block_index=block_index,
        block_type="paragraph",
        text=resolved_text,
        normalized_text=resolved_text,
        source_type="markdown",
        parser_name="seeded-db-snapshot",
        parser_version="1",
        page_number=block_index + 1,
        box=None,
        table_metadata={},
        ocr_metadata={},
        warnings=(),
    )


async def _seed_bound_source_authority(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    doc_keys: tuple[str, ...] = ("policy-a",),
) -> tuple[
    UUID,
    PolicyCorpusManifestRevision,
    PolicyCorpusVersion,
    PolicyCorpusRollout,
    tuple[PolicyDocument, ...],
]:
    resolved_tenant_id = tenant_id or uuid4()
    session.add(Tenant(id=resolved_tenant_id, name=f"tenant-{resolved_tenant_id}", status="active"))
    await session.flush()

    documents: list[PolicyDocument] = []
    blocks_by_document: dict[UUID, list[DocumentBlock]] = {}
    source_chunks_by_document: dict[UUID, list[PolicyChunk]] = {}
    immutable_by_document: dict[UUID, tuple[object, list[object]]] = {}
    evidence_repo = EvidenceVersionRepository(session)
    manifest_documents: list[dict[str, object]] = []
    for doc_key in doc_keys:
        parsed = (_parsed_block(doc_key),)
        canonical = build_canonical_document_content(parsed)
        document = PolicyDocument(
            id=uuid4(),
            tenant_id=resolved_tenant_id,
            doc_key=doc_key,
            doc_type="policy",
            title=f"Policy {doc_key}",
            effective_date=NOW.date(),
            risk_level="high",
            version=1,
            content=canonical.content,
            source_type="markdown",
            source_checksum=_sha256({"doc_key": doc_key, "content": canonical.content}),
            parser_metadata_json={"source": "database"},
            policy_version_fingerprint=_sha256({"doc_key": doc_key, "version": 1}),
            evidence_write_sequence=7,
        )
        session.add(document)
        await session.flush()
        block_rows = [
            DocumentBlock(
                id=uuid4(),
                tenant_id=resolved_tenant_id,
                doc_id=document.id,
                source_block_id=block.source_block_id,
                block_index=block.block_index,
                block_type=block.block_type,
                text=block.text,
                normalized_text=block.normalized_text,
                text_hash=_sha256(block.text),
                page_number=block.page_number,
                bbox_json={},
                table_metadata_json={},
                parser_metadata_json={
                    "source_type": block.source_type,
                    "parser_name": block.parser_name,
                    "parser_version": block.parser_version,
                    "warning_codes": [],
                },
                ocr_metadata_json={},
                source_uri=f"/source-files-that-must-not-be-read/{doc_key}.md",
            )
            for block in parsed
        ]
        source_chunks = [
            PolicyChunk(
                id=uuid4(),
                tenant_id=resolved_tenant_id,
                doc_id=document.id,
                chunk_id=f"{doc_key}_legacy",
                section="legacy",
                content=canonical.content,
                search_text=canonical.content,
                source_block_refs_json=[{"source_block_id": parsed[0].source_block_id}],
                ocr_metadata_json={},
                risk_level=document.risk_level,
                effective_date=document.effective_date,
                embedding=[0.0] * 1024,
                evidence_write_sequence=7,
            )
        ]
        session.add_all([*block_rows, *source_chunks])
        await session.flush()
        immutable = await evidence_repo.append_immutable_version(
            tenant_id=resolved_tenant_id,
            document=document,
            chunks=source_chunks,
            write_sequence=7,
            canonical_source=canonical,
        )
        documents.append(document)
        blocks_by_document[document.id] = block_rows
        source_chunks_by_document[document.id] = source_chunks
        immutable_by_document[document.id] = immutable
        manifest_documents.append(
            {
                "policy_document_id": str(document.id),
                "policy_document_version_id": str(immutable[0].id),
                "doc_key": doc_key,
                "document_version": 1,
                "source_type": document.source_type,
                "source_checksum": document.source_checksum,
                "source_block_ids": [block.source_block_id for block in block_rows],
                "chunk_ids": [chunk.chunk_id for chunk in source_chunks],
            }
        )

    manifest_payload = {
        "schema_version": "policy_corpus_source_manifest.v1",
        "tenant_id": str(resolved_tenant_id),
        "documents": manifest_documents,
    }
    manifest = PolicyCorpusManifestRevision(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json=manifest_payload,
        manifest_hash=_sha256(manifest_payload),
        document_count=len(documents),
        block_count=sum(len(rows) for rows in blocks_by_document.values()),
        chunk_count=sum(len(rows) for rows in source_chunks_by_document.values()),
    )
    session.add(manifest)
    await session.flush()
    source = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        generation_name="character.v1.bound",
        owner_marker="test.source-authority",
        run_token=None,
        config_schema_version="character_compatibility.v1",
        config_json={"schema_version": "character_compatibility.v1"},
        config_fingerprint="sha256:" + "0" * 64,
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
        next_document_index=len(documents),
        bootstrap_counts_json={
            "bound_document_count": len(documents),
            "bound_block_count": sum(len(rows) for rows in blocks_by_document.values()),
            "bound_chunk_count": sum(len(rows) for rows in source_chunks_by_document.values()),
        },
        validation_proof_json={},
        terminal_at=NOW,
    )
    session.add(source)
    await session.flush()
    for document in documents:
        immutable_document, immutable_chunks = immutable_by_document[document.id]
        session.add(
            CorpusDocumentBinding(
                tenant_id=resolved_tenant_id,
                corpus_version_id=source.id,
                policy_document_id=document.id,
                policy_document_version_id=immutable_document.id,
            )
        )
        session.add_all(
            [
                CorpusBlockBinding(
                    tenant_id=resolved_tenant_id,
                    corpus_version_id=source.id,
                    document_block_id=block.id,
                    policy_document_version_id=immutable_document.id,
                )
                for block in blocks_by_document[document.id]
            ]
        )
        session.add_all(
            [
                CorpusChunkBinding(
                    tenant_id=resolved_tenant_id,
                    corpus_version_id=source.id,
                    policy_chunk_id=chunk.id,
                    policy_chunk_version_id=immutable.id,
                )
                for chunk, immutable in zip(source_chunks_by_document[document.id], immutable_chunks, strict=True)
            ]
        )
    await session.flush()
    rollout = PolicyCorpusRollout(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        active_corpus_version_id=source.id,
        previous_corpus_version_id=None,
        rollout_epoch=7,
    )
    session.add(rollout)
    await session.flush()
    return resolved_tenant_id, manifest, source, rollout, tuple(documents)


class _RecordingEmbedder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(tuple(texts))
        return [[float(index + 1)] * 1024 for index, _ in enumerate(texts)]


async def _seed_evidence_rollout(session: AsyncSession, *, rollout_version: int = 11) -> None:
    if await session.get(EvidenceIdentityRollout, 1) is not None:
        return
    session.add(
        EvidenceIdentityRollout(
            id=1,
            rollout_version=rollout_version,
            dual_write_enabled_at=NOW,
            canonical_reads_enabled=True,
            canonical_reads_enabled_at=NOW,
            audit_counts_json={"dual_write_health": "healthy"},
        )
    )
    await session.flush()


async def _claim_bound_candidate(
    session: AsyncSession,
    *,
    doc_keys: tuple[str, ...] = ("policy-a",),
    tenant_id: UUID | None = None,
    lease_owner: str = "worker-a",
) -> tuple[
    PolicyReindexService,
    PolicyEmbeddingInputAssembler,
    object,
    PolicyCorpusVersion,
    PolicyCorpusRollout,
    tuple[PolicyDocument, ...],
]:
    resolved_tenant, manifest, source, rollout, documents = await _seed_bound_source_authority(
        session,
        tenant_id=tenant_id,
        doc_keys=doc_keys,
    )
    assembler = PolicyEmbeddingInputAssembler()
    service = PolicyReindexService(session)
    claimed = await service.claim(
        _claim_request(
            tenant_id=resolved_tenant,
            manifest=manifest,
            source=source,
            rollout=rollout,
            lease_owner=lease_owner,
            config_fingerprint=assembler.config.config_fingerprint,
        ),
        now=NOW,
    )
    building = await service.resume(claimed, now=NOW)
    return service, assembler, building, source, rollout, documents


async def _complete_bound_candidate(
    session: AsyncSession,
) -> tuple[
    PolicyReindexService,
    PolicyReindexRunIdentity,
    PolicyCorpusVersion,
    PolicyCorpusRollout,
]:
    await _seed_evidence_rollout(session)
    service, assembler, owner, source, rollout, _ = await _claim_bound_candidate(session)
    built = await service.build_next_document(
        owner,
        assembler=assembler,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    complete = await service.validate_candidate(built, assembler=assembler, now=NOW)
    return service, complete, source, rollout


def _selection_fixture(owner: PolicyReindexRunIdentity) -> ImmutableSelectionDecisionFixtureV1:
    return ImmutableSelectionDecisionFixtureV1(
        schema_version="rag_token_chunk_selection_fixture.v1",
        selection_decision_sha256=SELECTION_DECISION_HASH,
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


def _activation_request(
    owner: PolicyReindexRunIdentity,
    *,
    expected_active_corpus_version_id: UUID,
    expected_rollout_epoch: int,
    reason: PolicyCorpusActivationReason,
    selection: ImmutableSelectionDecisionFixtureV1 | ImmutableSelectionDecisionV1 | None,
) -> PolicyCorpusActivationRequest:
    return PolicyCorpusActivationRequest(
        tenant_id=owner.tenant_id,
        target_corpus_version_id=owner.corpus_version_id,
        expected_active_corpus_version_id=expected_active_corpus_version_id,
        expected_rollout_epoch=expected_rollout_epoch,
        expected_evidence_rollout_version=owner.expected_evidence_rollout_version,
        actor="operator.phase64_4.fixture",
        reason=reason,
        selection=selection,
    )


async def _active_chunk_ids(session: AsyncSession, *, tenant_id: UUID) -> set[str]:
    return set(
        (
            await session.execute(
                select(PolicyChunk.chunk_id)
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


@pytest.mark.asyncio
async def test_claim_seals_fixed_identity_and_keeps_active_authority_pointer_only(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    request = _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout)
    service = PolicyReindexService(session)

    owner = await service.claim(request, now=NOW)
    duplicate = await service.claim(request, now=NOW)

    assert owner == duplicate
    assert owner.state == "claimed"
    assert owner.state_version == 1
    assert owner.next_document_index == 0
    assert owner.ordered_doc_keys == ("policy-a", "policy-b")
    assert owner.config_fingerprint == TOKEN_CONFIG_FINGERPRINT
    assert owner.provider_parity_report_hash == PARITY_REPORT_HASH
    assert owner.source_manifest_revision_id == manifest.id
    assert owner.source_manifest_revision == 1
    assert owner.source_manifest_hash == manifest.manifest_hash
    assert owner.source_active_corpus_version_id == source.id
    assert owner.source_rollout_epoch == 7
    assert owner.lease_owner == "worker-a"
    assert owner.lease_expires_at == NOW + timedelta(minutes=15)
    assert POLICY_REINDEX_STATES == frozenset(
        {"claimed", "building", "built", "validating", "complete", "failed", "source_stale"}
    )
    assert "active" not in POLICY_REINDEX_STATES
    await session.refresh(rollout)
    assert rollout.active_corpus_version_id == source.id
    assert rollout.rollout_epoch == 7
    assert await session.scalar(select(func.count()).select_from(PolicyCorpusVersion)) == 2


@pytest.mark.asyncio
async def test_descriptor_bound_claim_recovers_exact_committed_identity_without_renewal_or_second_run(
    session: AsyncSession,
) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    run_token = uuid4()
    descriptor = build_policy_reindex_recovery_descriptor(
        sealed_at=NOW,
        tenant_id=tenant_id,
        run_token=run_token,
        generation_name=f"token.v1:{run_token.hex}",
        lease_owner="reviewed-worker",
        lease_expires_at=NOW + timedelta(hours=2),
        config_schema_version="embedding_tokenizer.v1",
        config_json={
            "max_embedding_tokens": 512,
            "overlap_tokens": 48,
            "target_embedding_tokens": 384,
        },
        config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
        parity_report_sha256=PARITY_REPORT_HASH,
        parity_config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
        parity_probe_fixture_sha256="sha256:" + "4" * 64,
        parity_submitted_content_sha256="sha256:" + "5" * 64,
        parity_captured_at=NOW - timedelta(minutes=5),
        parity_expires_at=NOW + timedelta(hours=23, minutes=55),
        source_manifest_revision_id=manifest.id,
        source_manifest_revision=manifest.revision,
        source_manifest_hash=manifest.manifest_hash,
        source_active_corpus_version_id=source.id,
        source_rollout_epoch=rollout.rollout_epoch,
        expected_evidence_rollout_version=11,
    )
    service = PolicyReindexService(session)

    claimed = await service.claim_from_descriptor(descriptor, now=NOW)
    await session.commit()  # Simulate a crash before the state artifact is published.
    recovered = await service.recover_identity(descriptor, now=NOW + timedelta(minutes=1))
    replayed_claim = await service.claim_from_descriptor(descriptor, now=NOW + timedelta(minutes=1))

    assert recovered == replayed_claim == claimed
    assert recovered.run_token == descriptor.run_token
    assert recovered.generation_name == descriptor.generation_name
    assert recovered.lease_owner == descriptor.lease_owner
    assert recovered.lease_expires_at == descriptor.lease_expires_at
    assert recovered.parity_expires_at == descriptor.parity_expires_at
    assert await session.scalar(select(func.count()).select_from(PolicyCorpusVersion)) == 2
    candidate = await session.get(PolicyCorpusVersion, claimed.corpus_version_id)
    assert candidate is not None
    assert candidate.state_version == 1
    assert candidate.next_document_index == 0
    assert candidate.validation_proof_json["recovery_descriptor"] == {
        "schema_version": "policy_reindex_recovery_descriptor_binding.v1",
        "descriptor_payload_sha256": descriptor.descriptor_payload_sha256,
        "parity_probe_fixture_sha256": descriptor.parity_probe_fixture_sha256,
        "parity_submitted_content_sha256": descriptor.parity_submitted_content_sha256,
    }


@pytest.mark.asyncio
async def test_recover_identity_refuses_foreign_run_and_ambiguous_rows_without_mutation(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    run_token = uuid4()
    descriptor = build_policy_reindex_recovery_descriptor(
        sealed_at=NOW,
        tenant_id=tenant_id,
        run_token=run_token,
        generation_name=f"token.v1:{run_token.hex}",
        lease_owner="reviewed-worker",
        lease_expires_at=NOW + timedelta(hours=1),
        config_schema_version="embedding_tokenizer.v1",
        config_json={"max_embedding_tokens": 512},
        config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
        parity_report_sha256=PARITY_REPORT_HASH,
        parity_config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
        parity_probe_fixture_sha256="sha256:" + "4" * 64,
        parity_submitted_content_sha256="sha256:" + "5" * 64,
        parity_captured_at=NOW - timedelta(minutes=5),
        parity_expires_at=NOW + timedelta(hours=23),
        source_manifest_revision_id=manifest.id,
        source_manifest_revision=manifest.revision,
        source_manifest_hash=manifest.manifest_hash,
        source_active_corpus_version_id=source.id,
        source_rollout_epoch=rollout.rollout_epoch,
        expected_evidence_rollout_version=11,
    )
    service = PolicyReindexService(session)
    claimed = await service.claim_from_descriptor(descriptor, now=NOW)

    foreign_run = build_policy_reindex_recovery_descriptor(
        **{
            field: getattr(descriptor, field)
            for field in descriptor.__dataclass_fields__
            if field not in {"schema_version", "descriptor_payload_sha256", "run_token", "generation_name"}
        },
        run_token=uuid4(),
        generation_name="token.v1:foreign",
    )
    with pytest.raises(PolicyReindexError) as missing:
        await service.recover_identity(foreign_run, now=NOW)
    assert missing.value.code is PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH

    row = await session.get(PolicyCorpusVersion, claimed.corpus_version_id)
    assert row is not None
    duplicate = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=row.tenant_id,
        generation_name=f"{row.generation_name}:duplicate",
        owner_marker=row.owner_marker,
        run_token=row.run_token,
        config_schema_version=row.config_schema_version,
        config_json=dict(row.config_json),
        config_fingerprint=row.config_fingerprint,
        provider_parity_report_hash=row.provider_parity_report_hash,
        source_manifest_revision_id=row.source_manifest_revision_id,
        source_manifest_hash=row.source_manifest_hash,
        source_active_corpus_version_id=row.source_active_corpus_version_id,
        source_rollout_epoch=row.source_rollout_epoch,
        expected_evidence_rollout_version=row.expected_evidence_rollout_version,
        state=row.state,
        state_version=row.state_version,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        next_document_index=row.next_document_index,
        bootstrap_counts_json=dict(row.bootstrap_counts_json),
        validation_proof_json=dict(row.validation_proof_json),
    )
    session.add(duplicate)
    await session.flush()
    with pytest.raises(PolicyReindexError) as ambiguous:
        await service.recover_identity(descriptor, now=NOW)
    assert ambiguous.value.code is PolicyReindexFailureCode.AUTHORITY_UNAVAILABLE
    assert row.state_version == duplicate.state_version == 1


@pytest.mark.asyncio
async def test_resume_and_ordered_checkpoint_use_cas_and_transaction_rollback(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    building = await service.resume(owner, now=NOW)
    assert building.state == "building"
    assert building.state_version == 2

    with pytest.raises(PolicyReindexError) as out_of_order:
        await service.checkpoint_document(building, doc_key="policy-b", now=NOW)
    assert out_of_order.value.code is PolicyReindexFailureCode.DOCUMENT_ORDER_MISMATCH

    first = await service.checkpoint_document(building, doc_key="policy-a", now=NOW)
    assert first.next_document_index == 1
    assert first.state == "building"
    with pytest.raises(PolicyReindexError) as stale:
        await service.checkpoint_document(building, doc_key="policy-a", now=NOW)
    assert stale.value.code is PolicyReindexFailureCode.CAS_CONFLICT

    await session.commit()
    try:
        async with session.begin():
            rolled_back = await service.checkpoint_document(first, doc_key="policy-b", now=NOW)
            assert rolled_back.state == "built"
            raise RuntimeError("interrupt after projection write but before transaction commit")
    except RuntimeError:
        pass
    await session.rollback()
    resumed = await service.resume(first, now=NOW)
    assert resumed.next_document_index == 1
    assert resumed.state == "building"


@pytest.mark.asyncio
async def test_resume_refuses_config_parity_owner_expiry_and_foreign_run(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    other_tenant_id, other_manifest, other_source, other_rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    other_owner = await service.claim(
        _claim_request(
            tenant_id=other_tenant_id,
            manifest=other_manifest,
            source=other_source,
            rollout=other_rollout,
            lease_owner="worker-b",
        ),
        now=NOW,
    )

    refusals = (
        (replace(owner, config_fingerprint="sha256:" + "a" * 64), PolicyReindexFailureCode.CONFIG_DRIFT),
        (
            replace(owner, provider_parity_report_hash="sha256:" + "b" * 64),
            PolicyReindexFailureCode.PARITY_DRIFT,
        ),
        (replace(owner, lease_owner="worker-b"), PolicyReindexFailureCode.LEASE_OWNER_MISMATCH),
        (replace(owner, run_token=other_owner.run_token), PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH),
        (replace(owner, tenant_id=other_tenant_id), PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH),
    )
    for drifted, expected_code in refusals:
        with pytest.raises(PolicyReindexError) as denied:
            await service.resume(drifted, now=NOW)
        assert denied.value.code is expected_code

    with pytest.raises(PolicyReindexError) as expired:
        await service.resume(owner, now=owner.lease_expires_at + timedelta(microseconds=1))
    assert expired.value.code is PolicyReindexFailureCode.LEASE_EXPIRED
    await session.refresh(source)
    await session.refresh(other_source)
    assert source.state == "complete"
    assert other_source.state == "complete"


@pytest.mark.asyncio
async def test_resume_marks_source_stale_on_manifest_or_active_pointer_epoch_drift(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    next_manifest_payload = {
        **manifest.manifest_json,
        "documents": [*manifest.manifest_json["documents"], {"doc_key": "policy-c"}],
    }
    session.add(
        PolicyCorpusManifestRevision(
            id=uuid4(),
            tenant_id=tenant_id,
            revision=2,
            manifest_schema_version="policy_corpus_source_manifest.v1",
            manifest_json=next_manifest_payload,
            manifest_hash=_sha256(next_manifest_payload),
            document_count=3,
            block_count=3,
            chunk_count=3,
        )
    )
    await session.flush()

    with pytest.raises(PolicyReindexError) as stale_manifest:
        await service.resume(owner, now=NOW)
    assert stale_manifest.value.code is PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    assert candidate.state == "source_stale"

    tenant2, manifest2, source2, rollout2 = await _seed_source_authority(session)
    owner2 = await service.claim(
        _claim_request(tenant_id=tenant2, manifest=manifest2, source=source2, rollout=rollout2),
        now=NOW,
    )
    replacement = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=tenant2,
        generation_name="character.v1.replacement",
        owner_marker="test",
        run_token=None,
        config_schema_version=source2.config_schema_version,
        config_json=source2.config_json,
        config_fingerprint=source2.config_fingerprint,
        provider_parity_report_hash=None,
        source_manifest_revision_id=manifest2.id,
        source_manifest_hash=manifest2.manifest_hash,
        source_active_corpus_version_id=None,
        source_rollout_epoch=None,
        expected_evidence_rollout_version=None,
        state="complete",
        state_version=1,
        lease_owner=None,
        lease_expires_at=None,
        next_document_index=2,
        bootstrap_counts_json={},
        validation_proof_json={},
        terminal_at=NOW,
    )
    session.add(replacement)
    await session.flush()
    rollout2.active_corpus_version_id = replacement.id
    rollout2.rollout_epoch += 1
    await session.flush()

    with pytest.raises(PolicyReindexError) as stale_pointer:
        await service.resume(owner2, now=NOW)
    assert stale_pointer.value.code is PolicyReindexFailureCode.SOURCE_POINTER_DRIFT
    candidate2 = await session.get(PolicyCorpusVersion, owner2.corpus_version_id)
    assert candidate2 is not None
    assert candidate2.state == "source_stale"


@pytest.mark.asyncio
async def test_resume_rejects_taken_lease_without_touching_other_tenant_or_run(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    other_tenant_id, other_manifest, other_source, other_rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    other = await service.claim(
        _claim_request(
            tenant_id=other_tenant_id,
            manifest=other_manifest,
            source=other_source,
            rollout=other_rollout,
            lease_owner="worker-b",
        ),
        now=NOW,
    )
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    candidate.lease_owner = "worker-takeover"
    candidate.state_version += 1
    await session.flush()

    with pytest.raises(PolicyReindexError) as denied:
        await service.resume(owner, now=NOW)
    assert denied.value.code is PolicyReindexFailureCode.LEASE_OWNER_MISMATCH
    other_candidate = await session.get(PolicyCorpusVersion, other.corpus_version_id)
    assert other_candidate is not None
    assert other_candidate.state == "claimed"
    assert other_candidate.next_document_index == 0


@pytest.mark.asyncio
async def test_candidate_build_uses_only_sealed_database_snapshot_and_stays_invisible(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, assembler, owner, source, rollout, documents = await _claim_bound_candidate(session)
    await session.commit()
    document = documents[0]
    original_content = document.content
    original_sequence = document.evidence_write_sequence
    embedder = _RecordingEmbedder()

    def _source_file_access_forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("candidate build must not read or reparse source files")

    monkeypatch.setattr("pathlib.Path.read_bytes", _source_file_access_forbidden)
    monkeypatch.setattr("pathlib.Path.read_text", _source_file_access_forbidden)
    built = await service.build_next_document(owner, assembler=assembler, embedder=embedder, now=NOW)

    assert built.state == "built"
    assert built.next_document_index == 1
    assert len(embedder.calls) == 1
    candidate_chunk_ids = set(
        (
            await session.execute(
                select(PolicyChunk.chunk_id)
                .join(CorpusChunkBinding, CorpusChunkBinding.policy_chunk_id == PolicyChunk.id)
                .where(
                    CorpusChunkBinding.tenant_id == owner.tenant_id,
                    CorpusChunkBinding.corpus_version_id == owner.corpus_version_id,
                )
            )
        ).scalars()
    )
    assert candidate_chunk_ids == {"policy-a_000"}
    active_chunk_ids = set(
        (
            await session.execute(
                select(PolicyChunk.chunk_id)
                .join(CorpusChunkBinding, CorpusChunkBinding.policy_chunk_id == PolicyChunk.id)
                .where(
                    CorpusChunkBinding.tenant_id == owner.tenant_id,
                    CorpusChunkBinding.corpus_version_id == rollout.active_corpus_version_id,
                )
            )
        ).scalars()
    )
    assert active_chunk_ids == {"policy-a_legacy"}
    await session.refresh(document)
    await session.refresh(rollout)
    assert document.content == original_content
    assert document.evidence_write_sequence == original_sequence
    assert rollout.active_corpus_version_id == source.id
    assert rollout.rollout_epoch == 7


@pytest.mark.asyncio
async def test_interrupted_candidate_build_rolls_back_then_retries_without_duplicates(
    session: AsyncSession,
) -> None:
    service, assembler, owner, _, rollout, _ = await _claim_bound_candidate(session)
    await session.commit()

    with pytest.raises(RuntimeError, match="interrupt before per-document commit"):
        async with session.begin():
            projected = await service.build_next_document(
                owner,
                assembler=assembler,
                embedder=_RecordingEmbedder(),
                now=NOW,
            )
            assert projected.next_document_index == 1
            raise RuntimeError("interrupt before per-document commit")

    assert (
        await session.scalar(
            select(func.count())
            .select_from(CorpusChunkBinding)
            .where(CorpusChunkBinding.corpus_version_id == owner.corpus_version_id)
        )
        == 0
    )
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    assert candidate.next_document_index == 0
    retried = await service.build_next_document(
        owner,
        assembler=assembler,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    assert retried.state == "built"
    assert (
        await session.scalar(
            select(func.count())
            .select_from(CorpusChunkBinding)
            .where(CorpusChunkBinding.corpus_version_id == owner.corpus_version_id)
        )
        == 1
    )
    await session.refresh(rollout)
    assert rollout.active_corpus_version_id != owner.corpus_version_id


@pytest.mark.asyncio
async def test_per_document_snapshot_recheck_rejects_mid_build_source_mutation(
    session: AsyncSession,
) -> None:
    service, assembler, owner, _, _, documents = await _claim_bound_candidate(session)
    await session.commit()
    document = documents[0]

    class _MutatingEmbedder(_RecordingEmbedder):
        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            embeddings = await super().embed_documents(texts)
            await session.execute(
                update(DocumentBlock)
                .where(DocumentBlock.tenant_id == owner.tenant_id, DocumentBlock.doc_id == document.id)
                .values(text="mutated after sealed snapshot", normalized_text="mutated after sealed snapshot")
            )
            return embeddings

    with pytest.raises(PolicyReindexError) as stale:
        async with session.begin():
            await service.build_next_document(
                owner,
                assembler=assembler,
                embedder=_MutatingEmbedder(),
                now=NOW,
            )
    assert stale.value.code is PolicyReindexFailureCode.SOURCE_SNAPSHOT_DRIFT
    assert (
        await session.scalar(
            select(func.count())
            .select_from(CorpusChunkBinding)
            .where(CorpusChunkBinding.corpus_version_id == owner.corpus_version_id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_complete_candidate_proves_coverage_deterministic_rebuild_and_immutable_replay(
    session: AsyncSession,
) -> None:
    service, assembler, owner, source, rollout, _ = await _claim_bound_candidate(
        session,
        doc_keys=("policy-a", "policy-b"),
    )
    first = await service.build_next_document(
        owner,
        assembler=assembler,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    assert first.state == "building"
    built = await service.build_next_document(
        first,
        assembler=assembler,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    assert built.state == "built"

    complete = await service.validate_candidate(built, assembler=assembler, now=NOW)

    assert complete.state == "complete"
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    assert candidate.bootstrap_counts_json == {
        "bound_document_count": 2,
        "bound_block_count": 2,
        "bound_chunk_count": 2,
    }
    assert candidate.deterministic_rebuild_hash is not None
    proof = candidate.validation_proof_json["candidate_validation"]
    assert proof["complete_document_coverage"] is True
    assert proof["complete_block_coverage"] is True
    assert proof["immutable_binding_replay"] is True
    assert proof["all_embedding_inputs_within_512_tokens"] is True
    await session.refresh(rollout)
    assert rollout.active_corpus_version_id == source.id


@pytest.mark.asyncio
async def test_cross_tenant_and_run_resume_or_rollback_cannot_clean_other_candidate(
    session: AsyncSession,
) -> None:
    service_a, assembler_a, owner_a, _, _, _ = await _claim_bound_candidate(
        session,
        lease_owner="worker-a",
    )
    service_b, assembler_b, owner_b, _, _, _ = await _claim_bound_candidate(
        session,
        lease_owner="worker-b",
    )
    built_b = await service_b.build_next_document(
        owner_b,
        assembler=assembler_b,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    await session.commit()

    with pytest.raises(RuntimeError, match="rollback run a only"):
        async with session.begin():
            await service_a.build_next_document(
                owner_a,
                assembler=assembler_a,
                embedder=_RecordingEmbedder(),
                now=NOW,
            )
            raise RuntimeError("rollback run a only")

    with pytest.raises(PolicyReindexError) as foreign_resume:
        await service_a.resume(replace(owner_a, corpus_version_id=owner_b.corpus_version_id), now=NOW)
    assert foreign_resume.value.code is PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH
    assert (
        await session.scalar(
            select(func.count())
            .select_from(CorpusChunkBinding)
            .where(CorpusChunkBinding.corpus_version_id == owner_b.corpus_version_id)
        )
        == 1
    )
    candidate_b = await session.get(PolicyCorpusVersion, owner_b.corpus_version_id)
    assert candidate_b is not None
    assert candidate_b.state == built_b.state == "built"


@pytest.mark.asyncio
async def test_fixture_cutover_rollback_and_restore_are_exactly_one_pointer_events(
    session: AsyncSession,
) -> None:
    service, owner, source, rollout = await _complete_bound_candidate(session)
    selection = _selection_fixture(owner)

    assert await _active_chunk_ids(session, tenant_id=owner.tenant_id) == {"policy-a_legacy"}
    cutover = await service.activate_corpus(
        _activation_request(
            owner,
            expected_active_corpus_version_id=source.id,
            expected_rollout_epoch=rollout.rollout_epoch,
            reason=PolicyCorpusActivationReason.SELECTED_CUTOVER,
            selection=selection,
        ),
        now=NOW,
    )
    assert cutover.active_corpus_version_id == owner.corpus_version_id
    assert cutover.previous_corpus_version_id == source.id
    assert cutover.rollout_epoch == 8
    assert await _active_chunk_ids(session, tenant_id=owner.tenant_id) == {"policy-a_000"}

    rollback_request = replace(
        _activation_request(
            owner,
            expected_active_corpus_version_id=owner.corpus_version_id,
            expected_rollout_epoch=8,
            reason=PolicyCorpusActivationReason.ROLLBACK_PRIOR,
            selection=None,
        ),
        target_corpus_version_id=source.id,
    )
    rollback = await service.activate_corpus(rollback_request, now=NOW + timedelta(seconds=1))
    assert rollback.active_corpus_version_id == source.id
    assert rollback.previous_corpus_version_id == owner.corpus_version_id
    assert rollback.rollout_epoch == 9
    assert await _active_chunk_ids(session, tenant_id=owner.tenant_id) == {"policy-a_legacy"}

    restored = await service.activate_corpus(
        _activation_request(
            owner,
            expected_active_corpus_version_id=source.id,
            expected_rollout_epoch=9,
            reason=PolicyCorpusActivationReason.RESTORE_SELECTED,
            selection=selection,
        ),
        now=NOW + timedelta(seconds=2),
    )
    assert restored.active_corpus_version_id == owner.corpus_version_id
    assert restored.previous_corpus_version_id == source.id
    assert restored.rollout_epoch == 10
    assert await _active_chunk_ids(session, tenant_id=owner.tenant_id) == {"policy-a_000"}

    rows = list(
        (
            await session.execute(
                select(PolicyCorpusActivationHistory)
                .where(PolicyCorpusActivationHistory.tenant_id == owner.tenant_id)
                .order_by(PolicyCorpusActivationHistory.rollout_epoch)
            )
        ).scalars()
    )
    assert [row.reason_code for row in rows] == [
        "selected_cutover",
        "rollback_prior",
        "restore_selected",
    ]
    assert [(row.prior_rollout_epoch, row.rollout_epoch) for row in rows] == [(7, 8), (8, 9), (9, 10)]
    assert [row.actor for row in rows] == ["operator.phase64_4.fixture"] * 3
    assert [row.selection_decision_hash for row in rows] == [
        SELECTION_DECISION_HASH,
        None,
        SELECTION_DECISION_HASH,
    ]
    assert all(row.receipt_hash is None for row in rows)
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    await session.refresh(source)
    assert candidate is not None
    assert candidate.state == source.state == "complete"


@pytest.mark.asyncio
async def test_real_selection_projection_authorizes_cutover_without_fixture_schema(
    session: AsyncSession,
) -> None:
    service, owner, source, rollout = await _complete_bound_candidate(session)
    selection = ImmutableSelectionDecisionV1(
        schema_version="rag_token_chunk_selection.v1",
        selection_decision_sha256=SELECTION_DECISION_HASH,
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

    activated = await service.activate_corpus(
        _activation_request(
            owner,
            expected_active_corpus_version_id=source.id,
            expected_rollout_epoch=rollout.rollout_epoch,
            reason=PolicyCorpusActivationReason.SELECTED_CUTOVER,
            selection=selection,
        ),
        now=NOW,
    )

    assert activated.active_corpus_version_id == owner.corpus_version_id
    history = (
        await session.execute(
            select(PolicyCorpusActivationHistory).where(
                PolicyCorpusActivationHistory.tenant_id == owner.tenant_id,
                PolicyCorpusActivationHistory.rollout_epoch == activated.rollout_epoch,
            )
        )
    ).scalar_one()
    assert history.selection_decision_hash == SELECTION_DECISION_HASH


@pytest.mark.asyncio
async def test_activation_rejects_incomplete_or_mismatched_fixture_without_pointer_or_history_mutation(
    session: AsyncSession,
) -> None:
    service, owner, source, rollout = await _complete_bound_candidate(session)
    selection = _selection_fixture(owner)
    request = _activation_request(
        owner,
        expected_active_corpus_version_id=source.id,
        expected_rollout_epoch=rollout.rollout_epoch,
        reason=PolicyCorpusActivationReason.SELECTED_CUTOVER,
        selection=selection,
    )
    invalid_selections = (
        replace(selection, tenant_id=uuid4()),
        replace(selection, run_token=uuid4()),
        replace(selection, lease_owner="foreign-worker"),
        replace(selection, provider_parity_report_hash="sha256:" + "8" * 64),
        replace(selection, config_fingerprint="sha256:" + "9" * 64),
        replace(selection, source_manifest_hash="sha256:" + "a" * 64),
        replace(selection, selection_decision_sha256="not-a-sha256"),
        replace(selection, outcome="rejected"),
    )
    for invalid in invalid_selections:
        with pytest.raises(PolicyReindexError) as denied:
            await service.activate_corpus(replace(request, selection=invalid), now=NOW)
        assert denied.value.code is PolicyReindexFailureCode.SELECTION_PROOF_INVALID

    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    candidate.validation_proof_json = {
        **candidate.validation_proof_json,
        "candidate_validation": {
            **candidate.validation_proof_json["candidate_validation"],
            "immutable_binding_replay": False,
        },
    }
    await session.flush()
    with pytest.raises(PolicyReindexError) as incomplete:
        await service.activate_corpus(request, now=NOW)
    assert incomplete.value.code is PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH
    await session.refresh(rollout)
    assert (rollout.active_corpus_version_id, rollout.rollout_epoch) == (source.id, 7)
    assert (
        await session.scalar(
            select(func.count())
            .select_from(PolicyCorpusActivationHistory)
            .where(PolicyCorpusActivationHistory.tenant_id == owner.tenant_id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_stale_activation_cas_has_no_pointer_or_history_side_effect(
    session: AsyncSession,
) -> None:
    service, owner, source, rollout = await _complete_bound_candidate(session)
    request = _activation_request(
        owner,
        expected_active_corpus_version_id=source.id,
        expected_rollout_epoch=rollout.rollout_epoch,
        reason=PolicyCorpusActivationReason.SELECTED_CUTOVER,
        selection=_selection_fixture(owner),
    )
    activated = await service.activate_corpus(request, now=NOW)
    with pytest.raises(PolicyReindexError) as stale:
        await service.activate_corpus(request, now=NOW)
    assert stale.value.code is PolicyReindexFailureCode.CAS_CONFLICT
    current = await session.get(PolicyCorpusRollout, rollout.id)
    assert current is not None
    assert (current.active_corpus_version_id, current.rollout_epoch) == (
        activated.active_corpus_version_id,
        activated.rollout_epoch,
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(PolicyCorpusActivationHistory)
            .where(PolicyCorpusActivationHistory.tenant_id == owner.tenant_id)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_concurrent_activation_cas_has_exactly_one_winner(session: AsyncSession, test_engine) -> None:
    _, owner, source, rollout = await _complete_bound_candidate(session)
    request = _activation_request(
        owner,
        expected_active_corpus_version_id=source.id,
        expected_rollout_epoch=rollout.rollout_epoch,
        reason=PolicyCorpusActivationReason.SELECTED_CUTOVER,
        selection=_selection_fixture(owner),
    )
    await session.commit()
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def activate() -> str:
        async with session_factory() as contender:
            try:
                await PolicyReindexService(contender).activate_corpus(request, now=NOW)
                await contender.commit()
                return "won"
            except PolicyReindexError as exc:
                await contender.rollback()
                return exc.code.value

    outcomes = await asyncio.gather(activate(), activate())
    assert sorted(outcomes) == [PolicyReindexFailureCode.CAS_CONFLICT.value, "won"]
    async with session_factory() as verifier:
        current = (
            await verifier.execute(select(PolicyCorpusRollout).where(PolicyCorpusRollout.tenant_id == owner.tenant_id))
        ).scalar_one()
        assert (current.active_corpus_version_id, current.rollout_epoch) == (owner.corpus_version_id, 8)
        assert (
            await verifier.scalar(
                select(func.count())
                .select_from(PolicyCorpusActivationHistory)
                .where(PolicyCorpusActivationHistory.tenant_id == owner.tenant_id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_candidate_cleanup_is_exact_identity_allowlisted_and_retains_all_evidence(
    session: AsyncSession,
) -> None:
    await _seed_evidence_rollout(session)
    service_a, assembler_a, owner_a, _, _, _ = await _claim_bound_candidate(
        session,
        lease_owner="worker-a",
    )
    service_b, assembler_b, owner_b, _, _, _ = await _claim_bound_candidate(
        session,
        lease_owner="worker-b",
    )
    built_a = await service_a.build_next_document(
        owner_a,
        assembler=assembler_a,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    built_b = await service_b.build_next_document(
        owner_b,
        assembler=assembler_b,
        embedder=_RecordingEmbedder(),
        now=NOW,
    )
    evidence_before = int(await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) or 0)
    bindings_before = int(await session.scalar(select(func.count()).select_from(CorpusChunkBinding)) or 0)

    with pytest.raises(PolicyReindexError) as foreign:
        await service_a.cleanup_candidate(
            replace(built_a, corpus_version_id=built_b.corpus_version_id),
            actor="operator.cleanup",
            now=NOW,
        )
    assert foreign.value.code is PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH

    cleaned = await service_a.cleanup_candidate(built_a, actor="operator.cleanup", now=NOW)
    assert cleaned.state == "failed"
    candidate_b = await session.get(PolicyCorpusVersion, built_b.corpus_version_id)
    assert candidate_b is not None
    assert candidate_b.state == "built"
    assert int(await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) or 0) == evidence_before
    assert int(await session.scalar(select(func.count()).select_from(CorpusChunkBinding)) or 0) == bindings_before
    assert await session.scalar(select(func.count()).select_from(PolicyCorpusActivationHistory)) == 0
