from __future__ import annotations

import re
from pathlib import Path

from src.memory.identity import ALLOWED_SOURCE_REF_KEYS
from src.memory.schemas import MemorySourceRefV1
from src.tools.contracts import ToolCallContext


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"
DB_MODELS_PATH = ROOT / "src" / "db" / "models.py"
MEMORY_DECISIONS_PATH = ROOT / ".planning" / "MEMORY-REDESIGN-DECISIONS.md"
PHASE47_DIR = ROOT / ".planning" / "phases" / "47-case-precedent-repositioning-and-closed-case-candidate-gener"
MIGRATIONS_DIR = ROOT / "src" / "db" / "migrations" / "versions"
AGENT_RUN_MEMORY_PATH = ROOT / "src" / "api" / "services" / "agent_run_memory.py"
CWC_LIFECYCLE_PATH = ROOT / "src" / "memory" / "case_working_context_lifecycle.py"
CASE_PRECEDENT_PATH = ROOT / "src" / "memory" / "case_precedent.py"
TOOLS_CONTRACTS_PATH = ROOT / "src" / "tools" / "contracts.py"
MEMORY_TOOL_EXECUTOR_PATH = ROOT / "src" / "tools" / "executors" / "memory.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _contract_case_memory_section() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.4 Case memory", "### 13.5 Memory write policy")


def test_contract_documents_reviewed_closed_case_precedent_boundary() -> None:
    section = _contract_case_memory_section()

    for term in (
        "reviewed closed-case precedent",
        "NOT active case state",
        "CaseMemoryService.submit_case_memory_candidate",
        "needs_review",
        "metadata/text retrieval",
        "query_embedding",
    ):
        assert term in section


def test_protected_memory_tables_and_conversation_case_link_are_retained() -> None:
    models = _source(DB_MODELS_PATH)
    conversation_thread_block = _between(models, "class ConversationThread", "Index(\"ix_conversation_threads")

    for term in (
        '__tablename__ = "case_memories"',
        '__tablename__ = "long_term_memories"',
        '__tablename__ = "case_working_contexts"',
    ):
        assert term in models
    assert "case_id: Mapped[str | None]" in conversation_thread_block


def test_no_destructive_schema_ops_in_implementation_surfaces() -> None:
    checked_sources = [(DB_MODELS_PATH, _source(DB_MODELS_PATH))]
    checked_sources.extend((path, _source(path)) for path in _phase47_migration_paths())
    destructive_patterns = (
        r"drop_table\([\"']case_memories[\"']",
        r"drop_table\([\"']long_term_memories[\"']",
        r"drop_table\([\"']case_working_contexts[\"']",
        r"drop_column\([\"']conversation_threads[\"'],\s*[\"']case_id[\"']",
        r"alter_column\([\"']conversation_threads[\"'],\s*[\"']case_id[\"']",
        r"rename_table\([\"']case_memories[\"']",
        r"rename_table\([\"']long_term_memories[\"']",
        r"rename_table\([\"']case_working_contexts[\"']",
    )

    violations: list[tuple[str, str]] = []
    for path, source in checked_sources:
        for pattern in destructive_patterns:
            if re.search(pattern, source):
                violations.append((str(path.relative_to(ROOT)), pattern))

    assert violations == []


def test_plan_text_has_no_unsafe_storage_action_instructions() -> None:
    checked_paths = sorted(PHASE47_DIR.glob("47-*-PLAN.md")) + [PHASE47_DIR / "47-VALIDATION.md"]
    protected_terms = (
        "case_memories",
        "long_term_memories",
        "case_working_contexts",
        "conversation_threads.case_id",
    )
    unsafe_verbs = ("drop", "rename", "replace", "remove", "delete", "retype", "alter")
    violations: list[tuple[str, int, str]] = []

    for path in checked_paths:
        for line_number, line in _planning_prose_lines(path):
            lowered = line.lower()
            if not any(term in lowered for term in protected_terms):
                continue
            if any(verb in lowered for verb in unsafe_verbs):
                violations.append((path.name, line_number, line.strip()))

    assert violations == []


def test_completed_agent_run_paths_do_not_generate_closed_case_candidates() -> None:
    source = "\n".join((_source(AGENT_RUN_MEMORY_PATH), _source(CWC_LIFECYCLE_PATH)))

    for token in (
        "generate_closed_case_precedent_candidate",
        "ClosedCasePrecedentService",
        "closed_case_cwc_candidate",
    ):
        assert token not in source


def test_phase47_plan_pytest_entrypoints_use_moca_runner() -> None:
    checked_paths = sorted(PHASE47_DIR.glob("47-*-PLAN.md")) + [PHASE47_DIR / "47-VALIDATION.md"]
    snippets: list[tuple[Path, str]] = []
    for path in checked_paths:
        snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

    assert snippets
    for path, snippet in snippets:
        assert snippet.startswith("UV_CACHE_DIR=/tmp/uv-cache uv run pytest"), (path, snippet)


