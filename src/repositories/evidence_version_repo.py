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

from collections.abc import Awaitable, Callable, Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusChunkBinding,
    CorpusDocumentBinding,
    EvidenceIdentityRollout,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusRollout,
    PolicyDocument,
    PolicyDocumentVersion,
)
from src.knowledge.evidence_identity import (
    ACCEPTED_POLICY_SCOPE_TYPE,
    CanonicalEvidenceIdentityV1,
    CanonicalEvidenceResolutionV1,
    EvidenceIdentityExternalReason,
    EvidenceIdentityInternalReason,
    EvidenceIdentityResolutionStatus,
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
    resolve_evidence_identity,
)
from src.knowledge.text_hash import evidence_text_hash
from src.rag.versioning import build_policy_version_fingerprint
from src.repositories.document_block_repo import CanonicalDocumentContentV2
from src.repositories.policy_corpus_scope import (
    ActivePolicyCorpusScope,
    join_active_chunk_projection,
    join_active_document_projection,
)

ROLLOUT_ID = 1
DEFAULT_EVIDENCE_RETENTION = timedelta(days=3650)
DUAL_WRITE_HEALTH_MAX_AGE = timedelta(minutes=5)


class EvidenceRolloutError(RuntimeError):
    """Base class for fail-closed rollout failures."""


class RolloutEpochMismatch(EvidenceRolloutError):
    pass


class DualWriteUnavailable(EvidenceRolloutError):
    pass


class ImmutableBindingMismatch(EvidenceRolloutError):
    pass


def canonical_document_version_matches_source(
    document_version: object,
    *,
    source_checksum: str | None,
    canonical_source: CanonicalDocumentContentV2 | None,
) -> bool:
    """Compare source identity without consulting chunk config or corpus."""

    schema_version = getattr(document_version, "canonical_content_schema_version", None)
    if schema_version is None:
        expected_content = (
            canonical_source.content if canonical_source is not None else getattr(document_version, "content", "")
        )
        if getattr(document_version, "content_hash", None) != evidence_text_hash(expected_content):
            return False
        persisted_checksum = getattr(document_version, "source_checksum", None)
        locator = getattr(document_version, "source_locator_json", None)
        if persisted_checksum is None and isinstance(locator, Mapping):
            persisted_checksum = locator.get("source_checksum")
        return source_checksum is None or persisted_checksum is None or persisted_checksum == source_checksum
    if canonical_source is None:
        return bool(
            schema_version == "canonical_document_content.v2"
            and getattr(document_version, "source_checksum", None) == source_checksum
            and getattr(document_version, "content_hash", None)
            == evidence_text_hash(str(getattr(document_version, "content", "")))
            and isinstance(getattr(document_version, "canonical_blocks_json", None), list)
            and getattr(document_version, "canonical_blocks_hash", None) is not None
        )
    return bool(
        schema_version == canonical_source.schema_version
        and getattr(document_version, "source_checksum", None) == source_checksum
        and getattr(document_version, "content", None) == canonical_source.content
        and getattr(document_version, "content_hash", None) == canonical_source.content_hash
        and getattr(document_version, "canonical_blocks_hash", None) == canonical_source.blocks_hash
        and list(getattr(document_version, "canonical_blocks_json", []) or []) == list(canonical_source.blocks_json)
    )


def canonical_chunk_version_matches_projection(chunk_version: object, chunk: PolicyChunk) -> bool:
    """Compare replay material and assembly audit; corpus visibility is external."""

    if getattr(chunk_version, "chunk_id", None) != chunk.chunk_id:
        return False
    if getattr(chunk_version, "text_hash", None) != evidence_text_hash(chunk.content):
        return False
    locator = getattr(chunk_version, "source_locator_json", None)
    persisted_refs = locator.get("source_block_refs") if isinstance(locator, Mapping) else None
    if list(persisted_refs or []) != list(chunk.source_block_refs_json or []):
        return False
    persisted_config = getattr(chunk_version, "chunking_config_fingerprint", None)
    persisted_input_hash = getattr(chunk_version, "embedding_input_hash", None)
    persisted_token_count = getattr(chunk_version, "embedding_token_count", None)
    if persisted_config is None and persisted_input_hash is None and persisted_token_count is None:
        return True
    return bool(
        getattr(chunk_version, "content", None) == chunk.content
        and getattr(chunk_version, "search_text", None) == chunk.search_text
        and persisted_config == chunk.chunking_config_fingerprint
        and persisted_input_hash == chunk.embedding_input_hash
        and persisted_token_count == chunk.embedding_token_count
    )


