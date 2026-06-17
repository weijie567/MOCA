---
phase: 16-long-term-case-memory
plan: 03
subsystem: memory
tags: [long-term-memory, review-policy, retrieval-predicates, write-events, tdd]

requires:
  - phase: 16-01-memory-identity
    provides: memory_identity.v1 content/source/candidate hash helpers
  - phase: 16-02-schema-migration
    provides: long_term_memories, memory_tombstones, and memory_write_events tables
provides:
  - Reviewed long-term profile memory service boundary
  - Deterministic source policy for auto-approved versus needs-review memory writes
  - Strict tenant/scope/current/freshness/tombstone retrieval predicates
  - Observable write, skip, review, and delete events with canonical candidate hashes
affects:
  - 16-05-tombstone-supersede
  - 16-07-context-assembler-memory
  - 16-08-memory-retrieval-integration
  - 16-09-legacy-search-eval-closure

tech-stack:
  added: []
  patterns:
    - Service-level source review policy around dedicated memory repository methods
    - Retrieval methods return bounded Pydantic prompt-safe views instead of ORM rows
    - memory_write_events reuse memory_identity.v1 candidate hashes

key-files:
  created:
    - src/memory/long_term.py
    - tests/memory/test_long_term_memory_service.py
    - tests/memory/test_long_term_memory_repository.py
  modified:
    - src/memory/repository.py
    - src/memory/schemas.py

key-decisions:
  - "LLM, semantic, summary, cross-case pattern, and behavior inference candidates are persisted only as needs_review and are excluded from retrieval."
  - "Explicit, admin, human-reviewed, deterministic tool, confirmed outcome, and approved approval-state sources may auto-approve when PII is not prohibited."
  - "Approve/reject review paths use the existing memory_write_events decision enum: decision=write/reason_code=approved and decision=skip/reason_code=rejected."
  - "Long-term retrieval returns bounded LongTermMemoryView values and excludes tombstoned rows by content hash or source identity."

patterns-established:
  - "Long-term memory service computes content/source/candidate hashes through src.memory.identity helpers before persistence or event emission."
  - "Retrieval predicates combine review_status.in_(auto_approved, approved), deleted_at, is_current, expires_at, PII, tenant/scope, and active tombstone filters."

requirements-completed: [LONGMEM-01, LONGMEM-02, MEMREVIEW-01, MEMEVAL-01]

duration: 10 min
completed: 2026-06-17
---

# Phase 16 Plan 03: Long-term Profile Memory Service Summary

**Reviewed long-term profile memory service with deterministic source policy, canonical write events, and strict prompt-safe retrieval predicates**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-17T15:47:36Z
- **Completed:** 2026-06-17T15:57:36Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Added `LongTermMemoryService` and `LongTermMemoryRepository` for reviewed long-term profile memory writes, review paths, deletion, event emission, and retrieval.
- Added Pydantic schemas for long-term write candidates, write results, and bounded prompt-safe memory views.
- Added tests covering explicit/deterministic auto-approval, LLM needs-review behavior, prohibited PII skip behavior, write events, review/delete events, tombstone filtering, and unpublished-state retrieval exclusion.

## Task Commits

Each task was committed atomically:

1. **Task 16-03-01: Add long-term memory service tests** - `c74d3f2` (test, RED)
2. **Task 16-03-02: Implement long-term memory service boundary** - `0367403` (feat, GREEN)
3. **Task 16-03-03: Implement long-term retrieval predicates** - `903b786` (test)
4. **Task 16-03-04: Emit long-term memory write events** - `a41ac00` (feat)

## Files Created/Modified

- `src/memory/long_term.py` - Long-term memory source policy, write path, approve/reject/delete event paths, and candidate-hash handling.
- `src/memory/repository.py` - Long-term repository persistence, review/delete state updates, event emission, and strict retrieval predicates.
- `src/memory/schemas.py` - Long-term write candidate/result/view schemas.
- `tests/memory/test_long_term_memory_service.py` - Service tests for review policy, PII skip, events, and review/delete paths.
- `tests/memory/test_long_term_memory_repository.py` - Repository tests for retrieval exclusion predicates, tombstones, tenant/scope isolation, and bounded views.

## Decisions Made

- Persisted unreviewed model/summary/semantic candidates as `needs_review` so they can be audited without becoming retrievable prompt memory.
- Kept successful auto-approved writes as `decision="write"` events and prohibited PII skips as `decision="skip", reason_code="pii_blocked"`.
- Represented approve/reject review events with existing schema-safe decisions plus reason codes instead of changing the Phase 16 schema in this plan.
- Returned bounded `LongTermMemoryView` values from retrieval to avoid exposing raw ORM rows to prompt assembly callers.

## TDD Gate Compliance

- **RED:** `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q` failed before implementation with missing `src.memory.long_term` and missing `LongTermMemoryRepository`.
- **GREEN:** The same command passed after service, repository, and schema implementation.
- **REFACTOR:** No separate refactor commit was needed; Task 16-03-03 and Task 16-03-04 added predicate/event coverage and implementation.

## Verification

- `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q` - passed, 7 tests.
- `uv run pytest tests/memory/test_memory_identity.py tests/memory/test_memory_schema.py -q` - passed, 13 tests.
- `uv run ruff check src/memory tests/memory` - passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Mapped approve/reject event paths onto existing event enum**
- **Found during:** Task 16-03-04 (Emit long-term memory write events)
- **Issue:** The Phase 16 schema from Plan 16-02 constrains `memory_write_events.decision` to `write`, `skip`, `needs_review`, `delete`, `supersede`, `tombstone`, or `write_blocked`; direct `approve` / `reject` decision literals would violate the DB contract.
- **Fix:** Implemented approve as `decision="write", reason_code="approved"` and reject as `decision="skip", reason_code="rejected"`, preserving observable review events without modifying the schema.
- **Files modified:** `src/memory/long_term.py`, `src/memory/repository.py`, `tests/memory/test_long_term_memory_service.py`
- **Verification:** `uv run pytest tests/memory/test_long_term_memory_service.py -q` and final plan verification passed.
- **Committed in:** `a41ac00`

---

**Total deviations:** 1 auto-fixed (1 blocking schema-contract alignment)
**Impact on plan:** No scope expansion. The service remains compatible with the existing Phase 16 schema while preserving auditability for review paths.

## Known Stubs

None. Stub scan found only optional typed `None` defaults and test empty-list assertions, not runtime placeholder data.

## Threat Flags

None. New write/review/retrieval surfaces are the planned Phase 16 long-term memory service surface and are covered by the plan threat model.

## Issues Encountered

None beyond the expected TDD RED failure and the documented schema-contract alignment.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-04-semantic-episode-PLAN.md`. Long-term profile memory now has reviewed write semantics, prompt-safe retrieval views, and observable events; correction/supersede and stronger tombstone no-rewrite behavior remain owned by later Phase 16 plans.

## Self-Check: PASSED

- Verified key files exist: `src/memory/long_term.py`, `src/memory/repository.py`, `src/memory/schemas.py`, `tests/memory/test_long_term_memory_service.py`, `tests/memory/test_long_term_memory_repository.py`, and this SUMMARY.
- Verified task commits exist in git history: `c74d3f2`, `0367403`, `903b786`, and `a41ac00`.
- Verified final commands passed: focused service/repository pytest, identity/schema pytest, and `ruff check src/memory tests/memory`.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-17*
