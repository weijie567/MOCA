---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
plan: 03
subsystem: memory
tags: [postgres, sqlalchemy, memory, audit, provenance]
requires:
  - phase: 44-memory-layering-case-working-context-thread-case-many-to-man
    provides: Wave 1 DDL and Wave 2 CWC resolver/schema/repository
provides:
  - explicit thread↔case link write lifecycle with active-row dedup
  - ConversationRepository.link_case B3 linkage point
  - isolated CWC write service with case_working_context audit events
  - PII blocked audit path and version-conflict skip audit path
affects: [memory, conversation, phase-44-wave-4, phase-45-memory-lifecycle-wiring]
tech-stack:
  added: []
  patterns:
    - method-local import to avoid conversation ↔ memory package initialization cycle
    - isolated child-session memory writes with parent transaction survival test
    - canonical memory_identity.v1 candidate hash for CWC audit events
key-files:
  created:
    - src/memory/thread_case_links.py
    - src/memory/case_working_context_service.py
    - tests/memory/test_thread_case_links.py
    - tests/memory/test_case_working_context_service.py
    - .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-03-SUMMARY.md
  modified:
    - src/conversation/repository.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
key-decisions:
  - "Thread↔case links are written only through explicit link_case/link_thread_to_case calls; append_message remains link-free."
  - "CWC writes require a real run_id because memory_write_events.run_id is NOT NULL, including staff_manual edits."
  - "Phase 45 owns wiring real run/staff callers to link_case and CWC read/write lifecycle hooks."
requirements-completed: [MEM-01, MEM-02]
duration: 12min
completed: 2026-07-03
---

# Phase 44 Plan 03: Memory Write Lifecycle Summary

**Explicit thread-case linkage and audited isolated Case Working Context writes.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-02T18:01:23Z
- **Completed:** 2026-07-02T18:12:37Z
- **Tasks:** 3/3
- **Files modified:** 8

## Accomplishments

- Added `ThreadCaseLinkRepository` with `link_source` validation, active-row dedup, and bidirectional active read helpers.
- Added `ConversationRepository.link_case(...)` as the explicit B3 linkage point while proving `append_message()` creates no link rows.
- Added `CaseWorkingContextService.write_case_working_context(...)` with validation-before-write, isolated child-session writes, canonical provenance hashing, `case_working_context` audit events, PII blocking, and version-conflict skip events.
- Added DB-backed tests for thread↔case dedup/many-to-many reads, explicit link-case lifecycle, CWC audit emission, blocked PII, conflict audit, full content hydration, and parent transaction isolation.

## Task Commits

1. **Task 1 RED: Thread-case repository tests** - `5d93324` (`test`)
2. **Task 1 GREEN: Thread-case repository** - `83820ea` (`feat`)
3. **Task 2: Explicit conversation linkage point** - `53efe92` (`feat`)
4. **Task 3 RED: CWC write service tests** - `994cadd` (`test`)
5. **Task 3 GREEN: CWC write service** - `db3bbcc` (`feat`)

## Files Created/Modified

- `src/memory/thread_case_links.py` - Thread-case link writer, dedup, and read helpers.
- `src/conversation/repository.py` - Adds `link_case(...)`; leaves legacy `case_id` path and `append_message()` behavior intact.
- `src/memory/case_working_context_service.py` - Isolated CWC write orchestration and audit event emission.
- `tests/memory/test_thread_case_links.py` - DB-backed thread-case lifecycle tests.
- `tests/memory/test_case_working_context_service.py` - DB-backed CWC service/audit/isolation tests.
- `.planning/ARCHITECTURE-DEBT.md` - Memory subsystem ledger entry for Wave 3.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Local validation note for the import-cycle failure and parallel DB schema collision.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_thread_case_links.py -x -q`
  - Task 1 RED: failed as expected with `ModuleNotFoundError: No module named 'src.memory.thread_case_links'`
  - Task 1 GREEN: `3 passed, 1 warning`
  - Task 2 final: `4 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/conversation/test_repository.py -q` -> `5 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_service.py -x -q`
  - Task 3 RED: failed as expected with `ModuleNotFoundError: No module named 'src.memory.case_working_context_service'`
  - Task 3 GREEN: `9 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/thread_case_links.py src/conversation/repository.py src/memory/case_working_context_service.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py` -> `All checks passed!`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py -q` -> `13 passed, 1 warning`
