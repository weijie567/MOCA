from __future__ import annotations

import ast
import re
from pathlib import Path

from src.agent import graph_vocabulary

ROOT = Path(__file__).resolve().parents[2]
APPROVAL_GATE_PATH = ROOT / "src" / "agent" / "nodes" / "approval_gate.py"
APPROVALS_ROUTER_PATH = ROOT / "src" / "api" / "routers" / "approvals.py"
AGENT_RUNS_TEST_PATH = ROOT / "tests" / "test_agent_runs_api.py"
CONTEXT_PATH = ROOT / ".planning" / "phases" / "34-approval-and-actiondraft-boundary-hardening" / "34-CONTEXT.md"
FINAL_RESPONSE_PATH = ROOT / "src" / "agent" / "nodes" / "final_response.py"
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
SRC_ROOT = ROOT / "src"
FORBIDDEN_EXECUTION_TABLES = (
    "action_executions",
    "action_outbox_events",
    "action_reconciliation_jobs",
    "action_compensation_records",
)
FORBIDDEN_EXECUTION_CLASSES = (
    "ActionExecution",
    "ActionOutbox",
    "Outbox",
    "Reconciliation",
    "Compensation",
)
PHASE64_5_NON_EXECUTION_PROJECTION_CLASSES = frozenset({"ProjectionReconciliationViewV1"})
FORBIDDEN_EXECUTION_WORDING = ("已发券", "已退款", "已关闭工单", "coupon issued", "refund completed", "ticket closed")


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_phase34_risk_gate_legacy_name_is_historical_projection_only() -> None:
    entry = graph_vocabulary.graph_vocabulary_entry("assess_risk_and_approval", kind="node")
    projected = graph_vocabulary.project_trace_step_for_contract({"node": "assess_risk_and_approval"})

    assert entry is None
    assert graph_vocabulary.target_graph_name("assess_risk_and_approval", kind="node") == "assess_risk_and_approval"
    assert projected["implementation_node"] == "assess_risk_and_approval"
    assert projected["target_node"] == "risk_gate"
    assert projected["target_graph_status"] == "historical_projection"
    assert projected["target_graph_status"] != "compatibility_alias"
    assert projected["target_graph_runnable"] is False


def test_phase34_route_after_risk_is_runtime_router() -> None:
    entry = graph_vocabulary.graph_vocabulary_entry("route_after_risk", kind="router")

    assert entry is not None
    assert entry.target_name == "route_after_risk"
    assert entry.status == "runtime"
    assert entry.runnable is True


def test_phase34_approval_gate_does_not_own_risk_policy_routing() -> None:
    source = _source(APPROVAL_GATE_PATH)

    assert "auto_allowed" not in source
    assert "approval_required" not in source
    assert "blocked" not in source
    assert '"action_draft"' not in source
    assert "'action_draft'" not in source


def test_phase34_approval_resume_does_not_widen_manager_scope_with_wildcard_or_requested_by_shortcut() -> None:
    source = _source(APPROVALS_ROUTER_PATH)

    assert "server_merchant_scope" not in source
    assert re.search(r"requested_by.*merchant", source) is None
    assert re.search(r"merchant_id.*requested_by", source) is None


def test_phase34_production_does_not_define_real_execution_tables_or_workers() -> None:
    violations: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ClassDef)
                and node.name not in PHASE64_5_NON_EXECUTION_PROJECTION_CLASSES
                and any(part in node.name for part in FORBIDDEN_EXECUTION_CLASSES)
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:class {node.name}")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(node.value, ast.Constant) and node.value.value in FORBIDDEN_EXECUTION_TABLES:
                            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:table {node.value.value}")

    assert violations == []


def test_phase34_final_response_production_has_no_execution_positive_wording() -> None:
    source = _source(FINAL_RESPONSE_PATH)

    for phrase in FORBIDDEN_EXECUTION_WORDING:
        assert phrase not in source


def test_phase34_route_after_risk_requires_opaque_auto_action_capability() -> None:
    source = _source(GRAPH_PATH)

    assert "AutoActionCapabilityRefV1" in source
    assert 'return "action_draft" if _auto_action_capability_ready(state) else "final_response"' in source
    assert "AutoAllowedActionBindingV1" not in source
    assert "approval_required" in source


def test_phase34_agent_runs_bridge_has_binding_preservation_coverage() -> None:
    source = _source(AGENT_RUNS_TEST_PATH)

    for required in (
        "target_merchant_id",
        "business_fact_refs",
        "verified_evidence_refs",
        "claim_verification_ref",
        "risk_decision_ref",
        "approval_idempotency_key",
    ):
        assert required in source


def test_phase34_context_defers_broad_trace_run_projection_hardening_to_phase35() -> None:
    if not CONTEXT_PATH.exists():
        return
    source = _source(CONTEXT_PATH)

    assert "Broad trace/run API projection hardening" in source
    assert "Phase 35" in source


def test_phase34_ordinary_chat_nodes_cannot_call_approval_service_decide() -> None:
    tree = ast.parse(_source(APPROVAL_GATE_PATH), filename=str(APPROVAL_GATE_PATH))
    imported_names: set[str] = set()
    decide_calls: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_names.update(alias.name for alias in node.names if node.module.startswith("src.approvals"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "decide":
            decide_calls.append(node.lineno)

    assert "ApprovalService" not in imported_names
    assert decide_calls == []
