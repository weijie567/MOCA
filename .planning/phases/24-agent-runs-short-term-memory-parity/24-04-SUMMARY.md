---
phase: 24-agent-runs-short-term-memory-parity
plan: 04
subsystem: conversation-memory
tags: [conversation-service, thread-summary, idempotency, prompt-safety]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: DB-backed idempotency indexes
provides:
  - Shared run-role user/assistant message get-or-create helpers
  - Tenant/user/thread scoped run-role and source-end repository lookups
  - Idempotent thread rolling summary persistence by source end
  - Prompt summary text without raw result refs
affects: [conversation-memory, thread-summary, tool-result-prompt-summary]

tech-stack:
  added: []
  patterns: [repository scoped lookup, service get-or-create helper, SAVEPOINT race handling]

key-files:
  created: []
  modified:
    - src/conversation/repository.py
    - src/conversation/service.py
    - src/memory/thread_summary.py

key-decisions:
  - "Keep helper callers behind ConversationService so prompt-safety validation remains centralized."
  - "Use repository lookups scoped by active ConversationThread instead of querying messages/summaries by run only."
  - "Keep raw_result_ref in structured tool-result storage but remove it from prompt_summary text."

patterns-established:
  - "Run-role idempotency helper flow: validate payload, load existing row, append through existing safe path, handle uniqueness race by reloading."
  - "Rolling summary idempotency flow: compute source_end_message_id, return existing summary if present, otherwise insert through existing summary path."

requirements-completed:
  - STM-01
  - STM-03
  - STM-04
  - STM-07
  - STM-08
  - STM-10
  - STM-13

duration: 24 min
completed: 2026-06-20
---

# Phase 24 Plan 04: Idempotency Primitives Summary

**Shared service/repository helpers for exactly-once agent-run messages and source-end rolling summaries**

## Performance

- **Duration:** 24 min
- **Started:** 2026-06-20T15:02:00Z
- **Completed:** 2026-06-20T15:26:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `ConversationRepository.get_message_by_run_role(...)` and `get_thread_summary_by_source_end(...)`.
- Added `ConversationService.append_or_get_user_message_for_run(...)` and `append_or_get_assistant_message_for_run(...)`.
- Updated `ThreadRollingSummaryService.persist_thread_summary(...)` to return existing summaries for the same `source_end_message_id`.
- Removed `raw_result_ref` from prompt summary text while preserving it in structured tool-result fields.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement run-role conversation message helpers** - `d03b305` (feat)
2. **Task 2: Implement idempotent thread rolling summary persistence** - `d03b305` (feat)

## Files Created/Modified

- `src/conversation/repository.py` - Adds scoped run-role message and source-end summary lookups.
- `src/conversation/service.py` - Adds service get-or-create helpers and prompt-summary raw-ref cleanup.
- `src/memory/thread_summary.py` - Adds source-end idempotency and race reload behavior.

## Decisions Made

- Used nested transaction scopes around inserts so uniqueness races can be handled by reloading existing rows without duplicating helper logic.
- Did not change API router behavior in this plan; later plans will call these shared helpers.

## Deviations from Plan

### Auto-fixed Issues

**1. Supplementary verification used a wrong pytest node name**
- **Found during:** extra regression after plan verification
- **Issue:** `test_tool_result_storage_layers_raw_result_and_prompt_summary` does not exist.
- **Fix:** Located real test names with `rg -n "def test_" tests/tools/test_tool_result_storage.py` and reran the intended coverage.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md` records the local validation issue.
- **Verification:** Corrected command passed with `2 passed, 1 warning`.

---

**Total deviations:** 1 auto-fixed validation-command issue.
**Impact on plan:** No production/test behavior impact.

## Issues Encountered

- None in production implementation. The only issue was the local pytest node-name typo recorded separately.

## User Setup Required

None - no external service configuration required.

## Verification

- `rg -n "def get_message_by_run_role|append_or_get_user_message_for_run|append_or_get_assistant_message_for_run|get_thread_summary_by_source_end|del run_id" src/conversation/repository.py src/conversation/service.py src/memory/thread_summary.py` - found required helpers and no active `del run_id`.
- `uv run ruff check src/conversation/repository.py src/conversation/service.py src/memory/thread_summary.py tests/conversation/test_service.py tests/memory/test_thread_summary.py` - passed.
- `uv run pytest tests/conversation/test_service.py::test_append_or_get_run_role_messages_are_idempotent -q` - passed.
- `uv run pytest tests/memory/test_thread_summary.py::test_thread_rolling_summary_is_idempotent_for_same_source_end tests/memory/test_thread_summary.py::test_thread_rolling_summary_includes_safe_tool_summaries_only tests/conversation/test_service.py::test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries -q` - passed.
- Full plan verification pytest command - `4 passed, 1 warning`.
- Supplementary tool-result storage regression - `2 passed, 1 warning`.

## Next Phase Readiness

Plan 24-05 can wire `/api/v1/agent-runs` creation and SSE execution to these shared conversation identity helpers.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
