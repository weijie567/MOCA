from __future__ import annotations

import pytest

from tests.rag.phase21_xfail_inventory import xfail_for


ACCEPTED_OCR_AVERAGE_CONFIDENCE = 80
REVIEW_NEEDED_OCR_CONFIDENCE_MIN = 55
REVIEW_NEEDED_OCR_CONFIDENCE_MAX = 79
REJECTED_OCR_CONFIDENCE_MAX = 54
OCR_TIMEOUT_SECONDS_PER_PAGE = 15


def _require_tesseract_preflight() -> None:
    pytesseract = pytest.importorskip("pytesseract", reason="pytesseract is required for native OCR tests")
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:  # pragma: no cover - depends on local native install
        pytest.skip(f"native Tesseract runtime unavailable: {exc}")


def test_ocr_confidence_threshold_scaffold_values_are_locked() -> None:
    assert ACCEPTED_OCR_AVERAGE_CONFIDENCE >= 80
    assert REVIEW_NEEDED_OCR_CONFIDENCE_MIN == 55
    assert REVIEW_NEEDED_OCR_CONFIDENCE_MAX == 79
    assert REJECTED_OCR_CONFIDENCE_MAX < 55
    assert OCR_TIMEOUT_SECONDS_PER_PAGE == 15


@xfail_for("21-03-02/image-ocr")
def test_image_ocr_parser_emits_text_pixel_boxes_language_engine_and_timeout_status() -> None:
    _require_tesseract_preflight()

    from src.rag.parsers.ocr import OcrParser

    result = OcrParser(language="chi_sim+eng", timeout_seconds=OCR_TIMEOUT_SECONDS_PER_PAGE).parse_image(
        b"png fixture bytes",
        source_name="refund_notice.png",
    )

    assert result.blocks[0].text == "七天无理由"
    assert result.blocks[0].source_box.unit == "pixel"
    assert result.blocks[0].ocr_metadata["language"] == "chi_sim+eng"
    assert result.blocks[0].ocr_metadata["engine"] == "tesseract"
    assert result.blocks[0].ocr_metadata["engine_version"]
    assert result.status in {"success", "timeout", "error"}


@xfail_for("21-03-02/ocr-confidence-metadata")
def test_ocr_confidence_stays_block_metadata_and_does_not_replace_retrieval_scores() -> None:
    _require_tesseract_preflight()

    from src.rag.parsers.ocr import classify_ocr_confidence

    metadata = classify_ocr_confidence(average_confidence=82)

    assert metadata["quality"] == "accepted"
    assert metadata["average_confidence"] >= ACCEPTED_OCR_AVERAGE_CONFIDENCE
    assert "EvidenceRefV1" not in metadata
    assert "best_score" not in metadata


@xfail_for("21-03-02/ocr-confidence-gates")
def test_ocr_confidence_gates_accept_review_or_reject_by_threshold() -> None:
    _require_tesseract_preflight()

    from src.rag.parsers.ocr import classify_ocr_confidence

    assert classify_ocr_confidence(average_confidence=80)["quality"] == "accepted"
    assert classify_ocr_confidence(average_confidence=55)["quality"] == "review-needed"
    assert classify_ocr_confidence(average_confidence=79)["quality"] == "review-needed"
    assert classify_ocr_confidence(average_confidence=54)["quality"] == "rejected"
    assert classify_ocr_confidence(text="", average_confidence=99)["quality"] == "rejected"

