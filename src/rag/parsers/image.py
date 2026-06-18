from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from src.rag.parsers.base import ParseResult, ParserFailureCode, safe_failed_result
from src.rag.parsers.ocr import OcrEngine
from src.rag.parsers.safety import validate_source_file


PARSER_NAME = "moca_image_ocr"
PARSER_VERSION = "21.03"

_SOURCE_FAILURE_TO_PARSE_FAILURE = {
    "UNSUPPORTED_SOURCE_TYPE": ParserFailureCode.UNSUPPORTED_SOURCE_TYPE.value,
    "SOURCE_SIGNATURE_MISMATCH": ParserFailureCode.SIGNATURE_MISMATCH.value,
    "SOURCE_FILE_TOO_LARGE": ParserFailureCode.FILE_TOO_LARGE.value,
    "SOURCE_IMAGE_TOO_LARGE": ParserFailureCode.IMAGE_TOO_LARGE.value,
    "BUSINESS_ARTIFACT_REJECTED": ParserFailureCode.BUSINESS_ARTIFACT_REJECTED.value,
    "SOURCE_MALFORMED": ParserFailureCode.MALFORMED_SOURCE.value,
    "SOURCE_DECOMPRESSION_HAZARD": "decompression_hazard",
}


class ImageOcrParser:
    source_type = "policy_image"
    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff"})

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
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=_SOURCE_FAILURE_TO_PARSE_FAILURE.get(
                    validation.failure_code or "",
                    ParserFailureCode.MALFORMED_SOURCE.value,
                ),
                safe_message=validation.safe_message or "Policy image source failed validation safely.",
            )

        try:
            with Image.open(path) as image:
                ocr_image = image.convert("RGB")
                rotation = _image_rotation(image)
        except Exception:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy image source could not be opened safely.",
            )

        result = self.ocr_engine.parse_image(
            ocr_image,
            doc_key=doc_key,
            source_type=source_type,
            block_index=0,
            page_number=None,
            rotation=rotation,
        )
        return ParseResult(
            status=result.status,
            source_type=source_type,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            blocks=result.blocks,
            warnings=result.warnings,
            failure_code=result.failure_code,
            safe_message=result.safe_message,
        )


def _image_rotation(image: Image.Image) -> int | None:
    try:
        exif = image.getexif()
    except Exception:
        return None
    orientation = exif.get(274) if exif else None
    return {3: 180, 6: 90, 8: 270}.get(orientation)
