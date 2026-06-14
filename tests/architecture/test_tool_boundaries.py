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


def test_graph_nodes_do_not_import_legacy_agent_tools_or_raw_integrations() -> None:
    violations: list[tuple[str, str]] = []
    for path in sorted((ROOT / "src" / "agent" / "nodes").glob("*.py")):
        for module in _imports(path):
            if module.startswith(("src.agent.tools", "src.integrations")):
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_no_code_imports_legacy_agent_tools_package() -> None:
    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests"):
        for path in sorted(base.glob("**/*.py")):
            for module in _imports(path):
                if module.startswith("src.agent.tools"):
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_no_code_imports_legacy_business_tools_package() -> None:
    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests"):
        for path in sorted(base.glob("**/*.py")):
            for module in _imports(path):
                if module.startswith("src.business_tools"):
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_no_code_imports_legacy_rag_retriever_facade() -> None:
    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in sorted(base.glob("**/*.py")):
            for module in _imports(path):
                if module == "src.rag.retriever":
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_no_code_imports_legacy_rag_contract_modules() -> None:
    assert not (ROOT / "src" / "rag" / "schemas.py").exists()
    assert not (ROOT / "src" / "rag" / "citation_validator.py").exists()

    violations: list[tuple[str, str]] = []
    forbidden = {"src.rag.schemas", "src.rag.citation_validator"}
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in sorted(base.glob("**/*.py")):
            if path == Path(__file__):
                continue
            for module in _imports(path):
                if module in forbidden:
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_no_code_imports_legacy_knowledge_adapters_package() -> None:
    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in sorted(base.glob("**/*.py")):
            for module in _imports(path):
                if module == "src.knowledge.adapters":
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_legacy_retrieve_policy_evidence_node_is_deleted() -> None:
    assert not (ROOT / "src" / "agent" / "nodes" / "retrieve_policy_evidence.py").exists()

    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in sorted(base.glob("**/*.py")):
            if path == Path(__file__):
                continue
            for module in _import_targets(path):
                if module == "src.agent.nodes.retrieve_policy_evidence":
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_legacy_load_business_context_node_is_deleted() -> None:
    assert not (ROOT / "src" / "agent" / "nodes" / "load_business_context.py").exists()

    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in sorted(base.glob("**/*.py")):
            if path == Path(__file__):
                continue
            for module in _import_targets(path):
                if module == "src.agent.nodes.load_business_context":
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_unified_manager_does_not_import_domain_services_directly() -> None:
    imports = _imports(ROOT / "src" / "tools" / "manager.py")
    forbidden_prefixes = (
        "src.actions.service",
        "src.business.service",
        "src.knowledge.service",
        "src.memory.service",
    )

    assert [module for module in imports if module.startswith(forbidden_prefixes)] == []


def test_domain_packages_do_not_import_graph_nodes_or_tool_manager() -> None:
    violations: list[tuple[str, str]] = []
    for package in ("actions", "business", "knowledge", "memory"):
        for path in sorted((ROOT / "src" / package).glob("**/*.py")):
            for module in _imports(path):
                if module.startswith(("src.agent.nodes", "src.tools.manager")):
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