class CanonicalReadCutoverBlocked(EvidenceRolloutError):
    pass


class CanonicalReadUnavailable(EvidenceRolloutError):
    """Generic fail-closed current-read error."""


@dataclass(frozen=True)
class EvidenceBackfillResult:
    watermark_sequence: int
    canonical_count: int
    resolved_count: int
    unresolved_count: int


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

    async def reserve_backfill_watermark(self, *, expected_rollout_version: int) -> int:
        """Reserve the snapshot boundary under the rollout lock.

        The caller commits after this method. Backfill then starts in a new
        transaction, leaving a deliberate writer window that final
        reconciliation must close.
        """

        row = await self.lock_rollout(
            expected_rollout_version=expected_rollout_version,
            require_dual_write=True,
        )
        self._require_current_dual_write_health(row)
        if row.backfill_watermark_sequence is not None:
            return int(row.backfill_watermark_sequence)
        watermark = await self.allocate_ingestion_sequence()
        row.backfill_watermark_sequence = watermark
        row.audit_counts_json = {
            **dict(row.audit_counts_json or {}),
            "backfill_status": "watermark_reserved",
            "backfill_watermark_sequence": watermark,
        }
        await self.session.flush()
        return watermark

    async def _active_documents_for_update(self) -> list[PolicyDocument]:
        """Lock current heads one tenant active pointer at a time."""

        tenant_ids = list(
            (
                await self.session.execute(
                    select(PolicyCorpusRollout.tenant_id).order_by(PolicyCorpusRollout.tenant_id)
                )
            ).scalars()
        )
        documents: list[PolicyDocument] = []
        for tenant_id in tenant_ids:
            await ActivePolicyCorpusScope.resolve(self.session, tenant_id=tenant_id)
            statement = join_active_document_projection(
                select(PolicyDocument).where(PolicyDocument.tenant_id == tenant_id),
                tenant_id=tenant_id,
            )
            rows = (
                await self.session.execute(
                    statement.order_by(PolicyDocument.doc_key, PolicyDocument.id).with_for_update()
                )
            ).scalars()
            documents.extend(rows)
        return documents

    async def backfill_current_heads(
        self,
        *,
        expected_rollout_version: int,
    ) -> EvidenceBackfillResult:
        """Backfill only current heads with a uniquely provable exact binding."""

        rollout = await self.lock_rollout(
            expected_rollout_version=expected_rollout_version,
            require_dual_write=True,
        )
        self._require_current_dual_write_health(rollout)
        if rollout.backfill_watermark_sequence is None:
            raise EvidenceRolloutError("backfill watermark is not reserved")
        watermark = int(rollout.backfill_watermark_sequence)
        documents = await self._active_documents_for_update()
        canonical_count = 0
        resolved_count = 0
        unresolved_count = 0
        for document in documents:
            chunks = list(
                (
                    await self.session.execute(
                        join_active_chunk_projection(
                            select(PolicyChunk).where(
                                PolicyChunk.tenant_id == document.tenant_id,
                                PolicyChunk.doc_id == document.id,
                            ),
                            tenant_id=document.tenant_id,
                        )
                        .order_by(PolicyChunk.tenant_id, PolicyChunk.doc_id, PolicyChunk.id)
                        .with_for_update()
                    )
                ).scalars()
            )
            failure = _legacy_head_failure(document, chunks)
            if failure is not None:
                _mark_legacy_unresolved(document, chunks, failure)
                unresolved_count += 1
                continue
            try:
                binding = await self.find_exact_binding(
                    tenant_id=document.tenant_id,
                    document=document,
                    chunks=chunks,
                    fingerprint=str(document.policy_version_fingerprint),
                )
            except ImmutableBindingMismatch as exc:
                _mark_legacy_unresolved(document, chunks, str(exc))
                unresolved_count += 1
                continue
            if binding is None:
                await self.append_immutable_version(
                    tenant_id=document.tenant_id,
                    document=document,
                    chunks=chunks,
                    write_sequence=document.evidence_write_sequence or watermark,
                )
                resolved_count += 1
            else:
                await self.project_write_sequence(
                    document=document,
                    chunks=chunks,
                    write_sequence=document.evidence_write_sequence or watermark,
                )
            canonical_count += 1

        rollout.audit_counts_json = {
            **dict(rollout.audit_counts_json or {}),
            "backfill_status": "snapshot_scanned",
            "canonical_count": canonical_count,
            "resolved_count": resolved_count,
            "unresolved_count": unresolved_count,
        }
        if unresolved_count:
            rollout.quarantine_reason = "legacy_unresolved"
        await self.session.flush()
        return EvidenceBackfillResult(
            watermark_sequence=watermark,
            canonical_count=canonical_count,
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
        )

    async def reconcile_and_enable_canonical_reads(
        self,
        *,
        expected_rollout_version: int,
        after_zero_gap: Callable[[], Awaitable[None]] | None = None,
    ) -> EvidenceIdentityRollout:
        """Reconcile and CAS-enable reads without releasing the rollout lock."""

        rollout = await self.lock_rollout(
            expected_rollout_version=expected_rollout_version,
            require_dual_write=True,
        )
        self._require_current_dual_write_health(rollout)
        if rollout.backfill_watermark_sequence is None:
            raise CanonicalReadCutoverBlocked("backfill watermark is not reserved")
        watermark = int(rollout.backfill_watermark_sequence)
        documents = await self._active_documents_for_update()
        canonical_count = 0
        reconciled_count = 0
        unresolved_count = 0
        binding_reused_after_watermark = 0
        reconciled_through = watermark
        for document in documents:
            chunks = list(
                (
                    await self.session.execute(
                        join_active_chunk_projection(
                            select(PolicyChunk).where(
                                PolicyChunk.tenant_id == document.tenant_id,
                                PolicyChunk.doc_id == document.id,
                            ),
                            tenant_id=document.tenant_id,
                        )
                        .order_by(PolicyChunk.tenant_id, PolicyChunk.doc_id, PolicyChunk.id)
                        .with_for_update()
                    )
                ).scalars()
            )
            sequence = document.evidence_write_sequence
            failure = _legacy_head_failure(document, chunks)
            if (
                sequence is None
                or failure is not None
                or any(chunk.evidence_write_sequence != sequence for chunk in chunks)
            ):
                _mark_legacy_unresolved(document, chunks, failure or "projection_sequence_mismatch")
                unresolved_count += 1
                continue
            try:
                binding = await self.find_exact_binding(
                    tenant_id=document.tenant_id,
                    document=document,
                    chunks=chunks,
                    fingerprint=str(document.policy_version_fingerprint),
                )
                if binding is None:
                    await self.append_immutable_version(
                        tenant_id=document.tenant_id,
                        document=document,
                        chunks=chunks,
                        write_sequence=int(sequence),
                    )
                    reconciled_count += 1
                elif int(sequence) > watermark:
                    binding_reused_after_watermark += 1
            except ImmutableBindingMismatch as exc:
                _mark_legacy_unresolved(document, chunks, str(exc))
                unresolved_count += 1
                continue
            canonical_count += 1
            reconciled_through = max(reconciled_through, int(sequence))

        counts = {
            **dict(rollout.audit_counts_json or {}),
            "backfill_status": "reconciled",
            "canonical_count": canonical_count,
            "resolved_count": reconciled_count,
            "unresolved_count": unresolved_count,
            "binding_reused_after_watermark": binding_reused_after_watermark,
            "reconciled_through_sequence": reconciled_through,
        }
        rollout.audit_counts_json = counts
        if unresolved_count:
            rollout.canonical_reads_enabled = False
            rollout.quarantine_reason = "legacy_unresolved"
            await self.session.flush()
            raise CanonicalReadCutoverBlocked("canonical evidence reconciliation has unresolved gaps")

        if after_zero_gap is not None:
            await after_zero_gap()
        now = datetime.now(UTC)
        rollout.reconciled_through_sequence = reconciled_through
        rollout.canonical_reads_enabled = True
        rollout.canonical_reads_enabled_at = now
        rollout.canonical_reads_disabled_at = None
        rollout.quarantine_reason = None
        rollout.rollout_version += 1
        await self.session.flush()
        return rollout

    async def disable_canonical_reads(
        self,
        *,
        expected_rollout_version: int,
        reason: str,
    ) -> EvidenceIdentityRollout:
        """Operationally disable current reads while immutable dual-write stays on."""

        quarantine_reason = reason.strip()
        if not quarantine_reason or len(quarantine_reason) > 500:
            raise EvidenceRolloutError("canonical read quarantine reason is invalid")
        rollout = await self.lock_rollout(
            expected_rollout_version=expected_rollout_version,
            require_dual_write=True,
        )
        now = datetime.now(UTC)
        rollout.canonical_reads_enabled = False
        rollout.canonical_reads_disabled_at = now
        rollout.quarantine_reason = quarantine_reason
        rollout.audit_counts_json = {
            **dict(rollout.audit_counts_json or {}),
            "canonical_read_status": "disabled",
            "canonical_reads_disabled_at": now.isoformat(),
            "quarantine_reason": quarantine_reason,
        }
        rollout.rollout_version += 1
        await self.session.flush()
        return rollout

    async def get_current_identities_by_keys(
        self,
        *,
        tenant_id: UUID,
        keys: Sequence[tuple[str, str]],
    ) -> dict[tuple[str, str], CanonicalEvidenceIdentityV1]:
        """Mint exact identities for current heads under an enabled rollout epoch."""

        if not keys:
            return {}
        rollout_version = await self._require_canonical_reads_enabled()
        requested = set(keys)
        rows = list(
            (
                await self.session.execute(
                    join_active_chunk_projection(
                        select(PolicyDocument, PolicyChunk, PolicyChunkVersion).join(
                            PolicyChunk,
                            (PolicyChunk.tenant_id == tenant_id) & (PolicyChunk.doc_id == PolicyDocument.id),
                        ),
                        tenant_id=tenant_id,
                    )
                    .join(
                        PolicyChunkVersion,
                        (PolicyChunkVersion.tenant_id == tenant_id)
                        & (PolicyChunkVersion.id == CorpusChunkBinding.policy_chunk_version_id)
                        & (
                            PolicyChunkVersion.policy_document_version_id
                            == CorpusDocumentBinding.policy_document_version_id
                        ),
                    )
                    .where(
                        PolicyDocument.tenant_id == tenant_id,
                        PolicyDocument.doc_key.in_({doc_key for doc_key, _ in requested}),
                    )
                )
            ).all()
        )
        identities: dict[tuple[str, str], CanonicalEvidenceIdentityV1] = {}
        for document, current_chunk, immutable_chunk in rows:
            key = (document.doc_key, current_chunk.chunk_id)
            if key not in requested:
                continue
            if not canonical_chunk_version_matches_projection(immutable_chunk, current_chunk):
                raise CanonicalReadUnavailable("canonical evidence unavailable")
            resolution = await self.mint_for_chunk_version(
                immutable_chunk,
                expected_tenant_id=tenant_id,
                expected_scope_type=ACCEPTED_POLICY_SCOPE_TYPE,
                expected_scope_id=str(tenant_id),
            )
            if resolution.identity is None or key in identities:
                raise CanonicalReadUnavailable("canonical evidence unavailable")
            identities[key] = resolution.identity
        if set(identities) != requested:
            raise CanonicalReadUnavailable("canonical evidence unavailable")
        if await self._require_canonical_reads_enabled() != rollout_version:
            raise CanonicalReadUnavailable("canonical evidence unavailable")
        return identities

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
        canonical_source: CanonicalDocumentContentV2 | None = None,
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
        if not canonical_document_version_matches_source(
            document_version,
            source_checksum=document.source_checksum,
            canonical_source=canonical_source,
        ) or (
            canonical_source is None
            and (
                document_version.content != document.content
                or document_version.content_hash != evidence_text_hash(document.content)
            )
        ):
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
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ImmutableBindingMismatch("ambiguous current chunk binding")
        compatible_chunks: list[PolicyChunkVersion] = []
        for chunk in chunks:
            matches = [row for row in immutable_chunks if canonical_chunk_version_matches_projection(row, chunk)]
            if not matches:
                return None
            compatible_chunks.append(max(matches, key=lambda row: row.chunk_version))
        return document_version, compatible_chunks

    async def append_immutable_version(
        self,
        *,
        tenant_id: UUID,
        document: PolicyDocument,
        chunks: Sequence[PolicyChunk],
        write_sequence: int,
        canonical_source: CanonicalDocumentContentV2 | None = None,
        correction_of_document_version_id: str | UUID | None = None,
        retention_until: datetime | None = None,
        project_current_head: bool = True,
    ) -> tuple[PolicyDocumentVersion, list[PolicyChunkVersion]]:
        """Append one document version and one row per produced chunk."""

        scope_id = str(tenant_id)
        document_version_number = int(document.version or 1)
        existing_document = (
            await self.session.execute(
                select(PolicyDocumentVersion).where(
                    PolicyDocumentVersion.tenant_id == tenant_id,
                    PolicyDocumentVersion.scope_type == ACCEPTED_POLICY_SCOPE_TYPE,
                    PolicyDocumentVersion.scope_id == scope_id,
                    PolicyDocumentVersion.doc_key == document.doc_key,
                    PolicyDocumentVersion.document_version == document_version_number,
                )
            )
        ).scalar_one_or_none()
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
        if existing_document is not None:
            if correction_id is not None or not canonical_document_version_matches_source(
                existing_document,
                source_checksum=document.source_checksum,
                canonical_source=canonical_source,
            ):
                raise ImmutableBindingMismatch("immutable document source mismatch")
            document_row = existing_document
        else:
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
                source_checksum=document.source_checksum if canonical_source is not None else None,
                canonical_content_schema_version=(canonical_source.schema_version if canonical_source else None),
                canonical_blocks_json=(list(canonical_source.blocks_json) if canonical_source else None),
                canonical_blocks_hash=(canonical_source.blocks_hash if canonical_source else None),
                source_locator_json=_document_source_locator(document),
                lifecycle_status="corrected" if correction_id is not None else "active",
                retention_until=retained_until,
                supersedes_version_id=previous_document.id if previous_document is not None else None,
                corrects_version_id=correction_id,
            )
            self.session.add(document_row)
            await self.session.flush()

        prior_chunk_rows = list(
            (
                await self.session.execute(
                    select(PolicyChunkVersion).where(
                        PolicyChunkVersion.tenant_id == tenant_id,
                        PolicyChunkVersion.policy_document_version_id == document_row.id,
                    )
                )
            ).scalars()
        )

        chunk_rows: list[PolicyChunkVersion] = []
        for chunk in sorted(chunks, key=lambda item: (str(item.chunk_id), str(item.id))):
            same_logical_chunk = [row for row in prior_chunk_rows if row.chunk_id == chunk.chunk_id]
            compatible_chunk = next(
                (
                    row
                    for row in sorted(same_logical_chunk, key=lambda item: item.chunk_version, reverse=True)
                    if canonical_chunk_version_matches_projection(row, chunk)
                ),
                None,
            )
            if compatible_chunk is not None:
                chunk_rows.append(compatible_chunk)
                continue
            previous_chunk = max(same_logical_chunk, key=lambda item: item.chunk_version, default=None)
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
                search_text=chunk.search_text,
                embedding=chunk.embedding,
                chunking_config_fingerprint=chunk.chunking_config_fingerprint,
                embedding_input_hash=chunk.embedding_input_hash,
                embedding_token_count=chunk.embedding_token_count,
                source_locator_json=_chunk_source_locator(document, chunk),
                lifecycle_status="corrected" if correction_id is not None else "active",
                retention_until=retained_until,
                supersedes_version_id=previous_chunk.id if previous_chunk is not None else None,
                corrects_version_id=previous_chunk.id if correction_id is not None and previous_chunk else None,
            )
            chunk_rows.append(row)
        self.session.add_all([row for row in chunk_rows if row not in prior_chunk_rows])
        await self.session.flush()
        if project_current_head:
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

    async def resolve_immutable_evidence(
        self,
        candidate: object,
        *,
        expected_tenant_id: UUID | str,
        expected_scope_type: str,
        expected_scope_id: str,
    ) -> CanonicalEvidenceResolutionV1:
        """Resolve canonical/hash input against exact retained immutable rows."""

        tenant_id = UUID(str(expected_tenant_id))
        candidates = await self._candidate_material(candidate, tenant_id=tenant_id)
        resolution = resolve_evidence_identity(
            candidate,  # type: ignore[arg-type]
            candidates,
            expected_tenant_id=str(tenant_id),
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )
        if resolution.status is EvidenceIdentityResolutionStatus.LEGACY_RESOLVED:
            return _generic_resolution_failure(EvidenceIdentityInternalReason.MALFORMED)
        return resolution

    async def resolve_exact(
        self,
        candidate: object,
        *,
        expected_tenant_id: UUID | str,
        expected_scope_type: str,
        expected_scope_id: str,
    ) -> CanonicalEvidenceResolutionV1:
        """Compatibility name for exact immutable resolution; aliases are excluded."""

        return await self.resolve_immutable_evidence(
            candidate,
            expected_tenant_id=expected_tenant_id,
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )

    async def resolve_legacy_alias(
        self,
        alias: str,
        *,
        expected_tenant_id: UUID | str,
        expected_scope_type: str,
        expected_scope_id: str,
    ) -> CanonicalEvidenceResolutionV1:
        """Explicitly upgrade one uniquely provable legacy display alias."""

        tenant_id = UUID(str(expected_tenant_id))
        candidates = await self._candidate_material(alias, tenant_id=tenant_id)
        resolution = resolve_evidence_identity(
            alias,
            candidates,
            expected_tenant_id=str(tenant_id),
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )
        if resolution.status is not EvidenceIdentityResolutionStatus.LEGACY_RESOLVED:
            return resolution
        return resolution

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

    @staticmethod
    def evidence_ref_from_identity(
        identity: CanonicalEvidenceIdentityV1,
        *,
        retrieved_at: str,
        retrieval_config_version: str = "retrieval.v3",
        score: float | None = None,
        rank: int | None = None,
    ):
        """Project only an owner-minted identity into the public ref schema."""

        from src.knowledge.schemas import EvidenceRefV1

        return EvidenceRefV1.from_canonical_identity(
            identity,
            retrieved_at=retrieved_at,
            retrieval_config_version=retrieval_config_version,
            score=score,
            rank=rank,
        )

    @staticmethod
    def legacy_ref_for_compatibility(
        *,
        tenant_id: str,
        doc_key: str,
        chunk_id: str,
        policy_version: str,
        text_value: str,
        retrieved_at: str,
        retrieval_config_version: str,
        score: float | None,
        rank: int | None,
    ):
        """Explicit adapter for persisted legacy/test-only mutable sources."""

        from src.knowledge.schemas import EvidenceRefV1

        return EvidenceRefV1.build(
            tenant_id=tenant_id,
            doc_key=doc_key,
            chunk_id=chunk_id,
            policy_version=policy_version,
            text=text_value,
            retrieved_at=retrieved_at,
            retrieval_config_version=retrieval_config_version,
            score=score,
            rank=rank,
        )

    async def _candidate_material(
        self,
        candidate: object,
        *,
        tenant_id: UUID,
    ) -> list[PersistedEvidenceIdentityMaterialV1]:
        statement = select(PolicyChunkVersion).where(PolicyChunkVersion.tenant_id == tenant_id)
        candidate_id = (
            candidate.get("chunk_version_id")
            if isinstance(candidate, Mapping)
            else getattr(candidate, "chunk_version_id", None)
        )
        if candidate_id:
            statement = statement.where(PolicyChunkVersion.id == UUID(str(candidate_id)))
        rows = list((await self.session.execute(statement)).scalars())
        return [_material_from_chunk(row) for row in rows]

    async def _require_canonical_reads_enabled(self) -> int:
        row = (
            await self.session.execute(
                select(EvidenceIdentityRollout)
                .where(EvidenceIdentityRollout.id == ROLLOUT_ID)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if row is None or not row.canonical_reads_enabled or row.quarantine_reason is not None:
            raise CanonicalReadUnavailable("canonical evidence unavailable")
        return int(row.rollout_version)

    def _require_current_dual_write_health(self, row: EvidenceIdentityRollout) -> None:
        audit = dict(row.audit_counts_json or {})
        if audit.get("dual_write_health") != "healthy":
            raise DualWriteUnavailable("dual-write health proof is unavailable")
        raw_checked_at = audit.get("dual_write_health_checked_at")
        if not isinstance(raw_checked_at, str):
            raise DualWriteUnavailable("dual-write health proof is unavailable")
        try:
            checked_at = _as_utc(datetime.fromisoformat(raw_checked_at))
        except ValueError as exc:
            raise DualWriteUnavailable("dual-write health proof is invalid") from exc
        if datetime.now(UTC) - checked_at > DUAL_WRITE_HEALTH_MAX_AGE:
            raise DualWriteUnavailable("dual-write health proof is stale")


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


def _legacy_head_failure(document: PolicyDocument, chunks: Sequence[PolicyChunk]) -> str | None:
    if not document.policy_version_fingerprint:
        return "missing_document_fingerprint"
    expected_fingerprint = build_policy_version_fingerprint(
        citation_text=document.content,
        title=document.title,
        doc_type=document.doc_type,
        risk_level=document.risk_level,
        effective_date=document.effective_date,
    )
    if document.policy_version_fingerprint != expected_fingerprint:
        return "document_fingerprint_mismatch"
    if not chunks:
        return "missing_chunks"
    logical_ids = [chunk.chunk_id for chunk in chunks]
    if len(logical_ids) != len(set(logical_ids)):
        return "ambiguous_logical_chunk"
    ordered_chunks = sorted(chunks, key=lambda chunk: (chunk.chunk_id, str(chunk.id)))
    if "\n\n".join(chunk.content for chunk in ordered_chunks).strip() != document.content.strip():
        return "document_chunk_content_mismatch"
    if any(not evidence_text_hash(chunk.content) for chunk in chunks):  # pragma: no cover - defensive
        return "chunk_hash_unavailable"
    return None


def _mark_legacy_unresolved(
    document: PolicyDocument,
    chunks: Sequence[PolicyChunk],
    reason: str,
) -> None:
    document.parser_metadata_json = {
        **dict(document.parser_metadata_json or {}),
        "evidence_identity_resolution": "legacy_unresolved",
        "evidence_identity_reason": reason,
    }
    for chunk in chunks:
        chunk.ocr_metadata_json = {
            **dict(chunk.ocr_metadata_json or {}),
            "evidence_identity_resolution": "legacy_unresolved",
            "evidence_identity_reason": reason,
        }


def _generic_resolution_failure(reason: EvidenceIdentityInternalReason) -> CanonicalEvidenceResolutionV1:
    return CanonicalEvidenceResolutionV1(
        status=EvidenceIdentityResolutionStatus.INVALID,
        internal_reason=reason,
        external_reason=EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE,
    )
