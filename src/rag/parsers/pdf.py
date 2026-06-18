from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pdfplumber
import pypdfium2
from PIL.Image import Image as PillowImage

from src.rag.parsers.base import (
    ParsedBlock,
    ParseResult,
    ParserFailureCode,
    ParserWarning,
    SourceBox,
    normalize_block_text,
    safe_failed_result,
    sanitize_visible_text,
    strip_hidden_markdown_comments,
)
from src.rag.parsers.ocr import OcrEngine
from src.rag.parsers.safety import validate_source_file


PARSER_NAME = "moca_pdf"
PARSER_VERSION = "21.03"
SCANNED_PAGE_TEXT_DENSITY_MIN = 8

_SOURCE_FAILURE_TO_PARSE_FAILURE = {
    "UNSUPPORTED_SOURCE_TYPE": ParserFailureCode.UNSUPPORTED_SOURCE_TYPE.value,
    "SOURCE_SIGNATURE_MISMATCH": ParserFailureCode.SIGNATURE_MISMATCH.value,
    "SOURCE_FILE_TOO_LARGE": ParserFailureCode.FILE_TOO_LARGE.value,
    "SOURCE_PAGE_LIMIT_EXCEEDED": ParserFailureCode.TOO_MANY_PAGES.value,
    "BUSINESS_ARTIFACT_REJECTED": ParserFailureCode.BUSINESS_ARTIFACT_REJECTED.value,
    "SOURCE_MALFORMED": ParserFailureCode.MALFORMED_SOURCE.value,
    "SOURCE_DECOMPRESSION_HAZARD": "decompression_hazard",
}


class PdfParser:
    source_type = "policy_pdf"
    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".pdf"})

    def __init__(self, *, ocr_engine: OcrEngine | None = None) -> None:
        self.ocr_engine = ocr_engine or OcrEngine()

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict[str, Any]) -> ParseResult:
        declared_mime = metadata.get("declared_mime") or metadata.get("declared_content_type")
        validation = validate_source_file(
            path,
            source_type=source_type,
            declared_mime=str(declared_mime) if declared_mime else None,
        )
        if not validation.allowed:
            return _validation_failure(source_type=source_type, validation=validation)

        blocks: list[ParsedBlock] = []
        warnings: list[ParserWarning] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    page_blocks, page_warnings = self._parse_page(
                        path=path,
                        page=page,
                        page_index=page_index,
                        doc_key=doc_key,
                        source_type=source_type,
                        block_index_start=len(blocks),
                    )
                    blocks.extend(page_blocks)
                    warnings.extend(page_warnings)
        except Exception:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy PDF source could not be parsed safely.",
            )

        if not blocks:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy PDF source did not contain visible text.",
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

    def _parse_page(
        self,
        *,
        path: Path,
        page: Any,
        page_index: int,
        doc_key: str,
        source_type: str,
        block_index_start: int,
    ) -> tuple[list[ParsedBlock], list[ParserWarning]]:
        page_number = int(getattr(page, "page_number", page_index + 1))
        rotation = _page_rotation(page)
        blocks: list[ParsedBlock] = []
        warnings: list[ParserWarning] = []
        tables = _page_tables(page)
        raw_text = page.extract_text() or ""
        unhidden_text, hidden_warnings = strip_hidden_markdown_comments(raw_text)
        sanitized_text, text_warnings = sanitize_visible_text(unhidden_text, block_index=block_index_start)
        warnings.extend(hidden_warnings)
        warnings.extend(text_warnings)

        if sanitized_text:
            blocks.append(
                ParsedBlock(
                    source_block_id=_pdf_source_block_id(
                        doc_key=doc_key,
                        source_type=source_type,
                        block_kind="text",
                        block_index=block_index_start,
                    ),
                    block_index=block_index_start,
                    block_type="paragraph",
                    text=sanitized_text,
                    normalized_text=normalize_block_text(sanitized_text),
                    source_type=source_type,
                    parser_name=self.parser_name,
                    parser_version=self.parser_version,
                    page_number=page_number,
                    box=_text_source_box(page, page_number=page_number, rotation=rotation),
                    table_metadata={},
                    ocr_metadata={},
                    warnings=(*hidden_warnings, *text_warnings),
                )
            )

        next_index = block_index_start + len(blocks)
        for table in tables:
            table_block, table_warnings = _table_block(
                table,
                doc_key=doc_key,
                source_type=source_type,
                page=page,
                page_number=page_number,
                rotation=rotation,
                block_index=next_index,
            )
            if table_block is not None:
                blocks.append(table_block)
                next_index += 1
            warnings.extend(table_warnings)

        if not blocks and _is_scanned_page(sanitized_text=sanitized_text, tables=tables):
            image = self._render_page_to_image(path, page_index, page)
            ocr_result = self.ocr_engine.parse_image(
                image,
                doc_key=doc_key,
                source_type=source_type,
                block_index=block_index_start,
                page_number=page_number,
                rotation=rotation,
            )
            if ocr_result.status == "failed":
                return [], list(ocr_result.warnings)
            converted = [
                _convert_ocr_block_to_pdf_page(block, page=page, image=image, rotation=rotation)
                for block in ocr_result.blocks
            ]
            return converted, list(ocr_result.warnings)

        return blocks, warnings

    def _render_page_to_image(self, path: Path, page_index: int, page: Any) -> PillowImage:
        pdf = pypdfium2.PdfDocument(str(path))
        try:
            pdf_page = pdf[page_index]
            try:
                bitmap = pdf_page.render(scale=2)
                return bitmap.to_pil().convert("RGB")
            finally:
                close_page = getattr(pdf_page, "close", None)
                if callable(close_page):
                    close_page()
        finally:
            close_pdf = getattr(pdf, "close", None)
            if callable(close_pdf):
                close_pdf()


