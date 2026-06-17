---
phase: 15-replay-event-contract
plan: 05
subsystem: replay
tags: [replay, api, event-store, access-control, pytest]

requires:
  - phase: 15-02
    provides: ReplayService append/projection boundary and shared allocator
  - phase: 15-03
    provides: V3 operation pairing and legacy/minimal provenance projection
  - phase: 15-04
    provides: run_status_changed lifecycle replay events
provides:
  - Event-store-first ReplayService.get_replay read path
  - GET /api/v1/agent-runs/{run_id}/replay route
  - Replay API tests for V3 response shape, ordering, access control, and /trace fallback
affects: [15-06-replay-safety, replay-api, trace-fallback]

tech-stack:
  added: []
  patterns:
    - Replay API delegates V3 response construction to ReplayService
    - /trace remains isolated on TraceRepository.build_timeline as rollback fallback
    - ReplayResponseV3 timelines omit non-contract projection metadata

key-files:
  created:
    - tests/replay/test_replay_api.py
  modified:
    - src/replay/service.py
    - src/api/routers/traces.py
    - tests/replay/test_replay_service.py

key-decisions:
  - "/replay uses ReplayService.get_replay and reads agent_trace_events ordered by sequence instead of legacy TraceRepository.build_timeline."
  - "/trace remains the legacy rollback/debug fallback and continues using TraceRepository.build_timeline."
  - "ReplayResponseV3 timeline entries are strict ReplayEventV3 items, so retention_class remains append/projection metadata outside the response contract."

patterns-established:
  - "Route-level access parity reuses the /trace tenant-scoped run lookup and supervisor role set."
  - "Replay API tests create event-store rows without legacy AgentStep rows to prove event-store-first reads."

requirements-completed: [REPLAY-01, REPLAY-03]

duration: 11 min
completed: 2026-06-16
---

# Phase 15 Plan 05: Replay API Read-Switch Summary

**Event-store-first `/replay` endpoint returning strict sequence-ordered ReplayResponseV3 while `/trace` remains the legacy fallback**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-16T15:20:17Z
- **Completed:** 2026-06-16T15:31:25Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `ReplayService.get_replay()` to load `AgentTraceEvent` rows ordered by `sequence` and return `replay_response.v3`.
- Added `/api/v1/agent-runs/{run_id}/replay` with the same tenant, owner, and supervisor access semantics as `/trace`.
- Added replay API tests for owner/admin access, cross-tenant 404, same-tenant non-owner 403, invalid UUID 404, sequence ordering, minimal-row provenance, and `/trace` fallback behavior.

## Task Commits

1. **Task 1 RED: replay read service tests** - `a923fa5` (test)
2. **Task 1 GREEN: event-store replay read service** - `42842ba` (feat)
3. **Task 2 RED: replay route access tests** - `34e6a64` (test)
4. **Task 2 GREEN: replay route with trace access parity** - `ec85320` (feat)

## Files Created/Modified

- `src/replay/service.py` - Adds `get_replay()` and strict response projection for replay reads.
- `src/api/routers/traces.py` - Adds `GET /{run_id}/replay` beside the preserved `/trace` route.
- `tests/replay/test_replay_service.py` - Adds service-level event-store ordering and minimal provenance tests.
- `tests/replay/test_replay_api.py` - Adds replay API access/read-switch tests and `/trace` fallback smoke coverage.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_api.py -q --tb=short` - PASS, 10 passed after Task 1.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/service.py tests/replay/test_replay_api.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_api.py tests/test_trace_api.py -q --tb=short` - PASS, 16 passed after Task 2.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/traces.py src/api/schemas/approvals.py tests/replay/test_replay_api.py tests/test_trace_api.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_api.py tests/replay/test_replay_service.py tests/test_trace_api.py -q --tb=short` - PASS, 26 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay src/api/routers/traces.py src/api/schemas/approvals.py tests/replay tests/test_trace_api.py` - PASS.
- Acceptance greps for `get_replay`, `ReplayResponseV3`, sequence ordering, route delegation, access statuses, and `build_timeline` isolation passed.

## Decisions Made

- Kept `/replay` and `/trace` as separate read models: `/replay` is event-store-first V3; `/trace` remains rollback/debug composition.
- Reused `TraceRepository.get_run()` only for tenant-scoped run lookup, not replay timeline construction.
- Preserved API schema ownership under `src/replay/schemas.py`; no duplicate replay schemas were added under API schemas.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Kept replay responses strict after retention metadata projection**
- **Found during:** Task 1 (ReplayService get_replay implementation)
- **Issue:** Existing `project_event()` appends `retention_class` to the projected retention dictionary, but `ReplayResponseV3` requires every timeline item to validate as strict `ReplayEventV3`.
- **Fix:** Added an `include_retention_class` option and made `get_replay()` use strict timeline items without the extra metadata.
- **Files modified:** `src/replay/service.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py -q --tb=short` and final plan verification passed.
- **Committed in:** `42842ba`

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** No scope expansion. The fix enforces the plan requirement that `/replay` returns strict V3 timeline items.

## Issues Encountered

- The Task 1 verification command named `tests/replay/test_replay_api.py` before route tests existed. The file was created during Task 1 and populated by Task 2, so the exact plan verification command could run without changing the plan.

## Known Stubs

None. Stub scan found only legitimate optional `None` defaults and no placeholder, TODO, or unwired mock runtime behavior.

## Threat Flags

None. The new network endpoint and access-control surface were expected in the plan threat model and are covered by replay API tests.

## TDD Gate Compliance

- RED commits are present before GREEN commits for both tasks.
- Task 1 RED failed on missing `ReplayService.get_replay`; GREEN passed after the service read method was added.
- Task 2 RED failed on the missing `/replay` route while `/trace` fallback passed; GREEN passed after the route was added.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 15-06. `/replay` now reads event-store rows first and returns sequence-ordered V3 responses with access parity; `/trace` remains the rollback fallback path.

## Self-Check: PASSED

- Verified key files exist on disk.
- Verified task commit hashes exist in git history.
- No missing summary claims found.

---
*Phase: 15-replay-event-contract*
*Completed: 2026-06-16*
