---
phase: 14-demo-action-executor-boundary
plan: 03
subsystem: agent-graph
tags: [langgraph, action-draft, tool-boundary, compatibility-shim, approvals]
requires:
  - phase: 14-demo-action-executor-boundary
    provides: action_draft.v2 persistence, draft_outcome.v1 service payloads, and AgentState draft fields from 14-01/14-02
  - phase: 13-approval-state-machine
    provides: trusted approval_result.v1 revision/hash binding fields
provides:
  - canonical action_draft graph node registration and route keys
  - Phase 14 execute_action compatibility shim with Phase 15 removal gate
  - node-only create_coupon_grant_draft caller authorization for action_draft
  - static boundary tests forbidding new execute_action shim imports and action_result success sentinels
affects: [phase-14, phase-15, graph-routing, approval-resume, replay]
tech-stack:
  added: []
  patterns: [canonical graph node boundary, quarantined compatibility shim, source import boundary test]
key-files:
  created:
    - src/agent/nodes/action_draft.py
    - .planning/phases/14-demo-action-executor-boundary/14-03-SUMMARY.md
  modified:
    - src/agent/nodes/execute_action.py
    - src/agent/graph.py
    - src/api/routers/approvals.py
    - src/tools/catalog.py
    - src/tools/manager.py
    - tests/architecture/test_action_draft_boundaries.py
    - tests/test_execute_action.py
    - tests/test_graph_routing.py
    - tests/agent/test_graph.py
    - tests/agent/test_tools/test_unified_tool_manager.py
    - tests/tools/test_catalog.py
key-decisions:
  - "The canonical graph node and caller_node value is action_draft; execute_action remains only an intent-layer requested_operation value or compatibility shim name."
  - "The create_coupon_grant_draft tool keeps its tool name but allows only caller node action_draft."
  - "Approval reconciliation imports action_draft directly so production source no longer depends on the execute_action shim; 14-04 still owns draft_outcome-based reconciliation wording."
patterns-established:
  - "Compatibility shims must carry an explicit owner, Phase 15 Replay Event Contract removal gate, and dated target."
  - "Architecture tests scan source imports to prevent legacy node shims from becoming second write paths."
requirements-completed: [DEMO-01, DEMO-02]
duration: 1h 2m
completed: 2026-06-16
---

# Phase 14 Plan 03: Action Draft Graph Boundary Summary

**Canonical LangGraph action draft boundary with execute_action quarantined as a delegating compatibility shim**

## Performance

- **Duration:** 1h 2m
- **Started:** 2026-06-16T00:03:04Z
- **Completed:** 2026-06-16T01:05:08Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Created `src/agent/nodes/action_draft.py` as the canonical graph node for durable demo draft creation.
- Replaced `src/agent/nodes/execute_action.py` with a short Phase 14 compatibility shim that delegates to `action_draft` and names the Phase 15 Replay Event Contract removal gate with target date `2026-07-16`.
- Updated `src/tools/catalog.py` and `src/tools/manager.py` so `create_coupon_grant_draft` remains the tool name but is node-only for caller `action_draft`.
- Rewired `src/agent/graph.py` route returns, conditional edge maps, node registration, and final-response edge to use `action_draft`.
- Added static and behavioral tests proving `requested_operation="execute_action"` remains intent taxonomy while backend write routing uses `action_draft`.

## Task Commits

1. **Task 1 RED: Action draft boundary tests** - `52257bf` (test)
2. **Task 1 GREEN: Action draft node boundary** - `615289e` (feat)
3. **Task 2 RED: Graph action draft routing tests** - `ec147b2` (test)
4. **Task 2 GREEN: Graph routes wired to action_draft** - `02e8935` (feat)

## Files Created/Modified

