from __future__ import annotations

from src.agent import graph_vocabulary


def test_phase34_risk_gate_runtime_alias_is_declared() -> None:
    entry = graph_vocabulary.graph_vocabulary_entry("assess_risk_and_approval", kind="node")

    assert entry is not None
    assert entry.target_name == "risk_gate"
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert entry.reason_codes == ("RISK_GATE_PROJECTED_FROM_ASSESS_RISK_AND_APPROVAL",)
    assert graph_vocabulary.target_graph_name("assess_risk_and_approval", kind="node") == "risk_gate"


def test_phase34_route_after_risk_is_runtime_router() -> None:
    entry = graph_vocabulary.graph_vocabulary_entry("route_after_risk", kind="router")

    assert entry is not None
    assert entry.target_name == "route_after_risk"
    assert entry.status == "runtime"
    assert entry.runnable is True
