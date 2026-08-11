"""Fail-closed persistence boundary for RAG format-parity evaluation rounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Literal, Sequence
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    DocumentBlock,
    EvidenceIdentityRollout,
    EvidenceSnapshotDependency,
    PolicyChunk,
    PolicyCorpusActivationHistory,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
    RagEvaluationRound,
    RagIngestionJob,
)
from src.knowledge.text_hash import evidence_text_hash
from src.repositories.document_block_repo import DocumentBlockRepository
from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.policy_corpus_scope import (
    join_active_block_projection,
    join_active_chunk_projection,
    join_active_document_projection,
)
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
    run_identity_hash: str
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
        if not _SHA256.fullmatch(self.run_identity_hash):
            raise EvaluationIsolationError("run_identity_mismatch")
        if not 0 <= self.next_document_index <= len(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("stale_progress")


@dataclass(frozen=True)
class AnchorLocatorRequirement:
    """One Gold anchor that must be proved by an exact current source block."""

    text: str
    section: str


@dataclass(frozen=True)
class RecordedSourceLocatorProof:
    source_block_id: str
    page_number: int | None


@dataclass(frozen=True)
class RecordedChunkLocatorProof:
    """Safe evidence identity captured from the one production retrieval."""

    chunk_id: str
    text_hash: str
    source_locators: tuple[RecordedSourceLocatorProof, ...]


@dataclass(frozen=True)
class _ExactAnchorProof:
    anchor_index: int
    section: str
    source_block_id: str


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
    head_mapping: dict[str, dict[str, Any]]
    immutable_counts: dict[str, int]
    resources: IngestionResourceProof


@dataclass(frozen=True)
class IngestionResourceProof:
    chunk_count: int
    duplicate_count: int
    offline_embedding_tokens: int
    provider_embedding_tokens: int | None
    provider_tokens_status: Literal["provider_reported", "unavailable"]
    config_fingerprint: str | None


@dataclass(frozen=True)
class RollbackBaselineProof:
    """Safe hashes and exact authority identities for rollback-only evaluation."""

    tenant_id: UUID
    active_corpus_version_id: UUID
    previous_corpus_version_id: UUID | None
    rollout_epoch: int
    rollout_sha256: str
    activation_history_count: int
    activation_history_hashes: tuple[str, ...]
    active_config_schema_version: str
    active_config_fingerprint: str
    active_corpus_sha256: str
    source_manifest_revision_id: UUID
    source_manifest_hash: str
    source_manifest_sha256: str
    current_document_count: int
    current_block_count: int
    current_chunk_count: int
    current_job_count: int
    current_view_sha256: str
    current_jobs_sha256: str
    evidence_rollout_version: int
    evidence_rollout_sha256: str
    immutable_document_count: int
    immutable_chunk_count: int
    immutable_counts: tuple[tuple[str, int], ...]
    immutable_counts_sha256: str
    proof_sha256: str

    def __post_init__(self) -> None:
        hashes = (
            *self.activation_history_hashes,
            self.rollout_sha256,
            self.active_config_fingerprint,
            self.active_corpus_sha256,
            self.source_manifest_hash,
            self.source_manifest_sha256,
            self.current_view_sha256,
            self.current_jobs_sha256,
            self.evidence_rollout_sha256,
            self.immutable_counts_sha256,
            self.proof_sha256,
        )
        immutable_counts = dict(self.immutable_counts)
        if (
            self.tenant_id != FORMAT_PARITY_TENANT_ID
            or self.rollout_epoch <= 0
            or self.activation_history_count != len(self.activation_history_hashes)
            or self.current_document_count != len(FORMAT_PARITY_DOC_KEYS)
            or min(
                self.current_block_count,
                self.current_chunk_count,
                self.current_job_count,
                self.immutable_document_count,
                self.immutable_chunk_count,
            )
            < 0
            or self.evidence_rollout_version <= 0
            or tuple(sorted(self.immutable_counts)) != self.immutable_counts
            or len(immutable_counts) != len(self.immutable_counts)
            or any(value < 0 for value in immutable_counts.values())
            or immutable_counts.get("policy_document_versions") != self.immutable_document_count
            or immutable_counts.get("policy_chunk_versions") != self.immutable_chunk_count
            or any(not _valid_prefixed_sha256(value) for value in hashes)
        ):
            raise EvaluationIsolationError("rollback_baseline_invalid")


@dataclass(frozen=True)
class RoundProgress:
    state: str
    has_attempt_reservation: bool


@dataclass(frozen=True)
class RunSequenceState:
    completed_results: tuple[dict[str, Any], ...]
    active: EvaluationRoundIdentity | None
    next_format: str | None


def validate_run_sequence(
    rows: list[RagEvaluationRound],
    *,
    run_token: UUID,
    expected_rollout_version: int,
    run_identity_hash: str,
    now: datetime,
) -> RunSequenceState:
    """Validate exact deterministic format order and durable terminal proofs."""

    by_format: dict[str, RagEvaluationRound] = {}
    for row in rows:
        if row.round_format in by_format:
            raise EvaluationIsolationError("round_sequence_duplicate")
        by_format[row.round_format] = row
    present = tuple(format_name for format_name in ROUND_FORMATS if format_name in by_format)
    if set(by_format) != set(present) or present != ROUND_FORMATS[: len(present)]:
        raise EvaluationIsolationError("round_sequence_order_mismatch")

    completed_results: list[dict[str, Any]] = []
    active: EvaluationRoundIdentity | None = None
    for index, round_format in enumerate(present):
        row = by_format[round_format]
        expected_round_token = uuid5(NAMESPACE_URL, f"{run_token}:{round_format}")
        if row.run_identity_hash != run_identity_hash:
            raise EvaluationIsolationError("run_identity_mismatch")
        if (
            row.tenant_id != FORMAT_PARITY_TENANT_ID
            or row.owner_marker != FORMAT_PARITY_OWNER_MARKER
            or row.run_token != run_token
            or row.round_token != expected_round_token
            or row.expected_rollout_version != expected_rollout_version
            or tuple(row.doc_keys_json) != FORMAT_PARITY_DOC_KEYS
        ):
            raise EvaluationIsolationError("round_sequence_identity_mismatch")
        if row.state in TERMINAL_STATES:
            if row.state != "completed" or index != len(completed_results):
                raise EvaluationIsolationError("round_sequence_terminal_mismatch")
            completed_results.append(_validated_terminal_result(row))
            continue
        if active is not None or index != len(present) - 1:
            raise EvaluationIsolationError("round_sequence_active_mismatch")
        if row.lease_expires_at <= now or row.terminal_at is not None:
            raise EvaluationIsolationError("active_round_mismatch")
        active = _identity_from_row(row)

    if active is not None:
        next_format = None
    elif len(present) < len(ROUND_FORMATS):
        next_format = ROUND_FORMATS[len(present)]
    else:
        next_format = None
    return RunSequenceState(
        completed_results=tuple(completed_results),
        active=active,
        next_format=next_format,
    )


def _identity_from_row(row: RagEvaluationRound) -> EvaluationRoundIdentity:
    return EvaluationRoundIdentity(
        round_id=row.id,
        tenant_id=row.tenant_id,
        owner_marker=row.owner_marker,
        run_token=row.run_token,
        round_token=row.round_token,
        round_format=row.round_format,
        state_version=row.state_version,
        next_document_index=row.next_document_index,
        run_identity_hash=row.run_identity_hash,
        expected_rollout_version=row.expected_rollout_version,
    )


def _validated_terminal_result(row: RagEvaluationRound) -> dict[str, Any]:
    proof = row.post_state_proof_json
    current = proof.get("current") if isinstance(proof, dict) else None
    head_keys = proof.get("head_keys") if isinstance(proof, dict) else None
    result = proof.get("round_result") if isinstance(proof, dict) else None
    try:
        current_is_clean = isinstance(current, dict) and all(
            int(current.get(key, -1)) == 0 for key in ("blocks", "chunks", "jobs")
        )
        head_key_set = set(head_keys) if isinstance(head_keys, list) else set()
    except (TypeError, ValueError):
        raise EvaluationIsolationError("terminal_round_proof_invalid") from None
    if (
        row.next_document_index != len(FORMAT_PARITY_DOC_KEYS)
        or row.next_step != "done"
        or row.terminal_at is None
        or row.failure_code is not None
        or row.attempt_doc_key is not None
        or row.expected_source_checksum is not None
        or row.reservation_at is not None
        or row.claimed_job_id is not None
        or not current_is_clean
        or not isinstance(head_keys, list)
        or head_key_set != set(FORMAT_PARITY_DOC_KEYS)
        or not isinstance(result, dict)
        or result.get("round_format") != row.round_format
        or result.get("round_token") != str(row.round_token)
        or result.get("outcome") not in {"completed_pass", "completed_quality_fail"}
        or result.get("pre_state_proved") is not True
        or result.get("post_state_proved") is not True
        or result.get("immutable_history_preserved") is not True
    ):
        raise EvaluationIsolationError("terminal_round_proof_invalid")
    return dict(result)


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


def _source_blocks_prove_recorded_anchors(
    candidates: Sequence[RecordedChunkLocatorProof],
    requirements: Sequence[AnchorLocatorRequirement],
    *,
    chunk_rows: Sequence[Any],
    block_rows: Sequence[Any],
    allowed_pdf_pages: Sequence[int],
) -> bool:
    """Validate hashes/locators and solve an exact per-anchor block assignment."""

    chunks_by_id: dict[str, Any] = {}
    for row in chunk_rows:
        chunk_id = str(row.chunk_id)
        if chunk_id in chunks_by_id:
            return False
        chunks_by_id[chunk_id] = row
    blocks_by_key: dict[tuple[Any, str], Any] = {}
    for block in block_rows:
        key = (block.doc_id, str(block.source_block_id))
        if key in blocks_by_key:
            return False
        blocks_by_key[key] = block

    allowed_pages = set(allowed_pdf_pages)
    exact_proofs: list[_ExactAnchorProof] = []
    for candidate in candidates:
        chunk = chunks_by_id.get(candidate.chunk_id)
        if chunk is None or evidence_text_hash(str(chunk.content)) != candidate.text_hash:
            return False
        refs = chunk.source_block_refs_json
        if not isinstance(refs, list):
            return False
        locators = {(item.source_block_id, item.page_number) for item in candidate.source_locators}
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            source_block_id = str(ref.get("source_block_id") or "")
            ref_hash = str(ref.get("text_hash") or "")
            block = blocks_by_key.get((chunk.doc_id, source_block_id))
            if block is None or (source_block_id, block.page_number) not in locators:
                continue
            if allowed_pages and block.page_number not in allowed_pages:
                continue
            if ref.get("page_number", block.page_number) != block.page_number:
                continue
            if ref_hash != block.text_hash or ref_hash != evidence_text_hash(str(block.text)):
                continue
            for anchor_index, requirement in enumerate(requirements):
                if requirement.text in str(block.text):
                    exact_proofs.append(
                        _ExactAnchorProof(
                            anchor_index=anchor_index,
                            section=requirement.section,
                            source_block_id=source_block_id,
                        )
                    )

    proofs_by_anchor = {
        index: tuple(proof for proof in exact_proofs if proof.anchor_index == index)
        for index in range(len(requirements))
    }
    if any(not proofs for proofs in proofs_by_anchor.values()):
        return False

    def assign(anchor_index: int, block_sections: dict[str, str]) -> bool:
        if anchor_index == len(requirements):
            return True
        for proof in proofs_by_anchor[anchor_index]:
            assigned_section = block_sections.get(proof.source_block_id)
            if assigned_section is not None and assigned_section != proof.section:
                continue
            next_sections = dict(block_sections)
            next_sections[proof.source_block_id] = proof.section
            if assign(anchor_index + 1, next_sections):
                return True
        return False

    return assign(0, {})


class RagEvaluationRoundRepository:
    """Every public mutation locks, proves, and CAS-updates one owner row."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = RagIngestionJobRepository(session)
        self.block_repo = DocumentBlockRepository(session)
        self.chunk_repo = PolicyChunkRepository(session)

    async def capture_rollback_baseline(self) -> RollbackBaselineProof:
        """Read the exact evaluation authority without persisting source content."""

        rollout = (
            await self.session.execute(
                select(PolicyCorpusRollout).where(PolicyCorpusRollout.tenant_id == FORMAT_PARITY_TENANT_ID)
            )
        ).scalar_one_or_none()
        evidence_rollout = await self.session.get(EvidenceIdentityRollout, 1)
        if rollout is None or evidence_rollout is None:
            raise EvaluationIsolationError("rollback_baseline_invalid")
        active_corpus = await self.session.get(PolicyCorpusVersion, rollout.active_corpus_version_id)
        if active_corpus is None or active_corpus.tenant_id != FORMAT_PARITY_TENANT_ID:
            raise EvaluationIsolationError("rollback_baseline_invalid")
        source_manifest = await self.session.get(
            PolicyCorpusManifestRevision,
            active_corpus.source_manifest_revision_id,
        )
        if (
            source_manifest is None
            or source_manifest.tenant_id != FORMAT_PARITY_TENANT_ID
            or source_manifest.manifest_hash != active_corpus.source_manifest_hash
            or active_corpus.state != "complete"
        ):
            raise EvaluationIsolationError("rollback_baseline_invalid")

        histories = list(
            (
                await self.session.execute(
                    select(PolicyCorpusActivationHistory)
                    .where(PolicyCorpusActivationHistory.tenant_id == FORMAT_PARITY_TENANT_ID)
                    .order_by(
                        PolicyCorpusActivationHistory.rollout_epoch,
                        PolicyCorpusActivationHistory.id,
                    )
                )
            ).scalars()
        )
        if (
            not histories
            or histories[-1].rollout_epoch != rollout.rollout_epoch
            or histories[-1].to_corpus_version_id != rollout.active_corpus_version_id
        ):
            raise EvaluationIsolationError("rollback_baseline_invalid")
        history_hashes = tuple(
            _canonical_sha256(
                {
                    "id": row.id,
                    "tenant_id": row.tenant_id,
                    "from_corpus_version_id": row.from_corpus_version_id,
                    "to_corpus_version_id": row.to_corpus_version_id,
                    "prior_rollout_epoch": row.prior_rollout_epoch,
                    "rollout_epoch": row.rollout_epoch,
                    "reason_code": row.reason_code,
                    "actor": row.actor,
                    "selection_decision_hash": row.selection_decision_hash,
                    "receipt_hash": row.receipt_hash,
                    "created_at": row.created_at,
                }
            )
            for row in histories
        )
        rollout_sha256 = _canonical_sha256(
            {
                "id": rollout.id,
                "tenant_id": rollout.tenant_id,
                "active_corpus_version_id": rollout.active_corpus_version_id,
                "previous_corpus_version_id": rollout.previous_corpus_version_id,
                "rollout_epoch": rollout.rollout_epoch,
                "quarantine_reason": rollout.quarantine_reason,
                "source_drifted_at": rollout.source_drifted_at,
            }
        )
        active_corpus_sha256 = _canonical_sha256(
            {
                "id": active_corpus.id,
                "tenant_id": active_corpus.tenant_id,
                "generation_name": active_corpus.generation_name,
                "owner_marker": active_corpus.owner_marker,
                "run_token": active_corpus.run_token,
                "config_schema_version": active_corpus.config_schema_version,
                "config_json": active_corpus.config_json,
                "config_fingerprint": active_corpus.config_fingerprint,
                "provider_parity_report_hash": active_corpus.provider_parity_report_hash,
                "source_manifest_revision_id": active_corpus.source_manifest_revision_id,
                "source_manifest_hash": active_corpus.source_manifest_hash,
                "source_active_corpus_version_id": active_corpus.source_active_corpus_version_id,
                "source_rollout_epoch": active_corpus.source_rollout_epoch,
                "expected_evidence_rollout_version": active_corpus.expected_evidence_rollout_version,
                "state": active_corpus.state,
                "state_version": active_corpus.state_version,
                "next_document_index": active_corpus.next_document_index,
                "bootstrap_counts_json": active_corpus.bootstrap_counts_json,
                "validation_proof_json": active_corpus.validation_proof_json,
                "deterministic_rebuild_hash": active_corpus.deterministic_rebuild_hash,
                "validation_report_hash": active_corpus.validation_report_hash,
                "failure_code": active_corpus.failure_code,
                "terminal_at": active_corpus.terminal_at,
            }
        )
        source_manifest_sha256 = _canonical_sha256(
            {
                "id": source_manifest.id,
                "tenant_id": source_manifest.tenant_id,
                "revision": source_manifest.revision,
                "manifest_schema_version": source_manifest.manifest_schema_version,
                "manifest_json": source_manifest.manifest_json,
                "manifest_hash": source_manifest.manifest_hash,
                "document_count": source_manifest.document_count,
                "block_count": source_manifest.block_count,
                "chunk_count": source_manifest.chunk_count,
            }
        )

        heads = await self._read_tenant_heads()
        if len(heads) != len(FORMAT_PARITY_DOC_KEYS) or {row.doc_key for row in heads} != set(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("rollback_baseline_invalid")
        document_ids = [row.id for row in heads]
        blocks = list(
            (
                await self.session.execute(
                    join_active_block_projection(
                        select(DocumentBlock).where(
                            DocumentBlock.tenant_id == FORMAT_PARITY_TENANT_ID,
                            DocumentBlock.doc_id.in_(document_ids),
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    ).order_by(
                        DocumentBlock.doc_id,
                        DocumentBlock.block_index,
                        DocumentBlock.id,
                    )
                )
            ).scalars()
        )
        chunks = list(
            (
                await self.session.execute(
                    join_active_chunk_projection(
                        select(PolicyChunk).where(
                            PolicyChunk.tenant_id == FORMAT_PARITY_TENANT_ID,
                            PolicyChunk.doc_id.in_(document_ids),
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    ).order_by(PolicyChunk.doc_id, PolicyChunk.chunk_id, PolicyChunk.id)
                )
            ).scalars()
        )
        jobs, jobs_sha256 = await self._current_job_proof()
        if not blocks or not chunks:
            raise EvaluationIsolationError("rollback_baseline_invalid")
        current_view_sha256 = _canonical_sha256(
            {
                "documents": [
                    {
                        "id": row.id,
                        "doc_key": row.doc_key,
                        "doc_type": row.doc_type,
                        "title_sha256": _canonical_sha256(row.title),
                        "effective_date": row.effective_date,
                        "risk_level": row.risk_level,
                        "version": row.version,
                        "content_sha256": _canonical_sha256(row.content),
                        "source_type": row.source_type,
                        "source_checksum": row.source_checksum,
                        "parser_metadata_sha256": _canonical_sha256(row.parser_metadata_json),
                        "policy_version_fingerprint": row.policy_version_fingerprint,
                        "evidence_write_sequence": row.evidence_write_sequence,
                    }
                    for row in heads
                ],
                "blocks": [
                    {
                        "id": row.id,
                        "doc_id": row.doc_id,
                        "source_block_id": row.source_block_id,
                        "block_index": row.block_index,
                        "block_type": row.block_type,
                        "text_hash": row.text_hash,
                        "normalized_text_sha256": _canonical_sha256(row.normalized_text),
                        "page_number": row.page_number,
                        "bbox_sha256": _canonical_sha256(row.bbox_json),
                        "table_metadata_sha256": _canonical_sha256(row.table_metadata_json),
                        "parser_metadata_sha256": _canonical_sha256(row.parser_metadata_json),
                        "ocr_metadata_sha256": _canonical_sha256(row.ocr_metadata_json),
                        "source_uri_sha256": _canonical_sha256(row.source_uri),
                    }
                    for row in blocks
                ],
                "chunks": [
                    {
                        "id": row.id,
                        "doc_id": row.doc_id,
                        "chunk_id": row.chunk_id,
                        "section_sha256": _canonical_sha256(row.section),
                        "content_sha256": _canonical_sha256(row.content),
                        "search_text_sha256": _canonical_sha256(row.search_text),
                        "source_refs_sha256": _canonical_sha256(row.source_block_refs_json),
                        "ocr_metadata_sha256": _canonical_sha256(row.ocr_metadata_json),
                        "risk_level": row.risk_level,
                        "effective_date": row.effective_date,
                        "embedding_sha256": _canonical_sha256(row.embedding),
                        "chunking_config_fingerprint": row.chunking_config_fingerprint,
                        "embedding_input_hash": row.embedding_input_hash,
                        "embedding_token_count": row.embedding_token_count,
                        "evidence_write_sequence": row.evidence_write_sequence,
                    }
                    for row in chunks
                ],
            }
        )
        immutable = await self._immutable_counts()
        rollback_immutable_counts = await self._rollback_immutable_counts()
        immutable_counts = tuple(sorted(rollback_immutable_counts.items()))
        immutable_counts_sha256 = _canonical_sha256(immutable_counts)
        evidence_sha256 = _canonical_sha256(
            {
                "id": evidence_rollout.id,
                "rollout_version": evidence_rollout.rollout_version,
                "dual_write_enabled_at": evidence_rollout.dual_write_enabled_at,
                "backfill_watermark_sequence": evidence_rollout.backfill_watermark_sequence,
                "reconciled_through_sequence": evidence_rollout.reconciled_through_sequence,
                "canonical_reads_enabled": evidence_rollout.canonical_reads_enabled,
                "canonical_reads_enabled_at": evidence_rollout.canonical_reads_enabled_at,
                "canonical_reads_disabled_at": evidence_rollout.canonical_reads_disabled_at,
                "quarantine_reason": evidence_rollout.quarantine_reason,
                "audit_counts_sha256": _canonical_sha256(evidence_rollout.audit_counts_json),
            }
        )
        base: dict[str, Any] = {
            "tenant_id": FORMAT_PARITY_TENANT_ID,
            "active_corpus_version_id": rollout.active_corpus_version_id,
            "previous_corpus_version_id": rollout.previous_corpus_version_id,
            "rollout_epoch": rollout.rollout_epoch,
            "rollout_sha256": rollout_sha256,
            "activation_history_count": len(histories),
            "activation_history_hashes": history_hashes,
            "active_config_schema_version": active_corpus.config_schema_version,
            "active_config_fingerprint": active_corpus.config_fingerprint,
            "active_corpus_sha256": active_corpus_sha256,
            "source_manifest_revision_id": source_manifest.id,
            "source_manifest_hash": source_manifest.manifest_hash,
            "source_manifest_sha256": source_manifest_sha256,
            "current_document_count": len(heads),
            "current_block_count": len(blocks),
            "current_chunk_count": len(chunks),
            "current_job_count": jobs,
            "current_view_sha256": current_view_sha256,
            "current_jobs_sha256": jobs_sha256,
            "evidence_rollout_version": evidence_rollout.rollout_version,
            "evidence_rollout_sha256": evidence_sha256,
            "immutable_document_count": immutable["document_versions"],
            "immutable_chunk_count": immutable["chunk_versions"],
            "immutable_counts": immutable_counts,
            "immutable_counts_sha256": immutable_counts_sha256,
        }
        return RollbackBaselineProof(**base, proof_sha256=_canonical_sha256(base))

    async def _read_tenant_heads(self) -> list[PolicyDocument]:
        return list(
            (
                await self.session.execute(
                    join_active_document_projection(
                        select(PolicyDocument).where(PolicyDocument.tenant_id == FORMAT_PARITY_TENANT_ID),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    ).order_by(PolicyDocument.doc_key, PolicyDocument.id)
                )
            ).scalars()
        )

    async def _current_job_proof(self) -> tuple[int, str]:
        jobs = list(
            (
                await self.session.execute(
                    select(RagIngestionJob)
                    .where(
                        RagIngestionJob.tenant_id == FORMAT_PARITY_TENANT_ID,
                        RagIngestionJob.doc_key.in_(FORMAT_PARITY_DOC_KEYS),
                    )
                    .order_by(RagIngestionJob.created_at, RagIngestionJob.id)
                )
            ).scalars()
        )
        return len(jobs), _canonical_sha256(
            [
                {
                    "id": row.id,
                    "doc_id": row.doc_id,
                    "doc_key": row.doc_key,
                    "source_type": row.source_type,
                    "source_checksum": row.source_checksum,
                    "parser_name": row.parser_name,
                    "parser_version": row.parser_version,
                    "stage": row.stage,
                    "status": row.status,
                    "error_code": row.error_code,
                    "counts_sha256": _canonical_sha256(row.counts_json),
                    "chunking_config_fingerprint": row.chunking_config_fingerprint,
                    "chunk_count": row.chunk_count,
                    "embedding_token_count_total": row.embedding_token_count_total,
                    "provider_prompt_tokens": row.provider_prompt_tokens,
                    "provider_total_tokens": row.provider_total_tokens,
                    "provider_usage_status": row.provider_usage_status,
                    "started_at": row.started_at,
                    "completed_at": row.completed_at,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in jobs
            ]
        )

    async def _rollback_immutable_counts(self) -> dict[str, int]:
        models = {
            "corpus_block_bindings": CorpusBlockBinding,
            "corpus_chunk_bindings": CorpusChunkBinding,
            "corpus_document_bindings": CorpusDocumentBinding,
            "evidence_snapshot_dependencies": EvidenceSnapshotDependency,
            "policy_chunk_versions": PolicyChunkVersion,
            "policy_corpus_manifest_revisions": PolicyCorpusManifestRevision,
            "policy_corpus_versions": PolicyCorpusVersion,
            "policy_document_versions": PolicyDocumentVersion,
            "rag_evaluation_rounds": RagEvaluationRound,
        }
        counts: dict[str, int] = {}
        for name, model in models.items():
            counts[name] = int(
                (
                    await self.session.execute(
                        select(func.count()).select_from(model).where(model.tenant_id == FORMAT_PARITY_TENANT_ID)
                    )
                ).scalar_one()
            )
        return counts

    async def lock_run_rows(self, run_token: UUID) -> list[RagEvaluationRound]:
        """Lock one exact run plus any active row that could conflict with it."""

        active_rows = list(
            (
                await self.session.execute(
                    select(RagEvaluationRound)
                    .where(
                        RagEvaluationRound.tenant_id == FORMAT_PARITY_TENANT_ID,
                        RagEvaluationRound.state.not_in(TERMINAL_STATES),
                    )
                    .order_by(RagEvaluationRound.created_at, RagEvaluationRound.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if len(active_rows) > 1:
            raise EvaluationIsolationError("active_round_cardinality")
        if active_rows and active_rows[0].run_token != run_token:
            raise EvaluationIsolationError("active_round_mismatch")
        return list(
            (
                await self.session.execute(
                    select(RagEvaluationRound)
                    .where(
                        RagEvaluationRound.tenant_id == FORMAT_PARITY_TENANT_ID,
                        RagEvaluationRound.run_token == run_token,
                    )
                    .order_by(RagEvaluationRound.created_at, RagEvaluationRound.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

    async def create_round(
        self,
        *,
        run_token: UUID,
        round_token: UUID,
        round_format: str,
        run_identity_hash: str,
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
            run_identity_hash=run_identity_hash,
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
            run_identity_hash=identity.run_identity_hash,
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

    async def prove_run_identity(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        """Re-lock the durable identity immediately before one provider search."""

        await self.lock_owned(owner)
        return owner

    async def prove_advanced_document(
        self,
        owner: EvaluationRoundIdentity,
        *,
        doc_key: str,
        source_checksum: str,
    ) -> EvaluationRoundIdentity:
        """Prove a skipped cursor against its recorded and current projection."""

        row = await self.lock_owned(
            owner,
            allowed_states=frozenset({"ingesting", "retrieving", "cleaning"}),
        )
        try:
            document_index = FORMAT_PARITY_DOC_KEYS.index(doc_key)
        except ValueError:
            raise EvaluationIsolationError("document_order_mismatch") from None
        if document_index >= owner.next_document_index or not _SHA256.fullmatch(source_checksum):
            raise EvaluationIsolationError("advanced_document_mismatch")
        raw_proof = row.head_mappings_json
        expected = raw_proof.get(doc_key) if isinstance(raw_proof, dict) else None
        if not isinstance(expected, dict) or expected.get("source_checksum") != canonical_ingestion_source_checksum(
            source_checksum
        ):
            raise EvaluationIsolationError("advanced_document_checksum_mismatch")
        heads = await self._lock_tenant_heads()
        await self._prove_recorded_projection(row, heads, require_all=False)
        return owner

    async def prove_advanced_document_resources(
        self,
        owner: EvaluationRoundIdentity,
        *,
        doc_key: str,
        source_checksum: str,
    ) -> tuple[EvaluationRoundIdentity, IngestionResourceProof]:
        """Rebuild safe resource counters for one already-checkpointed document."""

        proved = await self.prove_advanced_document(
            owner,
            doc_key=doc_key,
            source_checksum=source_checksum,
        )
        heads = await self._lock_tenant_heads()
        matching = [head for head in heads if head.doc_key == doc_key]
        if len(matching) != 1:
            raise EvaluationIsolationError("advanced_document_mismatch")
        return proved, await self._head_resource_proof(matching[0])

    async def prove_recorded_anchor_locators(
        self,
        *,
        doc_key: str,
        candidates: Sequence[RecordedChunkLocatorProof],
        requirements: Sequence[AnchorLocatorRequirement],
        allowed_pdf_pages: Sequence[int],
    ) -> bool:
        """Bind Gold anchors to exact source blocks without exposing block text."""

        if not candidates or not requirements:
            return False
        chunk_ids = [candidate.chunk_id for candidate in candidates]
        if len(chunk_ids) != len(set(chunk_ids)):
            return False
        chunk_rows = list(
            (
                await self.session.execute(
                    join_active_chunk_projection(
                        select(
                            PolicyChunk.doc_id,
                            PolicyChunk.chunk_id,
                            PolicyChunk.content,
                            PolicyChunk.source_block_refs_json,
                        )
                        .join(
                            PolicyDocument,
                            and_(
                                PolicyChunk.doc_id == PolicyDocument.id,
                                PolicyDocument.tenant_id == FORMAT_PARITY_TENANT_ID,
                            ),
                        )
                        .where(
                            PolicyChunk.tenant_id == FORMAT_PARITY_TENANT_ID,
                            PolicyDocument.doc_key == doc_key,
                            PolicyChunk.chunk_id.in_(chunk_ids),
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    )
                )
            ).all()
        )
        document_ids = {row.doc_id for row in chunk_rows}
        source_block_ids = {
            str(ref.get("source_block_id"))
            for row in chunk_rows
            for ref in (row.source_block_refs_json if isinstance(row.source_block_refs_json, list) else [])
            if isinstance(ref, dict) and str(ref.get("source_block_id") or "").strip()
        }
        if len(document_ids) != 1 or not source_block_ids:
            return False
        block_rows = list(
            (
                await self.session.execute(
                    join_active_block_projection(
                        select(DocumentBlock).where(
                            DocumentBlock.tenant_id == FORMAT_PARITY_TENANT_ID,
                            DocumentBlock.doc_id.in_(document_ids),
                            DocumentBlock.source_block_id.in_(source_block_ids),
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    )
                )
            )
            .scalars()
            .all()
        )
        return _source_blocks_prove_recorded_anchors(
            candidates,
            requirements,
            chunk_rows=chunk_rows,
            block_rows=block_rows,
            allowed_pdf_pages=allowed_pdf_pages,
        )

    async def prove_compatible_pre_state(
        self,
        owner: EvaluationRoundIdentity,
        *,
        rollback_baseline: RollbackBaselineProof | None = None,
    ) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"claimed"}))
        heads = await self._lock_tenant_heads()
        current_counts = await self._current_counts(heads)
        if rollback_baseline is None:
            if current_counts["blocks"] or current_counts["chunks"] or current_counts["jobs"]:
                raise EvaluationIsolationError("pre_state_not_clean")
            pre_state_proof: dict[str, Any] = {
                "current": current_counts,
                "head_ids": {head.doc_key: str(head.id) for head in heads},
            }
        else:
            observed = await self.capture_rollback_baseline()
            expected_counts = {
                "documents": rollback_baseline.current_document_count,
                "blocks": rollback_baseline.current_block_count,
                "chunks": rollback_baseline.current_chunk_count,
                "jobs": rollback_baseline.current_job_count,
            }
            if observed != rollback_baseline or current_counts != expected_counts:
                raise EvaluationIsolationError("rollback_baseline_mismatch")
            pre_state_proof = {
                "current": current_counts,
                "head_ids": {head.doc_key: str(head.id) for head in heads},
                "rollback_baseline_sha256": rollback_baseline.proof_sha256,
            }
        immutable = await self._immutable_counts()
        if rollback_baseline is not None and immutable != {
            "document_versions": rollback_baseline.immutable_document_count,
            "chunk_versions": rollback_baseline.immutable_chunk_count,
        }:
            raise EvaluationIsolationError("rollback_baseline_mismatch")
        return await self._cas(
            row,
            owner,
            state="ingesting",
            next_step="ingest",
            pre_state_proof_json=pre_state_proof,
            head_mappings_json={},
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

    async def prove_retrieval_ready(
        self,
        owner: EvaluationRoundIdentity,
        *,
        rollback_baseline: RollbackBaselineProof | None = None,
    ) -> EvaluationRoundIdentity:
        row = await self.lock_owned(owner, allowed_states=frozenset({"retrieving"}))
        if owner.next_document_index != len(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("retrieval_progress_incomplete")
        heads = await self._lock_tenant_heads()
        await self._prove_recorded_projection(row, heads, require_all=True)
        current = await self._current_counts(heads)
        if rollback_baseline is None and current["jobs"]:
            raise EvaluationIsolationError("retrieval_projection_invalid")
        if rollback_baseline is not None:
            job_count, jobs_sha256 = await self._current_job_proof()
            if (
                current["jobs"] != rollback_baseline.current_job_count
                or job_count != rollback_baseline.current_job_count
                or jobs_sha256 != rollback_baseline.current_jobs_sha256
            ):
                raise EvaluationIsolationError("retrieval_projection_invalid")
        return await self._cas(row, owner, state="cleaning", next_step="cleanup")

    async def cleanup_current_projection(
        self,
        owner: EvaluationRoundIdentity,
        *,
        terminal_state: Literal["completed", "abandoned"],
        failure_code: str | None = None,
        round_result: dict[str, Any] | None = None,
        rollback_baseline: RollbackBaselineProof | None = None,
    ) -> EvaluationRoundIdentity:
        allowed = frozenset({"cleaning", "expired", "ingesting", "retrieving"})
        row = await self.lock_owned(owner, allowed_states=allowed)
        heads = await self._lock_tenant_heads()
        proved_heads = await self._prove_recorded_projection(row, heads, require_all=False)
        before_current = await self._current_counts(heads)
        if rollback_baseline is None and before_current["jobs"]:
            raise EvaluationIsolationError("projection_drift")
        if rollback_baseline is not None:
            job_count, jobs_sha256 = await self._current_job_proof()
            if (
                before_current["jobs"] != rollback_baseline.current_job_count
                or job_count != rollback_baseline.current_job_count
                or jobs_sha256 != rollback_baseline.current_jobs_sha256
            ):
                raise EvaluationIsolationError("projection_drift")
        before_immutable = await self._immutable_counts()
        recorded = {key: int(value) for key, value in row.immutable_counts_json.items() if isinstance(value, int)}
        if any(before_immutable.get(key, 0) < value for key, value in recorded.items()):
            raise EvaluationIsolationError("immutable_history_regressed")
        if rollback_baseline is None:
            for head in proved_heads:
                await self.block_repo.delete_by_document_id(head.id, row.tenant_id)
                await self.chunk_repo.delete_by_document_id(head.id, row.tenant_id)
        current = await self._current_counts(heads)
        if rollback_baseline is None and (current["blocks"] or current["chunks"] or current["jobs"]):
            raise EvaluationIsolationError("post_cleanup_residual")
        if rollback_baseline is not None and current != before_current:
            raise EvaluationIsolationError("projection_drift")
        after_immutable = await self._immutable_counts()
        if any(after_immutable[key] < before_immutable[key] for key in before_immutable):
            raise EvaluationIsolationError("immutable_history_regressed")
        post_proof: dict[str, Any] = {
            "current": current,
            "head_keys": [head.doc_key for head in heads],
        }
        if rollback_baseline is not None:
            post_proof.update(
                rollback_pending=True,
                rollback_baseline_sha256=rollback_baseline.proof_sha256,
            )
        if round_result is not None:
            post_proof["round_result"] = dict(round_result)
        return await self._cas(
            row,
            owner,
            state=terminal_state,
            next_step="done",
            post_state_proof_json=post_proof,
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
                    join_active_document_projection(
                        select(PolicyDocument).where(
                            PolicyDocument.tenant_id == row.tenant_id,
                            PolicyDocument.doc_key == doc_key,
                        ),
                        tenant_id=row.tenant_id,
                    ).with_for_update()
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
                        join_active_block_projection(
                            select(DocumentBlock).where(
                                DocumentBlock.tenant_id == row.tenant_id,
                                DocumentBlock.doc_id == head.id,
                            ),
                            tenant_id=row.tenant_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            chunks = list(
                (
                    await self.session.execute(
                        join_active_chunk_projection(
                            select(PolicyChunk).where(
                                PolicyChunk.tenant_id == row.tenant_id,
                                PolicyChunk.doc_id == head.id,
                            ),
                            tenant_id=row.tenant_id,
                        ).with_for_update()
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
        resource_proof = self._resource_proof(chunks=chunks, job=jobs[0] if len(jobs) == 1 else None)
        return ProjectionInspection(
            state=classify_attempt_projection(projection),
            projection=projection,
            document_id=head.id if head is not None else None,
            job_id=jobs[0].id if len(jobs) == 1 else None,
            job_error_code=getattr(jobs[0], "error_code", None) if len(jobs) == 1 else None,
            head_mapping=(
                {
                    doc_key: {
                        "head_id": str(head.id),
                        "source_checksum": str(head.source_checksum),
                        "block_count": len(blocks),
                        "chunk_count": len(chunks),
                        "canonical_binding_count": len(chunk_ids & bound_ids),
                    }
                }
                if head is not None
                else {}
            ),
            immutable_counts=immutable,
            resources=resource_proof,
        )

    async def _head_resource_proof(self, head: PolicyDocument) -> IngestionResourceProof:
        chunks = list(
            (
                await self.session.execute(
                    join_active_chunk_projection(
                        select(PolicyChunk).where(
                            PolicyChunk.tenant_id == head.tenant_id,
                            PolicyChunk.doc_id == head.id,
                        ),
                        tenant_id=head.tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        return self._resource_proof(chunks=chunks, job=None)

    @staticmethod
    def _resource_proof(
        *,
        chunks: Sequence[PolicyChunk],
        job: RagIngestionJob | None,
    ) -> IngestionResourceProof:
        fingerprints = {
            str(fingerprint)
            for chunk in chunks
            if (fingerprint := getattr(chunk, "chunking_config_fingerprint", None)) is not None
        }
        provider_reported = bool(
            job is not None
            and getattr(job, "provider_usage_status", None) == "available"
            and getattr(job, "provider_prompt_tokens", None) is not None
        )
        hashes = [getattr(chunk, "embedding_input_hash", None) for chunk in chunks]
        return IngestionResourceProof(
            chunk_count=len(chunks),
            duplicate_count=len(chunks) - len({str(value) for value in hashes}) if all(hashes) else 0,
            offline_embedding_tokens=sum(int(getattr(chunk, "embedding_token_count", 0)) for chunk in chunks),
            provider_embedding_tokens=int(getattr(job, "provider_prompt_tokens")) if provider_reported else None,
            provider_tokens_status="provider_reported" if provider_reported else "unavailable",
            config_fingerprint=next(iter(fingerprints)) if len(fingerprints) == 1 else None,
        )

    async def _prove_recorded_projection(
        self,
        row: RagEvaluationRound,
        heads: list[PolicyDocument],
        *,
        require_all: bool,
    ) -> list[PolicyDocument]:
        raw_proof = row.head_mappings_json
        if not isinstance(raw_proof, dict):
            raise EvaluationIsolationError("projection_proof_invalid")
        proof_keys = set(raw_proof)
        if not proof_keys.issubset(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("projection_proof_invalid")
        if require_all and proof_keys != set(FORMAT_PARITY_DOC_KEYS):
            raise EvaluationIsolationError("projection_proof_incomplete")
        heads_by_key = {head.doc_key: head for head in heads}
        if any(doc_key not in heads_by_key for doc_key in proof_keys):
            raise EvaluationIsolationError("projection_drift")

        proved_heads: list[PolicyDocument] = []
        for head in heads:
            actual = await self._head_projection(head)
            expected = raw_proof.get(head.doc_key)
            if expected is None:
                if actual["block_count"] or actual["chunk_count"] or actual["canonical_binding_count"]:
                    raise EvaluationIsolationError("projection_drift")
                continue
            if not isinstance(expected, dict) or set(expected) != {
                "head_id",
                "source_checksum",
                "block_count",
                "chunk_count",
                "canonical_binding_count",
            }:
                raise EvaluationIsolationError("projection_proof_invalid")
            if actual != expected:
                raise EvaluationIsolationError("projection_drift")
            if (
                int(actual["block_count"]) <= 0
                or int(actual["chunk_count"]) <= 0
                or actual["canonical_binding_count"] != actual["chunk_count"]
            ):
                raise EvaluationIsolationError("projection_drift")
            proved_heads.append(head)
        return proved_heads

    async def _head_projection(self, head: PolicyDocument) -> dict[str, Any]:
        blocks = list(
            (
                await self.session.execute(
                    join_active_block_projection(
                        select(DocumentBlock).where(
                            DocumentBlock.tenant_id == FORMAT_PARITY_TENANT_ID,
                            DocumentBlock.doc_id == head.id,
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    ).with_for_update()
                )
            )
            .scalars()
            .all()
        )
        chunks = list(
            (
                await self.session.execute(
                    join_active_chunk_projection(
                        select(PolicyChunk).where(
                            PolicyChunk.tenant_id == FORMAT_PARITY_TENANT_ID,
                            PolicyChunk.doc_id == head.id,
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    ).with_for_update()
                )
            )
            .scalars()
            .all()
        )
        document_versions = list(
            (
                await self.session.execute(
                    select(PolicyDocumentVersion).where(
                        PolicyDocumentVersion.tenant_id == FORMAT_PARITY_TENANT_ID,
                        PolicyDocumentVersion.policy_document_id == head.id,
                        PolicyDocumentVersion.doc_key == head.doc_key,
                        PolicyDocumentVersion.document_version == head.version,
                    )
                )
            )
            .scalars()
            .all()
        )
        chunk_versions: list[PolicyChunkVersion] = []
        if len(document_versions) == 1:
            chunk_versions = list(
                (
                    await self.session.execute(
                        select(PolicyChunkVersion).where(
                            PolicyChunkVersion.tenant_id == FORMAT_PARITY_TENANT_ID,
                            PolicyChunkVersion.policy_document_version_id == document_versions[0].id,
                            PolicyChunkVersion.doc_key == head.doc_key,
                            PolicyChunkVersion.document_version == head.version,
                        )
                    )
                )
                .scalars()
                .all()
            )
        chunk_ids = {str(chunk.chunk_id) for chunk in chunks}
        bound_ids = {str(chunk.chunk_id) for chunk in chunk_versions}
        return {
            "head_id": str(head.id),
            "source_checksum": str(head.source_checksum),
            "block_count": len(blocks),
            "chunk_count": len(chunks),
            "canonical_binding_count": len(chunk_ids & bound_ids),
        }

    async def _lock_tenant_heads(self) -> list[PolicyDocument]:
        heads = list(
            (
                await self.session.execute(
                    join_active_document_projection(
                        select(PolicyDocument).where(PolicyDocument.tenant_id == FORMAT_PARITY_TENANT_ID),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    )
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
        if not document_ids:
            return {"documents": 0, "blocks": 0, "chunks": 0, "jobs": jobs}
        blocks = int(
            (
                await self.session.execute(
                    join_active_block_projection(
                        select(func.count())
                        .select_from(DocumentBlock)
                        .where(
                            DocumentBlock.tenant_id == FORMAT_PARITY_TENANT_ID,
                            DocumentBlock.doc_id.in_(document_ids),
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
                    )
                )
            ).scalar_one()
        )
        chunks = int(
            (
                await self.session.execute(
                    join_active_chunk_projection(
                        select(func.count())
                        .select_from(PolicyChunk)
                        .where(
                            PolicyChunk.tenant_id == FORMAT_PARITY_TENANT_ID,
                            PolicyChunk.doc_id.in_(document_ids),
                        ),
                        tenant_id=FORMAT_PARITY_TENANT_ID,
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
                RagEvaluationRound.run_identity_hash == owner.run_identity_hash,
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
            run_identity_hash=owner.run_identity_hash,
            expected_rollout_version=owner.expected_rollout_version,
        )

    @staticmethod
    def _assert_owned(row: RagEvaluationRound, owner: EvaluationRoundIdentity) -> None:
        if row.run_identity_hash != owner.run_identity_hash:
            raise EvaluationIsolationError("run_identity_mismatch")
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


def _valid_prefixed_sha256(value: object) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and bool(_SHA256.fullmatch(value[7:]))


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_canonical_json_default,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _canonical_json_default(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")
