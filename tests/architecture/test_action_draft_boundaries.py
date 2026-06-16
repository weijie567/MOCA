from __future__ import annotations

import ast
import re
from pathlib import Path

from src.tools.catalog import ToolCatalog
from src.tools.manager import _side_effect_allowed


ROOT = Path(__file__).resolve().parents[2]
NODE_PATH = ROOT / "src" / "agent" / "nodes" / "action_draft.py"
SHIM_PATH = ROOT / "src" / "agent" / "nodes" / "execute_action.py"
CATALOG_PATH = ROOT / "src" / "tools" / "catalog.py"
MANAGER_PATH = ROOT / "src" / "tools" / "manager.py"


def _source(path: Path) -> str:
    return path.read_text()


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def test_action_draft_node_is_canonical_entrypoint() -> None:
    assert NODE_PATH.exists()
    source = _source(NODE_PATH)

    assert "async def action_draft" in source
    assert "caller_node=\"action_draft\"" in source
    assert "draft_outcome" in source
    assert "execution_mode" in source
    assert "not_executed_demo" in source


def test_execute_action_is_phase14_compatibility_shim_only() -> None:
    source = _source(SHIM_PATH)

    assert "Phase 14 compatibility shim" in source
    assert "Phase 15 Replay Event Contract" in source
    assert "2026-07-16" in source
    assert "execute_action" in _function_names(SHIM_PATH)
    assert "return await action_draft(state, config)" in source
    for forbidden in ("UnifiedToolManager", "ActionToolExecutor", "ActionService", "ActionDraftRepository"):
        assert forbidden not in source


def test_action_result_compatibility_is_draft_only_not_success_sentinel() -> None:
    source = _source(NODE_PATH)

    assert "action_result" in source
    assert "draft_outcome" in source
    assert "Phase 15 Replay Event Contract" in source
    assert re.search(r"action_result.*status.*success|status.*success.*action_result", source) is None


def test_create_coupon_grant_draft_is_node_only_for_action_draft() -> None:
    descriptor = next(
        descriptor
        for descriptor in ToolCatalog().descriptors()
        if descriptor.name == "create_coupon_grant_draft"
    )

    assert descriptor.caller_allowlist == ["action_draft"]
    assert descriptor.exposure == "node_only"
    assert descriptor.requires_safety_snapshot is True
    assert _side_effect_allowed("action_draft", descriptor) is True
    assert _side_effect_allowed("execute_action", descriptor) is False
    assert "caller_allowlist=[\"action_draft\"]" in _source(CATALOG_PATH)
    assert 'caller_node == "action_draft"' in _source(MANAGER_PATH)
