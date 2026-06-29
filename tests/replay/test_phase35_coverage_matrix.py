from __future__ import annotations

import json
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
