from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.knowledge.text_hash import evidence_text_hash
from src.rag.parsers.base import ParsedBlock, validate_doc_key


@dataclass(frozen=True)
class ChunkResult:
    doc_key: str
    chunk_id: str
    section: str
    content: str
    chunk_index: int
    part_index: int | None = None


@dataclass(frozen=True)
class BlockChunkResult:
    doc_key: str
    chunk_id: str
    section: str
    content: str
    chunk_index: int
    part_index: int | None = None
    source_block_refs: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


_HEADING_PATTERN = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.MULTILINE)
_SENTENCE_BOUNDARIES = "。！？\n"
_FALLBACK_BOUNDARIES = " ，,"


def chunk_markdown(
    content: str,
    doc_key: str,
    max_chars: int = 1200,
    target_chars: int = 800,
    overlap_chars: int = 100,
) -> list[ChunkResult]:
    """Split Markdown policy text into stable heading-based chunks."""
    doc_key = validate_doc_key(doc_key)
    if max_chars <= 0 or target_chars <= 0:
        raise ValueError("max_chars and target_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must not be negative")
    if overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be smaller than target_chars")

    chunks: list[ChunkResult] = []
    chunk_index = 0

    for section, body in _iter_sections(content):
        if not body:
            continue

        if len(body) <= max_chars:
            chunks.append(
                ChunkResult(
                    doc_key=doc_key,
                    chunk_id=f"{doc_key}_{chunk_index:03d}",
                    section=section,
                    content=body,
                    chunk_index=chunk_index,
                )
            )
        else:
            for part_index, part in enumerate(_split_oversized(body, max_chars, target_chars, overlap_chars), start=1):
                chunks.append(
                    ChunkResult(
                        doc_key=doc_key,
                        chunk_id=f"{doc_key}_{chunk_index:03d}_part_{part_index}",
                        section=section,
                        content=part,
                        chunk_index=chunk_index,
                        part_index=part_index,
                    )
                )
        chunk_index += 1

    return chunks


def chunk_blocks(
    blocks: list[ParsedBlock] | tuple[ParsedBlock, ...],
    doc_key: str,
    max_chars: int = 1200,
    target_chars: int = 800,
    overlap_chars: int = 100,
) -> list[BlockChunkResult]:
    """Split parser blocks into stable chunks while preserving provenance refs."""
    doc_key = validate_doc_key(doc_key)
    if max_chars <= 0 or target_chars <= 0:
        raise ValueError("max_chars and target_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must not be negative")
    if overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be smaller than target_chars")

    ordered_blocks = tuple(blocks)
    chunks: list[BlockChunkResult] = []
    pending_texts: list[str] = []
    pending_refs: list[dict[str, Any]] = []
    section = "intro"
    chunk_index = 0

    def flush_pending() -> None:
        nonlocal chunk_index
        content = "\n".join(text for text in pending_texts if text).strip()
        if content:
            chunks.append(
                _make_block_chunk(
                    doc_key=doc_key,
                    chunk_index=chunk_index,
                    section=section,
                    content=content,
                    source_refs=tuple(pending_refs),
                    metadata=_chunk_metadata(tuple(pending_refs)),
                )
            )
            chunk_index += 1
        pending_texts.clear()
        pending_refs.clear()

    for block in ordered_blocks:
        visible_text = block.text.strip()
        if not visible_text:
            continue

        if block.block_type == "heading":
            if pending_texts and len("\n".join([*pending_texts, visible_text])) > max_chars:
                flush_pending()
            section = visible_text
            pending_texts.append(visible_text)
            pending_refs.append(_source_block_ref(block))
            continue

        if block.block_type == "table":
            flush_pending()
            table_chunks = _chunk_table_block(
                block=block,
                doc_key=doc_key,
                chunk_index=chunk_index,
                section=section if section != "intro" else "table",
                max_chars=max_chars,
                target_chars=target_chars,
            )
            chunks.extend(table_chunks)
            chunk_index += 1
            continue

        candidate = "\n".join([*pending_texts, visible_text]).strip()
        block_ref = _source_block_ref(block)
        if pending_texts and len(candidate) > max_chars:
            flush_pending()

        if len(visible_text) <= max_chars:
            pending_texts.append(visible_text)
            pending_refs.append(block_ref)
            continue

        for part_index, part in enumerate(
            _split_oversized(visible_text, max_chars, target_chars, overlap_chars), start=1
        ):
            chunks.append(
                _make_block_chunk(
                    doc_key=doc_key,
                    chunk_index=chunk_index,
                    section=section,
                    content=part,
                    source_refs=(block_ref,),
                    metadata=_chunk_metadata((block_ref,)),
                    part_index=part_index,
                )
            )
        chunk_index += 1

    flush_pending()
    return chunks


