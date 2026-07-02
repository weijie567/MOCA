from __future__ import annotations

import ast
import re
from pathlib import Path

from src.agent.working_state import project_working_state
from src.tools.catalog import ToolCatalog
from src.tools.policy import _side_effect_allowed


ROOT = Path(__file__).resolve().parents[2]
NODE_PATH = ROOT / "src" / "agent" / "nodes" / "action_draft.py"
SHIM_PATH = ROOT / "src" / "agent" / "nodes" / "execute_action.py"
CATALOG_PATH = ROOT / "src" / "tools" / "catalog.py"
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
POLICY_PATH = ROOT / "src" / "tools" / "policy.py"
SOURCE_ROOTS = (
    ROOT / "src" / "actions",
    ROOT / "src" / "agent",
    ROOT / "src" / "api",
    ROOT / "src" / "repositories",
    ROOT / "src" / "tools",
)
ACTION_RESULT_SUCCESS_PATTERN = re.compile(r"action_result.*status.*success|status.*success.*action_result")
FORBIDDEN_EXTERNAL_IMPORT_PARTS = (
    "external_adapter",
    "external_adapters",
    "action_outbox",
    "outbox_worker",
    "reconciliation",
    "compensation",
)


def _source(path: Path) -> str:
    return path.read_text()


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(_source(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def test_action_draft_node_is_canonical_entrypoint() -> None:
    assert NODE_PATH.exists()
    source = _source(NODE_PATH)

    assert "async def action_draft" in source
    assert 'caller_node="action_draft"' in source
    assert "draft_outcome" in source
    assert "execution_mode" in source
    assert "not_executed_demo" in source
    for required in (
        "target_merchant_id",
        "business_fact_refs",
        "verified_evidence_refs",
        "claim_verification_ref",
        "risk_decision_ref",
    ):
        assert required in source


def test_execute_action_is_phase14_compatibility_shim_only() -> None:
    source = _source(SHIM_PATH)

    assert "Phase 14 compatibility shim" in source
    assert "Owner: Phase 14 action-draft-boundary" in source
    assert "Phase 15 Replay Event Contract" in source
    assert "2026-07-16" in source
    assert "execute_action" in _function_names(SHIM_PATH)
    assert "return await action_draft(state, config)" in source
    for forbidden in ("ActionToolExecutor", "ActionService", "ActionDraftRepository"):
        assert forbidden not in source


def test_action_result_compatibility_is_draft_only_not_success_sentinel() -> None:
    source = _source(NODE_PATH)

    assert "action_result" in source
    assert "draft_outcome" in source
    assert "Phase 15 Replay Event Contract" in source
    assert re.search(r"action_result.*status.*success|status.*success.*action_result", source) is None


def test_create_coupon_grant_draft_is_node_only_for_action_draft() -> None:
    descriptor = next(
        descriptor for descriptor in ToolCatalog().descriptors() if descriptor.name == "create_coupon_grant_draft"
    )

    assert descriptor.caller_allowlist == ["action_draft"]
    assert descriptor.exposure == "node_only"
    assert descriptor.requires_safety_snapshot is True
    assert _side_effect_allowed("action_draft", descriptor) is True
    assert _side_effect_allowed("execute_action", descriptor) is False
    assert 'caller_allowlist=("action_draft",)' in _source(CATALOG_PATH)
    assert 'caller_node == "action_draft"' in _source(POLICY_PATH)


def test_graph_registers_canonical_action_draft_node_only() -> None:
    source = _source(GRAPH_PATH)

    assert "from src.agent.nodes.action_draft import action_draft" in source
    assert "from src.agent.nodes.execute_action import execute_action" not in source
    assert 'add_node("action_draft", action_draft)' in source
    assert 'add_node("execute_action"' not in source
    assert '"action_draft": "action_draft"' in source
    assert '"execute_action": "execute_action"' not in source
    assert 'add_edge("action_draft", "final_response")' in source


def test_source_does_not_import_execute_action_shim_outside_shim() -> None:
    violations: list[tuple[str, str]] = []
    for path in sorted((ROOT / "src").glob("**/*.py")):
        if path == SHIM_PATH:
            continue
        for module in _import_targets(path):
            if module in {"src.agent.nodes.execute_action", "src.agent.nodes.execute_action.execute_action"}:
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_graph_does_not_depend_on_action_result_success_sentinel() -> None:
    source = _source(GRAPH_PATH)

    assert ACTION_RESULT_SUCCESS_PATTERN.search(source) is None


def test_demo_action_sources_do_not_import_external_execution_paths() -> None:
    violations: list[tuple[str, str]] = []
    for root in SOURCE_ROOTS:
        for path in sorted(root.glob("**/*.py")):
            for module in _import_targets(path):
                normalized = module.lower()
                if any(part in normalized for part in FORBIDDEN_EXTERNAL_IMPORT_PARTS):
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_source_does_not_depend_on_action_result_success_sentinel() -> None:
    allowed = {
        "src/agent/nodes/action_draft.py",  # compatibility output construction only; guarded above.
    }
    violations: list[tuple[str, int, str]] = []
    for root in SOURCE_ROOTS:
        for path in sorted(root.glob("**/*.py")):
            relative = str(path.relative_to(ROOT))
            if relative in allowed:
                continue
            for line_no, line in enumerate(_source(path).splitlines(), start=1):
                if ACTION_RESULT_SUCCESS_PATTERN.search(line):
                    violations.append((relative, line_no, line.strip()))

    assert violations == []


def test_working_state_exposes_only_safe_action_draft_artifact() -> None:
    working_state = project_working_state(
        {
            "thread_id": "thread-action-boundary",
            "current_run_id": "run-action-boundary",
            "action_draft": {
                "draft_id": "draft-001",
                "action_type": "coupon_grant",
                "status": "draft_created",
                "summary": "Created a demo coupon draft.",
                "target_merchant_id": "merchant-1",
                "business_fact_refs": [{"resource_id": "RF-1001"}],
                "verified_evidence_refs": [{"evidence_id": "policy/chunk-001@v1"}],
                "claim_verification_ref": "claim_verification_bundle/bundle-1",
                "risk_decision_ref": "risk_decision/run-001/action-001",
                "payload": {"amount": 50, "secret": "ACTION_PAYLOAD_SHOULD_NOT_APPEAR"},
                "proposed_action": {"body": "PROPOSED_ACTION_SHOULD_NOT_APPEAR"},
                "snapshot_json": {"secret": "SNAPSHOT_JSON_SHOULD_NOT_APPEAR"},
                "edited_action_json": {"secret": "EDITED_ACTION_SHOULD_NOT_APPEAR"},
                "safety_snapshot_hash": "SAFETY_HASH_SHOULD_NOT_APPEAR",
            },
            "draft_outcome": {
                "status": "not_executed_demo",
                "payload": {"secret": "DRAFT_OUTCOME_SHOULD_NOT_APPEAR"},
            },
        }
    )

    dumped = working_state.model_dump(mode="json")
    serialized = working_state.model_dump_json()

    assert dumped["draft_artifact"] == {
        "draft_id": "draft-001",
        "action_type": "coupon_grant",
        "status": "draft_created",
        "summary": "Created a demo coupon draft.",
        "target_merchant_id": "merchant-1",
        "business_fact_ref_count": 1,
        "verified_evidence_ref_count": 1,
        "claim_verification_ref": "claim_verification_bundle/bundle-1",
        "risk_decision_ref": "risk_decision/run-001/action-001",
    }
    for forbidden in (
        "action_draft",
        "payload",
        "ACTION_PAYLOAD_SHOULD_NOT_APPEAR",
        "proposed_action",
        "PROPOSED_ACTION_SHOULD_NOT_APPEAR",
        "snapshot_json",
        "SNAPSHOT_JSON_SHOULD_NOT_APPEAR",
        "edited_action_json",
        "EDITED_ACTION_SHOULD_NOT_APPEAR",
        "safety_snapshot_hash",
        "SAFETY_HASH_SHOULD_NOT_APPEAR",
        "draft_outcome",
        "DRAFT_OUTCOME_SHOULD_NOT_APPEAR",
    ):
        assert forbidden not in serialized
