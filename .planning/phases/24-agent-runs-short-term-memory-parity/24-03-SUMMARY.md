---
phase: 24-agent-runs-short-term-memory-parity
plan: 03
subsystem: database
tags: [postgresql, alembic, sqlalchemy, idempotency, conversation-memory]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: Wave 0 RED validation plan definitions for run-role message and rolling-summary idempotency
provides:
  - DB-backed active run-role conversation message uniqueness for user and assistant rows
  - DB-backed active thread rolling summary uniqueness by source end message
  - Alembic duplicate preflight checks before unique index creation
affects: [agent-runs, conversation-memory, rolling-summary, sse-idempotency]

tech-stack:
  added: []
  patterns: [partial unique indexes, alembic duplicate preflight]

key-files:
  created:
    - src/db/migrations/versions/016_agent_run_memory_idempotency.py
  modified:
    - src/db/models.py

key-decisions:
  - "Use partial unique indexes instead of service-only checks for retry/process idempotency."
  - "Limit run-role uniqueness to active user/assistant messages so tool messages remain unconstrained by this Phase 24 contract."

patterns-established:
  - "Migration preflight raises RuntimeError with the target index name and duplicate key details before unique index creation."
  - "ORM Index names mirror Alembic index names exactly for future schema-drift checks."

requirements-completed:
  - STM-01
  - STM-03
  - STM-04
  - STM-10
  - STM-11

duration: 12 min
completed: 2026-06-20
---

# Phase 24 Plan 03: DB Idempotency Primitives Summary

**PostgreSQL partial unique indexes for exactly-once agent-run user/assistant messages and rolling thread summaries**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-20T13:49:00Z
- **Completed:** 2026-06-20T14:00:56Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `uq_conversation_messages_active_tenant_run_role` to enforce one active user message and one active assistant message per tenant/run/role.
- Added `uq_summaries_thread_rolling_source_end` to enforce one active `thread_rolling` summary per tenant/thread/source-end message.
- Added Alembic preflight checks that block migration if active duplicates already exist and report duplicate key fields plus `duplicate_count`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ORM and Alembic idempotency indexes** - `eb2f731` (feat)
2. **Task 2: [BLOCKING] Verify Alembic upgrade before dependent behavior** - `eb2f731` (verification gate, no code delta)

## Files Created/Modified

- `src/db/migrations/versions/016_agent_run_memory_idempotency.py` - Alembic revision with duplicate preflight checks, partial unique index creation, and exact-name downgrade drops.
- `src/db/models.py` - SQLAlchemy `Index(...)` declarations mirroring the migration names and predicates.

## Decisions Made

- Used PostgreSQL partial unique indexes for process/retry safety because Phase 24 idempotency cannot rely on in-process checks alone.
- Kept the message unique index scoped to active `user` and `assistant` rows with non-null `run_id`; tool rows are handled by existing tool-call/result semantics.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** Schema primitives are ready for service/API idempotency work.

## Issues Encountered

- Execution order deviation: this schema-only plan was executed before Plans 24-01 and 24-02 because the current working tree already had dirty changes overlapping those RED-test files. The dependent RED tests still need to be completed before treating Wave 1 as done.
- GSD `state.begin-phase` CLI argument mismatch was found during phase initialization and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## User Setup Required

None - no external service configuration required.

## Verification

- `rg -n "uq_conversation_messages_active_tenant_run_role|uq_summaries_thread_rolling_source_end" src/db/models.py src/db/migrations/versions/016_agent_run_memory_idempotency.py` - passed.
- `rg -n "revision: str = \"016_agent_run_memory_idempotency\"|down_revision: str \\| None = \"015_rag_production_ingestion_ocr\"" src/db/migrations/versions/016_agent_run_memory_idempotency.py` - passed.
- `uv run ruff check src/db/models.py src/db/migrations/versions/016_agent_run_memory_idempotency.py` - passed.
- `uv run alembic upgrade head` - passed.

## Next Phase Readiness

Plan 24-04 can rely on DB-backed duplicate-process/retry safety after Wave 1 RED tests are added and Wave 1 is closed.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
