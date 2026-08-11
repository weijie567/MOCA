from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import asdict
from datetime import UTC, date, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any
from typing import Protocol
from uuid import UUID
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.schemas import FORBIDDEN_MESSAGE_KEYS
from src.db.models import DocumentBlock, PolicyChunk, PolicyDocument, RagIngestionJob
from src.knowledge.text_hash import evidence_text_hash
from src.rag.chunker import BlockChunkResult, chunk_blocks
from src.rag.embedding_tokenizer import EmbeddingTokenCounter, load_embedding_tokenizer_config
from src.rag.embedder import EmbeddingBatchResultV1, EmbeddingService, EmbeddingUsageStatus
from src.rag.parsers.base import ParsedBlock, ParseResult, is_valid_doc_key
from src.rag.parsers.registry import ParserRegistry
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler, PolicyEmbeddingInputV1
from src.rag.search_text import build_policy_chunk_search_text
from src.rag.versioning import build_policy_version_fingerprint
from src.repositories.document_block_repo import (
    DocumentBlockRepository,
    build_canonical_document_content,
)
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.policy_corpus_scope import (
    ActivePolicyCorpusScope,
    PolicyCorpusScopeUnavailable,
    bind_active_policy_projection,
)
from src.repositories.policy_document_repo import PolicyDocumentRepository
from src.repositories.rag_ingestion_job_repo import RagIngestionJobRepository, validate_rag_ingestion_job


@dataclass
class IngestionReport:
    doc_key: str
    title: str
    status: str
    chunks_created: int = 0
    error: str | None = None
    job_id: UUID | None = None
    error_code: str | None = None
    safe_message: str | None = None
    evidence_write_sequence: int | None = None
    rollout_version: int | None = None


CHARACTER_COMPATIBILITY_CONFIG_VERSION = "character_compatibility.v1"
_CHARACTER_COMPATIBILITY_MAX_CHARS = 1200
_CHARACTER_COMPATIBILITY_TARGET_CHARS = 800
_CHARACTER_COMPATIBILITY_OVERLAP_CHARS = 100


class IngestionAssemblyMode(StrEnum):
    CHARACTER_COMPATIBILITY = "character_compatibility"
    TOKEN_AWARE = "token_aware"


class PolicyCorpusConfigError(RuntimeError):
    """An active corpus does not match either supported named configuration."""


