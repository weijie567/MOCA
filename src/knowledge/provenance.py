from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UNSAFE_STRING_PATTERNS = (
    re.compile(r"/(?:Users|home|tmp|var|private|Volumes)/"),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"raw[_ -]?(?:payload|parser|bytes|dump)", re.IGNORECASE),
    re.compile(r"parser_dump", re.IGNORECASE),
)
_FORBIDDEN_KEYS = {
    "action_authority_body",
    "approval_authority_body",
    "chain_of_thought",
    "debug_image",
    "file_bytes",
    "local_path",
    "normalized_text",
    "parser_dump",
    "private_reasoning",
    "raw",
    "raw_args",
    "raw_payload",
    "raw_prompt",
    "raw_tool_output",
    "stack_trace",
    "text",
}
_BBOX_KEYS = {"x0", "y0", "x1", "y1", "width", "height", "unit", "page_number"}
_PARSER_KEYS = {"source_type", "parser_name", "parser_version", "warning_codes"}
_OCR_KEYS = {
    "average_confidence",
    "confidence",
    "confidence_avg",
    "confidence_status",
    "engine",
    "engine_version",
    "error",
    "language",
    "low_confidence_word_count",
    "scanned_page",
    "timeout",
}


class SourceLocator(BaseModel):
    """Internal source location for a verified policy evidence ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_block_id: str
    block_index: int
    block_type: str
    page_number: int | None = None
    bbox: dict[str, Any] = Field(default_factory=dict)
    table: dict[str, Any] = Field(default_factory=dict)
    parser: dict[str, Any] = Field(default_factory=dict)
    ocr: dict[str, Any] = Field(default_factory=dict)


class EvidenceProvenance(BaseModel):
    """Internal/debug provenance side-path data for one verified evidence ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    doc_key: str
    chunk_id: str
    source_locators: list[SourceLocator] = Field(default_factory=list)


class EvidenceProvenanceLookupResult(BaseModel):
    """Internal batch lookup result keyed by EvidenceRefV1.evidence_id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: dict[str, EvidenceProvenance] = Field(default_factory=dict)


def source_locator_from_block(block: Any, *, source_ref: Mapping[str, Any] | None = None) -> SourceLocator:
    """Project a DocumentBlock row into a safe internal locator DTO."""

    ref = source_ref or {}
    return SourceLocator(
        source_block_id=str(getattr(block, "source_block_id")),
        block_index=int(getattr(block, "block_index")),
        block_type=str(getattr(block, "block_type")),
        page_number=getattr(block, "page_number", None),
        bbox=_safe_mapping(getattr(block, "bbox_json", None) or ref.get("bbox"), allowed_keys=_BBOX_KEYS),
        table=_safe_mapping(getattr(block, "table_metadata_json", None) or ref.get("table")),
        parser=_safe_mapping(getattr(block, "parser_metadata_json", None), allowed_keys=_PARSER_KEYS),
        ocr=_safe_mapping(getattr(block, "ocr_metadata_json", None) or ref.get("ocr"), allowed_keys=_OCR_KEYS),
    )


def _safe_mapping(value: Any, *, allowed_keys: set[str] | None = None) -> dict[str, Any]:
    safe = _safe_value(value, allowed_keys=allowed_keys)
    return safe if isinstance(safe, dict) else {}


def _safe_value(value: Any, *, allowed_keys: set[str] | None = None) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            normalized = key_text.lower()
            if normalized in _FORBIDDEN_KEYS:
                continue
            if allowed_keys is not None and normalized not in allowed_keys:
                continue
            safe_nested = _safe_value(nested)
            if safe_nested is not None:
                result[key_text] = safe_nested
        return result
    if isinstance(value, list):
        result = []
        for nested in value:
            safe_nested = _safe_value(nested)
            if safe_nested is not None:
                result.append(safe_nested)
        return result
    if isinstance(value, tuple):
        return _safe_value(list(value))
    if isinstance(value, str):
        text = value.strip()
        if not text or _CONTROL_CHARS.search(text) or any(pattern.search(text) for pattern in _UNSAFE_STRING_PATTERNS):
            return None
        return text
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)
