from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.architecture.graph_baseline import (
    graph_conditional_edge_mappings,
    graph_direct_edge_pairs,
    graph_router_route_values,
)


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TAXONOMY_PATH = SRC / "agent" / "safety" / "taxonomy.py"
RECOMMENDATION_PATH = SRC / "agent" / "nodes" / "recommendation_generation.py"
ROUTING_PATH = SRC / "agent" / "routing.py"
RISK_GATE_PATH = SRC / "agent" / "nodes" / "risk_gate.py"
GRAPH_PATH = SRC / "agent" / "graph.py"
APPROVAL_SCHEMA_PATH = SRC / "approvals" / "schemas.py"
APPROVAL_SERVICE_PATH = SRC / "approvals" / "service.py"
APPROVAL_ROUTER_PATH = SRC / "api" / "routers" / "approvals.py"
AGENT_RUNS_ROUTER_PATH = SRC / "api" / "routers" / "agent_runs.py"
CAPABILITY_PATH = SRC / "actions" / "capabilities.py"
ACTION_SERVICE_PATH = SRC / "actions" / "service.py"
ACTION_NODE_PATH = SRC / "agent" / "nodes" / "action_draft.py"
ACTION_POLICY_PATH = SRC / "tools" / "policy.py"
FRONTEND_API_PATH = ROOT / "frontend" / "src" / "lib" / "api.ts"
FRONTEND_HOOK_PATH = ROOT / "frontend" / "src" / "hooks" / "useAgentRun.ts"
PYTHON_FIXTURE_CONSUMER = ROOT / "tests" / "integration" / "test_phase64_1_runtime_safety_matrix.py"
TYPESCRIPT_FIXTURE_CONSUMERS = (
    ROOT / "frontend" / "src" / "lib" / "api.test.ts",
    ROOT / "frontend" / "e2e" / "phase64_1-approval-safety.spec.ts",
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.AST:
    return ast.parse(_source(path), filename=str(path))


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _definitions(name: str) -> list[str]:
    sites: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
                sites.append(_relative(path))
    return sorted(set(sites))


def _attribute_call_sites(attribute: str) -> list[str]:
    sites: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == attribute
            for node in ast.walk(_tree(path))
        ):
            sites.append(_relative(path))
    return sites


def _named_call_sites(name: str) -> list[str]:
    sites: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            for node in ast.walk(_tree(path))
        ):
            sites.append(_relative(path))
    return sites


