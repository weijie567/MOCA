from __future__ import annotations

import pytest

from src.agent import graph_vocabulary as graph_vocabulary_module
from src.agent.graph_vocabulary import (
    graph_vocabulary_entry,
    is_deferred_non_runnable_target,
    project_trace_step_for_contract,
    target_graph_name,
)

PHASE54_ALIAS_REASON_CODES = {
    "PHASE_54_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
}


@pytest.mark.parametrize(
    ("name", "kind", "target_name", "status", "runnable"),
    [
        ("classify_intent", "node", "contextual_intent_resolve", "compatibility_alias", True),
        ("intent_classification", "node", "contextual_intent_resolve", "compatibility_alias", True),
        ("classify_intent:pre_route", "node", "safety_pre_route", "compatibility_alias", True),
        ("session_memory_load", "node", "session_context_load", "compatibility_alias", True),
        ("session_context_load", "node", "session_context_load", "runtime", True),
        ("long_term_memory_retrieve", "node", "memory_context_load", "compatibility_alias", True),
        ("reviewed_memory_context_retrieve", "node", "memory_context_load", "runtime", True),
        ("extract_slots", "node", "slot_resolution_gate", "compatibility_alias", True),
        ("slot_resolution_gate", "node", "slot_resolution_gate", "runtime", True),
        ("route_after_intent", "router", "route_after_contextual_intent", "compatibility_alias", True),
        ("route_after_contextual_intent", "router", "route_after_contextual_intent", "runtime", True),
        ("route_after_slots", "router", "route_after_slot_resolution", "compatibility_alias", True),
        ("route_after_slot_resolution", "router", "route_after_slot_resolution", "runtime", True),
    ],
)
def test_legacy_graph_names_project_to_target_vocabulary(
    name: str,
    kind: str,
    target_name: str,
    status: str,
    runnable: bool,
) -> None:
    entry = graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

    assert entry is not None
    assert entry.legacy_name == name
    assert entry.target_name == target_name
    assert entry.kind == kind
    assert entry.status == status
    assert entry.runnable is runnable
    assert target_graph_name(name, kind=kind) == target_name  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("contextual_intent_resolve", "node"),
        ("session_context_load", "node"),
        ("memory_context_load", "node"),
        ("slot_resolution_gate", "node"),
        ("route_after_slot_resolution", "router"),
    ],
)
def test_target_graph_names_are_identity_mapped(name: str, kind: str) -> None:
    entry = graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

    assert entry is not None
    assert entry.target_name == name
    assert target_graph_name(name, kind=kind) == name  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name",
    [
        "receive_request",
        "investigate",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
        "memory_write",
        "session_context_load",
        "contextual_intent_resolve",
        "rag_context_build",
        "claim_verify",
    ],
)
def test_canonical_runtime_nodes_project_as_runtime(name: str) -> None:
    entry = graph_vocabulary_entry(name, kind="node")
    projected = project_trace_step_for_contract({"node": name, "status": "completed"})

    assert entry is not None
    assert entry.target_name == name
    assert entry.status == "runtime"
    assert entry.runnable is True
    assert projected["implementation_node"] == name
    assert projected["target_node"] == name
    assert projected["target_graph_status"] == "runtime"
    assert projected["target_graph_runnable"] is True


def test_phase53_contextual_intent_router_projects_as_runtime() -> None:
    entry = graph_vocabulary_entry("route_after_contextual_intent", kind="router")

    assert entry is not None
    assert entry.target_name == "route_after_contextual_intent"
    assert entry.status == "runtime"
    assert entry.runnable is True


def test_phase54_slot_resolution_runtime_entries_are_runnable() -> None:
    node_entry = graph_vocabulary_entry("slot_resolution_gate", kind="node")
    router_entry = graph_vocabulary_entry("route_after_slot_resolution", kind="router")

    assert node_entry is not None
    assert node_entry.target_name == "slot_resolution_gate"
    assert node_entry.status == "runtime"
    assert node_entry.runnable is True

    assert router_entry is not None
    assert router_entry.target_name == "route_after_slot_resolution"
    assert router_entry.status == "runtime"
    assert router_entry.runnable is True


