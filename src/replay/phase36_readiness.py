"""Strict Phase 36 trace/replay readiness artifact contract."""

from __future__ import annotations

import json
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


READINESS_SCHEMA_VERSION = "phase36_trace_replay_readiness.v1"
PHASE36_NAME = "36-merchant-scope-db-hardening-role-cleanup"
PHASE36_READINESS_PATH = Path("eval/replay/phase36-readiness.v1.json")

Phase36ReadinessResult = Literal[
    "ready_with_agent_run_binding",
    "ready_with_derived_refs_only",
    "not_ready",
]

APPROVED_FULL_SUITE_COMMAND = "UV_CACHE_DIR=/tmp/uv-cache uv run pytest"
APPROVED_PYTEST_ENTRYPOINT = APPROVED_FULL_SUITE_COMMAND + " "
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
REQUIRED_UNTRUSTED_FACT_TERMS = {
    "requested_by",
    "user.merchant_id",
    "owner identity",
    "thread id",
    "prompt text",
    "memory",
    "RAG",
    "LLM",
    "raw tool payload",
    "target_merchant_context",
    "replay_authorization_proof",
}
REQUIRED_COMMAND_MARKERS = {
    "tests/replay/test_phase36_readiness.py",
    "tests/replay/test_phase35_trace_replay_permissions.py",
    "tests/test_trace_api.py",
    "tests/business/test_service.py",
    "tests/knowledge/test_claim_verification_bundle.py",
    "tests/agent/test_memory_evidence_boundary.py",
}


class Phase36ReadinessArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["phase36_trace_replay_readiness.v1"]
    phase: Literal["36-merchant-scope-db-hardening-role-cleanup"]
    readiness_result: Phase36ReadinessResult
    trusted_facts: list[str] = Field(min_length=1)
    untrusted_facts: list[str] = Field(min_length=1)
    blockers: list[str]
    required_test_commands: list[str] = Field(min_length=1)
    phase37_allowed_next_steps: list[str] = Field(min_length=1)
    generated_from: list[str] = Field(min_length=1)


def load_phase36_readiness(path: Path | str = PHASE36_READINESS_PATH) -> Phase36ReadinessArtifact:
    """Load the Phase 36 readiness artifact from disk."""

    artifact_path = Path(path)
    return Phase36ReadinessArtifact.model_validate_json(artifact_path.read_text(encoding="utf-8"))


def validate_phase36_readiness(path: Path | str = PHASE36_READINESS_PATH) -> list[str]:
    """Return deterministic validation errors for the Phase 36 readiness artifact."""

    artifact_path = Path(path)
    try:
        raw_text = artifact_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"readiness artifact does not exist: {artifact_path}"]

    try:
        raw = json.loads(raw_text)
    except JSONDecodeError as exc:
        return [f"readiness artifact is not valid JSON: line {exc.lineno} column {exc.colno}"]

    try:
        artifact = Phase36ReadinessArtifact.model_validate(raw)
    except ValidationError as exc:
        return _validation_error_strings(exc)

    errors: list[str] = []
    _validate_untrusted_facts(artifact, errors)
    _validate_required_commands(artifact, errors)
    _validate_ready_result_consistency(artifact, errors)
    return errors


def _validation_error_strings(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"]) or "<root>"
        errors.append(f"{loc}: {error['msg']}")
    return sorted(errors)


def _validate_untrusted_facts(artifact: Phase36ReadinessArtifact, errors: list[str]) -> None:
    text = "\n".join(artifact.untrusted_facts)
    for term in sorted(REQUIRED_UNTRUSTED_FACT_TERMS):
        if term not in text:
            errors.append(f"untrusted_facts missing required weak-source term: {term}")


def _validate_required_commands(artifact: Phase36ReadinessArtifact, errors: list[str]) -> None:
    commands = artifact.required_test_commands
    for command in commands:
        if not _uses_approved_pytest_entrypoint(command):
            errors.append(f"required_test_commands contains unapproved entrypoint: {command!r}")
        if _contains_bare_pytest(command):
            errors.append(f"required_test_commands contains bare pytest entrypoint: {command!r}")

    command_text = "\n".join(commands)
    for marker in sorted(REQUIRED_COMMAND_MARKERS):
        if marker not in command_text:
            errors.append(f"required_test_commands missing focused marker: {marker}")

    if APPROVED_FULL_SUITE_COMMAND not in commands:
        errors.append("required_test_commands missing full suite command")


def _uses_approved_pytest_entrypoint(command: str) -> bool:
    return command == APPROVED_FULL_SUITE_COMMAND or command.startswith(APPROVED_PYTEST_ENTRYPOINT)


def _contains_bare_pytest(command: str) -> bool:
    return any(
        not _is_approved_pytest_entrypoint(match.group("entrypoint"))
        for match in PYTEST_ENTRYPOINT_RE.finditer(command)
    )


def _is_approved_pytest_entrypoint(entrypoint: str) -> bool:
    normalized = " ".join(entrypoint.strip().split())
    return normalized == APPROVED_FULL_SUITE_COMMAND


def _validate_ready_result_consistency(artifact: Phase36ReadinessArtifact, errors: list[str]) -> None:
    if artifact.readiness_result == "ready_with_agent_run_binding" and artifact.blockers:
        errors.append("ready_with_agent_run_binding must not include blockers")
    if artifact.readiness_result == "not_ready" and not artifact.blockers:
        errors.append("not_ready must include at least one blocker")
