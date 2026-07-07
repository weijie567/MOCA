---
phase: 56-recommendation-generation-and-rag-claim-status-alignment
reviewed: 2026-07-07T11:13:29Z
depth: deep
files_reviewed: 31
files_reviewed_list:
  - README.md
  - docs/architecture-overview.md
  - docs/current-langgraph-architecture.md
  - docs/rag-architecture-spec.md
  - docs/target-agent-platform-architecture-plan.md
  - frontend/src/components/timeline/TimelineStep.tsx
  - scripts/eval_agent.py
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/recommendation_generation.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_final_response.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/agent/test_rag_context_routing.py
  - tests/agent/test_trace.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/test_agent_runs_api.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 56: Code Review Report

**Reviewed:** 2026-07-07T11:13:29Z
**Depth:** deep
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Deep re-review of the Phase 56 scope found no remaining Critical or Warning issues.

WR-01 is fixed. `route_after_recommendation()` still routes missing-info drafts to `final_response`, but `final_response()` now downgrades displayable `missing_info` drafts to an insufficient-evidence response before completed recommendation rendering. The regression at `tests/agent/test_phase22_final_response.py:395` verifies the user-visible response includes the missing `refund_case_id` and does not render `建议：issue_coupon`.

WR-02 is fixed. Direct recommendation generation for partial verified evidence packages now delegates to the same `_partial_rag_context_can_generate()` guard used by router-level `route_after_rag_context`, so approval/action/high-risk/stale/conflict/rejected-candidate cases fail closed before the LLM runs. The parametrized regression at `tests/agent/test_nodes/test_generate_recommendation.py:577` covers the drift cases.

Verification run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_final_response.py::test_missing_info_action_draft_downgrades_before_completed_response tests/agent/test_nodes/test_generate_recommendation.py::test_partial_package_direct_generation_uses_router_blockers -q --tb=short
```

Result: `8 passed, 1 warning`.

## Info

### IN-01: CI graph contract still omits the approved action-draft path

**File:** `scripts/eval_agent.py:54`
**Issue:** The deterministic graph-contract category list still includes only `normal_policy_qa`, `refund_troubleshooting`, and `compensation_suggestion`. It omits an approved action-draft representative even though `_run_graph_contract_case()` can resume approvals. In the same harness, `_ci_action_result()` and `_ci_action_tool_result()` return only `draft_id`/`status` without the current `draft_outcome` contract required by `action_draft`. This leaves the approved `approval_gate -> action_draft -> final_response` contract underrepresented in CI graph-contract evals.
**Fix:** Add an `approval_approved` representative to `GRAPH_CONTRACT_CATEGORIES`, update `_ci_action_result()` / `_ci_action_tool_result()` to include a valid demo `draft_outcome`, and assert the approved graph summary includes `approval_gate`, `action_draft`, and final response text that confirms the demo draft was created without external side effects.

---

_Reviewed: 2026-07-07T11:13:29Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
