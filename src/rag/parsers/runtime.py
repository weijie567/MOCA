from __future__ import annotations

import concurrent.futures
import subprocess
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from src.rag.parsers.base import ParserFailureCode
from src.rag.parsers.safety import OCR_TIMEOUT_SECONDS_PER_PAGE, PARSER_TIMEOUT_SECONDS


T = TypeVar("T")


@dataclass(frozen=True)
class RuntimePreflightResult:
    available: bool
    installed_languages: tuple[str, ...] = ()
    version: str | None = None
    missing_languages: tuple[str, ...] = ()
    failure_code: str | None = None
    safe_message: str | None = None


@dataclass(frozen=True)
class DeadlineResult(Generic[T]):
    stage: str
    status: str
    value: T | None = None
    failure_code: str | None = None
    safe_message: str | None = None


def check_ocr_runtime(required_languages: tuple[str, ...] = ("chi_sim", "eng")) -> RuntimePreflightResult:
    """Preflight native Tesseract without exposing local paths or raw process dumps."""
    try:
        version_proc = subprocess.run(
            ["tesseract", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        langs_proc = subprocess.run(
            ["tesseract", "--list-langs"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return RuntimePreflightResult(
            available=False,
            failure_code="OCR_RUNTIME_UNAVAILABLE",
            safe_message="Tesseract OCR executable is unavailable.",
            missing_languages=tuple(required_languages),
        )
    except (OSError, subprocess.SubprocessError):
        return RuntimePreflightResult(
            available=False,
            failure_code="OCR_RUNTIME_UNAVAILABLE",
            safe_message="Tesseract OCR runtime preflight failed safely.",
            missing_languages=tuple(required_languages),
        )

    version = _safe_version_line(version_proc.stdout)
    languages = _parse_tesseract_languages(langs_proc.stdout)
    if version_proc.returncode != 0 or langs_proc.returncode != 0:
        return RuntimePreflightResult(
            available=False,
            installed_languages=languages,
            version=version,
            missing_languages=tuple(required_languages),
            failure_code="OCR_RUNTIME_UNAVAILABLE",
            safe_message="Tesseract OCR runtime preflight failed safely.",
        )

    required = tuple(dict.fromkeys(required_languages))
    missing = tuple(language for language in required if language not in set(languages))
    if missing:
        return RuntimePreflightResult(
            available=False,
            installed_languages=languages,
            version=version,
            missing_languages=missing,
            failure_code="OCR_LANGUAGE_UNAVAILABLE",
            safe_message="Tesseract OCR language data is unavailable.",
        )

    return RuntimePreflightResult(available=True, installed_languages=languages, version=version)


def run_with_parser_deadline(
    func: Callable[[], T],
    *,
    timeout_seconds: int = PARSER_TIMEOUT_SECONDS,
) -> DeadlineResult[T]:
    return _run_with_deadline(
        func,
        stage="parser",
        timeout_seconds=timeout_seconds,
        timeout_code=ParserFailureCode.PARSER_TIMEOUT.value,
        timeout_message="Parser execution timed out safely.",
    )


def run_with_ocr_deadline(
    func: Callable[[], T],
    *,
    timeout_seconds: int = OCR_TIMEOUT_SECONDS_PER_PAGE,
) -> DeadlineResult[T]:
    return _run_with_deadline(
        func,
        stage="ocr",
        timeout_seconds=timeout_seconds,
        timeout_code=ParserFailureCode.OCR_TIMEOUT.value,
        timeout_message="OCR execution timed out safely.",
    )


def _run_with_deadline(
    func: Callable[[], T],
    *,
    stage: str,
    timeout_seconds: int,
    timeout_code: str,
    timeout_message: str,
) -> DeadlineResult[T]:
    if timeout_seconds <= 0:
        return DeadlineResult(stage=stage, status="failed", failure_code=timeout_code, safe_message=timeout_message)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func)
    try:
        return DeadlineResult(stage=stage, status="success", value=future.result(timeout=timeout_seconds))
    except concurrent.futures.TimeoutError:
        future.cancel()
        return DeadlineResult(stage=stage, status="failed", failure_code=timeout_code, safe_message=timeout_message)
    except Exception:
        return DeadlineResult(
            stage=stage,
            status="failed",
            failure_code=ParserFailureCode.MALFORMED_SOURCE.value,
            safe_message=f"{stage.capitalize()} execution failed safely.",
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _safe_version_line(stdout: str) -> str | None:
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:80]
    return None


def _parse_tesseract_languages(stdout: str) -> tuple[str, ...]:
    languages: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("list of available languages"):
            continue
        languages.append(stripped)
    return tuple(sorted(dict.fromkeys(languages)))
