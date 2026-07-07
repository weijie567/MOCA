from __future__ import annotations

from pathlib import Path

import pytest

import scripts.diagnose_latency as diagnose_latency
import scripts.eval_agent as eval_agent
from src.agent import graph_vocabulary
from tests.architecture.graph_baseline import (
    CURRENT_ACTIVE_GRAPH_NODES_BASELINE,
    CURRENT_CONDITIONAL_EDGE_BASELINE,
    FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES,
    MIGRATION_MODE_LEGACY_NODE_MAP,
    TARGET_CANONICAL_GRAPH_NODES,
    graph_add_node_names,
    graph_conditional_edge_mappings,
    graph_direct_edge_pairs,
    graph_router_route_values,
)


def test_current_active_graph_node_set_matches_phase57_baseline() -> None:
    assert "safety_pre_route" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "session_context_load" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "contextual_intent_resolve" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "memory_context_load" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "recommendation_generation" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "risk_gate" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "classify_intent" not in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "session_memory_load" not in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "long_term_memory_retrieve" not in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "generate_recommendation" not in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert "assess_risk_and_approval" not in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert graph_add_node_names() == CURRENT_ACTIVE_GRAPH_NODES_BASELINE


def test_phase53_entry_edges_route_session_context_before_contextual_intent() -> None:
    direct_edges = graph_direct_edge_pairs()

    assert ("START", "receive_request") in direct_edges
    assert ("receive_request", "safety_pre_route") in direct_edges
    assert ("session_context_load", "contextual_intent_resolve") in direct_edges
    assert ("receive_request", "classify_intent") not in direct_edges
    assert ("classify_intent", "session_memory_load") not in direct_edges


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

    assert active_legacy_nodes == frozenset()
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {}
    for legacy_node, mapping in MIGRATION_MODE_LEGACY_NODE_MAP.items():
        assert mapping["target"] in TARGET_CANONICAL_GRAPH_NODES, legacy_node
        assert mapping["delete_phase"] in {"Phase 53", "Phase 54", "Phase 55", "Phase 56", "Phase 57"}
        assert mapping["owner_requirement"].startswith("CAGM-")


def test_phase57_closes_active_risk_legacy_row() -> None:
    assert "generate_recommendation" not in MIGRATION_MODE_LEGACY_NODE_MAP
    assert "assess_risk_and_approval" not in MIGRATION_MODE_LEGACY_NODE_MAP
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {}

    entry = graph_vocabulary.graph_vocabulary_entry("generate_recommendation", kind="node")
    if entry is not None:
        assert entry.target_name == "recommendation_generation"
    risk_entry = graph_vocabulary.graph_vocabulary_entry("assess_risk_and_approval", kind="node")
    if risk_entry is not None:
        assert risk_entry.target_name == "risk_gate"


def test_current_router_mappings_match_source_baseline() -> None:
    assert graph_conditional_edge_mappings() == CURRENT_CONDITIONAL_EDGE_BASELINE


def test_router_return_values_are_covered_by_registered_path_maps() -> None:
    route_maps = graph_conditional_edge_mappings()
    router_routes = graph_router_route_values()
    registered_nodes = graph_add_node_names()

    assert set(router_routes) == {router for _source, router in route_maps}
    assert router_routes["route_after_safety"] == frozenset(
        CURRENT_CONDITIONAL_EDGE_BASELINE[("safety_pre_route", "route_after_safety")]
    )
    assert router_routes["route_after_contextual_intent"] == frozenset(
        CURRENT_CONDITIONAL_EDGE_BASELINE[("contextual_intent_resolve", "route_after_contextual_intent")]
    )
    for source, router in route_maps:
        path_map = route_maps[(source, router)]
        assert source in registered_nodes, (source, router)
        assert path_map, (source, router)
        assert set(path_map.values()) <= registered_nodes, (source, router)
        assert router_routes[router], router
        assert router_routes[router] <= frozenset(path_map), router


