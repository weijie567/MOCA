---
phase: 24-agent-runs-short-term-memory-parity
plan: 06
subsystem: agent-runs-terminal-memory
tags: [agent-runs, sse, memory-finalizer, thread-summary, session-memory]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: Agent-run conversation identity wiring
provides:
  - Completed-run terminal memory finalizer service
  - Assistant message and rolling summary persistence before SSE final_response
  - Explicit session-memory write result before user-visible final response
  - Rollback coverage for staged finalizer writes when terminal completion persistence fails
affects: [agent-runs-api, conversation-memory, thread-summary, session-memory]

tech-stack:
  added: []
  patterns: [terminal finalizer service, pre-response memory result, single transaction completion]

key-files:
  created:
    - src/api/services/__init__.py
    - src/api/services/agent_run_memory.py
  modified:
    - src/api/routers/agent_runs.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "Use a FastAPI-free service boundary for completed-run memory finalization."
  - "Guard finalizer execution on the explicit computed final_status argument, not run.final_status."
  - "Keep _complete_run as the single transaction owner for run status, steps, and staged memory writes."
  - "Keep legacy /agent/chat background memory scheduling unchanged."

patterns-established:
  - "Completed finalizer writes assistant message, rolling summary, and bounded session memory before SSE final_response."
  - "Finalizer trace step records assistant_message_id, thread_summary_id, and canonical memory_write_status."
  - "Non-completed terminal statuses return skipped/no-op without completed-memory writes."

requirements-completed:
  - STM-03
  - STM-04
  - STM-06
  - STM-07
  - STM-10
  - STM-11
  - STM-13

duration: 13 min
completed: 2026-06-20
---

# Phase 24 Plan 06: Completed-Run Memory Finalizer Summary

**Agent-run final responses now wait for terminal memory persistence results**

## Performance

- **Duration:** 13 min
- **Started:** 2026-06-20T14:39:00Z
- **Completed:** 2026-06-20T14:52:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `finalize_completed_agent_run_memory(...)` in `src/api/services/agent_run_memory.py`.
- Persisted exactly one completed assistant message with `source=agent_runs.finalizer`.
- Updated rolling thread summaries idempotently from committed conversation messages.
- Ran terminal `memory_write(...)` before SSE `final_response` and recorded canonical `memory_write_status`.
- Wired both updates and lifecycle SSE branches through the finalizer before `_complete_run(...)`.
- Added tests for updates ordering, lifecycle ordering, skip/no-op status, rollback on `_complete_run` failure, and metadata denylist assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create completed-run memory finalizer service** - `b71848b` (feat)
2. **Task 2: Wire finalizer before SSE final_response** - `b71848b` (feat)
3. **Task 3: Verify completed-run idempotency and no raw leakage** - `b71848b` (feat)

## Files Created/Modified

- `src/api/services/__init__.py` - Adds API service package boundary.
- `src/api/services/agent_run_memory.py` - Implements completed-run finalizer and trace-step result mapping.
- `src/api/routers/agent_runs.py` - Calls the finalizer before `_complete_run(...)` and before SSE `final_response`.
- `tests/test_agent_runs_api.py` - Adds focused finalizer, lifecycle, rollback, and prompt-safety coverage.

## Decisions Made

- Canonicalized session-memory outcomes to `completed`, `skipped`, `error`, or `failed` for the finalizer trace step.
- Preserved `_schedule_memory_write_after_response(...)` as a helper for legacy `/agent/chat`; removed its completed `/agent-runs` final-response calls.
- Built memory-write state from graph state plus trusted run/user identity so direct generator tests and API streams share the same identity contract.

## Deviations from Plan

### Auto-fixed Issues

**1. Ordering test monkeypatched the old router-level `memory_write` path**
- **Found during:** 24-06 focused pytest verification
- **Issue:** The test still patched `src.api.routers.agent_runs.memory_write`, but the new service boundary calls `src.api.services.agent_run_memory.memory_write`.
- **Fix:** Updated the monkeypatch path and added identity/session assertions on the finalizer memory state.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md` records the local validation issue.
- **Verification:** Corrected 24-06 focused pytest passed with `19 passed, 1 warning`.

---

**Total deviations:** 1 auto-fixed test monkeypatch update.
**Impact on plan:** No production behavior impact.

## Issues Encountered

- No production blockers. The only issue was a test patch target that lagged behind the new service boundary.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py tests/test_agent_runs_api.py tests/memory/test_session_memory_service.py` - passed.
- `uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_updates_thread_summary_idempotently tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_skips_non_completed_status tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_rolls_back_if_complete_run_fails tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result tests/test_agent_runs_api.py::test_sse_lifecycle_events_final_response_after_bounded_memory_persistence_result tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/memory/test_session_memory_service.py -q` - passed with `19 passed, 1 warning`.
- Plan grep checks found required finalizer strings, explicit final-status guard, required memory-state identity fields, no `session.commit()`/`session.rollback()` in the finalizer service, and no completed `/agent-runs` background memory scheduling call.

## Next Phase Readiness

Plan 24-07 can build on the completed-only finalizer by tightening non-completed terminal semantics for error, cancel, and interruption paths.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
