---
phase: 24-agent-runs-short-term-memory-parity
plan: 05
subsystem: agent-runs-api
tags: [agent-runs, conversation-identity, sse, fail-closed]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: Shared conversation idempotency primitives
provides:
  - Agent-run creation writes an idempotent user conversation message
  - SSE execution injects trusted conversation IDs into graph config
  - Missing user conversation identity fails closed before graph execution
affects: [agent-runs-api, sse-execution, conversation-memory]

tech-stack:
  added: []
  patterns: [same-transaction create, trusted DB identity lookup, fail-closed terminal run state]

key-files:
  created: []
  modified:
    - src/api/routers/agent_runs.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "Create-run persists the user message in the same transaction as AgentRun creation."
  - "SSE graph config uses conversation IDs resolved from the database, never client-supplied IDs."
  - "A claimed run without its user message is marked error with RUN_CONVERSATION_MESSAGE_MISSING before graph execution."

patterns-established:
  - "Agent-run create path calls ConversationService.append_or_get_user_message_for_run(...) before commit."
  - "SSE path resolves the persisted user message after run claim and injects conversation_thread_id, conversation_message_id, and conversation_service."
  - "Fail-closed identity guard commits a terminal error state and returns HTTP 409 without calling the graph."

requirements-completed:
  - STM-01
  - STM-02
  - STM-07
  - STM-10
  - STM-13

duration: 32 min
completed: 2026-06-20
---

# Phase 24 Plan 05: Agent Run Conversation Identity Summary

**Agent-run create and SSE execution now share durable conversation identity**

## Performance

- **Duration:** 32 min
- **Started:** 2026-06-20T14:06:00Z
- **Completed:** 2026-06-20T14:38:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Updated `POST /api/v1/agent-runs` to create the user conversation message through `ConversationService.append_or_get_user_message_for_run(...)` before committing the pending run.
- Updated SSE execution to resolve the persisted user message from trusted run/user/thread IDs after `_claim_pending_run_for_stream(...)`.
- Injected `conversation_thread_id`, `conversation_message_id`, and `conversation_service` into graph config before streaming starts.
- Added fail-closed handling for missing user conversation identity: terminal `error` state, `RUN_CONVERSATION_MESSAGE_MISSING`, HTTP 409, and no graph call.

## Task Commits

Each task was committed atomically:

1. **Task 1: Persist exactly one user message during run creation** - `e7a3733` (feat)
2. **Task 2: Resolve user message and inject trusted SSE graph config** - `e7a3733` (feat)

## Files Created/Modified

- `src/api/routers/agent_runs.py` - Wires create-run persistence, trusted SSE config, and missing-message fail-closed terminal state.
- `tests/test_agent_runs_api.py` - Adds missing-user-message fail-closed coverage alongside the existing create/SSE conversation identity tests.

## Decisions Made

- Kept the response API contract unchanged while reusing the request trace ID for both run creation and user-message persistence.
- Used `ConversationRepository.get_message_by_run_role(...)` directly for SSE lookup because the stream path needs the persisted message ID before graph execution.
- Preserved `_trusted_tool_config(...)` scope handling and legacy `/agent/chat` behavior unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. Missing-user-message test initially called `_create_run` with an unsupported helper argument**
- **Found during:** focused 24-05 pytest verification
- **Issue:** The new test passed `thread_id=...` to `_create_run(...)`, but that helper does not accept a thread override.
- **Fix:** Removed the unsupported argument and used the helper's generated thread ID.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md` records the local validation issue.
- **Verification:** Corrected focused pytest command passed with `3 passed, 1 warning`.

---

**Total deviations:** 1 auto-fixed test-helper issue.
**Impact on plan:** No production behavior impact.

## Issues Encountered

- No production implementation blockers. The only issue was the local test-helper mismatch recorded separately.

## User Setup Required

None - no external service configuration required.

## Verification

- `rg -n "append_or_get_user_message_for_run|agent_runs.request.v1|agent_runs.create|RUN_CONVERSATION_MESSAGE_MISSING|conversation_thread_id|conversation_message_id|conversation_service" src/api/routers/agent_runs.py` - found required create/SSE/fail-closed strings.
- `uv run ruff check src/api/routers/agent_runs.py tests/test_agent_runs_api.py` - passed.
- `uv run pytest tests/test_agent_runs_api.py::test_create_agent_run_persists_exactly_one_user_message tests/test_agent_runs_api.py::test_agent_run_stream_passes_conversation_ids_to_graph_and_tools tests/test_agent_runs_api.py::test_agent_run_stream_fails_closed_when_user_message_missing -q` - passed.
- Full plan verification pytest command - `2 passed, 1 warning`.

## Next Phase Readiness

Plan 24-06 can implement completed-run assistant-message finalization on top of the trusted conversation IDs now passed through the Agent Run SSE path.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