def test_current_router_mappings_account_for_legacy_destinations() -> None:
    route_maps = graph_conditional_edge_mappings()

    for route_map in route_maps.values():
        assert "classify_intent" not in route_map.values()
        assert "session_memory_load" not in route_map.values()
        assert "long_term_memory_retrieve" not in route_map.values()

    assert route_maps[("slot_resolution_gate", "route_after_slot_resolution")]["memory_context_load"] == (
        "memory_context_load"
    )
    assert route_maps[("investigate", "route_after_investigate")]["recommendation_generation"] == (
        "recommendation_generation"
    )
    assert route_maps[("rag_context_build", "route_after_rag_context")]["recommendation_generation"] == (
        "recommendation_generation"
    )
    legacy_recommendation_edge = ("generate_" "recommendation", "route_after_recommendation")
    assert legacy_recommendation_edge not in route_maps
    assert route_maps[("recommendation_generation", "route_after_recommendation")] == {
        "claim_verify": "claim_verify",
        "final_response": "final_response",
    }
    assert route_maps[("claim_verify", "route_after_claim_verify")]["risk_gate"] == "risk_gate"
    assert ("assess_risk_and_approval", "route_after_risk") not in route_maps
    assert route_maps[("risk_gate", "route_after_risk")] == {
        "approval_gate": "approval_gate",
        "action_draft": "action_draft",
        "final_response": "final_response",
    }
    assert "risk_gate" not in route_maps[("risk_gate", "route_after_risk")]
    assert route_maps[("approval_gate", "route_after_approval")]["risk_gate"] == "risk_gate"

    legacy_destinations = {
        destination
        for route_map in route_maps.values()
        for destination in route_map.values()
        if destination in MIGRATION_MODE_LEGACY_NODE_MAP
    }
    assert legacy_destinations == set()


def test_phase57_frontend_timeline_labels_current_risk_gate_and_classifies_legacy_display() -> None:
    source = Path("frontend/src/components/timeline/TimelineStep.tsx").read_text(encoding="utf-8")

    assert "risk_gate:" in source
    legacy_lines = [line for line in source.splitlines() if "assess_risk_and_approval" in line]
    for line in legacy_lines:
        assert "DELETE_BY_PHASE_58" in line
        assert "historical" in line.lower()


def test_phase57_eval_current_run_surfaces_use_risk_gate_not_legacy_risk_node() -> None:
    case = _phase57_eval_case()
    fake_llm_keys = set(eval_agent._ci_fake_llm_responses(case))
    expected_node_sets = {
        category: set(
            eval_agent._expected_nodes_for_case(
                {
                    **case,
                    "category": category,
                    "expected_approval_required": category
                    in {"approval_required", "approval_approved", "approval_rejected"},
                }
            )
        )
        for category in eval_agent.GRAPH_CONTRACT_CATEGORIES
    }
    source = Path("scripts/eval_agent.py").read_text(encoding="utf-8")

    assert "risk_gate" in eval_agent.GRAPH_CONTRACT_PATCHED_NODES
    assert "assess_risk_and_approval" not in eval_agent.GRAPH_CONTRACT_PATCHED_NODES
    assert "risk_gate" in fake_llm_keys
    assert "assess_risk_and_approval" not in fake_llm_keys
    for nodes in expected_node_sets.values():
        assert "assess_risk_and_approval" not in nodes
    risk_relevant_categories = {"compensation_suggestion", "approval_approved"}
    for category in risk_relevant_categories:
        assert "risk_gate" in expected_node_sets[category]
    assert "from src.agent.nodes import risk_gate as risk_gate_module" in source
    assert "from src.agent.nodes import assess_risk_and_approval" not in source
    assert 'fake_llms["risk_gate"]' in source
    assert 'fake_llms["assess_risk_and_approval"]' not in source


def test_phase57_diagnostic_mock_report_uses_current_risk_gate_name() -> None:
    report = diagnose_latency.mock_report()
    nodes = [node["node"] for node in report["nodes"]]

    assert "risk_gate" in nodes
    assert "assess_risk_and_approval" not in nodes


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


def _phase57_eval_case() -> dict[str, object]:
    return {
        "id": "phase57-risk-gate",
        "thread_id": "phase57-risk-gate",
        "category": "approval_required",
        "query": "订单 ORD-2024-001 需要补偿 600 元，帮我生成方案。",
        "expected_intent": "compensation_suggestion",
        "expected_evidence_doc_keys": ["refund_policy"],
        "expected_approval_required": True,
        "expected_status": "completed",
        "expected_response_contains": ["补偿"],
        "expected_tools_called": ["get_order", "search_policy"],
    }