class PolicyInputAssembler(Protocol):
    def assemble(
        self,
        *,
        blocks: Sequence[ParsedBlock],
        doc_key: str,
        title: str,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[PolicyEmbeddingInputV1, ...]: ...


class CharacterCompatibilityAssembler:
    """Named read-only incumbent that preserves the pre-Plan04 provider bytes."""

    config_version = CHARACTER_COMPATIBILITY_CONFIG_VERSION

    def __init__(self, *, counter: EmbeddingTokenCounter | None = None) -> None:
        self.counter = counter or _default_embedding_token_counter()
        self.config_fingerprint = _character_compatibility_config_fingerprint(self.counter)

    def assemble(
        self,
        *,
        blocks: Sequence[ParsedBlock],
        doc_key: str,
        title: str,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[PolicyEmbeddingInputV1, ...]:
        chunks = chunk_blocks(
            tuple(blocks),
            doc_key=doc_key,
            max_chars=_CHARACTER_COMPATIBILITY_MAX_CHARS,
            target_chars=_CHARACTER_COMPATIBILITY_TARGET_CHARS,
            overlap_chars=_CHARACTER_COMPATIBILITY_OVERLAP_CHARS,
        )
        assembled: list[PolicyEmbeddingInputV1] = []
        for chunk in chunks:
            embedding_input = _render_character_compatibility_input(title=title, chunk=chunk)
            assembled.append(
                PolicyEmbeddingInputV1(
                    doc_key=chunk.doc_key,
                    chunk_id=chunk.chunk_id,
                    section=chunk.section,
                    citation_content=chunk.content,
                    primary_content=chunk.content,
                    overlap_content="",
                    search_text=build_policy_chunk_search_text(
                        title=title,
                        section=chunk.section,
                        content=chunk.content,
                        doc_type=doc_type,
                        risk_level=risk_level,
                        heading_path=_chunk_heading_path(chunk),
                        table_headers=_chunk_table_headers(chunk),
                        source_context=_chunk_source_context(chunk),
                    ),
                    embedding_input=embedding_input,
                    embedding_input_hash=("sha256:" + hashlib.sha256(embedding_input.encode("utf-8")).hexdigest()),
                    embedding_token_count=self.counter.count(embedding_input),
                    overlap_token_count=0,
                    chunking_config_fingerprint=self.config_fingerprint,
                    source_block_refs=tuple(MappingProxyType(dict(ref)) for ref in chunk.source_block_refs),
                    metadata=MappingProxyType(dict(chunk.metadata)),
                    chunk_index=chunk.chunk_index,
                    part_index=chunk.part_index,
                )
            )
        return tuple(assembled)


def assemble_policy_embedding_inputs(
    *,
    blocks: Sequence[ParsedBlock],
    doc_key: str,
    title: str,
    doc_type: str | None,
    risk_level: str | None,
    input_assembler: PolicyInputAssembler,
) -> tuple[PolicyEmbeddingInputV1, ...]:
    """Call the selected parsed-block assembler without local reconstruction."""
    return input_assembler.assemble(
        blocks=blocks,
        doc_key=doc_key,
        title=title,
        doc_type=doc_type,
        risk_level=risk_level,
    )


SAFE_INGESTION_REPORT_FIELDS = (
    "job_id",
    "doc_key",
    "source_type",
    "source_checksum",
    "parser_name",
    "parser_version",
    "ocr_engine",
    "stage",
    "status",
    "error_code",
    "safe_message",
    "warnings",
    "counts",
    "timings",
    "started_at",
    "completed_at",
)
_FORBIDDEN_REPORT_KEYS = FORBIDDEN_MESSAGE_KEYS | {
    "debug_image",
    "debug_payload",
    "exception",
    "file_bytes",
    "file_path",
    "hidden_text",
    "local_path",
    "parser_dump",
    "path",
    "raw_bytes",
    "raw_parser_dump",
    "stack",
    "stack_trace",
    "traceback",
}


def build_safe_ingestion_report(job: RagIngestionJob | Mapping[str, Any]) -> dict[str, Any]:
    """Project durable ingestion trace data into an allowlisted maintainer report."""

    return {
        "job_id": _safe_report_scalar(_read_report_field(job, "job_id", "id")),
        "doc_key": _safe_report_scalar(_read_report_field(job, "doc_key")),
        "source_type": _safe_report_scalar(_read_report_field(job, "source_type")),
        "source_checksum": _safe_report_scalar(_read_report_field(job, "source_checksum")),
        "parser_name": _safe_report_scalar(_read_report_field(job, "parser_name")),
        "parser_version": _safe_report_scalar(_read_report_field(job, "parser_version")),
        "ocr_engine": _safe_report_scalar(_read_report_field(job, "ocr_engine")),
        "stage": _safe_report_scalar(_read_report_field(job, "stage")),
        "status": _safe_report_scalar(_read_report_field(job, "status")),
        "error_code": _safe_report_scalar(_read_report_field(job, "error_code")),
        "safe_message": _safe_report_message(_read_report_field(job, "safe_message")),
        "warnings": _safe_report_list(_read_report_field(job, "warnings", "warnings_json")),
        "counts": _safe_report_mapping(_read_report_field(job, "counts", "counts_json")),
        "timings": _safe_report_mapping(_read_report_field(job, "timings", "timings_json")),
        "started_at": _safe_report_scalar(_read_report_field(job, "started_at")),
        "completed_at": _safe_report_scalar(_read_report_field(job, "completed_at")),
    }


def sanitize_failure_reason(
    reason: Any,
    *,
    failure_code: str = "parser_failed",
    default_message: str = "Policy source could not be parsed safely.",
) -> dict[str, str]:
    safe_reason = _safe_report_value(reason)
    code = failure_code
    message = default_message
    if isinstance(safe_reason, Mapping):
        raw_code = safe_reason.get("failure_code") or safe_reason.get("error_code")
        if raw_code:
            code = str(raw_code)
        raw_message = safe_reason.get("safe_message") or safe_reason.get("message") or safe_reason.get("error")
        if raw_message:
            message = str(raw_message)
    elif isinstance(safe_reason, str):
        message = safe_reason
    return {
        "failure_code": _safe_message(code, default=failure_code),
        "safe_message": _safe_message(message, default=default_message),
    }


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        embedder: EmbeddingService,
        tenant_id: UUID,
        *,
        assembly_mode: IngestionAssemblyMode = IngestionAssemblyMode.CHARACTER_COMPATIBILITY,
        input_assembler: PolicyInputAssembler | None = None,
    ):
        self.session = session
        self.embedder = embedder
        self.tenant_id = tenant_id
        self.assembly_mode = IngestionAssemblyMode(assembly_mode)
        self._input_assembler_explicit = input_assembler is not None
        self.input_assembler = input_assembler or _assembler_for_mode(self.assembly_mode)
        self.chunk_repo = PolicyChunkRepository(session)
        self.doc_repo = PolicyDocumentRepository(session)
        self.block_repo = DocumentBlockRepository(session)
        self.evidence_repo = EvidenceVersionRepository(session)
        self.job_repo = RagIngestionJobRepository(session)
        self.parser_registry = ParserRegistry()

    async def ingest_document(
        self,
        file_path: Path,
        doc_meta: dict,
        *,
        expected_rollout_version: int | None = None,
    ) -> IngestionReport:
        """
        Ingest one policy document.

        Parsing, chunking, and embeddings complete before the short locked
        document replacement transaction mutates committed policy rows.
        """
        raw_doc_key = doc_meta.get("doc_key")
        title = str(doc_meta.get("title") or "Untitled policy")
        if not is_valid_doc_key(raw_doc_key):
            return IngestionReport(
                doc_key="invalid_doc_key",
                title=title,
                status="failed",
                error="Policy document key is invalid.",
                error_code="invalid_doc_key",
                safe_message="Policy document key is invalid.",
            )
        doc_key = str(raw_doc_key)
        active_scope: ActivePolicyCorpusScope | None = None
        if isinstance(self.session, AsyncSession) and not self._input_assembler_explicit:
            try:
                active_scope = await ActivePolicyCorpusScope.resolve(self.session, tenant_id=self.tenant_id)
                self.input_assembler = assembler_for_active_policy_corpus(active_scope)
            except (PolicyCorpusConfigError, PolicyCorpusScopeUnavailable):
                return IngestionReport(
                    doc_key=doc_key,
                    title=title,
                    status="failed",
                    error="Active policy corpus configuration is unavailable.",
                    error_code="active_policy_corpus_config_unavailable",
                    safe_message="Active policy corpus configuration is unavailable.",
                )
        source_type = _source_type_for(file_path, doc_meta)
        source_checksum = _source_checksum(file_path)
        effective_date = doc_meta.get("effective_date")
        job: RagIngestionJob | None = None

        try:
            preexisting_doc = await self._get_existing_document_without_lock(doc_key)
        except Exception:
            preexisting_doc = None

        job = await self._create_job_trace(
            doc_id=preexisting_doc.id if preexisting_doc is not None else None,
            doc_key=doc_key,
            source_type=_safe_source_type_for_persistence(source_type),
            source_checksum=source_checksum,
            stage="received",
            status="running",
        )
        if job is None:
            return IngestionReport(
                doc_key=doc_key,
                title=title,
                status="failed",
                error="Job trace unavailable",
                error_code="job_trace_unavailable",
                safe_message="Policy ingestion job trace could not be persisted.",
            )
        durable_job_id = getattr(job, "id", None)

        try:
            parse_result = self.parser_registry.parse(
                file_path,
                doc_key=doc_key,
                source_type=_safe_source_type_for_persistence(source_type),
                metadata=doc_meta,
            )
            if parse_result.status == "failed":
                return await self._finish_preflight_failure(
                    job=job,
                    doc_key=doc_key,
                    title=title,
                    parse_result=parse_result,
                    stage="parsing",
                    default_code=parse_result.failure_code or "parse_failed",
                    default_message="Policy source could not be parsed.",
                )

            blocks = tuple(block for block in parse_result.blocks if block.text.strip())
            canonical_source = build_canonical_document_content(blocks)
            assembled_inputs = assemble_policy_embedding_inputs(
                blocks=blocks,
                doc_key=doc_key,
                title=title,
                doc_type=doc_meta["doc_type"],
                risk_level=doc_meta["risk_level"],
                input_assembler=self.input_assembler,
            )
            if not assembled_inputs:
                return await self._finish_preflight_failure(
                    job=job,
                    doc_key=doc_key,
                    title=title,
                    parse_result=parse_result,
                    stage="chunking",
                    default_code="no_chunks_produced",
                    default_message="Policy source did not produce visible chunks.",
                )

            texts = [dto.embedding_input for dto in assembled_inputs]
            embeddings, embedding_usage = await _embed_with_usage_audit(self.embedder, texts)
            if len(embeddings) != len(assembled_inputs):
                msg = f"Embedding count mismatch: expected {len(assembled_inputs)}, got {len(embeddings)}"
                return await self._finish_preflight_failure(
                    job=job,
                    doc_key=doc_key,
                    title=title,
                    parse_result=parse_result,
                    stage="embedding",
                    default_code="embedding_count_mismatch",
                    default_message=msg,
                    counts={"chunks": len(assembled_inputs), "embeddings": len(embeddings)},
                )
        except Exception:
            return await self._finish_preflight_failure(
                job=job,
                doc_key=doc_key,
                title=title,
                parse_result=None,
                stage="parsing",
                default_code="parse_failed",
                default_message="Policy source could not be parsed.",
            )

        doc_snapshot: dict[str, Any] | None = None
        doc: PolicyDocument | None = None
        write_sequence: int | None = None
        writer_rollout_version: int | None = None
        try:
            # SQLAlchemy sessions always take the rollout-first path. A few
            # legacy unit tests use deliberately tiny non-SQLAlchemy doubles;
            # they keep exercising parser/sanitizer behavior without claiming
            # rollout coverage.
            use_immutable_writer = isinstance(self.session, AsyncSession)
            if use_immutable_writer:
                writer_rollout = await self.evidence_repo.lock_for_writer(
                    expected_rollout_version=expected_rollout_version,
                )
                writer_rollout_version = writer_rollout.rollout_version
            # Lock the existing row through the final commit so concurrent
            # re-imports cannot write the same next content version.
            existing_doc = await self.doc_repo.get_by_doc_key_for_update(doc_key, self.tenant_id)
            locked_chunks: list[PolicyChunk] = []
            if use_immutable_writer and existing_doc is not None:
                locked_chunks = await self.chunk_repo.list_by_document_id_for_update(existing_doc.id, self.tenant_id)

            content = canonical_source.content
            effective_date = (
                effective_date or (existing_doc.effective_date if existing_doc is not None else None) or date.today()
            )
            fingerprint = build_policy_version_fingerprint(
                citation_text=content,
                title=title,
                doc_type=doc_meta["doc_type"],
                risk_level=doc_meta["risk_level"],
                effective_date=effective_date,
            )
            previous_fingerprint = (
                getattr(existing_doc, "policy_version_fingerprint", None) if existing_doc is not None else None
            )
            fingerprint_changed = bool(
                existing_doc is not None
                and (
                    existing_doc.content != content
                    if previous_fingerprint is None
                    else previous_fingerprint != fingerprint
                )
            )
            if use_immutable_writer:
                write_sequence = await self.evidence_repo.allocate_ingestion_sequence()

            if existing_doc:
                doc = existing_doc
                doc_snapshot = _snapshot_document(doc)
                if fingerprint_changed:
                    doc.version = (doc.version or 1) + 1
                doc.title = title
                doc.doc_type = doc_meta["doc_type"]
                doc.risk_level = doc_meta["risk_level"]
                doc.effective_date = effective_date
                doc.content = content
                doc.source_type = _safe_source_type_for_persistence(parse_result.source_type)
                doc.source_checksum = source_checksum
                doc.parser_metadata_json = _parser_metadata(parse_result)
                doc.policy_version_fingerprint = fingerprint
            else:
                doc = PolicyDocument(
                    id=uuid4(),
                    tenant_id=self.tenant_id,
                    doc_key=doc_key,
                    doc_type=doc_meta["doc_type"],
                    title=title,
                    effective_date=effective_date,
                    risk_level=doc_meta["risk_level"],
                    content=content,
                    source_type=_safe_source_type_for_persistence(parse_result.source_type),
                    source_checksum=source_checksum,
                    parser_metadata_json=_parser_metadata(parse_result),
                    policy_version_fingerprint=fingerprint,
                )
                self.session.add(doc)
                await self.session.flush()
                if getattr(doc, "id", None) is None:
                    doc.id = uuid4()
                if job is None:
                    job = await self._create_job_trace(
                        doc_id=doc.id,
                        doc_key=doc_key,
                        source_type=_safe_source_type_for_persistence(source_type),
                        source_checksum=source_checksum,
                        stage="persisting",
                        status="running",
                        commit_immediately=False,
                    )

            db_blocks = _document_blocks_from_parsed(
                tenant_id=self.tenant_id,
                doc_id=doc.id,
                blocks=blocks,
                parse_result=parse_result,
            )
            db_chunks = _policy_chunks_from_embedding_inputs(
                tenant_id=self.tenant_id,
                doc_id=doc.id,
                title=title,
                doc_type=doc_meta["doc_type"],
                risk_level=doc_meta["risk_level"],
                effective_date=effective_date,
                assembled_inputs=assembled_inputs,
                embeddings=embeddings,
            )
            reused_binding = None
            if use_immutable_writer and existing_doc is not None and not fingerprint_changed:
                reused_binding = await self.evidence_repo.find_exact_binding(
                    tenant_id=self.tenant_id,
                    document=doc,
                    chunks=db_chunks,
                    fingerprint=fingerprint,
                    canonical_source=canonical_source,
                )

            if reused_binding is not None:
                await self.evidence_repo.project_write_sequence(
                    document=doc,
                    chunks=locked_chunks,
                    write_sequence=write_sequence,
                )
                persisted_chunks = locked_chunks
                chunks_created = 0
            else:
                await self.block_repo.delete_by_document_id(doc.id, self.tenant_id)
                await self.chunk_repo.delete_by_document_id(doc.id, self.tenant_id)
                await self.block_repo.bulk_insert(db_blocks)
                await self.chunk_repo.bulk_insert(db_chunks)
                persisted_chunks = db_chunks
                chunks_created = len(db_chunks)
                if use_immutable_writer:
                    document_version, chunk_versions = await self.evidence_repo.append_immutable_version(
                        tenant_id=self.tenant_id,
                        document=doc,
                        chunks=persisted_chunks,
                        write_sequence=write_sequence,
                        canonical_source=canonical_source,
                        correction_of_document_version_id=doc_meta.get("correction_of_document_version_id"),
                    )
                    bound_scope = await bind_active_policy_projection(
                        self.session,
                        tenant_id=self.tenant_id,
                        document=doc,
                        blocks=db_blocks,
                        chunks=persisted_chunks,
                        document_version=document_version,
                        chunk_versions=chunk_versions,
                    )
                    if active_scope is not None and bound_scope != active_scope:
                        raise PolicyCorpusScopeUnavailable("active policy corpus pointer changed during ingestion")
            if job is not None:
                _mark_job_success(
                    job,
                    doc_id=doc.id,
                    parse_result=parse_result,
                    blocks=len(blocks),
                    chunks=len(persisted_chunks),
                    assembled_inputs=assembled_inputs,
                    embedding_usage=embedding_usage,
                )
            await self.session.commit()

            return IngestionReport(
                doc_key=doc_key,
                title=title,
                status="success",
                chunks_created=chunks_created,
                job_id=getattr(job, "id", None) if job is not None else None,
                evidence_write_sequence=write_sequence,
                rollout_version=writer_rollout_version,
            )
        except Exception as exc:
            await self.session.rollback()
            if doc is not None and doc_snapshot is not None:
                _restore_document(doc, doc_snapshot)
            elif doc is not None and job is not None and getattr(job, "doc_id", None) == doc.id:
                job.doc_id = None
            safe_message = _safe_message(str(exc), default="Document replacement failed safely.")
            failure_job = job
            if isinstance(self.session, AsyncSession) and durable_job_id is not None:
                failure_job = await self.session.get(RagIngestionJob, durable_job_id)
            if failure_job is not None:
                await self._mark_job_failed(
                    job=failure_job,
                    stage="persisting",
                    error_code="db_write_failed",
                    safe_message=safe_message,
                    counts={"chunks_created": 0},
                )
            return IngestionReport(
                doc_key=doc_key,
                title=title,
                status="failed",
                error=safe_message,
                job_id=durable_job_id,
                error_code="db_write_failed",
                safe_message=safe_message,
                evidence_write_sequence=None,
                rollout_version=None,
            )

    async def ingest_directory(self, dir_path: Path, manifest: list[dict]) -> list[IngestionReport]:
        """Process all documents in manifest and report per-document status."""
        reports = []
        for doc_meta in manifest:
            file_path = dir_path / doc_meta["file"]
            report = await self.ingest_document(file_path, doc_meta)
            reports.append(report)
        return reports

    async def _get_existing_document_without_lock(self, doc_key: str) -> PolicyDocument | None:
        getter = getattr(self.doc_repo, "get_by_doc_key", None)
        if getter is None:
            return None
        return await getter(doc_key, self.tenant_id)

    async def _create_job_trace(
        self,
        *,
        doc_id: UUID | None,
        doc_key: str,
        source_type: str,
        source_checksum: str,
        stage: str,
        status: str,
        commit_immediately: bool = True,
    ) -> RagIngestionJob | None:
        job = RagIngestionJob(
            id=uuid4(),
            tenant_id=self.tenant_id,
            doc_id=doc_id,
            doc_key=doc_key,
            source_type=_safe_source_type_for_persistence(source_type),
            source_checksum=source_checksum,
            parser_name="moca_parser_registry",
            parser_version="21.02",
            stage=stage,
            status=status,
            warnings_json=[],
            counts_json={},
            timings_json={},
            started_at=_utc_now(),
        )
        try:
            await self.job_repo.create(job)
            if commit_immediately:
                await self.session.commit()
            return job
        except Exception:
            if not commit_immediately:
                raise
            await self.session.rollback()
            return None

    async def _finish_preflight_failure(
        self,
        *,
        job: RagIngestionJob | None,
        doc_key: str,
        title: str,
        parse_result: ParseResult | None,
        stage: str,
        default_code: str,
        default_message: str,
        counts: dict[str, Any] | None = None,
    ) -> IngestionReport:
        error_code = _safe_trace_scalar(default_code, default="parser_failed")
        safe_message = _safe_message(
            parse_result.safe_message if parse_result is not None else default_message,
            default=default_message,
        )
        if job is not None:
            if parse_result is not None:
                job.parser_name = _safe_trace_scalar(parse_result.parser_name, default="unknown_parser")
                job.parser_version = _safe_trace_scalar(parse_result.parser_version, default="unknown")
                job.source_type = _safe_source_type_for_persistence(parse_result.source_type)
            await self._mark_job_failed(
                job=job,
                stage=stage,
                error_code=error_code,
                safe_message=safe_message,
                counts=counts or {"chunks_created": 0},
            )
        return IngestionReport(
            doc_key=doc_key,
            title=title,
            status="failed",
            error=safe_message,
            chunks_created=0,
            job_id=getattr(job, "id", None) if job is not None else None,
            error_code=error_code,
            safe_message=safe_message,
        )

    async def _mark_job_failed(
        self,
        *,
        job: RagIngestionJob,
        stage: str,
        error_code: str,
        safe_message: str,
        counts: dict[str, Any] | None = None,
    ) -> bool:
        job.stage = stage
        job.status = "failed"
        job.error_code = _safe_trace_scalar(error_code, default="ingestion_failed")
        job.safe_message = _safe_message(safe_message, default="Policy ingestion failed safely.")
        job.counts_json = counts or {"chunks_created": 0}
        job.completed_at = _utc_now()
        try:
            validate_rag_ingestion_job(job)
            await self.session.commit()
            return True
        except Exception:
            await self.session.rollback()
            return False


_SOURCE_TYPE_BY_EXTENSION = {
    ".md": "policy_markdown",
    ".markdown": "policy_markdown",
    ".txt": "policy_plain_text",
    ".text": "policy_plain_text",
    ".pdf": "policy_pdf",
    ".docx": "policy_docx",
    ".png": "policy_image",
    ".jpg": "policy_image",
    ".jpeg": "policy_image",
    ".tif": "policy_image",
    ".tiff": "policy_image",
}
_SAFE_JOB_SOURCE_TYPE = re.compile(r"^[a-z0-9][a-z0-9_]{0,31}$")
_SAFE_TRACE_SCALAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_UNSAFE_MESSAGE_PATTERNS = (
    re.compile(r"/(?:Users|home|tmp|var|private|Volumes)/"),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"raw[_ -]?(?:payload|parser|bytes|dump)", re.IGNORECASE),
    re.compile(r"parser_dump", re.IGNORECASE),
    re.compile(r"\b(?:Tool\s+System|ToolResultV2|BusinessFactRefV1)\b", re.IGNORECASE),
    re.compile(r"\bbusiness[_ -]?(?:object|artifact|fact)[_ -]?(?:payload|ref|refs|json|output)\b", re.IGNORECASE),
    re.compile(r"\b(?:order|refund|ticket|merchant|customer)_(?:id|payload|json)\b", re.IGNORECASE),
)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _source_type_for(file_path: Path, doc_meta: dict[str, Any]) -> str:
    return str(doc_meta.get("source_type") or _SOURCE_TYPE_BY_EXTENSION.get(file_path.suffix.lower()) or "unsupported")


