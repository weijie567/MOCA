---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
plan: 01
subsystem: memory
tags: [case-memory, case-precedent, mem-04, static-guards, memory-policy]

requires:
  - phase: 46-session-context-repositioning
    provides: session-context boundary and reviewed case-memory retrieval alignment
provides:
  - reviewed closed-case precedent contract semantics for case_memories
  - Phase 47 static red-line guards for protected memory tables and pytest entrypoints
  - review-required closed_case_cwc_candidate source type foundation
affects: [memory, case-memory, case-working-context, reviewed-memory-context, phase-47]

tech-stack:
  added: []
  patterns:
    - static semantic and destructive-schema guards for memory boundaries
    - review-required source-type policy gate before candidate generation exists

key-files:
  created:
    - tests/memory/test_phase47_case_precedent_alignment.py
    - .planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-01-SUMMARY.md
  modified:
    - docs/contract-spec.md
    - docs/current-implementation-map.md
    - docs/architecture-overview.md
    - .planning/MEMORY-REDESIGN-DECISIONS.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - src/memory/schemas.py
    - src/memory/policy.py
    - tests/memory/test_memory_policy.py

key-decisions:
  - "closed_case_cwc_candidate is a CaseMemorySourceType and is review-required only."
  - "MemorySourceRefV1 and ALLOWED_SOURCE_REF_KEYS stay fixed; close/CWC identity will use existing event_id and outcome_id."
  - "Phase 47 static migration checks use the repository's actual src/db/migrations/versions directory."

patterns-established:
  - "Planning-prose destructive-storage guard strips fenced code, interface/source-audit/threat-model sections, pattern lines, and prohibition language before scanning."
  - "Generated closed-case candidates are contractually invisible to reviewed retrieval until approved."

requirements-completed: [MEM-04]

duration: 6 min
completed: 2026-07-03
---

# Phase 47 Plan 01: Contract and Source Policy Foundation Summary

**Reviewed closed-case precedent semantics are now documented and statically guarded, with `closed_case_cwc_candidate` accepted only as a review-required case-memory source.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-03T13:38:19Z
- **Completed:** 2026-07-03T13:45:01Z
- **Tasks:** 2/2
- **Files modified:** 9

## Accomplishments

- Locked `case_memories` / `case_memory` as reviewed closed-case precedent, not active case state, and documented the Phase 47 closed-CWC candidate review boundary.
- Added `tests/memory/test_phase47_case_precedent_alignment.py` with static guards for contract terms, protected table identity, no completed-run close inference, Phase 47 pytest entrypoints, DEFER-3 carry-forward, and source-ref stability.
- Added `closed_case_cwc_candidate` to `CaseMemorySourceType` and `REVIEW_REQUIRED_CASE_SOURCE_TYPES` only; it is not auto-approved and does not extend source-ref identity keys.

## Task Commits

1. **Task 1: Lock case precedent semantics and static red lines** - `6e0af09` (`docs`)
2. **Task 2 RED: Add failing closed-case source policy tests** - `38ac0d9` (`test`)
3. **Task 2 GREEN: Add review-required closed-case source type** - `e80c009` (`feat`)

**Plan metadata:** committed separately after this summary.

## Files Created/Modified

- `docs/contract-spec.md` - Added reviewed closed-case precedent and closed-CWC candidate review semantics.
- `docs/current-implementation-map.md` - Reaffirmed `search_case_memory` as `MemoryToolExecutor -> CaseMemoryService.retrieve_reviewed(...)`.
- `docs/architecture-overview.md` - Clarified reviewed case memory vs active CWC and metadata/text retrieval.
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - Added Phase 47 DEFER-2 trace and carried `DEFER-3 -> Phase 48`.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Logged the handled GREEN validation failure.
- `src/memory/schemas.py` - Added `closed_case_cwc_candidate` to `CaseMemorySourceType`.
- `src/memory/policy.py` - Added `closed_case_cwc_candidate` to review-required case source types only.
- `tests/memory/test_memory_policy.py` - Added RED/GREEN policy and validation coverage.
- `tests/memory/test_phase47_case_precedent_alignment.py` - Added Phase 47 static alignment guards.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -x -q` -> `7 passed, 1 warning`
- RED: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_memory_policy.py -x -q` -> failed as expected because `closed_case_cwc_candidate` was classified as `unknown_source_type`
- GREEN final: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_memory_policy.py -x -q` -> `18 passed, 1 warning`
- Plan gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_memory_policy.py -q` -> `18 passed, 1 warning`