def _assignment_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _typescript_function(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_canonical_action_resolution_has_one_owner_before_claim_and_routing() -> None:
    assert _definitions("SafetyTaxonomyRegistry") == ["src/agent/safety/taxonomy.py"]
    assert _definitions("resolve_action_text") == ["src/agent/safety/taxonomy.py"]
    assert "action_resolution = resolve_action_text(draft.get(\"recommended_action\"))" in _source(
        RECOMMENDATION_PATH
    )
    assert _source(RECOMMENDATION_PATH).index("action_resolution = resolve_action_text") < _source(
        RECOMMENDATION_PATH
    ).index("material_claims = _material_claims_from_draft")
    forbidden_owner_names = {
        "_ACTIONABLE_RECOMMENDATIONS",
        "ACTIONABLE_ACTIONS",
        "ACTION_TYPE_ALIASES",
        "EXECUTABLE_ACTION_TYPES",
    }
    for path in (RECOMMENDATION_PATH, ROUTING_PATH):
        assert _assignment_names(path).isdisjoint(forbidden_owner_names), _relative(path)
    assert "canonical_action" in _source(ROUTING_PATH)
    assert "resolve_action_text" not in _source(ROUTING_PATH)
    assert "EXECUTABLE_ACTION_TYPES" in _source(TAXONOMY_PATH)


def test_deterministic_risk_rules_have_one_evaluator_and_loader() -> None:
    assert _definitions("_deterministic_risk_assessment") == ["src/agent/nodes/risk_gate.py"]
    assert _definitions("_load_risk_rules") == ["src/agent/nodes/risk_gate.py"]
    assert 'RISK_RULES_PATH = Path("rules/risk_rules.yaml")' in _source(RISK_GATE_PATH)
    assert "deterministic = _deterministic_risk_assessment" in _source(RISK_GATE_PATH)
    assert "return _deterministic_risk_assessment(draft, context, rules)" in _source(RISK_GATE_PATH)


def test_one_backend_decision_context_projector_feeds_list_get_and_sse() -> None:
    assert _definitions("ApprovalDecisionContextV1") == ["src/approvals/schemas.py"]
    assert _named_call_sites("ApprovalDecisionContextV1") == ["src/approvals/service.py"]
    service_source = _source(APPROVAL_SERVICE_PATH)
    approval_router = _source(APPROVAL_ROUTER_PATH)
    agent_runs_router = _source(AGENT_RUNS_ROUTER_PATH)
    assert "class ApprovalDecisionContext" in service_source
    assert "def project(self) -> ApprovalDecisionContextV1" in service_source
    assert approval_router.count("service.get_decision_context(") >= 3
    assert "decision_context=context.project()" in approval_router
    assert "service.project_decision_context(" in agent_runs_router
    assert '"decision_context": decision_context.model_dump(mode="json")' in agent_runs_router
    assert "ApprovalDecisionContextV1(" not in approval_router
    assert "ApprovalDecisionContextV1(" not in agent_runs_router


def test_python_and_typescript_consume_one_language_neutral_decision_fixture() -> None:
    fixture = ROOT / "contracts" / "fixtures" / "approval_decision_context_v1.json"
    assert fixture.is_file()
    python_consumer = _source(PYTHON_FIXTURE_CONSUMER)
    for path_part in ('"contracts"', '"fixtures"', '"approval_decision_context_v1.json"'):
        assert path_part in python_consumer
    for path in TYPESCRIPT_FIXTURE_CONSUMERS:
        assert "approval_decision_context_v1.json" in _source(path), _relative(path)
    assert not (fixture.parent / "approval_decision_context_v1.py").exists()
    assert not (fixture.parent / "approval_decision_context_v1.ts").exists()


def test_frontend_serializer_echoes_one_context_without_legacy_or_defaults() -> None:
    api_source = _source(FRONTEND_API_PATH)
    serializer = _typescript_function(
        api_source,
        "export function serializeApprovalDecision(",
        "export interface ApprovalRecord",
    )
    required_echoes = {
        "expected_request_version": "request_version",
        "expected_level_version": "level_version",
        "expected_assignment_version": "assignment_version",
        "expected_revision": "revision",
        "action_payload_hash": "action_payload_hash",
        "safety_snapshot_hash": "safety_snapshot_hash",
    }
    for output_key, context_key in required_echoes.items():
        assert f"{output_key}: context.{context_key}" in serializer
    assert re.search(r"\bdecision\s*:", serializer) is None
    assert "??" not in serializer
    assert "||" not in serializer
    assert "parseApprovalDecisionContext(structuredClone(context))" in api_source
    hook_source = _source(FRONTEND_HOOK_PATH)
    assert "isExactApprovalDecisionContext(reviewedContext, latest.data.decision_context)" in hook_source
    assert "const frozen = reviewedContext" in hook_source


def test_capability_mint_and_consume_are_single_owner_fixed_handler_paths() -> None:
    assert _attribute_call_sites("mint") == ["src/agent/nodes/risk_gate.py"]
    assert _attribute_call_sites("create_capability") == ["src/actions/capabilities.py"]
    assert _attribute_call_sites("lock_and_verify_for_draft") == ["src/actions/service.py"]
    assert _attribute_call_sites("mark_consumed") == ["src/actions/service.py"]
    capability_source = _source(CAPABILITY_PATH)
    action_service_source = _source(ACTION_SERVICE_PATH)
    action_node_source = _source(ACTION_NODE_PATH)
    assert 'AUTO_ACTION_CAPABILITY_HANDLER = "create_coupon_grant_draft"' in capability_source
    assert "handler=AUTO_ACTION_CAPABILITY_HANDLER" in action_service_source
    assert 'ACTION_TOOL_NAME = "create_coupon_grant_draft"' in action_node_source
    assert 'caller_node="action_draft"' in action_node_source


def test_capability_path_never_widens_general_permission_or_adds_production_executor() -> None:
    combined = "\n".join(
        _source(path)
        for path in (CAPABILITY_PATH, ACTION_SERVICE_PATH, ACTION_NODE_PATH, ACTION_POLICY_PATH, RISK_GATE_PATH)
    )
    for mutation in ("permissions.append(", "permissions.extend(", "permissions.update("):
        assert mutation not in combined
    assert "production_executor" not in combined
    assert 'add_node("action_execution"' not in _source(GRAPH_PATH)
    assert 'add_node("execute_action"' not in _source(GRAPH_PATH)


def test_action_draft_terminal_is_conditional_and_part_of_canonical_baseline() -> None:
    expected = {
        "final_response": "final_response",
        "terminal_error": "final_response",
    }
    mappings = graph_conditional_edge_mappings()
    assert mappings[("action_draft", "route_after_action_draft")] == expected
    assert graph_router_route_values()["route_after_action_draft"] == frozenset(expected)
    assert ("action_draft", "final_response") not in graph_direct_edge_pairs()
    routing_source = _source(ROUTING_PATH)
    assert "project_action_draft_terminal(state, require_action=True).route_key" in routing_source
    assert 'return route if route in _ACTION_DRAFT_ROUTES else "terminal_error"' in routing_source
