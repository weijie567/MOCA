from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"
DB_MODELS_PATH = ROOT / "src" / "db" / "models.py"
SEMANTIC_EPISODE_PATH = ROOT / "src" / "memory" / "semantic_episode.py"
REPOSITORY_PATH = ROOT / "src" / "memory" / "repository.py"
PHASE48_DIR = ROOT / ".planning" / "phases" / "48-narrow-long-term-explicit-preference-memory"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _contract_long_term_section() -> str:
    return _between(_source(CONTRACT_SPEC_PATH), "### 13.3 Long-term memory", "### 13.4 Case memory")


def test_phase48_contract_says_long_term_is_explicit_preference_only() -> None:
    section = _contract_long_term_section()

    for expected in (
        "Long-term memory stores explicit preference memory only",
        "explicit preference memory only",
        "explicit_user_preference",
        "explicit_admin_preference",
        "human_reviewed",
        "semantic_episode_candidate",
        "needs_review",
        "source_type",
        "memory_type='long_term_fact'",
    ):
        assert expected in section


def test_phase48_contract_forbids_long_term_business_state_policy_authority_and_run_summary() -> None:
    section = _contract_long_term_section()

    for expected in (
        "not operational business state",
        "not policy authority",
        "not approval/action authority",
        "not generic run summary storage",
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
        "run summaries",
        "strategy hints",
        "similar-case hints",
        "cross-case pattern candidates",
    ):
        assert expected in section


def test_phase48_preserves_memory_storage_identity() -> None:
    models = _source(DB_MODELS_PATH)

    for expected in (
        '__tablename__ = "long_term_memories"',
        '__tablename__ = "case_memories"',
        '__tablename__ = "session_memories"',
        '__tablename__ = "case_working_contexts"',
        '__tablename__ = "thread_case_links"',
    ):
        assert expected in models
    assert "class ConversationThread" in models
    assert "case_id: Mapped[str | None]" in models

    unsafe_patterns = (
        r"\bdrop_table\b",
        r"\brename_table\b",
        r"\bdrop_column\b",
        r"\brename_column\b",
        r"\bDROP\s+TABLE\b",
        r"\bALTER\s+TABLE\b.*\bRENAME\b",
    )
    violations: list[tuple[str, int, str]] = []
    for path in sorted(PHASE48_DIR.glob("48-*-PLAN.md")):
        for line_number, line in _planning_prose_lines(path):
            lowered = line.lower()
            if not any(
                term in lowered
                for term in (
                    "long_term_memories",
                    "case_memories",
                    "session_memories",
                    "case_working_contexts",
                    "thread_case_links",
                    "conversation_threads.case_id",
                )
            ):
                continue
            if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in unsafe_patterns):
                violations.append((path.name, line_number, line.strip()))

    assert violations == []


def test_phase48_plans_use_project_pytest_entrypoint() -> None:
    checked_paths = sorted(PHASE48_DIR.glob("48-*.md"))
    snippets: list[tuple[Path, str]] = []
    for path in checked_paths:
        snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

    assert snippets
    for path, snippet in snippets:
        assert snippet.startswith("UV_CACHE_DIR=/tmp/uv-cache uv run pytest"), (path.name, snippet)


def test_phase48_semantic_episode_source_mentions_only_preference_candidate_projection() -> None:
    source = _strip_python_comments(_source(SEMANTIC_EPISODE_PATH))
    projection_section = _between(source, "_SUMMARY_KEYS", "class SemanticEpisodeCandidate")

    assert "preference_candidate" in projection_section
    for forbidden in ("cross_case_pattern", "similar_case_hint", "strategy_hint"):
        assert forbidden not in projection_section


def test_phase48_retrieval_filters_published_preference_sources() -> None:
    source = _strip_python_comments(_source(REPOSITORY_PATH))
    retrieve_section = _between(source, "async def retrieve_profile_memory", "def _search_terms")

    assert "PUBLISHED_LONG_TERM_SOURCE_TYPES" in retrieve_section
    assert 'LongTermMemory.memory_kind == "preference"' in retrieve_section
    assert "LongTermMemory.source_type.in_" in retrieve_section


def _planning_prose_lines(path: Path) -> list[tuple[int, str]]:
    source = _strip_fenced_code(_strip_excluded_plan_sections(_source(path)))
    lines: list[tuple[int, str]] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if stripped.startswith(("|", "- path:", "from:", "to:", "via:", "pattern:")):
            continue
        if any(
            marker in lowered
            for marker in (
                "do not",
                "must not",
                "forbid",
                "forbidden",
                "not rename",
                "not renamed",
                "no destructive",
                "unsafe imperative matches",
                "preserve",
                "preserved",
                "unchanged",
            )
        ):
            continue
        lines.append((line_number, stripped))
    return lines


def _strip_fenced_code(source: str) -> str:
    return re.sub(r"```.*?```", "", source, flags=re.DOTALL)


def _strip_python_comments(source: str) -> str:
    return re.sub(r"(?m)^\s*#.*$", "", source)


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
