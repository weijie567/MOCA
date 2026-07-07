from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PHASE48_1_DIR = ROOT / ".planning" / "phases" / "48.1-memory-context-compatibility-debt-cleanup"
CONVERSATION_REPOSITORY_PATH = ROOT / "src" / "conversation" / "repository.py"
ROUTING_PATH = ROOT / "src" / "agent" / "routing.py"
WORKING_STATE_PATH = ROOT / "src" / "agent" / "working_state.py"
SESSION_BUNDLE_HELPER_PATH = ROOT / "src" / "agent" / "context" / "session_memory_bundle.py"
REVIEWED_MEMORY_NODE_PATH = ROOT / "src" / "agent" / "nodes" / "reviewed_memory_context_retrieve.py"
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
GRAPH_VOCABULARY_PATH = ROOT / "src" / "agent" / "graph_vocabulary.py"
DB_MODELS_PATH = ROOT / "src" / "db" / "models.py"
CONFIG_PATH = ROOT / "src" / "config.py"
MEMORY_REPOSITORY_PATH = ROOT / "src" / "memory" / "repository.py"
MEMORY_API_ROUTER_PATH = ROOT / "src" / "api" / "routers" / "memory.py"
MEMORY_API_SCHEMA_PATH = ROOT / "src" / "api" / "schemas" / "memory.py"
MEMORY_SEARCH_PATH = ROOT / "src" / "memory" / "search.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_block(path: Path, function_name: str) -> str:
    source = _source(path)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == function_name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"function not found: {function_name}")


def _assert_contains(path: Path, *tokens: str) -> None:
    source = _source(path)
    missing = [token for token in tokens if token not in source]
    assert missing == [], (path, missing)


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
        if re.match(r"^(?:UV_CACHE_DIR=\S+\s+)?(?:uv run pytest|pytest|python -m pytest|\.venv/bin/pytest)\b", stripped):
            snippets.append(stripped)
            continue
        for snippet in re.findall(r"`([^`]*pytest[^`]*)`", stripped):
            command = snippet.strip()
            if re.match(
                r"^(?:UV_CACHE_DIR=\S+\s+)?(?:uv run pytest|pytest|python -m pytest|\.venv/bin/pytest)\b",
                command,
            ):
                snippets.append(command)
    return snippets


def _is_pytest_prose(line: str) -> bool:
    lowered = line.lower()
    return any(
        marker in lowered
        for marker in (
            "approved pytest",
            "bare",
            "broad `rg`",
            "command snippets",
            "do not treat",
            "entrypoint",
            "extracts `<automated>`",
            "framework",
            "invalid",
            "pytest 9.",
            "pytest-asyncio",
            "rerun",
            "static test",
            "use `uv run pytest",
        )
    )


def test_phase48_1_plan_pytest_entrypoints_use_moca_runner() -> None:
    checked_paths = sorted(PHASE48_1_DIR.glob("48.1-*-PLAN.md")) + [PHASE48_1_DIR / "48.1-VALIDATION.md"]
    snippets: list[tuple[Path, str]] = []
    for path in checked_paths:
        snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

    assert snippets
    for path, snippet in snippets:
        assert snippet.startswith(
            ("UV_CACHE_DIR=/tmp/uv-cache uv run pytest", ".venv/bin/pytest")
        ), (path.name, snippet)


def test_thread_case_active_readers_use_thread_case_links() -> None:
    source = _source(CONVERSATION_REPOSITORY_PATH)
    summary_block = _function_block(CONVERSATION_REPOSITORY_PATH, "insert_thread_summary")
    helper_block = _function_block(CONVERSATION_REPOSITORY_PATH, "_legacy_summary_case_id_from_links")

    assert "ThreadCaseLinkRepository" in source
    assert "list_cases_for_thread" in helper_block
    assert "case_id=summary_case_id" in summary_block
    assert "case_id=thread.case_id" not in source

    active_sources = {
        CONVERSATION_REPOSITORY_PATH: source,
        ROOT / "src" / "conversation" / "service.py": _source(ROOT / "src" / "conversation" / "service.py"),
        ROOT / "src" / "memory" / "case_working_context_lifecycle.py": _source(
            ROOT / "src" / "memory" / "case_working_context_lifecycle.py"
        ),
    }
    denied_patterns = ("thread.case_id", "conversation_thread.case_id", "ConversationThread.case_id")
    violations: list[tuple[str, str]] = []
    for path, checked_source in active_sources.items():
        for pattern in denied_patterns:
            if pattern in checked_source:
                violations.append((str(path.relative_to(ROOT)), pattern))
    assert violations == []


def test_session_context_active_readers_prefer_canonical_fields() -> None:
    routing_helper = _function_block(ROUTING_PATH, "_session_slot_continuity")
    working_helper = _function_block(WORKING_STATE_PATH, "_session_context_memory")
    bundle_loader = _function_block(SESSION_BUNDLE_HELPER_PATH, "load_session_memory_bundle_for_state")

    assert 'state.get("session_context")' in routing_helper
    assert 'state.get("session_memory")' in routing_helper
    assert routing_helper.index('state.get("session_context")') < routing_helper.index('state.get("session_memory")')

    assert 'state.get("session_context")' in working_helper
    assert 'state.get("session_memory")' in working_helper
    assert working_helper.index('state.get("session_context")') < working_helper.index('state.get("session_memory")')

    assert "session_context_bundle_from_state" in bundle_loader
    assert "session_memory_bundle_from_state" in bundle_loader
    assert bundle_loader.index("session_context_bundle_from_state") < bundle_loader.index(
        "session_memory_bundle_from_state"
    )


