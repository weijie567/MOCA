"""Persistence primitives for policy corpus generations and projections.

This module deliberately does not route production reads, claim reindex runs,
or mutate the rollout pointer. Plan 06 owns active-scope routing and Plan 07
owns candidate lifecycle behavior. The repository here exposes only the
schema/bootstrap facts established by migration 030.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
)


CHARACTER_CORPUS_GENERATION = "character.v1"
CHARACTER_CORPUS_CONFIG_SCHEMA_VERSION = "character_compatibility.v1"


class PolicyCorpusUnavailable(RuntimeError):
    """A tenant has no uniquely resolvable corpus bootstrap authority."""


@dataclass(frozen=True)
class PolicyCorpusProjectionCounts:
    documents: int
    blocks: int
    chunks: int


@dataclass(frozen=True)
class PolicyCorpusBootstrapView:
    tenant_id: UUID
    corpus_version_id: UUID
    generation_name: str
    config_schema_version: str
    config_fingerprint: str
    rollout_epoch: int
    counts: PolicyCorpusProjectionCounts


class PolicyCorpusRepository:
    """Read migration-030 corpus/bootstrap state without selecting candidates."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_corpus(
        self,
        *,
        tenant_id: UUID,
        corpus_version_id: UUID,
    ) -> PolicyCorpusVersion | None:
        return (
            await self.session.execute(
                select(PolicyCorpusVersion).where(
                    PolicyCorpusVersion.tenant_id == tenant_id,
                    PolicyCorpusVersion.id == corpus_version_id,
                )
            )
        ).scalar_one_or_none()

    async def get_rollout(self, *, tenant_id: UUID) -> PolicyCorpusRollout | None:
        return (
            await self.session.execute(select(PolicyCorpusRollout).where(PolicyCorpusRollout.tenant_id == tenant_id))
        ).scalar_one_or_none()

    async def get_projection_counts(
        self,
        *,
        tenant_id: UUID,
        corpus_version_id: UUID,
    ) -> PolicyCorpusProjectionCounts:
        async def count(model: type[CorpusDocumentBinding | CorpusBlockBinding | CorpusChunkBinding]) -> int:
            value = await self.session.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.tenant_id == tenant_id,
                    model.corpus_version_id == corpus_version_id,
                )
            )
            return int(value or 0)

        return PolicyCorpusProjectionCounts(
            documents=await count(CorpusDocumentBinding),
            blocks=await count(CorpusBlockBinding),
            chunks=await count(CorpusChunkBinding),
        )

    async def require_character_bootstrap(self, *, tenant_id: UUID) -> PolicyCorpusBootstrapView:
        rollout = await self.get_rollout(tenant_id=tenant_id)
        if rollout is None:
            raise PolicyCorpusUnavailable("policy corpus bootstrap is unavailable")
        corpus = await self.get_corpus(
            tenant_id=tenant_id,
            corpus_version_id=rollout.active_corpus_version_id,
        )
        if (
            corpus is None
            or corpus.generation_name != CHARACTER_CORPUS_GENERATION
            or corpus.config_schema_version != CHARACTER_CORPUS_CONFIG_SCHEMA_VERSION
            or corpus.state != "complete"
        ):
            raise PolicyCorpusUnavailable("policy corpus bootstrap is unavailable")
        counts = await self.get_projection_counts(
            tenant_id=tenant_id,
            corpus_version_id=corpus.id,
        )
        expected = dict(corpus.bootstrap_counts_json or {})
        if (
            counts.documents != expected.get("bound_document_count")
            or counts.blocks != expected.get("bound_block_count")
            or counts.chunks != expected.get("bound_chunk_count")
        ):
            raise PolicyCorpusUnavailable("policy corpus bootstrap is unavailable")
        return PolicyCorpusBootstrapView(
            tenant_id=tenant_id,
            corpus_version_id=corpus.id,
            generation_name=corpus.generation_name,
            config_schema_version=corpus.config_schema_version,
            config_fingerprint=corpus.config_fingerprint,
            rollout_epoch=rollout.rollout_epoch,
            counts=counts,
        )
