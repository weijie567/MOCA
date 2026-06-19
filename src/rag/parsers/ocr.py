from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytesseract
from PIL.Image import Image as PillowImage

from src.rag.parsers.base import (
    ParsedBlock,
    ParseResult,
    ParserFailureCode,
    ParserWarning,
    SourceBox,
    normalize_block_text,
    safe_failed_result,
    sanitize_parser_text,
    sanitize_visible_text,
    validate_doc_key,
)
from src.rag.parsers.safety import (
    OCR_CONFIDENCE_ACCEPTED_MIN,
    OCR_CONFIDENCE_REVIEW_MIN,
    OCR_TIMEOUT_SECONDS_PER_PAGE,
)


PARSER_NAME = "moca_ocr"
PARSER_VERSION = "21.03"
DEFAULT_OCR_LANGUAGE = "chi_sim+eng"
OCR_ENGINE_NAME = "tesseract"


@dataclass(frozen=True)
class OcrEngine:
    language: str = DEFAULT_OCR_LANGUAGE
    timeout_seconds: int = OCR_TIMEOUT_SECONDS_PER_PAGE
    parser_name: str = PARSER_NAME
    parser_version: str = PARSER_VERSION

    def parse_image(
        self,
        image: PillowImage,
        *,
        doc_key: str,
        source_type: str,
        block_index: int = 0,
        page_number: int | None = None,
        rotation: int | None = None,
    ) -> ParseResult:
        engine_version = _engine_version()
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                output_type=pytesseract.Output.DICT,
                timeout=self.timeout_seconds,
            )
        except RuntimeError as exc:
            if "timeout" in str(exc).lower():
                return safe_failed_result(
                    source_type=source_type,
                    parser_name=self.parser_name,
                    parser_version=self.parser_version,
                    failure_code=ParserFailureCode.OCR_TIMEOUT,
                    safe_message="OCR execution timed out safely.",
                )
            return _ocr_safe_failure(source_type=source_type)
        except Exception:
            return _ocr_safe_failure(source_type=source_type)

        try:
            words, word_warnings = _word_boxes(data, page_number=page_number, block_index=block_index)
        except Exception:
            return _ocr_safe_failure(source_type=source_type)
        text = " ".join(word["text"] for word in words if str(word.get("text", "")).strip()).strip()
        sanitized, warnings = sanitize_visible_text(text, block_index=block_index)
        warnings = (*word_warnings, *warnings)
        confidences = [float(word["confidence"]) for word in words if isinstance(word.get("confidence"), int | float)]
        average_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        confidence_metadata = classify_ocr_confidence(text=sanitized, average_confidence=average_confidence)
        low_confidence_word_count = sum(1 for confidence in confidences if confidence < OCR_CONFIDENCE_REVIEW_MIN)
        metadata: dict[str, Any] = {
            "language": self.language,
            "engine": OCR_ENGINE_NAME,
            "engine_version": engine_version,
            "timeout": False,
            "error": None,
            "word_boxes": words,
            "average_confidence": average_confidence,
            "confidence": average_confidence,
            "low_confidence_word_count": low_confidence_word_count,
            **confidence_metadata,
        }
        if rotation is not None:
            metadata["rotation"] = rotation
        metadata["image_width"] = image.width
        metadata["image_height"] = image.height

        if not sanitized:
            return ParseResult(
                status="degraded",
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                blocks=(),
                warnings=warnings,
                failure_code=None,
                safe_message=None,
            )

        block = ParsedBlock(
            source_block_id=_ocr_source_block_id(doc_key=doc_key, source_type=source_type, block_index=block_index),
            block_index=block_index,
            block_type="ocr_text",
            text=sanitized,
            normalized_text=normalize_block_text(sanitized),
            source_type=source_type,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            page_number=page_number,
            box=_source_box_for_words(words, image=image, page_number=page_number, rotation=rotation),
            table_metadata={},
            ocr_metadata=metadata,
            warnings=warnings,
        )
        return ParseResult(
            status="degraded" if warnings else "success",
            source_type=source_type,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            blocks=(block,),
            warnings=warnings,
            failure_code=None,
            safe_message=None,
        )


def classify_ocr_confidence(*, text: str = "", average_confidence: float | int | None = None) -> dict[str, Any]:
    confidence = float(average_confidence or 0.0)
    if not text.strip() or confidence < OCR_CONFIDENCE_REVIEW_MIN:
        status = "rejected"
    elif confidence >= OCR_CONFIDENCE_ACCEPTED_MIN:
        status = "accepted"
    else:
        status = "review_needed"
    return {"confidence_status": status, "average_confidence": confidence}


def _engine_version() -> str:
    try:
        return str(pytesseract.get_tesseract_version())[:80]
    except Exception:
        return "unavailable"


def _ocr_safe_failure(*, source_type: str) -> ParseResult:
    return safe_failed_result(
        source_type=source_type,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        failure_code=ParserFailureCode.MALFORMED_SOURCE,
        safe_message="OCR execution failed safely.",
    )


def _word_boxes(
    data: dict[str, list[Any]], *, page_number: int | None, block_index: int | None
) -> tuple[list[dict[str, Any]], tuple[ParserWarning, ...]]:
    texts = data.get("text", [])
    boxes: list[dict[str, Any]] = []
    warnings: list[ParserWarning] = []
    for index, raw_text in enumerate(texts):
        text, text_warnings = sanitize_parser_text(str(raw_text).strip(), block_index=block_index)
        warnings.extend(text_warnings)
        confidence = _confidence_at(data, index)
        if not text or confidence < 0:
            continue
        left = _number_at(data, "left", index)
        top = _number_at(data, "top", index)
        width = _number_at(data, "width", index)
        height = _number_at(data, "height", index)
        boxes.append(
            {
                "text": text,
                "confidence": confidence,
                "x0": left,
                "y0": top,
                "x1": left + width,
                "y1": top + height,
                "width": width,
                "height": height,
                "unit": "pixel",
                "origin": "top_left",
                "page_number": page_number,
            }
        )
    return boxes, tuple(warnings)


def _source_box_for_words(
    words: list[dict[str, Any]],
    *,
    image: PillowImage,
    page_number: int | None,
    rotation: int | None,
) -> SourceBox:
    if not words:
        return SourceBox(
            page_number=page_number,
            x0=None,
            y0=None,
            x1=None,
            y1=None,
            width=float(image.width),
            height=float(image.height),
            unit="pixel",
            rotation=rotation,
        )
    return SourceBox(
        page_number=page_number,
        x0=min(float(word["x0"]) for word in words),
        y0=min(float(word["y0"]) for word in words),
        x1=max(float(word["x1"]) for word in words),
        y1=max(float(word["y1"]) for word in words),
        width=float(image.width),
        height=float(image.height),
        unit="pixel",
        rotation=rotation,
    )


def _confidence_at(data: dict[str, list[Any]], index: int) -> float:
    try:
        value = data.get("conf", [])[index]
        return float(value)
    except (TypeError, ValueError, IndexError):
        return -1.0


def _number_at(data: dict[str, list[Any]], key: str, index: int) -> float:
    try:
        return float(data.get(key, [])[index])
    except (TypeError, ValueError, IndexError):
        return 0.0


def _ocr_source_block_id(*, doc_key: str, source_type: str, block_index: int) -> str:
    safe_doc_key = validate_doc_key(doc_key)
    return f"{safe_doc_key}:{source_type}:ocr:{block_index:04d}"
