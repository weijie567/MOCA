from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DocumentBlock
from src.knowledge.text_hash import evidence_text_hash
from src.rag.parsers.base import ParsedBlock


MAX_DOCUMENT_BLOCK_TEXT_LENGTH = 20_000
CANONICAL_DOCUMENT_CONTENT_SCHEMA_VERSION = "canonical_document_content.v2"
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


@dataclass(frozen=True, slots=True)
class CanonicalDocumentContentV2:
    """Chunk-independent canonical source material for new document versions."""

    schema_version: str
    content: str
    content_hash: str
    blocks_json: tuple[dict[str, Any], ...]
    blocks_hash: str


def build_canonical_document_content(blocks: Sequence[ParsedBlock]) -> CanonicalDocumentContentV2:
    """Project authoritative parser blocks before any chunking or overlap."""

    ordered = sorted(blocks, key=lambda block: (block.block_index, block.source_block_id))
    block_indexes = [block.block_index for block in ordered]
    if len(set(block_indexes)) != len(block_indexes):
        raise ValueError("canonical_document_block_order_ambiguous")
    source_block_ids = [block.source_block_id for block in ordered]
    if len(set(source_block_ids)) != len(source_block_ids):
        raise ValueError("canonical_document_source_block_duplicate")

    snapshots = tuple(_canonical_block_snapshot(block) for block in ordered)
    canonical_json = json.dumps(
        snapshots,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    content = "\n".join(block.text for block in ordered).strip()
    return CanonicalDocumentContentV2(
        schema_version=CANONICAL_DOCUMENT_CONTENT_SCHEMA_VERSION,
        content=content,
        content_hash=evidence_text_hash(content),
        blocks_json=snapshots,
        blocks_hash="sha256:" + hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    )


def _canonical_block_snapshot(block: ParsedBlock) -> dict[str, Any]:
    return {
        "source_block_id": block.source_block_id,
        "block_index": block.block_index,
        "block_type": block.block_type,
        "text": block.text,
        "normalized_text": block.normalized_text,
        "source_type": block.source_type,
        "parser_name": block.parser_name,
        "parser_version": block.parser_version,
        "page_number": block.page_number,
        "bbox": asdict(block.box) if block.box is not None else None,
        "table_metadata": dict(block.table_metadata),
        "ocr_metadata": dict(block.ocr_metadata),
        "warning_codes": [warning.code for warning in block.warnings],
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
