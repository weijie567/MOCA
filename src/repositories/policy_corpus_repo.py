"""Persistence primitives for policy corpus generations and projections.

This module deliberately does not route production reads, claim reindex runs,
or mutate the rollout pointer. Plan 06 owns active-scope routing and Plan 07
owns candidate lifecycle behavior. The repository here exposes only the
schema/bootstrap facts established by migration 030.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    PolicyCorpusActivationHistory,
    PolicyCorpusManifestRevision,
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


@dataclass(frozen=True, slots=True)
class PolicyCorpusActivationView:
    tenant_id: UUID
    active_corpus_version_id: UUID
    previous_corpus_version_id: UUID | None
    rollout_epoch: int


class PolicyCorpusRepository:
    """Persistence owner for corpus bootstrap and tenant-scoped candidates."""

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

    async def acquire_tenant_rollout_lock(self, *, tenant_id: UUID) -> PolicyCorpusRollout:
        """Serialize claims, then lock the one tenant pointer row."""

        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:tenant_id AS text), 0))"),
            {"tenant_id": str(tenant_id)},
        )
        rollout = (
            await self.session.execute(
                select(PolicyCorpusRollout)
                .where(PolicyCorpusRollout.tenant_id == tenant_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if rollout is None:
            raise PolicyCorpusUnavailable("policy corpus rollout is unavailable")
        return rollout

    async def lock_latest_manifest(self, *, tenant_id: UUID) -> PolicyCorpusManifestRevision:
        manifest = (
            await self.session.execute(
                select(PolicyCorpusManifestRevision)
                .where(PolicyCorpusManifestRevision.tenant_id == tenant_id)
                .order_by(PolicyCorpusManifestRevision.revision.desc(), PolicyCorpusManifestRevision.id.desc())
                .limit(1)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if manifest is None:
            raise PolicyCorpusUnavailable("policy corpus manifest is unavailable")
        return manifest

    async def get_candidate_by_run(
        self,
        *,
        tenant_id: UUID,
        run_token: UUID,
    ) -> PolicyCorpusVersion | None:
        rows = list(
            (
                await self.session.execute(
                    select(PolicyCorpusVersion)
                    .where(
                        PolicyCorpusVersion.tenant_id == tenant_id,
                        PolicyCorpusVersion.run_token == run_token,
                    )
                    .order_by(PolicyCorpusVersion.created_at, PolicyCorpusVersion.id)
                    .with_for_update()
                )
            ).scalars()
        )
        if len(rows) > 1:
            raise PolicyCorpusUnavailable("policy corpus run identity is ambiguous")
        return rows[0] if rows else None

    async def lock_candidate(self, *, corpus_version_id: UUID) -> PolicyCorpusVersion | None:
        return (
            await self.session.execute(
                select(PolicyCorpusVersion)
                .where(PolicyCorpusVersion.id == corpus_version_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def cas_candidate(
        self,
        row: PolicyCorpusVersion,
        *,
        expected_state_version: int,
        expected_next_document_index: int,
        values: dict[str, Any],
    ) -> PolicyCorpusVersion | None:
        """CAS one exact tenant/run/owner/cursor without changing the pointer."""

        result = await self.session.execute(
            update(PolicyCorpusVersion)
            .where(
                PolicyCorpusVersion.id == row.id,
                PolicyCorpusVersion.tenant_id == row.tenant_id,
                PolicyCorpusVersion.run_token == row.run_token,
                PolicyCorpusVersion.owner_marker == row.owner_marker,
                PolicyCorpusVersion.state_version == expected_state_version,
                PolicyCorpusVersion.next_document_index == expected_next_document_index,
            )
            .values(**values, state_version=expected_state_version + 1, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        if (result.rowcount or 0) != 1:
            return None
        return await self.lock_candidate(corpus_version_id=row.id)

    async def activate_rollout_cas(
        self,
        rollout: PolicyCorpusRollout,
        *,
        expected_active_corpus_version_id: UUID,
        expected_rollout_epoch: int,
        target_corpus_version_id: UUID,
        reason_code: str,
        actor: str,
        selection_decision_hash: str | None,
    ) -> PolicyCorpusActivationView | None:
        """Flip one exact pointer and append its audit row in this transaction."""

        new_epoch = expected_rollout_epoch + 1
        result = await self.session.execute(
            update(PolicyCorpusRollout)
            .where(
                PolicyCorpusRollout.id == rollout.id,
                PolicyCorpusRollout.tenant_id == rollout.tenant_id,
                PolicyCorpusRollout.active_corpus_version_id == expected_active_corpus_version_id,
                PolicyCorpusRollout.rollout_epoch == expected_rollout_epoch,
            )
            .values(
                active_corpus_version_id=target_corpus_version_id,
                previous_corpus_version_id=expected_active_corpus_version_id,
                rollout_epoch=new_epoch,
                updated_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        if (result.rowcount or 0) != 1:
            return None
        self.session.add(
            PolicyCorpusActivationHistory(
                tenant_id=rollout.tenant_id,
                from_corpus_version_id=expected_active_corpus_version_id,
                to_corpus_version_id=target_corpus_version_id,
                prior_rollout_epoch=expected_rollout_epoch,
                rollout_epoch=new_epoch,
                reason_code=reason_code,
                actor=actor,
                selection_decision_hash=selection_decision_hash,
                receipt_hash=None,
            )
        )
        await self.session.flush()
        return PolicyCorpusActivationView(
            tenant_id=rollout.tenant_id,
            active_corpus_version_id=target_corpus_version_id,
            previous_corpus_version_id=expected_active_corpus_version_id,
            rollout_epoch=new_epoch,
        )

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
