from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"


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
        "`link_source=\"run_auto\"`",
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
