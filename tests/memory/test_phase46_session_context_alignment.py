from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"
DB_MODELS_PATH = ROOT / "src" / "db" / "models.py"
SESSION_MEMORY_MIGRATION_PATH = ROOT / "src" / "db" / "migrations" / "versions" / "007_session_memories.py"
PHASE46_DIR = ROOT / ".planning" / "phases" / "46-session-context-repositioning"


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


def _session_storage_rows() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "session_memories\n", "long_term_memories\n")


def test_contract_documents_post_cwc_session_context_boundary() -> None:
    section = "\n".join((_section_13_2(), _section_13_4(), _section_13_4a(), _session_storage_rows()))

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

    violations: list[tuple[str, str]] = []
    for path, source in checked_sources:
        for pattern in destructive_patterns:
            if re.search(pattern, source):
                violations.append((path.name, pattern))

    assert violations == []
