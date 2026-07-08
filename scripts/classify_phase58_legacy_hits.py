from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


LEGACY_TERMS = (
    "classify_intent",
    "intent_classification",
    "session_memory_load",
    "extract_slots",
    "long_term_memory_retrieve",
    "generate_recommendation",
    "assess_risk_and_approval",
    "route_after_intent",
    "route_after_slots",
)
DEFAULT_ROOTS = (
    "README.md",
    "docs",
    "src",
    "tests",
    "frontend",
    "scripts",
    "eval",
    "rules",
    ".planning/ARCHITECTURE-DEBT.md",
    ".planning/ROADMAP.md",
    ".planning/REQUIREMENTS.md",
    ".planning/STATE.md",
    ".planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup",
)
PHASE58_DIR = ".planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup"
EXCLUDED_RELATIVE_PATHS = frozenset({f"{PHASE58_DIR}/58-VALIDATION.md"})
SKIPPED_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "node_modules",
    }
)
CURRENT_DOC_PATHS = frozenset(
    {
        "README.md",
        "docs/architecture-overview.md",
        "docs/contract-spec.md",
        "docs/current-langgraph-architecture.md",
        "docs/target-agent-platform-architecture-plan.md",
    }
)
HISTORICAL_PROJECTION_PATHS = frozenset(
    {
        "src/agent/graph_vocabulary.py",
        "src/agent/rag_context/claims.py",
        "src/agent/trace.py",
        "src/api/routers/agent_runs.py",
        "src/api/routers/approvals.py",
        "src/api/routers/traces.py",
        "src/repositories/trace_repo.py",
        "frontend/src/components/timeline/TimelineStep.tsx",
    }
)
Category = Literal[
    "active_runtime_legacy",
    "current_docs_legacy_authority",
    "historical_data_read_projection",
    "legacy_wrapper_or_import_test",
    "tracked_build_metadata",
    "previous_state_documentation",
    "phase58_cleanup_artifact",
    "classifier_implementation",
    "unclassified",
]


@dataclass(frozen=True)
class HitRow:
    path: str
    line: int
    terms: tuple[str, ...]
    category: Category
    text: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify Phase 58 legacy graph-name references. "
            "Documented command: UV_CACHE_DIR=/tmp/uv-cache uv run python "
            "scripts/classify_phase58_legacy_hits.py --strict"
        )
    )
    parser.add_argument("--strict", action="store_true", help="Fail on active/current/unclassified rows.")
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=list(DEFAULT_ROOTS),
        help="Root files/directories relative to --root.",
    )
    args = parser.parse_args(argv)

    report = classify_legacy_hits(Path(args.root), args.roots)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

    if args.strict and (
        report["active_runtime_legacy"] > 0
        or report["current_docs_legacy_authority"] > 0
        or report["unclassified_rows"] > 0
    ):
        print(
            "strict mode failed: active_runtime_legacy, current_docs_legacy_authority, "
            "and unclassified_rows must all be zero",
            file=sys.stderr,
        )
        return 1
    return 0


def classify_legacy_hits(root: Path, roots: list[str]) -> dict[str, object]:
    resolved_root = root.resolve()
    rows: list[HitRow] = []
    for path in _iter_scan_files(resolved_root, roots):
        relative_path = _relative_path(path, resolved_root)
        if relative_path in EXCLUDED_RELATIVE_PATHS:
            continue
        for line_number, line in _iter_text_lines(path):
            terms = tuple(term for term in LEGACY_TERMS if term in line)
            if not terms:
                continue
            category = _classify_row(relative_path, line, terms)
            rows.append(
                HitRow(
                    path=relative_path,
                    line=line_number,
                    terms=terms,
                    category=category,
                    text=line.strip(),
                )
            )

    category_counts = Counter(row.category for row in rows)
    files_with_hits = {row.path for row in rows}
    unclassified = [row for row in rows if row.category == "unclassified"]
    active_runtime = [row for row in rows if row.category == "active_runtime_legacy"]
    current_docs = [row for row in rows if row.category == "current_docs_legacy_authority"]
    return {
        "total_hits": len(rows),
        "files": len(files_with_hits),
        "category_counts": dict(sorted(category_counts.items())),
        "active_runtime_legacy": len(active_runtime),
        "current_docs_legacy_authority": len(current_docs),
        "unclassified_rows": len(unclassified),
        "excluded_paths": sorted(EXCLUDED_RELATIVE_PATHS),
        "sample_rows": [asdict(row) for row in rows[:25]],
        "active_runtime_rows": [asdict(row) for row in active_runtime[:25]],
        "current_docs_rows": [asdict(row) for row in current_docs[:25]],
        "unclassified_row_samples": [asdict(row) for row in unclassified[:25]],
    }


