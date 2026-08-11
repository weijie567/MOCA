"""Single authority for current and explicitly scoped policy corpora.

Production repositories never accept a caller-selected corpus id.  They join
the tenant rollout pointer through the helpers in this module.  Evaluation and
reindex code may instead pass an :class:`ExactPolicyCorpusScope` whose purpose
is explicit at construction time.  Immutable evidence history remains outside
both DTOs and resolves its stored version ids directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

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
)


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
