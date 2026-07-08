---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
reviewed: 2026-07-08T07:30:37Z
depth: deep
files_reviewed: 45
files_reviewed_list:
  - eval/replay/dev-contract-manifest.v1.json
  - frontend/src/components/timeline/TimelineStep.tsx
  - scripts/classify_phase58_legacy_hits.py
  - scripts/eval_agent.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/recommendation_generation.py
  - src/agent/nodes/risk_gate.py
  - src/agent/nodes/slot_resolution_gate.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - tests/agent/test_empty_session_adapter.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_adapter.py
  - tests/agent/test_intent_golden_contract.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_memory_context_load.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_nodes/test_contextual_intent_resolve.py
  - tests/agent/test_nodes/test_recommendation_generation.py
  - tests/agent/test_nodes/test_risk_gate.py
  - tests/agent/test_nodes/test_session_context_load.py
  - tests/agent/test_nodes/test_slot_resolution_gate.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_trace.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/architecture/test_memory_contract_delta.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/architecture/test_phase33_rag_claim_boundaries.py
  - tests/architecture/test_phase34_approval_action_boundaries.py
  - tests/conftest.py
  - tests/eval/test_phase35_replay_eval_gates.py
  - tests/knowledge/test_facade_integration.py
  - tests/knowledge/test_phase21_boundaries.py
  - tests/memory/test_phase48_1_memory_compat_alignment.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
  - tests/test_graph_routing.py
  - tests/test_interception_rate.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 58: Code Review Report

**Reviewed:** 2026-07-08T07:30:37Z
**Depth:** deep
**Files Reviewed:** 45
**Status:** issues_found

## Summary

Reviewed the listed Phase 58 graph vocabulary, routing, node implementations, API/frontend projections, replay/eval harness, and regression tests. The active graph/router contract is mostly covered, but two Phase 58 no-debt checks still leave current-runtime regressions undetected: the legacy-hit classifier masks active node-file hits, and the current SSE/frontend node label maps are not exact projections of the final 15 canonical nodes.

No critical security issues were found.

## Warnings

### WR-01: Strict Legacy Classifier Masks Active Node-File Hits

**File:** `scripts/classify_phase58_legacy_hits.py:217`

**Issue:** `_classify_row()` classifies every `src/agent/nodes/*` hit as `legacy_wrapper_or_import_test` after only checking `src/agent/graph.py` and `src/agent/routing.py` for active runtime rows. That means strict mode can pass with `active_runtime_legacy: 0` even when an active canonical node file contains a legacy graph/output name. I reproduced this with the project-approved entrypoint:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --roots src/agent/nodes/final_response.py --strict
```

The command exited 0 and classified `src/agent/nodes/final_response.py:374` containing `intent_classification` as `legacy_wrapper_or_import_test`. This undermines the Phase 58 no-active-legacy gate.

**Fix:** Treat active canonical node implementation files as active runtime paths before the broad wrapper/test bucket. Keep an explicit allowlist for true compatibility wrappers or import tests.

```python
ACTIVE_NODE_PATHS = {
    f"src/agent/nodes/{node}.py"
    for node in (
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
    )
}

if normalized in ACTIVE_NODE_PATHS:
    return "active_runtime_legacy"
```

Add a regression test with a temporary `src/agent/nodes/final_response.py` or other active node file containing `intent_classification` and assert `--strict` fails with `active_runtime_legacy == 1`.

### WR-02: Current Timeline Label Maps Do Not Match Final Canonical Nodes

**Files:** `src/api/routers/agent_runs.py:56`, `frontend/src/components/timeline/TimelineStep.tsx:5`

**Issue:** The backend and frontend `NODE_MESSAGES` maps omit five final canonical nodes: `safety_pre_route`, `rag_context_build`, `claim_verify`, `action_draft`, and `clarification_gate`. Both maps also still include `execute_action`, which is explicitly no longer a registered graph node. The final canonical set in `tests/architecture/test_canonical_graph_baseline.py:69` includes all five missing nodes, and `tests/agent/test_graph.py:1022` asserts `action_draft` is present while `tests/agent/test_graph.py:1023` asserts `execute_action` is absent. Current API/frontend tests only check a subset of label keys in `tests/test_agent_runs_api.py:1005`, so this projection drift is not caught.

**Fix:** Update both label maps to cover the exact current canonical node set and remove `execute_action` from current labels. Then strengthen the tests to compare exact key sets.

```python
from tests.architecture.graph_baseline import TARGET_CANONICAL_GRAPH_NODES

def test_agent_run_sse_node_messages_cover_exact_canonical_graph_nodes() -> None:
    assert set(NODE_MESSAGES) == TARGET_CANONICAL_GRAPH_NODES
```

For the frontend test, parse the literal `NODE_MESSAGES` keys and assert the same exact set, or export the canonical set into a shared frontend fixture so `TimelineStep.tsx` cannot drift from the backend projection contract.

---

_Reviewed: 2026-07-08T07:30:37Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
