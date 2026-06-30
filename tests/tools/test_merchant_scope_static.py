from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
TRUSTED_FACTORY = SRC_ROOT / "platform" / "trusted_context.py"
HIGH_RISK_WILDCARD_SURFACES = (
    SRC_ROOT / "agent" / "graph.py",
    SRC_ROOT / "agent" / "nodes" / "approval_gate.py",
    SRC_ROOT / "agent" / "nodes" / "action_draft.py",
    SRC_ROOT / "agent" / "nodes" / "rag_context_build.py",
    SRC_ROOT / "agent" / "nodes" / "session_memory_load.py",
    SRC_ROOT / "memory" / "service.py",
    SRC_ROOT / "tools" / "runtime.py",
    SRC_ROOT / "approvals" / "service.py",
    SRC_ROOT / "actions" / "drafts.py",
)


def test_production_business_scope_wildcards_stay_inside_trusted_context_factory() -> None:
    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path == TRUSTED_FACTORY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _WildcardMerchantScopeVisitor(path)
        visitor.visit(tree)
        offenders.extend(visitor.offenders)

    assert offenders == []


def test_phase36_high_risk_surfaces_are_covered_by_wildcard_static_scan() -> None:
    missing = [path.relative_to(PROJECT_ROOT).as_posix() for path in HIGH_RISK_WILDCARD_SURFACES if not path.exists()]

    assert missing == []


class _WildcardMerchantScopeVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.offenders: list[str] = []

    def visit_Dict(self, node: ast.Dict) -> None:
        if _dict_has_wildcard_merchant_ids(node):
            self._add(node, 'dict literal with merchant_ids ["*"]')
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg in {"merchant_ids", "server_merchant_scope"} and _contains_wildcard_scope(node.value):
            self._add(node, f"{node.arg} wildcard scope")
        self.generic_visit(node)

    def _add(self, node: ast.AST, reason: str) -> None:
        rel = self.path.relative_to(PROJECT_ROOT)
        self.offenders.append(f"{rel}:{getattr(node, 'lineno', '?')} {reason}")


def _dict_has_wildcard_merchant_ids(node: ast.Dict) -> bool:
    for key, value in zip(node.keys, node.values, strict=True):
        if isinstance(key, ast.Constant) and key.value == "merchant_ids" and _is_wildcard_sequence(value):
            return True
    return False


def _contains_wildcard_scope(node: ast.AST) -> bool:
    if _is_wildcard_sequence(node):
        return True
    if isinstance(node, ast.Dict):
        return _dict_has_wildcard_merchant_ids(node)
    return False


def _is_wildcard_sequence(node: ast.AST) -> bool:
    if not isinstance(node, ast.List | ast.Tuple | ast.Set):
        return False
    return any(isinstance(item, ast.Constant) and item.value == "*" for item in node.elts)
