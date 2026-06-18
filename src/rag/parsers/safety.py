from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.rag.parsers.base import ParserFailureCode


MAX_SOURCE_FILE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_IMAGE_DIMENSION = 8000
PARSER_TIMEOUT_SECONDS = 30
OCR_TIMEOUT_SECONDS_PER_PAGE = 15
OCR_CONFIDENCE_ACCEPTED_MIN = 80
OCR_CONFIDENCE_REVIEW_MIN = 55

POLICY_SOURCE_TYPES = frozenset(
    {
        "policy_markdown",
        "policy_plain_text",
        "policy_text",
        "policy_pdf",
        "policy_docx",
        "policy_image",
    }
)

_BUSINESS_ARTIFACT_TYPES = frozenset(
    {
        "order",
        "refund",
        "ticket",
        "screenshot",
        "tool_result",
        "business_fact_ref",
        "action_trace",
        "order_export",
        "refund_case",
        "ticket_transcript",
        "business_screenshot",
    }
)
_BUSINESS_ARTIFACT_PREFIXES = ("order_", "refund_", "ticket_", "screenshot_", "action_trace_")

_SOURCE_TYPE_BY_EXTENSION = {
    ".md": "policy_markdown",
    ".markdown": "policy_markdown",
    ".txt": "policy_plain_text",
    ".text": "policy_plain_text",
    ".pdf": "policy_pdf",
    ".docx": "policy_docx",
    ".png": "policy_image",
    ".jpg": "policy_image",
    ".jpeg": "policy_image",
    ".tif": "policy_image",
    ".tiff": "policy_image",
}

_SIGNATURES_BY_EXTENSION = {
    ".pdf": (b"%PDF",),
    ".docx": (b"PK\x03\x04",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}

_CONTENT_TYPES_BY_EXTENSION = {
    ".md": frozenset({"text/markdown", "text/plain", "application/octet-stream"}),
    ".markdown": frozenset({"text/markdown", "text/plain", "application/octet-stream"}),
    ".txt": frozenset({"text/plain", "application/octet-stream"}),
    ".text": frozenset({"text/plain", "application/octet-stream"}),
    ".pdf": frozenset({"application/pdf", "application/octet-stream"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
        }
    ),
    ".png": frozenset({"image/png", "application/octet-stream"}),
    ".jpg": frozenset({"image/jpeg", "application/octet-stream"}),
    ".jpeg": frozenset({"image/jpeg", "application/octet-stream"}),
    ".tif": frozenset({"image/tiff", "application/octet-stream"}),
    ".tiff": frozenset({"image/tiff", "application/octet-stream"}),
}


@dataclass(frozen=True)
class SourceValidationResult:
    allowed: bool
    failure_code: str | None = None
    safe_message: str | None = None
    source_type: str | None = None


def reject_business_artifact_source(source_type: str, metadata: dict | None = None) -> str | None:
    normalized = source_type.strip().lower()
    metadata = metadata or {}
    metadata_values = {
        str(metadata.get(key, "")).strip().lower()
        for key in ("source_type", "source_kind", "artifact_type", "kind", "object_type")
    }

    if (
        normalized in _BUSINESS_ARTIFACT_TYPES
        or any(normalized.startswith(prefix) for prefix in _BUSINESS_ARTIFACT_PREFIXES)
        or metadata_values.intersection(_BUSINESS_ARTIFACT_TYPES)
    ):
        return ParserFailureCode.BUSINESS_ARTIFACT_REJECTED.value
    return None


def validate_policy_source_type(source_type: str, metadata: dict | None = None) -> SourceValidationResult:
    business_failure = reject_business_artifact_source(source_type, metadata)
    if business_failure:
        return SourceValidationResult(
            allowed=False,
            failure_code=business_failure,
            safe_message="Business artifacts cannot be ingested as policy sources.",
            source_type=source_type,
        )

    if source_type not in POLICY_SOURCE_TYPES:
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.UNSUPPORTED_SOURCE_TYPE.value,
            safe_message="Unsupported policy source type.",
            source_type=source_type,
        )

    return SourceValidationResult(allowed=True, source_type=source_type)


def validate_policy_source(
    *,
    filename: str,
    declared_content_type: str | None,
    signature: bytes,
    size_bytes: int,
    source_type: str | None = None,
    metadata: dict | None = None,
    page_count: int | None = None,
    image_dimensions: tuple[int, int] | None = None,
) -> SourceValidationResult:
    extension = Path(filename).suffix.lower()
    inferred_source_type = _SOURCE_TYPE_BY_EXTENSION.get(extension)
    effective_source_type = source_type or inferred_source_type

    if effective_source_type is None:
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.UNSUPPORTED_SOURCE_TYPE.value,
            safe_message="Unsupported policy source extension.",
        )

    source_type_result = validate_policy_source_type(effective_source_type, metadata)
    if not source_type_result.allowed:
        return source_type_result

    if inferred_source_type is None or inferred_source_type != effective_source_type:
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.SIGNATURE_MISMATCH.value,
            safe_message="Policy source extension does not match source type.",
            source_type=effective_source_type,
        )

    if size_bytes > MAX_SOURCE_FILE_BYTES:
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.FILE_TOO_LARGE.value,
            safe_message="Policy source exceeds the maximum file size.",
            source_type=effective_source_type,
        )

    expected_content_types = _CONTENT_TYPES_BY_EXTENSION.get(extension, frozenset())
    if declared_content_type and expected_content_types and declared_content_type not in expected_content_types:
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.SIGNATURE_MISMATCH.value,
            safe_message="Declared content type does not match policy source extension.",
            source_type=effective_source_type,
        )

    expected_signatures = _SIGNATURES_BY_EXTENSION.get(extension, ())
    if expected_signatures and not any(signature.startswith(expected) for expected in expected_signatures):
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.SIGNATURE_MISMATCH.value,
            safe_message="Policy source file signature does not match extension.",
            source_type=effective_source_type,
        )

    if effective_source_type == "policy_pdf" and page_count is not None and page_count > MAX_PDF_PAGES:
        return SourceValidationResult(
            allowed=False,
            failure_code=ParserFailureCode.TOO_MANY_PAGES.value,
            safe_message="Policy PDF exceeds the maximum page count.",
            source_type=effective_source_type,
        )

    if effective_source_type == "policy_image" and image_dimensions is not None:
        width, height = image_dimensions
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            return SourceValidationResult(
                allowed=False,
                failure_code=ParserFailureCode.IMAGE_TOO_LARGE.value,
                safe_message="Policy image exceeds the maximum dimensions.",
                source_type=effective_source_type,
            )

    return SourceValidationResult(allowed=True, source_type=effective_source_type)
