from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Final, NoReturn
from uuid import UUID

from src.rag.embedding_tokenizer import EmbeddingTokenizerConfigV1, ProviderParityStatus


PARITY_SCHEMA_VERSION: Final = "embedding_tokenizer_parity.v1"
_PARITY_INPUT_COUNT: Final = 10
_SHA256_PREFIX: Final = "sha256:"
_REGION_CLASSES: Final = frozenset({"dashscope_public", "custom_openai_compatible"})
_UNAVAILABLE_REASONS: Final = frozenset(
    {
        "provider_credentials_unavailable",
        "provider_request_unavailable",
        "provider_usage_unavailable",
    }
)
_QUARANTINE_REASONS: Final = frozenset({"single_count_mismatch", "aggregate_count_mismatch"})


class ParityFailureCode(StrEnum):
    REPORT_UNAVAILABLE = "report_unavailable"
    REPORT_INVALID = "report_invalid"
    CREATE_CONFLICT = "create_conflict"
    WRITE_FAILED = "write_failed"
    CONFIG_FINGERPRINT_MISMATCH = "config_fingerprint_mismatch"
    PROVIDER_MISMATCH = "provider_mismatch"
    MODEL_MISMATCH = "model_mismatch"
    FIXTURE_HASH_MISMATCH = "fixture_hash_mismatch"
    CONTENT_HASH_MISMATCH = "content_hash_mismatch"
    STALE = "stale"
    CAPTURE_TIME_INVALID = "capture_time_invalid"
    PASSED_REQUIRED = "passed_required"
    SINGLE_COUNT_MISMATCH = "single_count_mismatch"
    AGGREGATE_COUNT_MISMATCH = "aggregate_count_mismatch"


