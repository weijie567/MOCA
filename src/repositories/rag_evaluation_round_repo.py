"""Fail-closed persistence boundary for RAG format-parity evaluation rounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import re
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    DocumentBlock,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
    RagEvaluationRound,
    RagIngestionJob,
)
from src.repositories.document_block_repo import DocumentBlockRepository
from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.rag_ingestion_job_repo import (
    RagIngestionJobRepository,
    canonical_ingestion_source_checksum,
)


FORMAT_PARITY_TENANT_ID = UUID("64300000-0000-4000-8000-000000000001")
FORMAT_PARITY_OWNER_MARKER = "moca.rag_format_parity.v1"
FORMAT_PARITY_DOC_KEYS = (
    "eval_refund_eligibility_and_return",
    "eval_quality_compensation_and_approval",
    "eval_cross_border_and_digital_goods",
)
ROUND_FORMATS = ("markdown", "digital_pdf", "scanned_pdf")
TERMINAL_STATES = frozenset({"completed", "abandoned"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvaluationIsolationError(RuntimeError):
    """One external denial with a stable internal reason for safe diagnostics."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("evaluation isolation denied")


@dataclass(frozen=True)
class EvaluationRoundIdentity:
    round_id: UUID
    tenant_id: UUID
    owner_marker: str
    run_token: UUID
    round_token: UUID
    round_format: str
    state_version: int
    next_document_index: int
    expected_rollout_version: int = 1

    def __post_init__(self) -> None:
        if (
            self.tenant_id != FORMAT_PARITY_TENANT_ID
            or self.owner_marker != FORMAT_PARITY_OWNER_MARKER
            or self.run_token.int == 0
            or self.round_token.int == 0
            or self.round_format not in ROUND_FORMATS
        ):
            raise EvaluationIsolationError("identity_mismatch")
        if self.state_version <= 0 or self.expected_rollout_version <= 0:
            raise EvaluationIsolationError("stale_state")
        if not 0 <= self.next_document_index <= len(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("stale_progress")


class ProjectionState(StrEnum):
    RESERVATION_ONLY = "reservation_only"
    JOB_ONLY = "job_only"
    FAILURE = "failure"
    EXACT_COMPLETE = "exact_complete"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class AttemptProjection:
    head_count: int = 0
    matching_head_count: int = 0
    block_count: int = 0
    chunk_count: int = 0
    immutable_document_count: int = 0
    immutable_chunk_count: int = 0
    canonical_binding_count: int = 0
    job_count: int = 0
    null_doc_job_count: int = 0
    success_job_count: int = 0
    failed_job_count: int = 0


@dataclass(frozen=True)
class ProjectionInspection:
    state: ProjectionState
    projection: AttemptProjection
    document_id: UUID | None
    job_id: UUID | None
    job_error_code: str | None
    head_mapping: dict[str, str]
    immutable_counts: dict[str, int]


@dataclass(frozen=True)
class RoundProgress:
    state: str
    has_attempt_reservation: bool


def classify_attempt_projection(projection: AttemptProjection) -> ProjectionState:
    """Classify only commit states supported by production ingestion."""

    counts = tuple(vars(projection).values())
    if any(value < 0 for value in counts):
        return ProjectionState.MALFORMED
    if projection.head_count > 1 or projection.matching_head_count > projection.head_count:
        return ProjectionState.MALFORMED
    if projection.job_count > 1:
        return ProjectionState.MALFORMED
    if not projection.job_count:
        if not projection.block_count and not projection.chunk_count and not projection.canonical_binding_count:
            return ProjectionState.RESERVATION_ONLY
        return ProjectionState.MALFORMED
    if projection.failed_job_count == 1:
        if projection.success_job_count or projection.block_count or projection.chunk_count:
            return ProjectionState.MALFORMED
        return ProjectionState.FAILURE
    if projection.null_doc_job_count == 1:
        if projection.success_job_count or projection.block_count or projection.chunk_count:
            return ProjectionState.MALFORMED
        return ProjectionState.JOB_ONLY
    exact_complete = (
        projection.job_count == 1
        and projection.success_job_count == 1
        and projection.matching_head_count == 1
        and projection.block_count > 0
        and projection.chunk_count > 0
        and projection.immutable_document_count >= 1
        and projection.immutable_chunk_count >= projection.chunk_count
        and projection.canonical_binding_count == projection.chunk_count
    )
    return ProjectionState.EXACT_COMPLETE if exact_complete else ProjectionState.MALFORMED


class RagEvaluationRoundRepository:
    """Every public mutation locks, proves, and CAS-updates one owner row."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = RagIngestionJobRepository(session)
        self.block_repo = DocumentBlockRepository(session)
        self.chunk_repo = PolicyChunkRepository(session)

    async def create_round(
        self,
        *,
        run_token: UUID,
        round_token: UUID,
        round_format: str,
        lease_expires_at: datetime,
        expected_rollout_version: int = 1,
    ) -> EvaluationRoundIdentity:
        identity = EvaluationRoundIdentity(
            round_id=uuid4(),
            tenant_id=FORMAT_PARITY_TENANT_ID,
            owner_marker=FORMAT_PARITY_OWNER_MARKER,
            run_token=run_token,
            round_token=round_token,
            round_format=round_format,
            state_version=1,
            next_document_index=0,
            expected_rollout_version=expected_rollout_version,
        )
        row = RagEvaluationRound(
            id=identity.round_id,
            tenant_id=identity.tenant_id,
            owner_marker=identity.owner_marker,
            run_token=identity.run_token,
            round_token=identity.round_token,
            round_format=identity.round_format,
            doc_keys_json=list(FORMAT_PARITY_DOC_KEYS),
            state="claimed",
            state_version=1,
            expected_rollout_version=expected_rollout_version,
            next_document_index=0,
            next_step="preflight",
            lease_expires_at=lease_expires_at,
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError:
            raise EvaluationIsolationError("active_round_conflict") from None
        return identity

    async def lock_owned(
        self,
        owner: EvaluationRoundIdentity,
        *,
        allowed_states: frozenset[str] | None = None,
    ) -> RagEvaluationRound:
        stmt = (
            select(RagEvaluationRound)
            .where(RagEvaluationRound.id == owner.round_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise EvaluationIsolationError("owner_unavailable")
        self._assert_owned(row, owner)
        if allowed_states is not None and row.state not in allowed_states:
            raise EvaluationIsolationError("state_mismatch")
        return row

    async def read_progress(self, owner: EvaluationRoundIdentity) -> RoundProgress:
        row = await self.lock_owned(owner)
        return RoundProgress(
            state=row.state,
            has_attempt_reservation=row.attempt_doc_key is not None,
        )

    async def prove_compatible_pre_state(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"claimed"}))
        heads = await self._lock_tenant_heads()
        current_counts = await self._current_counts(heads)
        if current_counts["blocks"] or current_counts["chunks"] or current_counts["jobs"]:
            raise EvaluationIsolationError("pre_state_not_clean")
        immutable = await self._immutable_counts()
        head_mapping = {head.doc_key: str(head.id) for head in heads}
        return await self._cas(
            row,
            owner,
            state="ingesting",
            next_step="ingest",
            pre_state_proof_json={"current": current_counts, "head_keys": list(head_mapping)},
            head_mappings_json=head_mapping,
            immutable_counts_json=immutable,
        )

    async def reserve_document(
        self,
        owner: EvaluationRoundIdentity,
        *,
        doc_key: str,
        source_checksum: str,
        reserved_at: datetime,
    ) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"ingesting"}))
        expected_key = FORMAT_PARITY_DOC_KEYS[owner.next_document_index] if owner.next_document_index < 3 else None
        if doc_key != expected_key:
            raise EvaluationIsolationError("document_order_mismatch")
        if not _SHA256.fullmatch(source_checksum):
            raise EvaluationIsolationError("source_checksum_invalid")
        if row.attempt_doc_key is not None:
            if row.attempt_doc_key != doc_key or row.expected_source_checksum != source_checksum:
                raise EvaluationIsolationError("attempt_mismatch")
            return owner
        return await self._cas(
            row,
            owner,
            attempt_doc_key=doc_key,
            expected_source_checksum=source_checksum,
            reservation_at=reserved_at,
            claimed_job_id=None,
        )

    async def inspect_attempt(self, owner: EvaluationRoundIdentity) -> ProjectionInspection:
        row = await self.lock_owned(owner, allowed_states=frozenset({"ingesting"}))
        if not row.attempt_doc_key or not row.expected_source_checksum or row.reservation_at is None:
            raise EvaluationIsolationError("reservation_missing")
        return await self._inspect_locked(row)

    async def claim_attempt_job(
        self,
        owner: EvaluationRoundIdentity,
        *,
        require_null_document: bool,
    ) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"ingesting"}))
        if not row.attempt_doc_key or not row.expected_source_checksum or row.reservation_at is None:
            raise EvaluationIsolationError("reservation_missing")
        if require_null_document:
            jobs = await self.job_repo.lock_evaluation_attempt_candidates(
                tenant_id=row.tenant_id,
                doc_key=row.attempt_doc_key,
                source_checksum=row.expected_source_checksum,
                reserved_at=row.reservation_at,
            )
        else:
            jobs = await self.job_repo.lock_all_evaluation_attempt_jobs(
                tenant_id=row.tenant_id,
                doc_key=row.attempt_doc_key,
                source_checksum=row.expected_source_checksum,
                reserved_at=row.reservation_at,
            )
        if len(jobs) != 1:
            raise EvaluationIsolationError("attempt_job_cardinality")
        return await self._cas(row, owner, claimed_job_id=jobs[0].id)

    async def retry_attempt(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        """Delete one previously CAS-claimed job and retry the same cursor."""

        row = await self.lock_owned(owner, allowed_states=frozenset({"ingesting"}))
        inspection = await self._inspect_locked(row)
        if inspection.state not in {ProjectionState.JOB_ONLY, ProjectionState.FAILURE}:
            raise EvaluationIsolationError("attempt_not_retryable")
        if row.claimed_job_id is None or row.claimed_job_id != inspection.job_id:
            raise EvaluationIsolationError("attempt_job_not_claimed")
        deleted = await self.job_repo.delete_exact_evaluation_attempt(
            job_id=row.claimed_job_id,
            tenant_id=row.tenant_id,
            doc_key=row.attempt_doc_key or "",
            source_checksum=row.expected_source_checksum or "",
        )
        if deleted != 1:
            raise EvaluationIsolationError("attempt_job_delete_mismatch")
        return await self._cas(
            row,
            owner,
            claimed_job_id=None,
            attempt_doc_key=None,
            expected_source_checksum=None,
            reservation_at=None,
            failure_code=None,
            safe_message=None,
        )

    async def advance_exact_complete(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"ingesting"}))
        inspection = await self._inspect_locked(row)
        if inspection.state is not ProjectionState.EXACT_COMPLETE:
            raise EvaluationIsolationError("projection_not_complete")
        if row.claimed_job_id is None or row.claimed_job_id != inspection.job_id:
            raise EvaluationIsolationError("attempt_job_not_claimed")
        deleted = await self.job_repo.delete_exact_evaluation_attempt(
            job_id=row.claimed_job_id,
            tenant_id=row.tenant_id,
            doc_key=row.attempt_doc_key or "",
            source_checksum=row.expected_source_checksum or "",
        )
        if deleted != 1:
            raise EvaluationIsolationError("attempt_job_delete_mismatch")
        next_index = owner.next_document_index + 1
        state = "retrieving" if next_index == len(FORMAT_PARITY_DOC_KEYS) else "ingesting"
        next_step = "retrieve" if state == "retrieving" else "ingest"
        mappings = dict(row.head_mappings_json)
        mappings.update(inspection.head_mapping)
        return await self._cas(
            row,
            owner,
            state=state,
            next_step=next_step,
            next_document_index=next_index,
            claimed_job_id=None,
            attempt_doc_key=None,
            expected_source_checksum=None,
            reservation_at=None,
            head_mappings_json=mappings,
            immutable_counts_json=inspection.immutable_counts,
        )

    async def advance_exact_failed_quality(
        self,
        owner: EvaluationRoundIdentity,
        *,
        error_code: str,
    ) -> EvaluationRoundIdentity:
        """Advance one controlled scanned-PDF failure after exact cleanup proof."""

        if owner.round_format != "scanned_pdf" or error_code != "malformed_source":
            raise EvaluationIsolationError("quality_failure_not_allowed")
        row = await self.lock_owned(owner, allowed_states=frozenset({"ingesting"}))
        inspection = await self._inspect_locked(row)
        if inspection.state is not ProjectionState.FAILURE:
            raise EvaluationIsolationError("quality_failure_projection_mismatch")
        if inspection.job_error_code != error_code:
            raise EvaluationIsolationError("quality_failure_code_mismatch")
        if row.claimed_job_id is None or row.claimed_job_id != inspection.job_id:
            raise EvaluationIsolationError("attempt_job_not_claimed")
        deleted = await self.job_repo.delete_exact_evaluation_attempt(
            job_id=row.claimed_job_id,
            tenant_id=row.tenant_id,
            doc_key=row.attempt_doc_key or "",
            source_checksum=row.expected_source_checksum or "",
        )
        if deleted != 1:
            raise EvaluationIsolationError("attempt_job_delete_mismatch")
        residual = await self._inspect_locked(row)
        if residual.state is not ProjectionState.RESERVATION_ONLY or any(
            (
                residual.projection.job_count,
                residual.projection.block_count,
                residual.projection.chunk_count,
                residual.projection.canonical_binding_count,
            )
        ):
            raise EvaluationIsolationError("quality_failure_residual")
        recorded_immutable = {
            key: int(value) for key, value in row.immutable_counts_json.items() if isinstance(value, int)
        }
        if any(residual.immutable_counts.get(key, 0) < value for key, value in recorded_immutable.items()):
            raise EvaluationIsolationError("immutable_history_regressed")
        next_index = owner.next_document_index + 1
        state = "cleaning" if next_index == len(FORMAT_PARITY_DOC_KEYS) else "ingesting"
        next_step = "cleanup" if state == "cleaning" else "ingest"
        return await self._cas(
            row,
            owner,
            state=state,
            next_step=next_step,
            next_document_index=next_index,
            claimed_job_id=None,
            attempt_doc_key=None,
            expected_source_checksum=None,
            reservation_at=None,
            immutable_counts_json=residual.immutable_counts,
        )

    async def prove_retrieval_ready(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"retrieving"}))
        if owner.next_document_index != len(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("retrieval_progress_incomplete")
        heads = await self._lock_tenant_heads()
        current = await self._current_counts(heads)
        if len(heads) != 3 or current["blocks"] <= 0 or current["chunks"] <= 0 or current["jobs"]:
            raise EvaluationIsolationError("retrieval_projection_invalid")
        return await self._cas(row, owner, state="cleaning", next_step="cleanup")

    async def cleanup_current_projection(
        self,
        owner: EvaluationRoundIdentity,
        *,
        terminal_state: Literal["completed", "abandoned"],
        failure_code: str | None = None,
    ) -> EvaluationRoundIdentity:
        allowed = frozenset({"cleaning", "expired", "ingesting", "retrieving"})
        row = await self.lock_owned(owner, allowed_states=allowed)
        heads = await self._lock_tenant_heads()
        before_immutable = await self._immutable_counts()
        recorded = {key: int(value) for key, value in row.immutable_counts_json.items() if isinstance(value, int)}
        if any(before_immutable.get(key, 0) < value for key, value in recorded.items()):
            raise EvaluationIsolationError("immutable_history_regressed")
        for head in heads:
            await self.block_repo.delete_by_document_id(head.id, row.tenant_id)
            await self.chunk_repo.delete_by_document_id(head.id, row.tenant_id)
        current = await self._current_counts(heads)
        if current["blocks"] or current["chunks"] or current["jobs"]:
            raise EvaluationIsolationError("post_cleanup_residual")
        after_immutable = await self._immutable_counts()
        if any(after_immutable[key] < before_immutable[key] for key in before_immutable):
            raise EvaluationIsolationError("immutable_history_regressed")
        return await self._cas(
            row,
            owner,
            state=terminal_state,
            next_step="done",
            post_state_proof_json={"current": current, "head_keys": [head.doc_key for head in heads]},
            immutable_counts_json=after_immutable,
            failure_code=failure_code,
            safe_message="evaluation round completed"
            if terminal_state == "completed"
            else "evaluation round abandoned",
            terminal_at=datetime.now(UTC),
            claimed_job_id=None,
            attempt_doc_key=None,
            expected_source_checksum=None,
            reservation_at=None,
        )

    async def expire_claim(self, owner: EvaluationRoundIdentity, *, now: datetime) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner)
        if row.state in TERMINAL_STATES or row.lease_expires_at > now:
            raise EvaluationIsolationError("claim_not_expirable")
        return await self._cas(row, owner, state="expired", failure_code="lease_expired")

    async def _inspect_locked(self, row: RagEvaluationRound) -> ProjectionInspection:
        doc_key = row.attempt_doc_key
        checksum = row.expected_source_checksum
        reserved_at = row.reservation_at
        if doc_key is None or checksum is None or reserved_at is None:
            raise EvaluationIsolationError("reservation_missing")
        persisted_checksum = canonical_ingestion_source_checksum(checksum)
        head_rows = (
            (
                await self.session.execute(
                    select(PolicyDocument)
                    .where(PolicyDocument.tenant_id == row.tenant_id, PolicyDocument.doc_key == doc_key)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if len(head_rows) > 1:
            raise EvaluationIsolationError("head_cardinality")
        head = head_rows[0] if head_rows else None
        jobs = await self.job_repo.lock_all_evaluation_attempt_jobs(
            tenant_id=row.tenant_id,
            doc_key=doc_key,
            source_checksum=checksum,
            reserved_at=reserved_at,
        )
        blocks: list[DocumentBlock] = []
        chunks: list[PolicyChunk] = []
        document_versions: list[PolicyDocumentVersion] = []
        chunk_versions: list[PolicyChunkVersion] = []
        if head is not None:
            blocks = list(
                (
                    await self.session.execute(
                        select(DocumentBlock).where(
                            DocumentBlock.tenant_id == row.tenant_id,
                            DocumentBlock.doc_id == head.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            chunks = list(
                (
                    await self.session.execute(
                        select(PolicyChunk)
                        .where(PolicyChunk.tenant_id == row.tenant_id, PolicyChunk.doc_id == head.id)
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            document_versions = list(
                (
                    await self.session.execute(
                        select(PolicyDocumentVersion).where(
                            PolicyDocumentVersion.tenant_id == row.tenant_id,
                            PolicyDocumentVersion.policy_document_id == head.id,
                            PolicyDocumentVersion.doc_key == doc_key,
                            PolicyDocumentVersion.document_version == head.version,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if document_versions:
                chunk_versions = list(
                    (
                        await self.session.execute(
                            select(PolicyChunkVersion).where(
                                PolicyChunkVersion.tenant_id == row.tenant_id,
                                PolicyChunkVersion.policy_document_version_id == document_versions[0].id,
                                PolicyChunkVersion.doc_key == doc_key,
                                PolicyChunkVersion.document_version == head.version,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
        chunk_ids = {chunk.chunk_id for chunk in chunks}
        bound_ids = {chunk.chunk_id for chunk in chunk_versions}
        projection = AttemptProjection(
            head_count=len(head_rows),
            matching_head_count=int(head is not None and head.source_checksum == persisted_checksum),
            block_count=len(blocks),
            chunk_count=len(chunks),
            immutable_document_count=len(document_versions),
            immutable_chunk_count=len(chunk_versions),
            canonical_binding_count=len(chunk_ids & bound_ids),
            job_count=len(jobs),
            null_doc_job_count=sum(job.doc_id is None for job in jobs),
            success_job_count=sum(job.status == "success" for job in jobs),
            failed_job_count=sum(job.status == "failed" for job in jobs),
        )
        immutable = await self._immutable_counts()
        return ProjectionInspection(
            state=classify_attempt_projection(projection),
            projection=projection,
            document_id=head.id if head is not None else None,
            job_id=jobs[0].id if len(jobs) == 1 else None,
            job_error_code=getattr(jobs[0], "error_code", None) if len(jobs) == 1 else None,
            head_mapping={doc_key: str(head.id)} if head is not None else {},
            immutable_counts=immutable,
        )

    async def _lock_tenant_heads(self) -> list[PolicyDocument]:
        heads = list(
            (
                await self.session.execute(
                    select(PolicyDocument)
                    .where(PolicyDocument.tenant_id == FORMAT_PARITY_TENANT_ID)
                    .order_by(PolicyDocument.doc_key, PolicyDocument.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if any(head.doc_key not in FORMAT_PARITY_DOC_KEYS for head in heads):
            raise EvaluationIsolationError("extra_document_state")
        if len({head.doc_key for head in heads}) != len(heads):
            raise EvaluationIsolationError("duplicate_document_state")
        return heads

    async def _current_counts(self, heads: list[PolicyDocument]) -> dict[str, int]:
        document_ids = [head.id for head in heads]
        if not document_ids:
            return {"documents": 0, "blocks": 0, "chunks": 0, "jobs": 0}
        blocks = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(DocumentBlock)
                    .where(
                        DocumentBlock.tenant_id == FORMAT_PARITY_TENANT_ID,
                        DocumentBlock.doc_id.in_(document_ids),
                    )
                )
            ).scalar_one()
        )
        chunks = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(PolicyChunk)
                    .where(
                        PolicyChunk.tenant_id == FORMAT_PARITY_TENANT_ID,
                        PolicyChunk.doc_id.in_(document_ids),
                    )
                )
            ).scalar_one()
        )
        jobs = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(RagIngestionJob)
                    .where(
                        RagIngestionJob.tenant_id == FORMAT_PARITY_TENANT_ID,
                        RagIngestionJob.doc_key.in_(FORMAT_PARITY_DOC_KEYS),
                    )
                )
            ).scalar_one()
        )
        return {"documents": len(heads), "blocks": blocks, "chunks": chunks, "jobs": jobs}

    async def _immutable_counts(self) -> dict[str, int]:
        documents = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(PolicyDocumentVersion)
                    .where(PolicyDocumentVersion.tenant_id == FORMAT_PARITY_TENANT_ID)
                )
            ).scalar_one()
        )
        chunks = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(PolicyChunkVersion)
                    .where(PolicyChunkVersion.tenant_id == FORMAT_PARITY_TENANT_ID)
                )
            ).scalar_one()
        )
        return {"document_versions": documents, "chunk_versions": chunks}

    async def _cas(
        self,
        row: RagEvaluationRound,
        owner: EvaluationRoundIdentity,
        **values: Any,
    ) -> EvaluationRoundIdentity:
        next_version = owner.state_version + 1
        result = await self.session.execute(
            update(RagEvaluationRound)
            .where(
                RagEvaluationRound.id == row.id,
                RagEvaluationRound.tenant_id == FORMAT_PARITY_TENANT_ID,
                RagEvaluationRound.owner_marker == FORMAT_PARITY_OWNER_MARKER,
                RagEvaluationRound.run_token == owner.run_token,
                RagEvaluationRound.round_token == owner.round_token,
                RagEvaluationRound.round_format == owner.round_format,
                RagEvaluationRound.state_version == owner.state_version,
                RagEvaluationRound.expected_rollout_version == owner.expected_rollout_version,
                RagEvaluationRound.next_document_index == owner.next_document_index,
            )
            .values(**values, state_version=next_version, updated_at=func.now())
        )
        if (result.rowcount or 0) != 1:
            raise EvaluationIsolationError("cas_conflict")
        return EvaluationRoundIdentity(
            round_id=owner.round_id,
            tenant_id=owner.tenant_id,
            owner_marker=owner.owner_marker,
            run_token=owner.run_token,
            round_token=owner.round_token,
            round_format=owner.round_format,
            state_version=next_version,
            next_document_index=int(values.get("next_document_index", owner.next_document_index)),
            expected_rollout_version=owner.expected_rollout_version,
        )

    @staticmethod
    def _assert_owned(row: RagEvaluationRound, owner: EvaluationRoundIdentity) -> None:
        actual_identity = (
            row.tenant_id,
            row.owner_marker,
            row.run_token,
            row.round_token,
            row.round_format,
            row.expected_rollout_version,
        )
        expected_identity = (
            owner.tenant_id,
            owner.owner_marker,
            owner.run_token,
            owner.round_token,
            owner.round_format,
            owner.expected_rollout_version,
        )
        if actual_identity != expected_identity:
            raise EvaluationIsolationError("identity_mismatch")
        if tuple(row.doc_keys_json) != FORMAT_PARITY_DOC_KEYS:
            raise EvaluationIsolationError("allowlist_mismatch")
        if row.state_version != owner.state_version:
            raise EvaluationIsolationError("stale_state")
        if row.next_document_index != owner.next_document_index:
            raise EvaluationIsolationError("stale_progress")
