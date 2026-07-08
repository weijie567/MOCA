from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from src.agent import graph_vocabulary
from src.api.routers import agent_runs, traces


ROOT = Path(__file__).resolve().parents[2]
PHASE_DIR = ROOT / ".planning" / "phases" / "32-intent-graph-migration"
MAPPING_DOC = PHASE_DIR / "32-MVP-TARGET-MAPPING.md"

CANONICAL_RUNTIME_MAPPINGS = [
    ("receive_request", "node"),
    ("safety_pre_route", "node"),
    ("session_context_load", "node"),
    ("contextual_intent_resolve", "node"),
    ("slot_resolution_gate", "node"),
    ("memory_context_load", "node"),
    ("investigate", "node"),
    ("rag_context_build", "node"),
    ("recommendation_generation", "node"),
    ("claim_verify", "node"),
    ("risk_gate", "node"),
    ("approval_gate", "node"),
    ("action_draft", "node"),
    ("clarification_gate", "node"),
    ("final_response", "node"),
    ("route_after_safety", "router"),
    ("route_after_contextual_intent", "router"),
    ("route_after_slot_resolution", "router"),
    ("route_after_investigate", "router"),
    ("route_after_rag_context", "router"),
    ("route_after_recommendation", "router"),
    ("route_after_claim_verify", "router"),
    ("route_after_risk", "router"),
    ("route_after_approval", "router"),
]
LEGACY_ACTIVE_VOCABULARY_NAMES = [
    ("classify_intent", "node"),
    ("intent_classification", "node"),
    ("classify_intent:pre_route", "node"),
    ("session_memory_load", "node"),
    ("long_term_memory_retrieve", "node"),
    ("reviewed_memory_context_retrieve", "node"),
    ("extract_slots", "node"),
    ("generate_recommendation", "node"),
    ("assess_risk_and_approval", "node"),
    ("route_after_intent", "router"),
    ("route_after_slots", "router"),
]

POLICY_CONSTANTS = ("DIRECT_RESPONSE_INTENTS", "INTENT_ROUTE_POLICY", "REQUIRED_SLOT_POLICY")
PHASE32_ARTIFACT_GLOBS = ("32-*-PLAN.md", "32-*-SUMMARY.md", "32-MVP-TARGET-MAPPING.md")
BULLET_INLINE_COMMAND_RE = re.compile(r"^-\s+`([^`]+)`")


def test_phase32_current_graph_vocabulary_is_canonical_only() -> None:
    for name, kind in CANONICAL_RUNTIME_MAPPINGS:
        entry = graph_vocabulary.graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

        assert entry is not None, name
        assert entry.target_name == name
        assert graph_vocabulary.target_graph_name(name, kind=kind) == name  # type: ignore[arg-type]
        assert entry.status == "runtime"
        assert entry.runnable is True

    for legacy_name, kind in LEGACY_ACTIVE_VOCABULARY_NAMES:
        assert graph_vocabulary.graph_vocabulary_entry(legacy_name, kind=kind) is None  # type: ignore[arg-type]
        assert graph_vocabulary.target_graph_name(legacy_name, kind=kind) == legacy_name  # type: ignore[arg-type]


def test_phase32_mapping_document_is_historical_when_present() -> None:
    if not MAPPING_DOC.exists():
        pytest.skip("32-MVP-TARGET-MAPPING.md is created by Phase 32 Plan 05 Task 2")

    rows = _mapping_doc_rows()
    for legacy_name, kind in LEGACY_ACTIVE_VOCABULARY_NAMES:
        row = rows.get((legacy_name, kind))
        if row is not None:
            assert graph_vocabulary.graph_vocabulary_entry(legacy_name, kind=kind) is None  # type: ignore[arg-type]


def test_phase32_consumers_do_not_reference_direct_policy_constants() -> None:
    for relative_path in (
        "src/agent/routing.py",
        "src/agent/nodes/contextual_intent_resolve.py",
        "src/agent/nodes/receive_request.py",
    ):
        source = (ROOT / relative_path).read_text()
        for constant in POLICY_CONSTANTS:
            assert constant not in source, f"{relative_path} references {constant} directly"


def test_run_trace_replay_visibility_guards_are_admin_only_and_ignore_target_merchant_context() -> None:
    assert agent_runs.ADMIN_RUN_VISIBILITY_ROLES == {"admin"}
    assert traces.ADMIN_RUN_VISIBILITY_ROLES == {"admin"}

    guarded_sources = [
        inspect.getsource(agent_runs._ensure_can_view_run),
        inspect.getsource(agent_runs._ensure_can_execute_run),
        inspect.getsource(traces.get_run_trace),
        inspect.getsource(traces.get_run_replay),
    ]
    for source in guarded_sources:
        assert "target_merchant_context" not in source


def test_phase32_artifacts_use_project_test_entrypoints_for_validation_commands() -> None:
    violations: list[str] = []
    for path in _phase32_artifacts():
        for line_number, command in _validation_commands(path):
            if command.startswith("pytest") or command.startswith("python -m pytest"):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {command}")

    assert violations == []


def test_validation_commands_extract_bullet_inline_code_with_result_suffix(tmp_path: Path) -> None:
    artifact = tmp_path / "summary.md"
    artifact.write_text(
        "\n".join(
            [
                "- `pytest tests/foo.py -q` - failed before rerun",
                "- `python -m pytest tests/bar.py -q` - invalid entrypoint",
                "- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/baz.py -q` - passed",
            ]
        )
    )

    commands = [command for _, command in _validation_commands(artifact)]
    violations = [
        command
        for command in commands
        if command.startswith("pytest") or command.startswith("python -m pytest")
    ]

    assert commands == [
        "pytest tests/foo.py -q",
        "python -m pytest tests/bar.py -q",
        "UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/baz.py -q",
    ]
    assert violations == [
        "pytest tests/foo.py -q",
        "python -m pytest tests/bar.py -q",
    ]


def _phase32_artifacts() -> list[Path]:
    artifacts: list[Path] = []
    for pattern in PHASE32_ARTIFACT_GLOBS:
        artifacts.extend(PHASE_DIR.glob(pattern))
    return sorted(path for path in artifacts if path.exists())


def _validation_commands(path: Path) -> list[tuple[int, str]]:
    commands: list[tuple[int, str]] = []
    in_bash_block = False
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_bash_block = stripped in {"```bash", "```sh", "```shell"}
            continue
        command = ""
        if stripped.startswith("<automated>"):
            command = stripped.removeprefix("<automated>").split("</automated>", 1)[0].strip()
        elif in_bash_block:
            command = stripped.removeprefix("$ ").strip()
        elif match := BULLET_INLINE_COMMAND_RE.match(stripped):
            command = match.group(1).strip()
        elif stripped.startswith("| `"):
            command = stripped.strip("|").split("|", 1)[0].strip().strip("`")
        if command:
            commands.append((line_number, command))
    return commands


def _mapping_doc_rows() -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for line in MAPPING_DOC.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [_normalize_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 5 or cells[0] == "legacy_name":
            continue
        legacy_name, kind, target, status, runnable = cells[:5]
        rows[(legacy_name, kind)] = {
            "target": target,
            "status": status,
            "runnable": runnable.lower(),
        }
    return rows


def _normalize_cell(cell: str) -> str:
    return cell.strip().strip("`").strip()
