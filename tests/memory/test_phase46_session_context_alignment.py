from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"
DB_MODELS_PATH = ROOT / "src" / "db" / "models.py"
SESSION_MEMORY_MIGRATION_PATH = ROOT / "src" / "db" / "migrations" / "versions" / "007_session_memories.py"
PHASE46_DIR = ROOT / ".planning" / "phases" / "46-session-context-repositioning"
MEMORY_DECISIONS_PATH = ROOT / ".planning" / "MEMORY-REDESIGN-DECISIONS.md"
SESSION_RUNTIME_PATHS = (
    ROOT / "src" / "memory" / "session_bundle.py",
    ROOT / "src" / "agent" / "nodes" / "session_context_load.py",
    ROOT / "src" / "memory" / "write_service.py",
    ROOT / "src" / "agent" / "nodes" / "memory_write.py",
)
SESSION_SCHEMA_CLASSES = (
    "SessionMemoryView",
    "SessionMemoryBundle",
    "SessionContextMemory",
    "SessionContextBundle",
    "SessionMemoryWriteCandidate",
)
MEMORY_EXECUTOR_PATH = ROOT / "src" / "tools" / "executors" / "memory.py"
LEGACY_SESSION_SEARCH_PATH = ROOT / "src" / "memory" / "search.py"
CWC_LIFECYCLE_PATH = ROOT / "src" / "memory" / "case_working_context_lifecycle.py"
REVIEWED_MEMORY_NODE_PATH = ROOT / "src" / "agent" / "nodes" / "reviewed_memory_context_retrieve.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _class_block(source: str, class_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"class not found: {class_name}")


def _function_block(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == function_name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"function not found: {function_name}")


def _pytest_command_snippets(path: Path) -> list[str]:
    snippets: list[str] = []
    for line in _source(path).splitlines():
        stripped = line.strip()
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


def _section_13_2() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.2 Session memory", "### 13.3 Long-term memory")


def _section_13_4() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.4 Case memory", "### 13.4a Case Working Context")


def _section_13_4a() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.4a Case Working Context", "### 13.5 Memory write policy")


def _memory_storage_rows() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "session_memories\n", "memory_write_events\n")


def test_contract_documents_post_cwc_session_context_boundary() -> None:
    section = "\n".join((_section_13_2(), _section_13_4(), _section_13_4a(), _memory_storage_rows()))

    for term in (
        "same-thread temporary conversational context",
        "case_working_contexts",
        "case_memories",
        "long_term_memories",
        "policy_topic_hints",
        "prior_policy_mention_refs",
        "last_business_context_refs",
        "EvidenceRefV1",
        "business fact",
        "approval",
        "action",
        "replay",
    ):
        assert term in section


def test_session_memories_remains_thread_scoped_without_case_id() -> None:
    model_block = _class_block(_source(DB_MODELS_PATH), "SessionMemory")
    migration_source = _source(SESSION_MEMORY_MIGRATION_PATH)

    assert '__tablename__ = "session_memories"' in model_block
    assert "tenant_id" in model_block
    assert "user_id" in model_block
    assert "thread_id" in model_block
    assert "case_id" not in model_block
    assert "refund_case_id" not in model_block

    upgrade_block = _between(migration_source, "def upgrade() -> None:", "def downgrade() -> None:")
    assert '"session_memories"' in upgrade_block
    assert '"tenant_id"' in upgrade_block
    assert '"user_id"' in upgrade_block
    assert '"thread_id"' in upgrade_block
    assert "case_id" not in upgrade_block
    assert "refund_case_id" not in upgrade_block


