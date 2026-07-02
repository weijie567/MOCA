from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"
MEMORY_DECISIONS_PATH = ROOT / ".planning" / "MEMORY-REDESIGN-DECISIONS.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section_13() -> str:
    source = _source(CONTRACT_SPEC_PATH)
    section_start = source.index("## 13. Memory 设计")
    section_end = source.index("## 14. Prompt 设计")
    return source[section_start:section_end]


def test_contract_spec_defines_case_working_context_as_contextual_only_layer() -> None:
    section = _section_13()

    for term in (
        "Case Working Context",
        "case_working_contexts",
        "authority_class = contextual_only",
        "NOT an `EvidenceRefV1`",
        "cannot authorize policy/risk/approval/action",
        "claims and verified facts separately",
        "policy body text and sensitive raw PII must never be stored",
        "case_working_context_revisions",
    ):
        assert term in section


def test_contract_spec_keeps_case_memory_as_precedent_not_active_case_state() -> None:
    section = _section_13()

    assert "`case_memories` / `case_memory` are reviewed precedent, NOT active case state" in section
    assert "Case Working Context is distinct from `case_memory`" in section
    assert "current case's working state" in section


def test_contract_spec_records_additive_thread_case_many_to_many() -> None:
    section = _section_13()

    for term in (
        "additive many-to-many",
        "thread_case_links",
        "refund_cases.id",
        "conversation_threads.case_id",
        "does not drop, rename, retype, or replace",
    ):
        assert term in section


def test_contract_spec_retains_red_line_table_names_and_cwc_audit_type() -> None:
    source = _source(CONTRACT_SPEC_PATH)
    section = _section_13()

    assert "case_memories" in source
    assert "long_term_memories" in source
    assert "case_working_context" in section
    assert "memory_write_events" in section
    assert (
        "memory_write_events.memory_type in ('session_slot', 'long_term_fact', "
        "'case_memory', 'case_working_context', 'none')"
    ) in source


def test_memory_redesign_decisions_preserve_defer_trace() -> None:
    source = _source(MEMORY_DECISIONS_PATH)

    for marker in ("DEFER-1", "DEFER-2", "DEFER-3"):
        assert marker in source

    assert "Phase 44 delivered: CWC layer + thread↔case M:N" in source
    assert "auto-update hook wiring deferred to Phase 45 memory lifecycle wiring" in source
