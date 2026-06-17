---
phase: 14-demo-action-executor-boundary
plan: 07
subsystem: actions
tags: [action-draft, approval-binding, permissions, demo-mode, pytest]

requires:
  - phase: 14-demo-action-executor-boundary
    provides: action_draft.v2 persistence, draft_outcome semantics, and canonical action_draft node from plans 14-01 through 14-06
  - phase: 13-approval-state-machine
    provides: ActionSafetySnapshot, CanonicalHashProfile v1, and approved request hash/revision bindings
provides:
  - Canonical payload/hash/action_type validation before durable action draft persistence
  - Fail-closed omitted-approval draft authorization until durable auto_allowed evidence exists
  - Non-self-escalating action_draft write-tool permission boundary
  - Complete ActionDraftV2Data service projection and bounded idempotency key material
affects: [phase-14-verification, phase-15-replay-event-contract, phase-17-external-action-execution]

tech-stack:
  added: []
  patterns:
    - compute_action_payload_hash(payload) is checked before action draft persistence
    - approval_request_id=None fails with AUTO_ALLOWED_BINDING_REQUIRED in Phase 14
    - action_draft passes only trusted configured permissions into ToolCallContext

key-files:
  created:
    - .planning/phases/14-demo-action-executor-boundary/14-07-SUMMARY.md
  modified:
    - src/actions/service.py
    - src/agent/nodes/action_draft.py
    - src/api/routers/approvals.py
    - tests/agent/test_tools/test_create_coupon_grant_draft.py
    - tests/test_execute_action.py

key-decisions:
  - "ActionService rejects payload/hash and action_type mismatches before draft persistence."
  - "Phase 14 does not infer auto_allowed authorization from ActionSafetySnapshot existence."
  - "Approval resume may pass tool:create_coupon_grant_draft only after an approved accept/approve decision returns trusted approval_result.v1."

patterns-established:
  - "ActionDraftV2Data projections are validated at the service boundary before returning tool data."
  - "Long draft idempotency keys preserve the raw key in a sha256 digest while bounding stored material to the String(256) column."

requirements-completed: [DEMO-01, DEMO-02]

duration: 24 min
completed: 2026-06-16
---

# Phase 14 Plan 07: Gap Closure Summary

**Action draft creation now binds persisted proposed_action payloads to approved hashes, rejects omitted approval paths, and relies on trusted write-tool permissions.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-06-16T03:50:00Z
- **Completed:** 2026-06-16T04:14:25Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added canonical `compute_action_payload_hash(payload)` validation and top-level `action_type` binding before `ActionDraft` persistence.
- Returned service `action_draft` data through `ActionDraftV2Data.model_validate`, including `proposed_action`, `approval_ref`, `draft_outcome`, and `created_at`.
- Replaced no-approval draft success with `AUTO_ALLOWED_BINDING_REQUIRED` until a durable auto-allowed evidence model exists.
- Removed the `action_draft` node's `tool:create_coupon_grant_draft` self-grant and verified `PERMISSION_REQUIRED` blocks executor dispatch.
- Added a trusted approval-resume config path so only approved accept/approve decisions carry the write-tool permission into resumed draft reconciliation.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Action draft binding regressions** - `f035b9b` (test)
2. **Task 1 GREEN: Payload/hash binding and v2 projection** - `2772279` (feat)
3. **Task 2 RED: Omitted approval fail-closed regressions** - `64e6094` (test)
4. **Task 2 GREEN: AUTO_ALLOWED_BINDING_REQUIRED branch** - `d2f89f5` (feat)
5. **Task 3 RED: Missing permission regression** - `762b8b2` (test)
6. **Task 3 GREEN: Remove permission self-grant** - `c662e97` (feat)
7. **Task 3 follow-up: Approval resume trusted permission** - `fed3799` (fix)

## Files Created/Modified

