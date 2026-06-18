from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


MAX_PARSED_BLOCK_TEXT_CHARS = 12_000

BlockType = Literal["heading", "paragraph", "table", "image", "list", "footer", "header", "ocr_text"]
ParseStatus = Literal["success", "degraded", "failed"]
SourceBoxUnit = Literal["pdf_point", "pixel", "logical"]
SourceBoxOrigin = Literal["top_left"]


class ParserFailureCode(StrEnum):
    UNSUPPORTED_SOURCE_TYPE = "unsupported_source_type"
    SIGNATURE_MISMATCH = "signature_mismatch"
    FILE_TOO_LARGE = "file_too_large"
    TOO_MANY_PAGES = "too_many_pages"
    IMAGE_TOO_LARGE = "image_too_large"
    PARSER_TIMEOUT = "parser_timeout"
    OCR_TIMEOUT = "ocr_timeout"
    MALFORMED_SOURCE = "malformed_source"
    BUSINESS_ARTIFACT_REJECTED = "business_artifact_rejected"


class ParserWarningCode(StrEnum):
    HIDDEN_TEXT_IGNORED = "hidden_text_ignored"
    CONTROL_CHARACTERS_REMOVED = "control_characters_removed"
    LOCAL_PATH_REDACTED = "local_path_redacted"
    RAW_PARSER_PAYLOAD_IGNORED = "raw_parser_payload_ignored"
    TEXT_TRUNCATED = "text_truncated"
    EMPTY_BLOCK_SKIPPED = "empty_block_skipped"
    PARSER_EXCEPTION_SANITIZED = "parser_exception_sanitized"


@dataclass(frozen=True)
class SourceBox:
    page_number: int | None
    x0: float | None
    y0: float | None
    x1: float | None
    y1: float | None
    width: float | None
    height: float | None
    unit: SourceBoxUnit
    origin: SourceBoxOrigin = "top_left"
    rotation: int | None = None


@dataclass(frozen=True)
class ParserWarning:
    code: str
    message: str
    block_index: int | None = None


@dataclass(frozen=True)
class ParsedBlock:
    source_block_id: str
    block_index: int
    block_type: BlockType
    text: str
    normalized_text: str
    source_type: str
    parser_name: str
    parser_version: str
    page_number: int | None
    box: SourceBox | None
    table_metadata: dict[str, Any] = field(default_factory=dict)
    ocr_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[ParserWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_metadata", dict(self.table_metadata))
        object.__setattr__(self, "ocr_metadata", dict(self.ocr_metadata))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class ParseResult:
    status: ParseStatus
    source_type: str
    parser_name: str
    parser_version: str
    blocks: tuple[ParsedBlock, ...]
    warnings: tuple[ParserWarning, ...]
    failure_code: str | None
    safe_message: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocks", tuple(self.blocks))
        object.__setattr__(self, "warnings", tuple(self.warnings))


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_LOCAL_PATH_RE = re.compile(
    r"(?:(?:file://)?/(?:Users|home|private|tmp|var|Volumes)/[^\s)>\]]+|[A-Za-z]:\\[^\s)>\]]+)"
)
_RAW_PAYLOAD_MARKERS = (
    "raw_bytes",
    "parser_dump",
    "debug_ocr_payload",
    "Traceback (most recent call last)",
    "%PDF-",
)


def safe_failed_result(
    *,
    source_type: str,
    parser_name: str,
    parser_version: str,
    failure_code: ParserFailureCode | str,
    safe_message: str,
    warnings: tuple[ParserWarning, ...] = (),
) -> ParseResult:
    return ParseResult(
        status="failed",
        source_type=source_type,
        parser_name=parser_name,
        parser_version=parser_version,
        blocks=(),
        warnings=warnings,
        failure_code=str(failure_code),
        safe_message=safe_message,
    )


def synthetic_source_block_id(*, doc_key: str, source_type: str, block_index: int) -> str:
    return f"{doc_key}:{source_type}:synthetic:{block_index:04d}"


def strip_hidden_markdown_comments(text: str) -> tuple[str, tuple[ParserWarning, ...]]:
    if not _HTML_COMMENT_RE.search(text):
        return text, ()
    cleaned = _HTML_COMMENT_RE.sub("", text)
    return (
        cleaned,
        (
            ParserWarning(
                code=ParserWarningCode.HIDDEN_TEXT_IGNORED.value,
                message="Hidden Markdown/HTML comments were ignored.",
            ),
        ),
    )


def sanitize_visible_text(text: str, *, block_index: int | None = None) -> tuple[str, tuple[ParserWarning, ...]]:
    warnings: list[ParserWarning] = []
    cleaned = unicodedata.normalize("NFC", text)

    without_control = "".join(
        char for char in cleaned if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )
    if without_control != cleaned:
        warnings.append(
            ParserWarning(
                code=ParserWarningCode.CONTROL_CHARACTERS_REMOVED.value,
                message="Control characters were removed from parser text.",
                block_index=block_index,
            )
        )
    cleaned = without_control

    without_paths = _LOCAL_PATH_RE.sub("[redacted_path]", cleaned)
    if without_paths != cleaned:
        warnings.append(
            ParserWarning(
                code=ParserWarningCode.LOCAL_PATH_REDACTED.value,
                message="Local filesystem paths were redacted from parser text.",
                block_index=block_index,
            )
        )
    cleaned = without_paths

    retained_lines: list[str] = []
    raw_payload_removed = False
    for line in cleaned.splitlines():
        if any(marker in line for marker in _RAW_PAYLOAD_MARKERS):
            raw_payload_removed = True
            continue
        retained_lines.append(line)
    if raw_payload_removed:
        warnings.append(
            ParserWarning(
                code=ParserWarningCode.RAW_PARSER_PAYLOAD_IGNORED.value,
                message="Raw parser/debug payload text was ignored.",
                block_index=block_index,
            )
        )
    cleaned = "\n".join(retained_lines).strip()

    if len(cleaned) > MAX_PARSED_BLOCK_TEXT_CHARS:
        cleaned = cleaned[:MAX_PARSED_BLOCK_TEXT_CHARS].rstrip()
        warnings.append(
            ParserWarning(
                code=ParserWarningCode.TEXT_TRUNCATED.value,
                message="Parser block text exceeded the maximum block size and was truncated.",
                block_index=block_index,
            )
        )

    return cleaned, tuple(warnings)


def normalize_block_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