def _iter_scan_files(root: Path, roots: list[str]):
    for configured_root in roots:
        path = (root / configured_root).resolve()
        if not _is_relative_to(path, root) or not path.exists():
            continue
        if path.is_file():
            yield path
            continue
        for candidate in sorted(path.rglob("*")):
            if not candidate.is_file():
                continue
            if SKIPPED_DIR_NAMES.intersection(candidate.relative_to(root).parts):
                continue
            yield candidate


def _iter_text_lines(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for line_number, line in enumerate(text.splitlines(), start=1):
        yield line_number, line


def _classify_row(path: str, line: str, terms: tuple[str, ...]) -> Category:
    normalized = path.replace("\\", "/")
    stripped = line.strip()
    lowered = stripped.lower()

    if normalized == "scripts/classify_phase58_legacy_hits.py":
        return "classifier_implementation"
    if normalized.startswith(f"{PHASE58_DIR}/"):
        return "phase58_cleanup_artifact"
    if normalized.startswith("moca.egg-info/") or normalized == "moca.egg-info/SOURCES.txt":
        return "tracked_build_metadata"
    if _is_active_runtime_row(normalized, stripped, terms):
        return "active_runtime_legacy"
    if normalized in CURRENT_DOC_PATHS and _looks_like_current_docs_authority(lowered):
        return "current_docs_legacy_authority"
    if normalized in HISTORICAL_PROJECTION_PATHS:
        return "historical_data_read_projection"
    if normalized.startswith(".planning/"):
        return "previous_state_documentation"
    if normalized.startswith("src/agent/nodes/"):
        return "legacy_wrapper_or_import_test"
    if normalized == "src/agent/routing.py":
        return "legacy_wrapper_or_import_test"
    if normalized.startswith("tests/"):
        return "legacy_wrapper_or_import_test"
    if normalized.startswith(("eval/", "rules/")):
        return "legacy_wrapper_or_import_test"
    if normalized.startswith("scripts/"):
        return "legacy_wrapper_or_import_test"
    if normalized.startswith("docs/") or normalized == "README.md":
        return "previous_state_documentation"
    return "unclassified"


def _is_active_runtime_row(path: str, line: str, terms: tuple[str, ...]) -> bool:
    quoted_terms = [f'"{term}"' for term in terms] + [f"'{term}'" for term in terms]
    if path == "src/agent/graph.py" and any(token in line for token in quoted_terms):
        return True
    if path == "src/agent/routing.py":
        if re.match(r"def route_after_(intent|slots)\(", line):
            return True
        if any(token in line for token in quoted_terms) and not re.match(r"def _route_after_(intent|slots)\(", line):
            return True
    return False


def _looks_like_current_docs_authority(lowered_line: str) -> bool:
    authority_markers = (
        "active",
        "current",
        "registered",
        "runtime",
        "route",
        "当前",
        "现行",
        "注册",
        "路由",
    )
    historical_markers = (
        "compatibility",
        "historical",
        "history",
        "legacy",
        "current-to-target",
        "no longer",
        "not active",
        "not current",
        "migration matrix",
        "migration needed",
        "phase 58",
        "semantic alias",
        "为什么当前",
        "会变胖",
        "不再",
        "历史",
        "兼容",
        "旧",
        "迁移",
        "容易膨胀",
    )
    return any(marker in lowered_line for marker in authority_markers) and not any(
        marker in lowered_line for marker in historical_markers
    )


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