Warnings were the existing LangGraph/LangChain pending deprecation warning.

## Decisions Made

- Used a dedicated `closed_case_cwc_candidate` source type because the Phase 47 provenance needs are more specific than generic `summary_candidate`.
- Kept `MemorySourceRefV1` and `ALLOWED_SOURCE_REF_KEYS` unchanged, including `policy_version`; future close/CWC identity uses existing allowed fields.
- Adapted the migration static guard to `src/db/migrations/versions`, the repository's real Alembic revision directory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used actual Alembic migration directory for static guard**
- **Found during:** Task 1 (Lock case precedent semantics and static red lines)
- **Issue:** The plan referenced `alembic/versions/`, but this repository stores migration revisions under `src/db/migrations/versions/`.
- **Fix:** The implementation-surface guard scans `src/db/models.py` plus Phase 47-identifying files under `src/db/migrations/versions/`.
- **Files modified:** `tests/memory/test_phase47_case_precedent_alignment.py`
- **Verification:** Focused Phase 47 alignment test passed.
- **Committed in:** `6e0af09`

**2. [Rule 1 - Bug] Corrected source-type insertion target after GREEN validation failure**
- **Found during:** Task 2 (Add review-required closed-case source type)
- **Issue:** The first GREEN patch inserted `closed_case_cwc_candidate` into long-term source surfaces, so case policy still reported `unknown_source_type`.
- **Fix:** Moved the source type into `CaseMemorySourceType` and `REVIEW_REQUIRED_CASE_SOURCE_TYPES`, removed it from long-term surfaces, and logged the validation incident.
- **Files modified:** `src/memory/schemas.py`, `src/memory/policy.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Focused Task 2 command passed with `18 passed, 1 warning`.
- **Committed in:** `e80c009`

---

**Total deviations:** 2 auto-fixed (1 blocking issue, 1 implementation bug).
**Impact on plan:** Both fixes preserved the intended Phase 47 boundary; no source-ref schema extension, table rename, migration, or Phase 48 behavior was introduced.

## Issues Encountered

- Task 2 GREEN initially failed because the source string landed in the long-term memory source lists. It was corrected and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No authentication gates occurred.

## Known Stubs

None. Stub-pattern scan hits were optional/empty defaults in typed schemas and test fixtures, plus a pre-existing implementation-map placeholder row; none are unresolved implementation stubs for this plan.

## Threat Flags

None beyond the plan threat model. This plan added static tests, documentation, and source-type policy only; it introduced no new network endpoint, auth path, file access boundary, schema migration, or external trust surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 47-02. MEM-04 is not phase-complete yet: remaining Phase 47 plans still need the trusted closed-case projection service, governed write lifecycle, retrieval validation, and final phase verification.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-01-SUMMARY.md`.
- Task commits found in git history: `6e0af09`, `38ac0d9`, `e80c009`.
- Key created/modified files exist: `tests/memory/test_phase47_case_precedent_alignment.py`, `src/memory/schemas.py`, `src/memory/policy.py`, `tests/memory/test_memory_policy.py`, `docs/contract-spec.md`.
- Remaining dirty files are the three pre-existing user-owned files from the executor prompt and were not staged or committed.

---
*Phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener*
*Completed: 2026-07-03*
