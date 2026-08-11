from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, NoReturn

from src.rag.chunker import chunk_metadata, format_table_row, source_block_ref
from src.rag.embedding_tokenizer import EmbeddingTokenCounter, load_embedding_tokenizer_config
from src.rag.parsers.base import ParsedBlock, validate_doc_key
from src.rag.search_text import build_policy_chunk_search_text


_STRUCTURAL_BOUNDARIES = (
    re.compile(r"(?<=\n)"),
    re.compile(r"(?<=[。！？!?；;])"),
    re.compile(r"(?<=[，,：:])"),
    re.compile(r"(?<=\s)"),
)
_VARIATION_SELECTORS = frozenset({"\ufe0e", "\ufe0f"})


class PolicyEmbeddingInputFailureCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    ENVELOPE_TOO_LARGE = "envelope_too_large"
    FINAL_INPUT_OVERFLOW = "final_input_overflow"
    NO_PROGRESS = "no_progress"


class PolicyEmbeddingInputError(RuntimeError):
    """Safe assembly failure containing only an allowlisted reason code."""

    def __init__(self, code: PolicyEmbeddingInputFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class PolicyEmbeddingInputV1:
    doc_key: str
    chunk_id: str
    section: str
    citation_content: str
    primary_content: str
    overlap_content: str
    search_text: str
    embedding_input: str
    embedding_input_hash: str
    embedding_token_count: int
    overlap_token_count: int
    chunking_config_fingerprint: str
    source_block_refs: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any]
    chunk_index: int
    part_index: int | None = None


@dataclass(frozen=True, slots=True)
class _AssemblyUnit:
    section: str
    content: str
    source_block_refs: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]
    joiner: str = "\n"
    force_boundary: bool = False


@dataclass(frozen=True, slots=True)
class _BaseChunk:
    section: str
    primary_content: str
    source_block_refs: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]


