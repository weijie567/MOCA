"""Phase 35 replay/eval dev-contract manifest contract."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.replay.phase35_matrix import load_phase35_matrix, validate_phase35_matrix


MANIFEST_PATH = Path("eval/replay/dev-contract-manifest.v1.json")
MATRIX_PATH = Path("eval/replay/phase35-coverage-matrix.v1.json")
PHASE_NAME = "35-replay-and-eval-hardening"
SCHEMA_VERSION = "phase35_replay_dev_contract_manifest.v1"

REQUIRED_DEV_CONTRACT_CATEGORIES = {
    "schema_validity",
    "platform_event_coverage",
    "event_order",
    "terminal_replay_timelines",
    "redaction",
    "owner_admin_only_permissions",
    "cross_tenant_cross_merchant_negatives",
    "forbidden_behavior",
    "release_monitoring_manifest_format",
}
REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS = {
    "raw_prompt_leak",
    "raw_tool_payload_leak",
    "pii_leak",
    "action_raw_payload_leak",
    "owner_admin_only_bypass",
    "cross_tenant_replay_access",
    "cross_merchant_replay_access",
    "unsupported_claim_to_action_bound_path",
    "no_evidence_to_deterministic_action_recommendation",
    "unsafe_action_path",
    "stale_business_fact_ref_accepted",
    "wrong_scope_business_fact_ref_accepted",
    "invalid_scope_evidence_accepted",
    "approval_payload_hash_mismatch_creates_action_draft",
}
REQUIRED_NON_BLOCKING_GATE_PATHS = {
    "eval/replay/release-gate.v1.json": "release",
    "eval/replay/monitoring-gate.v1.json": "monitoring",
}
APPROVED_PYTEST_ENTRYPOINTS = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest ",
    "uv run pytest ",
    ".venv/bin/pytest ",
    ".venv/bin/python -m pytest ",
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
ALLOWED_TEST_ROOTS = {
    "tests/replay/",
    "tests/eval/",
    "tests/architecture/",
    "tests/agent/",
    "tests/actions/",
}


class ForbiddenBehaviorCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    gate_level: Literal["dev-contract"]
    blocking: bool
    source_decisions: list[str]
    description: str = Field(min_length=1)
    expected_guard: str = Field(min_length=1)
    test_paths: list[str]


class NonBlockingGateRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    gate_level: Literal["release", "monitoring"]
    schema_version: str = Field(min_length=1)
    blocking: str = Field(min_length=1)
    failure_impact: str = Field(min_length=1)
    phase35_blocking: bool


class Phase35DevContractManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["phase35_replay_dev_contract_manifest.v1"]
    phase: Literal["35-replay-and-eval-hardening"]
    gate_level: Literal["dev-contract"]
    blocking: Literal["phase_exit"]
    failure_impact: Literal["block_phase_35_verification"]
    coverage_matrix_path: str = Field(min_length=1)
    coverage_matrix_hash: str = Field(min_length=1)
    required_gate_categories: list[str]
    forbidden_behaviors: list[ForbiddenBehaviorCase]
    required_test_commands: list[str]
    non_blocking_gate_refs: list[NonBlockingGateRef]


def load_dev_contract_manifest(path: Path = MANIFEST_PATH) -> Phase35DevContractManifest:
    """Load the Phase 35 dev-contract manifest from disk."""

    return Phase35DevContractManifest.model_validate_json(path.read_text(encoding="utf-8"))


def compute_file_sha256(path: Path) -> str:
    """Return the project-standard SHA-256 digest string for an artifact."""

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dev_contract_manifest(manifest: Phase35DevContractManifest) -> list[str]:
    """Return deterministic validation errors for the Phase 35 dev-contract manifest."""

    errors: list[str] = []
    _validate_coverage_matrix_ref(manifest, errors)
    _validate_required_categories(manifest, errors)
    _validate_forbidden_behaviors(manifest, errors)
    _validate_required_commands(manifest, errors)
    _validate_non_blocking_gate_refs(manifest, errors)
    return errors


def _validate_coverage_matrix_ref(manifest: Phase35DevContractManifest, errors: list[str]) -> None:
    if manifest.coverage_matrix_path != str(MATRIX_PATH):
        errors.append(f"coverage_matrix_path must be {MATRIX_PATH}")
        return

    if not MATRIX_PATH.exists():
        errors.append(f"coverage_matrix_path does not exist: {MATRIX_PATH}")
        return

    expected_hash = compute_file_sha256(MATRIX_PATH)
    if manifest.coverage_matrix_hash != expected_hash:
        errors.append(f"coverage_matrix_hash does not match {MATRIX_PATH}")

    matrix_errors = validate_phase35_matrix(load_phase35_matrix(MATRIX_PATH))
    errors.extend(f"coverage_matrix: {error}" for error in matrix_errors)


def _validate_required_categories(manifest: Phase35DevContractManifest, errors: list[str]) -> None:
    categories = manifest.required_gate_categories
    category_set = set(categories)
    for category in sorted(REQUIRED_DEV_CONTRACT_CATEGORIES - category_set):
        errors.append(f"missing required gate category {category!r}")
    for category in sorted(category_set - REQUIRED_DEV_CONTRACT_CATEGORIES):
        errors.append(f"unknown required gate category {category!r}")
    for category in sorted({category for category in categories if categories.count(category) > 1}):
        errors.append(f"duplicate required gate category {category!r}")


def _validate_forbidden_behaviors(manifest: Phase35DevContractManifest, errors: list[str]) -> None:
    cases = manifest.forbidden_behaviors
    case_ids = [case.case_id for case in cases]
    case_id_set = set(case_ids)
    for case_id in sorted(REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS - case_id_set):
        errors.append(f"missing forbidden behavior case {case_id!r}")
    for case_id in sorted(case_id_set - REQUIRED_FORBIDDEN_BEHAVIOR_CASE_IDS):
        errors.append(f"unknown forbidden behavior case {case_id!r}")
    for case_id in sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1}):
        errors.append(f"duplicate forbidden behavior case {case_id!r}")

    for case in cases:
        prefix = f"{case.case_id}: "
        if not case.blocking:
            errors.append(f"{prefix}dev-contract case must be blocking")
        if case.category not in REQUIRED_DEV_CONTRACT_CATEGORIES:
            errors.append(f"{prefix}unknown gate category {case.category!r}")
        if not case.source_decisions:
            errors.append(f"{prefix}empty source_decisions")
        if not case.test_paths:
            errors.append(f"{prefix}empty test_paths")
        for test_path in case.test_paths:
            _validate_test_path(test_path, prefix, errors)


def _validate_test_path(test_path: str, prefix: str, errors: list[str]) -> None:
    if not any(test_path.startswith(root) for root in ALLOWED_TEST_ROOTS):
        errors.append(f"{prefix}test_path {test_path!r} is outside approved Phase 35 test roots")
    if not Path(test_path).exists():
        errors.append(f"{prefix}test_path does not exist: {test_path}")


def _validate_required_commands(manifest: Phase35DevContractManifest, errors: list[str]) -> None:
    if not manifest.required_test_commands:
        errors.append("required_test_commands is empty")
    for command in manifest.required_test_commands:
        if not command.startswith(APPROVED_PYTEST_ENTRYPOINTS):
            errors.append(f"required_test_commands contains unapproved entrypoint: {command!r}")
        if _contains_bare_pytest(command):
            errors.append(f"required_test_commands contains bare pytest entrypoint: {command!r}")


def _contains_bare_pytest(command: str) -> bool:
    return any(
        not _is_approved_pytest_entrypoint(match.group("entrypoint"))
        for match in PYTEST_ENTRYPOINT_RE.finditer(command)
    )


def _is_approved_pytest_entrypoint(entrypoint: str) -> bool:
    normalized = " ".join(entrypoint.strip().split())
    return normalized in {prefix.strip() for prefix in APPROVED_PYTEST_ENTRYPOINTS}


def _validate_non_blocking_gate_refs(manifest: Phase35DevContractManifest, errors: list[str]) -> None:
    refs_by_path = {ref.path: ref for ref in manifest.non_blocking_gate_refs}
    ref_paths = set(refs_by_path)
    required_paths = set(REQUIRED_NON_BLOCKING_GATE_PATHS)
    for path in sorted(required_paths - ref_paths):
        errors.append(f"missing non_blocking_gate_refs path {path!r}")
    for path in sorted(ref_paths - required_paths):
        errors.append(f"unknown non_blocking_gate_refs path {path!r}")

    for path, expected_gate_level in REQUIRED_NON_BLOCKING_GATE_PATHS.items():
        ref = refs_by_path.get(path)
        if ref is None:
            continue
        _validate_non_blocking_gate_ref(ref, expected_gate_level, errors)


def _validate_non_blocking_gate_ref(
    ref: NonBlockingGateRef,
    expected_gate_level: str,
    errors: list[str],
) -> None:
    prefix = f"{ref.path}: "
    if ref.gate_level != expected_gate_level:
        errors.append(f"{prefix}gate_level must be {expected_gate_level!r}")
    if ref.blocking == "phase_exit" or ref.phase35_blocking:
        errors.append(f"{prefix}must not block Phase 35 exit")

    path = Path(ref.path)
    if not path.exists():
        errors.append(f"{prefix}referenced manifest does not exist")
        return

    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact.get("schema_version") != ref.schema_version:
        errors.append(f"{prefix}schema_version does not match referenced manifest")
    if artifact.get("gate_level") != ref.gate_level:
        errors.append(f"{prefix}gate_level does not match referenced manifest")
    if artifact.get("blocking") != ref.blocking:
        errors.append(f"{prefix}blocking does not match referenced manifest")
    if artifact.get("failure_impact") != ref.failure_impact:
        errors.append(f"{prefix}failure_impact does not match referenced manifest")
    if artifact.get("blocking") == "phase_exit":
        errors.append(f"{prefix}referenced manifest incorrectly blocks Phase 35 exit")
    _validate_non_blocking_gate_semantics(ref, artifact, errors)


def _validate_non_blocking_gate_semantics(
    ref: NonBlockingGateRef,
    artifact: dict[str, Any],
    errors: list[str],
) -> None:
    prefix = f"{ref.path}: "
    if ref.gate_level == "release":
        if artifact.get("default_gate_status") != "statistical_gate_not_demonstrated":
            errors.append(f"{prefix}release gate must record statistical_gate_not_demonstrated")
        return

    allowed_statuses = set(artifact.get("allowed_statuses", []))
    if allowed_statuses != {"pending", "not_applicable", "sample_only"}:
        errors.append(f"{prefix}monitoring allowed_statuses must be pending/not_applicable/sample_only")
    metrics = artifact.get("metrics", [])
    for metric in metrics:
        if metric.get("phase35_blocking") is not False:
            errors.append(f"{prefix}monitoring metric {metric.get('metric_id')!r} must be non-blocking")
