from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
ROUTING_PATH = ROOT / "src" / "agent" / "routing.py"

TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "memory_context_load",
        "investigate",
        "rag_context_build",
        "recommendation_generation",
        "claim_verify",
        "risk_gate",
        "approval_gate",
        "action_draft",
        "clarification_gate",
        "final_response",
    }
)

CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "memory_context_load",
        "investigate",
        "rag_context_build",
        "recommendation_generation",
        "claim_verify",
        "assess_risk_and_approval",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
    }
)

MIGRATION_MODE_LEGACY_NODE_MAP = {
    "assess_risk_and_approval": {
        "target": "risk_gate",
        "delete_phase": "Phase 57",
        "owner_requirement": "CAGM-08",
    },
}

FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES = frozenset(
    {"slot_extraction", "normalize_input", "memory_write", "trace_close", "action_execution"}
)

CURRENT_CONDITIONAL_EDGE_BASELINE = {
    ("safety_pre_route", "route_after_safety"): {
        "session_context_load": "session_context_load",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
    ("contextual_intent_resolve", "route_after_contextual_intent"): {
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
        "investigate": "investigate",
        "slot_resolution_gate": "slot_resolution_gate",
    },
    ("slot_resolution_gate", "route_after_slot_resolution"): {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "memory_context_load": "memory_context_load",
    },
    ("investigate", "route_after_investigate"): {
        "final_response": "final_response",
        "clarification_gate": "clarification_gate",
        "rag_context_build": "rag_context_build",
        "recommendation_generation": "recommendation_generation",
    },
    ("rag_context_build", "route_after_rag_context"): {
        "recommendation_generation": "recommendation_generation",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
    ("recommendation_generation", "route_after_recommendation"): {
        "claim_verify": "claim_verify",
        "final_response": "final_response",
    },
    ("claim_verify", "route_after_claim_verify"): {
        "assess_risk_and_approval": "assess_risk_and_approval",
        "final_response": "final_response",
    },
    ("assess_risk_and_approval", "route_after_risk"): {
        "assess_risk_and_approval": "assess_risk_and_approval",
        "approval_gate": "approval_gate",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
    ("approval_gate", "route_after_approval"): {
        "approval_gate": "approval_gate",
        "assess_risk_and_approval": "assess_risk_and_approval",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
}


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _string_literal(node: ast.AST, *, context: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise AssertionError(f"Unsupported graph baseline shape: {context}")


def _name(node: ast.AST, *, context: str) -> str:
    if isinstance(node, ast.Name):
        return node.id
    raise AssertionError(f"Unsupported graph baseline shape: {context}")


def _edge_endpoint(node: ast.AST, *, context: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    raise AssertionError(f"Unsupported graph baseline shape: {context}")


def graph_add_node_names(path: Path = GRAPH_PATH) -> frozenset[str]:
    tree = ast.parse(_source(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_node"):
            continue
        if not node.args:
            raise AssertionError("Unsupported graph baseline shape: add_node without positional node name")
        names.add(_string_literal(node.args[0], context="add_node node name"))
    return frozenset(names)


def graph_direct_edge_pairs(path: Path = GRAPH_PATH) -> frozenset[tuple[str, str]]:
    tree = ast.parse(_source(path))
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_edge"):
            continue
        if node.keywords or len(node.args) != 2:
            raise AssertionError("Unsupported graph baseline shape: add_edge must use exactly source and destination")
        pairs.add(
            (
                _edge_endpoint(node.args[0], context="add_edge source"),
                _edge_endpoint(node.args[1], context="add_edge destination"),
            )
        )
    return frozenset(pairs)


def graph_conditional_edge_mappings(path: Path = GRAPH_PATH) -> dict[tuple[str, str], dict[str, str]]:
    tree = ast.parse(_source(path))
    mappings: dict[tuple[str, str], dict[str, str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_conditional_edges"
        ):
            continue
        if node.keywords or len(node.args) != 3:
            raise AssertionError(
                "Unsupported graph baseline shape: add_conditional_edges must use exactly "
                "positional source, router, and path_map"
            )

        source = _string_literal(node.args[0], context="add_conditional_edges source")
        router = _name(node.args[1], context="add_conditional_edges router")
        route_map = node.args[2]
        if not isinstance(route_map, ast.Dict):
            raise AssertionError("Unsupported graph baseline shape: add_conditional_edges path_map is not dict literal")

        mappings[(source, router)] = {}
        for key, value in zip(route_map.keys, route_map.values, strict=True):
            mappings[(source, router)][
                _string_literal(key, context=f"{source}.{router} route key")
            ] = _string_literal(value, context=f"{source}.{router} route destination")
    return mappings


def _string_set_literals(path: Path) -> dict[str, frozenset[str]]:
    tree = ast.parse(_source(path))
    sets: dict[str, frozenset[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Set):
            continue
        values = {
            _string_literal(element, context=f"{node.targets[0].id} set literal")
            for element in node.value.elts
        }
        sets[node.targets[0].id] = frozenset(values)
    return sets


def _function_def(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Router function not found: {name}")


def _guarded_name_routes(
    node: ast.AST,
    string_sets: dict[str, frozenset[str]],
) -> tuple[str, frozenset[str]] | None:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.In):
        return None
    if not isinstance(node.left, ast.Name) or len(node.comparators) != 1:
        return None
    comparator = node.comparators[0]
    if not isinstance(comparator, ast.Name) or comparator.id not in string_sets:
        return None
    return node.left.id, string_sets[comparator.id]


def _return_literals(
    node: ast.AST,
    *,
    string_sets: dict[str, frozenset[str]],
    guarded_names: dict[str, frozenset[str]],
    context: str,
) -> frozenset[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return frozenset({node.value})
    if isinstance(node, ast.IfExp):
        guard = _guarded_name_routes(node.test, string_sets)
        if guard is not None and isinstance(node.body, ast.Name) and node.body.id == guard[0]:
            return guard[1] | _return_literals(
                node.orelse,
                string_sets=string_sets,
                guarded_names=guarded_names,
                context=context,
            )
        return _return_literals(
            node.body,
            string_sets=string_sets,
            guarded_names=guarded_names,
            context=context,
        ) | _return_literals(
            node.orelse,
            string_sets=string_sets,
            guarded_names=guarded_names,
            context=context,
        )
    if isinstance(node, ast.Name) and node.id in guarded_names:
        return guarded_names[node.id]
    raise AssertionError(f"Unsupported router return shape: {context}")


def _collect_router_routes(
    node: ast.AST,
    *,
    string_sets: dict[str, frozenset[str]],
    guarded_names: dict[str, frozenset[str]],
    context: str,
) -> frozenset[str]:
    if isinstance(node, ast.Return):
        if node.value is None:
            raise AssertionError(f"Unsupported router return shape: {context}")
        return _return_literals(
            node.value,
            string_sets=string_sets,
            guarded_names=guarded_names,
            context=context,
        )
    if isinstance(node, ast.If):
        guard = _guarded_name_routes(node.test, string_sets)
        body_guarded_names = guarded_names
        if guard is not None:
            body_guarded_names = {**guarded_names, guard[0]: guard[1]}
        return _collect_router_routes_from_statements(
            node.body,
            string_sets=string_sets,
            guarded_names=body_guarded_names,
            context=context,
        ) | _collect_router_routes_from_statements(
            node.orelse,
            string_sets=string_sets,
            guarded_names=guarded_names,
            context=context,
        )
    if isinstance(node, ast.Try):
        routes = _collect_router_routes_from_statements(
            node.body,
            string_sets=string_sets,
            guarded_names=guarded_names,
            context=context,
        )
        for handler in node.handlers:
            routes |= _collect_router_routes_from_statements(
                handler.body,
                string_sets=string_sets,
                guarded_names=guarded_names,
                context=context,
            )
        return (
            routes
            | _collect_router_routes_from_statements(
                node.orelse,
                string_sets=string_sets,
                guarded_names=guarded_names,
                context=context,
            )
            | _collect_router_routes_from_statements(
                node.finalbody,
                string_sets=string_sets,
                guarded_names=guarded_names,
                context=context,
            )
        )
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return frozenset()

    routes: set[str] = set()
    for child in ast.iter_child_nodes(node):
        routes.update(
            _collect_router_routes(
                child,
                string_sets=string_sets,
                guarded_names=guarded_names,
                context=context,
            )
        )
    return frozenset(routes)


def _collect_router_routes_from_statements(
    statements: list[ast.stmt],
    *,
    string_sets: dict[str, frozenset[str]],
    guarded_names: dict[str, frozenset[str]],
    context: str,
) -> frozenset[str]:
    routes: set[str] = set()
    for statement in statements:
        routes.update(
            _collect_router_routes(
                statement,
                string_sets=string_sets,
                guarded_names=guarded_names,
                context=context,
            )
        )
    return frozenset(routes)


def _router_route_values(path: Path, router_names: set[str]) -> dict[str, frozenset[str]]:
    tree = ast.parse(_source(path))
    string_sets = _string_set_literals(path)
    values: dict[str, frozenset[str]] = {}
    for router_name in router_names:
        function = _function_def(tree, router_name)
        routes = _collect_router_routes_from_statements(
            function.body,
            string_sets=string_sets,
            guarded_names={},
            context=router_name,
        )
        if not routes:
            raise AssertionError(f"Router function has no discoverable route returns: {router_name}")
        values[router_name] = routes
    return values


def graph_router_route_values() -> dict[str, frozenset[str]]:
    routing_router_names = {
        "route_after_safety",
        "route_after_contextual_intent",
        "route_after_slot_resolution",
        "route_after_investigate",
        "route_after_rag_context",
        "route_after_recommendation",
        "route_after_claim_verify",
    }
    graph_router_names = {"route_after_risk", "route_after_approval"}
    return {
        **_router_route_values(ROUTING_PATH, routing_router_names),
        **_router_route_values(GRAPH_PATH, graph_router_names),
    }
