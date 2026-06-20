---
phase: 24-agent-runs-short-term-memory-parity
plan: 01
subsystem: testing
tags: [pytest, fastapi, sse, conversation-memory, red-tests]

requires: []
provides:
  - RED API/SSE tests for agent-run user message persistence
  - RED API/SSE tests for trusted conversation IDs in graph config
  - RED API/SSE tests for completed-run assistant messages and rolling summaries
  - RED duplicate, non-completed, ordering, and three-turn smoke coverage
affects: [agent-runs, sse, conversation-memory, thread-summary, session-memory]

tech-stack:
  added: []
  patterns: [ASGI SSE integration RED tests, DB row-count idempotency assertions]

key-files:
  created: []
  modified:
    - tests/test_agent_runs_api.py

key-decisions:
  - "Encode Phase 24 API/SSE contracts as RED tests before production changes."
  - "Keep duplicate stream coverage focused on row counts so later implementation can preserve the existing 409 duplicate claim model."

patterns-established:
  - "Use `_run_agent_run_stream` to execute ASGI SSE tests and parse emitted data lines."
  - "Assert conversation-message, summary, tool-result, and memory-write idempotency through SQLAlchemy row counts."

requirements-completed:
  - STM-01
  - STM-02
  - STM-03
  - STM-04
  - STM-09
  - STM-10
  - STM-11
  - STM-13
  - STM-14

duration: 28 min
completed: 2026-06-20
---

# Phase 24 Plan 01: API/SSE RED Test Summary

**Executable RED coverage for `/api/v1/agent-runs + SSE` conversation persistence, terminal memory ordering, duplicate safety, and three-turn continuity**

## Performance

- **Duration:** 28 min
- **Started:** 2026-06-20T14:01:00Z
- **Completed:** 2026-06-20T14:29:00Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments

- Added named RED tests for user-message persistence, trusted conversation IDs in graph config, completed assistant messages, and rolling-summary persistence.
- Replaced the old `test_sse_final_response_before_memory_write_schedule` expectation with `test_sse_final_response_after_bounded_memory_persistence_result`.
- Added non-completed, duplicate stream, and three-turn smoke tests that encode Phase 24 idempotency and continuity expectations.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RED create and graph-config tests** - `5f110fd` (test)
2. **Task 2: Add RED completed-finalizer and ordering tests** - `5f110fd` (test)
3. **Task 3: Add RED failure, retry, and smoke tests** - `5f110fd` (test)

## Files Created/Modified

- `tests/test_agent_runs_api.py` - Adds Phase 24 RED tests and helper row-count/SSE parsing utilities.

## Decisions Made

- Kept the duplicate stream contract aligned with the existing pending-run claim model: second stream returns 409 and must not duplicate memory surfaces.
- The non-completed test documents that error/cancel/interrupted paths must not create completed assistant messages or rolling summaries.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Avoided SQLAlchemy expired attribute access in async test**
- **Found during:** Task 2 focused RED run
- **Issue:** `user.tenant_id` was accessed after async commits in the summary test, producing `MissingGreenlet` instead of a clean RED assertion.
- **Fix:** Cached `tenant_id` before the stream/commit boundary.
- **Files modified:** `tests/test_agent_runs_api.py`
- **Verification:** Focused RED command now fails only on expected Phase 24 behavior gaps.
- **Committed in:** `5f110fd`

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** The fix improved test determinism without changing target behavior.

## Issues Encountered

- The current implementation fails the new RED tests as expected: POST does not persist user messages; SSE config lacks conversation IDs; completed runs do not persist assistant messages or rolling summaries; memory persistence still happens after `final_response`.

## User Setup Required

None - no external service configuration required.

## Verification

- `rg -n "test_create_agent_run_persists_exactly_one_user_message|test_agent_run_stream_passes_conversation_ids_to_graph_and_tools|test_completed_agent_run_persists_exactly_one_assistant_message|test_completed_agent_run_updates_thread_summary_idempotently|test_sse_final_response_after_bounded_memory_persistence_result|test_agent_run_error_cancel_interrupted_do_not_write_completed_memory|test_duplicate_sse_stream_does_not_duplicate_memory_surfaces|test_three_turn_agent_runs_smoke_uses_slots_and_summary_context|test_sse_final_response_before_memory_write_schedule" tests/test_agent_runs_api.py` - found all new names and no old active ordering test name.
- `uv run ruff check tests/test_agent_runs_api.py` - passed.
- `uv run pytest tests/test_agent_runs_api.py::test_create_agent_run_persists_exactly_one_user_message tests/test_agent_runs_api.py::test_agent_run_stream_passes_conversation_ids_to_graph_and_tools tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_updates_thread_summary_idempotently tests/test_agent_runs_api.py::test_agent_run_error_cancel_interrupted_do_not_write_completed_memory tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result tests/test_agent_runs_api.py::test_three_turn_agent_runs_smoke_uses_slots_and_summary_context -q` - exited 1 as expected; 7 failed on target behavior gaps, 1 passed for non-completed no-false-memory behavior.

## Next Phase Readiness

Plans 24-05 through 24-07 can now implement against exact API/SSE test names for persistence, finalizer ordering, and retry safety.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
