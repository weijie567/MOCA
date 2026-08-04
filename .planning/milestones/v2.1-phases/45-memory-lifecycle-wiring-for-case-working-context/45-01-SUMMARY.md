---
phase: 45-memory-lifecycle-wiring-for-case-working-context
plan: 01
subsystem: memory
tags: [case-working-context, memory, pydantic, lifecycle-adapter, tdd]
requires:
  - phase: 44-memory-layering-case-working-context-thread-case-many-to-man
    provides: Case Working Context resolver, repository, thread-case link surface, and audited write service
provides:
  - contextual-only CWC ref and lifecycle status DTOs
  - additive MemoryContextBundle fields for active CWC payload and status
  - graph/API-neutral CWC lifecycle adapter foundation
  - trusted case-ref extraction and active-row payload projection tests
affects: [memory, case-working-context, phase-45-plan-02, phase-45-plan-03]
tech-stack:
  added: []
  patterns:
    - TDD red/green commits for lifecycle contract surfaces
    - fail-closed trusted case-ref extraction from explicit run state only
    - prompt-safe CWC row projection through hydrate_content plus contextual refs
key-files:
  created:
    - src/memory/case_working_context_lifecycle.py
    - tests/agent/test_case_working_context_lifecycle.py
    - .planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-01-SUMMARY.md
  modified:
    - src/memory/context_refs.py
    - tests/memory/test_context_refs.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/codebase/STRUCTURE.md
key-decisions:
  - "CWC lifecycle status/ref contracts remain contextual-only and separate from evidence, business fact, approval, action, and replay authority DTOs."
  - "Trusted case-ref extraction accepts only active_slots, extracted_slots, and explicitly enabled terminal business_context fields; candidate slots and memory surfaces are ignored."
  - "Active CWC payload projection derives refs only from persisted CWC row fields and hydrates content through the Phase 44 repository helper."
patterns-established:
  - "CWC lifecycle adapter owns trusted state filtering before later graph/API/finalizer callers wire read/link/write behavior."
  - "CWC bundle exposure is additive; reviewed long-term and case memory items remain unchanged."
requirements-completed: [MEM-01, MEM-02]
duration: 5min
completed: 2026-07-03
---

# Phase 45 Plan 01: CWC Lifecycle Boundary Summary

**Contextual-only Case Working Context lifecycle contracts plus a graph/API-neutral adapter for trusted identity extraction and active-row projection.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-03T05:05:08Z
- **Completed:** 2026-07-03T05:09:55Z
- **Tasks:** 2/2
- **Files modified:** 8

## Accomplishments

- Added `CaseWorkingContextRef` and `CaseWorkingContextLifecycleStatusV1` with `authority_class="contextual_only"` and explicit lifecycle status fields.
- Extended `MemoryContextBundle` with optional active CWC payload/status fields without changing `long_term_items` or `case_items`.
- Added `CaseWorkingContextLifecycleAdapter` foundation with trusted case-ref extraction, Phase 44 resolver/repository seams, active CWC payload projection, and status constructors.
- Added focused TDD coverage for red-line sources: no candidate slots, session memory, reviewed case memory, or memory context can select a CWC case.

## Task Commits

1. **Task 1 RED: CWC lifecycle ref/status tests** - `9fa41d2` (`test`)
2. **Task 1 GREEN: Contextual CWC refs and bundle fields** - `b5794a8` (`feat`)
3. **Task 2 RED: CWC lifecycle adapter tests** - `571b5f3` (`test`)
4. **Task 2 GREEN: Adapter foundation** - `7e5c757` (`feat`)

## Files Created/Modified

