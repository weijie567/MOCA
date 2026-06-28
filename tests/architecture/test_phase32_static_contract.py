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

REQUIRED_MAPPINGS = [
    ("classify_intent", "node", "contextual_intent_resolve", "compatibility_alias", True),
    ("intent_classification", "node", "contextual_intent_resolve", "compatibility_alias", True),
    ("classify_intent:pre_route", "node", "safety_pre_route", "compatibility_alias", True),
    ("session_memory_load", "node", "session_context_load", "compatibility_alias", True),
    ("long_term_memory_retrieve", "node", "memory_context_load", "compatibility_alias", True),
    ("reviewed_memory_context_retrieve", "node", "memory_context_load", "runtime", True),
    ("extract_slots", "node", "slot_resolution_gate", "compatibility_alias", True),
    ("slot_resolution_gate", "node", "slot_resolution_gate", "compatibility_alias", True),
    ("route_after_intent", "router", "route_after_contextual_intent", "compatibility_alias", True),
    ("route_after_slots", "router", "route_after_slot_resolution", "compatibility_alias", True),
    ("rag_context_build", "node", "rag_context_build", "deferred_non_runnable", False),
    ("claim_verify", "node", "claim_verify", "deferred_non_runnable", False),
]

POLICY_CONSTANTS = ("DIRECT_RESPONSE_INTENTS", "INTENT_ROUTE_POLICY", "REQUIRED_SLOT_POLICY")
PHASE32_ARTIFACT_GLOBS = ("32-*-PLAN.md", "32-*-SUMMARY.md", "32-MVP-TARGET-MAPPING.md")
BULLET_INLINE_COMMAND_RE = re.compile(r"^-\s+`([^`]+)`")


def test_phase33_rag_and_claim_targets_are_deferred_non_runnable_and_not_graph_registered() -> None:
    graph_source = (ROOT / "src" / "agent" / "graph.py").read_text()

    assert not re.search(r"builder\.add_node\(\s*['\"]rag_context_build['\"]", graph_source)
    assert not re.search(r"builder\.add_node\(\s*['\"]claim_verify['\"]", graph_source)
    for name in ("rag_context_build", "claim_verify"):
        entry = graph_vocabulary.graph_vocabulary_entry(name, kind="node")
        assert entry is not None
        assert entry.status == "deferred_non_runnable"
        assert entry.runnable is False
        assert graph_vocabulary.is_deferred_non_runnable_target(name, kind="node") is True


def test_phase32_required_mapping_entries_match_graph_vocabulary() -> None:
    for legacy_name, kind, target_name, status, runnable in REQUIRED_MAPPINGS:
        entry = graph_vocabulary.graph_vocabulary_entry(legacy_name, kind=kind)  # type: ignore[arg-type]

        assert entry is not None, legacy_name
        assert entry.target_name == target_name
        assert graph_vocabulary.target_graph_name(legacy_name, kind=kind) == target_name  # type: ignore[arg-type]
        assert entry.status == status
        assert entry.runnable is runnable


def test_phase32_mapping_document_matches_graph_vocabulary_when_present() -> None:
    if not MAPPING_DOC.exists():
        pytest.skip("32-MVP-TARGET-MAPPING.md is created by Phase 32 Plan 05 Task 2")

    rows = _mapping_doc_rows()
    for legacy_name, kind, target_name, status, runnable in REQUIRED_MAPPINGS:
        row = rows.get((legacy_name, kind))
        assert row is not None, f"Missing mapping row for {legacy_name}/{kind}"
        assert row["target"] == target_name
        assert row["status"] == status
        assert row["runnable"] == str(runnable).lower()


def test_phase32_consumers_do_not_reference_direct_policy_constants() -> None:
    for relative_path in (
        "src/agent/routing.py",
        "src/agent/nodes/classify_intent.py",
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
