from __future__ import annotations

import ast
from pathlib import Path

import src.agent.safety.taxonomy as taxonomy


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_TAXONOMY_PATH = ROOT / "src" / "agent" / "safety" / "taxonomy.py"
MIGRATED_CALLER_PATHS = (
    ROOT / "src" / "agent" / "nodes" / "risk_gate.py",
    ROOT / "src" / "agent" / "nodes" / "action_draft.py",
    ROOT / "src" / "agent" / "intent_policy.py",
    ROOT / "src" / "agent" / "routing.py",
)
FORBIDDEN_SOURCE_ASSIGNMENT_PARTS = ("ACTIONABLE", "ACTION_TYPES", "WRITE_ACTIONS")
FORBIDDEN_EXACT_TOKENS = (
    "FULL_REFUND_TERMS",
    "ACTIONABLE_ACTIONS",
    "_ACTION_BOUND_INTENTS",
    "english_action_terms",
    "chinese_action_terms",
)
FORBIDDEN_LOCAL_ALIAS_TUPLES = (
    '("execute", "refund now", "override", "compensation", "coupon")',
    '("直接退款", "执行", "发券", "创建", "补偿", "券", "赔付")',
    '("compensation", "coupon")',
    '("补偿", "券", "赔付")',
)
FORBIDDEN_ACTION_TYPE_HARDCODES = (
    '"action_type": "manual_review"',
    '"action_type": "blocked"',
    "action_type='manual_review'",
    "action_type='blocked'",
    'action_type="manual_review"',
    'action_type="blocked"',
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


def test_canonical_safety_taxonomy_owner_exports_migrated_helper_api() -> None:
    assert CANONICAL_TAXONOMY_PATH.exists()

    for helper_name in (
        "canonical_executable_action_type",
        "detect_pre_route_action_request",
        "is_actionable_recommendation",
        "matches_compensation_alias",
        "matches_full_refund_alias",
        "resolve_action_text",
        "risk_assessment_with_disposition",
    ):
        assert hasattr(taxonomy, helper_name)


def test_no_duplicate_action_taxonomy_sources_outside_canonical_owner() -> None:
    violations: list[tuple[str, int, str]] = []
    for path in MIGRATED_CALLER_PATHS:
        for node in ast.walk(_tree(path)):
            target_names = _assignment_target_names(node)
            if not target_names or not _is_collection_source_value(node):
                continue
            for name in target_names:
                if name.startswith("NON_EXECUTABLE"):
                    continue
                if name in {"NO_ACTION_RECOMMENDATIONS", "APPROVAL_DECISION_TYPES"}:
                    continue
                if name in FORBIDDEN_EXACT_TOKENS or any(part in name for part in FORBIDDEN_SOURCE_ASSIGNMENT_PARTS):
                    violations.append((_relative(path), getattr(node, "lineno", 0), name))

    assert violations == []


def test_no_local_canonical_action_type_functions_outside_taxonomy_owner() -> None:
    violations: list[tuple[str, str]] = []
    for path in MIGRATED_CALLER_PATHS:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "_canonical_action_type":
                violations.append((_relative(path), node.name))

    assert violations == []


def test_no_local_pre_route_or_compensation_alias_tuples_outside_taxonomy_owner() -> None:
    violations: list[tuple[str, int, str]] = []
    for path in MIGRATED_CALLER_PATHS:
        for line_no, line in enumerate(_source(path).splitlines(), start=1):
            stripped = line.strip()
            for token in (*FORBIDDEN_EXACT_TOKENS, *FORBIDDEN_LOCAL_ALIAS_TUPLES):
                if token in stripped:
                    violations.append((_relative(path), line_no, token))

    assert violations == []


def test_non_executable_dispositions_are_not_hardcoded_as_action_types_outside_taxonomy_owner() -> None:
    violations: list[tuple[str, int, str]] = []
    for path in MIGRATED_CALLER_PATHS:
        for line_no, line in enumerate(_source(path).splitlines(), start=1):
            stripped = line.strip()
            for token in FORBIDDEN_ACTION_TYPE_HARDCODES:
                if token in stripped:
                    violations.append((_relative(path), line_no, token))

    assert violations == []
