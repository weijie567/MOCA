from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from src.replay.phase36_readiness import (
    PHASE36_READINESS_PATH,
    READINESS_SCHEMA_VERSION,
    Phase36ReadinessArtifact,
    Phase36ReadinessResult,
    load_phase36_readiness,
    validate_phase36_readiness,
)


APPROVED_COMMAND_PREFIX = "UV_CACHE_DIR=/tmp/uv-cache uv run pytest "
READINESS_RESULTS = {
    "ready_with_agent_run_binding",
    "ready_with_derived_refs_only",
    "not_ready",
}
UNTRUSTED_FACT_TERMS = {
    "requested_by",
    "user.merchant_id",
    "thread id",
    "prompt text",
    "memory",
    "RAG",
    "LLM",
    "raw tool payload",
    "target_merchant_context",
    "replay_authorization_proof",
}


def _load_raw(path: Path = PHASE36_READINESS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_readiness_artifact_loads_with_exact_phase36_schema_and_one_result():
    artifact = load_phase36_readiness()

    assert artifact.schema_version == READINESS_SCHEMA_VERSION
    assert artifact.phase == "36-merchant-scope-db-hardening-role-cleanup"
    assert artifact.readiness_result in READINESS_RESULTS
    assert isinstance(artifact.readiness_result, str)
    assert validate_phase36_readiness() == []


def test_allowed_readiness_values_are_exactly_phase36_contract():
    annotation = Phase36ReadinessResult

    assert set(annotation.__args__) == READINESS_RESULTS
    assert len(annotation.__args__) == 3

    raw = _load_raw()
    for value in READINESS_RESULTS:
        Phase36ReadinessArtifact.model_validate(raw | {"readiness_result": value})

    with_bad_value = raw | {"readiness_result": "ready_after_manager_visibility"}
    with_empty_value = raw | {"readiness_result": ""}

    for payload in (with_bad_value, with_empty_value):
        try:
            Phase36ReadinessArtifact.model_validate(payload)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"invalid readiness_result accepted: {payload['readiness_result']!r}")


def test_readiness_artifact_lists_required_fact_and_next_step_sections():
    artifact = load_phase36_readiness()

    assert artifact.trusted_facts
    assert artifact.untrusted_facts
    assert artifact.required_test_commands
    assert artifact.phase37_allowed_next_steps
    assert artifact.generated_from


def test_required_commands_use_project_scoped_pytest_entrypoint_only():
    artifact = load_phase36_readiness()

    assert artifact.required_test_commands
    for command in artifact.required_test_commands:
        assert command.startswith(APPROVED_COMMAND_PREFIX), command
        assert " python -m pytest" not in command
        assert " pytest " not in command.removeprefix(APPROVED_COMMAND_PREFIX), command
        assert not command.startswith("pytest ")


def test_required_commands_reject_unscoped_or_chained_pytest_entrypoints(tmp_path: Path):
    raw = _load_raw()
    bad_path = tmp_path / "phase36-readiness.bad.json"
    bad_path.write_text(
        json.dumps(
            raw
            | {
                "required_test_commands": [
                    "pytest tests/replay/test_phase36_readiness.py",
                    (
                        "UV_CACHE_DIR=/tmp/uv-cache uv run pytest "
                        "tests/replay/test_phase36_readiness.py; "
                        "python -m pytest tests/replay/test_leak.py"
                    ),
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    errors = validate_phase36_readiness(bad_path)

    assert sum("bare pytest entrypoint" in error for error in errors) == 2


def test_artifact_marks_weak_scope_sources_as_untrusted_facts():
    raw_text = PHASE36_READINESS_PATH.read_text(encoding="utf-8")
    artifact = load_phase36_readiness()
    untrusted = "\n".join(artifact.untrusted_facts)

    for term in UNTRUSTED_FACT_TERMS:
        assert term in raw_text
        assert term in untrusted


def test_artifact_includes_focused_no_widening_and_full_suite_commands():
    artifact = load_phase36_readiness()
    commands = "\n".join(artifact.required_test_commands)

    assert "tests/replay/test_phase36_readiness.py" in commands
    assert "tests/replay/test_phase35_trace_replay_permissions.py" in commands
    assert "tests/test_trace_api.py" in commands
    assert "UV_CACHE_DIR=/tmp/uv-cache uv run pytest" in commands
