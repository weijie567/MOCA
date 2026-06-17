---
phase: 09-business-tool-facade
plan: 03
subsystem: business-tools
tags: [adapters, pydantic, provenance, no-raw-leak]

requires:
  - phase: 09-01
    provides: ToolCallContext, ToolResultV2, ToolError, and BusinessFactRefV1 contracts
  - phase: 09-02
    provides: Registry dispatch seam for executable read adapters
provides:
  - Deterministic raw business-read to ToolResultV2 normalization
  - Strict projected success payloads with business-fact provenance
  - Invalid-response and raw-error no-leak guarantees
affects: [09-04-service, 09-05-read-switch, 10-investigate-loop]

tech-stack:
  added: []
  patterns:
    - Strict per-resource Pydantic projections at the raw adapter boundary
    - Constant safe summaries and errors that never interpolate raw upstream payloads

key-files:
  created:
    - src/business_tools/adapters.py
    - tests/business_tools/test_adapters.py
  modified: []

key-decisions: []

patterns-established:
  - "Business read adapters validate and project success data before constructing ToolResultV2."
  - "Invalid or malformed raw responses are replaced by fresh data-free invalid_response envelopes."

requirements-completed: [TOOL-02]

duration: 4min
completed: 2026-06-12
---

# Phase 09 Plan 03: Business Read Adapter Summary

**Strict raw-read adapters now map all order, refund, and ticket outcomes into safe typed results with business provenance and no invalid payload leakage**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-12T14:33:43Z
- **Completed:** 2026-06-12T14:37:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added executable order, refund-case, and ticket adapters while preserving the existing raw tools and authorization helper in place.
- Mapped raw success, forbidden, not-found, timeout, validation, database, malformed-response, and exception outcomes into deterministic `ToolResultV2` envelopes.
- Proved strict success projection, business-fact provenance, required integer latency, and serialized no-raw-leak behavior with nine focused test cases.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement deterministic raw-to-ToolResultV2 adapters** - `1b8d19d` (feat)
2. **Task 2: Add mapping, provenance, and no-raw-leak tests** - `baf3562` (test)

## Files Created/Modified

- `src/business_tools/adapters.py` - Strict raw read projections, status mapping, safe errors, latency, and business provenance.
- `tests/business_tools/test_adapters.py` - Mapping, no-leak, forwarding, latency, and provenance contract tests.

## Decisions Made

None - followed the approved plan and reused the existing input models and raw tools in place.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired malformed GSD tracking output**
- **Found during:** Plan metadata update
- **Issue:** The metric handler produced a four-column row under a five-column header, and the roadmap helper could not match the repository's table-based format.
- **Fix:** Restored a valid metric row and applied the equivalent minimal `3/5` Phase 9 roadmap progress update.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** Tracking diffs and Markdown table structure inspected before metadata commit.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Tracking artifacts remain valid and accurately reflect completed plan progress.

## Issues Encountered

- The plan's bare `pytest` command is not available on this shell's `PATH`; the identical focused suite passed through the repository's `.venv/bin/pytest` executable.

## Known Stubs

None. Empty policy evidence lists and unavailable logistics/merchant-risk adapters are intentional Phase 9 contract boundaries.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 09-04 can dispatch the three executable reads through the registry and aggregate typed results in `BusinessToolService`.
- Logistics and merchant-risk remain explicit registry-owned unavailable declarations with no adapter implementation.

## Self-Check: PASSED

- Confirmed both created files exist.
- Confirmed task commits `1b8d19d` and `baf3562` exist.
- Confirmed `34 passed` for `tests/business_tools/`.

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-12*
