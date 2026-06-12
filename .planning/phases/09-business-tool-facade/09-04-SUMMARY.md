---
phase: 09-business-tool-facade
plan: 04
subsystem: business-tools
tags: [facade, retry, authorization, aggregation, pydantic]

requires:
  - phase: 09-02
    provides: ToolRegistry descriptor and authorization pipeline
  - phase: 09-03
    provides: Typed order, refund-case, and ticket adapters
provides:
  - Bounded per-call BusinessToolService dispatch with stable retry identity
  - Default live registry composition root for executable business reads
  - Typed conditional BusinessContextV1 aggregation
affects: [09-05-read-switch, 10-investigate-loop]

tech-stack:
  added: []
  patterns:
    - Runtime AsyncSession injection outside serializable ToolCallContext
    - Deny-first scope and permission gates before registry dispatch
    - Distinct logical tool-call identity with stable per-call retry identity

key-files:
  created:
    - src/business_tools/service.py
    - tests/business_tools/test_service.py
  modified: []

key-decisions:
  - "BusinessToolService is the live registry-to-adapter composition root; callers inject only AsyncSession."

patterns-established:
  - "invoke_tool bounds retries by ToolCallContext.max_attempts and reuses tool_call_id across attempts."
  - "fetch_context mints one tool_call_id per requested resource and aggregates only typed tool results."

requirements-completed: [TOOL-01, TOOL-02]

duration: 5min
completed: 2026-06-12
---

# Phase 09 Plan 04: Business Tool Service Summary

**Bounded business-tool dispatch now enforces trusted scope and permissions, composes real read adapters, and aggregates typed business context**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-12T14:42:29Z
- **Completed:** 2026-06-12T14:47:47Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added the stable BusinessToolService boundary with fail-closed scope checks, pre-dispatch permission enforcement, bounded retries, and stable logical tool-call identity.
- Added the concrete default registry composition root wired to the real order, refund-case, and ticket adapters.
- Added typed conditional aggregation with complete, partial, insufficient, and aggregate-error semantics plus 12 focused service tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement bounded BusinessToolService.invoke_tool** - `c736d67` (feat)
2. **Task 2: Implement BusinessToolService.fetch_context aggregation** - `fd3b7ab` (feat)
3. **Task 3: Add retry, scope, and aggregation tests** - `52e6e9d` (test)

## Files Created/Modified

- `src/business_tools/service.py` - Bounded facade dispatch, live registry composition, deterministic scope helper, and typed context aggregation.
- `tests/business_tools/test_service.py` - Retry-cap, authorization, scope, aggregate-status, identity, and real-adapter composition coverage.

## Decisions Made

- Kept AsyncSession as a constructor-injected runtime dependency and left ToolCallContext serializable.
- Kept order/refund/ticket resource merchant checks at the existing raw `merchant_can_access` seam because their adapter inputs expose no merchant-identifying dimension.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Enforced descriptor permissions before registry dispatch**
- **Found during:** Task 3 (service authorization tests)
- **Issue:** The initial facade delegated missing-permission calls to `ToolRegistry.invoke`, but the approved plan requires permission-token denial before registry and adapter execution.
- **Fix:** Resolved the descriptor permission in BusinessToolService and returned a safe `PERMISSION_REQUIRED` denial before invoking the registry.
- **Files modified:** `src/business_tools/service.py`, `tests/business_tools/test_service.py`
- **Verification:** Missing-permission test asserts `registry.invoke.assert_not_awaited()`; all 46 business-tools tests pass.
- **Committed in:** `52e6e9d`

**2. [Rule 1 - Bug] Repaired malformed GSD tracking output**
- **Found during:** Plan metadata update
- **Issue:** State handlers inserted malformed decision, metric, and session values, while the roadmap helper could not match the repository's table-based format.
- **Fix:** Restored valid state fields and applied the equivalent minimal `4/5` roadmap and requirements-footer updates.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Verification:** Tracking diffs and Markdown table structure inspected before the metadata commit.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 2 auto-fixed (1 missing critical functionality, 1 bug)
**Impact on plan:** The fixes close the planned authorization boundary and preserve valid execution tracking without adding feature scope.

## Issues Encountered

- The sandbox initially blocked creation of `.git/index.lock`; task commits were rerun with approved git permissions and normal hooks.

## Known Stubs

None. Empty aggregate collections and optional freshness values are normative typed-result defaults.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 09-05 can switch the existing business-context node to `BusinessToolService.fetch_context`.
- Phase 10 can call `invoke_tool` as the bounded single-tool dispatch boundary.

## Self-Check: PASSED

- Confirmed `src/business_tools/service.py` and `tests/business_tools/test_service.py` exist.
- Confirmed task commits `c736d67`, `fd3b7ab`, and `52e6e9d` exist.
- Confirmed `12 passed` for the focused service suite and `46 passed` for `tests/business_tools/`.

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-12*