def _iter_sections(content: str) -> list[tuple[str, str]]:
    matches = list(_HEADING_PATTERN.finditer(content))
    sections: list[tuple[str, str]] = []

    if not matches:
        body = content.strip()
        return [("intro", body)] if body else []

    intro = content[: matches[0].start()].strip()
    if intro:
        sections.append(("intro", intro))

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if body:
            sections.append((match.group(1).strip(), body))

    return sections


def _make_block_chunk(
    *,
    doc_key: str,
    chunk_index: int,
    section: str,
    content: str,
    source_refs: tuple[dict[str, Any], ...],
    metadata: dict[str, Any],
    part_index: int | None = None,
) -> BlockChunkResult:
    chunk_id = f"{doc_key}_{chunk_index:03d}"
    if part_index is not None:
        chunk_id = f"{chunk_id}_part_{part_index}"
    return BlockChunkResult(
        doc_key=doc_key,
        chunk_id=chunk_id,
        section=section,
        content=content,
        chunk_index=chunk_index,
        part_index=part_index,
        source_block_refs=source_refs,
        metadata=metadata,
    )


def _source_block_ref(block: ParsedBlock) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "source_block_id": block.source_block_id,
        "block_index": block.block_index,
        "block_type": block.block_type,
        "text_hash": evidence_text_hash(block.text),
    }
    if block.page_number is not None:
        ref["page_number"] = block.page_number
    if block.box is not None:
        ref["bbox"] = asdict(block.box)
    if block.table_metadata:
        ref["table"] = _table_ref_metadata(block.table_metadata)
    if block.ocr_metadata:
        ref["ocr"] = dict(block.ocr_metadata)
    return ref


def _table_ref_metadata(table_metadata: dict[str, Any]) -> dict[str, Any]:
    table = dict(table_metadata)
    merged_cells: list[Any] = list(table.get("merged_cells", [])) if isinstance(table.get("merged_cells"), list) else []
    rows = table.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("merged_cells"), list):
                merged_cells.extend(row["merged_cells"])
    if merged_cells:
        table["merged_cells"] = merged_cells
    return table


def _chunk_metadata(source_refs: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source_block_ids": [ref["source_block_id"] for ref in source_refs],
        "block_types": [ref["block_type"] for ref in source_refs],
    }
    table_refs = [ref["table"] for ref in source_refs if "table" in ref]
    ocr_refs = [ref["ocr"] for ref in source_refs if "ocr" in ref]
    if table_refs:
        metadata["table"] = _merge_table_metadata(table_refs)
    if ocr_refs:
        metadata["ocr"] = {"blocks": ocr_refs}
    return metadata


def _merge_table_metadata(table_refs: list[dict[str, Any]]) -> dict[str, Any]:
    headers: list[Any] = []
    merged_cells: list[Any] = []
    repeated_headers = False
    row_count = 0
    for table in table_refs:
        if not headers and isinstance(table.get("headers"), list):
            headers = list(table["headers"])
        repeated_headers = repeated_headers or bool(table.get("repeated_headers"))
        rows = table.get("rows")
        if isinstance(rows, list):
            row_count += len(rows)
            for row in rows:
                if isinstance(row, dict) and isinstance(row.get("merged_cells"), list):
                    merged_cells.extend(row["merged_cells"])
        if isinstance(table.get("merged_cells"), list):
            merged_cells.extend(table["merged_cells"])
    merged: dict[str, Any] = {
        "headers": headers,
        "repeated_headers": repeated_headers,
        "row_count": row_count,
    }
    if merged_cells:
        merged["merged_cells"] = merged_cells
    return merged


