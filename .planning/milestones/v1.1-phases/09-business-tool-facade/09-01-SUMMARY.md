---
phase: 09-business-tool-facade
plan: 01
subsystem: business-tools
tags: [pydantic, contracts, provenance, trusted-context]

requires:
  - phase: 08-knowledge-facade
    provides: Canonical EvidenceRefV1 policy provenance contract
provides:
  - Trusted ToolCallContext v2 projection
  - Typed ToolResultV2 and BusinessContextV1 contracts
  - Separate BusinessFactRefV1 business provenance
affects: [09-02-registry, 09-03-adapters, 09-04-service, 09-05-read-switch]

tech-stack:
  added: []
  patterns:
    - Strict Pydantic v2 facade contracts with extra fields forbidden
    - Canonical cross-facade schema imports instead of reduced redefinitions

key-files:
  created:
    - src/business_tools/__init__.py
    - src/business_tools/schemas.py
    - tests/business_tools/__init__.py
    - tests/business_tools/test_schemas.py
  modified: []

key-decisions: []

patterns-established:
  - "Business and policy provenance remain separate through BusinessFactRefV1 and canonical EvidenceRefV1."
  - "ToolCallContext stays serializable and carries no runtime database session."

requirements-completed: [TOOL-01, TOOL-02]

duration: 4min
completed: 2026-06-12
---

# Phase 09 Plan 01: Business Tool Contracts Summary

**Strict Pydantic v2 contracts establish trusted tool-call context, required-latency results, and separate business versus policy provenance**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-12T14:15:05Z
- **Completed:** 2026-06-12T14:18:35Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added all six Phase 9 business-tool facade contracts with exact schema-version literals and result statuses.
- Reused canonical `EvidenceRefV1` while introducing non-coercible `BusinessFactRefV1` provenance.
- Added 15 focused schema checks covering statuses, strict context fields, defaults, provenance separation, and required latency.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create all v2 business-tool contracts** - `fb83c8f` (feat)
2. **Task 2: Add schema contract tests** - `0564268` (test)

## Files Created/Modified

- `src/business_tools/__init__.py` - Business-tool facade package marker.
- `src/business_tools/schemas.py` - Canonical Phase 9 context, request, result, error, provenance, and aggregate contracts.
- `tests/business_tools/__init__.py` - Business-tool test package marker.
- `tests/business_tools/test_schemas.py` - Focused contract validation suite.

## Decisions Made

None - followed the approved plan and contract-spec shapes as specified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired malformed GSD tracking output**
- **Found during:** Plan metadata update
- **Issue:** The requirements handler split bold requirement IDs across lines, the metric handler produced a four-column row under a five-column header, and the roadmap helper could not match the repository's roadmap format.
- **Fix:** Restored valid requirement lines and metric columns, then applied the equivalent minimal `1/5` Phase 9 roadmap progress update.
- **Files modified:** `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** Tracking diffs and Markdown structure inspected before metadata commit.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Tracking artifacts remain valid and accurately reflect completed plan progress.

## Issues Encountered

- The plan's bare `python` verification command lacked project dependencies in the shell environment. The identical assertion set passed under the repository-standard `UV_CACHE_DIR=/tmp/uv-cache uv run python` environment.
- The roadmap update helper reported no matching checkbox because this roadmap uses a progress table and `**Plans**` field rather than per-plan checkboxes.

## Known Stubs

None. Optional `None` values and empty provenance lists are intentional normative contract defaults.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Registry, adapter, service, and read-switch plans can import the canonical Phase 9 contracts.
- No blockers identified.

## Self-Check: PASSED

- Confirmed all four created files exist.
- Confirmed task commits `fb83c8f` and `0564268` exist.

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-12*