@pytest.mark.parametrize(
    ("name", "kind", "target_name"),
    [
        ("extract_slots", "node", "slot_resolution_gate"),
        ("route_after_slots", "router", "route_after_slot_resolution"),
    ],
)
def test_phase54_retained_aliases_are_compatibility_only_with_delete_phase(
    name: str,
    kind: str,
    target_name: str,
) -> None:
    entry = graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

    assert entry is not None
    assert entry.target_name == target_name
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert PHASE54_ALIAS_REASON_CODES <= set(entry.reason_codes)


def test_phase54_slot_resolution_vocabulary_entries_are_unique() -> None:
    expected_pairs = {
        ("node", "slot_resolution_gate"),
        ("router", "route_after_slot_resolution"),
        ("node", "extract_slots"),
        ("router", "route_after_slots"),
    }

    for pair in expected_pairs:
        matches = [
            entry
            for entry in graph_vocabulary_module._ENTRIES
            if (entry.kind, entry.legacy_name) == pair
        ]
        assert len(matches) == 1, pair


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("classify_intent", "node"),
        ("intent_classification", "node"),
        ("session_memory_load", "node"),
        ("route_after_intent", "router"),
    ],
)
def test_phase53_retained_compatibility_aliases_are_not_runtime(name: str, kind: str) -> None:
    entry = graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

    assert entry is not None
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert "PHASE_53_COMPATIBILITY_ALIAS" in entry.reason_codes
    assert "DELETE_BY_PHASE_58" in entry.reason_codes


def test_phase_33_claim_verify_is_runtime_runnable() -> None:
    name = "claim_verify"
    entry = graph_vocabulary_entry(name, kind="node")
    projected = project_trace_step_for_contract({"node": name, "status": "completed"})

    assert entry is not None
    assert entry.target_name == name
    assert entry.status == "runtime"
    assert entry.runnable is True
    assert is_deferred_non_runnable_target(name, kind="node") is False
    assert projected["target_graph_status"] == "runtime"
    assert projected["target_graph_runnable"] is True


def test_phase_52_safety_pre_route_projects_as_runtime_node() -> None:
    entry = graph_vocabulary_entry("safety_pre_route", kind="node")
    projected = project_trace_step_for_contract({"node": "safety_pre_route", "status": "completed"})

    assert entry is not None
    assert entry.target_name == "safety_pre_route"
    assert entry.status == "runtime"
    assert entry.runnable is True
    assert projected["implementation_node"] == "safety_pre_route"
    assert projected["target_node"] == "safety_pre_route"
    assert projected["target_graph_status"] == "runtime"
    assert projected["target_graph_runnable"] is True


def test_phase_52_classifier_pre_route_alias_remains_temporary_compatibility() -> None:
    entry = graph_vocabulary_entry("classify_intent:pre_route", kind="node")
    projected = project_trace_step_for_contract({"node": "classify_intent:pre_route", "status": "completed"})

    assert entry is not None
    assert entry.target_name == "safety_pre_route"
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert projected["implementation_node"] == "classify_intent:pre_route"
    assert projected["target_node"] == "safety_pre_route"
    assert projected["target_graph_status"] == "compatibility_alias"
    assert projected["target_graph_runnable"] is True


def test_unknown_graph_name_is_safe_passthrough() -> None:
    assert graph_vocabulary_entry("custom_debug_node", kind="node") is None
    assert target_graph_name("custom_debug_node", kind="node") == "custom_debug_node"

    projected = project_trace_step_for_contract({"node": "custom_debug_node", "status": "completed"})

    assert projected["implementation_node"] == "custom_debug_node"
    assert projected["target_node"] == "custom_debug_node"
    assert projected["target_graph_status"] == "unknown_passthrough"
    assert projected["target_graph_runnable"] is True


def test_project_trace_step_preserves_original_fields_and_adds_contract_projection() -> None:
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
    assert projected["target_graph_status"] == "compatibility_alias"
    assert projected["target_graph_runnable"] is True
    assert projected is not original