class TokenizerParityError(RuntimeError):
    """Safe parity failure containing only an allowlisted reason code."""

    def __init__(self, code: ParityFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ParityProbeResultV1:
    probe_id: str
    category: str
    embedding_input_sha256: str
    offline_tokens: int
    provider_prompt_tokens: int | None
    provider_total_tokens: int | None
    exact_match: bool | None


@dataclass(frozen=True, slots=True)
class EmbeddingTokenizerParityReportV1:
    schema_version: str
    run_id: UUID
    captured_at: datetime
    region_class: str
    provider: str
    model: str
    dimensions: int
    tokenizer_contract_version: str
    config_fingerprint: str
    assembly_schema_version: str
    probe_fixture_sha256: str
    submitted_content_sha256: str
    provider_parity_status: ProviderParityStatus
    reason_code: str
    probes: tuple[ParityProbeResultV1, ...]
    aggregate_input_count: int
    aggregate_offline_tokens: int
    aggregate_provider_prompt_tokens: int | None
    aggregate_provider_total_tokens: int | None
    aggregate_exact_match: bool | None


def parity_content_sha256(probes: tuple[ParityProbeResultV1, ...]) -> str:
    safe_identity = [
        {
            "embedding_input_sha256": probe.embedding_input_sha256,
            "offline_tokens": probe.offline_tokens,
            "probe_id": probe.probe_id,
        }
        for probe in probes
    ]
    canonical = json.dumps(safe_identity, sort_keys=True, separators=(",", ":")).encode()
    return _SHA256_PREFIX + hashlib.sha256(canonical).hexdigest()


def build_parity_report(
    *,
    run_id: UUID,
    captured_at: datetime,
    region_class: str,
    config: EmbeddingTokenizerConfigV1,
    probe_fixture_sha256: str,
    submitted_content_sha256: str,
    probes: tuple[ParityProbeResultV1, ...],
    aggregate_provider_prompt_tokens: int | None,
    aggregate_provider_total_tokens: int | None,
    unavailable_reason: str | None = None,
) -> EmbeddingTokenizerParityReportV1:
    _validate_common_inputs(
        run_id=run_id,
        captured_at=captured_at,
        region_class=region_class,
        probe_fixture_sha256=probe_fixture_sha256,
        submitted_content_sha256=submitted_content_sha256,
        probes=probes,
    )
    offline_total = sum(probe.offline_tokens for probe in probes)
    any_missing = (
        any(probe.provider_prompt_tokens is None or probe.provider_total_tokens is None for probe in probes)
        or aggregate_provider_prompt_tokens is None
        or aggregate_provider_total_tokens is None
    )
    any_single_mismatch = any(probe.exact_match is not True for probe in probes)
    aggregate_exact = (
        None
        if aggregate_provider_prompt_tokens is None or aggregate_provider_total_tokens is None
        else aggregate_provider_prompt_tokens == offline_total
    )

    if any_missing:
        status = ProviderParityStatus.UNAVAILABLE
        reason_code = unavailable_reason or "provider_usage_unavailable"
        if reason_code not in _UNAVAILABLE_REASONS:
            _fail(ParityFailureCode.REPORT_INVALID)
    elif any_single_mismatch:
        status = ProviderParityStatus.QUARANTINED
        reason_code = "single_count_mismatch"
    elif aggregate_exact is not True:
        status = ProviderParityStatus.QUARANTINED
        reason_code = "aggregate_count_mismatch"
    else:
        status = ProviderParityStatus.PASSED
        reason_code = "exact_match"

    report = EmbeddingTokenizerParityReportV1(
        schema_version=PARITY_SCHEMA_VERSION,
        run_id=run_id,
        captured_at=captured_at.astimezone(UTC),
        region_class=region_class,
        provider=config.provider,
        model=config.model,
        dimensions=config.dimensions,
        tokenizer_contract_version=config.schema_version,
        config_fingerprint=config.config_fingerprint,
        assembly_schema_version=config.assembly_schema_version,
        probe_fixture_sha256=probe_fixture_sha256,
        submitted_content_sha256=submitted_content_sha256,
        provider_parity_status=status,
        reason_code=reason_code,
        probes=probes,
        aggregate_input_count=len(probes),
        aggregate_offline_tokens=offline_total,
        aggregate_provider_prompt_tokens=aggregate_provider_prompt_tokens,
        aggregate_provider_total_tokens=aggregate_provider_total_tokens,
        aggregate_exact_match=aggregate_exact,
    )
    _validate_report(report)
    return report


def write_parity_report_create_only(
    report: EmbeddingTokenizerParityReportV1,
    *,
    root: Path,
    fault_injector: Callable[[str], None] | None = None,
) -> Path:
    _validate_report(report)
    fingerprint = report.config_fingerprint.removeprefix(_SHA256_PREFIX)
    destination = root / "runs" / fingerprint / f"{report.run_id}.json"
    try:
        _ensure_directory_durable(destination.parent)
    except (OSError, TokenizerParityError):
        _fail(ParityFailureCode.WRITE_FAILED)
    payload = _canonical_report_bytes(report)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".parity-", suffix=".tmp", dir=destination.parent)
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, destination)
        _inject_fault(fault_injector, "published")
        temporary_path.unlink()
        temporary_path = None
        _fsync_directory(destination.parent)
        _inject_fault(fault_injector, "parent_fsynced")
    except FileExistsError:
        _fail(ParityFailureCode.CREATE_CONFLICT)
    except OSError:
        _fail(ParityFailureCode.WRITE_FAILED)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return destination


