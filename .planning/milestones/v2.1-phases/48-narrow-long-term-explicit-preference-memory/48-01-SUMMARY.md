---
phase: 48-narrow-long-term-explicit-preference-memory
plan: 01
subsystem: memory
tags: [long-term-memory, preferences, contract-spec, static-tests, gsd]

requires:
  - phase: 47-case-precedent-repositioning-and-closed-case-candidate-generation
    provides: reviewed case precedent layering and DEFER-3 handoff for long-term preference memory
provides:
  - explicit preference-only target contract for published long-term memory
  - Phase 48 static guards for storage identity and approved pytest entrypoints
  - architecture delta tests updated away from broad durable long-term semantics
affects: [phase-48, memory, contract-spec, long-term-memory]

tech-stack:
  added: []
  patterns:
    - static docs/architecture tests for phase contract locks
    - legacy storage identity preserved while service semantics narrow

key-files:
  created:
    - tests/memory/test_phase48_long_term_preference_alignment.py
  modified:
    - docs/contract-spec.md
    - docs/architecture-overview.md
    - docs/memory-contract-delta.md
    - .planning/MEMORY-REDESIGN-DECISIONS.md
    - tests/architecture/test_memory_contract_delta.py

key-decisions:
  - "Published long-term memory is explicit preference memory only."
  - "Published source types are limited to explicit_user_preference, explicit_admin_preference, and human_reviewed."
  - "memory_type='long_term_fact' remains a legacy storage/table identity label only."

patterns-established:
  - "Phase static guards scan planning artifacts for destructive storage instructions while preserving table identity."
  - "Phase artifacts must use UV_CACHE_DIR=/tmp/uv-cache uv run pytest for runnable pytest commands."

requirements-completed: [MEM-05]

duration: 20min
completed: 2026-07-04
---

# Phase 48 Plan 01 Summary

**Explicit preference-only long-term memory contract with static locks for storage identity and MOCA pytest entrypoints**

## Performance

- **Duration:** about 20 min
- **Started:** 2026-07-04T07:45:00+08:00
- **Completed:** 2026-07-04T08:06:09+08:00
- **Tasks:** 2
- **Files modified:** 6 implementation/test/doc files, plus execution metadata

## Accomplishments

- Rewrote `docs/contract-spec.md` §13.3/§13.5 so published long-term memory is explicit preference-only and excludes business state, policy authority, action authority, run summaries, strategy hints, and broad semantic patterns.
- Reconciled `docs/architecture-overview.md`, `docs/memory-contract-delta.md`, and `.planning/MEMORY-REDESIGN-DECISIONS.md` with Phase 48 source-type and semantic-episode decisions.
- Added `tests/memory/test_phase48_long_term_preference_alignment.py` to lock contract language, protected memory table identity, destructive-plan detection, and approved pytest command usage.

## Task Commits

1. **Task 1: Rewrite normative long-term memory contract** - `034319b` (docs/test)
2. **Task 2: Add Phase 48 static alignment and entrypoint guards** - `0d5051d` (test)

## Files Created/Modified

- `docs/contract-spec.md` - Normative long-term memory contract narrowed to explicit preference-only semantics.
- `docs/architecture-overview.md` - Memory retrieval row updated to reviewed explicit preference retrieval.
- `docs/memory-contract-delta.md` - Architecture delta target updated away from broad durable facts/patterns.
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - Added Phase 48 planning trace.
- `tests/architecture/test_memory_contract_delta.py` - Contract delta assertions updated to the new preference-only target.
- `tests/memory/test_phase48_long_term_preference_alignment.py` - New Phase 48 static guard suite.

## Decisions Made

Long-term storage names remain unchanged for compatibility. The semantic target moved to explicit preferences only, with `memory_type='long_term_fact'` documented as a legacy storage/table identity label rather than permission to publish facts, patterns, constraints, tool results, or run summaries.

## Deviations from Plan

Task 1 also updated `tests/architecture/test_memory_contract_delta.py`. The plan listed that file under the overall modified-file set and Task 2, but the docs rewrite needed the architecture delta assertions updated immediately so the old durable fact/pattern target would not remain test-locked after the contract edit.

## Issues Encountered

- GSD `state.begin-phase` named arguments were parsed positionally and briefly miswrote `.planning/STATE.md`; the state file was manually repaired and the issue was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- The first version of the storage identity static guard flagged its own unsafe-pattern explanation in `48-01-PLAN.md`; `_planning_prose_lines` now skips that meta text and the focused test suite passes.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_memory_contract_delta.py -x -q` -> 7 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py tests/architecture/test_memory_contract_delta.py -x -q` -> 11 passed, 1 warning.

## User Setup Required

None.

## Next Phase Readiness

48-02 can now implement source policy and semantic episode narrowing against a locked preference-only contract. The protected storage identities are covered by static tests, and runnable Phase 48 pytest commands are guarded against the invalid bare pytest entrypoint.

---
*Phase: 48-narrow-long-term-explicit-preference-memory*
*Completed: 2026-07-04*
