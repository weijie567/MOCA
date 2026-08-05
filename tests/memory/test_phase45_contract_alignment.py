from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"
PHASE45_DIR = ROOT / ".planning" / "milestones" / "v2.1-phases" / "45-memory-lifecycle-wiring-for-case-working-context"
LIFECYCLE_PATH = ROOT / "src" / "memory" / "case_working_context_lifecycle.py"
FINALIZER_PATH = ROOT / "src" / "api" / "services" / "agent_run_memory.py"
INVESTIGATE_PATH = ROOT / "src" / "agent" / "nodes" / "investigate.py"
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
DB_MODELS_PATH = ROOT / "src" / "db" / "models.py"
PHASE45_CODE_PATHS = (
    ROOT / "src" / "memory" / "case_working_context_lifecycle.py",
    ROOT / "src" / "api" / "services" / "agent_run_memory.py",
    ROOT / "src" / "agent" / "state.py",
    ROOT / "src" / "agent" / "nodes" / "receive_request.py",
    ROOT / "src" / "agent" / "nodes" / "reviewed_memory_context_retrieve.py",
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _section_9_4() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 9.4 Node contract table", "### 9.5 Router")


def _agent_state_registry() -> str:
    return _between(
        _source(CONTRACT_SPEC_PATH),
        "#### AgentState canonical field registry",
        "### 10.2 Slot inheritance rules",
    )


def _section_13_4a() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.4a Case Working Context", "### 13.5 Memory write policy")


def _section_13_5() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.5 Memory write policy", "### 13.6 Storage model")


def test_contract_memory_context_load_writes_contextual_cwc_fields() -> None:
    section = _section_9_4()

    for term in (
        "`memory_context_load`",
        "`case_working_context`",
        "`case_working_context_lifecycle_status`",
        "contextual-only run state",
        "CaseWorkingContextLifecycleAdapter",
        "before `investigate` consumes memory",
    ):
        assert term in section


def test_contract_agent_state_registry_records_cwc_fields_and_writer() -> None:
    registry = _agent_state_registry()

    for term in (
        "`case_working_context`, `case_working_context_lifecycle_status`",
        "contextual-only loaded view",
        "memory_context_load / CaseWorkingContextLifecycleAdapter",
        "reset loaded view each turn",
        "memory tables / AgentStep refs",
    ):
        assert term in registry


def test_contract_cwc_lifecycle_records_active_read_run_auto_and_terminal_writeback() -> None:
    section = _section_13_4a()

    for term in (
        "active CWC read",
        "tenant + `refund_cases.id`",
        '`link_source="run_auto"`',
        "linked_by_run_id",
        "terminal finalizer",
        "CaseWorkingContextService.write_case_working_context(...)",
        "best-effort memory side effect",
    ):
        assert term in section


def test_contract_cwc_lifecycle_records_projection_and_failure_isolation() -> None:
    section = _section_13_4a()

    for term in (
        "deterministic terminal writeback",
        "no LLM summarizer",
        "PII/ref-only",
        "expected_version",
        "conflict",
        "do not roll back",
        "assistant message",
        "thread summary",
        "approval/action/user response artifacts",
    ):
        assert term in section


def test_contract_memory_write_keeps_cwc_audit_only() -> None:
    section = _section_13_5()

    for term in (
        "`case_working_context` memory_write_events",
        "audit records only",
        "not evidence/policy/approval/action authority",
        "run_id",
        "source_ref",
    ):
        assert term in section


def test_phase45_cwc_projection_has_no_llm_or_summarizer_dependency() -> None:
    source = "\n".join((_source(LIFECYCLE_PATH), _source(FINALIZER_PATH)))

    for token in ("ChatOpenAI", "OpenAI", "summary_llm"):
        assert token not in source
    assert re.search(r"\bllm\b", source, flags=re.IGNORECASE) is None
    assert re.search(r"\bsummarize\b", source, flags=re.IGNORECASE) is None


def test_phase45_cwc_lifecycle_has_no_case_memories_backfill() -> None:
    source = "\n".join((_source(LIFECYCLE_PATH), _source(FINALIZER_PATH)))

    for token in (
        "CaseMemoryRepository",
        "CaseMemoryService",
        "case_memories",
        "search_case_memory",
    ):
        assert token not in source


def test_investigate_does_not_write_graph_global_active_slots() -> None:
    tree = ast.parse(_source(INVESTIGATE_PATH))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if _constant_str(key) == "active_slots":
                    violations.append("return {'active_slots': ...}")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _writes_active_slots_subscript(target):
                    violations.append("result['active_slots'] = ...")
        if isinstance(node, ast.AnnAssign | ast.AugAssign) and _writes_active_slots_subscript(node.target):
            violations.append("result['active_slots'] = ...")

    assert violations == []


def test_graph_stays_react_decoupled_and_final_response_terminal() -> None:
    source = _source(GRAPH_PATH)

    assert 'builder.add_node("memory_write"' not in source
    assert 'builder.add_edge("final_response", "memory_write")' not in source
    assert 'builder.add_edge("final_response", END)' in source
    assert "ReAct" not in source
    assert "react_loop" not in source


def test_legacy_memory_tables_and_conversation_case_id_are_retained() -> None:
    models = _source(DB_MODELS_PATH)
    phase45_sources = "\n".join(_source(path) for path in PHASE45_CODE_PATHS)
    phase45_plans = "\n".join(_source(path) for path in sorted(PHASE45_DIR.glob("45-*-PLAN.md")))
    phase45_surface = f"{phase45_sources}\n{phase45_plans}"

    for term in (
        '__tablename__ = "case_memories"',
        '__tablename__ = "long_term_memories"',
        "ConversationThread.case_id",
        "ix_conversation_threads_case_id",
    ):
        assert term in models

    for pattern in (
        r"drop_table\(['\"]case_memories['\"]",
        r"drop_table\(['\"]long_term_memories['\"]",
        r"drop_column\(['\"]conversation_threads['\"],\s*['\"]case_id['\"]",
        r"rename_table\(['\"]case_memories['\"]",
        r"rename_table\(['\"]long_term_memories['\"]",
    ):
        assert re.search(pattern, phase45_surface) is None


def test_phase45_plans_and_validation_reject_bare_pytest_commands() -> None:
    checked_paths = sorted(PHASE45_DIR.glob("45-*-PLAN.md")) + [PHASE45_DIR / "45-VALIDATION.md"]
    snippets: list[tuple[Path, str]] = []
    for path in checked_paths:
        snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

    assert snippets
    for path, snippet in snippets:
        assert snippet.startswith("UV_CACHE_DIR=/tmp/uv-cache uv run pytest"), (path, snippet)


def _constant_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _writes_active_slots_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and _constant_str(node.slice) == "active_slots"


def _pytest_command_snippets(path: Path) -> list[str]:
    snippets: list[str] = []
    for line in _source(path).splitlines():
        stripped = line.strip()
        automated_match = re.search(r"<automated>(.*?)</automated>", stripped)
        if automated_match and "pytest" in automated_match.group(1):
            snippets.append(automated_match.group(1).strip())
            continue
        if stripped.startswith(("UV_CACHE_DIR=/tmp/uv-cache uv run pytest", "pytest", "python -m pytest")):
            snippets.append(stripped)
            continue
        if _is_forbidden_pytest_prose(stripped):
            continue
        for snippet in re.findall(r"`([^`]*pytest[^`]*)`", stripped):
            command = snippet.strip()
            if command.startswith(("UV_CACHE_DIR=/tmp/uv-cache uv run pytest", "pytest", "python -m pytest")):
                snippets.append(command)
    return snippets


def _is_forbidden_pytest_prose(line: str) -> bool:
    lowered = line.lower()
    return any(word in lowered for word in ("bare", "invalid", "reject", "unapproved", "approved-entrypoint"))
