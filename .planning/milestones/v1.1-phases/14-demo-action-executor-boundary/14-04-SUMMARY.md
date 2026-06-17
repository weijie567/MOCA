---
phase: 14-demo-action-executor-boundary
plan: 04
subsystem: approvals
tags: [approval-resume, action-draft, draft-outcome, final-response, demo-boundary]

requires:
  - phase: 14-03
    provides: canonical action_draft node and draft_outcome compatibility output
provides:
  - Approval resume reconciliation using draft_outcome.v1 not-executed semantics
  - Final-response wording that says a draft was created and no external action was executed
  - Regression tests for missing/side-effecting draft_outcome and forbidden external-success wording
affects: [phase-14, phase-15-replay-event-contract, approval-api, final-response]

tech-stack:
  added: []
  patterns:
    - draft_outcome.status == not_executed_demo plus external_side_effect is False as demo success signal
    - action_result retained only as deprecated compatibility/error context, not success authority

key-files:
  created:
    - .planning/phases/14-demo-action-executor-boundary/14-04-SUMMARY.md
  modified:
    - src/api/routers/approvals.py
    - src/agent/nodes/final_response.py
    - tests/test_approval_api.py
    - tests/test_approval_integration.py
    - tests/agent/test_nodes/test_final_response.py

key-decisions:
  - "Approval resume reconciliation treats only draft_outcome.v1 not_executed_demo with external_side_effect=false as success."
  - "Final response success wording reads action_draft/draft_outcome and does not use action_result.status == success."

patterns-established:
  - "API/final consumers validate demo draft success with the same draft_outcome helper semantics."
  - "Forbidden external-success phrase tests split literals so static scans can detect real positive wording."

requirements-completed: [DEMO-01, DEMO-02]

duration: 31 min
completed: 2026-06-16
---

# Phase 14 Plan 04: Approval Resume and Final/API Wording Summary

**Approval resume and final-response surfaces now use draft_outcome.v1 to report draft-created, not-executed demo behavior.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-06-16T01:22:33Z
- **Completed:** 2026-06-16T01:53:11Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Replaced approval resume reconciliation success checks with `draft_outcome.status == "not_executed_demo"` and `external_side_effect is False`.
- Updated final-response wording to say a compensation draft was created and demo mode did not execute coupon issuance, refund, ticket closure, or external actions.
- Added regression coverage for missing/side-effecting `draft_outcome`, legacy `action_result.status == "success"` misuse, and forbidden external-success phrases.

## Task Commits

1. **Task 1 RED: Approval draft outcome tests** - `7aa31f9` (test)
2. **Task 1 GREEN: Approval draft outcome reconciliation** - `509b0a4` (feat)
3. **Task 2 RED: Final response draft outcome tests** - `1ab2846` (test)
4. **Task 2 GREEN: Final response wording** - `3c5a1a6` (feat)

**Plan metadata:** committed separately after summary creation.

## Files Created/Modified

- `src/api/routers/approvals.py` - Reconciles approved resume retries from `draft_outcome`, fail-closing invalid demo outcomes under `action_draft_reconcile_failed`.
- `src/agent/nodes/final_response.py` - Builds approved and auto-allowed draft-created/not-executed wording from `action_draft` and `draft_outcome`.
- `tests/test_approval_api.py` - Adds API reconciliation tests for valid, missing, and side-effecting draft outcomes plus a static success-sentinel guard.
- `tests/test_approval_integration.py` - Asserts approved flows persist `not_executed_demo` with no external side effect.
- `tests/agent/test_nodes/test_final_response.py` - Adds final wording, forbidden phrase, side-effecting outcome, and legacy `action_result` regression tests.

## Decisions Made

- `draft_outcome.v1` is the only success signal for API/final demo draft surfaces.
- `action_result` remains readable only for error context and deprecated compatibility output; it is not a success authority.
- Final response risk text now says approval is needed before creating an action draft rather than implying later external execution.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- Initial sandboxed DB-backed pytest runs could not connect to local PostgreSQL (`PermissionError: Operation not permitted`). The plan-level pytest target was rerun with approved unsandboxed DB access and passed.
- One interim Task 1 verification attempt hit PostgreSQL schema setup contention while another parallel executor was active. A focused reconciliation slice passed immediately, and the full exact plan pytest command passed after Task 2.
- In a fresh worktree, dev test dependencies were available only after invoking the dev extra during interim checks. The final exact plan verification commands ran successfully.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_final_response.py tests/test_approval_api.py tests/test_approval_integration.py -q --tb=short` - passed, 41 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py src/agent/nodes/final_response.py tests/test_approval_api.py tests/test_approval_integration.py tests/agent/test_nodes/test_final_response.py` - passed.
- `rg -n "execute_action\\(|action_result.*status.*success|status.*success.*action_result" src/api/routers/approvals.py` - no matches.
- `rg -n "action_result.*status.*success|status.*success.*action_result" src/agent/nodes/final_response.py` - no matches.
- `rg -n "waiting for final issuance|issued coupon|refunded|closed ticket|external success|等待最终发放|已发放|已退款|已关闭工单|执行成功" src/agent/nodes/final_response.py tests/agent/test_nodes/test_final_response.py tests/test_approval_api.py tests/test_approval_integration.py` - no matches.

## TDD Gate Compliance

- RED gate commits present: `7aa31f9`, `1ab2846`.
- GREEN gate commits present after RED: `509b0a4`, `3c5a1a6`.
- No refactor-only commit was needed.

## Known Stubs

None.

## Threat Flags

None - no new endpoints, schema changes, file access paths, or trust-boundary surfaces were introduced beyond the planned approval/final wording checks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 14-05 can consume the same `draft_outcome` truth for trace/event projection without relying on final/API `action_result.status == "success"` behavior.

## Self-Check: PASSED

- Summary file exists.
- Key modified files exist.
- Task commits found: `7aa31f9`, `509b0a4`, `1ab2846`, `3c5a1a6`.
- No tracked file deletions detected.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
