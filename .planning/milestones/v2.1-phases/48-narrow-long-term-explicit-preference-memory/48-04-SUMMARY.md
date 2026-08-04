---
phase: 48-narrow-long-term-explicit-preference-memory
plan: 04
subsystem: memory
tags: [long-term-memory, retrieval, review, supersede, tombstone, validation]

requires:
  - phase: 48-narrow-long-term-explicit-preference-memory
    provides: 48-03 explicit user/admin preference write paths
provides:
  - published preference-only long-term retrieval predicate
  - human-reviewed source conversion for reviewed preference candidates
  - non-preference approval rejection at service/API layers
  - explicit supersede/tombstone/no-auto-merge lifecycle regressions
  - full Phase 48 validation gate
affects: [phase-48, memory-retrieval, memory-review, memory-api, architecture-tests]

tech-stack:
  added: []
  patterns:
    - repository-owned prompt-facing retrieval filters
    - review approval converts candidate source to human_reviewed after validation
    - correction lifecycle remains explicit supersede/tombstone only

key-files:
  modified:
    - src/memory/repository.py
    - src/memory/long_term.py
    - tests/memory/test_long_term_memory_repository.py
    - tests/memory/test_reviewed_memory_context_boundary.py
    - tests/memory/test_phase48_long_term_preference_alignment.py
    - tests/memory/test_long_term_memory_service.py
    - tests/test_memory_review_api.py
    - tests/architecture/test_memory_contract_delta.py
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Prompt-facing long-term retrieval is repository-filtered to preference rows from explicit_user_preference, explicit_admin_preference, or human_reviewed."
  - "Approving semantic_episode_candidate preferences publishes them as human_reviewed and updates source identity hash consistently."
  - "Non-preference long-term approval is a controlled service/API error, not a 500."
  - "Similar same-scope preferences are not auto-merged; only explicit supersede changes currentness."

patterns-established:
  - "MemoryContextService relies on repository-filtered long-term preference rows instead of duplicating filters."
  - "Review approval source conversion happens only after validation passes."

requirements-completed: [MEM-05]

duration: 19min
completed: 2026-07-04
---

# Phase 48 Plan 04 Summary

**Prompt-facing long-term memory retrieval, review publishing, lifecycle, and final validation**

## Performance

- **Duration:** about 19 min
- **Started:** 2026-07-04T08:28:33+08:00
- **Completed:** 2026-07-04T08:47:39+08:00
- **Tasks:** 3
- **Files modified:** 8 source/test files, plus planning records

## Accomplishments

- Added repository retrieval predicates so `retrieve_profile_memory(...)` returns only current, prompt-safe, non-tombstoned `memory_kind="preference"` rows from `PUBLISHED_LONG_TERM_SOURCE_TYPES`.
- Converted approved review-required long-term preference candidates to `source_type="human_reviewed"` and updated `source_ref_json` / `source_identity_hash` consistently.
- Added service/API rejection for non-preference long-term approval, with API returning a controlled conflict response and leaving the row unpublished.
- Locked explicit correction/deletion semantics: `supersede_memory(...)` controls replacement, tombstones block rewrites, and similar preferences do not auto-merge.
- Ran the full Phase 48 gate and focused ruff clean.

## Task Commits

1. **Task 1: Filter prompt retrieval to published preference rows only** - `32b358e`
2. **Task 2: Publish reviewed candidates as human_reviewed and validate lifecycle** - `b0b32cd`
3. **Task 3: Align static contract guard with Phase 48 source policy** - `bf48778`

## Files Created/Modified

- `src/memory/repository.py` - Published preference-only retrieval predicate and source/kind filters.
- `src/memory/long_term.py` - Approval path rejects non-preference rows and publishes reviewed preferences as `human_reviewed`.
- `tests/memory/test_long_term_memory_repository.py` - Retrieval source/kind allow/deny coverage.
- `tests/memory/test_reviewed_memory_context_boundary.py` - Reviewed context exclusion coverage for disallowed long-term rows.
- `tests/memory/test_long_term_memory_service.py` - Approval, supersede, tombstone, no-auto-merge lifecycle coverage.
- `tests/test_memory_review_api.py` - Controlled API error regression for non-preference approval.
- `tests/memory/test_phase48_long_term_preference_alignment.py` / `tests/architecture/test_memory_contract_delta.py` - Static final invariant guards.

## Decisions Made

Repository filtering is the prompt-facing source of truth for long-term retrieval; context service stays thin and does not duplicate the same preference/source predicates. Reviewed automatic preference candidates lose the automatic source type when published, so `semantic_episode_candidate` never appears as a published prompt source.

## Deviations from Plan

None. Two existing tests/guards still reflected pre-Phase-48 assumptions (`llm_candidate` long-term needs-review and old `requires_review` test names); both were corrected to the accepted Phase 48 source policy and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_repository.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_long_term_preference_alignment.py -x -q` -> 32 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_service.py tests/test_memory_review_api.py tests/agent/test_memory_evidence_boundary.py -x -q` -> 44 passed, 3 warnings.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_memory_contract_delta.py::test_memory_contract_boundary_tests_are_present tests/memory/test_phase48_long_term_preference_alignment.py -q` -> 7 passed, 1 warning.
- Full Phase 48 gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py tests/architecture/test_memory_contract_delta.py tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py tests/memory/test_memory_write_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_memory_write_node.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/test_memory_review_api.py -q` -> 135 passed, 3 warnings.
- Focused ruff check for Phase 48 source/tests -> pass.

## User Setup Required

None.

## Phase Readiness

Phase 48 is complete. MEM-05 is implemented and verified: published long-term memory is explicit preference-only, semantic episode output is candidate-only, tenant-scoped preference writes are admin-only, and reviewed memory remains contextual-only.

---
*Phase: 48-narrow-long-term-explicit-preference-memory*
*Completed: 2026-07-04*
