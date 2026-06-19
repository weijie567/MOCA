from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


ACCEPTED_OCR_AVERAGE_CONFIDENCE = 80
REVIEW_NEEDED_OCR_CONFIDENCE_MIN = 55
REVIEW_NEEDED_OCR_CONFIDENCE_MAX = 79
REJECTED_OCR_CONFIDENCE_MAX = 54
OCR_TIMEOUT_SECONDS_PER_PAGE = 15


def test_ocr_confidence_threshold_scaffold_values_are_locked() -> None:
    assert ACCEPTED_OCR_AVERAGE_CONFIDENCE >= 80
    assert REVIEW_NEEDED_OCR_CONFIDENCE_MIN == 55
    assert REVIEW_NEEDED_OCR_CONFIDENCE_MAX == 79
    assert REJECTED_OCR_CONFIDENCE_MAX < 55
    assert OCR_TIMEOUT_SECONDS_PER_PAGE == 15


def _completed(stdout: str, returncode: int = 0):
    from subprocess import CompletedProcess

    return CompletedProcess(args=["tesseract"], returncode=returncode, stdout=stdout, stderr="")


def test_ocr_runtime_preflight_accepts_chi_sim_and_eng(monkeypatch) -> None:
    from src.rag.parsers import runtime

    def fake_run(args, **kwargs):
        if args == ["tesseract", "--version"]:
            return _completed("tesseract 5.5.0\n")
        return _completed("List of available languages in /safe:\nchi_sim\neng\n")

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    result = runtime.check_ocr_runtime()

    assert result.available is True
    assert result.failure_code is None
    assert result.installed_languages == ("chi_sim", "eng")


def test_ocr_runtime_preflight_reports_missing_chi_sim(monkeypatch) -> None:
    from src.rag.parsers import runtime

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda args, **kwargs: _completed("tesseract 5.5.0\n")
        if args == ["tesseract", "--version"]
        else _completed("List of available languages in /safe:\neng\n"),
    )

    result = runtime.check_ocr_runtime()

    assert result.available is False
    assert result.failure_code == "OCR_LANGUAGE_UNAVAILABLE"
    assert result.missing_languages == ("chi_sim",)


def test_ocr_runtime_preflight_reports_missing_eng(monkeypatch) -> None:
    from src.rag.parsers import runtime

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda args, **kwargs: _completed("tesseract 5.5.0\n")
        if args == ["tesseract", "--version"]
        else _completed("List of available languages in /safe:\nchi_sim\n"),
    )

    result = runtime.check_ocr_runtime()

    assert result.available is False
    assert result.failure_code == "OCR_LANGUAGE_UNAVAILABLE"
    assert result.missing_languages == ("eng",)


def test_ocr_runtime_preflight_reports_missing_executable(monkeypatch) -> None:
    from src.rag.parsers import runtime

    def missing_run(args, **kwargs):
        raise FileNotFoundError("tesseract")

    monkeypatch.setattr(runtime.subprocess, "run", missing_run)

    result = runtime.check_ocr_runtime()

    assert result.available is False
    assert result.failure_code == "OCR_RUNTIME_UNAVAILABLE"
    assert result.missing_languages == ("chi_sim", "eng")


def _write_png(tmp_path, *, name: str = "refund_notice.png", size: tuple[int, int] = (200, 80)) -> Path:
    path = tmp_path / name
    Image.new("RGB", size, color="white").save(path)
    return path


def _ocr_data(*, texts: list[str], confidences: list[int]) -> dict[str, list]:
    return {
        "level": [5 for _ in texts],
        "page_num": [1 for _ in texts],
        "block_num": [1 for _ in texts],
        "par_num": [1 for _ in texts],
        "line_num": [1 for _ in texts],
        "word_num": list(range(1, len(texts) + 1)),
        "left": [10 + index * 42 for index, _ in enumerate(texts)],
        "top": [12 for _ in texts],
        "width": [36 for _ in texts],
        "height": [18 for _ in texts],
        "conf": confidences,
        "text": texts,
    }


def test_image_ocr_parser_emits_text_pixel_boxes_language_engine_and_timeout_status(tmp_path, monkeypatch) -> None:
    from src.rag.parsers import ocr as ocr_module
    from src.rag.parsers.image import ImageOcrParser

    image_path = _write_png(tmp_path)
    calls: dict[str, object] = {}

    def fake_image_to_data(image, *, lang, output_type, timeout, config=""):
        calls.update({"lang": lang, "timeout": timeout, "output_type": output_type})
        return _ocr_data(texts=["七天", "无理由"], confidences=[90, 86])

    monkeypatch.setattr(ocr_module.pytesseract, "get_tesseract_version", lambda: "5.5.0")
    monkeypatch.setattr(ocr_module.pytesseract, "image_to_data", fake_image_to_data)

    result = ImageOcrParser().parse(image_path, doc_key="refund_notice", source_type="policy_image", metadata={})

    assert result.status == "success"
    assert result.blocks[0].text == "七天 无理由"
    assert result.blocks[0].box is not None
    assert result.blocks[0].box.unit == "pixel"
    assert result.blocks[0].box.origin == "top_left"
    assert result.blocks[0].box.width == 200
    assert result.blocks[0].box.height == 80
    assert result.blocks[0].ocr_metadata["language"] == "chi_sim+eng"
    assert result.blocks[0].ocr_metadata["engine"] == "tesseract"
    assert result.blocks[0].ocr_metadata["engine_version"] == "5.5.0"
    assert result.blocks[0].ocr_metadata["average_confidence"] == pytest.approx(88.0)
    assert result.blocks[0].ocr_metadata["confidence_status"] == "accepted"
    assert result.blocks[0].ocr_metadata["low_confidence_word_count"] == 0
    assert result.blocks[0].ocr_metadata["timeout"] is False
    assert result.blocks[0].ocr_metadata["error"] is None
    assert result.blocks[0].ocr_metadata["word_boxes"][0]["unit"] == "pixel"
    assert calls == {
        "lang": "chi_sim+eng",
        "timeout": OCR_TIMEOUT_SECONDS_PER_PAGE,
        "output_type": ocr_module.pytesseract.Output.DICT,
    }