def _validation_failure(*, source_type: str, validation: Any) -> ParseResult:
    return safe_failed_result(
        source_type=source_type,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        failure_code=_SOURCE_FAILURE_TO_PARSE_FAILURE.get(
            validation.failure_code or "",
            ParserFailureCode.MALFORMED_SOURCE.value,
        ),
        safe_message=validation.safe_message or "Policy PDF source failed validation safely.",
    )


def _page_rotation(page: Any) -> int | None:
    rotation = getattr(page, "rotation", None)
    try:
        return int(rotation) if rotation is not None else None
    except (TypeError, ValueError):
        return None


def _page_tables(page: Any) -> list:
    try:
        return page.extract_tables() or []
    except Exception:
        return []


def _text_source_box(page: Any, *, page_number: int, rotation: int | None) -> SourceBox:
    words = _page_words(page)
    width = float(getattr(page, "width", 0) or 0)
    height = float(getattr(page, "height", 0) or 0)
    if not words:
        return SourceBox(
            page_number=page_number,
            x0=0.0,
            y0=0.0,
            x1=width,
            y1=height,
            width=width,
            height=height,
            unit="pdf_point",
            rotation=rotation,
        )
    return SourceBox(
        page_number=page_number,
        x0=min(float(word.get("x0", 0.0)) for word in words),
        y0=min(float(word.get("top", word.get("y0", 0.0))) for word in words),
        x1=max(float(word.get("x1", 0.0)) for word in words),
        y1=max(float(word.get("bottom", word.get("y1", 0.0))) for word in words),
        width=width,
        height=height,
        unit="pdf_point",
        rotation=rotation,
    )


def _page_words(page: Any) -> list[dict[str, Any]]:
    try:
        return list(page.extract_words() or [])
    except Exception:
        return []


def _table_block(
    table: list,
    *,
    doc_key: str,
    source_type: str,
    page: Any,
    page_number: int,
    rotation: int | None,
    block_index: int,
) -> tuple[ParsedBlock | None, tuple[ParserWarning, ...]]:
    normalized_rows = [[_cell_text(cell) for cell in row] for row in table if row]
    if not normalized_rows:
        return None, ()
    headers = normalized_rows[0]
    data_rows = normalized_rows[1:]
    text = "\n".join(" | ".join(row) for row in normalized_rows).strip()
    sanitized, warnings = sanitize_visible_text(text, block_index=block_index)
    if not sanitized:
        return None, warnings
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
            source_block_id=_pdf_source_block_id(
                doc_key=doc_key,
                source_type=source_type,
                block_kind="table",
                block_index=block_index,
            ),
            block_index=block_index,
            block_type="table",
            text=sanitized,
            normalized_text=normalize_block_text(sanitized),
            source_type=source_type,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            page_number=page_number,
            box=_text_source_box(page, page_number=page_number, rotation=rotation),
            table_metadata=metadata,
            ocr_metadata={},
            warnings=warnings,
        ),
        warnings,
    )


def _cell_text(cell: Any) -> str:
    return "" if cell is None else str(cell).strip()


def _is_scanned_page(*, sanitized_text: str, tables: list) -> bool:
    return len(sanitized_text.strip()) < SCANNED_PAGE_TEXT_DENSITY_MIN and not tables


def _convert_ocr_block_to_pdf_page(
    block: ParsedBlock,
    *,
    page: Any,
    image: PillowImage,
    rotation: int | None,
) -> ParsedBlock:
    page_width = float(getattr(page, "width", image.width) or image.width)
    page_height = float(getattr(page, "height", image.height) or image.height)
    page_number = int(getattr(page, "page_number", block.page_number or 1))
    box = block.box
    converted_box = None
    if box is not None:
        scale_x = page_width / float(image.width or 1)
        scale_y = page_height / float(image.height or 1)
        converted_box = SourceBox(
            page_number=page_number,
            x0=None if box.x0 is None else float(box.x0) * scale_x,
            y0=None if box.y0 is None else float(box.y0) * scale_y,
            x1=None if box.x1 is None else float(box.x1) * scale_x,
            y1=None if box.y1 is None else float(box.y1) * scale_y,
            width=page_width,
            height=page_height,
            unit="pdf_point",
            rotation=rotation,
        )
    metadata = dict(block.ocr_metadata)
    metadata.update(
        {
            "scanned_page": True,
            "rendered_image_width": image.width,
            "rendered_image_height": image.height,
        }
    )
    return replace(
        block,
        page_number=page_number,
        box=converted_box,
        ocr_metadata=metadata,
    )


def _pdf_source_block_id(*, doc_key: str, source_type: str, block_kind: str, block_index: int) -> str:
    return f"{doc_key}:{source_type}:{block_kind}:{block_index:04d}"
