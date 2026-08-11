from __future__ import annotations

import json
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from src.rag.embedding_tokenizer import ProviderParityStatus, load_embedding_tokenizer_config
from src.rag.tokenizer_parity import (
    PARITY_SCHEMA_VERSION,
    EmbeddingTokenizerParityReportV1,
    ParityFailureCode,
    ParityProbeResultV1,
    TokenizerParityError,
    build_parity_report,
    load_parity_report,
    parity_content_sha256,
    require_fresh_provider_parity,
    write_parity_report_create_only,
)


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = ROOT / "evaluation" / "golden" / "embedding_tokenizer_parity_probes.v1.json"
SCRIPT_PATH = ROOT / "scripts" / "check_embedding_tokenizer_parity.py"


def _probe_results(*, provider_delta: int | None) -> tuple[ParityProbeResultV1, ...]:
    return tuple(
        ParityProbeResultV1(
            probe_id=f"probe-{index:02d}",
            category="safe_synthetic",
            embedding_input_sha256=f"sha256:{index:064x}",
            offline_tokens=20 + index,
            provider_prompt_tokens=None if provider_delta is None else 20 + index + provider_delta,
            provider_total_tokens=None if provider_delta is None else 20 + index + provider_delta,
            exact_match=None if provider_delta is None else provider_delta == 0,
        )
        for index in range(10)
    )


def _report(
    *,
    captured_at: datetime,
    provider_delta: int | None,
    unavailable_reason: str | None = None,
) -> EmbeddingTokenizerParityReportV1:
    config = load_embedding_tokenizer_config()
    probes = _probe_results(provider_delta=provider_delta)
    offline_total = sum(probe.offline_tokens for probe in probes)
    provider_total = None if provider_delta is None else offline_total + provider_delta
    return build_parity_report(
        run_id=uuid4(),
        captured_at=captured_at,
        region_class="dashscope_public",
        config=config,
        probe_fixture_sha256="sha256:" + "a" * 64,
        submitted_content_sha256=parity_content_sha256(probes),
        probes=probes,
        aggregate_provider_prompt_tokens=provider_total,
        aggregate_provider_total_tokens=provider_total,
        unavailable_reason=unavailable_reason,
    )


def test_parity_fixture_is_ten_structured_safe_probes_without_preassembled_inputs() -> None:
    payload = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "embedding_tokenizer_parity_probes.v1"
    assert len(payload["probes"]) == 10
    assert len({probe["id"] for probe in payload["probes"]}) == 10
    assert all(set(probe) == {"id", "category", "doc_key", "title", "block"} for probe in payload["probes"])
    assert all("embedding_input" not in json.dumps(probe) for probe in payload["probes"])


def test_parity_cli_has_no_caller_preassembled_or_local_envelope_seam() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PolicyEmbeddingInputAssembler" in source
    assert "ParsedBlock(" in source
    assert ".embedding_input" in source
    assert "--input" not in source
    assert "_render_embedding_input" not in source
    assert "embed_documents_with_usage" in source


def test_report_schema_is_frozen_strict_and_safe() -> None:
    assert PARITY_SCHEMA_VERSION == "embedding_tokenizer_parity.v1"
    assert {field.name for field in fields(ParityProbeResultV1)} == {
        "probe_id",
        "category",
        "embedding_input_sha256",
        "offline_tokens",
        "provider_prompt_tokens",
        "provider_total_tokens",
        "exact_match",
    }
    forbidden = {"text", "api_key", "base_url", "raw_response", "path", "exception"}
    assert forbidden.isdisjoint(field.name for field in fields(EmbeddingTokenizerParityReportV1))


def test_unavailable_report_is_create_only_and_never_mutates_prior_bytes(tmp_path: Path) -> None:
    report = _report(
        captured_at=datetime(2026, 8, 11, 6, 30, tzinfo=UTC),
        provider_delta=None,
        unavailable_reason="provider_usage_unavailable",
    )

    report_path = write_parity_report_create_only(report, root=tmp_path)
    original = report_path.read_bytes()

    assert report.provider_parity_status is ProviderParityStatus.UNAVAILABLE
    assert load_parity_report(report_path) == report
    assert (
        report_path == tmp_path / "runs" / report.config_fingerprint.removeprefix("sha256:") / f"{report.run_id}.json"
    )
    with pytest.raises(TokenizerParityError) as exc_info:
        write_parity_report_create_only(report, root=tmp_path)
    assert exc_info.value.code is ParityFailureCode.CREATE_CONFLICT
    assert report_path.read_bytes() == original