def test_defer_3_remains_phase48_scope() -> None:
    decisions = _source(MEMORY_DECISIONS_PATH)

    assert "DEFER-3 -> Phase 48" in decisions


def test_source_ref_schema_and_identity_keys_remain_stable() -> None:
    expected_keys = {
        "source_type",
        "run_id",
        "event_id",
        "conversation_message_id",
        "tool_result_id",
        "agent_run_id",
        "business_object_type",
        "business_object_id",
        "policy_version",
        "outcome_id",
    }

    assert set(MemorySourceRefV1.model_fields) == expected_keys
    assert set(ALLOWED_SOURCE_REF_KEYS) == expected_keys
    assert "cwc_version" not in MemorySourceRefV1.model_fields
    assert "closed_at" not in MemorySourceRefV1.model_fields
    assert "cwc_version" not in ALLOWED_SOURCE_REF_KEYS
    assert "closed_at" not in ALLOWED_SOURCE_REF_KEYS


def test_case_precedent_projection_has_no_authority_or_replay_imports() -> None:
    source = _source(CASE_PRECEDENT_PATH)

    for forbidden in (
        "EvidenceRefV1",
        "BusinessFactRefV1",
        "ApprovalRequest",
        "ApprovalDecision",
        "ActionDraft",
        "ReplayEvent",
        "ReplayTruth",
    ):
        assert forbidden not in source
    for allowed in ("CaseMemoryWriteCandidate", "MemorySourceRefV1", "CaseWorkingContextContentV1"):
        assert allowed in source


def test_tool_context_and_memory_executor_do_not_take_case_id() -> None:
    contracts_source = _source(TOOLS_CONTRACTS_PATH)
    executor_source = _source(MEMORY_TOOL_EXECUTOR_PATH)
    tool_context_block = _between(contracts_source, "class ToolCallContext", "class ToolRequest")

    assert "case_id" not in ToolCallContext.model_fields
    assert "case_id" not in tool_context_block
    assert "context.case_id" not in executor_source
    for expected in ("context.tenant_id", "context.user_id", "context.thread_id", "_merchant_ids"):
        assert expected in executor_source


def _phase47_migration_paths() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    paths: list[Path] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        source = _source(path)
        identity = f"{path.name}\n{source}".lower()
        if "phase47" in identity or "phase 47" in identity or "case_precedent" in identity:
            paths.append(path)
    return paths


def _planning_prose_lines(path: Path) -> list[tuple[int, str]]:
    source = _strip_fenced_code(_strip_excluded_plan_sections(_source(path)))
    lines: list[tuple[int, str]] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if stripped.startswith(("|", "```", "- path:", "from:", "to:", "via:", "pattern:")):
            continue
        if any(marker in lowered for marker in ("do not", "must not", "forbid", "forbidden", "not rename", "not renamed", "not active", "no destructive")):
            continue
        lines.append((line_number, stripped))
    return lines


def _strip_fenced_code(source: str) -> str:
    return re.sub(r"```.*?```", "", source, flags=re.DOTALL)


def _strip_excluded_plan_sections(source: str) -> str:
    for section in ("interfaces", "source_audit", "threat_model"):
        source = re.sub(rf"<{section}>.*?</{section}>", "", source, flags=re.DOTALL)
    return source


def _pytest_command_snippets(path: Path) -> list[str]:
    snippets: list[str] = []
    for line in _source(path).splitlines():
        stripped = line.strip()
        if _is_pytest_prose(stripped):
            continue
        automated_match = re.search(r"<automated>(.*?)</automated>", stripped)
        if automated_match and "pytest" in automated_match.group(1):
            snippets.append(automated_match.group(1).strip())
            continue
        if re.match(r"^(?:UV_CACHE_DIR=\S+\s+)?(?:uv run pytest|pytest|python -m pytest)\b", stripped):
            snippets.append(stripped)
            continue
        for snippet in re.findall(r"`([^`]*pytest[^`]*)`", stripped):
            command = snippet.strip()
            if re.match(r"^(?:UV_CACHE_DIR=\S+\s+)?(?:uv run pytest|pytest|python -m pytest)\b", command):
                snippets.append(command)
    return snippets


def _is_pytest_prose(line: str) -> bool:
    lowered = line.lower()
    return any(
        marker in lowered
        for marker in (
            "approved pytest",
            "bare",
            "commands must use",
            "every command",
            "framework",
            "invalid",
            "pytest-asyncio",
            "reject",
            "use `uv run pytest",
        )
    )
