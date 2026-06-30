from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from src.replay.phase35_matrix import (
    REQUIRED_BOUNDARIES,
    Phase35CoverageMatrix,
    load_phase35_matrix,
    validate_phase35_matrix,
)
from src.replay.validators import REPLAY_EVENT_TYPES


MATRIX_PATH = Path("eval/replay/phase35-coverage-matrix.v1.json")
MATRIX_SELF_TEST = "tests/replay/test_phase35_coverage_matrix.py"
ROADMAP_PATH = Path(".planning/ROADMAP.md")
PHASE35_PLAN_DIR = Path(".planning/phases/35-replay-and-eval-hardening")
PHASE35_PLAN_FILES = tuple(PHASE35_PLAN_DIR / f"35-{index:02d}-PLAN.md" for index in range(1, 7))
PHASE35_SCAN_FILES = (*PHASE35_PLAN_FILES, MATRIX_PATH)
PLAN_PROGRESS_RE = re.compile(r"\*\*Plans:\*\*\s+(?P<complete>\d+)/6 plans complete")

EXPECTED_ROW_FIELDS = {
    "boundary",
    "owner",
    "replay_events",
    "trace_projection",
    "eval_gate_level",
    "forbidden_behaviors",
    "acceptance_tests",
    "decision_assertions",
    "event_strategy",
    "notes",
}
ALLOWED_ASSERTION_TYPES = {
    "replay_event_payload",
    "trace_projection",
    "api_projection",
    "eval_manifest",
}
REQUIRED_LEFT_HALF_ASSERTIONS = {
    "trusted_context_projection": "trusted_context_projection_replay_context",
    "intent_policy": "intent_policy_effective_route_trace",
    "slot_policy": "slot_policy_inheritance_trace",
    "memory_load_policy": "memory_load_scope_trace",
    "business_fact_read_scope_freshness": "business_fact_scope_freshness_proof",
    "risk_decision": "risk_decision_action_path_trace",
}
DETERMINISTIC_DEV_CONTRACT_BOUNDARIES = {
    "trusted_context_projection",
    "slot_policy",
    "memory_load_policy",
    "tool_visibility",
    "tool_runtime_auth",
    "business_fact_read_scope_freshness",
    "rag_validation",
    "claim_verification",
    "risk_decision",
    "approval_lifecycle",
    "action_draft",
}
APPROVED_PYTEST_ENTRYPOINTS = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest",
    "uv run pytest",
    ".venv/bin/pytest",
    ".venv/bin/python -m pytest",
)
PYTEST_COMMAND_START_RE = re.compile(r"^(?:UV_CACHE_DIR=\S+\s+)?(?:uv\s+run\s+pytest|\.venv/bin/pytest|\.venv/bin/python\s+-m\s+pytest|python\s+-m\s+pytest|pytest)\b")
INLINE_CODE_RE = re.compile(r"`([^`]*pytest[^`]*)`")
AUTOMATED_XML_RE = re.compile(r"<automated>([^<]*pytest[^<]*)</automated>")


def test_phase35_matrix_covers_required_platform_boundaries() -> None:
    matrix = load_phase35_matrix()

    assert validate_phase35_matrix(matrix) == []
    assert matrix.schema_version == "phase35_replay_coverage_matrix.v1"
    assert matrix.phase == "35-replay-and-eval-hardening"
    assert matrix.blocking_gate == "dev-contract"
    assert matrix.event_type_policy == "no_new_event_types_in_phase35_matrix"
    assert set(matrix.gate_levels) == {"dev-contract", "release", "monitoring"}
    assert {row.boundary for row in matrix.rows} == REQUIRED_BOUNDARIES


def test_phase35_matrix_rows_are_replay_contracts_not_documentation_only() -> None:
    raw = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    matrix = Phase35CoverageMatrix.model_validate(raw)

    for raw_row, row in zip(raw["rows"], matrix.rows, strict=True):
        assert set(raw_row) == EXPECTED_ROW_FIELDS
        assert row.event_strategy == "existing_event_plus_payload_contract"
        assert set(row.replay_events) <= REPLAY_EVENT_TYPES
        assert row.trace_projection
        assert row.eval_gate_level in matrix.gate_levels
        assert row.forbidden_behaviors
        assert row.acceptance_tests
        assert row.decision_assertions

        for assertion in row.decision_assertions:
            assert assertion.assertion_type in ALLOWED_ASSERTION_TYPES
            assert assertion.test_path in row.acceptance_tests
            assert assertion.asserts


def test_phase35_matrix_uses_registered_events_and_existing_event_strategy() -> None:
    matrix = load_phase35_matrix()

    assert validate_phase35_matrix(matrix) == []
    for row in matrix.rows:
        assert set(row.replay_events) <= REPLAY_EVENT_TYPES
        assert row.event_strategy == "existing_event_plus_payload_contract"
        assert any(test.endswith(".py") for test in row.acceptance_tests)
        assert row.decision_assertions


def test_phase35_matrix_distinguishes_dev_release_and_monitoring_gates() -> None:
    matrix = load_phase35_matrix()
    rows = {row.boundary: row for row in matrix.rows}
    gate_levels = {row.eval_gate_level for row in matrix.rows}

    assert {"dev-contract", "release", "monitoring"} <= gate_levels
    for boundary in DETERMINISTIC_DEV_CONTRACT_BOUNDARIES:
        assert rows[boundary].eval_gate_level == "dev-contract"