def _chunk_table_block(
    *,
    block: ParsedBlock,
    doc_key: str,
    chunk_index: int,
    section: str,
    max_chars: int,
    target_chars: int,
) -> list[BlockChunkResult]:
    table_ref = _source_block_ref(block)
    table = block.table_metadata
    headers = [str(header).strip() for header in table.get("headers", []) if str(header).strip()]
    rows = table.get("rows")
    if not headers or not isinstance(rows, list) or not rows:
        return [
            _make_block_chunk(
                doc_key=doc_key,
                chunk_index=chunk_index,
                section=section,
                content=block.text.strip(),
                source_refs=(table_ref,),
                metadata=_chunk_metadata((table_ref,)),
            )
        ]

    header_line = " | ".join(headers)
    row_lines = [_format_table_row(headers, row) for row in rows]
    emitted: list[BlockChunkResult] = []
    current_rows: list[str] = []
    part_index = 1

    def emit_rows(rows_to_emit: list[str]) -> None:
        nonlocal part_index
        content = "\n".join([header_line, *rows_to_emit]).strip()
        emitted.append(
            _make_block_chunk(
                doc_key=doc_key,
                chunk_index=chunk_index,
                section=section,
                content=content,
                source_refs=(table_ref,),
                metadata=_chunk_metadata((table_ref,)),
                part_index=part_index,
            )
        )
        part_index += 1

    for row_line in row_lines:
        candidate = "\n".join([header_line, *current_rows, row_line])
        if current_rows and (len(candidate) > max_chars or len(candidate) > target_chars):
            emit_rows(current_rows)
            current_rows = []
        current_rows.append(row_line)

    if current_rows:
        emit_rows(current_rows)

    if len(emitted) == 1:
        only = emitted[0]
        return [
            _make_block_chunk(
                doc_key=doc_key,
                chunk_index=chunk_index,
                section=section,
                content=only.content,
                source_refs=only.source_block_refs,
                metadata=only.metadata or {},
            )
        ]
    return emitted


def _format_table_row(headers: list[str], row: Any) -> str:
    if isinstance(row, dict):
        cells = row.get("cells", [])
    else:
        cells = row
    if not isinstance(cells, list):
        return str(row).strip()

    parts: list[str] = []
    for index, cell in enumerate(cells):
        value = str(cell).strip()
        if not value:
            continue
        if index < len(headers):
            parts.append(f"{headers[index]}={value}")
        else:
            parts.append(value)
    return " | ".join(parts)


def _split_oversized(text: str, max_chars: int, target_chars: int, overlap_chars: int) -> list[str]:
    parts: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        remaining = text_len - start
        if remaining <= max_chars:
            part = text[start:].strip()
            if part:
                parts.append(part)
            break

        preferred_end = min(start + target_chars, text_len)
        end = _find_split_position(text, start, preferred_end)
        if end <= start:
            end = min(start + max_chars, text_len)

        part = text[start:end].strip()
        if part:
            parts.append(part)

        next_start = max(end - overlap_chars, start + 1)
        start = _trim_leading_boundary(text, next_start)

    return parts


def _find_split_position(text: str, start: int, preferred_end: int) -> int:
    lower_bound = start + max(1, preferred_end - start - 200)

    for index in range(preferred_end - 1, lower_bound - 1, -1):
        if text[index] in _SENTENCE_BOUNDARIES:
            return index + 1

    for index in range(preferred_end - 1, start, -1):
        if text[index] in _FALLBACK_BOUNDARIES:
            return index + 1

    return preferred_end


def _trim_leading_boundary(text: str, start: int) -> int:
    while start < len(text) and text[start] in " \n\t，,。！？":
        start += 1
    return start
