"""Phase 35 replay/eval coverage matrix contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.replay.validators import REPLAY_EVENT_TYPES


MATRIX_PATH = Path("eval/replay/phase35-coverage-matrix.v1.json")
MATRIX_SCHEMA_VERSION = "phase35_replay_coverage_matrix.v1"
PHASE_NAME = "35-replay-and-eval-hardening"
BLOCKING_GATE = "dev-contract"
EVENT_TYPE_POLICY = "no_new_event_types_in_phase35_matrix"
EVENT_STRATEGY = "existing_event_plus_payload_contract"
MATRIX_SELF_TEST_PATH = "tests/replay/test_phase35_coverage_matrix.py"

REQUIRED_BOUNDARIES = {
    "trusted_context_projection",
    "intent_policy",
    "slot_policy",
    "memory_load_policy",
    "memory_write_policy",
    "tool_visibility",
    "tool_runtime_auth",
    "business_fact_read_scope_freshness",
    "rag_validation",
    "claim_verification",
    "risk_decision",
    "approval_lifecycle",
    "action_draft",
}
REQUIRED_GATE_LEVELS = {"dev-contract", "release", "monitoring"}
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
APPROVED_PYTEST_ENTRYPOINTS = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest",
    "uv run pytest",
    ".venv/bin/pytest",
    ".venv/bin/python -m pytest",
)
PYTEST_ENTRYPOINT_RE = re.compile(
    r"(^|[\s`;&|])"
    r"(?P<entrypoint>"
    r"(?:UV_CACHE_DIR=\S+\s+)?uv\s+run\s+pytest"
    r"|\.venv/bin/pytest"
    r"|\.venv/bin/python\s+-m\s+pytest"
    r"|python\s+-m\s+pytest"
    r"|pytest"
    r")(?=\s|$)"
)


class Phase35DecisionAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assertion_id: str = Field(min_length=1)
    test_path: str = Field(min_length=1)
    assertion_type: str = Field(min_length=1)
    asserts: str = Field(min_length=1)


class Phase35CoverageRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boundary: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    replay_events: list[str]
    trace_projection: str = Field(min_length=1)
    eval_gate_level: str = Field(min_length=1)
    forbidden_behaviors: list[str]
    acceptance_tests: list[str]
    decision_assertions: list[Phase35DecisionAssertion]
    event_strategy: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class Phase35CoverageMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    blocking_gate: str = Field(min_length=1)
    event_type_policy: str = Field(min_length=1)
    gate_levels: list[str]
    rows: list[Phase35CoverageRow]


def load_phase35_matrix(path: Path = MATRIX_PATH) -> Phase35CoverageMatrix:
    """Load the Phase 35 matrix artifact from disk."""

    return Phase35CoverageMatrix.model_validate_json(path.read_text(encoding="utf-8"))


def validate_phase35_matrix(matrix: Phase35CoverageMatrix) -> list[str]:
    """Return deterministic contract errors for the Phase 35 matrix."""

    errors: list[str] = []
    _validate_matrix_metadata(matrix, errors)
    _validate_boundary_set(matrix, errors)

    for row in matrix.rows:
        _validate_row(row, matrix.gate_levels, errors)

    return errors


def _validate_matrix_metadata(matrix: Phase35CoverageMatrix, errors: list[str]) -> None:
    if matrix.schema_version != MATRIX_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MATRIX_SCHEMA_VERSION!r}")
    if matrix.phase != PHASE_NAME:
        errors.append(f"phase must be {PHASE_NAME!r}")
    if matrix.blocking_gate != BLOCKING_GATE:
        errors.append(f"blocking_gate must be {BLOCKING_GATE!r}")
    if matrix.event_type_policy != EVENT_TYPE_POLICY:
        errors.append(f"event_type_policy must be {EVENT_TYPE_POLICY!r}")

    gate_levels = set(matrix.gate_levels)
    missing = REQUIRED_GATE_LEVELS - gate_levels
    unknown = gate_levels - REQUIRED_GATE_LEVELS
    for gate in sorted(missing):
        errors.append(f"missing required gate level {gate!r}")
    for gate in sorted(unknown):
        errors.append(f"unknown gate level {gate!r}")
    _validate_no_unscoped_pytest_entrypoint(matrix.gate_levels, "gate_levels", errors)


def _validate_boundary_set(matrix: Phase35CoverageMatrix, errors: list[str]) -> None:
    boundaries = [row.boundary for row in matrix.rows]
    boundary_set = set(boundaries)
    for boundary in sorted(REQUIRED_BOUNDARIES - boundary_set):
        errors.append(f"missing required boundary {boundary!r}")
    for boundary in sorted(boundary_set - REQUIRED_BOUNDARIES):
        errors.append(f"unknown boundary {boundary!r}")

    duplicates = sorted({boundary for boundary in boundaries if boundaries.count(boundary) > 1})
    for boundary in duplicates:
        errors.append(f"duplicate boundary {boundary!r}")


def _validate_row(row: Phase35CoverageRow, matrix_gate_levels: list[str], errors: list[str]) -> None:
    prefix = f"{row.boundary}: "

    if row.eval_gate_level not in REQUIRED_GATE_LEVELS or row.eval_gate_level not in matrix_gate_levels:
        errors.append(f"{prefix}unknown gate level {row.eval_gate_level!r}")
    if row.event_strategy != EVENT_STRATEGY:
        errors.append(f"{prefix}event_strategy must be {EVENT_STRATEGY!r}")
    if not row.replay_events:
        errors.append(f"{prefix}empty replay_events")
    for event_type in row.replay_events:
        if event_type not in REPLAY_EVENT_TYPES:
            errors.append(f"{prefix}unregistered replay event {event_type!r}")
    if not row.forbidden_behaviors:
        errors.append(f"{prefix}empty forbidden_behaviors")
    if not row.acceptance_tests:
        errors.append(f"{prefix}empty acceptance_tests")
    if not row.decision_assertions:
        errors.append(f"{prefix}empty decision_assertions")

    acceptance_tests = set(row.acceptance_tests)
    assertion_ids = {assertion.assertion_id for assertion in row.decision_assertions}
    required_assertion = REQUIRED_LEFT_HALF_ASSERTIONS.get(row.boundary)
    if required_assertion and required_assertion not in assertion_ids:
        errors.append(f"{prefix}required left-half assertion id {required_assertion!r} is missing")

    for assertion in row.decision_assertions:
        if assertion.assertion_type not in ALLOWED_ASSERTION_TYPES:
            errors.append(f"{prefix}unknown assertion_type {assertion.assertion_type!r}")
        if assertion.test_path not in acceptance_tests:
            errors.append(f"{prefix}decision assertion test_path {assertion.test_path!r} is absent from acceptance_tests")
        if not assertion.asserts.strip():
            errors.append(f"{prefix}decision assertion {assertion.assertion_id!r} has empty asserts")
        if required_assertion == assertion.assertion_id and assertion.test_path == MATRIX_SELF_TEST_PATH:
            errors.append(f"{prefix}{assertion.assertion_id!r} must point to a focused Phase 35 test")

    _validate_no_unscoped_pytest_entrypoint(row.model_dump(mode="python"), row.boundary, errors)


def _validate_no_unscoped_pytest_entrypoint(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, str):
        if _contains_unscoped_pytest_entrypoint(value):
            errors.append(f"{location}: unscoped pytest entrypoint {value!r}")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_no_unscoped_pytest_entrypoint(child, f"{location}.{key}", errors)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_no_unscoped_pytest_entrypoint(child, f"{location}[{index}]", errors)


def _contains_unscoped_pytest_entrypoint(value: str) -> bool:
    if "pytest" not in value:
        return False
    return any(
        not _is_approved_pytest_entrypoint(match.group("entrypoint"))
        for match in PYTEST_ENTRYPOINT_RE.finditer(value)
    )


def _is_approved_pytest_entrypoint(entrypoint: str) -> bool:
    normalized = " ".join(entrypoint.strip().split())
    return normalized in APPROVED_PYTEST_ENTRYPOINTS


def dump_phase35_matrix_json(matrix: Phase35CoverageMatrix) -> str:
    """Render deterministic matrix JSON for test diagnostics and future tooling."""

    return json.dumps(matrix.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