def test_mismatched_single_counts_are_quarantined_without_provider_success_claim() -> None:
    report = _report(
        captured_at=datetime(2026, 8, 11, 6, 30, tzinfo=UTC),
        provider_delta=1,
    )

    assert report.provider_parity_status is ProviderParityStatus.QUARANTINED
    assert report.reason_code == "single_count_mismatch"
    assert all(probe.exact_match is False for probe in report.probes)


def test_fresh_gate_rejects_unavailable_quarantined_stale_and_identity_drift(tmp_path: Path) -> None:
    now = datetime(2026, 8, 11, 7, 0, tzinfo=UTC)
    config = load_embedding_tokenizer_config()
    unavailable = _report(
        captured_at=now - timedelta(minutes=5),
        provider_delta=None,
        unavailable_reason="provider_credentials_unavailable",
    )
    unavailable_path = write_parity_report_create_only(unavailable, root=tmp_path / "unavailable")

    with pytest.raises(TokenizerParityError) as exc_info:
        require_fresh_provider_parity(
            unavailable_path,
            config=config,
            expected_probe_fixture_sha256=unavailable.probe_fixture_sha256,
            expected_submitted_content_sha256=unavailable.submitted_content_sha256,
            now=now,
            maximum_age=timedelta(hours=1),
        )
    assert exc_info.value.code is ParityFailureCode.PASSED_REQUIRED

    quarantined = _report(captured_at=now - timedelta(minutes=5), provider_delta=1)
    quarantined_path = write_parity_report_create_only(quarantined, root=tmp_path / "quarantined")
    with pytest.raises(TokenizerParityError) as exc_info:
        require_fresh_provider_parity(
            quarantined_path,
            config=config,
            expected_probe_fixture_sha256=quarantined.probe_fixture_sha256,
            expected_submitted_content_sha256=quarantined.submitted_content_sha256,
            now=now,
            maximum_age=timedelta(hours=1),
        )
    assert exc_info.value.code is ParityFailureCode.PASSED_REQUIRED

    stale = _report(captured_at=now - timedelta(hours=2), provider_delta=None)
    stale_path = write_parity_report_create_only(stale, root=tmp_path / "stale")
    with pytest.raises(TokenizerParityError) as exc_info:
        require_fresh_provider_parity(
            stale_path,
            config=config,
            expected_probe_fixture_sha256=stale.probe_fixture_sha256,
            expected_submitted_content_sha256=stale.submitted_content_sha256,
            now=now,
            maximum_age=timedelta(hours=1),
        )
    assert exc_info.value.code is ParityFailureCode.STALE

    fresh_path = write_parity_report_create_only(unavailable, root=tmp_path / "identity")
    with pytest.raises(TokenizerParityError) as exc_info:
        require_fresh_provider_parity(
            fresh_path,
            config=config,
            expected_probe_fixture_sha256="sha256:" + "b" * 64,
            expected_submitted_content_sha256=unavailable.submitted_content_sha256,
            now=now,
            maximum_age=timedelta(hours=1),
        )
    assert exc_info.value.code is ParityFailureCode.FIXTURE_HASH_MISMATCH


def test_loader_rejects_unknown_fields_and_never_reflects_unsafe_values(tmp_path: Path) -> None:
    report = _report(
        captured_at=datetime(2026, 8, 11, 6, 30, tzinfo=UTC),
        provider_delta=None,
        unavailable_reason="provider_usage_unavailable",
    )
    source_path = write_parity_report_create_only(report, root=tmp_path / "source")
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["raw_response"] = "secret raw provider payload"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TokenizerParityError) as exc_info:
        load_parity_report(invalid_path)

    assert exc_info.value.code is ParityFailureCode.REPORT_INVALID
    assert str(exc_info.value) == ParityFailureCode.REPORT_INVALID.value
