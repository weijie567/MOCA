"""Shared active character-corpus fixtures for retrieval integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusChunkBinding,
    CorpusDocumentBinding,
    PolicyChunk,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocument,
)
from src.rag.ingestion import CharacterCompatibilityAssembler
from src.repositories.evidence_version_repo import EvidenceVersionRepository


async def bind_character_corpus(session: AsyncSession, *, tenant_id: UUID) -> None:
    """Bind every current tenant policy row to one active character corpus."""

    documents = list(
        (
            await session.execute(
                select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id).order_by(PolicyDocument.doc_key)
            )
        ).scalars()
    )
    evidence = EvidenceVersionRepository(session)
    manifest_documents: list[dict[str, object]] = []
    document_bindings: list[CorpusDocumentBinding] = []
    chunk_bindings: list[CorpusChunkBinding] = []
    immutable_by_document = {}
    for sequence, document in enumerate(documents, start=1):
        chunks = list(
            (
                await session.execute(
                    select(PolicyChunk)
                    .where(PolicyChunk.tenant_id == tenant_id, PolicyChunk.doc_id == document.id)
                    .order_by(PolicyChunk.chunk_id)
                )
            ).scalars()
        )
        immutable = await evidence.find_exact_binding(
            tenant_id=tenant_id,
            document=document,
            chunks=chunks,
            fingerprint=document.policy_version_fingerprint,
        )
        if immutable is None:
            immutable = await evidence.append_immutable_version(
                tenant_id=tenant_id,
                document=document,
                chunks=chunks,
                write_sequence=sequence,
                canonical_source=None,
            )
        immutable_document, immutable_chunks = immutable
        immutable_by_document[document.id] = (immutable_document, immutable_chunks, chunks)
        manifest_documents.append(
            {
                "policy_document_id": str(document.id),
                "policy_document_version_id": str(immutable_document.id),
                "doc_key": document.doc_key,
                "document_version": int(document.version or 1),
                "source_type": document.source_type,
                "source_checksum": document.source_checksum,
                "source_block_ids": [],
                "chunk_ids": [chunk.chunk_id for chunk in chunks],
            }
        )
    manifest_payload = {
        "schema_version": "policy_corpus_source_manifest.v1",
        "tenant_id": str(tenant_id),
        "documents": manifest_documents,
    }
    encoded = json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest_hash = "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()
    manifest = PolicyCorpusManifestRevision(
        tenant_id=tenant_id,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json=manifest_payload,
        manifest_hash=manifest_hash,
        document_count=len(documents),
        block_count=0,
        chunk_count=sum(len(item[2]) for item in immutable_by_document.values()),
    )
    session.add(manifest)
    await session.flush()
    assembler = CharacterCompatibilityAssembler()
    corpus = PolicyCorpusVersion(
        tenant_id=tenant_id,
        generation_name="character.v1",
        owner_marker="test.active_character_corpus.fixture",
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
        next_document_index=len(documents),
        bootstrap_counts_json={
            "bound_document_count": len(documents),
            "bound_block_count": 0,
            "bound_chunk_count": sum(len(item[2]) for item in immutable_by_document.values()),
        },
        validation_proof_json={"fixture": "active_character_corpus"},
        terminal_at=datetime.now(UTC),
    )
    session.add(corpus)
    await session.flush()
    for document in documents:
        immutable_document, immutable_chunks, chunks = immutable_by_document[document.id]
        document_bindings.append(
            CorpusDocumentBinding(
                tenant_id=tenant_id,
                corpus_version_id=corpus.id,
                policy_document_id=document.id,
                policy_document_version_id=immutable_document.id,
            )
        )
        chunk_bindings.extend(
            CorpusChunkBinding(
                tenant_id=tenant_id,
                corpus_version_id=corpus.id,
                policy_chunk_id=chunk.id,
                policy_chunk_version_id=immutable.id,
            )
            for chunk, immutable in zip(chunks, immutable_chunks, strict=True)
        )
    session.add_all([*document_bindings, *chunk_bindings])
    session.add(
        PolicyCorpusRollout(
            tenant_id=tenant_id,
            active_corpus_version_id=corpus.id,
            previous_corpus_version_id=None,
            rollout_epoch=1,
        )
    )
    await session.flush()