- `src/agent/nodes/action_draft.py` - Canonical graph node, approval binding validation, tool manager call with `caller_node="action_draft"`, and draft-only compatibility output.
- `src/agent/nodes/execute_action.py` - Delegating compatibility shim only.
- `src/agent/graph.py` - Canonical `action_draft` node registration, route keys, and edges.
- `src/api/routers/approvals.py` - Imports and calls `action_draft` directly to avoid source dependency on the shim.
- `src/tools/catalog.py` - Tool descriptor caller allowlist changed to `["action_draft"]`.
- `src/tools/manager.py` - Write-side-effect guard recognizes `action_draft`.
- `tests/architecture/test_action_draft_boundaries.py` - Static boundary tests for shim quarantine, action_result compatibility, graph registration, and source import bans.
- `tests/test_execute_action.py` - Node behavior tests now invoke canonical `action_draft` and verify shim delegation.
- `tests/test_graph_routing.py` - Graph route tests expect `action_draft` while preserving intent taxonomy.
- `tests/agent/test_graph.py` - Compiled graph tests expect the canonical node and conditional edge.
- `tests/agent/test_tools/test_unified_tool_manager.py` and `tests/tools/test_catalog.py` - Tool allowlist expectations updated for `action_draft`.

## Decisions Made

- Kept `requested_operation="execute_action"` unchanged because it describes user intent, not backend side-effect execution.
- Kept `action_result` only as deprecated draft-only compatibility output and guarded against `action_result.status == "success"` in the action draft boundary.
- Updated the approval reconciliation import now, but intentionally left the remaining `action_result` reconciliation semantics for Plan 14-04, which owns the draft_outcome API/final wording migration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed remaining source dependency on execute_action shim**
- **Found during:** Task 2 (graph/source import boundary)
- **Issue:** `tests/architecture/test_action_draft_boundaries.py` forbids source imports of `src.agent.nodes.execute_action` outside the shim, but `src/api/routers/approvals.py` still imported and called `execute_action`.
- **Fix:** Changed approval reconciliation to import and call `action_draft` directly. The deeper `draft_outcome` reconciliation semantics remain in Plan 14-04 scope.
- **Files modified:** `src/api/routers/approvals.py`
- **Verification:** Focused pytest suite passed; source import scan test passed.
- **Committed in:** `02e8935`

---

**Total deviations:** 1 auto-fixed (blocking boundary violation).
**Impact on plan:** Necessary to satisfy the Phase 14 shim quarantine contract. No external execution path was added; Phase 14 demo draft semantics remain intact.

## Issues Encountered

- The initial executor agent completed several commits but stalled before returning or writing the summary. The orchestrator shut it down, inspected the committed work, finished Task 2 locally, reran verification, and created this summary.
- The first focused pytest run inside the sandbox failed to open the local PostgreSQL socket with `PermissionError: [Errno 1] Operation not permitted`. The same command passed outside the sandbox with approved local database access.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_action_draft_boundaries.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_graph.py -q --tb=short` - passed, 86 tests, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/action_draft.py src/agent/nodes/execute_action.py src/agent/graph.py src/tools/catalog.py src/tools/manager.py tests/architecture/test_action_draft_boundaries.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_graph.py` - passed.
- `gsd-sdk query verify.key-links .planning/phases/14-demo-action-executor-boundary/14-03-PLAN.md` - passed, 2/2 key links verified.
- Plan acceptance `rg` checks for canonical `action_draft`, absent independent shim write path, shim removal-gate text, absent `action_result.status == "success"` dependencies in the node/graph, action_draft caller allowlist, graph route keys, and preserved `requested_operation="execute_action"` taxonomy passed.

## Self-Check: PASSED

- Key files created by this plan exist on disk.
- `git log --oneline --grep=14-03` returns the task commits listed above.
- Required verification commands passed.
- `execute_action` is a delegating shim only, and new production source imports use `action_draft`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Wave 4 (`14-04` and `14-05`). Plan 14-04 must finish moving approval resume/API/final wording from legacy `action_result` compatibility to canonical `draft_outcome` truth; Plan 14-05 can build trace events on the canonical `action_draft` node name.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
