from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DocumentBlock, PolicyChunk, PolicyDocument, RagIngestionJob
from src.knowledge.text_hash import evidence_text_hash
from src.rag.chunker import BlockChunkResult, chunk_blocks
from src.rag.embedder import EmbeddingService
from src.rag.parsers.base import ParsedBlock, ParseResult
from src.rag.parsers.registry import ParserRegistry
from src.rag.search_text import build_policy_chunk_search_text
from src.rag.versioning import build_policy_version_fingerprint
from src.repositories.document_block_repo import DocumentBlockRepository
from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.policy_document_repo import PolicyDocumentRepository
from src.repositories.rag_ingestion_job_repo import RagIngestionJobRepository


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


class IngestionService:
    def __init__(self, session: AsyncSession, embedder: EmbeddingService, tenant_id: UUID):
        self.session = session
        self.embedder = embedder
        self.tenant_id = tenant_id
        self.chunk_repo = PolicyChunkRepository(session)
        self.doc_repo = PolicyDocumentRepository(session)
        self.block_repo = DocumentBlockRepository(session)
        self.job_repo = RagIngestionJobRepository(session)
        self.parser_registry = ParserRegistry()

    async def ingest_document(self, file_path: Path, doc_meta: dict) -> IngestionReport:
        """
        Ingest one policy document.

        Parsing, chunking, and embeddings complete before the short locked
        document replacement transaction mutates committed policy rows.
        """
        doc_key = doc_meta["doc_key"]
        title = doc_meta["title"]
        source_type = _source_type_for(file_path, doc_meta)
        source_checksum = _source_checksum(file_path)
        effective_date = doc_meta.get("effective_date")
        job: RagIngestionJob | None = None

        try:
            preexisting_doc = await self._get_existing_document_without_lock(doc_key)
        except Exception:
            preexisting_doc = None

        if preexisting_doc is not None:
            job = await self._create_job_trace(
                doc_id=preexisting_doc.id,
                doc_key=doc_key,
                source_type=source_type,
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

        try:
            parse_result = self.parser_registry.parse(
                file_path,
                doc_key=doc_key,
                source_type=source_type,
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
            chunks = chunk_blocks(blocks, doc_key=doc_key)
            if not chunks:
                return await self._finish_preflight_failure(
                    job=job,
                    doc_key=doc_key,
                    title=title,
                    parse_result=parse_result,
                    stage="chunking",
                    default_code="no_chunks_produced",
                    default_message="Policy source did not produce visible chunks.",
                )

            texts = [_embedding_text(title=title, chunk=chunk) for chunk in chunks]
            embeddings = await self.embedder.embed_documents(texts)
            if len(embeddings) != len(chunks):
                msg = f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}"
                return await self._finish_preflight_failure(
                    job=job,
                    doc_key=doc_key,
                    title=title,
                    parse_result=parse_result,
                    stage="embedding",
                    default_code="embedding_count_mismatch",
                    default_message=msg,
                    counts={"chunks": len(chunks), "embeddings": len(embeddings)},
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
        try:
            # Lock the existing row through the final commit so concurrent
            # re-imports cannot write the same next content version.
            existing_doc = await self.doc_repo.get_by_doc_key_for_update(doc_key, self.tenant_id)
            if existing_doc:
                doc = existing_doc
                doc_snapshot = _snapshot_document(doc)
                content = _document_citation_text(chunks)
                effective_date = effective_date or doc.effective_date or date.today()
                fingerprint = build_policy_version_fingerprint(
                    citation_text=content,
                    title=title,
                    doc_type=doc_meta["doc_type"],
                    risk_level=doc_meta["risk_level"],
                    effective_date=effective_date,
                )
                previous_fingerprint = getattr(doc, "policy_version_fingerprint", None)
                fingerprint_changed = doc.content != content if previous_fingerprint is None else previous_fingerprint != fingerprint
                if fingerprint_changed:
                    doc.version = (doc.version or 1) + 1
                doc.title = title
                doc.doc_type = doc_meta["doc_type"]
                doc.risk_level = doc_meta["risk_level"]
                doc.effective_date = effective_date
                doc.content = content
                doc.source_type = parse_result.source_type
                doc.source_checksum = source_checksum
                doc.parser_metadata_json = _parser_metadata(parse_result)
                doc.policy_version_fingerprint = fingerprint
            else:
                effective_date = effective_date or date.today()
                content = _document_citation_text(chunks)
                fingerprint = build_policy_version_fingerprint(
                    citation_text=content,
                    title=title,
                    doc_type=doc_meta["doc_type"],
                    risk_level=doc_meta["risk_level"],
                    effective_date=effective_date,
                )
                doc = PolicyDocument(
                    id=uuid4(),
                    tenant_id=self.tenant_id,
                    doc_key=doc_key,
                    doc_type=doc_meta["doc_type"],
                    title=title,
                    effective_date=effective_date,
                    risk_level=doc_meta["risk_level"],
                    content=content,
                    source_type=parse_result.source_type,
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
                        source_type=source_type,
                        source_checksum=source_checksum,
                        stage="persisting",
                        status="running",
                        commit_immediately=False,
                    )

            await self.block_repo.delete_by_document_id(doc.id, self.tenant_id)
            await self.chunk_repo.delete_by_document_id(doc.id, self.tenant_id)
            db_blocks = _document_blocks_from_parsed(
                tenant_id=self.tenant_id,
                doc_id=doc.id,
                blocks=blocks,
                parse_result=parse_result,
            )
            db_chunks = _policy_chunks_from_block_chunks(
                tenant_id=self.tenant_id,
                doc_id=doc.id,
                title=title,
                doc_type=doc_meta["doc_type"],
                risk_level=doc_meta["risk_level"],
                effective_date=effective_date,
                chunks=chunks,
                embeddings=embeddings,
            )
            await self.block_repo.bulk_insert(db_blocks)
            await self.chunk_repo.bulk_insert(db_chunks)
            if job is not None:
                _mark_job_success(job, doc_id=doc.id, parse_result=parse_result, blocks=len(blocks), chunks=len(chunks))
            await self.session.commit()

            return IngestionReport(
                doc_key=doc_key,
                title=title,
                status="success",
                chunks_created=len(db_chunks),
                job_id=getattr(job, "id", None) if job is not None else None,
            )
        except Exception as exc:
            await self.session.rollback()
            if doc is not None and doc_snapshot is not None:
                _restore_document(doc, doc_snapshot)
            safe_message = _safe_message(str(exc), default="Document replacement failed safely.")
            if job is not None:
                await self._mark_job_failed(
                    job=job,
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
                job_id=getattr(job, "id", None) if job is not None else None,
                error_code="db_write_failed",
                safe_message=safe_message,
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
        doc_id: UUID,
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
            source_type=source_type,
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
        error_code = default_code
        safe_message = _safe_message(
            parse_result.safe_message if parse_result is not None else default_message,
            default=default_message,
        )
        if job is not None:
            if parse_result is not None:
                job.parser_name = parse_result.parser_name
                job.parser_version = parse_result.parser_version
                job.source_type = parse_result.source_type
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
        job.error_code = error_code
        job.safe_message = _safe_message(safe_message, default="Policy ingestion failed safely.")
        job.counts_json = counts or {"chunks_created": 0}
        job.completed_at = _utc_now()
        try:
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
_UNSAFE_MESSAGE_PATTERNS = (
    re.compile(r"/(?:Users|home|tmp|var|private|Volumes)/"),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"raw[_ -]?(?:payload|parser|bytes|dump)", re.IGNORECASE),
    re.compile(r"parser_dump", re.IGNORECASE),
)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _source_type_for(file_path: Path, doc_meta: dict[str, Any]) -> str:
    return str(doc_meta.get("source_type") or _SOURCE_TYPE_BY_EXTENSION.get(file_path.suffix.lower()) or "unsupported")


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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _document_citation_text(chunks: list[BlockChunkResult]) -> str:
    return "\n\n".join(chunk.content for chunk in chunks).strip()


def _embedding_text(*, title: str, chunk: BlockChunkResult) -> str:
    prefix = f"{title}: {chunk.content}" if chunk.section == "intro" else f"{title} / {chunk.section}: {chunk.content}"
    source_context = " ".join(
        f"source_block_id={ref['source_block_id']}"
        for ref in chunk.source_block_refs
        if ref.get("source_block_id")
    )
    if source_context:
        return f"{prefix}\n{source_context}"
    return prefix


def _parser_metadata(parse_result: ParseResult) -> dict[str, Any]:
    return {
        "source_type": parse_result.source_type,
        "parser_name": parse_result.parser_name,
        "parser_version": parse_result.parser_version,
        "warning_codes": [warning.code for warning in parse_result.warnings],
    }


def _block_parser_metadata(block: ParsedBlock) -> dict[str, Any]:
    return {
        "source_type": block.source_type,
        "parser_name": block.parser_name,
        "parser_version": block.parser_version,
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


def _policy_chunks_from_block_chunks(
    *,
    tenant_id: UUID,
    doc_id: UUID,
    title: str,
    doc_type: str,
    risk_level: str,
    effective_date: date,
    chunks: list[BlockChunkResult],
    embeddings: list[list[float]],
) -> list[PolicyChunk]:
    db_chunks: list[PolicyChunk] = []
    for index, chunk in enumerate(chunks):
        db_chunks.append(
            PolicyChunk(
                tenant_id=tenant_id,
                doc_id=doc_id,
                chunk_id=chunk.chunk_id,
                section=chunk.section,
                content=chunk.content,
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
                source_block_refs_json=[dict(ref) for ref in chunk.source_block_refs],
                ocr_metadata_json=_chunk_ocr_metadata(chunk),
                risk_level=risk_level,
                effective_date=effective_date,
                embedding=embeddings[index],
            )
        )
    return db_chunks


def _chunk_ocr_metadata(chunk: BlockChunkResult) -> dict[str, Any]:
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
) -> None:
    job.doc_id = doc_id
    job.parser_name = parse_result.parser_name
    job.parser_version = parse_result.parser_version
    job.source_type = parse_result.source_type
    job.stage = "completed"
    job.status = "success"
    job.error_code = None
    job.safe_message = None
    job.warnings_json = [{"code": warning.code} for warning in parse_result.warnings]
    job.counts_json = {"blocks": blocks, "chunks": chunks, "chunks_created": chunks}
    job.completed_at = _utc_now()


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