def test_phase35_roadmap_keeps_six_plan_shape() -> None:
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    if "### Phase 35: Replay and Eval Hardening" not in roadmap:
        pytest.skip("Phase 35 planning docs are archived outside the active .planning roadmap.")
    phase35_section = roadmap.split("### Phase 35: Replay and Eval Hardening", maxsplit=1)[1]
    phase35_section = phase35_section.split("## Backlog", maxsplit=1)[0]

    progress = PLAN_PROGRESS_RE.search(phase35_section)
    assert progress is not None
    assert int(progress.group("complete")) >= 0

    expected_plan_names = [f"35-{index:02d}-PLAN.md" for index in range(1, 7)]
    assert re.findall(r"35-\d{2}-PLAN\.md", phase35_section) == expected_plan_names
    for plan_file in expected_plan_names:
        assert plan_file in phase35_section
    assert "35-06-PLAN.md" in phase35_section
    assert "35-07-PLAN.md" not in phase35_section


def test_phase35_plan_and_matrix_files_have_approved_entrypoint_scan() -> None:
    if not PHASE35_PLAN_DIR.exists():
        pytest.skip("Phase 35 plan files are archived outside the active .planning directory.")
    violations: list[str] = []
    for path in PHASE35_SCAN_FILES:
        assert path.exists()
        for snippet in _pytest_command_snippets(path):
            if not any(entrypoint in snippet for entrypoint in APPROVED_PYTEST_ENTRYPOINTS):
                violations.append(f"{path}:{snippet}")

    assert violations == []


def test_phase35_matrix_has_focused_left_half_decision_assertions() -> None:
    matrix = load_phase35_matrix()
    rows = {row.boundary: row for row in matrix.rows}

    for boundary, assertion_id in REQUIRED_LEFT_HALF_ASSERTIONS.items():
        assertions = {assertion.assertion_id: assertion for assertion in rows[boundary].decision_assertions}
        assert assertion_id in assertions
        assert assertions[assertion_id].test_path != MATRIX_SELF_TEST


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda raw: raw["rows"].pop(),
            "missing required boundary",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("eval_gate_level", "experimental"),
            "unknown gate level",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("replay_events", []),
            "empty replay_events",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("replay_events", ["phase35_new_event_type"]),
            "unregistered replay event",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("forbidden_behaviors", []),
            "empty forbidden_behaviors",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("acceptance_tests", []),
            "empty acceptance_tests",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("decision_assertions", []),
            "empty decision_assertions",
        ),
        (
            lambda raw: _first_assertion(raw).__setitem__(
                "test_path", "tests/replay/test_phase35_missing_contract.py"
            ),
            "decision assertion test_path",
        ),
        (
            lambda raw: _required_assertion(raw, "trusted_context_projection").__setitem__(
                "test_path", MATRIX_SELF_TEST
            ),
            "must point to a focused Phase 35 test",
        ),
        (
            lambda raw: _first_row(raw).__setitem__("event_strategy", "new_event_type"),
            "event_strategy",
        ),
        (
            lambda raw: _first_row(raw)["acceptance_tests"].append("pytest tests/replay/test_leak.py"),
            "unscoped pytest entrypoint",
        ),
        (
            lambda raw: _first_row(raw).__setitem__(
                "notes",
                (
                    "Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_ok.py` before "
                    "`pytest tests/replay/test_leak.py`"
                ),
            ),
            "unscoped pytest entrypoint",
        ),
        (
            lambda raw: _first_row(raw).__setitem__(
                "notes",
                (
                    "Run `uv run pytest tests/replay/test_ok.py && "
                    "python -m pytest tests/replay/test_leak.py`"
                ),
            ),
            "unscoped pytest entrypoint",
        ),
    ],
)
def test_phase35_matrix_validator_reports_contract_drift(
    mutator: Any,
    expected: str,
) -> None:
    raw = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    mutator(raw)
    matrix = Phase35CoverageMatrix.model_validate(raw)

    errors = validate_phase35_matrix(matrix)

    assert any(expected in error for error in errors)


def _first_row(raw: dict[str, Any]) -> dict[str, Any]:
    return raw["rows"][0]


def _first_assertion(raw: dict[str, Any]) -> dict[str, Any]:
    return _first_row(raw)["decision_assertions"][0]


def _required_assertion(raw: dict[str, Any], boundary: str) -> dict[str, Any]:
    row = next(row for row in raw["rows"] if row["boundary"] == boundary)
    assertion_id = REQUIRED_LEFT_HALF_ASSERTIONS[boundary]
    return next(assertion for assertion in row["decision_assertions"] if assertion["assertion_id"] == assertion_id)


def _pytest_command_snippets(path: Path) -> list[str]:
    snippets: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if PYTEST_COMMAND_START_RE.match(stripped):
            snippets.append(stripped)
        for match in INLINE_CODE_RE.finditer(line):
            snippet = match.group(1).strip()
            if PYTEST_COMMAND_START_RE.match(snippet):
                snippets.append(snippet)
        for match in AUTOMATED_XML_RE.finditer(line):
            snippet = match.group(1).strip()
            if PYTEST_COMMAND_START_RE.match(snippet):
                snippets.append(snippet)
    return [snippet for snippet in snippets if "pytest" in snippet]