class PolicyEmbeddingInputAssembler:
    """Sole authority for bounded policy citation/search/provider input assembly."""

    def __init__(self, *, counter: EmbeddingTokenCounter | None = None) -> None:
        self.counter = counter or EmbeddingTokenCounter(load_embedding_tokenizer_config())
        self.config = self.counter.config

    def assemble(
        self,
        *,
        blocks: Sequence[ParsedBlock],
        doc_key: str,
        title: str,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[PolicyEmbeddingInputV1, ...]:
        safe_doc_key = validate_doc_key(doc_key)
        if not isinstance(title, str) or not isinstance(blocks, Sequence):
            _fail(PolicyEmbeddingInputFailureCode.INVALID_INPUT)

        ordered_blocks = tuple(blocks)
        if any(not isinstance(block, ParsedBlock) for block in ordered_blocks):
            _fail(PolicyEmbeddingInputFailureCode.INVALID_INPUT)

        units = self._build_units(blocks=ordered_blocks, title=title)
        if not units:
            return ()

        base_chunks = self._pack_units(units=units, title=title)
        assembled: list[PolicyEmbeddingInputV1] = []
        for chunk_index, base in enumerate(base_chunks):
            previous = base_chunks[chunk_index - 1] if chunk_index else None
            assembled.append(
                self._finalize(
                    base=base,
                    previous=previous,
                    doc_key=safe_doc_key,
                    chunk_index=chunk_index,
                    title=title,
                    doc_type=doc_type,
                    risk_level=risk_level,
                )
            )
        return tuple(assembled)

    def _build_units(self, *, blocks: tuple[ParsedBlock, ...], title: str) -> tuple[_AssemblyUnit, ...]:
        units: list[_AssemblyUnit] = []
        section = "intro"
        for block in blocks:
            visible_text = block.text.strip()
            if not visible_text:
                continue
            if block.block_type == "heading":
                section = visible_text

            ref = source_block_ref(block)
            if block.block_type == "table":
                units.extend(self._table_units(block=block, section=section, ref=ref, title=title))
                continue

            metadata = chunk_metadata((ref,))
            pieces = self._split_to_fit(
                text=visible_text,
                section=section,
                title=title,
                source_refs=(ref,),
                content_prefix="",
            )
            units.extend(
                _AssemblyUnit(
                    section=section,
                    content=piece,
                    source_block_refs=(ref,),
                    metadata=metadata,
                    joiner="\n" if piece_index == 0 else "",
                )
                for piece_index, piece in enumerate(pieces)
                if piece
            )
        return tuple(units)

    def _table_units(
        self,
        *,
        block: ParsedBlock,
        section: str,
        ref: dict[str, Any],
        title: str,
    ) -> tuple[_AssemblyUnit, ...]:
        table = block.table_metadata
        headers = [str(header).strip() for header in table.get("headers", []) if str(header).strip()]
        rows = table.get("rows")
        if not headers or not isinstance(rows, list) or not rows:
            pieces = self._split_to_fit(
                text=block.text.strip(),
                section=section,
                title=title,
                source_refs=(ref,),
                content_prefix="",
            )
            return tuple(
                _AssemblyUnit(
                    section=section,
                    content=piece,
                    source_block_refs=(ref,),
                    metadata=chunk_metadata((ref,)),
                    joiner="\n" if piece_index == 0 else "",
                    force_boundary=True,
                )
                for piece_index, piece in enumerate(pieces)
            )

        header_line = " | ".join(headers)
        row_units: list[tuple[str, int | str, bool]] = []
        for fallback_index, row in enumerate(rows):
            row_index = row.get("row_index", fallback_index) if isinstance(row, dict) else fallback_index
            row_line = format_table_row(headers, row)
            if not row_line:
                continue
            row_pieces = self._split_to_fit(
                text=row_line,
                section=section,
                title=title,
                source_refs=(ref,),
                content_prefix=f"{header_line}\n",
            )
            row_units.extend((piece, row_index, len(row_pieces) > 1) for piece in row_pieces)

        emitted: list[_AssemblyUnit] = []
        pending_rows: list[str] = []
        pending_indices: list[int | str] = []
        pending_oversized = False

        def emit_pending() -> None:
            nonlocal pending_oversized
            if not pending_rows:
                return
            content = "\n".join((header_line, *pending_rows))
            metadata = chunk_metadata((ref,))
            table_metadata = dict(metadata.get("table", {}))
            table_metadata.update(
                {
                    "headers": list(headers),
                    "repeated_headers": True,
                    "row_indices": list(pending_indices),
                    "oversized_row_split": pending_oversized,
                }
            )
            metadata["table"] = table_metadata
            emitted.append(
                _AssemblyUnit(
                    section=section,
                    content=content,
                    source_block_refs=(ref,),
                    metadata=metadata,
                    joiner="\n",
                    force_boundary=True,
                )
            )
            pending_rows.clear()
            pending_indices.clear()
            pending_oversized = False

        for row_piece, row_index, oversized in row_units:
            candidate_rows = (*pending_rows, row_piece)
            candidate_content = "\n".join((header_line, *candidate_rows))
            candidate_count = self._count_final(
                title=title,
                section=section,
                content=candidate_content,
                source_refs=(ref,),
            )
            if pending_rows and candidate_count > self.config.target_embedding_tokens:
                emit_pending()
            pending_rows.append(row_piece)
            pending_indices.append(row_index)
            pending_oversized = pending_oversized or oversized
            if oversized:
                emit_pending()
        emit_pending()
        return tuple(emitted)

    def _split_to_fit(
        self,
        *,
        text: str,
        section: str,
        title: str,
        source_refs: tuple[dict[str, Any], ...],
        content_prefix: str,
    ) -> tuple[str, ...]:
        self._require_envelope_capacity(
            title=title,
            section=section,
            source_refs=source_refs,
            content_prefix=content_prefix,
        )
        if self._content_fits(
            title=title,
            section=section,
            content=f"{content_prefix}{text}",
            source_refs=source_refs,
        ):
            return (text,)

        pieces = [text]
        for boundary in _STRUCTURAL_BOUNDARIES:
            next_pieces: list[str] = []
            for piece in pieces:
                if self._content_fits(
                    title=title,
                    section=section,
                    content=f"{content_prefix}{piece}",
                    source_refs=source_refs,
                ):
                    next_pieces.append(piece)
                    continue
                structural = tuple(part for part in boundary.split(piece) if part)
                next_pieces.extend(structural if len(structural) > 1 else (piece,))
            pieces = next_pieces

        fitted: list[str] = []
        for piece in pieces:
            if self._content_fits(
                title=title,
                section=section,
                content=f"{content_prefix}{piece}",
                source_refs=source_refs,
            ):
                fitted.append(piece)
                continue
            fitted.extend(
                self._token_windows(
                    text=piece,
                    section=section,
                    title=title,
                    source_refs=source_refs,
                    content_prefix=content_prefix,
                )
            )

        if not fitted or "".join(fitted) != text or any(not piece for piece in fitted):
            _fail(PolicyEmbeddingInputFailureCode.NO_PROGRESS)
        return tuple(fitted)

    def _token_windows(
        self,
        *,
        text: str,
        section: str,
        title: str,
        source_refs: tuple[dict[str, Any], ...],
        content_prefix: str,
    ) -> tuple[str, ...]:
        windows: list[str] = []
        remaining = text
        while remaining:
            if self._content_fits(
                title=title,
                section=section,
                content=f"{content_prefix}{remaining}",
                source_refs=source_refs,
            ):
                windows.append(remaining)
                break

            end = self._largest_fitting_prefix_end(
                text=remaining,
                section=section,
                title=title,
                source_refs=source_refs,
                content_prefix=content_prefix,
            )
            end = _move_before_unsafe_unicode_boundary(remaining, end)
            if end <= 0:
                _fail(PolicyEmbeddingInputFailureCode.ENVELOPE_TOO_LARGE)
            window = remaining[:end]
            if not window or remaining[end:] == remaining:
                _fail(PolicyEmbeddingInputFailureCode.NO_PROGRESS)
            if not self._content_fits(
                title=title,
                section=section,
                content=f"{content_prefix}{window}",
                source_refs=source_refs,
            ):
                _fail(PolicyEmbeddingInputFailureCode.FINAL_INPUT_OVERFLOW)
            windows.append(window)
            remaining = remaining[end:]

        if "".join(windows) != text:
            _fail(PolicyEmbeddingInputFailureCode.NO_PROGRESS)
        return tuple(windows)

    def _largest_fitting_prefix_end(
        self,
        *,
        text: str,
        section: str,
        title: str,
        source_refs: tuple[dict[str, Any], ...],
        content_prefix: str,
    ) -> int:
        lower = 1
        upper = len(text)
        best = 0
        while lower <= upper:
            middle = (lower + upper) // 2
            candidate = f"{content_prefix}{text[:middle]}"
            if self._content_fits(
                title=title,
                section=section,
                content=candidate,
                source_refs=source_refs,
            ):
                best = middle
                lower = middle + 1
            else:
                upper = middle - 1
        return best

    def _pack_units(self, *, units: tuple[_AssemblyUnit, ...], title: str) -> tuple[_BaseChunk, ...]:
        emitted: list[_BaseChunk] = []
        pending: list[_AssemblyUnit] = []

        def emit_pending() -> None:
            if not pending:
                return
            emitted.append(self._base_from_units(tuple(pending)))
            pending.clear()

        for unit in units:
            if unit.force_boundary:
                emit_pending()
                base = self._base_from_units((unit,))
                self._require_base_fits(base=base, title=title)
                emitted.append(base)
                continue

            if pending and pending[-1].section != unit.section:
                emit_pending()
            candidate_units = (*pending, unit)
            candidate = self._base_from_units(candidate_units)
            candidate_count = self._count_final(
                title=title,
                section=candidate.section,
                content=candidate.primary_content,
                source_refs=candidate.source_block_refs,
            )
            if pending and candidate_count > self.config.target_embedding_tokens:
                emit_pending()
            pending.append(unit)
            self._require_base_fits(base=self._base_from_units(tuple(pending)), title=title)
        emit_pending()
        return tuple(emitted)

    def _base_from_units(self, units: tuple[_AssemblyUnit, ...]) -> _BaseChunk:
        if not units:
            _fail(PolicyEmbeddingInputFailureCode.NO_PROGRESS)
        return _BaseChunk(
            section=units[0].section,
            primary_content=units[0].content + "".join(f"{unit.joiner}{unit.content}" for unit in units[1:]),
            source_block_refs=_dedupe_refs(ref for unit in units for ref in unit.source_block_refs),
            metadata=_merge_metadata(units),
        )

    def _require_base_fits(self, *, base: _BaseChunk, title: str) -> None:
        if not base.primary_content:
            _fail(PolicyEmbeddingInputFailureCode.NO_PROGRESS)
        if not self._content_fits(
            title=title,
            section=base.section,
            content=base.primary_content,
            source_refs=base.source_block_refs,
        ):
            _fail(PolicyEmbeddingInputFailureCode.FINAL_INPUT_OVERFLOW)

    def _finalize(
        self,
        *,
        base: _BaseChunk,
        previous: _BaseChunk | None,
        doc_key: str,
        chunk_index: int,
        title: str,
        doc_type: str | None,
        risk_level: str | None,
    ) -> PolicyEmbeddingInputV1:
        overlap = ""
        final_refs = base.source_block_refs
        if previous is not None and previous.section == base.section:
            overlap = self._largest_fitting_overlap(
                previous=previous,
                current=base,
                title=title,
            )
            if overlap:
                final_refs = _dedupe_refs((*previous.source_block_refs, *base.source_block_refs))

        citation_content = f"{overlap}\n{base.primary_content}" if overlap else base.primary_content
        embedding_input = self._render_embedding_input(
            title=title,
            section=base.section,
            content=citation_content,
            source_refs=final_refs,
        )
        token_count = self.counter.count(embedding_input)
        if token_count > self.config.max_embedding_tokens:
            _fail(PolicyEmbeddingInputFailureCode.FINAL_INPUT_OVERFLOW)
        if self.counter.count(embedding_input) != token_count:
            _fail(PolicyEmbeddingInputFailureCode.FINAL_INPUT_OVERFLOW)

        table = base.metadata.get("table", {})
        headers = table.get("headers", ()) if isinstance(table, dict) else ()
        source_context = tuple(_search_source_context(final_refs))
        search_text = build_policy_chunk_search_text(
            title=title,
            section=base.section,
            content=citation_content,
            doc_type=doc_type,
            risk_level=risk_level,
            heading_path=(base.section,) if base.section != "intro" else (),
            table_headers=tuple(str(header) for header in headers),
            source_context=source_context,
        )
        frozen_refs = tuple(_freeze_mapping(ref) for ref in final_refs)
        frozen_metadata = _freeze_mapping(base.metadata)
        return PolicyEmbeddingInputV1(
            doc_key=doc_key,
            chunk_id=f"{doc_key}_{chunk_index:03d}",
            section=base.section,
            citation_content=citation_content,
            primary_content=base.primary_content,
            overlap_content=overlap,
            search_text=search_text,
            embedding_input=embedding_input,
            embedding_input_hash="sha256:" + hashlib.sha256(embedding_input.encode("utf-8")).hexdigest(),
            embedding_token_count=token_count,
            overlap_token_count=self.counter.count(overlap) if overlap else 0,
            chunking_config_fingerprint=self.config.config_fingerprint,
            source_block_refs=frozen_refs,
            metadata=frozen_metadata,
            chunk_index=chunk_index,
        )

    def _largest_fitting_overlap(
        self,
        *,
        previous: _BaseChunk,
        current: _BaseChunk,
        title: str,
    ) -> str:
        source = previous.primary_content
        lower = 0
        upper = len(source) - 1
        best = ""
        combined_refs = _dedupe_refs((*previous.source_block_refs, *current.source_block_refs))
        while lower <= upper:
            middle = (lower + upper) // 2
            start = _move_after_unsafe_unicode_boundary(source, middle)
            candidate = source[start:]
            if not candidate:
                upper = middle - 1
                continue
            overlap_count = self.counter.count(candidate)
            citation = f"{candidate}\n{current.primary_content}"
            final_count = self._count_final(
                title=title,
                section=current.section,
                content=citation,
                source_refs=combined_refs,
            )
            if overlap_count <= self.config.overlap_tokens and final_count <= self.config.max_embedding_tokens:
                best = candidate
                upper = middle - 1
            else:
                lower = middle + 1
        return best

    def _require_envelope_capacity(
        self,
        *,
        title: str,
        section: str,
        source_refs: tuple[dict[str, Any], ...],
        content_prefix: str,
    ) -> None:
        envelope_count = self._count_final(
            title=title,
            section=section,
            content=content_prefix,
            source_refs=source_refs,
        )
        if envelope_count >= self.config.max_embedding_tokens:
            _fail(PolicyEmbeddingInputFailureCode.ENVELOPE_TOO_LARGE)

    def _content_fits(
        self,
        *,
        title: str,
        section: str,
        content: str,
        source_refs: tuple[dict[str, Any], ...],
    ) -> bool:
        return (
            self._count_final(
                title=title,
                section=section,
                content=content,
                source_refs=source_refs,
            )
            <= self.config.max_embedding_tokens
        )

    def _count_final(
        self,
        *,
        title: str,
        section: str,
        content: str,
        source_refs: tuple[dict[str, Any], ...],
    ) -> int:
        return self.counter.count(
            self._render_embedding_input(
                title=title,
                section=section,
                content=content,
                source_refs=source_refs,
            )
        )

    @staticmethod
    def _render_embedding_input(
        *,
        title: str,
        section: str,
        content: str,
        source_refs: tuple[dict[str, Any], ...],
    ) -> str:
        prefix = f"{title}: {content}" if section == "intro" else f"{title} / {section}: {content}"
        source_ids = sorted({str(ref["source_block_id"]) for ref in source_refs if ref.get("source_block_id")})
        source_lines = "\n".join(f"source_block_id={source_id}" for source_id in source_ids)
        return f"{prefix}\n{source_lines}" if source_lines else prefix


def _dedupe_refs(refs: Sequence[dict[str, Any]] | Any) -> tuple[dict[str, Any], ...]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        source_id = str(ref.get("source_block_id", ""))
        if source_id and source_id not in seen:
            seen.add(source_id)
            deduped.append(ref)
    return tuple(deduped)


def _merge_metadata(units: tuple[_AssemblyUnit, ...]) -> dict[str, Any]:
    source_refs = _dedupe_refs(ref for unit in units for ref in unit.source_block_refs)
    metadata = chunk_metadata(source_refs)
    table_units = [unit.metadata.get("table") for unit in units if isinstance(unit.metadata.get("table"), dict)]
    if table_units:
        row_indices: list[Any] = []
        oversized = False
        for table in table_units:
            row_indices.extend(table.get("row_indices", []))
            oversized = oversized or bool(table.get("oversized_row_split"))
        table_metadata = dict(metadata.get("table", {}))
        table_metadata.update(
            {
                "row_indices": row_indices,
                "oversized_row_split": oversized,
                "repeated_headers": True,
            }
        )
        metadata["table"] = table_metadata
    return metadata


def _search_source_context(refs: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    parts: list[str] = []
    for ref in refs:
        source_block_id = ref.get("source_block_id")
        if source_block_id:
            parts.append(f"source_block_id={source_block_id}")
        page_number = ref.get("page_number")
        if page_number is not None:
            parts.append(f"page={page_number}")
    return tuple(parts)


def _move_before_unsafe_unicode_boundary(text: str, end: int) -> int:
    while 0 < end < len(text) and _unsafe_boundary(text, end):
        end -= 1
    return end


def _move_after_unsafe_unicode_boundary(text: str, start: int) -> int:
    while 0 < start < len(text) and _unsafe_boundary(text, start):
        start += 1
    return start


def _unsafe_boundary(text: str, index: int) -> bool:
    next_char = text[index]
    previous_char = text[index - 1]
    return (
        bool(unicodedata.combining(next_char))
        or next_char in _VARIATION_SELECTORS
        or next_char == "\u200d"
        or previous_char == "\u200d"
    )


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _fail(code: PolicyEmbeddingInputFailureCode) -> NoReturn:
    raise PolicyEmbeddingInputError(code) from None