- `grep -n "deleted_at" src/memory/thread_case_links.py` -> active-row filters at lines 63, 80, 98.
- `grep -n "def link_case" src/conversation/repository.py` -> matched line 97.
- `grep -n "run_memory_side_effect_in_isolated_session" src/memory/case_working_context_service.py` -> matched import and call.
- `git grep -n "conversation_threads.case_id" src/conversation/repository.py` -> no matches because the Python repository uses ORM attributes, not table-qualified SQL strings.
- `git grep -n "case_id" src/conversation/repository.py` -> confirms legacy `case_id: str | None` creation path and `summary.case_id = thread.case_id` remain, with the new UUID `link_case` path additive.

## Decisions Made

- Did not modify migrations, table names, `case_memories`, `long_term_memories`, or `conversation_threads.case_id`.
- Kept the real run/staff invocation sites out of Wave 3. `DEFER-LINK-CASE-CALLER -> Phase 45 memory lifecycle wiring`.
- Kept CWC active-read consumer wiring out of Wave 3. `DEFER-CWC-READ-ACTIVE-CALLER -> Phase 45 memory lifecycle wiring`.
- Did not update `.planning/STATE.md` or `.planning/ROADMAP.md` because the orchestrator owns phase state for this Wave 3 execution.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Import Cycle] Moved ThreadCaseLinkRepository import into link_case**
- **Found during:** Task 2 verification.
- **Issue:** Module-level import from `src.conversation.repository` to `src.memory.thread_case_links` triggered `src.memory.__init__`, which re-entered conversation imports before `ConversationRepository` finished initializing.
- **Fix:** Kept the return type import from ORM models but moved `ThreadCaseLinkRepository` import into `ConversationRepository.link_case(...)`.
- **Files modified:** `src/conversation/repository.py`
- **Commit:** `53efe92`

**2. [Rule 1 - Test Bug] Removed order assumption from many-to-many case list assertion**
- **Found during:** Task 2 serial rerun of `tests/memory/test_thread_case_links.py`.
- **Issue:** The test assumed insertion order for `list_cases_for_thread`; the behavior only requires returning all active case IDs.
- **Fix:** Asserted set membership instead of list order.
- **Files modified:** `tests/memory/test_thread_case_links.py`
- **Commit:** `53efe92`

### Project-Rule Documentation

**1. [CLAUDE.md / AGENTS.md - Local Validation Ledger] Recorded Wave 3 validation failures**
- **Found during:** Task 2 verification.
- **Issue:** Import cycle and parallel DB-backed pytest schema collision were local validation failures requiring documentation.
- **Fix:** Added a Chinese entry to `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Commit:** summary metadata commit

**2. [CLAUDE.md / AGENTS.md - Memory Architecture Debt Ledger] Added verified Wave 3 memory entry**
- **Found during:** Summary preparation after memory subsystem changes.
- **Issue:** Project rules require recording memory subsystem fixes and remaining risks.
- **Fix:** Added a Chinese Phase 44 Wave 3 entry with problem/root cause, fix, evidence, verification, and Phase 45/Wave 4 residual risks.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Commit:** summary metadata commit

## Issues Encountered

- One parallel DB-backed verification attempt failed because two pytest processes rebuilt the same `moca_test` schema simultaneously; all DB-backed Phase 44 gates were rerun serially and passed.
- The literal `conversation_threads.case_id` grep in the plan did not match this Python repository file; the practical `case_id` grep confirms the legacy ORM path remains.

## Known Stubs

None. Stub scan only found type/default annotations such as optional `None` defaults; no placeholder data source or UI stub was introduced.

## Threat Flags

None beyond the plan threat model. The new write surfaces are the planned `thread_case_links` writer and `memory_write_events(memory_type='case_working_context')` audit path, both covered by T-44-11 through T-44-15.

## User Setup Required

None. PostgreSQL-backed tests passed in the existing local test environment.

## Next Phase Readiness

Ready for 44-04. Wave 4 can perform contract-spec alignment and final no-redline verification. Phase 45 owns real lifecycle call-site wiring for `link_case` and CWC read/write consumers.

## Self-Check: PASSED

- Created files found: `thread_case_links.py`, `case_working_context_service.py`, both focused test files, and this summary.
- Task commits found in git history: `5d93324`, `83820ea`, `53efe92`, `994cadd`, `db3bbcc`.
- Red lines verified by scope: no DDL/migration changes, no `case_memories` / `long_term_memories` rename, and no `conversation_threads.case_id` migration/retype/drop.