def test_phase46_plans_do_not_destructively_change_memory_schema() -> None:
    checked_paths = sorted(PHASE46_DIR.glob("46-*-PLAN.md"))
    checked_sources = [(path, _source(path)) for path in checked_paths]
    destructive_patterns = (
        r"drop_table\([\"']session_memories[\"']\)",
        r"drop_table\([\"']case_memories[\"']\)",
        r"drop_table\([\"']long_term_memories[\"']\)",
        r"drop_table\([\"']case_working_contexts[\"']\)",
        r"drop_column\([\"']conversation_threads[\"'],\s*[\"']case_id[\"']\)",
        r"alter_column\([\"']conversation_threads[\"'],\s*[\"']case_id[\"']",
        r"rename_table\([\"']session_memories[\"']",
    )

    violations: list[tuple[str, str, str]] = []
    for path, source in checked_sources:
        for line in source.splitlines():
            if "Reject exact patterns such as" in line:
                continue
            for pattern in destructive_patterns:
                if re.search(pattern, line):
                    violations.append((path.name, pattern, line.strip()))

    assert violations == []


def test_session_context_modules_do_not_construct_authority_refs() -> None:
    checked_source = "\n".join(_source(path) for path in SESSION_RUNTIME_PATHS)
    schemas_source = _source(ROOT / "src" / "memory" / "schemas.py")
    checked_source += "\n".join(_class_block(schemas_source, class_name) for class_name in SESSION_SCHEMA_CLASSES)
    forbidden_tokens = (
        "EvidenceRefV1",
        "BusinessFactRefV1(",
        "from src.tools.contracts import BusinessFactRefV1",
        "ApprovalRequest",
        "ApprovalDecision",
        "ActionDraft",
        "ReplayEvent",
        "ReplayTruth",
        "CaseWorkingContextWriteCandidate",
        "CaseWorkingContextLifecycleAdapter",
    )

    violations = [token for token in forbidden_tokens if token in checked_source]
    assert violations == []


def test_search_case_memory_uses_reviewed_case_memory_service() -> None:
    source = _source(MEMORY_EXECUTOR_PATH)

    for token in ("CaseMemoryService", "CaseMemoryRepository", "retrieve_reviewed"):
        assert token in source
    for token in ("LegacySessionPrecedentSearchService", "SessionMemoryRepository"):
        assert token not in source


def test_legacy_session_precedent_search_is_debug_only_not_planner_facing() -> None:
    legacy_source = _source(LEGACY_SESSION_SEARCH_PATH)
    executor_source = _source(MEMORY_EXECUTOR_PATH)

    assert "class LegacySessionPrecedentSearchService" in legacy_source
    assert "debug-only" in legacy_source
    assert "must not back the planner-facing" in legacy_source
    assert "search_case_memory" in legacy_source
    assert "LegacySessionPrecedentSearchService" not in executor_source


def test_session_memory_is_not_case_working_context_fallback() -> None:
    checked_source = "\n".join((_source(CWC_LIFECYCLE_PATH), _source(REVIEWED_MEMORY_NODE_PATH)))
    forbidden_identity_sources = (
        'state.get("session_memory")',
        'state.get("session_context")',
        'state.get("case_memory")',
        'memory_context.get("case_memory")',
        "CaseMemoryRepository",
        "CaseMemoryService",
    )

    violations = [token for token in forbidden_identity_sources if token in checked_source]
    assert violations == []


def test_phase47_and_phase48_defers_remain_named() -> None:
    decisions = _source(MEMORY_DECISIONS_PATH)
    phase46_plans = "\n".join(_source(path) for path in sorted(PHASE46_DIR.glob("46-*-PLAN.md")))

    assert "DEFER-2 -> Phase 47" in decisions
    assert "DEFER-3 -> Phase 48" in decisions
    for token in (
        "ClosedCasePrecedentGenerator",
        "closed_case_candidate",
        "closed_case_precedent_generation",
        "ExplicitPreferenceMemory",
        "explicit_preference_memory_write",
        "remember_preference",
    ):
        assert token not in phase46_plans


def test_phase46_plan_pytest_entrypoints_use_moca_runner() -> None:
    checked_paths = sorted(PHASE46_DIR.glob("46-*-PLAN.md")) + [PHASE46_DIR / "46-VALIDATION.md"]
    snippets: list[tuple[Path, str]] = []
    for path in checked_paths:
        snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

    assert snippets
    for path, snippet in snippets:
        assert snippet.startswith("UV_CACHE_DIR=/tmp/uv-cache uv run pytest"), (path, snippet)