def _ensure_directory_durable(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        if current == current.parent:
            break
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            continue
        _fsync_directory(directory.parent)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        _fail(ParityFailureCode.WRITE_FAILED)


def _inject_fault(fault_injector: Callable[[str], None] | None, boundary: str) -> None:
    if fault_injector is not None:
        fault_injector(boundary)


def load_parity_report(report_path: Path) -> EmbeddingTokenizerParityReportV1:
    try:
        payload = json.loads(report_path.read_bytes())
    except OSError:
        _fail(ParityFailureCode.REPORT_UNAVAILABLE)
    except (TypeError, ValueError):
        _fail(ParityFailureCode.REPORT_INVALID)
    report = _report_from_payload(payload)
    _validate_report(report)
    return report


def require_fresh_provider_parity(
    report_path: Path,
    *,
    config: EmbeddingTokenizerConfigV1,
    expected_probe_fixture_sha256: str,
    expected_submitted_content_sha256: str,
    now: datetime | None = None,
    maximum_age: timedelta = timedelta(hours=24),
) -> EmbeddingTokenizerParityReportV1:
    report = load_parity_report(report_path)
    if report.config_fingerprint != config.config_fingerprint:
        _fail(ParityFailureCode.CONFIG_FINGERPRINT_MISMATCH)
    if report.provider != config.provider:
        _fail(ParityFailureCode.PROVIDER_MISMATCH)
    if (
        report.model != config.model
        or report.dimensions != config.dimensions
        or report.tokenizer_contract_version != config.schema_version
        or report.assembly_schema_version != config.assembly_schema_version
    ):
        _fail(ParityFailureCode.MODEL_MISMATCH)
    if report.probe_fixture_sha256 != expected_probe_fixture_sha256:
        _fail(ParityFailureCode.FIXTURE_HASH_MISMATCH)
    if (
        report.submitted_content_sha256 != expected_submitted_content_sha256
        or parity_content_sha256(report.probes) != report.submitted_content_sha256
    ):
        _fail(ParityFailureCode.CONTENT_HASH_MISMATCH)

    checked_at = now or datetime.now(UTC)
    if checked_at.tzinfo is None or maximum_age <= timedelta(0):
        _fail(ParityFailureCode.CAPTURE_TIME_INVALID)
    age = checked_at.astimezone(UTC) - report.captured_at.astimezone(UTC)
    if age < timedelta(0):
        _fail(ParityFailureCode.CAPTURE_TIME_INVALID)
    if age > maximum_age:
        _fail(ParityFailureCode.STALE)
    if report.provider_parity_status is not ProviderParityStatus.PASSED:
        _fail(ParityFailureCode.PASSED_REQUIRED)
    if len(report.probes) != _PARITY_INPUT_COUNT or any(
        probe.provider_prompt_tokens != probe.offline_tokens or probe.exact_match is not True for probe in report.probes
    ):
        _fail(ParityFailureCode.SINGLE_COUNT_MISMATCH)
    if (
        report.aggregate_input_count != _PARITY_INPUT_COUNT
        or report.aggregate_offline_tokens != sum(probe.offline_tokens for probe in report.probes)
        or report.aggregate_provider_prompt_tokens != report.aggregate_offline_tokens
        or report.aggregate_provider_total_tokens is None
        or report.aggregate_exact_match is not True
    ):
        _fail(ParityFailureCode.AGGREGATE_COUNT_MISMATCH)
    return report


def _validate_common_inputs(
    *,
    run_id: UUID,
    captured_at: datetime,
    region_class: str,
    probe_fixture_sha256: str,
    submitted_content_sha256: str,
    probes: tuple[ParityProbeResultV1, ...],
) -> None:
    if not isinstance(run_id, UUID) or captured_at.tzinfo is None or region_class not in _REGION_CLASSES:
        _fail(ParityFailureCode.REPORT_INVALID)
    if not _valid_sha256(probe_fixture_sha256) or not _valid_sha256(submitted_content_sha256):
        _fail(ParityFailureCode.REPORT_INVALID)
    if len(probes) != _PARITY_INPUT_COUNT or len({probe.probe_id for probe in probes}) != len(probes):
        _fail(ParityFailureCode.REPORT_INVALID)
    for probe in probes:
        _validate_probe(probe)
    if parity_content_sha256(probes) != submitted_content_sha256:
        _fail(ParityFailureCode.CONTENT_HASH_MISMATCH)


def _validate_report(report: EmbeddingTokenizerParityReportV1) -> None:
    if report.schema_version != PARITY_SCHEMA_VERSION:
        _fail(ParityFailureCode.REPORT_INVALID)
    _validate_common_inputs(
        run_id=report.run_id,
        captured_at=report.captured_at,
        region_class=report.region_class,
        probe_fixture_sha256=report.probe_fixture_sha256,
        submitted_content_sha256=report.submitted_content_sha256,
        probes=report.probes,
    )
    if (
        report.provider != "dashscope"
        or report.model != "text-embedding-v4"
        or type(report.dimensions) is not int
        or report.dimensions <= 0
        or report.tokenizer_contract_version != "embedding_tokenizer.v1"
        or report.assembly_schema_version != "policy_embedding_input.v1"
        or not _valid_sha256(report.config_fingerprint)
        or report.aggregate_input_count != _PARITY_INPUT_COUNT
        or report.aggregate_offline_tokens != sum(probe.offline_tokens for probe in report.probes)
    ):
        _fail(ParityFailureCode.REPORT_INVALID)
    if report.provider_parity_status is ProviderParityStatus.PASSED:
        if report.reason_code != "exact_match":
            _fail(ParityFailureCode.REPORT_INVALID)
    elif report.provider_parity_status is ProviderParityStatus.QUARANTINED:
        if report.reason_code not in _QUARANTINE_REASONS:
            _fail(ParityFailureCode.REPORT_INVALID)
    elif report.reason_code not in _UNAVAILABLE_REASONS:
        _fail(ParityFailureCode.REPORT_INVALID)

    aggregate_exact = (
        None
        if report.aggregate_provider_prompt_tokens is None or report.aggregate_provider_total_tokens is None
        else report.aggregate_provider_prompt_tokens == report.aggregate_offline_tokens
    )
    if report.aggregate_exact_match is not aggregate_exact:
        _fail(ParityFailureCode.REPORT_INVALID)
    missing_usage = (
        any(probe.provider_prompt_tokens is None or probe.provider_total_tokens is None for probe in report.probes)
        or aggregate_exact is None
    )
    single_mismatch = any(probe.exact_match is not True for probe in report.probes)
    if report.provider_parity_status is ProviderParityStatus.PASSED:
        if missing_usage or single_mismatch or aggregate_exact is not True:
            _fail(ParityFailureCode.REPORT_INVALID)
    elif report.provider_parity_status is ProviderParityStatus.QUARANTINED:
        expected_reason = "single_count_mismatch" if single_mismatch else "aggregate_count_mismatch"
        if missing_usage or aggregate_exact is None or report.reason_code != expected_reason:
            _fail(ParityFailureCode.REPORT_INVALID)
    elif not missing_usage:
        _fail(ParityFailureCode.REPORT_INVALID)


def _validate_probe(probe: ParityProbeResultV1) -> None:
    if (
        not probe.probe_id
        or not probe.category
        or not _valid_sha256(probe.embedding_input_sha256)
        or type(probe.offline_tokens) is not int
        or probe.offline_tokens <= 0
    ):
        _fail(ParityFailureCode.REPORT_INVALID)
    prompt = probe.provider_prompt_tokens
    total = probe.provider_total_tokens
    if prompt is None or total is None:
        if prompt is not None or total is not None or probe.exact_match is not None:
            _fail(ParityFailureCode.REPORT_INVALID)
        return
    if type(prompt) is not int or prompt < 0 or type(total) is not int or total < 0:
        _fail(ParityFailureCode.REPORT_INVALID)
    if probe.exact_match is not (prompt == probe.offline_tokens):
        _fail(ParityFailureCode.REPORT_INVALID)


def _report_from_payload(payload: object) -> EmbeddingTokenizerParityReportV1:
    report_fields = {
        "schema_version",
        "run_id",
        "captured_at",
        "region_class",
        "provider",
        "model",
        "dimensions",
        "tokenizer_contract_version",
        "config_fingerprint",
        "assembly_schema_version",
        "probe_fixture_sha256",
        "submitted_content_sha256",
        "provider_parity_status",
        "reason_code",
        "probes",
        "aggregate_input_count",
        "aggregate_offline_tokens",
        "aggregate_provider_prompt_tokens",
        "aggregate_provider_total_tokens",
        "aggregate_exact_match",
    }
    if not isinstance(payload, dict) or set(payload) != report_fields or not isinstance(payload["probes"], list):
        _fail(ParityFailureCode.REPORT_INVALID)
    try:
        probes = tuple(_probe_from_payload(item) for item in payload["probes"])
        captured_at = datetime.fromisoformat(str(payload["captured_at"]).replace("Z", "+00:00"))
        report = EmbeddingTokenizerParityReportV1(
            schema_version=_strict_str(payload["schema_version"]),
            run_id=UUID(_strict_str(payload["run_id"])),
            captured_at=captured_at,
            region_class=_strict_str(payload["region_class"]),
            provider=_strict_str(payload["provider"]),
            model=_strict_str(payload["model"]),
            dimensions=_strict_int(payload["dimensions"]),
            tokenizer_contract_version=_strict_str(payload["tokenizer_contract_version"]),
            config_fingerprint=_strict_str(payload["config_fingerprint"]),
            assembly_schema_version=_strict_str(payload["assembly_schema_version"]),
            probe_fixture_sha256=_strict_str(payload["probe_fixture_sha256"]),
            submitted_content_sha256=_strict_str(payload["submitted_content_sha256"]),
            provider_parity_status=ProviderParityStatus(_strict_str(payload["provider_parity_status"])),
            reason_code=_strict_str(payload["reason_code"]),
            probes=probes,
            aggregate_input_count=_strict_int(payload["aggregate_input_count"]),
            aggregate_offline_tokens=_strict_int(payload["aggregate_offline_tokens"]),
            aggregate_provider_prompt_tokens=_optional_int(payload["aggregate_provider_prompt_tokens"]),
            aggregate_provider_total_tokens=_optional_int(payload["aggregate_provider_total_tokens"]),
            aggregate_exact_match=_optional_bool(payload["aggregate_exact_match"]),
        )
    except (TypeError, ValueError):
        _fail(ParityFailureCode.REPORT_INVALID)
    return report


def _probe_from_payload(payload: object) -> ParityProbeResultV1:
    expected_fields = {
        "probe_id",
        "category",
        "embedding_input_sha256",
        "offline_tokens",
        "provider_prompt_tokens",
        "provider_total_tokens",
        "exact_match",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        _fail(ParityFailureCode.REPORT_INVALID)
    return ParityProbeResultV1(
        probe_id=_strict_str(payload["probe_id"]),
        category=_strict_str(payload["category"]),
        embedding_input_sha256=_strict_str(payload["embedding_input_sha256"]),
        offline_tokens=_strict_int(payload["offline_tokens"]),
        provider_prompt_tokens=_optional_int(payload["provider_prompt_tokens"]),
        provider_total_tokens=_optional_int(payload["provider_total_tokens"]),
        exact_match=_optional_bool(payload["exact_match"]),
    )


def _canonical_report_bytes(report: EmbeddingTokenizerParityReportV1) -> bytes:
    payload: dict[str, Any] = {
        "schema_version": report.schema_version,
        "run_id": str(report.run_id),
        "captured_at": report.captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "region_class": report.region_class,
        "provider": report.provider,
        "model": report.model,
        "dimensions": report.dimensions,
        "tokenizer_contract_version": report.tokenizer_contract_version,
        "config_fingerprint": report.config_fingerprint,
        "assembly_schema_version": report.assembly_schema_version,
        "probe_fixture_sha256": report.probe_fixture_sha256,
        "submitted_content_sha256": report.submitted_content_sha256,
        "provider_parity_status": report.provider_parity_status.value,
        "reason_code": report.reason_code,
        "probes": [
            {
                "probe_id": probe.probe_id,
                "category": probe.category,
                "embedding_input_sha256": probe.embedding_input_sha256,
                "offline_tokens": probe.offline_tokens,
                "provider_prompt_tokens": probe.provider_prompt_tokens,
                "provider_total_tokens": probe.provider_total_tokens,
                "exact_match": probe.exact_match,
            }
            for probe in report.probes
        ],
        "aggregate_input_count": report.aggregate_input_count,
        "aggregate_offline_tokens": report.aggregate_offline_tokens,
        "aggregate_provider_prompt_tokens": report.aggregate_provider_prompt_tokens,
        "aggregate_provider_total_tokens": report.aggregate_provider_total_tokens,
        "aggregate_exact_match": report.aggregate_exact_match,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(_SHA256_PREFIX):
        return False
    digest = value.removeprefix(_SHA256_PREFIX)
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _strict_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value


def _strict_int(value: object) -> int:
    if type(value) is not int:
        raise TypeError
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _strict_int(value)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise TypeError
    return value


def _fail(code: ParityFailureCode) -> NoReturn:
    raise TokenizerParityError(code) from None
