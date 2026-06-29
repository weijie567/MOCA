from __future__ import annotations

import json
from pathlib import Path

from src.replay.phase35_eval_manifest import (
    REQUIRED_DEV_CONTRACT_CATEGORIES,
    REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS,
    compute_file_sha256,
    load_dev_contract_manifest,
    validate_dev_contract_manifest,
)


MANIFEST = Path("eval/replay/dev-contract-manifest.v1.json")
COVERAGE_MATRIX = Path("eval/replay/phase35-coverage-matrix.v1.json")
RELEASE_GATE = Path("eval/replay/release-gate.v1.json")
MONITORING_GATE = Path("eval/replay/monitoring-gate.v1.json")
APPROVED_COMMAND_PREFIXES = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest ",
    "uv run pytest ",
    ".venv/bin/pytest ",
    ".venv/bin/python -m pytest ",
)


def _load_raw(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_dev_contract_manifest_is_schema_valid_and_phase_exit_blocking():
    manifest = load_dev_contract_manifest(MANIFEST)

    assert manifest.schema_version == "phase35_replay_dev_contract_manifest.v1"
    assert manifest.phase == "35-replay-and-eval-hardening"
    assert manifest.gate_level == "dev-contract"
    assert manifest.blocking == "phase_exit"
    assert manifest.failure_impact == "block_phase_35_verification"
    assert validate_dev_contract_manifest(manifest) == []


def test_manifest_references_phase35_coverage_matrix_with_hash():
    manifest = load_dev_contract_manifest(MANIFEST)

    assert manifest.coverage_matrix_path == str(COVERAGE_MATRIX)
    assert manifest.coverage_matrix_hash == compute_file_sha256(COVERAGE_MATRIX)

    raw = _load_raw(MANIFEST)
    assert raw["coverage_matrix_hash"].startswith("sha256:")


def test_manifest_includes_all_deterministic_forbidden_behavior_cases():
    manifest = load_dev_contract_manifest(MANIFEST)
    cases_by_id = {case.case_id: case for case in manifest.forbidden_behaviors}

    assert set(cases_by_id) == REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS
    assert {
        "raw_prompt_leak",
        "unsupported_claim_to_action_bound_path",
        "approval_payload_hash_mismatch_creates_action_draft",
    } <= set(cases_by_id)

    for case_id, case in cases_by_id.items():
        assert case.gate_level == "dev-contract", case_id
        assert case.blocking is True, case_id
        assert case.test_paths, case_id
        for test_path in case.test_paths:
            assert Path(test_path).exists(), f"{case_id}: {test_path}"


def test_required_gate_categories_match_phase35_dev_contract_decisions():
    manifest = load_dev_contract_manifest(MANIFEST)

    assert set(manifest.required_gate_categories) == REQUIRED_DEV_CONTRACT_CATEGORIES
    assert len(manifest.required_gate_categories) == len(REQUIRED_DEV_CONTRACT_CATEGORIES)
    assert "release_monitoring_manifest_format" in manifest.required_gate_categories


def test_release_and_monitoring_gates_are_manifest_format_refs_not_phase35_blockers():
    manifest = load_dev_contract_manifest(MANIFEST)
    refs_by_path = {ref.path: ref for ref in manifest.non_blocking_gate_refs}

    assert set(refs_by_path) == {str(RELEASE_GATE), str(MONITORING_GATE)}
    assert refs_by_path[str(RELEASE_GATE)].gate_level == "release"
    assert refs_by_path[str(MONITORING_GATE)].gate_level == "monitoring"

    release = _load_raw(RELEASE_GATE)
    monitoring = _load_raw(MONITORING_GATE)
    assert release["default_gate_status"] == "statistical_gate_not_demonstrated"
    assert release["blocking"] != "phase_exit"
    assert monitoring["blocking"] != "phase_exit"
    assert all(metric["phase35_blocking"] is False for metric in monitoring["metrics"])


def test_required_commands_use_moca_approved_project_entrypoints():
    manifest = load_dev_contract_manifest(MANIFEST)

    assert manifest.required_test_commands
    for command in manifest.required_test_commands:
        assert command.startswith(APPROVED_COMMAND_PREFIXES), command
        assert " python -m pytest" not in command
        assert not command.startswith("pytest ")


def test_stale_coverage_matrix_hash_fails_validation():
    manifest = load_dev_contract_manifest(MANIFEST)
    stale = manifest.model_copy(update={"coverage_matrix_hash": "sha256:stale"})

    assert "coverage_matrix_hash does not match eval/replay/phase35-coverage-matrix.v1.json" in (
        validate_dev_contract_manifest(stale)
    )
