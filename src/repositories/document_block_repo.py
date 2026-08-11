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

from src.db.models import (
    CorpusBlockBinding,
    CorpusDocumentBinding,
    DocumentBlock,
    PolicyDocument,
    PolicyDocumentVersion,
)
from src.knowledge.text_hash import evidence_text_hash
from src.rag.parsers.base import ParsedBlock, ParserWarning, SourceBox
from src.repositories.policy_corpus_scope import (
    ActivePolicyCorpusScope,
    PolicyCorpusScopeUnavailable,
    active_block_ids,
    join_active_block_projection,
)


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


@dataclass(frozen=True, slots=True)
class AuthoritativePolicyDocumentSnapshotV1:
    """Sealed, corpus-qualified policy source loaded exclusively from PostgreSQL."""

    tenant_id: UUID
    source_corpus_version_id: UUID
    policy_document_id: UUID
    policy_document_version_id: UUID
    doc_key: str
    document_version: int
    doc_type: str
    title: str
    effective_date: Any
    risk_level: str
    source_type: str
    source_checksum: str
    evidence_write_sequence: int | None
    blocks: tuple[ParsedBlock, ...]
    block_ids: tuple[UUID, ...]
    canonical_source: CanonicalDocumentContentV2
    snapshot_hash: str


class AuthoritativeSourceSnapshotError(RuntimeError):
    """Safe refusal when a sealed manifest does not match its database source."""


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
            DocumentBlock.id.in_(active_block_ids(tenant_id=tenant_id, document_id=document_id)),
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def bulk_insert(self, blocks: Sequence[DocumentBlock]) -> None:
        tenant_ids = {block.tenant_id for block in blocks}
        if len(tenant_ids) != 1:
            raise PolicyCorpusScopeUnavailable("one tenant active policy corpus is required")
        tenant_id = next(iter(tenant_ids))
        await ActivePolicyCorpusScope.resolve(self.session, tenant_id=tenant_id)
        for block in blocks:
            validate_document_block(block)
        self.session.add_all(list(blocks))
        await self.session.flush()

    async def list_by_document_id(self, document_id: UUID, tenant_id: UUID) -> list[DocumentBlock]:
        stmt = join_active_block_projection(
            select(DocumentBlock).where(
                DocumentBlock.doc_id == document_id,
                DocumentBlock.tenant_id == tenant_id,
            ),
            tenant_id=tenant_id,
        )
        stmt = stmt.order_by(DocumentBlock.block_index)
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
        stmt = join_active_block_projection(
            select(DocumentBlock).where(
                DocumentBlock.tenant_id == tenant_id,
                DocumentBlock.doc_id == document_id,
                DocumentBlock.source_block_id.in_(list(source_block_ids)),
            ),
            tenant_id=tenant_id,
        )
        stmt = stmt.order_by(DocumentBlock.block_index)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def load_authoritative_snapshot(
        self,
        *,
        tenant_id: UUID,
        source_corpus_version_id: UUID,
        manifest_document: Mapping[str, Any],
    ) -> AuthoritativePolicyDocumentSnapshotV1:
        """Lock and snapshot one manifest document from an explicit source corpus."""

        try:
            policy_document_id = UUID(str(manifest_document["policy_document_id"]))
            policy_document_version_id = UUID(str(manifest_document["policy_document_version_id"]))
            doc_key = str(manifest_document["doc_key"])
            document_version = int(manifest_document["document_version"])
            expected_source_checksum = str(manifest_document["source_checksum"])
            expected_block_ids = tuple(str(value) for value in manifest_document["source_block_ids"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthoritativeSourceSnapshotError("source_manifest_document_invalid") from exc

        document_row = (
            await self.session.execute(
                select(PolicyDocument, PolicyDocumentVersion)
                .join(
                    CorpusDocumentBinding,
                    (CorpusDocumentBinding.tenant_id == tenant_id)
                    & (CorpusDocumentBinding.corpus_version_id == source_corpus_version_id)
                    & (CorpusDocumentBinding.policy_document_id == PolicyDocument.id),
                )
                .join(
                    PolicyDocumentVersion,
                    (PolicyDocumentVersion.tenant_id == tenant_id)
                    & (PolicyDocumentVersion.id == CorpusDocumentBinding.policy_document_version_id),
                )
                .where(
                    PolicyDocument.tenant_id == tenant_id,
                    PolicyDocument.id == policy_document_id,
                    PolicyDocument.doc_key == doc_key,
                    PolicyDocumentVersion.id == policy_document_version_id,
                    PolicyDocumentVersion.document_version == document_version,
                )
                .with_for_update()
            )
        ).one_or_none()
        if document_row is None:
            raise AuthoritativeSourceSnapshotError("source_document_binding_missing")
        document, immutable_document = document_row
        if document.source_checksum != expected_source_checksum:
            raise AuthoritativeSourceSnapshotError("source_document_checksum_mismatch")

        block_rows = list(
            (
                await self.session.execute(
                    select(DocumentBlock)
                    .join(
                        CorpusBlockBinding,
                        (CorpusBlockBinding.tenant_id == tenant_id)
                        & (CorpusBlockBinding.corpus_version_id == source_corpus_version_id)
                        & (CorpusBlockBinding.document_block_id == DocumentBlock.id)
                        & (CorpusBlockBinding.policy_document_version_id == policy_document_version_id),
                    )
                    .where(
                        DocumentBlock.tenant_id == tenant_id,
                        DocumentBlock.doc_id == policy_document_id,
                    )
                    .order_by(DocumentBlock.block_index, DocumentBlock.id)
                    .with_for_update()
                )
            ).scalars()
        )
        if tuple(block.source_block_id for block in block_rows) != expected_block_ids:
            raise AuthoritativeSourceSnapshotError("source_block_coverage_mismatch")
        parsed_blocks = tuple(
            _parsed_block_from_row(block, source_type=str(document.source_type or "unknown")) for block in block_rows
        )
        canonical_source = build_canonical_document_content(parsed_blocks)
        if not _immutable_source_matches(immutable_document, canonical_source, expected_source_checksum):
            raise AuthoritativeSourceSnapshotError("source_immutable_document_mismatch")
        snapshot_hash = _authoritative_snapshot_hash(
            document=document,
            immutable_document=immutable_document,
            blocks=block_rows,
            canonical_source=canonical_source,
        )
        return AuthoritativePolicyDocumentSnapshotV1(
            tenant_id=tenant_id,
            source_corpus_version_id=source_corpus_version_id,
            policy_document_id=document.id,
            policy_document_version_id=immutable_document.id,
            doc_key=document.doc_key,
            document_version=int(document.version),
            doc_type=document.doc_type,
            title=document.title,
            effective_date=document.effective_date,
            risk_level=document.risk_level,
            source_type=str(document.source_type or "unknown"),
            source_checksum=expected_source_checksum,
            evidence_write_sequence=document.evidence_write_sequence,
            blocks=parsed_blocks,
            block_ids=tuple(block.id for block in block_rows),
            canonical_source=canonical_source,
            snapshot_hash=snapshot_hash,
        )

    async def recheck_authoritative_snapshot(
        self,
        snapshot: AuthoritativePolicyDocumentSnapshotV1,
        *,
        manifest_document: Mapping[str, Any],
    ) -> None:
        current = await self.load_authoritative_snapshot(
            tenant_id=snapshot.tenant_id,
            source_corpus_version_id=snapshot.source_corpus_version_id,
            manifest_document=manifest_document,
        )
        if current.snapshot_hash != snapshot.snapshot_hash:
            raise AuthoritativeSourceSnapshotError("source_snapshot_drift")


def _parsed_block_from_row(block: DocumentBlock, *, source_type: str) -> ParsedBlock:
    parser = dict(block.parser_metadata_json or {})
    bbox = dict(block.bbox_json or {})
    warning_codes = parser.get("warning_codes", [])
    if not isinstance(warning_codes, list):
        warning_codes = []
    return ParsedBlock(
        source_block_id=block.source_block_id,
        block_index=block.block_index,
        block_type=block.block_type,  # type: ignore[arg-type]
        text=block.text,
        normalized_text=block.normalized_text,
        source_type=str(parser.get("source_type") or source_type),
        parser_name=str(parser.get("parser_name") or "database_snapshot"),
        parser_version=str(parser.get("parser_version") or "unknown"),
        page_number=block.page_number,
        box=SourceBox(**bbox) if bbox else None,
        table_metadata=dict(block.table_metadata_json or {}),
        ocr_metadata=dict(block.ocr_metadata_json or {}),
        warnings=tuple(ParserWarning(code=str(code), message=str(code)) for code in warning_codes),
    )


def _immutable_source_matches(
    immutable_document: PolicyDocumentVersion,
    canonical_source: CanonicalDocumentContentV2,
    source_checksum: str,
) -> bool:
    return bool(
        immutable_document.source_checksum == source_checksum
        and immutable_document.canonical_content_schema_version == canonical_source.schema_version
        and immutable_document.content == canonical_source.content
        and immutable_document.content_hash == canonical_source.content_hash
        and immutable_document.canonical_blocks_hash == canonical_source.blocks_hash
    )


def _authoritative_snapshot_hash(
    *,
    document: PolicyDocument,
    immutable_document: PolicyDocumentVersion,
    blocks: Sequence[DocumentBlock],
    canonical_source: CanonicalDocumentContentV2,
) -> str:
    payload = {
        "schema_version": "authoritative_policy_document_snapshot.v1",
        "policy_document_id": str(document.id),
        "policy_document_version_id": str(immutable_document.id),
        "doc_key": document.doc_key,
        "document_version": int(document.version),
        "doc_type": document.doc_type,
        "title": document.title,
        "effective_date": document.effective_date.isoformat(),
        "risk_level": document.risk_level,
        "source_type": document.source_type,
        "source_checksum": document.source_checksum,
        "evidence_write_sequence": document.evidence_write_sequence,
        "canonical_content_hash": canonical_source.content_hash,
        "canonical_blocks_hash": canonical_source.blocks_hash,
        "blocks": [
            {
                "id": str(block.id),
                "source_block_id": block.source_block_id,
                "block_index": block.block_index,
                "block_type": block.block_type,
                "text": block.text,
                "normalized_text": block.normalized_text,
                "text_hash": block.text_hash,
                "page_number": block.page_number,
                "bbox": block.bbox_json,
                "table_metadata": block.table_metadata_json,
                "parser_metadata": block.parser_metadata_json,
                "ocr_metadata": block.ocr_metadata_json,
                "source_uri": block.source_uri,
            }
            for block in blocks
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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
