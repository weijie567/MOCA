from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRUSTED_CONTEXT_OWNER = ROOT / "src" / "platform" / "trusted_context.py"
PROMPT_PROJECTORS = ROOT / "src" / "agent" / "context" / "projectors.py"
ROUTE_SEAMS = [
    ROOT / "src" / "api" / "routers" / "agent.py",
    ROOT / "src" / "api" / "routers" / "agent_runs.py",
]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _class_defs(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def test_only_platform_module_defines_trusted_context_models() -> None:
    assert TRUSTED_CONTEXT_OWNER.exists()

    definitions: list[tuple[str, str]] = []
    for path in sorted((ROOT / "src").glob("**/*.py")):
        if path.name == "__init__.py":
            continue
        for name in _class_defs(path):
            if name in {"TrustedContext", "MerchantScopeV1", "TrustedContextFactory"}:
                definitions.append((str(path.relative_to(ROOT)), name))

    assert definitions == [
        ("src/platform/trusted_context.py", "MerchantScopeV1"),
        ("src/platform/trusted_context.py", "TrustedContext"),
        ("src/platform/trusted_context.py", "TrustedContextFactory"),
    ]


def test_prompt_projectors_do_not_import_trusted_context_authority() -> None:
    imports = _imports(PROMPT_PROJECTORS)

    assert [module for module in imports if module.startswith("src.platform.trusted_context")] == []
    assert [module for module in imports if module.startswith("src.platform.context_projections")] == []


def test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors() -> None:
    seams = [
        ROOT / "src" / "api" / "routers" / "search.py",
        ROOT / "src" / "api" / "routers" / "agent.py",
        ROOT / "src" / "api" / "routers" / "agent_runs.py",
        ROOT / "src" / "agent" / "nodes" / "investigate.py",
        ROOT / "src" / "agent" / "nodes" / "action_draft.py",
        ROOT / "src" / "tools" / "executors" / "knowledge.py",
    ]
    required_helpers = {
        "TrustedContextFactory",
        "project_to_tool_context",
        "project_to_knowledge_context",
        "project_tool_context_to_knowledge_context",
    }
    violations: list[str] = []

    for path in seams:
        source = path.read_text()
        if not any(helper in source for helper in required_helpers):
            violations.append(f"{path.relative_to(ROOT)} does not use trusted-context projection helpers")
        if "ToolCallContext(" in source or "KnowledgeContext(" in source:
            violations.append(f"{path.relative_to(ROOT)} still directly constructs service context")

    assert violations == []
    assert required_helpers


def test_route_current_run_id_fields_delegate_to_legacy_identity_projection() -> None:
    for path in ROUTE_SEAMS:
        source = path.read_text()

        assert "project_to_legacy_agent_state_identity" in source
        assert '"current_run_id":' not in source