def test_image_ocr_parser_sanitizes_word_box_text_and_metadata(tmp_path, monkeypatch) -> None:
    from src.rag.parsers import ocr as ocr_module
    from src.rag.parsers.base import ParserWarningCode
    from src.rag.parsers.image import ImageOcrParser

    image_path = _write_png(tmp_path)

    def fake_image_to_data(image, *, lang, output_type, timeout, config=""):
        return _ocr_data(
            texts=[
                "七天",
                "/Users/ming/private/ocr-source.png",
                "parser_dump: Traceback (most recent call last)",
            ],
            confidences=[90, 88, 91],
        )

    monkeypatch.setattr(ocr_module.pytesseract, "get_tesseract_version", lambda: "5.5.0")
    monkeypatch.setattr(ocr_module.pytesseract, "image_to_data", fake_image_to_data)

    result = ImageOcrParser().parse(image_path, doc_key="refund_notice", source_type="policy_image", metadata={})
    metadata_projection = repr(result.blocks[0].ocr_metadata)
    warning_codes = {warning.code for warning in result.warnings}

    assert result.status == "degraded"
    assert "七天" in result.blocks[0].text
    assert "/Users/ming" not in result.blocks[0].text
    assert "/Users/ming" not in metadata_projection
    assert "Traceback" not in result.blocks[0].text
    assert "Traceback" not in metadata_projection
    assert ParserWarningCode.LOCAL_PATH_REDACTED.value in warning_codes
    assert ParserWarningCode.RAW_PARSER_PAYLOAD_IGNORED.value in warning_codes


def test_image_ocr_parser_tolerates_malformed_ocr_dict_lengths(tmp_path, monkeypatch) -> None:
    from src.rag.parsers import ocr as ocr_module
    from src.rag.parsers.image import ImageOcrParser

    image_path = _write_png(tmp_path)

    def fake_image_to_data(image, *, lang, output_type, timeout, config=""):
        data = _ocr_data(texts=["七天", "无理由"], confidences=[90, 86])
        data["conf"] = [90]
        return data

    monkeypatch.setattr(ocr_module.pytesseract, "get_tesseract_version", lambda: "5.5.0")
    monkeypatch.setattr(ocr_module.pytesseract, "image_to_data", fake_image_to_data)

    result = ImageOcrParser().parse(image_path, doc_key="refund_notice", source_type="policy_image", metadata={})

    assert result.status == "success"
    assert result.blocks[0].text == "七天"


def test_ocr_confidence_gates_accept_review_or_reject_by_threshold() -> None:
    from src.rag.parsers.ocr import classify_ocr_confidence

    assert classify_ocr_confidence(text="ok", average_confidence=80)["confidence_status"] == "accepted"
    assert classify_ocr_confidence(text="ok", average_confidence=55)["confidence_status"] == "review_needed"
    assert classify_ocr_confidence(text="ok", average_confidence=79)["confidence_status"] == "review_needed"
    assert classify_ocr_confidence(text="ok", average_confidence=54)["confidence_status"] == "rejected"
    assert classify_ocr_confidence(text="", average_confidence=99)["confidence_status"] == "rejected"


def test_ocr_confidence_stays_block_metadata_and_has_no_retrieval_fields() -> None:
    from src.rag.parsers.ocr import classify_ocr_confidence

    metadata = classify_ocr_confidence(text="七天无理由", average_confidence=82)

    assert metadata["confidence_status"] == "accepted"
    assert metadata["average_confidence"] >= ACCEPTED_OCR_AVERAGE_CONFIDENCE
    assert "EvidenceRefV1" not in metadata
    assert "best_score" not in metadata


def test_image_ocr_timeout_returns_safe_failure_without_local_path(tmp_path, monkeypatch) -> None:
    from src.rag.parsers import ocr as ocr_module
    from src.rag.parsers.image import ImageOcrParser

    image_path = _write_png(tmp_path)

    def fake_timeout(*args, **kwargs):
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(ocr_module.pytesseract, "get_tesseract_version", lambda: "5.5.0")
    monkeypatch.setattr(ocr_module.pytesseract, "image_to_data", fake_timeout)

    result = ImageOcrParser().parse(image_path, doc_key="refund_notice", source_type="policy_image", metadata={})

    assert result.status == "failed"
    assert result.failure_code == "ocr_timeout"
    assert result.blocks == ()
    assert result.safe_message == "OCR execution timed out safely."
    assert str(image_path) not in repr(result)
