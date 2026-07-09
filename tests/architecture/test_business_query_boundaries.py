from __future__ import annotations

import ast
from pathlib import Path

from src.agent.nodes.investigate_planner import INVESTIGATE_ALLOWED_TOOL_NAMES
from src.tools.catalog import ToolCatalog, investigate_tool_names


ROOT = Path(__file__).resolve().parents[2]
INVESTIGATE_PATH = ROOT / "src/agent/nodes/investigate.py"
BUSINESS_EXECUTOR_PATH = ROOT / "src/tools/executors/business.py"
BUSINESS_QUERY_COMPILER_PATH = ROOT / "src/business/query/compiler.py"


def _source(path: Path) -> str:
    return path.read_text()


def _tree(path: Path) -> ast.Module:
    return ast.parse(_source(path), filename=str(path))


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.rsplit(".", maxsplit=1)[-1] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _module_matches(module: str, forbidden: str) -> bool:
    return module == forbidden or module.startswith(f"{forbidden}.")


def _call_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_investigate_node_does_not_own_business_query_runtime_dependencies() -> None:
    modules = _imported_modules(INVESTIGATE_PATH)
    names = _imported_names(INVESTIGATE_PATH)

    for forbidden in ("src.repositories", "src.db.models", "src.business.service", "src.business.query.compiler"):
        assert not any(_module_matches(module, forbidden) for module in modules), forbidden
    assert "BusinessFactService" not in names
    assert "BusinessQueryCompiler" not in names


def test_business_tool_executor_delegates_without_query_construction() -> None:
    modules = _imported_modules(BUSINESS_EXECUTOR_PATH)
    calls = _call_names(BUSINESS_EXECUTOR_PATH)

    for forbidden in ("src.repositories", "src.db.models", "src.business.query.compiler"):
        assert not any(_module_matches(module, forbidden) for module in modules), forbidden
    sqlalchemy_modules = {
        module
        for module in modules
        if module == "sqlalchemy" or module.startswith("sqlalchemy.")
    }
    assert sqlalchemy_modules <= {"sqlalchemy.ext.asyncio"}
    assert "invoke_tool" in calls
    assert not calls.intersection(
        {
            "select",
            "text",
            "and_",
            "or_",
            "where",
            "filter",
            "filter_by",
            "join",
            "order_by",
            "limit",
            "offset",
            "execute",
            "scalars",
            "scalar",
        }
    )


def test_business_query_compiler_uses_structured_queries_without_raw_sql_or_generic_lists() -> None:
    modules = _imported_modules(BUSINESS_QUERY_COMPILER_PATH)
    names = _imported_names(BUSINESS_QUERY_COMPILER_PATH)
    calls = _call_names(BUSINESS_QUERY_COMPILER_PATH)
    source = _source(BUSINESS_QUERY_COMPILER_PATH)

    assert "text" not in names
    assert not any(_module_matches(module, "sqlalchemy.sql") for module in modules)
    assert "select" in calls
    assert not calls.intersection({"text", "execute", "exec_driver_sql", "from_statement", "raw_sql"})
    for forbidden in ("raw_sql", "list_all", "find_all", "query_all", "get_all", "generic_list"):
        assert forbidden not in source


def test_business_query_tool_is_consistent_between_catalog_and_investigate_planner() -> None:
    catalog_names = investigate_tool_names(ToolCatalog().descriptors())
    required = {"business_query", "query_business_metric"}

    assert required <= catalog_names
    assert required <= INVESTIGATE_ALLOWED_TOOL_NAMES
    assert catalog_names <= INVESTIGATE_ALLOWED_TOOL_NAMES
