from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

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


LEGACY_GRAPH_NAMES = frozenset(
    {
        "classify_intent",
        "intent_classification",
        "classify_intent:pre_route",
        "session_memory_load",
        "extract_slots",
        "long_term_memory_retrieve",
        "reviewed_memory_context_retrieve",
        "generate_recommendation",
        "assess_risk_and_approval",
    }
)
LEGACY_ROUTER_NAMES = frozenset({"route_after_intent", "route_after_slots"})
CLASSIFIER_SCRIPT = Path("scripts/classify_phase58_legacy_hits.py")
PHASE58_DIR = Path(".planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup")


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


def test_phase58_current_vocabulary_excludes_legacy_runtime_aliases() -> None:
    assert "generate_recommendation" not in MIGRATION_MODE_LEGACY_NODE_MAP
    assert "assess_risk_and_approval" not in MIGRATION_MODE_LEGACY_NODE_MAP
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {}

    for name in LEGACY_GRAPH_NAMES:
        assert graph_vocabulary.graph_vocabulary_entry(name, kind="node") is None, name
        assert graph_vocabulary.target_graph_name(name, kind="node") == name
    for name in LEGACY_ROUTER_NAMES:
        assert graph_vocabulary.graph_vocabulary_entry(name, kind="router") is None, name
        assert graph_vocabulary.target_graph_name(name, kind="router") == name

    assert all(entry.status != "compatibility_alias" for entry in graph_vocabulary._ENTRIES)
    assert all("DELETE_BY_PHASE_58" not in entry.reason_codes for entry in graph_vocabulary._ENTRIES)


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
    assert "risk_gate" in set(eval_agent._expected_nodes_for_case(case))
    for category in {"approval_approved"}:
        assert "risk_gate" in expected_node_sets[category]
    assert "from src.agent.nodes import risk_gate as risk_gate_module" in source
    legacy_import = "from src.agent.nodes import " + "assess_risk_and_approval"
    assert legacy_import not in source
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
    assert graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES
    assert graph_add_node_names().isdisjoint(FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES)

    routing_source = Path("src/agent/routing.py").read_text(encoding="utf-8")
    assert "def route_after_intent(" not in routing_source
    assert "def route_after_slots(" not in routing_source

    router_values = {
        route_value
        for route_values in graph_router_route_values().values()
        for route_value in route_values
    }
    assert router_values.isdisjoint(LEGACY_GRAPH_NAMES)
    assert router_values <= TARGET_CANONICAL_GRAPH_NODES

    current_node_entries = {
        entry.legacy_name
        for entry in graph_vocabulary._ENTRIES
        if entry.kind == "node" and entry.status == "runtime"
    }
    assert current_node_entries == TARGET_CANONICAL_GRAPH_NODES


def test_phase58_legacy_hit_classifier_exposes_main_and_strict_report_fields() -> None:
    classifier = importlib.import_module("scripts.classify_phase58_legacy_hits")
    result = _run_phase58_classifier("--strict")

    assert callable(classifier.main)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    for key in (
        "total_hits",
        "files",
        "category_counts",
        "active_runtime_legacy",
        "current_docs_legacy_authority",
        "unclassified_rows",
    ):
        assert key in payload
    assert payload["active_runtime_legacy"] == 0
    assert payload["current_docs_legacy_authority"] == 0
    assert payload["unclassified_rows"] == 0
    assert str(PHASE58_DIR / "58-VALIDATION.md") in payload["excluded_paths"]


def test_phase58_legacy_hit_classifier_strict_fails_active_runtime_rows(tmp_path: Path) -> None:
    graph_path = tmp_path / "src" / "agent" / "graph.py"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text('builder.add_node("classify_intent", classify_intent)\n', encoding="utf-8")

    result = _run_phase58_classifier("--strict", "--root", str(tmp_path), "--roots", "src")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["active_runtime_legacy"] == 1
    assert payload["unclassified_rows"] == 0


def test_phase58_legacy_hit_classifier_strict_fails_unclassified_rows(tmp_path: Path) -> None:
    unknown_path = tmp_path / "unknown.txt"
    unknown_path.write_text("classify_intent\n", encoding="utf-8")

    result = _run_phase58_classifier("--strict", "--root", str(tmp_path), "--roots", "unknown.txt")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["active_runtime_legacy"] == 0
    assert payload["unclassified_rows"] == 1


def test_phase58_legacy_hit_classifier_allows_classified_nonzero_totals(tmp_path: Path) -> None:
    state_path = tmp_path / ".planning" / "STATE.md"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("Previous state mentioned classify_intent as historical context.\n", encoding="utf-8")

    result = _run_phase58_classifier("--strict", "--root", str(tmp_path), "--roots", ".planning/STATE.md")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_hits"] == 1
    assert payload["files"] == 1
    assert payload["category_counts"]["previous_state_documentation"] == 1
    assert payload["active_runtime_legacy"] == 0
    assert payload["unclassified_rows"] == 0


def test_phase58_legacy_hit_classifier_excludes_generated_validation_artifact(tmp_path: Path) -> None:
    validation_path = tmp_path / PHASE58_DIR / "58-VALIDATION.md"
    validation_path.parent.mkdir(parents=True)
    validation_path.write_text("Generated report mentions classify_intent.\n", encoding="utf-8")

    result = _run_phase58_classifier("--strict", "--root", str(tmp_path), "--roots", str(PHASE58_DIR))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_hits"] == 0
    assert str(PHASE58_DIR / "58-VALIDATION.md") in payload["excluded_paths"]


def _run_phase58_classifier(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLASSIFIER_SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )


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
