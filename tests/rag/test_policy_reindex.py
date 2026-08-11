from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    DocumentBlock,
    PolicyChunk,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocument,
    Tenant,
)
from src.rag.parsers.base import ParsedBlock
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.policy_reindex import (
    POLICY_REINDEX_STATES,
    FreshProviderParityClaimV1,
    PolicyReindexClaimRequest,
    PolicyReindexError,
    PolicyReindexFailureCode,
    PolicyReindexService,
)
from src.repositories.document_block_repo import build_canonical_document_content
from src.repositories.evidence_version_repo import EvidenceVersionRepository


NOW = datetime(2026, 8, 11, 8, 30, tzinfo=UTC)
TOKEN_CONFIG_FINGERPRINT = "sha256:" + "1" * 64
PARITY_REPORT_HASH = "sha256:" + "2" * 64


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
    assert candidate.validation_proof_json["complete_document_coverage"] is True
    assert candidate.validation_proof_json["complete_block_coverage"] is True
    assert candidate.validation_proof_json["immutable_binding_replay"] is True
    assert candidate.validation_proof_json["all_embedding_inputs_within_512_tokens"] is True
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