def test_reviewed_memory_hint_aliases_are_explicit() -> None:
    routing_source = _source(ROUTING_PATH)
    reviewed_node_source = _source(REVIEWED_MEMORY_NODE_PATH)

    for source in (routing_source, reviewed_node_source):
        assert "needs_reviewed_memory_context" in source
        assert "needs_long_term_memory" in source
    assert 'return [], "memory_context_load", []' in routing_source
    assert 'return [], "long_term_memory_retrieve", []' not in routing_source


def test_runtime_graph_compatibility_node_names_remain() -> None:
    graph_source = _source(GRAPH_PATH)
    vocabulary_source = _source(GRAPH_VOCABULARY_PATH)

    assert 'builder.add_node("session_context_load", session_context_load)' in graph_source
    assert 'builder.add_node("session_memory_load", session_memory_load)' not in graph_source
    assert 'builder.add_node("memory_context_load", memory_context_load)' in graph_source
    assert 'builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)' not in graph_source
    assert '"memory_context_load": "memory_context_load"' in graph_source
    assert '"long_term_memory_retrieve": "long_term_memory_retrieve"' not in graph_source
    for token in (
        '"session_memory_load"',
        '"session_context_load"',
        '"PHASE_53_COMPATIBILITY_ALIAS"',
        '"long_term_memory_retrieve"',
        '"memory_context_load"',
        '"compatibility_alias"',
        '"DELETE_BY_PHASE_58"',
    ):
        assert token in vocabulary_source


def test_deferred_compatibility_names_remain_static_only() -> None:
    _assert_contains(
        DB_MODELS_PATH,
        '__tablename__ = "session_memories"',
        '__tablename__ = "long_term_memories"',
        '__tablename__ = "case_memories"',
        '__tablename__ = "case_working_contexts"',
        '__tablename__ = "conversation_threads"',
        "case_id: Mapped[str | None]",
    )
    _assert_contains(MEMORY_REPOSITORY_PATH, 'LONG_TERM_MEMORY_TYPE = "long_term_fact"')
    _assert_contains(CONFIG_PATH, "session_memory_enabled")
    _assert_contains(
        MEMORY_API_ROUTER_PATH,
        '@router.post("/long-term/preferences"',
        '@router.post("/long-term/{memory_id}/approve"',
    )
    _assert_contains(MEMORY_API_SCHEMA_PATH, 'memory_type: Literal["long_term"]')
    _assert_contains(MEMORY_SEARCH_PATH, "class LegacySessionPrecedentSearchService", "debug-only")


def test_phase48_1_plans_do_not_destructively_rename_memory_surfaces() -> None:
    protected_patterns = (
        r"drop_table\([\"']session_memories[\"']\)",
        r"drop_table\([\"']long_term_memories[\"']\)",
        r"drop_table\([\"']case_memories[\"']\)",
        r"drop_table\([\"']case_working_contexts[\"']\)",
        r"drop_table\([\"']thread_case_links[\"']\)",
        r"drop_column\([\"']conversation_threads[\"'],\s*[\"']case_id[\"']\)",
        r"alter_column\([\"']conversation_threads[\"'],\s*[\"']case_id[\"']",
        r"rename_table\([\"']session_memories[\"']",
        r"\b(delete|remove|rename)\b.*\bsession_memory_load\b",
        r"\b(delete|remove|rename)\b.*\blong_term_memory_retrieve\b",
        r"\b(delete|remove|rename)\b.*\blong_term_fact\b",
        r"\b(delete|remove|rename)\b.*\bsession_memory_enabled\b",
        r"\b(delete|remove|rename)\b.*\b/long-term\b",
        r"\b(delete|remove|rename)\b.*\bLegacySessionPrecedentSearchService\b",
    )
    violations: list[tuple[str, int, str]] = []
    for path in sorted(PHASE48_1_DIR.glob("48.1-*-PLAN.md")):
        for line_number, line in enumerate(_source(path).splitlines(), start=1):
            stripped = line.strip()
            if not stripped or _is_static_guard_meta_line(stripped):
                continue
            for pattern in protected_patterns:
                if re.search(pattern, stripped, flags=re.IGNORECASE):
                    violations.append((path.name, line_number, stripped))

    assert violations == []


def _is_static_guard_meta_line(line: str) -> bool:
    lowered = line.lower()
    if line.startswith(("- `", "|", "pattern:", "contains:", "via:")):
        return True
    return any(
        marker in lowered
        for marker in (
            "acceptance",
            "defer",
            "deferred",
            "do not",
            "exact checks",
            "forbid",
            "forbidden",
            "guard",
            "must not",
            "no destructive",
            "not rename",
            "preserve",
            "protected",
            "reject",
            "remain",
            "retained",
            "static",
            "unchanged",
            "wording",
        )
    )
