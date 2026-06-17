---
phase: 15-replay-event-contract
plan: 06
subsystem: replay
tags: [replay, redaction, action-draft, coverage, verification]

requires:
  - phase: 15-05
    provides: event-store-first `/replay` route, access parity, and `/trace` rollback fallback
provides:
  - Replay-facing demo draft safety cleanup
  - Raw action payload replay regressions
  - Final Phase 15 coverage and deferred-owner record
  - Final Alembic, focused pytest, full pytest, and ruff gate evidence
affects: [phase-15-verification, phase-16-memory, phase-17-external-execution]

tech-stack:
  added: []
  patterns:
    - `action_draft_created` replay payload carries safe `draft_outcome` rather than raw proposed action data
    - Final phase coverage records owner-named deferrals and exact command statuses

key-files:
  created:
    - .planning/phases/15-replay-event-contract/15-COVERAGE.md
    - .planning/phases/15-replay-event-contract/15-06-SUMMARY.md
  modified:
    - src/actions/service.py
    - tests/replay/test_replay_redaction_retention.py
    - tests/replay/test_replay_api.py
    - tests/agent/test_tools/test_create_coupon_grant_draft.py
    - .planning/phases/15-replay-event-contract/15-COVERAGE.md

key-decisions:
  - "`action_draft_created` remains draft-only and now projects `DraftOutcomeV1` in redacted replay payloads."
  - "Phase 15 marks external execution/outbox/reconciliation/compensation and `action_execution_*` as Phase 17-owned deferrals."
  - "`/trace` remains the rollback fallback through `TraceRepository.build_timeline()` while `/replay` stays event-store-first."

patterns-established:
  - "Replay-facing action draft events expose only safe refs plus `execution_mode=demo`, `external_side_effect=false`, and `draft_outcome.status=not_executed_demo`."
  - "Coverage artifacts must include final command rows with `PASS`, `FAIL`, or `NOT_RUN`, plus owner-named blocking follow-ups for non-passing gates."

requirements-completed: [REPLAY-01, REPLAY-02, REPLAY-03]

duration: 36 min
completed: 2026-06-16
---

# Phase 15 Plan 06: Replay Safety and Final Coverage Summary

**Draft-only replay projection for demo action drafts, final Phase 15 coverage matrix, and passing Alembic/pytest/ruff verification gates**

## Performance

- **Duration:** 36 min
- **Started:** 2026-06-16T15:35:47Z
- **Completed:** 2026-06-16T16:12:13Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added RED/GREEN coverage proving `action_draft_created` replay data cannot imply external execution.
- Added `DraftOutcomeV1` to the action draft event redacted payload while keeping raw `ActionDraft.payload` out of `/replay`.
- Created `15-COVERAGE.md` mapping REPLAY-01, REPLAY-02, REPLAY-03, source decisions, deferred owners, compatibility disposition, `/trace` fallback, and final command statuses.
- Ran and recorded the final Phase 15 Alembic, focused pytest, full pytest, exact replay/event/trace pytest, and ruff gates.

## Task Commits

1. **Task 1 RED: demo draft replay safety regression** - `888d1f4` (test)
2. **Task 1 GREEN: safe draft outcome projection** - `dbc2f91` (feat)
3. **Task 2: coverage and deferred-owner record** - `7e20e88` (docs)
4. **Task 3: final verification gate record** - `92b7746` (docs)

## Files Created/Modified

- `src/actions/service.py` - Adds safe `DraftOutcomeV1` data to `action_draft_created` redacted replay payloads.
- `tests/agent/test_tools/test_create_coupon_grant_draft.py` - Adds the failing RED regression and projection assertions for draft-only replay semantics.
- `tests/replay/test_replay_redaction_retention.py` - Adds replay projection assertions excluding raw payload and external execution markers.
- `tests/replay/test_replay_api.py` - Adds `/replay` response assertions proving raw `ActionDraft.payload` remains absent.
- `.planning/phases/15-replay-event-contract/15-COVERAGE.md` - Records requirement coverage, owner-named deferrals, `/trace` fallback, compatibility disposition, and final command statuses.
- `.planning/phases/15-replay-event-contract/15-06-SUMMARY.md` - Records this plan outcome.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_replay_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` - PASS, 29 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/service.py src/repositories/trace_repo.py tests/replay tests/agent/test_tools/test_create_coupon_grant_draft.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py tests/approvals/test_events.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` - PASS, 133 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - PASS, 873 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short` - PASS, 70 passed, 1 warning.

## Decisions Made

- Kept `action_result` compatibility output as non-success `draft_created`, while replay-facing data uses `draft_outcome.status="not_executed_demo"` and `external_side_effect=false`.
- Kept Phase 17 external execution, outbox, reconciliation, compensation, `action_execution_*`, and external worker allocator tests out of Phase 15.
- Kept active SLA scanner enablement owned by a named post-Phase 15 SLA Scanner Enablement phase.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.  
**Impact on plan:** No scope expansion.

## Issues Encountered

None.

## Known Stubs

None. Stub scan found only an intentional empty-list assertion in a test helper, not placeholder or unwired runtime behavior.

## Threat Flags

None. The plan strengthened an existing action draft replay surface and did not add new network endpoints, auth paths, file access patterns, schema changes, external execution, outbox, reconciliation, or compensation behavior.

## TDD Gate Compliance

- RED commit `888d1f4` added a failing replay demo draft safety regression; it failed on missing `draft_outcome`.
- GREEN commit `dbc2f91` implemented the safe projection and passed the focused replay/action tests.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 15 is complete and ready for verification: all final gate commands are recorded as `PASS` in `15-COVERAGE.md`. Phase 16 remains owner for memory identity/tombstones/review workflow. Phase 17 remains owner for external execution/outbox/reconciliation/compensation and `action_execution_*`.

## Self-Check: PASSED

- Verified key files exist on disk.
- Verified task commit hashes exist in git history: `888d1f4`, `dbc2f91`, `7e20e88`, `92b7746`.
- No tracked file deletions detected in task commits.

---
*Phase: 15-replay-event-contract*
*Completed: 2026-06-16*
