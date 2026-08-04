from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SMOKE_CASES = Path("eval/replay/release-smoke-cases.v1.json")
RELEASE_GATE = Path("eval/replay/release-gate.v1.json")
MONITORING_GATE = Path("eval/replay/monitoring-gate.v1.json")
COVERAGE_MATRIX = Path("eval/replay/phase35-coverage-matrix.v1.json")

RELEASE_AREAS = {
    "intent_hard_negatives",
    "rag_claim_support",
    "approval_action_safety",
}
MONITORING_METRICS = {
    "replay_completeness",
    "drift",
    "false_negative_trend",
    "tool_deny_reasons",
    "rag_no_evidence_trend",
    "memory_write_quality",
}
ALLOWED_MONITORING_STATUSES = {"pending", "not_applicable", "sample_only"}
APPROVED_MANIFEST_COMMAND = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_release_monitoring_manifests.py -q --tb=short"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_release_smoke_cases_are_limited_three_area_artifact():
    artifact = _load_json(SMOKE_CASES)

    assert artifact["schema_version"] == "phase35_replay_release_smoke_cases.v1"
    assert artifact["dataset_version"] == "phase35-replay-release-smoke.v1"
    assert artifact["case_count"] == 3
    assert len(artifact["cases"]) == 3

    cases_by_area = {case["release_area"]: case for case in artifact["cases"]}
    assert set(cases_by_area) == RELEASE_AREAS
    for release_area, case in cases_by_area.items():
        assert case["case_id"].startswith(f"phase35_release_smoke_{release_area}")
        assert case["fixture_kind"] == "limited_smoke_reference"
        assert case["expected_gate_level"] == "release"
        assert case["expected_status"] == "smoke_only"
        assert case["source_boundary"]
        assert case["coverage_gap"]
        assert case["statistical_evidence"] == "not_release_scale_evidence"


def test_release_gate_references_smoke_dataset_and_coverage_matrix_hashes():
    manifest = _load_json(RELEASE_GATE)

    assert manifest["schema_version"] == "phase35_replay_release_gate.v1"
    assert manifest["gate_level"] == "release"
    assert manifest["blocking"] == "release_not_phase35_exit"
    assert manifest["failure_impact"] == "block_replay_eval_release_not_phase_35_exit"
    assert manifest["dataset_version"] == "phase35-replay-release-smoke.v1"
    assert manifest["dataset_path"] == str(SMOKE_CASES)
    assert manifest["dataset_hash"] == _sha256(SMOKE_CASES)
    assert manifest["dataset_size"] == 3
    assert manifest["coverage_manifest_path"] == str(COVERAGE_MATRIX)
    assert manifest["coverage_manifest_hash"] == _sha256(COVERAGE_MATRIX)
    assert manifest["command_entrypoint"] == APPROVED_MANIFEST_COMMAND
    assert manifest["default_gate_status"] == "statistical_gate_not_demonstrated"
    assert manifest["coverage_status"] == "incomplete"


def test_release_metrics_record_sample_gaps_without_statistical_claims():
    manifest = _load_json(RELEASE_GATE)
    smoke = _load_json(SMOKE_CASES)
    smoke_case_ids = {case["release_area"]: case["case_id"] for case in smoke["cases"]}

    metrics_by_id = {metric["metric_id"]: metric for metric in manifest["metrics"]}
    assert set(metrics_by_id) == RELEASE_AREAS
    for release_area, metric in metrics_by_id.items():
        assert metric["gate_status"] == "statistical_gate_not_demonstrated"
        assert metric["required_min_n"] > metric["smoke_n"]
        assert metric["smoke_n"] == 1
        assert metric["statistical_n"] == 0
        assert metric["smoke_case_ids"] == [smoke_case_ids[release_area]]
        assert set(metric["gap_reasons"]) <= {
            "release_scale_sample_size_not_demonstrated",
            "coverage_gap_recorded",
        }
        assert "release_scale_sample_size_not_demonstrated" in metric["gap_reasons"]


def test_monitoring_gate_metric_schema_and_status_values():
    manifest = _load_json(MONITORING_GATE)

    assert manifest["schema_version"] == "phase35_replay_monitoring_gate.v1"
    assert manifest["gate_level"] == "monitoring"
    assert manifest["blocking"] == "monitoring_not_phase35_exit"
    assert manifest["failure_impact"] == "trigger_review_or_degrade_not_phase_35_exit"
    assert manifest["command_entrypoint"] == APPROVED_MANIFEST_COMMAND

    metrics_by_id = {metric["metric_id"]: metric for metric in manifest["metrics"]}
    assert set(metrics_by_id) == MONITORING_METRICS
    observed_statuses = {metric["status"] for metric in metrics_by_id.values()}
    assert observed_statuses <= ALLOWED_MONITORING_STATUSES
    assert "sample_only" in observed_statuses

    for metric in metrics_by_id.values():
        assert metric["status"] in ALLOWED_MONITORING_STATUSES
        assert metric["metric_name"]
        assert metric["description"]
        assert metric["gate_semantics"]
        assert metric["phase35_blocking"] is False
