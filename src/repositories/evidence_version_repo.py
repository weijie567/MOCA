"""Immutable evidence versions and the singleton rollout control plane.

Lock order is a correctness contract, not an implementation detail:

1. lock ``evidence_identity_rollouts(id=1)`` with ``FOR UPDATE``;
2. validate the caller's rollout epoch and required state;
3. lock current ``PolicyDocument`` / ``PolicyChunk`` heads in deterministic
   ``(tenant_id, doc_key, id)`` order;
4. allocate at most one ingestion sequence and mutate projections/history.

Writers, backfill/reconciliation, operational rollback, and final activation
all enter through this owner so no caller may acquire the locks in reverse.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    EvidenceIdentityRollout,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
)
from src.knowledge.evidence_identity import (
    ACCEPTED_POLICY_SCOPE_TYPE,
    CanonicalEvidenceResolutionV1,
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
    resolve_evidence_identity,
)
from src.knowledge.text_hash import evidence_text_hash

ROLLOUT_ID = 1
DEFAULT_EVIDENCE_RETENTION = timedelta(days=3650)


class EvidenceRolloutError(RuntimeError):
    """Base class for fail-closed rollout failures."""


class RolloutEpochMismatch(EvidenceRolloutError):
    pass


class DualWriteUnavailable(EvidenceRolloutError):
    pass


class ImmutableBindingMismatch(EvidenceRolloutError):
    pass


class EvidenceVersionRepository:
    """Only persistence owner for immutable evidence and rollout state."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_rollout(
        self,
        *,
        expected_rollout_version: int | None,
        require_dual_write: bool,
    ) -> EvidenceIdentityRollout:
        row = (
            await self.session.execute(
                select(EvidenceIdentityRollout).where(EvidenceIdentityRollout.id == ROLLOUT_ID).with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise EvidenceRolloutError("evidence rollout state is unavailable")
        if expected_rollout_version is not None and row.rollout_version != expected_rollout_version:
            raise RolloutEpochMismatch("stale evidence rollout epoch")
        if require_dual_write and row.dual_write_enabled_at is None:
            raise DualWriteUnavailable("immutable evidence dual-write is not enabled")
        return row

    async def lock_for_writer(self, *, expected_rollout_version: int | None) -> EvidenceIdentityRollout:
        return await self.lock_rollout(
            expected_rollout_version=expected_rollout_version,
            require_dual_write=True,
        )

    async def activate_dual_write(
        self,
        *,
        expected_rollout_version: int,
        health_checked_at: datetime,
    ) -> EvidenceIdentityRollout:
        """CAS-enable dual-write without performing backfill or read cutover."""

        row = await self.lock_rollout(
            expected_rollout_version=expected_rollout_version,
            require_dual_write=False,
        )
        if row.backfill_watermark_sequence is not None:
            raise EvidenceRolloutError("dual-write activation must precede backfill")
        checked_at = _as_utc(health_checked_at)
        row.dual_write_enabled_at = row.dual_write_enabled_at or checked_at
        row.audit_counts_json = {
            **dict(row.audit_counts_json or {}),
            "dual_write_health": "healthy",
            "dual_write_health_checked_at": checked_at.isoformat(),
        }
        row.rollout_version += 1
        await self.session.flush()
        return row

    async def allocate_ingestion_sequence(self) -> int:
        value = await self.session.scalar(text("SELECT nextval('evidence_ingestion_write_seq')"))
        if value is None:
            raise EvidenceRolloutError("evidence ingestion sequence is unavailable")
        return int(value)

    async def find_exact_binding(
        self,
        *,
        tenant_id: UUID,
        document: PolicyDocument,
        chunks: Sequence[PolicyChunk],
        fingerprint: str,
    ) -> tuple[PolicyDocumentVersion, list[PolicyChunkVersion]] | None:
        scope_id = str(tenant_id)
        document_rows = list(
            (
                await self.session.execute(
                    select(PolicyDocumentVersion).where(
                        PolicyDocumentVersion.tenant_id == tenant_id,
                        PolicyDocumentVersion.scope_type == ACCEPTED_POLICY_SCOPE_TYPE,
                        PolicyDocumentVersion.scope_id == scope_id,
                        PolicyDocumentVersion.doc_key == document.doc_key,
                        PolicyDocumentVersion.document_version == int(document.version or 1),
                    )
                )
            ).scalars()
        )
        if not document_rows:
            return None
        if len(document_rows) != 1:
            raise ImmutableBindingMismatch("ambiguous immutable document binding")
        document_version = document_rows[0]
        if document_version.content_hash != evidence_text_hash(document.content):
            raise ImmutableBindingMismatch("immutable document hash mismatch")
        if fingerprint != document.policy_version_fingerprint:
            raise ImmutableBindingMismatch("immutable document fingerprint mismatch")

        immutable_chunks = list(
            (
                await self.session.execute(
                    select(PolicyChunkVersion)
                    .where(
                        PolicyChunkVersion.tenant_id == tenant_id,
                        PolicyChunkVersion.policy_document_version_id == document_version.id,
                    )
                    .order_by(PolicyChunkVersion.chunk_id, PolicyChunkVersion.chunk_version)
                )
            ).scalars()
        )
        expected = {(chunk.chunk_id, evidence_text_hash(chunk.content)) for chunk in chunks}
        actual = {(chunk.chunk_id, chunk.text_hash) for chunk in immutable_chunks}
        if len(expected) != len(chunks) or expected != actual:
            raise ImmutableBindingMismatch("immutable chunk binding mismatch")
        return document_version, immutable_chunks

    async def append_immutable_version(
        self,
        *,
        tenant_id: UUID,
        document: PolicyDocument,
        chunks: Sequence[PolicyChunk],
        write_sequence: int,
        correction_of_document_version_id: str | UUID | None = None,
        retention_until: datetime | None = None,
    ) -> tuple[PolicyDocumentVersion, list[PolicyChunkVersion]]:
        """Append one document version and one row per produced chunk."""

        scope_id = str(tenant_id)
        document_version_number = int(document.version or 1)
        previous_document = (
            await self.session.execute(
                select(PolicyDocumentVersion)
                .where(
                    PolicyDocumentVersion.tenant_id == tenant_id,
                    PolicyDocumentVersion.scope_type == ACCEPTED_POLICY_SCOPE_TYPE,
                    PolicyDocumentVersion.scope_id == scope_id,
                    PolicyDocumentVersion.doc_key == document.doc_key,
                    PolicyDocumentVersion.document_version < document_version_number,
                )
                .order_by(PolicyDocumentVersion.document_version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        correction_id = _optional_uuid(correction_of_document_version_id)
        if correction_id is not None:
            correction_target = await self.session.get(PolicyDocumentVersion, correction_id)
            if (
                correction_target is None
                or correction_target.tenant_id != tenant_id
                or correction_target.doc_key != document.doc_key
            ):
                raise ImmutableBindingMismatch("correction target is unavailable")

        retained_until = retention_until or (datetime.now(UTC) + DEFAULT_EVIDENCE_RETENTION)
        document_row = PolicyDocumentVersion(
            id=uuid4(),
            tenant_id=tenant_id,
            policy_document_id=document.id,
            scope_type=ACCEPTED_POLICY_SCOPE_TYPE,
            scope_id=scope_id,
            doc_key=document.doc_key,
            document_version=document_version_number,
            content=document.content,
            content_hash=evidence_text_hash(document.content),
            source_locator_json=_document_source_locator(document),
            lifecycle_status="corrected" if correction_id is not None else "active",
            retention_until=retained_until,
            supersedes_version_id=previous_document.id if previous_document is not None else None,
            corrects_version_id=correction_id,
        )
        self.session.add(document_row)
        await self.session.flush()

        previous_chunks: dict[str, PolicyChunkVersion] = {}
        if previous_document is not None:
            previous_chunks = {
                row.chunk_id: row
                for row in (
                    (
                        await self.session.execute(
                            select(PolicyChunkVersion).where(
                                PolicyChunkVersion.tenant_id == tenant_id,
                                PolicyChunkVersion.policy_document_version_id == previous_document.id,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            }

        chunk_rows: list[PolicyChunkVersion] = []
        for chunk in sorted(chunks, key=lambda item: (str(item.chunk_id), str(item.id))):
            previous_chunk = previous_chunks.get(chunk.chunk_id)
            row = PolicyChunkVersion(
                id=uuid4(),
                tenant_id=tenant_id,
                policy_document_version_id=document_row.id,
                scope_type=ACCEPTED_POLICY_SCOPE_TYPE,
                scope_id=scope_id,
                doc_key=document.doc_key,
                document_version=document_version_number,
                chunk_id=chunk.chunk_id,
                chunk_version=(previous_chunk.chunk_version + 1) if previous_chunk is not None else 1,
                content=chunk.content,
                text_hash=evidence_text_hash(chunk.content),
                source_locator_json=_chunk_source_locator(document, chunk),
                lifecycle_status="corrected" if correction_id is not None else "active",
                retention_until=retained_until,
                supersedes_version_id=previous_chunk.id if previous_chunk is not None else None,
                corrects_version_id=previous_chunk.id if correction_id is not None and previous_chunk else None,
            )
            chunk_rows.append(row)
        self.session.add_all(chunk_rows)
        await self.session.flush()
        await self.project_write_sequence(document=document, chunks=chunks, write_sequence=write_sequence)
        return document_row, chunk_rows

    async def project_write_sequence(
        self,
        *,
        document: PolicyDocument,
        chunks: Sequence[PolicyChunk],
        write_sequence: int,
    ) -> None:
        document.evidence_write_sequence = write_sequence
        for chunk in chunks:
            chunk.evidence_write_sequence = write_sequence
        await self.session.flush()

    async def resolve_exact(
        self,
        candidate: object,
        *,
        expected_tenant_id: UUID | str,
        expected_scope_type: str,
        expected_scope_id: str,
    ) -> CanonicalEvidenceResolutionV1:
        """Resolve canonical or legacy input against exact immutable candidates."""

        tenant_id = UUID(str(expected_tenant_id))
        candidates = await self._candidate_material(candidate, tenant_id=tenant_id)
        return resolve_evidence_identity(
            candidate,  # type: ignore[arg-type]
            candidates,
            expected_tenant_id=str(tenant_id),
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )

    async def mint_for_chunk_version(
        self,
        chunk: PolicyChunkVersion,
        *,
        expected_tenant_id: UUID | str,
        expected_scope_type: str,
        expected_scope_id: str,
    ) -> CanonicalEvidenceResolutionV1:
        return mint_canonical_evidence_identity(
            _material_from_chunk(chunk),
            expected_tenant_id=str(expected_tenant_id),
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )

    async def _candidate_material(
        self,
        candidate: object,
        *,
        tenant_id: UUID,
    ) -> list[PersistedEvidenceIdentityMaterialV1]:
        statement = select(PolicyChunkVersion).where(PolicyChunkVersion.tenant_id == tenant_id)
        candidate_id = getattr(candidate, "chunk_version_id", None)
        if candidate_id:
            statement = statement.where(PolicyChunkVersion.id == UUID(str(candidate_id)))
        rows = list((await self.session.execute(statement)).scalars())
        return [_material_from_chunk(row) for row in rows]


def _material_from_chunk(chunk: PolicyChunkVersion) -> PersistedEvidenceIdentityMaterialV1:
    return PersistedEvidenceIdentityMaterialV1(
        tenant_id=str(chunk.tenant_id),
        scope_type=chunk.scope_type,
        scope_id=chunk.scope_id,
        document_version_id=str(chunk.policy_document_version_id),
        chunk_version_id=str(chunk.id),
        doc_key=chunk.doc_key,
        document_version=chunk.document_version,
        chunk_id=chunk.chunk_id,
        chunk_version=chunk.chunk_version,
        text_hash=chunk.text_hash,
    )


def _document_source_locator(document: PolicyDocument) -> dict[str, object]:
    locator: dict[str, object] = {"source_type": document.source_type or "policy_source"}
    if document.source_checksum:
        locator["source_checksum"] = document.source_checksum
    return locator


def _chunk_source_locator(document: PolicyDocument, chunk: PolicyChunk) -> dict[str, object]:
    locator = _document_source_locator(document)
    locator["source_block_refs"] = list(chunk.source_block_refs_json or [])
    return locator


def _optional_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ImmutableBindingMismatch("correction target is unavailable") from exc


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
