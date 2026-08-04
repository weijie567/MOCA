---
phase: 45-memory-lifecycle-wiring-for-case-working-context
plan: 02
subsystem: memory
tags: [case-working-context, memory, thread-case-links, reviewed-memory-context, tdd]
requires:
  - phase: 45-memory-lifecycle-wiring-for-case-working-context
    provides: lifecycle adapter foundation and CWC contextual refs from 45-01
provides:
  - additive AgentState fields for active CWC payload and lifecycle status
  - CWC link-and-active-read lifecycle adapter with run_auto thread-case linking
  - memory_context_load seam wiring for active CWC payload/status
  - focused tests for skipped, unresolved, link failure, dedupe, and seam error behavior
affects: [memory, case-working-context, phase-45-plan-03, phase-45-plan-04]
tech-stack:
  added: []
  patterns:
    - TDD red/green commits for state, lifecycle adapter, and memory seam wiring
    - SQLAlchemy nested transaction savepoint around read-seam thread-case link writes
    - fail-closed trusted_context parsing for CWC lifecycle identity
key-files:
  created:
    - .planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-02-SUMMARY.md
  modified:
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - src/memory/case_working_context_lifecycle.py
    - src/agent/nodes/reviewed_memory_context_retrieve.py
    - tests/agent/test_nodes/test_receive_request.py
    - tests/agent/test_case_working_context_lifecycle.py
    - tests/agent/test_reviewed_memory_context_retrieve.py
    - .planning/ARCHITECTURE-DEBT.md
key-decisions:
  - "Read-seam thread-case linking uses session.begin_nested() and never rolls back the shared graph session directly."
  - "CWC identity for memory_context_load comes only from trusted_context plus trusted case refs in state; missing identity yields explicit skipped status."
  - "Active CWC remains separate from reviewed case_memory and is exposed through additive state and memory_context_bundle fields."
patterns-established:
  - "CWC read/link lifecycle returns contextual-only status refs for success, skip, missing, and link failure."
  - "reviewed_memory_context_retrieve preserves reviewed memory output even when CWC lifecycle loading errors."
requirements-completed: [MEM-01, MEM-02]
duration: 10min
completed: 2026-07-03
---

# Phase 45 Plan 02: Active CWC Read and Link Wiring Summary

**Active Case Working Context read plus `run_auto` thread-case linking at the existing memory_context_load seam.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-03T05:15:24Z
- **Completed:** 2026-07-03T05:24:33Z
- **Tasks:** 3/3
- **Files modified:** 8

## Accomplishments

- Added `case_working_context` and `case_working_context_lifecycle_status` to `AgentState` and reset both at each `receive_request`.
- Implemented `CaseWorkingContextLifecycleAdapter.link_and_load_active(...)` with trusted case resolution, `run_auto` thread-case linking, savepoint-wrapped link failure handling, and active CWC read projection.
- Wired active CWC payload/status into `reviewed_memory_context_retrieve` and `memory_context_bundle` without changing graph topology or repurposing reviewed `case_memory`.

## Task Commits

1. **Task 1 RED: CWC state/reset tests** - `0c41b84` (`test`)
2. **Task 1 GREEN: AgentState and receive_request fields** - `82b623f` (`feat`)
3. **Task 2 RED: link/load lifecycle tests** - `a19076d` (`test`)
4. **Task 2 GREEN: lifecycle link_and_load_active** - `c442591` (`feat`)
5. **Task 3 RED: memory seam CWC tests** - `4d26bb8` (`test`)
6. **Task 3 GREEN: reviewed-memory seam wiring** - `a944a04` (`feat`)

## Files Created/Modified

