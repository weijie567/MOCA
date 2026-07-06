from __future__ import annotations

import pytest

from src.agent import graph_vocabulary
from tests.architecture.graph_baseline import (
    CURRENT_ACTIVE_GRAPH_NODES_BASELINE,
    CURRENT_CONDITIONAL_EDGE_BASELINE,
    FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES,
    MIGRATION_MODE_LEGACY_NODE_MAP,
    TARGET_CANONICAL_GRAPH_NODES,
    graph_add_node_names,
    graph_conditional_edge_mappings,
    graph_router_route_values,
)


def test_current_active_graph_node_set_matches_phase51_baseline() -> None:
    assert graph_add_node_names() == CURRENT_ACTIVE_GRAPH_NODES_BASELINE


def test_target_canonical_graph_node_set_is_exact_phase50_contract() -> None:
    assert TARGET_CANONICAL_GRAPH_NODES == frozenset(
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
    assert TARGET_CANONICAL_GRAPH_NODES.isdisjoint(FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES)


def test_migration_mode_maps_every_active_legacy_node_to_target() -> None:
    active_legacy_nodes = CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES

    assert active_legacy_nodes == frozenset(MIGRATION_MODE_LEGACY_NODE_MAP)
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {
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
    for legacy_node, mapping in MIGRATION_MODE_LEGACY_NODE_MAP.items():
        assert mapping["target"] in TARGET_CANONICAL_GRAPH_NODES, legacy_node
        assert mapping["delete_phase"] in {"Phase 53", "Phase 54", "Phase 55", "Phase 56", "Phase 57"}
        assert mapping["owner_requirement"].startswith("CAGM-")


def test_migration_mode_matrix_does_not_depend_on_graph_vocabulary_only() -> None:
    assert MIGRATION_MODE_LEGACY_NODE_MAP["generate_recommendation"]["target"] == "recommendation_generation"

    entry = graph_vocabulary.graph_vocabulary_entry("generate_recommendation", kind="node")
    if entry is not None:
        assert entry.target_name == "recommendation_generation"


def test_current_router_mappings_match_source_baseline() -> None:
    assert graph_conditional_edge_mappings() == CURRENT_CONDITIONAL_EDGE_BASELINE


def test_router_return_values_are_covered_by_registered_path_maps() -> None:
    route_maps = graph_conditional_edge_mappings()
    router_routes = graph_router_route_values()
    registered_nodes = graph_add_node_names()

    assert set(router_routes) == {router for _source, router in route_maps}
    for source, router in route_maps:
        path_map = route_maps[(source, router)]
        assert source in registered_nodes, (source, router)
        assert path_map, (source, router)
        assert set(path_map.values()) <= registered_nodes, (source, router)
        assert router_routes[router], router
        assert router_routes[router] <= frozenset(path_map), router


def test_current_router_mappings_account_for_legacy_destinations() -> None:
    route_maps = graph_conditional_edge_mappings()

    assert route_maps[("investigate", "route_after_investigate")]["recommendation_generation"] == (
        "generate_recommendation"
    )
    assert route_maps[("rag_context_build", "route_after_rag_context")]["recommendation_generation"] == (
        "generate_recommendation"
    )
    assert route_maps[("claim_verify", "route_after_claim_verify")]["assess_risk_and_approval"] == (
        "assess_risk_and_approval"
    )
    assert route_maps[("approval_gate", "route_after_approval")]["assess_risk_and_approval"] == (
        "assess_risk_and_approval"
    )

    legacy_destinations = {
        destination
        for route_map in route_maps.values()
        for destination in route_map.values()
        if destination in MIGRATION_MODE_LEGACY_NODE_MAP
    }
    assert {
        "session_memory_load",
        "long_term_memory_retrieve",
        "generate_recommendation",
        "assess_risk_and_approval",
    }.issubset(legacy_destinations)


def test_forbidden_internal_or_lifecycle_names_are_not_registered_graph_nodes() -> None:
    assert graph_add_node_names().isdisjoint(FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES)


def test_slot_extraction_drift_is_explicitly_rejected() -> None:
    assert "slot_extraction" not in graph_add_node_names(), (
        "`slot_extraction` is not a registered main-chain graph node. If a future phase promotes it, "
        "update docs/contract-spec.md, docs/target-agent-platform-architecture-plan.md, and "
        ".planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md first."
    )


def test_final_no_debt_gate_is_marked_phase58_scope() -> None:
    pytest.skip("Phase 58 cutover enforces exact canonical graph node set; Phase 51 records the gate.")
    assert graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES
