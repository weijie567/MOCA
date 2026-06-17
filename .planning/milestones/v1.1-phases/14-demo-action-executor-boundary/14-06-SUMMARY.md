---
phase: 14-demo-action-executor-boundary
plan: 06
subsystem: testing
tags: [action-draft, demo-boundary, coverage, pytest, ruff]

requires:
  - phase: 14-demo-action-executor-boundary
    provides: action_draft.v2 persistence, action_draft graph boundary, draft_outcome wording, and trace projection from plans 14-01 through 14-05
  - phase: 13-approval-state-machine
    provides: approval revision and ActionSafetySnapshot binding consumed by action drafts
provides:
  - Negative boundary coverage for no external execution/outbox/reconciliation/compensation surfaces
  - Static guardrails for execute_action and action_result compatibility
  - Final Phase 14 source coverage artifact with deferred Phase 15/17 owners
  - Focused, full-suite, and ruff final gate results
affects: [phase-14, phase-15-replay-event-contract, phase-17-external-action-execution]

tech-stack:
  added: []
  patterns: [negative architecture coverage, evidence-first coverage matrix, compatibility removal gate tracking]

key-files:
  created:
    - .planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md
    - .planning/phases/14-demo-action-executor-boundary/14-06-SUMMARY.md
  modified:
    - tests/actions/test_action_draft_v2.py
    - tests/architecture/test_action_draft_boundaries.py
    - tests/agent/test_events.py
    - tests/test_trace_api.py
    - tests/agent/test_nodes/test_final_response.py

key-decisions:
  - "Phase 14 final coverage treats ReplayEventV3/lifecycle/read-switch work as Phase 15-owned and external execution/outbox/reconciliation/compensation as Phase 17-owned."
  - "execute_action and action_result compatibility remain temporary surfaces with Phase 15 Replay Event Contract removal/replacement gates targeting 2026-07-16 unless Phase 15 is replanned."

patterns-established:
  - "Final action-draft boundary tests cover absent external tables, imports, events, trace payload leakage, and external-success wording."
  - "Coverage rows are marked COVERED only when tied to concrete source, test, or command evidence."

requirements-completed: [DEMO-01, DEMO-02]

duration: 16 min
completed: 2026-06-16
---

# Phase 14 Plan 06: Negative Boundary Coverage and Source Audit Summary

**Final Phase 14 boundary gates prove demo mode creates durable drafts only, with downstream replay and external execution explicitly deferred to their owner phases.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-06-16T02:24:45Z
- **Completed:** 2026-06-16T02:40:30Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added final negative tests proving no Phase 17 external execution tables, imports, event names, trace payload leaks, or external-success wording were introduced.
- Created `14-COVERAGE.md` mapping DEMO-01, DEMO-02, D-01..D-28, research constraints, compatibility dispositions, and Phase 15/17 deferrals to concrete evidence.
- Ran the focused Phase 14 gate, full pytest suite, and ruff across `src` and `tests`.

## Task Commits

1. **Task 1: Add negative boundary coverage for draft-only semantics** - `bf7c173` (test)
2. **Task 2: Create coverage artifact and run final gates** - `4c9fb5e` (docs)

## Files Created/Modified

- `tests/actions/test_action_draft_v2.py` - Adds SQLAlchemy metadata negative coverage for absent Phase 17 external tables.
- `tests/architecture/test_action_draft_boundaries.py` - Adds static scans for external execution imports and legacy `action_result.status == "success"` dependencies.
- `tests/agent/test_events.py` - Adds `action_execution_*` registration/emission negative coverage.
- `tests/test_trace_api.py` - Adds stronger trace projection coverage excluding raw draft payload data.
- `tests/agent/test_nodes/test_final_response.py` - Adds direct forbidden phrase fixtures and demo draft wording checks.
- `.planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md` - Final evidence-first coverage and compatibility disposition artifact.
- `.planning/phases/14-demo-action-executor-boundary/14-06-SUMMARY.md` - Plan completion record.

## Decisions Made

- Followed the Phase 14 boundary: no production runtime behavior was added because the new negative assertions passed against the existing 14-01..14-05 implementation.
- Recorded Phase 15 as owner for ReplayEventV3, lifecycle finalizer, read-switch, and frontend timeline label cleanup.
- Recorded Phase 17 as owner for external execution, outbox, reconciliation, compensation, and adapter dispatch.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed.  
**Impact on plan:** No scope change.

## Issues Encountered

- The first Task 1 pytest run inside the sandbox could not open the local PostgreSQL socket (`PermissionError: [Errno 1] Operation not permitted`). The same command passed with approved local database access.

## TDD Gate Compliance

- Task 1 was marked `tdd="true"` but was a test-coverage hardening task over behavior already implemented by earlier Phase 14 plans.
- Test commit present: `bf7c173`.
- No separate GREEN implementation commit was needed; the added tests passed against existing source after DB access was granted.

## Verification

Passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_action_draft_v2.py tests/architecture/test_action_draft_boundaries.py tests/agent/test_events.py tests/test_trace_api.py tests/agent/test_nodes/test_final_response.py -q --tb=short
# 60 passed, 1 warning

UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/test_approval_integration.py tests/test_trace_api.py tests/agent/test_graph.py tests/agent/test_nodes/test_final_response.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py tests/agent/test_nodes/test_receive_request.py -q --tb=short
# 118 passed, 1 warning

UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short
# 813 passed, 1 warning

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests
# All checks passed
```

Acceptance checks passed:

```bash
rg -n "action_executions|action_outbox_events|action_reconciliation_jobs|action_compensation_records|action_execution_" tests/actions/test_action_draft_v2.py tests/architecture/test_action_draft_boundaries.py tests/agent/test_events.py
rg -n "action_result.*status.*success|status.*success.*action_result" tests/architecture/test_action_draft_boundaries.py
rg -n "waiting for final issuance|issued coupon|refunded|closed ticket|external success|等待最终发放|已发放|已退款|已关闭工单|执行成功" tests/agent/test_nodes/test_final_response.py
rg -n "DEMO-01|DEMO-02|D-01|D-27|D-28|DEFERRED_WITH_OWNER|execute_action compatibility|action_result compatibility|2026-07-16" .planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md
rg -n "normative contract fields|implementation extensions|proposed_action.*payload|payload.*proposed_action|docs/contract-spec.md" .planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md
rg -n "Phase 15.*delayed|replanned|owner phase|removal gate|target date" .planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md
```

`rg -n "MISSING" .planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md` returned no matches.

## Known Stubs

None. Stub scan hits were intentional empty list/dict values inside tests, not runtime or UI stubs.

## Threat Flags

None - this plan added tests and planning docs only; it introduced no new endpoint, auth path, file access pattern, schema, or trust-boundary surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 14 has final negative boundary coverage and source audit evidence. Phase 15 can plan replay/lifecycle/read-switch work with explicit compatibility removal gates for `execute_action` and `action_result`; Phase 17 remains the first owner of external execution.

## Self-Check: PASSED

- `14-COVERAGE.md` exists.
- `14-06-SUMMARY.md` exists.
- Task commits found in `git log --oneline --all`: `bf7c173`, `4c9fb5e`.
- No tracked file deletions detected in either task commit.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
