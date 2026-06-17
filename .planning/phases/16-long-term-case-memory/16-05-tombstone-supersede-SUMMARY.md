---
phase: 16-long-term-case-memory
plan: 05
subsystem: memory
tags: [tombstone, no-rewrite, supersede, long-term-memory, tdd]

requires:
  - phase: 16-03-long-term-memory-service
    provides: LongTermMemoryService, LongTermMemoryRepository, memory_write_events, reviewed long-term retrieval predicates
  - phase: 16-04-semantic-episode
    provides: review-gated semantic_episode_candidate source type for downstream write paths
provides:
  - Transactional long-term memory tombstones for forget/delete paths
  - Exact tombstone no-rewrite matching by canonical content hash or allowed source identity
  - Correction/supersede write path that leaves one current replacement and evented supersede state
  - Delayed separate-session rewrite coverage for tombstone_match skip events
affects:
  - 16-06-reviewed-case-memory
  - 16-07-context-assembler-memory
  - 16-08-memory-retrieval-integration
  - 16-09-legacy-search-eval-closure

tech-stack:
  added: []
  patterns:
    - Same-session transaction checks active tombstones before inserting long-term memories
    - Tombstone matching is exact identity-only and avoids semantic/vector matching
    - Supersede updates previous row, inserts replacement, and emits memory_write_events in one session transaction

key-files:
  created:
    - src/memory/tombstones.py
    - tests/memory/test_memory_tombstones.py
  modified:
    - src/memory/long_term.py
    - src/memory/repository.py
    - tests/memory/test_long_term_memory_service.py

key-decisions:
  - "Tombstone no-rewrite checks run before long-term memory insert and emit decision=skip/reason_code=tombstone_match."
  - "Tombstone matching uses canonical content_hash first, then allowed source_identity_hash fallback, with no semantic similarity path."
  - "Forget/delete create active tombstone identities while keeping existing delete event semantics for delete_memory."
  - "Supersede marks the previous row superseded/non-current, inserts a current replacement, links supersedes/superseded_by, and emits decision=supersede."

patterns-established:
  - "LongTermMemoryRepository.create_tombstone(...) computes source_identity_hash from allowed MemorySourceRefV1 fields."
  - "LongTermMemoryService.write_memory(...) checks check_tombstone_before_write(...) before PII/review insert decisions."
  - "Delayed writer tests use a committed session A tombstone and separate async session B candidate write."

requirements-completed: [LONGMEM-03, TOMBSTONE-01, TOMBSTONE-02, MEMREVIEW-01, MEMEVAL-01]

duration: 14 min
completed: 2026-06-17
---

# Phase 16 Plan 05: Tombstones, No-rewrite, And Supersede Summary

**Exact tombstone no-rewrite protection with transactional forget/delete, supersede replacement chains, and memory write events**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-17T16:15:58Z
- **Completed:** 2026-06-17T16:29:35Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Added exact tombstone helpers and repository APIs for `create_tombstone(...)`, `active_tombstone_matches(...)`, `check_tombstone_before_write(...)`, and `forget_memory(...)`.
- Wired long-term writes to skip active tombstone matches before insert with `reason_code="tombstone_match"` and no semantic/vector similarity logic.
- Added forget/delete tombstone creation so retrieval excludes forgotten/deleted long-term memories immediately and delayed writers cannot resurrect source-matched content.
- Added supersede behavior that marks the previous row `review_status="superseded"`, links replacement rows, keeps exactly one current row, and emits `decision="supersede"`.
- Added same-transaction, source fallback, no-semantic-similarity, supersede, and separate-session delayed rewrite coverage.

## Task Commits

Each task was committed atomically:

1. **Task 16-05-01: Add tombstone and supersede tests** - `e904f46` (test, RED)
2. **Task 16-05-02: Implement tombstone matching** - `c685a44` (feat, GREEN)
3. **Task 16-05-03: Implement supersede transaction** - `defc493` (test, supersede service coverage)
4. **Task 16-05-04: Add delayed rewrite concurrency coverage** - `693cc1b` (test, separate-session coverage)

## Files Created/Modified

