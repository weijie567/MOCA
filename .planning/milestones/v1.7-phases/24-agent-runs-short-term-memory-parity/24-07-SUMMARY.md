---
phase: 24-agent-runs-short-term-memory-parity
plan: 07
subsystem: agent-runs-terminal-semantics
tags: [agent-runs, sse, retry-idempotency, terminal-status, memory-guards]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: Completed-run memory finalizer and pre-response ordering
provides:
  - Verified completed-only terminal memory guards
  - Duplicate/reopened stream side-effect spy coverage
  - Failure/interruption coverage for no false completed memory
affects: [agent-runs-api, sse-retry, memory-finalizer-tests]

tech-stack:
  added: []
  patterns: [pending-run claim guard, completed-only memory guard, duplicate side-effect spies]

key-files:
  created: []
  modified:
    - tests/test_agent_runs_api.py

key-decisions:
  - "Keep duplicate/reopened streams conflict-safe with RUN_ALREADY_STARTED instead of adding SSE replay."
  - "Treat Plan 24-06 finalizer status guard as the production completed-only gate."
  - "Strengthen duplicate-stream tests with call spies rather than adding new router branches."

patterns-established:
  - "Duplicate stream test tracks graph, finalizer, memory_write, user-message helper, assistant-message helper, and summary calls."
  - "Non-completed terminal paths are verified through row-count assertions instead of synthetic assistant-memory writes."

requirements-completed:
  - STM-09
  - STM-10
  - STM-11
  - STM-12
  - STM-13

duration: 4 min
completed: 2026-06-20
---

# Phase 24 Plan 07: Non-Completed Terminal Semantics Summary

**Failure, interruption, and duplicate-stream paths do not create false completed memory**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-20T14:52:00Z
- **Completed:** 2026-06-20T14:56:00Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments

- Verified existing completed-only finalizer guard in `src/api/services/agent_run_memory.py`.
- Verified error, cancellation, and approval interruption paths do not create assistant messages or thread summaries.
- Hardened duplicate SSE stream test with spies for graph execution, finalizer, `memory_write`, user/assistant message helpers, and thread-summary persistence.
- Confirmed duplicate streams still return `RUN_ALREADY_STARTED` and do not replay or re-run side effects.

## Task Commits

Each task was committed atomically:

1. **Task 1: Gate non-completed terminal states away from completed memory** - `e73cd36` (test)
2. **Task 2: Harden duplicate retry/reopen idempotency** - `e73cd36` (test)
3. **Task 3: Keep timeline persistence statuses truthful** - `e73cd36` (test)

## Files Created/Modified

- `tests/test_agent_runs_api.py` - Adds duplicate-stream call-count spies to prove no second graph/finalizer/memory side effects.

## Decisions Made

- Did not add SSE event replay for completed runs; duplicate/reopened streams remain conflict-safe with `HTTP 409`.
- Did not add new production branches because the 24-06 finalizer already gates on explicit `final_status == "completed"`.

## Deviations from Plan

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check src/api/routers/agent_runs.py src/api/services/agent_run_memory.py tests/test_agent_runs_api.py` - passed.
- `uv run pytest tests/test_agent_runs_api.py::test_agent_run_error_cancel_interrupted_do_not_write_completed_memory tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result tests/test_agent_runs_api.py::test_sse_interrupted_path_skips_memory_write -q` - passed with `4 passed, 1 warning`.
- Grep checks confirmed `RUN_ALREADY_STARTED`, `agent_run_memory_finalize`, and `memory_write_status` coverage remains present.

## Next Phase Readiness

Plan 24-08 can now focus on prompt-context loading and continuity after terminal memory semantics are bounded.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
