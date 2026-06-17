---
phase: 16-long-term-case-memory
plan: 02
subsystem: database
tags: [sqlalchemy, alembic, pgvector, memory, tombstones]

requires:
  - phase: 16-01-memory-identity
    provides: memory_identity.v1 content/source/candidate hash contracts consumed by schema identity columns
provides:
  - Durable SQLAlchemy models for long-term memory, case memory, tombstones, and memory write events
  - Alembic migration 013 creating reviewed memory tables, constraints, indexes, pgvector case embedding, and downgrade
  - Schema contract tests covering table presence, identity columns, lifecycle checks, tombstone indexes, and migration preflight objects
affects:
  - 16-03-long-term-memory-service
  - 16-05-tombstone-supersede
  - 16-06-reviewed-case-memory
  - 16-08-memory-retrieval-integration

tech-stack:
  added: []
  patterns:
    - SQLAlchemy ORM models paired with static Alembic schema contract tests
    - PostgreSQL/pgvector Vector(1024) case memory embedding on the existing database stack
    - Tenant/scope/memory-type tombstone identity indexes for content and source identity matching

key-files:
  created:
    - src/db/migrations/versions/013_long_term_case_memory.py
    - tests/memory/test_memory_schema.py
  modified:
    - src/db/models.py

key-decisions:
  - "Use separate durable Phase 16 tables instead of overloading session_memories."
  - "Use PostgreSQL/pgvector Vector(1024) plus HNSW index for reviewed case memory embeddings."
  - "Index active tombstones by tenant, memory type, scope, content hash, and source identity to support exact no-rewrite checks."

patterns-established:
  - "Reviewed memory schema: lifecycle fields live on dedicated long-term/case/tombstone/write-event tables."
  - "Migration readiness tests: static schema checks cover downgrade order, index names, constraints, and no session_memories mutation."

requirements-completed: [MEMSCHEMA-01, TOMBSTONE-01, MEMREVIEW-01, MEMEVAL-01]

duration: 10 min
completed: 2026-06-17
---

# Phase 16 Plan 02: Reviewed Memory Schema And Migration Summary

**Reviewed long-term/case memory storage with SQLAlchemy models, Alembic 013 migration, pgvector case embeddings, tombstone identity indexes, and schema readiness tests**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-17T15:30:39Z
- **Completed:** 2026-06-17T15:40:42Z
- **Tasks:** 4
- **Files modified:** 3

## Accomplishments

- Added four durable Phase 16 memory tables in ORM and migration: `long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events`.
- Added review, PII, scope, memory type, confidence, and write-decision constraints without mutating `session_memories`.
- Added tenant/scope-aware retrieval, content identity, source identity, tombstone, write-event, and case metadata indexes, plus a pgvector HNSW index for case embeddings.
- Added schema tests proving table presence, case `content_hash` / `source_identity_hash`, lifecycle constraints, tombstone active identity index, preflight objects, and downgrade drop order.

## Task Commits

Each task was committed atomically:

1. **Task 16-02-01: Add memory schema contract tests** - `a1a7c46` (test)
2. **Task 16-02-02: Add Phase 16 ORM models** - `2c37acd` (feat)
3. **Task 16-02-03: Add Alembic memory migration** - `90b15c5` (feat)
4. **Task 16-02-04: Run blocking migration readiness gate** - `fde0947` (test)

**Plan metadata:** `e797200` docs commit.

## Files Created/Modified

- `src/db/models.py` - Adds `LongTermMemory`, `CaseMemory`, `MemoryTombstone`, and `MemoryWriteEvent` models with constraints and indexes.
- `src/db/migrations/versions/013_long_term_case_memory.py` - Creates/drops Phase 16 memory tables and indexes after `012_thread_user_scope`.
- `tests/memory/test_memory_schema.py` - Adds schema contract and migration readiness tests.

## Decisions Made

- Used dedicated memory tables and did not alter `session_memories`.
- Kept long-term memory predicate-based and added `Vector(1024)` only to reviewed case memory.
- Added both content-hash and source-identity indexes so tombstone checks can match canonical content or stable source identity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Resolved Task 2/3 verification coupling**
- **Found during:** Task 16-02-02 (Add Phase 16 ORM models)
- **Issue:** The task-level verify command `uv run pytest tests/memory/test_memory_schema.py -q` necessarily read both ORM and migration assertions, so it could not pass after ORM-only changes while migration 013 was still absent.
- **Fix:** Continued directly into Task 16-02-03, created the migration, then reran the same schema tests until they passed before committing the model and migration work separately.
- **Files modified:** `src/db/models.py`, `src/db/migrations/versions/013_long_term_case_memory.py`
- **Verification:** `uv run pytest tests/memory/test_memory_schema.py -q` passed after migration creation.
- **Committed in:** `2c37acd`, `90b15c5`

---

**Total deviations:** 1 auto-fixed (1 blocking issue)
**Impact on plan:** No scope expansion. The adjustment only resolved an internal verification-order coupling while preserving separate task commits.

## Issues Encountered

- `make migrate` succeeded locally and applied `012_thread_user_scope -> 013_long_term_case_memory`; no unavailable-DB fallback was needed.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - no functional stubs found in files created or modified by this plan.

## Verification

- `uv run pytest tests/memory/test_memory_schema.py -q` - passed (`6 passed`, one existing LangGraph deprecation warning).
- `make migrate` - passed; Alembic reported PostgreSQL transactional DDL and applied/no-oped head migration.
- `uv run ruff check src/db/models.py src/db/migrations/versions/013_long_term_case_memory.py tests/memory/test_memory_schema.py` - passed.

## Next Phase Readiness

Ready for `16-03-long-term-memory-service`. The schema now exposes durable reviewed memory storage, but retrieval predicates, tombstone transactions, supersede behavior, and service-level tenant/scope validation still belong to later Phase 16 plans.

## Self-Check: PASSED

- Created/modified files verified on disk.
- Task commits verified in git log: `a1a7c46`, `2c37acd`, `90b15c5`, `fde0947`.
- Verification commands passed: schema pytest, `make migrate`, and focused ruff check.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-17*
