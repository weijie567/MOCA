from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.schemas import FORBIDDEN_MESSAGE_KEYS
from src.db.models import RagIngestionJob


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UNSAFE_MESSAGE_PATTERNS = (
    re.compile(r"/(?:Users|home|tmp|var|private|Volumes)/"),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"raw[_ -]?(?:payload|parser|bytes|dump)", re.IGNORECASE),
    re.compile(r"parser_dump", re.IGNORECASE),
)
_SAFE_DOC_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SAFE_SOURCE_TYPE = re.compile(r"^[a-z0-9][a-z0-9_]{0,31}$")
_FORBIDDEN_TRACE_KEYS = FORBIDDEN_MESSAGE_KEYS | {
    "debug_image",
    "debug_payload",
    "exception",
    "file_bytes",
    "file_path",
    "local_path",
    "parser_dump",
    "path",
    "raw",
    "raw_args",
    "raw_bytes",
    "raw_parser_dump",
    "raw_payload",
    "raw_prompt",
    "raw_tool_output",
    "stack",
    "stack_trace",
    "traceback",
}


class RagIngestionJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: RagIngestionJob) -> RagIngestionJob:
        validate_rag_ingestion_job(job)
        self.session.add(job)
        await self.session.flush()
        return job

    async def delete_by_document_id(self, document_id: UUID, tenant_id: UUID) -> int:
        stmt = delete(RagIngestionJob).where(
            RagIngestionJob.doc_id == document_id,
            RagIngestionJob.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def list_by_document_id(self, document_id: UUID, tenant_id: UUID) -> list[RagIngestionJob]:
        stmt = (
            select(RagIngestionJob)
            .where(
                RagIngestionJob.doc_id == document_id,
                RagIngestionJob.tenant_id == tenant_id,
            )
            .order_by(RagIngestionJob.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def latest_by_doc_key(self, *, tenant_id: UUID, doc_key: str) -> RagIngestionJob | None:
        stmt = (
            select(RagIngestionJob)
            .where(
                RagIngestionJob.tenant_id == tenant_id,
                RagIngestionJob.doc_key == doc_key,
            )
            .order_by(RagIngestionJob.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def lock_evaluation_attempt_candidates(
        self,
        *,
        tenant_id: UUID,
        doc_key: str,
        source_checksum: str,
        reserved_at: datetime,
    ) -> list[RagIngestionJob]:
        """Lock at most two post-reservation NULL-document attempts.

        Returning two rows is intentional: the evaluation owner must treat more
        than one candidate as malformed rather than choosing one arbitrarily.
        The caller durably CAS-records the sole UUID before requesting deletion.
        """

        stmt = (
            select(RagIngestionJob)
            .where(
                RagIngestionJob.tenant_id == tenant_id,
                RagIngestionJob.doc_key == doc_key,
                RagIngestionJob.source_checksum == source_checksum,
                RagIngestionJob.created_at >= reserved_at,
                RagIngestionJob.doc_id.is_(None),
            )
            .order_by(RagIngestionJob.created_at, RagIngestionJob.id)
            .limit(2)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def lock_all_evaluation_attempt_jobs(
        self,
        *,
        tenant_id: UUID,
        doc_key: str,
        source_checksum: str,
        reserved_at: datetime,
    ) -> list[RagIngestionJob]:
        """Lock all exact post-reservation jobs for projection classification."""

        stmt = (
            select(RagIngestionJob)
            .where(
                RagIngestionJob.tenant_id == tenant_id,
                RagIngestionJob.doc_key == doc_key,
                RagIngestionJob.source_checksum == source_checksum,
                RagIngestionJob.created_at >= reserved_at,
            )
            .order_by(RagIngestionJob.created_at, RagIngestionJob.id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_exact_evaluation_attempt(
        self,
        *,
        job_id: UUID,
        tenant_id: UUID,
        doc_key: str,
        source_checksum: str,
    ) -> int:
        """Delete one CAS-claimed attempt; never delete by doc-key alone."""

        stmt = delete(RagIngestionJob).where(
            RagIngestionJob.id == job_id,
            RagIngestionJob.tenant_id == tenant_id,
            RagIngestionJob.doc_key == doc_key,
            RagIngestionJob.source_checksum == source_checksum,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0


def validate_rag_ingestion_job(job: RagIngestionJob) -> None:
    _reject_unsafe_scalar(job.doc_key, "doc_key", pattern=_SAFE_DOC_KEY)
    _reject_unsafe_scalar(job.source_type, "source_type", pattern=_SAFE_SOURCE_TYPE)
    _reject_unsafe_scalar(job.source_checksum, "source_checksum")
    _reject_unsafe_scalar(job.parser_name, "parser_name")
    _reject_unsafe_scalar(job.parser_version, "parser_version")
    _reject_unsafe_scalar(job.ocr_engine, "ocr_engine")
    _reject_unsafe_scalar(job.stage, "stage")
    _reject_unsafe_scalar(job.status, "status")
    _reject_unsafe_scalar(job.error_code, "error_code")
    _reject_unsafe_scalar(job.safe_message, "safe_message")
    _reject_forbidden_trace_keys(job.warnings_json, "warnings_json")
    _reject_forbidden_trace_keys(job.counts_json, "counts_json")
    _reject_forbidden_trace_keys(job.timings_json, "timings_json")


def _reject_unsafe_scalar(value: Any, field_name: str, *, pattern: re.Pattern[str] | None = None) -> None:
    if value is None:
        return
    text = str(value)
    if _CONTROL_CHARS.search(text):
        raise ValueError(f"rag_ingestion_job_{field_name}_control_chars")
    if any(unsafe_pattern.search(text) for unsafe_pattern in _UNSAFE_MESSAGE_PATTERNS):
        raise ValueError(f"rag_ingestion_job_{field_name}_not_sanitized")
    if pattern is not None and not pattern.fullmatch(text):
        raise ValueError(f"rag_ingestion_job_{field_name}_invalid")


def _reject_forbidden_trace_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if key_text.lower() in _FORBIDDEN_TRACE_KEYS:
                raise ValueError(f"{path}.{key_text} must not contain raw parser trace data")
            _reject_forbidden_trace_keys(nested, f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_trace_keys(nested, f"{path}[{index}]")