def _safe_source_type_for_persistence(source_type: Any) -> str:
    value = str(source_type or "unsupported").strip().lower()
    if _SAFE_JOB_SOURCE_TYPE.fullmatch(value):
        return value
    return "unsupported"


def _safe_trace_scalar(value: Any, *, default: str) -> str:
    text = str(value or default).strip() or default
    if (
        _CONTROL_CHARS.search(text)
        or any(pattern.search(text) for pattern in _UNSAFE_MESSAGE_PATTERNS)
        or not _SAFE_TRACE_SCALAR.fullmatch(text)
    ):
        return default
    return text


def _source_checksum(file_path: Path) -> str:
    try:
        return "sha256:" + hashlib.sha256(file_path.read_bytes()).hexdigest()
    except OSError:
        return "sha256:unavailable"


def _safe_message(message: str | None, *, default: str) -> str:
    value = (message or default).strip() or default
    if _CONTROL_CHARS.search(value) or any(pattern.search(value) for pattern in _UNSAFE_MESSAGE_PATTERNS):
        value = default
    return value[:500]


def _read_report_field(job: RagIngestionJob | Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if isinstance(job, Mapping):
            if name in job:
                return job[name]
            continue
        if hasattr(job, name):
            return getattr(job, name)
    return None


def _safe_report_message(value: Any) -> str | None:
    if value is None:
        return None
    safe_value = _safe_report_value(value)
    if safe_value is None:
        return "Policy ingestion message was redacted."
    return _safe_message(str(safe_value), default="Policy ingestion message was redacted.")


def _safe_report_scalar(value: Any) -> Any:
    safe_value = _safe_report_value(value)
    if isinstance(safe_value, dict | list):
        return None
    return safe_value


def _safe_report_mapping(value: Any) -> dict[str, Any]:
    safe_value = _safe_report_value(value)
    return safe_value if isinstance(safe_value, dict) else {}


def _safe_report_list(value: Any) -> list[Any]:
    safe_value = _safe_report_value(value)
    return safe_value if isinstance(safe_value, list) else []


def _safe_report_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if _is_forbidden_report_key(key_text):
                continue
            safe_nested = _safe_report_value(nested)
            if safe_nested is not None:
                safe[key_text] = safe_nested
        return safe
    if isinstance(value, list):
        safe_items = []
        for nested in value:
            safe_nested = _safe_report_value(nested)
            if safe_nested is not None:
                safe_items.append(safe_nested)
        return safe_items
    if isinstance(value, tuple):
        return _safe_report_value(list(value))
    if isinstance(value, bytes | bytearray | memoryview):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Path):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or _CONTROL_CHARS.search(text) or any(pattern.search(text) for pattern in _UNSAFE_MESSAGE_PATTERNS):
            return None
        return text
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)