- `src/memory/tombstones.py` - Exact tombstone identity helper functions for allowed source identity hashing and active match checks.
- `src/memory/repository.py` - Tombstone create/match/check/forget repository methods plus replacement insert parameters for supersede chains.
- `src/memory/long_term.py` - Write-path tombstone checks, forget alias, delete tombstone creation, and supersede transaction behavior.
- `tests/memory/test_memory_tombstones.py` - TDD tombstone/no-rewrite/supersede and delayed separate-session coverage.
- `tests/memory/test_long_term_memory_service.py` - Service-level supersede chain and write-event coverage.

## Decisions Made

- Used exact matching only: canonical `content_hash` first, then allowed `source_identity_hash`; no embedding, fuzzy, or semantic matching participates in deletion/no-rewrite behavior.
- Kept `delete_memory(...)` event semantics as `decision="delete"` while also creating a tombstone identity through the shared forget repository path.
- Implemented supersede in `LongTermMemoryService` rather than adding a new service layer, matching the existing Phase 16 memory service boundary.

## TDD Gate Compliance

- **RED:** `uv run pytest tests/memory/test_memory_tombstones.py -q` failed before implementation with missing `forget_long_term_memory`, `create_tombstone`, and `supersede_memory` APIs.
- **GREEN:** `uv run pytest tests/memory/test_memory_tombstones.py -q` passed after adding tombstone/no-rewrite and supersede implementation.
- **REFACTOR:** No separate refactor commit was needed.

## Verification

- `uv run pytest tests/memory/test_memory_tombstones.py -q` - passed, 6 tests.
- `uv run pytest tests/memory/test_memory_tombstones.py tests/memory/test_long_term_memory_service.py -q` - passed, 12 tests.
- `uv run pytest tests/memory -q` - passed, 60 tests.
- `uv run ruff check src/memory/long_term.py src/memory/repository.py src/memory/tombstones.py tests/memory/test_memory_tombstones.py tests/memory/test_long_term_memory_service.py` - passed.
- Acceptance greps confirmed `tombstone_match`, `source_identity_hash`, `review_status = "superseded"`, `superseded_by`, exactly-one-current assertions, delayed/separate-session test naming, and no `.cosine_distance` in tombstone logic.

## Deviations from Plan

### Task Sequencing Adjustments

**1. Supersede runtime code landed in the GREEN implementation commit**
- **Found during:** Task 16-05-02 (Implement tombstone matching)
- **Issue:** Task 16-05-02 verification runs the full `tests/memory/test_memory_tombstones.py` file, while Task 16-05-01 intentionally placed supersede RED tests in that same file.
- **Adjustment:** Implemented `supersede_memory(...)` in the GREEN commit so the Task 16-05-02 verify command could pass, then committed additional supersede service coverage as Task 16-05-03.
- **Files modified:** `src/memory/long_term.py`, `src/memory/repository.py`, `tests/memory/test_long_term_memory_service.py`
- **Verification:** `uv run pytest tests/memory/test_memory_tombstones.py tests/memory/test_long_term_memory_service.py -q`
- **Committed in:** `c685a44` and `defc493`

**Total deviations:** 1 sequencing adjustment. No scope expansion beyond the plan objective.

## Known Stubs

None. Stub scan found only type annotations/defaults and test empty-result assertions (`[]`/`None`), not placeholder data, TODO/FIXME, or unwired runtime/UI data flow.

## Issues Encountered

- Initial RED run hit a test-file syntax error because a patch marker was accidentally included in the new test file. It was removed before the RED commit; the committed RED failure was the intended missing-API failure.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-06-reviewed-case-memory-PLAN.md`. Long-term memory now has exact tombstone/no-rewrite and supersede foundations that reviewed case memory can mirror for case tombstones and write-event observability.

## Self-Check: PASSED

- Verified key files exist: `src/memory/tombstones.py`, `tests/memory/test_memory_tombstones.py`, and this SUMMARY.
- Verified task commits exist in git history: `e904f46`, `c685a44`, `defc493`, and `693cc1b`.
- Verified TDD gate commits exist in order: RED `e904f46` before GREEN `c685a44`.
- Verified final commands passed: focused tombstone/long-term service pytest, full `tests/memory` pytest, and focused Ruff check.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-17*
