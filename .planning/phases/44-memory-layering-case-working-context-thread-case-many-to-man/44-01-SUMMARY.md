---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
plan: 01
subsystem: database
tags: [postgres, alembic, sqlalchemy, memory, schema]
requires:
  - phase: 43-intent-recognition-multi-intent-tier-a
    provides: stable pre-Phase 44 intent and memory-adjacent runtime baseline
provides:
  - thread_case_links additive M:N thread to refund-case schema
  - case_working_contexts case-scoped contextual working-state schema
  - case_working_context_revisions append-only CWC snapshot history
  - memory_write_events case_working_context audit CHECK support
affects: [memory, conversation, alembic, phase-44-wave-2]
tech-stack:
  added: []
  patterns:
    - additive Alembic DDL with UUID refund_cases.id case identity
    - append-only revision table for contextual memory history
key-files:
  created:
    - src/db/migrations/versions/021_thread_case_links.py
    - src/db/migrations/versions/022_case_working_context.py
    - tests/db/test_phase44_schema.py
  modified:
    - src/db/models.py
    - src/memory/policy.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
key-decisions:
  - "CWC and thread links bind to refund_cases.id UUID; conversation_threads.case_id string semantics remain unchanged."
  - "CWC stays authority_class='contextual_only' and stores working-state JSONB separately from case_memories/long_term_memories."
  - "memory_write_events keeps the shared audit table and widens only the memory_type CHECK for case_working_context."
patterns-established:
  - "Phase 44 migrations stay linear: 020 -> 021 -> 022."
  - "CWC downgrade blocks if case_working_context audit rows exist instead of coercing or deleting them."
requirements-completed: [MEM-01, MEM-02]
duration: 10min
completed: 2026-07-03
---

# Phase 44 Plan 01: Memory Layering DDL Summary

**Postgres DDL foundation for case working context and thread-case many-to-many links, with audited CWC writes and guarded downgrade behavior.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-02T17:30:14Z
- **Completed:** 2026-07-02T17:40:33Z
- **Tasks:** 3/3
- **Files modified:** 6

## Accomplishments

- Added `thread_case_links` as an additive M:N association table from `conversation_threads.id` to `refund_cases.id`.
- Added `case_working_contexts` and `case_working_context_revisions` with non-authoritative contextual constraints, JSONB defaults, versioning, and active-scope indexes.
- Widened `memory_write_events.memory_type` to accept `case_working_context` in both migration and ORM, and added policy literal support.
- Added DB-backed schema tests covering metadata, nullable/default parity, audit insert, downgrade guard, and clean re-upgrade.

## Task Commits

1. **Task 1: thread_case_links table** - `1d112f8` (`feat`)
2. **Task 2: case_working_contexts + revisions** - `c7dd6da` (`feat`)
3. **Task 3: CHECK/policy sync + schema tests** - `c3575de` (`test`)

## Files Created/Modified

- `src/db/migrations/versions/021_thread_case_links.py` - Adds `thread_case_links` and indexes.
- `src/db/migrations/versions/022_case_working_context.py` - Adds CWC tables, revision table, CHECK widening, and guarded downgrade.
- `src/db/models.py` - Adds `ThreadCaseLink`, `CaseWorkingContext`, `CaseWorkingContextRevision`, and syncs `MemoryWriteEvent` CHECK.
- `src/memory/policy.py` - Adds `case_working_context` to `MemoryPolicyMemoryType`.
- `tests/db/test_phase44_schema.py` - Adds metadata and live migration tests.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records the local default-DB seed-data issue encountered during mandatory Alembic validation.

## Verification

- `uv run python -c "import ast,sys; ast.parse(open('src/db/models.py').read()); ast.parse(open('src/db/migrations/versions/021_thread_case_links.py').read()); print('ok')"` -> `ok`
- `uv run python -c "import ast; ast.parse(open('src/db/models.py').read()); ast.parse(open('src/db/migrations/versions/022_case_working_context.py').read()); print('ok')"` -> `ok`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py -x -q` -> `3 passed, 5 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` -> passed after repairing pre-existing local seed data documented below
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic downgrade -1` -> passed (`022 -> 021`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic downgrade -1` -> passed (`021 -> 020`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` -> passed (`020 -> 021 -> 022`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic current` -> `022_case_working_context (head)`
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` -> single head `022_case_working_context (head)`
- `git grep -n "case_memories\|long_term_memories" -- src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py` -> no matches

## Decisions Made

- Followed the plan's additive schema boundary: no rename of `case_memories` / `long_term_memories`, and no change to `conversation_threads.case_id`.
- Used the shared `memory_write_events` audit table with a guarded downgrade instead of introducing a separate audit table in Wave 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Local Validation] Repaired default local DB seed data for pre-existing Phase 36 preflight**
- **Found during:** Plan-level mandatory `alembic upgrade head`
- **Issue:** Default local `moca` DB was at `016_agent_run_memory_idempotency`; upgrading through existing migration `019_phase36_merchant_scope_hardening` failed because six active business users had `merchant_id = NULL`.
- **Fix:** Bound the affected demo users to same-tenant merchants according to `scripts/seed_demo.py`, then reran `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` successfully.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` passed and current revision is `022_case_working_context (head)`.
- **Committed in:** plan metadata commit

**Total deviations:** 1 auto-fixed blocking local validation issue.
**Impact on plan:** No Phase 44 code scope change; the fix was local dev data repair required to satisfy the mandatory migration gate.

## Issues Encountered

- Initial default-DB `alembic upgrade head` failed in pre-existing migration `019`; incident recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Pytest emitted existing LangGraph and Alembic deprecation warnings; no test failures.

## Known Stubs

None introduced by this plan. Stub scan only hit pre-existing text outside the Phase 44 diff.

## Threat Flags

None beyond the plan threat model. The new DDL trust-boundary surfaces were explicitly covered by T-44-01 through T-44-05.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 44-02. Downstream service/repository work can build against the linear `022_case_working_context` head and the new ORM contracts.

## Self-Check: PASSED

- Created files found: `021_thread_case_links.py`, `022_case_working_context.py`, `tests/db/test_phase44_schema.py`, and this summary.
- Task commits found in git history: `1d112f8`, `c7dd6da`, `c3575de`.
- Current default local DB revision verified at `022_case_working_context (head)`.

---
*Phase: 44-memory-layering-case-working-context-thread-case-many-to-man*
*Completed: 2026-07-03*
