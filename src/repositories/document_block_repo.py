from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DocumentBlock


MAX_DOCUMENT_BLOCK_TEXT_LENGTH = 20_000
SAFE_WARNING_CODE_KEY = "warning_codes"
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_FORBIDDEN_METADATA_KEYS = {
    "comment_text",
    "debug_ocr_payload",
    "docx_comment",
    "file_path",
    "hidden_pdf_text",
    "hidden_text",
    "local_path",
    "parser_dump",
    "raw",
    "raw_bytes",
    "raw_parser_dump",
    "raw_payload",
    "stack_trace",
}


class DocumentBlockRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_by_document_id(self, document_id: UUID, tenant_id: UUID) -> int:
        stmt = delete(DocumentBlock).where(
            DocumentBlock.doc_id == document_id,
            DocumentBlock.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def bulk_insert(self, blocks: Sequence[DocumentBlock]) -> None:
        for block in blocks:
            validate_document_block(block)
        self.session.add_all(list(blocks))
        await self.session.flush()

    async def list_by_document_id(self, document_id: UUID, tenant_id: UUID) -> list[DocumentBlock]:
        stmt = (
            select(DocumentBlock)
            .where(
                DocumentBlock.doc_id == document_id,
                DocumentBlock.tenant_id == tenant_id,
            )
            .order_by(DocumentBlock.block_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_source_block_ids(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        source_block_ids: Sequence[str],
    ) -> list[DocumentBlock]:
        if not source_block_ids:
            return []
        stmt = (
            select(DocumentBlock)
            .where(
                DocumentBlock.tenant_id == tenant_id,
                DocumentBlock.doc_id == document_id,
                DocumentBlock.source_block_id.in_(list(source_block_ids)),
            )
            .order_by(DocumentBlock.block_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


def validate_document_block(block: DocumentBlock) -> None:
    """Reject unsafe parser/OCR material before it becomes durable block text."""

    if len(block.text) > MAX_DOCUMENT_BLOCK_TEXT_LENGTH:
        raise ValueError("document_block_text_too_long")
    if _CONTROL_CHARS.search(block.text):
        raise ValueError("document_block_text_control_chars")
    _reject_forbidden_metadata_keys(block.parser_metadata_json, "parser_metadata_json")
    _reject_forbidden_metadata_keys(block.ocr_metadata_json, "ocr_metadata_json")


def _reject_forbidden_metadata_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            normalized = key_text.lower()
            if normalized in _FORBIDDEN_METADATA_KEYS and normalized != SAFE_WARNING_CODE_KEY:
                raise ValueError(f"{path}.{key_text} must be represented by safe warning codes")
            _reject_forbidden_metadata_keys(nested, f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_metadata_keys(nested, f"{path}[{index}]")