def _is_forbidden_report_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized in _FORBIDDEN_REPORT_KEYS


def _utc_now() -> datetime:
    return datetime.now(UTC)


@lru_cache(maxsize=1)
def _default_embedding_token_counter() -> EmbeddingTokenCounter:
    return EmbeddingTokenCounter(load_embedding_tokenizer_config())


def _assembler_for_mode(mode: IngestionAssemblyMode) -> PolicyInputAssembler:
    counter = _default_embedding_token_counter()
    if mode is IngestionAssemblyMode.CHARACTER_COMPATIBILITY:
        return CharacterCompatibilityAssembler(counter=counter)
    return PolicyEmbeddingInputAssembler(counter=counter)


def assembler_for_active_policy_corpus(scope: ActivePolicyCorpusScope) -> PolicyInputAssembler:
    """Select the sole assembler matching one internally resolved active config."""

    counter = _default_embedding_token_counter()
    character = CharacterCompatibilityAssembler(counter=counter)
    if (
        scope.generation_name == "character.v1"
        and scope.config_schema_version == CHARACTER_COMPATIBILITY_CONFIG_VERSION
        and scope.config_fingerprint == character.config_fingerprint
    ):
        return character
    token_config = counter.config
    if (
        scope.generation_name != "character.v1"
        and scope.config_schema_version == token_config.schema_version
        and scope.config_fingerprint == token_config.config_fingerprint
    ):
        return PolicyEmbeddingInputAssembler(counter=counter)
    raise PolicyCorpusConfigError("active_policy_corpus_config_unavailable")


