"""Persistence primitives for policy corpus generations and projections.

Plan 06 owns active-scope routing, Plan 07 owns candidate lifecycle behavior,
and Plan 08 adds the only pointer CAS plus ordinary-ingestion copy-on-write
primitive. Selection policy and durable cutover receipts remain outside this
repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    DocumentBlock,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusActivationHistory,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyDocument,
    PolicyDocumentVersion,
    Tenant,
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


@dataclass(frozen=True, slots=True)
class PolicyCorpusCowView:
    activation: PolicyCorpusActivationView
    corpus_version_id: UUID
    manifest_revision_id: UUID
    manifest_revision: int


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

        await self._acquire_tenant_lock(tenant_id=tenant_id)
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

    async def ensure_tenant_character_bootstrap(
        self,
        *,
        tenant_id: UUID,
        config_json: dict[str, Any],
        config_fingerprint: str,
        now: datetime | None = None,
    ) -> PolicyCorpusRollout:
        """Create the sole empty first-corpus authority under the tenant lock."""

        await self._acquire_tenant_lock(tenant_id=tenant_id)
        rollout = (
            await self.session.execute(
                select(PolicyCorpusRollout)
                .where(PolicyCorpusRollout.tenant_id == tenant_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if rollout is not None:
            return rollout

        tenant_exists = (
            await self.session.execute(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())
        ).scalar_one_or_none()
        if tenant_exists is None:
            raise PolicyCorpusUnavailable("policy corpus tenant is unavailable")
        existing_manifest = await self.session.scalar(
            select(func.count())
            .select_from(PolicyCorpusManifestRevision)
            .where(PolicyCorpusManifestRevision.tenant_id == tenant_id)
        )
        existing_corpus = await self.session.scalar(
            select(func.count()).select_from(PolicyCorpusVersion).where(PolicyCorpusVersion.tenant_id == tenant_id)
        )
        if int(existing_manifest or 0) != 0 or int(existing_corpus or 0) != 0:
            raise PolicyCorpusUnavailable("policy corpus bootstrap authority is incomplete")
        if (
            config_json.get("schema_version") != CHARACTER_CORPUS_CONFIG_SCHEMA_VERSION
            or _sha256_json(config_json) != config_fingerprint
        ):
            raise PolicyCorpusUnavailable("policy corpus bootstrap config is invalid")

        created_at = _as_utc(now or datetime.now(UTC))
        manifest_payload = {
            "schema_version": "policy_corpus_source_manifest.v1",
            "tenant_id": str(tenant_id),
            "documents": [],
        }
        manifest = PolicyCorpusManifestRevision(
            tenant_id=tenant_id,
            revision=1,
            manifest_schema_version="policy_corpus_source_manifest.v1",
            manifest_json=manifest_payload,
            manifest_hash=_sha256_json(manifest_payload),
            document_count=0,
            block_count=0,
            chunk_count=0,
        )
        self.session.add(manifest)
        await self.session.flush()
        corpus = PolicyCorpusVersion(
            tenant_id=tenant_id,
            generation_name=CHARACTER_CORPUS_GENERATION,
            owner_marker="moca.policy_ingestion.bootstrap.v1",
            run_token=None,
            config_schema_version=CHARACTER_CORPUS_CONFIG_SCHEMA_VERSION,
            config_json=dict(config_json),
            config_fingerprint=config_fingerprint,
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
            validation_proof_json={
                "bootstrap_contract": CHARACTER_CORPUS_GENERATION,
                "visibility": "empty_first_corpus",
            },
            terminal_at=created_at,
        )
        self.session.add(corpus)
        await self.session.flush()
        rollout = PolicyCorpusRollout(
            tenant_id=tenant_id,
            active_corpus_version_id=corpus.id,
            previous_corpus_version_id=None,
            rollout_epoch=1,
        )
        self.session.add(rollout)
        self.session.add(
            PolicyCorpusActivationHistory(
                tenant_id=tenant_id,
                from_corpus_version_id=None,
                to_corpus_version_id=corpus.id,
                prior_rollout_epoch=0,
                rollout_epoch=1,
                reason_code="bootstrap_character_v1",
                actor="moca.policy_ingestion.bootstrap.v1",
                selection_decision_hash=None,
                receipt_hash=None,
            )
        )
        await self.session.flush()
        return rollout

    async def _acquire_tenant_lock(self, *, tenant_id: UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:tenant_id AS text), 0))"),
            {"tenant_id": str(tenant_id)},
        )

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
            .execution_options(synchronize_session="fetch")
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
        source_drifted_at: datetime | None = None,
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
                source_drifted_at=source_drifted_at,
                updated_at=func.now(),
            )
            .execution_options(synchronize_session="fetch")
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

    async def get_bound_document_version(
        self,
        *,
        tenant_id: UUID,
        corpus_version_id: UUID,
        policy_document_id: UUID,
    ) -> PolicyDocumentVersion | None:
        return (
            await self.session.execute(
                select(PolicyDocumentVersion)
                .join(
                    CorpusDocumentBinding,
                    (CorpusDocumentBinding.tenant_id == tenant_id)
                    & (CorpusDocumentBinding.corpus_version_id == corpus_version_id)
                    & (CorpusDocumentBinding.policy_document_version_id == PolicyDocumentVersion.id),
                )
                .where(
                    CorpusDocumentBinding.policy_document_id == policy_document_id,
                    PolicyDocumentVersion.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

    async def create_ingestion_cow(
        self,
        *,
        rollout: PolicyCorpusRollout,
        source_manifest: PolicyCorpusManifestRevision,
        active_corpus: PolicyCorpusVersion,
        document: PolicyDocument,
        blocks: list[DocumentBlock],
        chunks: list[PolicyChunk],
        document_version: PolicyDocumentVersion | None,
        chunk_versions: list[PolicyChunkVersion],
        expected_evidence_rollout_version: int,
        actor: str,
        delete_document: bool = False,
        now: datetime | None = None,
    ) -> PolicyCorpusCowView:
        """Append one same-config corpus and atomically replace current visibility."""

        changed_at = _as_utc(now or datetime.now(UTC))
        if (
            rollout.active_corpus_version_id != active_corpus.id
            or active_corpus.tenant_id != rollout.tenant_id
            or source_manifest.tenant_id != rollout.tenant_id
            or active_corpus.source_manifest_revision_id != source_manifest.id
            or active_corpus.source_manifest_hash != source_manifest.manifest_hash
            or active_corpus.state != "complete"
            or document.tenant_id != rollout.tenant_id
        ):
            raise PolicyCorpusUnavailable("policy corpus source authority changed")
        if delete_document:
            if blocks or chunks or document_version is not None or chunk_versions:
                raise PolicyCorpusUnavailable("deleted policy corpus projection is not empty")
        elif (
            document_version is None
            or document_version.tenant_id != rollout.tenant_id
            or document_version.policy_document_id != document.id
            or len(chunks) != len(chunk_versions)
            or any(chunk.tenant_id != rollout.tenant_id or chunk.doc_id != document.id for chunk in chunks)
            or any(block.tenant_id != rollout.tenant_id or block.doc_id != document.id for block in blocks)
        ):
            raise PolicyCorpusUnavailable("policy corpus replacement projection is invalid")

        prior_documents = source_manifest.manifest_json.get("documents")
        if not isinstance(prior_documents, list):
            raise PolicyCorpusUnavailable("policy corpus manifest is invalid")
        next_documents = [
            dict(item) for item in prior_documents if isinstance(item, dict) and item.get("doc_key") != document.doc_key
        ]
        if len(next_documents) != len(prior_documents) - sum(
            1 for item in prior_documents if isinstance(item, dict) and item.get("doc_key") == document.doc_key
        ):
            raise PolicyCorpusUnavailable("policy corpus manifest is invalid")
        replaced_documents = [
            item for item in prior_documents if isinstance(item, dict) and item.get("doc_key") == document.doc_key
        ]
        prior_block_count = sum(
            len(item.get("source_block_ids", []))
            for item in replaced_documents
            if isinstance(item.get("source_block_ids"), list)
        )
        prior_chunk_count = sum(
            len(item.get("chunk_ids", [])) for item in replaced_documents if isinstance(item.get("chunk_ids"), list)
        )
        if not delete_document:
            assert document_version is not None
            next_documents.append(
                {
                    "policy_document_id": str(document.id),
                    "policy_document_version_id": str(document_version.id),
                    "doc_key": document.doc_key,
                    "document_version": int(document.version or 1),
                    "source_type": document.source_type,
                    "source_checksum": document.source_checksum,
                    "source_block_ids": [
                        block.source_block_id for block in sorted(blocks, key=lambda row: row.block_index)
                    ],
                    "chunk_ids": [chunk.chunk_id for chunk in sorted(chunks, key=lambda row: row.chunk_id)],
                }
            )
        next_documents.sort(key=lambda item: str(item["doc_key"]))
        manifest_payload = {
            "schema_version": "policy_corpus_source_manifest.v1",
            "tenant_id": str(rollout.tenant_id),
            "documents": next_documents,
        }
        manifest_hash = _sha256_json(manifest_payload)
        next_revision = source_manifest.revision + 1
        next_block_count = source_manifest.block_count - prior_block_count + (0 if delete_document else len(blocks))
        next_chunk_count = source_manifest.chunk_count - prior_chunk_count + (0 if delete_document else len(chunks))
        next_manifest = PolicyCorpusManifestRevision(
            id=uuid4(),
            tenant_id=rollout.tenant_id,
            revision=next_revision,
            manifest_schema_version="policy_corpus_source_manifest.v1",
            manifest_json=manifest_payload,
            manifest_hash=manifest_hash,
            document_count=len(next_documents),
            block_count=next_block_count,
            chunk_count=next_chunk_count,
        )
        self.session.add(next_manifest)
        await self.session.flush()
        suffix = f":ingest:{next_revision}"
        generation_name = active_corpus.generation_name[: 128 - len(suffix)] + suffix
        next_corpus = PolicyCorpusVersion(
            id=uuid4(),
            tenant_id=rollout.tenant_id,
            generation_name=generation_name,
            owner_marker="moca.policy_ingestion.cow.v1",
            run_token=None,
            config_schema_version=active_corpus.config_schema_version,
            config_json=dict(active_corpus.config_json or {}),
            config_fingerprint=active_corpus.config_fingerprint,
            provider_parity_report_hash=active_corpus.provider_parity_report_hash,
            source_manifest_revision_id=next_manifest.id,
            source_manifest_hash=manifest_hash,
            source_active_corpus_version_id=active_corpus.id,
            source_rollout_epoch=rollout.rollout_epoch,
            expected_evidence_rollout_version=expected_evidence_rollout_version,
            state="complete",
            state_version=1,
            lease_owner=None,
            lease_expires_at=None,
            next_document_index=len(next_documents),
            bootstrap_counts_json={
                "bound_document_count": len(next_documents),
                "bound_block_count": next_block_count,
                "bound_chunk_count": next_chunk_count,
            },
            validation_proof_json={
                "ordinary_ingestion_cow": {
                    "schema_version": "policy_ingestion_cow.v1",
                    "source_manifest_hash": source_manifest.manifest_hash,
                    "manifest_hash": manifest_hash,
                    "config_fingerprint": active_corpus.config_fingerprint,
                    "immutable_rows_retained": True,
                }
            },
            terminal_at=changed_at,
        )
        self.session.add(next_corpus)
        await self.session.flush()

        document_bindings = list(
            (
                await self.session.execute(
                    select(CorpusDocumentBinding).where(
                        CorpusDocumentBinding.tenant_id == rollout.tenant_id,
                        CorpusDocumentBinding.corpus_version_id == active_corpus.id,
                        CorpusDocumentBinding.policy_document_id != document.id,
                    )
                )
            ).scalars()
        )
        block_bindings = list(
            (
                await self.session.execute(
                    select(CorpusBlockBinding)
                    .join(DocumentBlock, DocumentBlock.id == CorpusBlockBinding.document_block_id)
                    .where(
                        CorpusBlockBinding.tenant_id == rollout.tenant_id,
                        CorpusBlockBinding.corpus_version_id == active_corpus.id,
                        DocumentBlock.doc_id != document.id,
                    )
                )
            ).scalars()
        )
        chunk_bindings = list(
            (
                await self.session.execute(
                    select(CorpusChunkBinding)
                    .join(PolicyChunk, PolicyChunk.id == CorpusChunkBinding.policy_chunk_id)
                    .where(
                        CorpusChunkBinding.tenant_id == rollout.tenant_id,
                        CorpusChunkBinding.corpus_version_id == active_corpus.id,
                        PolicyChunk.doc_id != document.id,
                    )
                )
            ).scalars()
        )
        self.session.add_all(
            [
                CorpusDocumentBinding(
                    tenant_id=rollout.tenant_id,
                    corpus_version_id=next_corpus.id,
                    policy_document_id=row.policy_document_id,
                    policy_document_version_id=row.policy_document_version_id,
                )
                for row in document_bindings
            ]
        )
        self.session.add_all(
            [
                CorpusBlockBinding(
                    tenant_id=rollout.tenant_id,
                    corpus_version_id=next_corpus.id,
                    document_block_id=row.document_block_id,
                    policy_document_version_id=row.policy_document_version_id,
                )
                for row in block_bindings
            ]
        )
        self.session.add_all(
            [
                CorpusChunkBinding(
                    tenant_id=rollout.tenant_id,
                    corpus_version_id=next_corpus.id,
                    policy_chunk_id=row.policy_chunk_id,
                    policy_chunk_version_id=row.policy_chunk_version_id,
                )
                for row in chunk_bindings
            ]
        )
        if not delete_document:
            assert document_version is not None
            self.session.add(
                CorpusDocumentBinding(
                    tenant_id=rollout.tenant_id,
                    corpus_version_id=next_corpus.id,
                    policy_document_id=document.id,
                    policy_document_version_id=document_version.id,
                )
            )
            self.session.add_all(
                [
                    CorpusBlockBinding(
                        tenant_id=rollout.tenant_id,
                        corpus_version_id=next_corpus.id,
                        document_block_id=block.id,
                        policy_document_version_id=document_version.id,
                    )
                    for block in blocks
                ]
            )
            self.session.add_all(
                [
                    CorpusChunkBinding(
                        tenant_id=rollout.tenant_id,
                        corpus_version_id=next_corpus.id,
                        policy_chunk_id=chunk.id,
                        policy_chunk_version_id=immutable.id,
                    )
                    for chunk, immutable in zip(chunks, chunk_versions, strict=True)
                ]
            )
        await self.session.flush()
        counts = await self.get_projection_counts(
            tenant_id=rollout.tenant_id,
            corpus_version_id=next_corpus.id,
        )
        if (counts.documents, counts.blocks, counts.chunks) != (
            len(next_documents),
            next_block_count,
            next_chunk_count,
        ):
            raise PolicyCorpusUnavailable("policy corpus copy-on-write coverage mismatch")
        await self.session.execute(
            update(PolicyCorpusVersion)
            .where(
                PolicyCorpusVersion.tenant_id == rollout.tenant_id,
                PolicyCorpusVersion.id != next_corpus.id,
                PolicyCorpusVersion.source_manifest_revision_id == source_manifest.id,
                PolicyCorpusVersion.state.in_({"claimed", "building", "built", "validating", "complete"}),
            )
            .values(
                state="source_stale",
                state_version=PolicyCorpusVersion.state_version + 1,
                failure_code="source_manifest_drift",
                safe_message="corpus source authority changed by ordinary ingestion",
                terminal_at=changed_at,
                updated_at=func.now(),
            )
            .execution_options(synchronize_session="fetch")
        )
        activation = await self.activate_rollout_cas(
            rollout,
            expected_active_corpus_version_id=active_corpus.id,
            expected_rollout_epoch=rollout.rollout_epoch,
            target_corpus_version_id=next_corpus.id,
            reason_code="ordinary_ingestion",
            actor=actor,
            selection_decision_hash=None,
            source_drifted_at=changed_at,
        )
        if activation is None:
            raise PolicyCorpusUnavailable("policy corpus pointer changed")
        return PolicyCorpusCowView(
            activation=activation,
            corpus_version_id=next_corpus.id,
            manifest_revision_id=next_manifest.id,
            manifest_revision=next_revision,
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


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
