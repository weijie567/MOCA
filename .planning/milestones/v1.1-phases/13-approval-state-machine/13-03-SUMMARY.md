---
phase: 13-approval-state-machine
plan: 03
subsystem: approvals
tags: [approval-service, state-machine, cas, action-safety-snapshot, pytest]

requires:
  - phase: 13-approval-state-machine
    provides: CanonicalHashProfile, ActionSafetySnapshot, and v2 approval schema from Plans 13-01 and 13-02
provides:
  - Package-owned ApprovalService create/decide/expire transition boundary
  - Strict approval create, decision, result, and trusted approval_result.v1 schemas
  - Package-owned approval repository locks, revision allocation, decision/event inserts, and CAS helpers
  - Snapshot-owner persistence seam for ActionSafetySnapshot rows
  - Transition and hash-binding tests for stale versions, wrong bindings, legacy rows, and exact hashes
affects: [phase-13-approval-state-machine, phase-14-demo-action-boundary, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - ApprovalService owns executable transitions behind strict server-side commands
    - Snapshot persistence is shared through src/approvals/snapshot_service.py rather than exposed as an ApprovalService transition
    - Decisions store pre-transition redundant binding versions while service results return post-transition versions

key-files:
  created:
    - src/approvals/policy.py
    - src/approvals/repository.py
    - src/approvals/service.py
    - src/approvals/snapshot_service.py
    - tests/approvals/test_hash_binding.py
    - tests/approvals/test_service_transitions.py
    - tests/approvals/test_single_level_runtime.py
  modified:
    - src/approvals/schemas.py

key-decisions:
  - "ApprovalDecisionCommand carries run_id, thread_id, level_id, and assignment_id in addition to expected versions so the service can validate the full decision -> assignment -> level -> request binding."
  - "ApprovalService calls persist_action_safety_snapshot from src/approvals/snapshot_service.py but does not expose snapshot persistence as a transition method for auto-allowed paths."
  - "Approval decision rows record the version/revision values used to authorize the decision; ApprovalDecisionResult and approval_result.v1 return the post-transition versions."

patterns-established:
  - "Transition failures raise ApprovalTransitionError with stable domain codes before decision/event insert, preserving rollback/no-orphan guarantees."
  - "New v2 request creation allocates revision as max(existing tenant/run revision)+1, preserving deterministic legacy backfill."

requirements-completed:
  - APPROVAL-01
  - APPROVAL-03
  - SNAPSHOT-01

duration: 15 min
completed: 2026-06-15
---

# Phase 13 Plan 03: Approval Service Transaction Boundary Summary

**ApprovalService transitions with exact action/snapshot hash binding, request-level-assignment CAS, and package-owned snapshot persistence**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-15T07:35:13Z
- **Completed:** 2026-06-15T07:50:34Z
- **Tasks:** 4
- **Files modified:** 8

## Accomplishments

- Added transition/hash tests covering stale request, level, assignment, and revision values; wrong tenant/run/thread/binding; self-approval; missing snapshots; changed payload/evidence/config hash material; and legacy v1 fail-closed behavior.
- Added strict approval command/result schemas plus policy helpers for role checks, self-approval, default single-level assignment, and SLA due time.
- Added `src/approvals/repository.py` with `with_for_update` locks, max-revision allocation, v2 request/level/assignment creation, and redundant decision/event binding inserts.
- Added `src/approvals/snapshot_service.py` and `ApprovalService.create_request`, `decide`, and `expire_due_request` with exact hash binding and service-built `approval_result.v1` payloads.

## Task Commits

1. **Task 1: Add ApprovalService transition and hash-binding tests** - `2c8334d` (test)
2. **Task 2: Add approval command/result schemas and policy** - `4abbcdd` (feat)
3. **Task 3: Implement package-owned repository locks, inserts, and CAS helpers** - `2e98a49` (feat)
4. **Task 4: Implement ApprovalService create_request, decide, and expire** - `b4c3f1a` (feat)

## Files Created/Modified

- `src/approvals/schemas.py` - Approval decision type/status literals, create/decision commands, create/decision results, and trusted resume payload schema.
- `src/approvals/policy.py` - Approval role/self-approval/assignment/SLA policy helper.
- `src/approvals/repository.py` - Package-owned locks, revision allocation, snapshot/request/decision/event inserts, and version increments.
- `src/approvals/snapshot_service.py` - Snapshot-owner persistence seam and proposed action hash computation.
- `src/approvals/service.py` - ApprovalService create/decide/expire state-machine boundary.
- `tests/approvals/test_service_transitions.py` - Transition CAS, mismatch, self-approval, and rollback tests.
- `tests/approvals/test_single_level_runtime.py` - Single-level target-table runtime and request creation tests.
- `tests/approvals/test_hash_binding.py` - Hash-binding and legacy fail-closed tests.

## Verification

- `uv run pytest tests/approvals/test_service_transitions.py tests/approvals/test_single_level_runtime.py tests/approvals/test_hash_binding.py -q --tb=short` - **PASS**: 28 passed, 1 existing LangGraph deprecation warning.
- `uv run pytest tests/approvals/test_canonical_hash.py tests/approvals/test_snapshots.py tests/approvals/test_migration_contract.py -q --tb=short` - **PASS**: 26 passed, 1 existing LangGraph deprecation warning.
- `uv run ruff check src/approvals tests/approvals/test_service_transitions.py tests/approvals/test_single_level_runtime.py tests/approvals/test_hash_binding.py` - **PASS**.

## Decisions Made

- Added explicit run/thread/level/assignment identity fields to `ApprovalDecisionCommand` because version values alone cannot validate the required cross-table binding failures.
- Kept snapshot persistence as `src/approvals/snapshot_service.py::persist_action_safety_snapshot(...)`; `ApprovalService` uses it for request creation but does not expose it as an auto-allow transition.
- Recorded decision rows with the pre-transition request/level/assignment versions used for authorization, while the returned service result carries the post-transition versions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added explicit decision binding identity fields**
- **Found during:** Task 2 (Add approval command/result schemas and policy)
- **Issue:** The plan listed expected request/level/assignment versions on `ApprovalDecisionCommand`, but the phase constraint also requires wrong run/thread/assignment-level/request binding failures. Versions alone cannot identify which level or assignment the reviewer is authorizing.
- **Fix:** Added `run_id`, `thread_id`, `level_id`, and `assignment_id` to the decision command and validated them in `ApprovalService.decide`.
- **Files modified:** `src/approvals/schemas.py`, `src/approvals/service.py`, `tests/approvals/test_service_transitions.py`, `tests/approvals/test_single_level_runtime.py`
- **Verification:** Focused service pytest and ruff checks passed.
- **Committed in:** `4abbcdd`, `b4c3f1a`

**2. [Rule 1 - Bug] Corrected event-count tests after requested-event insertion**
- **Found during:** Task 4 (Implement ApprovalService create_request, decide, and expire)
- **Issue:** Task 1 tests counted all `approval_events`, but Task 3 correctly creates an `approval_requested` event during request creation before a decision is made.
- **Fix:** Updated decision tests to count only `approval_decided` events when asserting decision insertion.
- **Files modified:** `tests/approvals/test_service_transitions.py`, `tests/approvals/test_single_level_runtime.py`
- **Verification:** Focused service pytest passed with 28 tests.
- **Committed in:** `b4c3f1a`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both changes tighten the intended approval safety boundary. No out-of-scope action execution or API cutover work was added.

## Issues Encountered

- Focused pytest commands emit one existing LangGraph `allowed_objects` pending-deprecation warning from the dependency stack; tests pass.

## Known Stubs

None. `edit` and `respond` intentionally return `not_implemented_for_plan_05` from `ApprovalService.decide` as specified by this plan; Plan 13-05 owns their detailed revalidation behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-04 can cut API, chat/SSE, and graph callers over to server-side `ApprovalRequestCreateCommand` and `ApprovalDecisionCommand` construction. Plan 13-05 remains responsible for `edit`, `respond`, and `needs_info` revalidation.

## Self-Check: PASSED

- Verified created files exist: `src/approvals/policy.py`, `src/approvals/repository.py`, `src/approvals/service.py`, `src/approvals/snapshot_service.py`, the three new approval test files, and this summary.
- Verified task commits exist: `2c8334d`, `4abbcdd`, `2e98a49`, and `b4c3f1a`.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