- `src/memory/context_refs.py` - Adds CWC contextual ref/status models and optional bundle fields.
- `src/memory/case_working_context_lifecycle.py` - Adds lifecycle adapter foundation, trusted case-ref extraction, active payload projection, and status helpers.
- `tests/memory/test_context_refs.py` - Adds CWC ref/status/bundle contract tests and authority import guard coverage.
- `tests/agent/test_case_working_context_lifecycle.py` - Adds adapter contract tests for trusted identity extraction, active payload projection, and skipped status.
- `.planning/ARCHITECTURE-DEBT.md` - Adds the required memory subsystem ledger entry for the Phase 45 Plan 01 lifecycle boundary fix.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records the handled `gsd-sdk state.*` flag/positional argument mismatch encountered during metadata updates.
- `.planning/codebase/STRUCTURE.md` - Refreshes the memory module description to include CWC lifecycle adapter ownership.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py -x -q`
  - RED before implementation: failed with missing `CaseWorkingContextLifecycleStatusV1`.
  - GREEN after implementation: `18 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py -x -q`
  - RED before implementation: failed with missing `src.memory.case_working_context_lifecycle`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/memory/test_context_refs.py -x -q` -> `24 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py -q` -> `24 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/context_refs.py src/memory/case_working_context_lifecycle.py tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py` -> `All checks passed!`
- `grep -n "class CaseWorkingContextLifecycleStatusV1" src/memory/context_refs.py` -> matched.
- `grep -n "case_working_context_status_ref" src/memory/context_refs.py` -> matched.
- `grep -n "class CaseWorkingContextLifecycleAdapter" src/memory/case_working_context_lifecycle.py` -> matched.
- `grep -n "candidate_slots" tests/agent/test_case_working_context_lifecycle.py` -> matched negative test.
- `grep -n "resolve_case_id" src/memory/case_working_context_lifecycle.py` -> matched imported Phase 44 resolver seam.

## Decisions Made

- Kept lifecycle status fields string-based and optional where future skip/error paths may not have a resolved case or read/write result yet.
- Exposed active CWC through additive bundle fields instead of merging it into reviewed `case_items`.
- Kept this plan out of graph topology, finalizer writeback, migrations, and ReAct behavior changes.

## Deviations from Plan

### Project-Rule Documentation

**1. [CLAUDE.md / AGENTS.md - Memory Architecture Debt Ledger] Added Phase 45 Plan 01 memory entry**
- **Found during:** Summary preparation after memory subsystem changes.
- **Issue:** Project rules require appending verified memory subsystem fixes to `.planning/ARCHITECTURE-DEBT.md`.
- **Fix:** Added a Chinese Phase 45 Plan 01 entry with issue/root cause, fix, evidence, verification, and remaining 45-02/45-03/45-04 risks.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Diff reviewed; entry only claims adapter foundation completion and explicitly defers read/link/write call-site wiring.

**Total deviations:** 1 project-rule documentation update.
**Impact on plan:** No code scope expansion; the extra change records required subsystem debt status.

## Issues Encountered

- Expected TDD RED failures occurred before each GREEN implementation.
- During metadata updates, `gsd-sdk state.record-metric` / `state.record-session` accepted flag-style arguments but wrote flag names into `STATE.md`. This was repaired manually, and a Chinese incident entry was added to `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. Stub scan found only typed optional/default fields and test assertions for empty/default values; no placeholder data source or UI stub was introduced.

## Threat Flags

None beyond the plan threat model. The new trust boundary is the planned lifecycle adapter, and tests cover the required fail-closed sources.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 45-02. Later plans can call the adapter for active CWC read and `run_auto` thread-case linking, then terminal writeback, without embedding trust filtering directly into graph or finalizer code.

## TDD Gate Compliance

- RED commits present: `9fa41d2`, `571b5f3`.
- GREEN commits present after RED: `b5794a8`, `7e5c757`.
- No refactor commit was needed.

## Self-Check: PASSED

- Created files found: `src/memory/case_working_context_lifecycle.py`, `tests/agent/test_case_working_context_lifecycle.py`, and this summary.
- Task commits found in git history: `9fa41d2`, `b5794a8`, `571b5f3`, `7e5c757`.
- Current dirty user-owned files remain outside this plan's staged code commits.

---
*Phase: 45-memory-lifecycle-wiring-for-case-working-context*
*Completed: 2026-07-03*
