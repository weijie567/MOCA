from __future__ import annotations

import pytest

from src.agent import graph_vocabulary as graph_vocabulary_module
from src.agent.graph_vocabulary import (
    graph_vocabulary_entry,
    is_deferred_non_runnable_target,
    project_trace_step_for_contract,
    target_graph_name,
)
from tests.architecture.graph_baseline import TARGET_CANONICAL_GRAPH_NODES


CURRENT_ROUTER_NAMES = frozenset(
    {
        "route_after_safety",
        "route_after_contextual_intent",
        "route_after_slot_resolution",
        "route_after_investigate",
        "route_after_rag_context",
        "route_after_recommendation",
        "route_after_claim_verify",
        "route_after_risk",
        "route_after_approval",
    }
)

HISTORICAL_STORED_NAME_PROJECTIONS = {
    "classify_intent": ("node", "contextual_intent_resolve"),
    "intent_classification": ("node", "contextual_intent_resolve"),
    "classify_intent:pre_route": ("node", "safety_pre_route"),
    "session_memory_load": ("node", "session_context_load"),
    "long_term_memory_retrieve": ("node", "memory_context_load"),
    "reviewed_memory_context_retrieve": ("node", "memory_context_load"),
    "extract_slots": ("node", "slot_resolution_gate"),
    "generate_recommendation": ("node", "recommendation_generation"),
    "assess_risk_and_approval": ("node", "risk_gate"),
    "route_after_intent": ("router", "route_after_contextual_intent"),
    "route_after_slots": ("router", "route_after_slot_resolution"),
}


@pytest.mark.parametrize("name", sorted(TARGET_CANONICAL_GRAPH_NODES))
def test_final_canonical_runtime_nodes_are_identity_mapped(name: str) -> None:
    entry = graph_vocabulary_entry(name, kind="node")
    projected = project_trace_step_for_contract({"node": name, "status": "completed"})

    assert entry is not None
    assert entry.legacy_name == name
    assert entry.target_name == name
    assert entry.kind == "node"
    assert entry.status == "runtime"
    assert entry.runnable is True
    assert entry.reason_codes == ()
    assert target_graph_name(name, kind="node") == name
    assert is_deferred_non_runnable_target(name, kind="node") is False
    assert projected["implementation_node"] == name
    assert projected["target_node"] == name
    assert projected["target_graph_status"] == "runtime"
    assert projected["target_graph_runnable"] is True


@pytest.mark.parametrize("name", sorted(CURRENT_ROUTER_NAMES))
def test_current_runtime_routers_are_identity_mapped(name: str) -> None:
    entry = graph_vocabulary_entry(name, kind="router")

    assert entry is not None
    assert entry.legacy_name == name
    assert entry.target_name == name
    assert entry.kind == "router"
    assert entry.status == "runtime"
    assert entry.runnable is True
    assert entry.reason_codes == ()
    assert target_graph_name(name, kind="router") == name


@pytest.mark.parametrize(
    ("name", "kind", "target_name"),
    [(name, kind, target_name) for name, (kind, target_name) in HISTORICAL_STORED_NAME_PROJECTIONS.items()],
)
def test_legacy_names_are_not_current_runtime_vocabulary(name: str, kind: str, target_name: str) -> None:
    assert graph_vocabulary_entry(name, kind=kind) is None  # type: ignore[arg-type]
    assert target_graph_name(name, kind=kind) == name  # type: ignore[arg-type]

    projected = project_trace_step_for_contract({"node": name, "status": "completed"})

    assert projected["node"] == name
    assert projected["implementation_node"] == name
    assert projected["target_node"] == target_name
    assert projected["target_graph_status"] == "historical_projection"
    assert projected["target_graph_status"] != "compatibility_alias"
    assert projected["target_graph_runnable"] is False


def test_active_vocabulary_has_no_compatibility_alias_rows_or_phase58_delete_markers() -> None:
    assert all(entry.status != "compatibility_alias" for entry in graph_vocabulary_module._ENTRIES)
    assert all("DELETE_BY_PHASE_58" not in entry.reason_codes for entry in graph_vocabulary_module._ENTRIES)
    assert all(
        not any(reason_code.endswith("_COMPATIBILITY_ALIAS") for reason_code in entry.reason_codes)
        for entry in graph_vocabulary_module._ENTRIES
    )


def test_active_vocabulary_entries_are_unique_and_match_final_runtime_surface() -> None:
    pairs = [(entry.kind, entry.legacy_name) for entry in graph_vocabulary_module._ENTRIES]

    assert len(pairs) == len(set(pairs))
    assert {
        entry.legacy_name
        for entry in graph_vocabulary_module._ENTRIES
        if entry.kind == "node"
    } == TARGET_CANONICAL_GRAPH_NODES
    assert {
        entry.legacy_name
        for entry in graph_vocabulary_module._ENTRIES
        if entry.kind == "router"
    } == CURRENT_ROUTER_NAMES


def test_non_main_lifecycle_names_are_not_active_runtime_vocabulary() -> None:
    assert graph_vocabulary_entry("memory_write", kind="node") is None
    assert target_graph_name("memory_write", kind="node") == "memory_write"


def test_unknown_graph_name_is_safe_passthrough() -> None:
    assert graph_vocabulary_entry("custom_debug_node", kind="node") is None
    assert target_graph_name("custom_debug_node", kind="node") == "custom_debug_node"

    projected = project_trace_step_for_contract({"node": "custom_debug_node", "status": "completed"})

    assert projected["implementation_node"] == "custom_debug_node"
    assert projected["target_node"] == "custom_debug_node"
    assert projected["target_graph_status"] == "unknown_passthrough"
    assert projected["target_graph_runnable"] is True


def test_project_trace_step_preserves_original_fields_and_adds_historical_projection() -> None:
    original = {
        "node": "extract_slots",
        "status": "completed",
        "latency_ms": 12,
        "metrics_json": {"slot_resolution_gate": True},
    }

    projected = project_trace_step_for_contract(original)

    assert projected["node"] == "extract_slots"
    assert projected["status"] == "completed"
    assert projected["latency_ms"] == 12
    assert projected["metrics_json"] == {"slot_resolution_gate": True}
    assert projected["implementation_node"] == "extract_slots"
    assert projected["target_node"] == "slot_resolution_gate"
    assert projected["target_graph_status"] == "historical_projection"
    assert projected["target_graph_runnable"] is False
    assert projected is not original