- `src/agent/state.py` - Adds active CWC payload/status state fields.
- `src/agent/nodes/receive_request.py` - Clears active CWC fields at turn start.
- `src/memory/case_working_context_lifecycle.py` - Adds lifecycle result model and `link_and_load_active(...)` orchestration.
- `src/agent/nodes/reviewed_memory_context_retrieve.py` - Invokes CWC lifecycle loading from trusted context and merges payload/status into outputs.
- `tests/agent/test_nodes/test_receive_request.py` - Covers CWC state declaration and reset.
- `tests/agent/test_case_working_context_lifecycle.py` - Covers run_auto linking, dedupe, skipped/unresolved paths, link failure savepoint behavior, and active CWC payload loading.
- `tests/agent/test_reviewed_memory_context_retrieve.py` - Covers seam invocation, bundle merge, skipped status, and adapter error behavior.
- `.planning/ARCHITECTURE-DEBT.md` - Records the verified memory-subsystem fix and remaining 45-03/45-04 risks.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py -x -q`
  - RED before implementation: failed with missing `case_working_context`.
  - GREEN after implementation: `14 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_case_links.py -x -q`
  - RED before implementation: failed with missing `link_and_load_active`.
  - GREEN after implementation: `20 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_case_working_context_lifecycle.py -x -q`
  - RED before implementation: failed because CWC adapter was not invoked.
  - GREEN after implementation: `24 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_case_working_context_lifecycle.py -q` -> `38 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_working_context_lifecycle.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/reviewed_memory_context_retrieve.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_case_working_context_lifecycle.py` -> `All checks passed!`
- `grep -n "link_source=\"run_auto\"" src/memory/case_working_context_lifecycle.py` -> matched.
- `grep -n "linked_by_run_id=run_id" src/memory/case_working_context_lifecycle.py` -> matched.
- `grep -n "begin_nested" src/memory/case_working_context_lifecycle.py` -> matched.
- `grep -n "case_working_context_lifecycle_status" src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/reviewed_memory_context_retrieve.py` -> matched all three files.
- `grep -n "case_working_context_status_ref" src/agent/nodes/reviewed_memory_context_retrieve.py` -> matched.
- `git diff -- src/agent/graph.py` -> no diff.

## Decisions Made

- Used a SQLAlchemy nested transaction for read-seam link creation so link failures are visible but do not poison the parent graph session.
- Kept success status broad (`status="completed"`) while expressing the specific lifecycle state through `resolve_status`, `link_status`, and `read_status`.
- Kept `memory_context` as the reviewed-memory bundle and added CWC fields to root state plus `memory_context_bundle`, preserving existing reviewed-memory consumers.

## Deviations from Plan

### Project-Rule Documentation

**1. [CLAUDE.md / AGENTS.md - Memory Architecture Debt Ledger] Added Phase 45 Plan 02 memory entry**
- **Found during:** Summary preparation after memory subsystem changes.
- **Issue:** Project rules require appending verified memory subsystem fixes to `.planning/ARCHITECTURE-DEBT.md`.
- **Fix:** Added a Chinese Phase 45 Plan 02 entry with issue/root cause, fix, evidence, verification, and remaining 45-03/45-04 risks.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Diff reviewed; entry claims only active read/link wiring and explicitly defers terminal writeback/spec final sweep.
- **Committed in:** final metadata commit.

**Total deviations:** 1 project-rule documentation update.
**Impact on plan:** No code scope expansion; the extra change records required subsystem debt status.

## Issues Encountered

- Expected TDD RED failures occurred before each GREEN implementation.
- No local validation incident required `.planning/LOCAL-VALIDATION-ISSUES.md`; the only warning was an existing LangGraph deprecation warning.

## Known Stubs

None. Stub scan found only explicit `None` payloads for skipped/missing/error CWC lifecycle paths; these are tested status states, not placeholders.

## Threat Flags

None beyond the plan threat model. The planned trusted-context-to-link/read boundary is implemented with tenant-scoped resolver checks, trusted context parsing, and contextual-only CWC projection.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 45-03. Terminal finalizer CWC writeback can now reuse the same lifecycle adapter boundary while preserving the read/link semantics and explicit status fields established here.

## TDD Gate Compliance

- RED commits present: `0c41b84`, `a19076d`, `4d26bb8`.
- GREEN commits present after RED: `82b623f`, `c442591`, `a944a04`.
- No refactor commit was needed.

## Self-Check: PASSED

- Created files found: `.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-02-SUMMARY.md`.
- Modified implementation/test files found: `src/agent/state.py`, `src/agent/nodes/receive_request.py`, `src/memory/case_working_context_lifecycle.py`, `src/agent/nodes/reviewed_memory_context_retrieve.py`, and focused tests.
- Task commits found in git history: `0c41b84`, `82b623f`, `a19076d`, `c442591`, `4d26bb8`, `a944a04`.
- Current dirty user-owned files remain outside this plan's staged code commits.

---
*Phase: 45-memory-lifecycle-wiring-for-case-working-context*
*Completed: 2026-07-03*
