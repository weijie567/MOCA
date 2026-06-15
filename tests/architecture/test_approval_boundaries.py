from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def test_approval_routers_do_not_import_legacy_approval_repository() -> None:
    violations: list[tuple[str, str]] = []
    for path in (
        ROOT / "src" / "api" / "routers" / "approvals.py",
        ROOT / "src" / "api" / "routers" / "agent.py",
        ROOT / "src" / "api" / "routers" / "agent_runs.py",
    ):
        for module in _imports(path):
            if module == "src.repositories.approval_repo" or module.startswith(
                "src.repositories.approval_repo."
            ):
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_approval_transition_methods_are_not_imported_outside_approvals_package() -> None:
    violations: list[tuple[str, str]] = []
    compatibility_path = ROOT / "src" / "repositories" / "approval_repo.py"
    for base in (ROOT / "src", ROOT / "tests"):
        for path in sorted(base.glob("**/*.py")):
            if path == compatibility_path:
                continue
            for module in _import_targets(path):
                if module in {
                    "src.repositories.approval_repo",
                    "src.repositories.approval_repo.ApprovalRepository",
                }:
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_graph_nodes_do_not_import_raw_action_or_business_adapters_for_approval() -> None:
    violations: list[tuple[str, str]] = []
    forbidden_prefixes = (
        "src.actions.drafts",
        "src.actions.service",
        "src.business",
        "src.business_tools",
        "src.integrations",
        "src.repositories.approval_repo",
    )
    for path in sorted((ROOT / "src" / "agent" / "nodes").glob("*.py")):
        for module in _imports(path):
            if module.startswith(forbidden_prefixes):
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_approval_service_is_canonical_transition_owner() -> None:
    service_path = ROOT / "src" / "approvals" / "service.py"
    assert service_path.exists()
    classes = [
        node.name
        for node in ast.walk(ast.parse(service_path.read_text()))
        if isinstance(node, ast.ClassDef)
    ]

    assert "ApprovalService" in classes
