from __future__ import annotations

from pathlib import Path
from typing import Any

# The python-docx package exposes its import module as `docx`.
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.rag.parsers.base import (
    ParsedBlock,
    ParseResult,
    ParserFailureCode,
    ParserWarning,
    normalize_block_text,
    safe_failed_result,
    sanitize_visible_text,
)
from src.rag.parsers.safety import validate_source_file


PARSER_NAME = "moca_docx"
PARSER_VERSION = "21.03"

_SOURCE_FAILURE_TO_PARSE_FAILURE = {
    "UNSUPPORTED_SOURCE_TYPE": ParserFailureCode.UNSUPPORTED_SOURCE_TYPE.value,
    "SOURCE_SIGNATURE_MISMATCH": ParserFailureCode.SIGNATURE_MISMATCH.value,
    "SOURCE_FILE_TOO_LARGE": ParserFailureCode.FILE_TOO_LARGE.value,
    "BUSINESS_ARTIFACT_REJECTED": ParserFailureCode.BUSINESS_ARTIFACT_REJECTED.value,
    "SOURCE_MALFORMED": ParserFailureCode.MALFORMED_SOURCE.value,
    "SOURCE_DECOMPRESSION_HAZARD": "decompression_hazard",
}


class DocxParser:
    source_type = "policy_docx"
    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".docx"})

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict[str, Any]) -> ParseResult:
        declared_mime = metadata.get("declared_mime") or metadata.get("declared_content_type")
        validation = validate_source_file(
            path,
            source_type=source_type,
            declared_mime=str(declared_mime) if declared_mime else None,
        )
        if not validation.allowed:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=_SOURCE_FAILURE_TO_PARSE_FAILURE.get(
                    validation.failure_code or "",
                    ParserFailureCode.MALFORMED_SOURCE.value,
                ),
                safe_message=validation.safe_message or "Policy DOCX source failed validation safely.",
            )

        try:
            document = Document(str(path))
        except Exception:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy DOCX source could not be parsed safely.",
            )

        blocks: list[ParsedBlock] = []
        warnings: list[ParserWarning] = []
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                block, block_warnings = _paragraph_block(
                    item,
                    doc_key=doc_key,
                    source_type=source_type,
                    block_index=len(blocks),
                )
            elif isinstance(item, Table):
                block, block_warnings = _table_block(
                    item,
                    doc_key=doc_key,
                    source_type=source_type,
                    block_index=len(blocks),
                )
            else:
                continue
            warnings.extend(block_warnings)
            if block is not None:
                blocks.append(block)

        if not blocks:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy DOCX source did not contain visible text.",
                warnings=tuple(warnings),
            )

        return ParseResult(
            status="degraded" if warnings else "success",
            source_type=source_type,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            blocks=tuple(blocks),
            warnings=tuple(warnings),
            failure_code=None,
            safe_message=None,
        )


def _paragraph_block(
    paragraph: Paragraph,
    *,
    doc_key: str,
    source_type: str,
    block_index: int,
) -> tuple[ParsedBlock | None, tuple[ParserWarning, ...]]:
    sanitized, warnings = sanitize_visible_text(paragraph.text, block_index=block_index)
    if not sanitized:
        return None, warnings
    block_type = "heading" if _is_heading(paragraph) else "paragraph"
    return (
        ParsedBlock(
            source_block_id=_docx_source_block_id(doc_key=doc_key, source_type=source_type, block_index=block_index),
            block_index=block_index,
            block_type=block_type,
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
        ),
        warnings,
    )


def _table_block(
    table: Table,
    *,
    doc_key: str,
    source_type: str,
    block_index: int,
) -> tuple[ParsedBlock | None, tuple[ParserWarning, ...]]:
    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return None, ()
    text = "\n".join(" | ".join(row) for row in rows).strip()
    sanitized, warnings = sanitize_visible_text(text, block_index=block_index)
    if not sanitized:
        return None, warnings
    headers = rows[0]
    data_rows = rows[1:]
    metadata = {
        "headers": headers,
        "rows": [{"row_index": index, "cells": row} for index, row in enumerate(data_rows, start=1)],
        "cells": [
            {"row_index": row_index, "col_index": col_index, "text": cell}
            for row_index, row in enumerate(data_rows, start=1)
            for col_index, cell in enumerate(row)
        ],
    }
    return (
        ParsedBlock(
            source_block_id=_docx_source_block_id(doc_key=doc_key, source_type=source_type, block_index=block_index),
            block_index=block_index,
            block_type="table",
            text=sanitized,
            normalized_text=normalize_block_text(sanitized),
            source_type=source_type,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            page_number=None,
            box=None,
            table_metadata=metadata,
            ocr_metadata={},
            warnings=warnings,
        ),
        warnings,
    )


def _is_heading(paragraph: Paragraph) -> bool:
    style = getattr(paragraph, "style", None)
    style_name = str(getattr(style, "name", "") or "")
    return style_name == "Title" or style_name.startswith("Heading")


def _docx_source_block_id(*, doc_key: str, source_type: str, block_index: int) -> str:
    return f"{doc_key}:{source_type}:logical:{block_index:04d}"
