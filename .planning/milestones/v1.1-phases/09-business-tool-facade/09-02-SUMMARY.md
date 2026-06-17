---
phase: 09-business-tool-facade
plan: 02
subsystem: business-tools
tags: [registry, authorization, pydantic, json-schema]

requires:
  - phase: 09-01
    provides: ToolCallContext, ToolError, and ToolResultV2 contracts
provides:
  - Canonical nine-entry business-tool descriptor table
  - Ordered registry authorization and validation pipeline
  - Write-tool hard block and safe no-leak rejection envelopes
affects: [09-03-adapters, 09-04-service, 10-investigate-loop]

tech-stack:
  added: []
  patterns:
    - JSON-schema-shaped descriptors with private Pydantic input-model association
    - Resolve then write/caller/permission/input gates before adapter execution

key-files:
  created:
    - src/business_tools/registry.py
    - tests/business_tools/test_registry.py
  modified: []

key-decisions:
  - "Write descriptors remain declared but are hard-blocked before adapter access; action event families remain deferred to Phase 17."
  - "AsyncSession is passed explicitly to registry adapters and never added to ToolCallContext."

patterns-established:
  - "Registry-created rejections always discard data, use safe constant summaries, set latency_ms=0, and leave audit_ref=None."
  - "The descriptor table derives investigate allowlist membership and resource-type consistency."

requirements-completed: [TOOL-01, TOOL-03]

duration: 7min
completed: 2026-06-12
---

# Phase 09 Plan 02: Business Tool Registry Summary

**Nine canonical business-tool descriptors now dispatch through an ordered authorization and validation pipeline with write execution hard-blocked**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-12T14:23:25Z
- **Completed:** 2026-06-12T14:29:59Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Declared the complete eight read/retrieval tools plus the declare-only coupon draft write tool from one descriptor table.
- Enforced resolve, write block, caller allowlist, required permission, input validation, adapter, and output validation ordering.
- Added 10 registry tests proving rejection-before-adapter behavior, explicit session threading, unavailable declarations, and no raw invalid-response leakage.

## Task Commits

Each task was committed atomically:

1. **Task 1: Define ToolDescriptor and the full descriptor table** - `d0d6c0b` (feat)
2. **Task 2: Implement ToolRegistry.invoke gate pipeline** - `7ef13af` (feat)
3. **Task 3: Add registry gate and consistency tests** - `3434796` (test)

## Files Created/Modified

- `src/business_tools/registry.py` - Canonical descriptors, registration, gate pipeline, and JSON-schema validation boundary.
- `tests/business_tools/test_registry.py` - Authorization ordering, no-execution, no-leak, delegation, and consistency tests.

## Decisions Made

- Kept `create_coupon_grant_draft.event_family=None` with the approved SCF-3 Phase 17 deferral while denying it before all other gates.
- Used an explicit fourth `AsyncSession` runtime parameter per SCF-8 so trusted `ToolCallContext` remains serializable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed declared-only input model construction**
- **Found during:** Task 3 (registry gate and consistency tests)
- **Issue:** Pydantic v2 cannot instantiate the bare `BaseModel` used after JSON-schema validation for declared-only tools.
- **Fix:** Added an internal permissive `_SchemaInput` model and validated declared-only input into it.
- **Files modified:** `src/business_tools/registry.py`
- **Verification:** `test_declared_only_tool_returns_unavailable_without_adapter` and the complete registry suite pass.
- **Committed in:** `3434796`

**2. [Rule 1 - Bug] Repaired malformed GSD tracking output**
- **Found during:** Plan metadata update
- **Issue:** The requirements handler split `TOOL-03` across lines, the metric handler produced a four-column row under a five-column header, and the roadmap helper could not match the repository's table-based format.
- **Fix:** Restored valid requirement and metric rows, updated traceability text, and applied the equivalent minimal `2/5` roadmap progress update.
- **Files modified:** `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** Tracking diffs and Markdown structure inspected before metadata commit.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes are required for correct registry behavior and valid execution tracking, with no feature scope added.

## Issues Encountered

None.

## Known Stubs

None. Retrieval, logistics, merchant-risk, and write adapters are intentionally unavailable or denied by the approved phase ownership boundaries.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 09-03 can provide the three executable read adapters through the registry's optional adapter-loading seam.
- Plan 09-04 can use `ToolRegistry.invoke` as the facade's single-tool dispatch boundary.

## Self-Check: PASSED

- Confirmed both created files exist.
- Confirmed task commits `d0d6c0b`, `7ef13af`, and `3434796` exist.
- Confirmed `25 passed` for `tests/business_tools/`.

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-12*
