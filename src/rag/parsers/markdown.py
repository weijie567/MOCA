from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from src.rag.parsers.base import (
    BlockType,
    ParsedBlock,
    ParseResult,
    ParserFailureCode,
    ParserWarning,
    normalize_block_text,
    safe_failed_result,
    sanitize_visible_text,
    strip_hidden_markdown_comments,
    synthetic_source_block_id,
)


PARSER_NAME = "moca_markdown"
PARSER_VERSION = "21.01"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


class MarkdownParserAdapter:
    source_type = "policy_markdown"
    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".md", ".markdown"})

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict[str, Any]) -> ParseResult:
        try:
            raw_text = path.read_text(encoding=str(metadata.get("encoding", "utf-8")))
        except UnicodeDecodeError:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy Markdown source could not be decoded as text.",
            )
        except OSError:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy Markdown source could not be read.",
            )

        cleaned_text, hidden_warnings = strip_hidden_markdown_comments(raw_text)
        cleaned_text, safety_warnings = sanitize_visible_text(cleaned_text)
        document_warnings = (*hidden_warnings, *safety_warnings)
        blocks = tuple(_iter_markdown_blocks(cleaned_text, doc_key=doc_key, source_type=source_type))
        if not blocks:
            return ParseResult(
                status="failed",
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                blocks=(),
                warnings=(
                    *document_warnings,
                    ParserWarning(code="empty_source", message="No visible Markdown blocks were produced."),
                ),
                failure_code=ParserFailureCode.MALFORMED_SOURCE.value,
                safe_message="Policy Markdown source did not contain visible text.",
            )

        block_warnings = tuple(warning for block in blocks for warning in block.warnings)
        warnings = (*document_warnings, *block_warnings)
        return ParseResult(
            status="degraded" if warnings else "success",
            source_type=source_type,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            blocks=blocks,
            warnings=warnings,
            failure_code=None,
            safe_message=None,
        )


def _iter_markdown_blocks(text: str, *, doc_key: str, source_type: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    buffer: list[str] = []
    buffer_type = "paragraph"

    def flush() -> None:
        nonlocal buffer, buffer_type
        if not buffer:
            return
        raw_block = "\n".join(buffer).strip()
        _append_block(blocks, raw_block, buffer_type, doc_key=doc_key, source_type=source_type)
        buffer = []
        buffer_type = "paragraph"

    for line in text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush()
            _append_block(blocks, heading_match.group(2), "heading", doc_key=doc_key, source_type=source_type)
            continue

        if not line.strip():
            flush()
            continue

        line_type = "list" if _LIST_RE.match(line) else "paragraph"
        if buffer and line_type != buffer_type:
            flush()
        buffer_type = line_type
        buffer.append(line)

    flush()
    return blocks


def _append_block(
    blocks: list[ParsedBlock],
    raw_text: str,
    block_type: str,
    *,
    doc_key: str,
    source_type: str,
) -> None:
    block_index = len(blocks)
    sanitized, warnings = sanitize_visible_text(raw_text, block_index=block_index)
    if not sanitized:
        return

    blocks.append(
        ParsedBlock(
            source_block_id=synthetic_source_block_id(
                doc_key=doc_key,
                source_type=source_type,
                block_index=block_index,
            ),
            block_index=block_index,
            block_type=cast(BlockType, block_type),
            text=sanitized,
            normalized_text=normalize_block_text(sanitized),
            source_type=source_type,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            page_number=None,
            box=None,
            table_metadata={},
            ocr_metadata={},
            warnings=warnings,
        )
    )
