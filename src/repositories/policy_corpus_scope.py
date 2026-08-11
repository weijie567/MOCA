"""Single authority for current and explicitly scoped policy corpora.

Production repositories never accept a caller-selected corpus id.  They join
the tenant rollout pointer through the helpers in this module.  Evaluation and
reindex code may instead pass an :class:`ExactPolicyCorpusScope` whose purpose
is explicit at construction time.  Immutable evidence history remains outside
both DTOs and resolves its stored version ids directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    DocumentBlock,
    PolicyChunk,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocument,
    PolicyChunkVersion,
    PolicyDocumentVersion,
)
from src.knowledge.text_hash import evidence_text_hash


class PolicyCorpusScopeUnavailable(RuntimeError):
    """The requested tenant corpus authority cannot be proved."""


@dataclass(frozen=True, slots=True)
class ActivePolicyCorpusScope:
    """One resolved tenant rollout pointer and its immutable configuration."""

    tenant_id: UUID
    corpus_version_id: UUID
    generation_name: str
    config_schema_version: str
    config_fingerprint: str
    rollout_epoch: int

    @classmethod
    async def resolve(cls, session: AsyncSession, *, tenant_id: UUID) -> ActivePolicyCorpusScope:
        row = (
            await session.execute(
                select(PolicyCorpusRollout, PolicyCorpusVersion)
                .join(
                    PolicyCorpusVersion,
                    and_(
                        PolicyCorpusVersion.tenant_id == PolicyCorpusRollout.tenant_id,
                        PolicyCorpusVersion.id == PolicyCorpusRollout.active_corpus_version_id,
                    ),
                )
                .where(
                    PolicyCorpusRollout.tenant_id == tenant_id,
                    PolicyCorpusRollout.quarantine_reason.is_(None),
                    PolicyCorpusVersion.state == "complete",
                )
            )
        ).one_or_none()
        if row is None:
            raise PolicyCorpusScopeUnavailable("active policy corpus is unavailable")
        rollout, corpus = row
        return cls(
            tenant_id=tenant_id,
            corpus_version_id=corpus.id,
            generation_name=corpus.generation_name,
            config_schema_version=corpus.config_schema_version,
            config_fingerprint=corpus.config_fingerprint,
            rollout_epoch=int(rollout.rollout_epoch),
        )

    def require_tenant(self, tenant_id: UUID) -> None:
        if tenant_id != self.tenant_id:
            raise PolicyCorpusScopeUnavailable("active policy corpus tenant mismatch")

    def require_chunk_config(self, config_fingerprint: str | None) -> None:
        if config_fingerprint != self.config_fingerprint:
            raise PolicyCorpusScopeUnavailable("active policy corpus config mismatch")


@dataclass(frozen=True, slots=True)
class ExactPolicyCorpusScope:
    """Caller-owned exact scope for evaluation or reindex operations only."""

    tenant_id: UUID
    corpus_version_id: UUID
    purpose: Literal["evaluation", "reindex"]

    @classmethod
    def for_evaluation(cls, *, tenant_id: UUID, corpus_version_id: UUID) -> ExactPolicyCorpusScope:
        return cls(tenant_id=tenant_id, corpus_version_id=corpus_version_id, purpose="evaluation")

    @classmethod
    def for_reindex(cls, *, tenant_id: UUID, corpus_version_id: UUID) -> ExactPolicyCorpusScope:
        return cls(tenant_id=tenant_id, corpus_version_id=corpus_version_id, purpose="reindex")

    def require_tenant(self, tenant_id: UUID) -> None:
        if tenant_id != self.tenant_id:
            raise ValueError("policy corpus scope tenant mismatch")


def join_active_chunk_projection(statement, *, tenant_id: UUID):
    """Join one current chunk statement to the tenant active rollout pointer."""

    return (
        statement.join(
            CorpusChunkBinding,
            and_(
                CorpusChunkBinding.tenant_id == tenant_id,
                CorpusChunkBinding.policy_chunk_id == PolicyChunk.id,
            ),
        )
        .join(
            PolicyCorpusRollout,
            and_(
                PolicyCorpusRollout.tenant_id == tenant_id,
                PolicyCorpusRollout.active_corpus_version_id == CorpusChunkBinding.corpus_version_id,
            ),
        )
        .join(
            PolicyCorpusVersion,
            and_(
                PolicyCorpusVersion.tenant_id == tenant_id,
                PolicyCorpusVersion.id == PolicyCorpusRollout.active_corpus_version_id,
                PolicyCorpusVersion.state == "complete",
            ),
        )
        .join(
            CorpusDocumentBinding,
            and_(
                CorpusDocumentBinding.tenant_id == tenant_id,
                CorpusDocumentBinding.corpus_version_id == PolicyCorpusRollout.active_corpus_version_id,
                CorpusDocumentBinding.policy_document_id == PolicyDocument.id,
            ),
        )
        .where(PolicyCorpusRollout.quarantine_reason.is_(None))
    )


def join_active_block_projection(statement, *, tenant_id: UUID):
    """Join one current block statement to the tenant active rollout pointer."""

    return (
        statement.join(
            CorpusBlockBinding,
            and_(
                CorpusBlockBinding.tenant_id == tenant_id,
                CorpusBlockBinding.document_block_id == DocumentBlock.id,
            ),
        )
        .join(
            PolicyCorpusRollout,
            and_(
                PolicyCorpusRollout.tenant_id == tenant_id,
                PolicyCorpusRollout.active_corpus_version_id == CorpusBlockBinding.corpus_version_id,
            ),
        )
        .join(
            PolicyCorpusVersion,
            and_(
                PolicyCorpusVersion.tenant_id == tenant_id,
                PolicyCorpusVersion.id == PolicyCorpusRollout.active_corpus_version_id,
                PolicyCorpusVersion.state == "complete",
            ),
        )
        .join(
            PolicyDocument,
            and_(
                PolicyDocument.tenant_id == tenant_id,
                PolicyDocument.id == DocumentBlock.doc_id,
            ),
        )
        .join(
            CorpusDocumentBinding,
            and_(
                CorpusDocumentBinding.tenant_id == tenant_id,
                CorpusDocumentBinding.corpus_version_id == PolicyCorpusRollout.active_corpus_version_id,
                CorpusDocumentBinding.policy_document_id == PolicyDocument.id,
            ),
        )
        .where(PolicyCorpusRollout.quarantine_reason.is_(None))
    )


def join_active_document_projection(statement, *, tenant_id: UUID):
    """Join one current document statement to the tenant active pointer."""

    return (
        statement.join(
            CorpusDocumentBinding,
            and_(
                CorpusDocumentBinding.tenant_id == tenant_id,
                CorpusDocumentBinding.policy_document_id == PolicyDocument.id,
            ),
        )
        .join(
            PolicyCorpusRollout,
            and_(
                PolicyCorpusRollout.tenant_id == tenant_id,
                PolicyCorpusRollout.active_corpus_version_id == CorpusDocumentBinding.corpus_version_id,
            ),
        )
        .join(
            PolicyCorpusVersion,
            and_(
                PolicyCorpusVersion.tenant_id == tenant_id,
                PolicyCorpusVersion.id == PolicyCorpusRollout.active_corpus_version_id,
                PolicyCorpusVersion.state == "complete",
            ),
        )
        .where(PolicyCorpusRollout.quarantine_reason.is_(None))
    )


def active_chunk_ids(*, tenant_id: UUID, document_id: UUID | None = None):
    statement = join_active_chunk_projection(select(PolicyChunk.id), tenant_id=tenant_id).where(
        PolicyChunk.tenant_id == tenant_id
    )
    if document_id is not None:
        statement = statement.where(PolicyChunk.doc_id == document_id)
    return statement


def active_block_ids(*, tenant_id: UUID, document_id: UUID | None = None):
    statement = join_active_block_projection(select(DocumentBlock.id), tenant_id=tenant_id).where(
        DocumentBlock.tenant_id == tenant_id
    )
    if document_id is not None:
        statement = statement.where(DocumentBlock.doc_id == document_id)
    return statement


def active_document_ids(*, tenant_id: UUID):
    return join_active_document_projection(select(PolicyDocument.id), tenant_id=tenant_id).where(
        PolicyDocument.tenant_id == tenant_id
    )


async def bind_active_policy_projection(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    document: PolicyDocument,
    blocks: Sequence[DocumentBlock],
    chunks: Sequence[PolicyChunk],
    document_version: PolicyDocumentVersion,
    chunk_versions: Sequence[PolicyChunkVersion],
) -> ActivePolicyCorpusScope:
    """Append current-to-immutable bindings under the internally resolved pointer.

    The caller supplies current and immutable material, never a corpus id.  A
    pointer/config change between assembly and this write therefore fails
    closed instead of projecting bytes into the wrong corpus.
    """

    scope = await ActivePolicyCorpusScope.resolve(session, tenant_id=tenant_id)
    scope.require_tenant(document.tenant_id)
    scope.require_tenant(document_version.tenant_id)
    for block in blocks:
        scope.require_tenant(block.tenant_id)
        if block.doc_id != document.id:
            raise PolicyCorpusScopeUnavailable("active policy corpus block mismatch")
    for chunk in chunks:
        scope.require_tenant(chunk.tenant_id)
        scope.require_chunk_config(chunk.chunking_config_fingerprint)
        if chunk.doc_id != document.id:
            raise PolicyCorpusScopeUnavailable("active policy corpus chunk mismatch")
    if document_version.policy_document_id != document.id:
        raise PolicyCorpusScopeUnavailable("active policy corpus document version mismatch")

    versions_by_chunk_id: dict[str, PolicyChunkVersion] = {}
    for version in chunk_versions:
        scope.require_tenant(version.tenant_id)
        if version.policy_document_version_id != document_version.id or version.chunk_id in versions_by_chunk_id:
            raise PolicyCorpusScopeUnavailable("active policy corpus chunk version mismatch")
        versions_by_chunk_id[version.chunk_id] = version
    if set(versions_by_chunk_id) != {chunk.chunk_id for chunk in chunks}:
        raise PolicyCorpusScopeUnavailable("active policy corpus chunk coverage mismatch")

    existing_document = (
        await session.execute(
            select(CorpusDocumentBinding).where(
                CorpusDocumentBinding.tenant_id == tenant_id,
                CorpusDocumentBinding.corpus_version_id == scope.corpus_version_id,
                CorpusDocumentBinding.policy_document_id == document.id,
            )
        )
    ).scalar_one_or_none()
    if existing_document is None:
        session.add(
            CorpusDocumentBinding(
                id=uuid4(),
                tenant_id=tenant_id,
                corpus_version_id=scope.corpus_version_id,
                policy_document_id=document.id,
                policy_document_version_id=document_version.id,
            )
        )
    elif existing_document.policy_document_version_id != document_version.id:
        raise PolicyCorpusScopeUnavailable("active policy corpus document binding is immutable")

    block_ids = [block.id for block in blocks]
    existing_block_ids: set[UUID] = set()
    if block_ids:
        existing_block_ids = set(
            (
                await session.execute(
                    select(CorpusBlockBinding.document_block_id).where(
                        CorpusBlockBinding.tenant_id == tenant_id,
                        CorpusBlockBinding.corpus_version_id == scope.corpus_version_id,
                        CorpusBlockBinding.document_block_id.in_(block_ids),
                    )
                )
            ).scalars()
        )
    session.add_all(
        [
            CorpusBlockBinding(
                id=uuid4(),
                tenant_id=tenant_id,
                corpus_version_id=scope.corpus_version_id,
                document_block_id=block.id,
                policy_document_version_id=document_version.id,
            )
            for block in blocks
            if block.id not in existing_block_ids
        ]
    )

    chunk_ids = [chunk.id for chunk in chunks]
    existing_chunks: dict[UUID, UUID] = {}
    if chunk_ids:
        existing_chunks = dict(
            (
                await session.execute(
                    select(
                        CorpusChunkBinding.policy_chunk_id,
                        CorpusChunkBinding.policy_chunk_version_id,
                    ).where(
                        CorpusChunkBinding.tenant_id == tenant_id,
                        CorpusChunkBinding.corpus_version_id == scope.corpus_version_id,
                        CorpusChunkBinding.policy_chunk_id.in_(chunk_ids),
                    )
                )
            ).all()
        )
    new_chunk_bindings: list[CorpusChunkBinding] = []
    for chunk in chunks:
        version = versions_by_chunk_id[chunk.chunk_id]
        if not _chunk_version_matches_projection(version, chunk):
            raise PolicyCorpusScopeUnavailable("active policy corpus immutable chunk mismatch")
        existing_version_id = existing_chunks.get(chunk.id)
        if existing_version_id is not None and existing_version_id != version.id:
            raise PolicyCorpusScopeUnavailable("active policy corpus chunk binding is immutable")
        if existing_version_id is None:
            new_chunk_bindings.append(
                CorpusChunkBinding(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    corpus_version_id=scope.corpus_version_id,
                    policy_chunk_id=chunk.id,
                    policy_chunk_version_id=version.id,
                )
            )
    session.add_all(new_chunk_bindings)
    await session.flush()
    return scope


def _chunk_version_matches_projection(version: PolicyChunkVersion, chunk: PolicyChunk) -> bool:
    return bool(
        version.chunk_id == chunk.chunk_id
        and version.content == chunk.content
        and version.text_hash == evidence_text_hash(chunk.content)
        and version.search_text == chunk.search_text
        and version.chunking_config_fingerprint == chunk.chunking_config_fingerprint
        and version.embedding_input_hash == chunk.embedding_input_hash
        and version.embedding_token_count == chunk.embedding_token_count
        and version.source_locator_json.get("source_block_refs") == chunk.source_block_refs_json
    )