- `src/actions/service.py` - Computes canonical payload hashes, rejects action binding mismatches, bounds long idempotency keys, validates `ActionDraftV2Data`, and fails closed when approval id is omitted.
- `src/agent/nodes/action_draft.py` - Passes only configured trusted permissions into `ToolCallContext`.
- `src/api/routers/approvals.py` - Supplies `tool:create_coupon_grant_draft` only for approved accept/approve resume reconciliation.
- `tests/agent/test_tools/test_create_coupon_grant_draft.py` - Adds DB-backed regressions for payload mismatch, action type mismatch, omitted approvals, bare snapshots, v2 projection, and bounded keys.
- `tests/test_execute_action.py` - Adds the missing-permission node regression and explicit trusted permissions for success paths.

## Decisions Made

- Followed the plan choice to close the `ActionDraftV2Data` projection warning instead of renaming the response projection.
- Kept no-approval draft creation disabled in current Phase 14 code; future auto-allowed drafts need a durable binding model before re-enablement.
- Treated approval resume permission propagation as trusted API/approval-service output, not as a graph-node self-grant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added trusted write permission to approved resume config**
- **Found during:** Plan-level Phase 14 focused gate after Task 3
- **Issue:** Removing the `action_draft` self-grant caused approval resume reconciliation to call the node without `tool:create_coupon_grant_draft`, so approved decisions no longer created durable demo drafts.
- **Fix:** Added `_resume_graph_config` in `src/api/routers/approvals.py`; it supplies `tool:create_coupon_grant_draft` only when `ApprovalDecisionResult` is approved and decision type is `accept`/`approve`.
- **Files modified:** `src/api/routers/approvals.py`
- **Verification:** Targeted approval integration slice passed, and the full Phase 14 focused gate passed.
- **Committed in:** `fed3799`

---

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** The fix preserves the plan's non-self-escalating node boundary while keeping approved resume flows functional.

## Issues Encountered

- Sandboxed DB-backed pytest runs could not open the local PostgreSQL socket (`PermissionError: [Errno 1] Operation not permitted`). The exact commands were rerun with approved local DB access and passed.
- The Phase 14 focused gate initially failed two approval integration tests after permission self-grant removal; the approved-resume config fix above resolved both failures.

## Verification

Passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py -q --tb=short
# 38 passed, 1 warning

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/service.py src/agent/nodes/action_draft.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py
# All checks passed

UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/test_approval_integration.py tests/test_trace_api.py tests/agent/test_graph.py tests/agent/test_nodes/test_final_response.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py tests/agent/test_nodes/test_receive_request.py -q --tb=short
# 125 passed, 1 warning

UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short
# 820 passed, 1 warning

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests
# All checks passed
```

Acceptance checks passed for:

- `compute_action_payload_hash` in `src/actions/service.py`
- `ACTION_BINDING_MISMATCH` payload/hash and action type tests
- `ActionDraftV2Data.model_validate` in service and tests
- `key_sha256` bounded idempotency material
- `AUTO_ALLOWED_BINDING_REQUIRED` service/tests and no `auto_allowed` revision marker returns
- Missing-permission `PERMISSION_REQUIRED` node regression
- No `permissions.append` self-grant in `src/agent/nodes/action_draft.py`

## TDD Gate Compliance

- RED commits present before GREEN: `f035b9b`, `64e6094`, `762b8b2`.
- GREEN commits present after RED: `2772279`, `d2f89f5`, `c662e97`.
- Rule 2 fix commit present after GREEN: `fed3799`.
- No refactor-only commit was needed.

## Known Stubs

None. Stub scan hits were intentional typed `None` defaults, empty test assertions, or local test list initialization; no runtime/UI stubs were introduced.

## Threat Flags

None. The plan modified existing action/approval trust boundaries to implement the planned mitigations and did not add new endpoints, schema, file access paths, external execution, outbox, reconciliation, compensation, or ReplayEventV3/read-switch work.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 14 verification gaps are closed. Phase 15 can plan replay/lifecycle/read-switch work on top of a durable draft-only action boundary; Phase 17 remains the owner of external execution/outbox/reconciliation/compensation.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/14-demo-action-executor-boundary/14-07-SUMMARY.md`.
- Key modified files exist on disk.
- Task and auto-fix commits found in `git log --oneline --all`: `f035b9b`, `2772279`, `64e6094`, `d2f89f5`, `762b8b2`, `c662e97`, `fed3799`.
- No tracked file deletions detected in task commits.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