def _character_compatibility_config_fingerprint(counter: EmbeddingTokenCounter) -> str:
    payload = {
        "schema_version": CHARACTER_COMPATIBILITY_CONFIG_VERSION,
        "embedding_tokenizer_config_fingerprint": counter.config.config_fingerprint,
        "max_chars": _CHARACTER_COMPATIBILITY_MAX_CHARS,
        "target_chars": _CHARACTER_COMPATIBILITY_TARGET_CHARS,
        "overlap_chars": _CHARACTER_COMPATIBILITY_OVERLAP_CHARS,
        "provider_input_envelope": "legacy_ingestion.v1",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _embed_with_usage_audit(
    embedder: EmbeddingService,
    texts: list[str],
) -> tuple[list[list[float]], EmbeddingBatchResultV1 | None]:
    embed_with_usage = getattr(embedder, "embed_documents_with_usage", None)
    if callable(embed_with_usage):
        result = await embed_with_usage(texts)
        return [list(vector) for vector in result.embeddings], result
    return await embedder.embed_documents(texts), None


def _render_character_compatibility_input(*, title: str, chunk: BlockChunkResult) -> str:
    prefix = f"{title}: {chunk.content}" if chunk.section == "intro" else f"{title} / {chunk.section}: {chunk.content}"
    source_context = " ".join(
        f"source_block_id={ref['source_block_id']}" for ref in chunk.source_block_refs if ref.get("source_block_id")
    )
    if source_context:
        return f"{prefix}\n{source_context}"
    return prefix


def _parser_metadata(parse_result: ParseResult) -> dict[str, Any]:
    return {
        "source_type": _safe_source_type_for_persistence(parse_result.source_type),
        "parser_name": _safe_trace_scalar(parse_result.parser_name, default="unknown_parser"),
        "parser_version": _safe_trace_scalar(parse_result.parser_version, default="unknown"),
        "warning_codes": [warning.code for warning in parse_result.warnings],
    }


def _block_parser_metadata(block: ParsedBlock) -> dict[str, Any]:
    return {
        "source_type": _safe_source_type_for_persistence(block.source_type),
        "parser_name": _safe_trace_scalar(block.parser_name, default="unknown_parser"),
        "parser_version": _safe_trace_scalar(block.parser_version, default="unknown"),
        "warning_codes": [warning.code for warning in block.warnings],
    }


def _document_blocks_from_parsed(
    *,
    tenant_id: UUID,
    doc_id: UUID,
    blocks: tuple[ParsedBlock, ...],
    parse_result: ParseResult,
) -> list[DocumentBlock]:
    rows: list[DocumentBlock] = []
    for block in blocks:
        rows.append(
            DocumentBlock(
                tenant_id=tenant_id,
                doc_id=doc_id,
                source_block_id=block.source_block_id,
                block_index=block.block_index,
                block_type=block.block_type,
                text=block.text,
                normalized_text=block.normalized_text,
                text_hash=evidence_text_hash(block.text),
                page_number=block.page_number,
                bbox_json=asdict(block.box) if block.box is not None else {},
                table_metadata_json=dict(block.table_metadata),
                parser_metadata_json=_block_parser_metadata(block) or _parser_metadata(parse_result),
                ocr_metadata_json=dict(block.ocr_metadata),
                source_uri=None,
            )
        )
    return rows


def _policy_chunks_from_embedding_inputs(
    *,
    tenant_id: UUID,
    doc_id: UUID,
    title: str,
    doc_type: str,
    risk_level: str,
    effective_date: date,
    assembled_inputs: Sequence[PolicyEmbeddingInputV1],
    embeddings: list[list[float]],
) -> list[PolicyChunk]:
    db_chunks: list[PolicyChunk] = []
    for index, assembled in enumerate(assembled_inputs):
        db_chunks.append(
            PolicyChunk(
                tenant_id=tenant_id,
                doc_id=doc_id,
                chunk_id=assembled.chunk_id,
                section=assembled.section,
                content=assembled.citation_content,
                search_text=assembled.search_text,
                source_block_refs_json=[dict(ref) for ref in assembled.source_block_refs],
                ocr_metadata_json=_chunk_ocr_metadata(assembled),
                risk_level=risk_level,
                effective_date=effective_date,
                embedding=embeddings[index],
                chunking_config_fingerprint=assembled.chunking_config_fingerprint,
                embedding_input_hash=assembled.embedding_input_hash,
                embedding_token_count=assembled.embedding_token_count,
            )
        )
    return db_chunks


def _chunk_ocr_metadata(chunk: PolicyEmbeddingInputV1) -> dict[str, Any]:
    ocr_refs = [ref["ocr"] for ref in chunk.source_block_refs if "ocr" in ref]
    return {"blocks": ocr_refs} if ocr_refs else {}


def _chunk_heading_path(chunk: BlockChunkResult) -> tuple[str, ...]:
    return (chunk.section,) if chunk.section and chunk.section != "intro" else ()


def _chunk_table_headers(chunk: BlockChunkResult) -> tuple[str, ...]:
    table = chunk.metadata.get("table", {})
    headers = table.get("headers") if isinstance(table, dict) else None
    if not isinstance(headers, list):
        return ()
    return tuple(str(header) for header in headers if str(header).strip())


def _chunk_source_context(chunk: BlockChunkResult) -> tuple[str, ...]:
    parts: list[str] = []
    for ref in chunk.source_block_refs:
        source_block_id = ref.get("source_block_id")
        if source_block_id:
            parts.append(f"source_block_id={source_block_id}")
        page_number = ref.get("page_number")
        if page_number is not None:
            parts.append(f"page={page_number}")
    return tuple(parts)


def _mark_job_success(
    job: RagIngestionJob,
    *,
    doc_id: UUID,
    parse_result: ParseResult,
    blocks: int,
    chunks: int,
    assembled_inputs: Sequence[PolicyEmbeddingInputV1],
    embedding_usage: EmbeddingBatchResultV1 | None,
) -> None:
    config_fingerprints = {item.chunking_config_fingerprint for item in assembled_inputs}
    if len(config_fingerprints) != 1:
        raise ValueError("mixed_chunking_config_fingerprints")
    token_counts = [item.embedding_token_count for item in assembled_inputs]
    job.doc_id = doc_id
    job.parser_name = _safe_trace_scalar(parse_result.parser_name, default="unknown_parser")
    job.parser_version = _safe_trace_scalar(parse_result.parser_version, default="unknown")
    job.source_type = _safe_source_type_for_persistence(parse_result.source_type)
    job.stage = "completed"
    job.status = "success"
    job.error_code = None
    job.safe_message = None
    job.warnings_json = [{"code": warning.code} for warning in parse_result.warnings]
    job.counts_json = {"blocks": blocks, "chunks": chunks, "chunks_created": chunks}
    job.chunking_config_fingerprint = next(iter(config_fingerprints))
    job.chunk_count = len(assembled_inputs)
    job.embedding_token_count_min = min(token_counts)
    job.embedding_token_count_max = max(token_counts)
    job.embedding_token_count_total = sum(token_counts)
    job.provider_prompt_tokens = embedding_usage.prompt_tokens if embedding_usage is not None else None
    job.provider_total_tokens = embedding_usage.total_tokens if embedding_usage is not None else None
    job.provider_usage_status = (
        "available"
        if embedding_usage is not None and embedding_usage.usage_status is EmbeddingUsageStatus.REPORTED
        else "unavailable"
    )
    job.completed_at = _utc_now()
    validate_rag_ingestion_job(job)


def _snapshot_document(doc: Any) -> dict[str, Any]:
    fields = (
        "version",
        "content",
        "title",
        "doc_type",
        "risk_level",
        "effective_date",
        "source_type",
        "source_checksum",
        "parser_metadata_json",
        "policy_version_fingerprint",
    )
    return {field: getattr(doc, field, None) for field in fields}


def _restore_document(doc: Any, snapshot: dict[str, Any]) -> None:
    for field, value in snapshot.items():
        setattr(doc, field, value)
