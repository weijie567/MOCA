---
phase: 48-narrow-long-term-explicit-preference-memory
plan: 02
subsystem: memory
tags: [long-term-memory, preferences, source-policy, semantic-episode, audit]

requires:
  - phase: 48-narrow-long-term-explicit-preference-memory
    provides: 48-01 explicit preference-only contract/static locks
provides:
  - published long-term source allowlist in memory policy
  - pre-insert service skips for non-preference and disallowed long-term candidates
  - semantic episode projection limited to needs-review preference candidates
affects: [phase-48, memory, long-term-memory, semantic-episode, memory-write-events]

tech-stack:
  added: []
  patterns:
    - policy decision skip before repository insertion
    - semantic observations can produce review candidates, not prompt-usable long-term rows

key-files:
  created: []
  modified:
    - src/memory/policy.py
    - src/memory/schemas.py
    - src/memory/long_term.py
    - src/memory/semantic_episode.py
    - tests/memory/test_memory_policy.py
    - tests/memory/test_long_term_memory_service.py
    - tests/memory/test_semantic_episode_projection.py
    - tests/memory/test_phase48_long_term_preference_alignment.py
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Only explicit_user_preference, explicit_admin_preference, and human_reviewed can auto-publish long-term memory."
  - "semantic_episode_candidate remains needs_review and must write preference candidates only."
  - "deterministic tool results, business outcomes, approval state, LLM/summary/pattern/behavior inference sources skip before insertion."

patterns-established:
  - "LongTermMemoryService returns skipped results and emits MemoryWriteEvent for source policy rejects before insert."
  - "Semantic episode long-term projection iterates only preference_candidate keys."

requirements-completed: [MEM-05]

duration: 11min
completed: 2026-07-04
---

# Phase 48 Plan 02 Summary

**Preference-only long-term write policy with semantic episodes restricted to reviewable preference candidates**

## Performance

- **Duration:** about 11 min
- **Started:** 2026-07-04T08:06:09+08:00
- **Completed:** 2026-07-04T08:16:59+08:00
- **Tasks:** 2
- **Files modified:** 9 files, plus architecture debt ledger

## Accomplishments

- Replaced broad durable long-term auto-publish sources with `PUBLISHED_LONG_TERM_SOURCE_TYPES = {"explicit_user_preference", "explicit_admin_preference", "human_reviewed"}`.
- Changed `LongTermMemoryWriteCandidate.memory_kind` default to `preference` and added pre-insert skip branches for non-preference memory kind and disallowed source types.
- Narrowed semantic episode projection so only `preference_candidate` produces `semantic_episode_candidate` needs-review long-term candidates.

## Task Commits

1. **Task 1: Narrow long-term source policy and service insertion guards** - `495c483` (feat/test)
2. **Task 2: Narrow semantic episodes to needs-review preference candidates only** - `9e842e4` (feat/test)

## Files Created/Modified

- `src/memory/policy.py` - Published source allowlist, semantic review source, and disallowed long-term source skip decision.
- `src/memory/schemas.py` - Long-term write candidate default memory kind changed to `preference`.
- `src/memory/long_term.py` - Pre-insert skip result/event helper for non-preference and policy-skip candidates.
- `src/memory/semantic_episode.py` - Preference-candidate-only projection and fixed preference memory kind.
- `tests/memory/test_memory_policy.py` - Phase 48 source policy and default-kind coverage.
- `tests/memory/test_long_term_memory_service.py` - Pre-insert skip and reviewable semantic candidate coverage.
- `tests/memory/test_semantic_episode_projection.py` - Candidate-only semantic projection coverage.
- `tests/memory/test_phase48_long_term_preference_alignment.py` - Static guard for semantic episode projection source.
- `.planning/ARCHITECTURE-DEBT.md` - Memory subsystem debt fix recorded.

## Decisions Made

`semantic_episode_candidate` is the only automatic long-term source that can still create a row, and that row is pending review. Published prompt-usable long-term memory is still limited to explicit user/admin preference or human-reviewed preference.

## Deviations from Plan

The service guard was applied to both `write_memory(...)` and `supersede_memory(...)`. The plan explicitly called out `write_memory(...)`, but supersede also inserts long-term rows, so leaving it unguarded would preserve the same non-preference/source-policy bypass in the correction path.

## Issues Encountered

None. Focused tests and ruff passed with the existing LangGraph/LangChain deprecation warning.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py -x -q` -> 33 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py -x -q` -> 10 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py -q` -> 43 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/policy.py src/memory/schemas.py src/memory/long_term.py src/memory/semantic_episode.py tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py` -> pass.

## User Setup Required

None.

## Next Phase Readiness

48-03 can add explicit chat/admin preference write entries on top of a service layer that now rejects non-preference and disallowed long-term writes before insertion. Retrieval and review publish semantics remain for 48-04.

---
*Phase: 48-narrow-long-term-explicit-preference-memory*
*Completed: 2026-07-04*
