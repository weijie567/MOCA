from __future__ import annotations

import ast
from pathlib import Path

import src.agent.rag_context.risk_labels as risk_labels


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RAG_RISK_LABEL_PATH = ROOT / "src" / "agent" / "rag_context" / "risk_labels.py"
CANONICAL_RAG_RISK_LABEL_MODULE = "src.agent.rag_context.risk_labels"
MIGRATED_CALLER_PATHS = (
    ROOT / "src" / "agent" / "rag_context" / "builder.py",
    ROOT / "src" / "agent" / "rag_context" / "metrics.py",
    ROOT / "src" / "agent" / "rag_context" / "verifier.py",
    ROOT / "src" / "agent" / "rag_context" / "routing.py",
    ROOT / "src" / "agent" / "nodes" / "recommendation_generation.py",
)
FORBIDDEN_LOCAL_SOURCE_NAMES = {
    "_ROUTE_MANUAL_REVIEW_REASONS",
    "_ROUTE_STALE_OR_OCR_REASONS",
    "_ROUTING_RISK_LABELS",
    "_SAFE_EVIDENCE_RISK_LABELS",
    "_SAFE_RISK_LABELS",
}
REGISTRY_IMPORT_NAMES = {
    "ROUTE_MANUAL_REVIEW_REASONS",
    "ROUTE_STALE_OR_OCR_REASONS",
    "filter_prompt_safe_risk_labels",
    "filter_safe_evidence_risk_labels",
    "metric_level3_trigger_labels",
    "requires_semantic_review_for_risk_hints",
    "routing_risk_labels",
}
CANONICAL_RAG_RISK_LABEL_STRINGS = frozenset(
    risk_labels.SAFE_EVIDENCE_RISK_LABELS
    | risk_labels.SEMANTIC_REVIEW_RISK_LABELS
    | risk_labels.MANUAL_REVIEW_TRIGGER_RISK_LABELS
    | risk_labels.ROUTING_RISK_LABELS
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.AST:
    return ast.parse(_source(path))


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _assignment_target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Assign):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _is_collection_source_value(node: ast.AST) -> bool:
    value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
    return isinstance(value, ast.Tuple | ast.List | ast.Set | ast.Dict | ast.Call | ast.GeneratorExp | ast.SetComp)


def _canonical_risk_label_strings_in(node: ast.AST) -> list[str]:
    strings = {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and child.value in CANONICAL_RAG_RISK_LABEL_STRINGS
    }
    return sorted(strings)


def _is_local_risk_label_source_set(node: ast.AST) -> bool:
    if isinstance(node, ast.Tuple | ast.List | ast.Set | ast.Dict):
        return len(_canonical_risk_label_strings_in(node)) >= 2
    if isinstance(node, ast.Assign | ast.AnnAssign) and _is_collection_source_value(node):
        return len(_canonical_risk_label_strings_in(node)) >= 2
    return False


def test_canonical_rag_risk_label_owner_exports_expected_helper_api() -> None:
    assert CANONICAL_RAG_RISK_LABEL_PATH.exists()
    for helper_name in (
        "MANUAL_REVIEW_TRIGGER_RISK_LABELS",
        "METRIC_LEVEL3_TRIGGER_LABELS",
        "PROMPT_SAFE_RISK_LABELS",
        "RAG_RISK_LABEL_REGISTRY",
        "ROUTE_MANUAL_REVIEW_REASONS",
        "ROUTE_STALE_OR_OCR_REASONS",
        "ROUTING_RISK_LABELS",
        "SAFE_EVIDENCE_RISK_LABELS",
        "SEMANTIC_REVIEW_RISK_LABELS",
        "filter_prompt_safe_risk_labels",
        "filter_safe_evidence_risk_labels",
        "metric_level3_trigger_labels",
        "requires_semantic_review_for_risk_hints",
        "routing_risk_labels",
    ):
        assert hasattr(risk_labels, helper_name)


def test_no_duplicate_rag_risk_label_source_sets_outside_registry() -> None:
    violations: list[tuple[str, int, str, str]] = []
    for path in MIGRATED_CALLER_PATHS:
        for node in ast.walk(_tree(path)):
            target_names = _assignment_target_names(node)
            if target_names and _is_collection_source_value(node):
                for name in target_names:
                    if name in FORBIDDEN_LOCAL_SOURCE_NAMES:
                        violations.append(
                            (_relative(path), getattr(node, "lineno", 0), name, "retired local source name")
                        )
            if _is_local_risk_label_source_set(node):
                labels = ", ".join(_canonical_risk_label_strings_in(node))
                names = ", ".join(target_names) if target_names else type(node).__name__
                violations.append((_relative(path), getattr(node, "lineno", 0), names, labels))

    assert violations == []


def test_rag_risk_label_helpers_are_imported_from_canonical_owner() -> None:
    violations: list[tuple[str, int, str, str | None]] = []
    for path in MIGRATED_CALLER_PATHS:
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.ImportFrom):
                continue
            imported_names = {alias.name for alias in node.names}
            registry_names = imported_names & REGISTRY_IMPORT_NAMES
            if registry_names and node.module != CANONICAL_RAG_RISK_LABEL_MODULE:
                violations.append(
                    (
                        _relative(path),
                        getattr(node, "lineno", 0),
                        ", ".join(sorted(registry_names)),
                        node.module,
                    )
                )

    assert violations == []
