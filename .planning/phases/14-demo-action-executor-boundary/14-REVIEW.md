---
phase: 14-demo-action-executor-boundary
reviewed: 2026-06-16T07:30:22Z
depth: deep
files_reviewed: 33
files_reviewed_list:
  - src/actions/drafts.py
  - src/actions/schemas.py
  - src/actions/service.py
  - src/agent/events.py
  - src/agent/graph.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/execute_action.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/receive_request.py
  - src/agent/state.py
  - src/api/routers/approvals.py
  - src/api/routers/traces.py
  - src/db/migrations/versions/009_action_draft_v2.py
  - src/db/models.py
  - src/repositories/action_draft_repo.py
  - src/repositories/trace_repo.py
  - src/tools/catalog.py
  - src/tools/executors/action.py
  - src/tools/manager.py
  - tests/actions/test_action_draft_v2.py
  - tests/agent/test_events.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_tools/test_create_coupon_grant_draft.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/architecture/test_action_draft_boundaries.py
  - tests/test_approval_api.py
  - tests/test_approval_integration.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
  - tests/tools/test_catalog.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
cross_review:
  codex: completed
  critical: 0
  new_findings: 0
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-16T07:30:22Z
**Depth:** deep
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Reviewed the Phase 14 action draft boundary implementation across action service, graph routing, approval resume reconciliation, trace projections, tool catalog/manager, persistence models/migration, and the related test suite. GSD deep review plus Codex cross-review found no critical issues and confirmed three warning-level correctness/security boundary gaps.

## Warnings

### WR-01: Per-turn reset leaves stale action safety bindings in checkpoint state

**File:** `src/agent/nodes/receive_request.py:57`

**Issue:** `receive_request` resets `proposed_action`, `approval_result`, `action_draft`, `draft_outcome`, `execution_mode`, and `action_result`, but it does not reset the Phase 14 binding fields `approval_revision_refs`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, `safety_snapshot_verified`, `policy_config_version`, `risk_config_version`, `retrieval_config_version`, or `auto_allowed`. Those fields are produced by `assess_risk_and_approval` when an action recommendation is evaluated and then consumed by `route_after_risk`, `route_after_approval`, and `action_draft`. Because LangGraph checkpoint state persists across turns, a later turn that returns early from `assess_risk_and_approval` with no action, such as `policy_qa` or `insufficient_evidence`, will not overwrite these fields. The stale binding values can then survive in final state, traces, or any later routing/debug logic that inspects the full checkpoint state, weakening the intended per-turn isolation for action approval bindings.

**Fix:** Extend `receive_request` to clear all action/approval binding fields in the same reset block, and add a regression test that seeds stale bindings and verifies they are removed.

```python
"approval_revision_refs": None,
"action_payload_hash": None,
"safety_snapshot_ref": None,
"safety_snapshot_hash": None,
"safety_snapshot_verified": None,
"policy_config_version": None,
"risk_config_version": None,
"retrieval_config_version": None,
"auto_allowed": None,
```

### WR-02: Successful draft tool results can synthesize a demo success outcome when the contract payload is missing

**File:** `src/agent/nodes/action_draft.py:116`

**Issue:** `_draft_update_from_tool_result` treats any `ToolResultV2` with `status == "success"` as a successful draft update path. If `result.data` lacks a dict `draft_outcome`, the node synthesizes a fallback `not_executed_demo` outcome with `external_side_effect=False`. If a malformed non-empty `draft_outcome` is present, the code still writes it into state instead of failing closed. That means a successful tool status can mask a malformed Phase 14 payload and produce final/trace state that looks like a valid demo draft outcome.

**Fix:** Validate the success payload against the expected action draft and `DraftOutcomeV1` contract before updating state. Missing, empty, or invalid `draft_outcome` should become an error result and error trace status rather than a synthesized success outcome. Add regression coverage for missing and malformed `draft_outcome` on a success tool result.

### WR-03: Trace projection masks invalid persisted draft outcomes as safe demo defaults

**File:** `src/repositories/trace_repo.py:140`

**Issue:** `_safe_draft_outcome` projects persisted `draft.draft_outcome` fields and validates them with `DraftOutcomeV1`. On validation failure it returns `DraftOutcomeV1().model_dump(mode="json")`, whose defaults represent a `not_executed_demo` outcome with `external_side_effect=False`. As a result, corrupted or invalid persisted data can be exposed through trace APIs as a clean no-side-effect demo outcome, reducing audit fidelity.

**Fix:** Do not replace invalid persisted data with a successful default. Return an explicit invalid/error projection, omit the outcome with an error marker, or otherwise expose that the stored outcome failed validation. Add trace API regression coverage for invalid persisted `draft_outcome`.

## Cross-Review

Codex independently reviewed the same Phase 14 scope and confirmed all three warnings. It found no critical issues and no additional high-confidence findings.

---

_Reviewed: 2026-06-16T07:30:22Z_
_Reviewer: Claude (gsd-code-reviewer) + Codex cross-review_
_Depth: deep_
