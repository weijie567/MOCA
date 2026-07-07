---
phase: 57-risk-gate-and-approval-gate-canonicalization
reviewed: 2026-07-07T15:56:51Z
depth: deep
files_reviewed: 34
files_reviewed_list:
  - README.md
  - docs/architecture-overview.md
  - docs/current-langgraph-architecture.md
  - docs/target-agent-platform-architecture-plan.md
  - frontend/src/components/timeline/TimelineStep.tsx
  - scripts/diagnose_latency.py
  - scripts/eval_agent.py
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/approval_gate.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/risk_gate.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/approvals/service.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_nodes/test_assess_risk_and_approval.py
  - tests/agent/test_nodes/test_risk_gate.py
  - tests/agent/test_trace.py
  - tests/approvals/test_needs_info_resume.py
  - tests/approvals/test_service_transitions.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/architecture/test_phase33_rag_claim_boundaries.py
  - tests/architecture/test_phase34_approval_action_boundaries.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 57: Code Review Report

**Reviewed:** 2026-07-07T15:56:51Z
**Depth:** deep
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Reviewed the Phase 57 canonicalization from `assess_risk_and_approval` to active `risk_gate`, including graph registration, routers, approval resume/retry normalization, action authorization bindings, trace vocabulary, API surfaces, frontend display compatibility, eval harnesses, docs, and tests.

No Critical or Warning issues were found in the runtime graph/routing path, approval authority checks, risk gate fail-closed behavior, or persisted legacy retry normalization. The remaining findings are Info-level stale verification/diagnostic assumptions that should be cleaned up before the Phase 58 compatibility removal.

Targeted verification passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/test_approval_gate.py tests/test_approval_api.py tests/approvals/test_service_transitions.py tests/test_agent_runs_api.py tests/test_trace_api.py -q --tb=short
```

Result: `319 passed, 1 skipped, 1 warning in 275.26s`.

## Info

### IN-01: Stale router-edge oracle omits auto-allowed action route

**File:** `tests/agent/test_graph.py:58`

**Issue:** `ROUTER_EDGE_KEYS["route_after_risk"]` only lists `approval_gate` and `final_response`, but the active graph and architecture baseline now include `action_draft` as the valid auto-allowed route from `risk_gate`. The dedicated routing tests cover this branch, but this generic router oracle is stale and can mislead future edits or miss drift in this file.

**Fix:** Include the canonical `action_draft` edge and add a bound auto-allowed assertion to this generic router test, or derive the expected keys from `tests/architecture/graph_baseline.py`.

```python
ROUTER_EDGE_KEYS = {
    # ...
    "route_after_risk": {"approval_gate", "action_draft", "final_response"},
    # ...
}
```

### IN-02: Latency mock report still emits retired current-run node names

**File:** `scripts/diagnose_latency.py:92`

**Issue:** `mock_report()` was updated for `risk_gate`, but it still emits `classify_intent` and `generate_recommendation` as synthetic current-run nodes. Phase 57 docs and graph baseline state that current runtime nodes are `contextual_intent_resolve` and `recommendation_generation`; leaving the mock partially legacy keeps diagnostic examples anchored to retired node names.

**Fix:** Update the mock report to use current registered node names and keep legacy names only in explicit historical-trace fixtures.

```python
nodes = [
    {"node": "contextual_intent_resolve", ...},
    {"node": "recommendation_generation", ...},
    {"node": "risk_gate", ...},
]
```

---

_Reviewed: 2026-07-07T15:56:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
