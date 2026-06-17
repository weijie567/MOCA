---
phase: 13-approval-state-machine
plan: 07
subsystem: approvals
tags: [approval-service, architecture-boundaries, legacy-quarantine, action-safety-snapshot, pytest]

requires:
  - phase: 13-approval-state-machine
    provides: ApprovalService transitions, API/graph cutover, needs_info/edit semantics, and approval event helpers from Plans 13-03 through 13-06
provides:
  - Static approval owner-boundary tests forbidding legacy transition imports
  - Deleted legacy src/repositories/approval_repo.py v1 transition repository
  - Rewritten legacy approval/action tests around ApprovalService, ApprovalDecisionCommand, v2 revision/version fields, and exact hash/snapshot bindings
  - Fail-closed action and graph guards for incomplete or mismatched approval_result.v1 bindings
affects: [phase-13-approval-state-machine, phase-14-demo-action-boundary, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - AST boundary tests protect ApprovalService as the canonical approval transition owner
    - approval_result.v1 must carry revision/version and action/snapshot hash fields before action routing or action draft creation
    - Legacy approval_request.v1 rows are non-executable and tested through ApprovalService fail-closed behavior

key-files:
  created:
    - tests/architecture/test_approval_boundaries.py
    - .planning/phases/13-approval-state-machine/13-07-SUMMARY.md
  modified:
    - src/agent/graph.py
    - src/agent/nodes/execute_action.py
    - tests/test_approval_models.py
    - tests/test_execute_action.py
    - tests/test_graph_routing.py
  deleted:
    - src/repositories/approval_repo.py

key-decisions:
  - "Deleted src/repositories/approval_repo.py instead of leaving a compatibility shim because source callers had already moved to src.approvals and the remaining legacy references were obsolete tests."
  - "Direct action-node execution now requires approval_result.v1 revision/version fields plus exact action_payload_hash, safety_snapshot_ref, and safety_snapshot_hash matches, mirroring graph routing."
  - "Legacy approval model tests now assert ApprovalService semantics, including terminal conflicts and legacy_v1 fail-closed behavior, rather than v1 repository idempotency."

patterns-established:
  - "Approval boundary tests scan imports with AST targets rather than regex-only source text."
  - "Action authorization checks validate both trusted payload shape and state binding before invoking the action draft tool."

requirements-completed:
  - APPROVAL-01
  - APPROVAL-02
  - APPROVAL-03
  - SNAPSHOT-01

duration: 10 min
completed: 2026-06-15
---

# Phase 13 Plan 07: Legacy Approval Quarantine Summary

**ApprovalService is now the only executable approval transition owner, with legacy repository deletion, static owner-boundary tests, and v2 hash/revision test coverage**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-15T09:30:54Z
- **Completed:** 2026-06-15T09:40:57Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `tests/architecture/test_approval_boundaries.py` with AST import scans for router, graph-node, test, and service ownership boundaries.
- Deleted `src/repositories/approval_repo.py`, removing the public v1 `decide` and `mark_expired` transition path.
- Rewrote legacy approval model tests to use `ApprovalService`, `ApprovalDecisionCommand`, v2 revision/version checks, exact hashes, and `legacy_v1` fail-closed behavior.
- Updated action and graph guards so `approval_result.v1` must include revision/version fields and exact action/snapshot bindings before action draft routing.

## Task Commits

1. **Task 1: Add approval architecture boundary tests** - `c9968f9` (test)
2. **Task 2: Delete or quarantine legacy approval repository transition methods** - `4b58dfc` (fix)
3. **Task 3: Rewrite legacy approval and action tests around v2 service semantics** - `c592d21` (fix)

## Files Created/Modified

- `tests/architecture/test_approval_boundaries.py` - AST import boundary tests for approval routers, graph nodes, legacy repository imports, and canonical `ApprovalService` ownership.
- `src/repositories/approval_repo.py` - Deleted obsolete v1 repository transition path.
- `tests/test_approval_models.py` - Rewritten from legacy repository semantics to ApprovalService v2 semantics.
- `src/agent/graph.py` - Requires v2 approval result revision/version fields before approved routing to action.
- `src/agent/nodes/execute_action.py` - Requires complete matching approval result bindings before action draft creation.
- `tests/test_execute_action.py` - Updated to service-shaped approval results and missing/mismatched binding fail-closed tests.
- `tests/test_graph_routing.py` - Added missing revision/version fail-closed routing coverage.

## Verification

- `uv run pytest tests/architecture/test_approval_boundaries.py tests/test_approval_models.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_execute_action.py tests/test_graph_routing.py -q --tb=short` - **PASS**: 89 passed, 1 existing LangGraph pending-deprecation warning.
- `uv run ruff check src/agent/graph.py src/agent/nodes/execute_action.py tests/test_approval_models.py tests/test_execute_action.py tests/test_graph_routing.py tests/architecture/test_approval_boundaries.py` - **PASS**.
- `rg -n "src\\.repositories\\.approval_repo|ApprovalRepository" tests/test_approval_models.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_execute_action.py tests/test_graph_routing.py` - **PASS**: no matches.

## Decisions Made

- Deleted the compatibility repository rather than leaving a read/list shim because source callers no longer needed it and tests could be rewritten onto `ApprovalService`.
- Treated direct `execute_action` approval binding validation as critical correctness, not only a graph-routing concern, because the node can be unit-invoked with crafted state.
- Preserved Phase 14 ownership of full action draft boundary work; this plan only adds fail-closed guards around existing draft creation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added direct action-node approval binding guard**
- **Found during:** Task 3 (Rewrite legacy approval and action tests around v2 service semantics)
- **Issue:** `route_after_approval` already checked hashes before action routing, but `execute_action` itself accepted any approved `approval_result.v1` without requiring revision/version fields or exact action/snapshot binding matches.
- **Fix:** Added required approval result field checks and state binding validation in `src/agent/nodes/execute_action.py`, mirrored required revision/version checks in `src/agent/graph.py`, and added fail-closed tests.
- **Files modified:** `src/agent/nodes/execute_action.py`, `src/agent/graph.py`, `tests/test_execute_action.py`, `tests/test_graph_routing.py`
- **Verification:** Focused pytest and ruff checks passed.
- **Committed in:** `c592d21`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The fix tightens the specified approval hash/snapshot/revision boundary without adding Phase 14 external execution behavior.

## Issues Encountered

- Focused pytest commands emit one existing LangGraph `allowed_objects` pending-deprecation warning from the dependency stack; tests pass.
- A pre-existing untracked `study_plan/` directory remains in the worktree and was not touched.

## Known Stubs

None - stub scan found only normal local empty-list initialization and explicit `None` test state assignment, not placeholder behavior or unwired data paths.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the legacy transition, approval owner boundary, and action hash/snapshot guard surfaces are covered by this plan threat model and verified by the focused test suite.

## Self-Check: PASSED

- Found `.planning/phases/13-approval-state-machine/13-07-SUMMARY.md`.
- Found `tests/architecture/test_approval_boundaries.py`.
- Verified `src/repositories/approval_repo.py` is deleted.
- Verified task commits `c9968f9`, `4b58dfc`, and `c592d21` resolve in git history.

## Next Phase Readiness

Plan 13-08 can record final Phase 13 read-switch status and coverage gates with the legacy approval transition owner removed and executable boundary tests in place.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
