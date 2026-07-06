from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"

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
        "classify_intent",
        "session_memory_load",
        "extract_slots",
        "long_term_memory_retrieve",
        "investigate",
        "rag_context_build",
        "generate_recommendation",
        "claim_verify",
        "assess_risk_and_approval",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
    }
)

MIGRATION_MODE_LEGACY_NODE_MAP = {
    "classify_intent": {
        "target": "contextual_intent_resolve",
        "delete_phase": "Phase 53",
        "owner_requirement": "CAGM-04",
    },
    "session_memory_load": {
        "target": "session_context_load",
        "delete_phase": "Phase 53",
        "owner_requirement": "CAGM-04",
    },
    "extract_slots": {
        "target": "slot_resolution_gate",
        "delete_phase": "Phase 54",
        "owner_requirement": "CAGM-05",
    },
    "long_term_memory_retrieve": {
        "target": "memory_context_load",
        "delete_phase": "Phase 55",
        "owner_requirement": "CAGM-06",
    },
    "generate_recommendation": {
        "target": "recommendation_generation",
        "delete_phase": "Phase 56",
        "owner_requirement": "CAGM-07",
    },
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
    ("classify_intent", "route_after_intent"): {
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
        "investigate": "investigate",
        "session_memory_load": "session_memory_load",
    },
    ("extract_slots", "route_after_slots"): {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "long_term_memory_retrieve": "long_term_memory_retrieve",
    },
    ("investigate", "route_after_investigate"): {
        "final_response": "final_response",
        "clarification_gate": "clarification_gate",
        "rag_context_build": "rag_context_build",
        "recommendation_generation": "generate_recommendation",
    },
    ("rag_context_build", "route_after_rag_context"): {
        "recommendation_generation": "generate_recommendation",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
    ("generate_recommendation", "route_after_recommendation"): {
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


def graph_add_node_names(path: Path = GRAPH_PATH) -> frozenset[str]:
    tree = ast.parse(_source(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_node"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value)
    return frozenset(names)


def graph_conditional_edge_mappings(path: Path = GRAPH_PATH) -> dict[tuple[str, str], dict[str, str]]:
    tree = ast.parse(_source(path))
    mappings: dict[tuple[str, str], dict[str, str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_conditional_edges"
            and len(node.args) >= 3
        ):
            continue

        source = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
        router = node.args[1].id if isinstance(node.args[1], ast.Name) else None
        route_map = node.args[2]
        if not isinstance(source, str) or router is None or not isinstance(route_map, ast.Dict):
            continue

        mappings[(source, router)] = {
            key.value: value.value
            for key, value in zip(route_map.keys, route_map.values, strict=True)
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        }
    return mappings
