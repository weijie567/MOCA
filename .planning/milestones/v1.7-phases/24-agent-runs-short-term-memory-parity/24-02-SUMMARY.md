---
phase: 24-agent-runs-short-term-memory-parity
plan: 02
subsystem: testing
tags: [pytest, prompt-context, session-memory, authority-boundary, red-tests]

requires: []
provides:
  - RED service tests for agent-run prompt context parity
  - RED service tests for run-role message and rolling-summary idempotency
  - RED session-memory tests for current-turn override and fail-closed scope checks
  - RED prompt-safety and memory authority-boundary tests
affects: [conversation-memory, thread-summary, session-memory, context-assembler, rag-authority]

tech-stack:
  added: []
  patterns: [service RED tests, material-claim authority boundary checks, session-memory scope fixtures]

key-files:
  created: []
  modified:
    - tests/conversation/test_service.py
    - tests/memory/test_thread_summary.py
    - tests/agent/test_session_memory_integration.py
    - tests/agent/context/test_assembler.py
    - tests/agent/test_memory_evidence_boundary.py

key-decisions:
  - "Keep 24-02 as RED-only: no production source changes."
  - "Stage only Phase 24 hunks in `tests/agent/test_session_memory_integration.py`; pre-existing user dirty tests remain unstaged."
  - "Use existing graph, service, and material-claim verifier boundaries instead of introducing test-only production hooks."

patterns-established:
  - "Prompt-context RED tests assert recent messages, prior rolling summaries, and tool prompt summaries are all scoped and non-empty."
  - "Session-memory RED tests assert trusted inherited metadata remains contextual and current-turn extracted slots win."
  - "Authority-boundary tests keep memory/recent/summary/session context below policy, business fact, action, and replay authority."

requirements-completed:
  - STM-05
  - STM-06
  - STM-07
  - STM-08
  - STM-12
  - STM-13

duration: 31 min
completed: 2026-06-20
---

# Phase 24 Plan 02: Prompt Context RED Test Summary

**Executable RED coverage for agent-run prompt context, session-memory continuity, prompt safety, and memory authority boundaries**

## Performance

- **Duration:** 31 min
- **Started:** 2026-06-20T14:30:00Z
- **Completed:** 2026-06-20T15:01:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added prompt-context tests for prior `thread_rolling` summary, bounded recent messages, prompt-safe tool summaries, scope assertions, and run-role idempotency helpers.
- Added rolling-summary idempotency test requiring repeated same-source-end persistence to return the existing summary and keep row count at one.
- Added session-memory tests for explicit current-turn override and wrong tenant/user/thread, expired, and incompatible fail-closed behavior.
- Added prompt assembler and material-claim authority-boundary tests asserting forbidden raw/private/authority/debug/replay markers stay out of prompt or memory surfaces.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RED conversation and summary service tests** - `9dc2427` (test)
2. **Task 2: Add RED session slot continuity and fail-closed tests** - `9dc2427` (test)
3. **Task 3: Add RED prompt-safety and authority-boundary tests** - `9dc2427` (test)

## Files Created/Modified

- `tests/conversation/test_service.py` - Adds prompt-context parity and run-role idempotency RED tests.
- `tests/memory/test_thread_summary.py` - Adds same-source-end rolling-summary idempotency RED test.
- `tests/agent/test_session_memory_integration.py` - Adds current-turn override and fail-closed scope RED tests.
- `tests/agent/context/test_assembler.py` - Adds agent-runs prompt-safety RED test.
- `tests/agent/test_memory_evidence_boundary.py` - Adds memory authority-boundary RED test.

## Decisions Made

- The session integration file already had unrelated unstaged user changes. Only the 24-02 hunks were staged and committed.
- The focused RED run intentionally allows some tests to pass where current behavior already satisfies the contract; the command still exits as expected because uncovered target gaps fail.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed as written.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** Wave 1 now has complete RED coverage for downstream implementation.

## Issues Encountered

- Current implementation fails the new RED tests as expected:
  - tool prompt summaries still expose `raw_result_ref` marker content;
  - `ConversationService.append_or_get_user_message_for_run` and `append_or_get_assistant_message_for_run` do not exist yet;
  - repeated rolling summary persistence returns `None` instead of the existing summary;
  - `ContextAssembler` does not sanitize raw/private/authority/debug markers from all agent-run prompt surfaces.

## User Setup Required

None - no external service configuration required.

## Verification

- `rg -n "test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries|test_append_or_get_run_role_messages_are_idempotent" tests/conversation/test_service.py` - found both names.
- `rg -n "test_thread_rolling_summary_is_idempotent_for_same_source_end" tests/memory/test_thread_summary.py` - found the summary idempotency test.
- `rg -n "test_agent_runs_session_slots_explicit_current_turn_overrides_inherited|test_agent_runs_session_memory_wrong_scope_fails_closed" tests/agent/test_session_memory_integration.py` - found both names.
- `rg -n "test_agent_runs_prompt_context_excludes_raw_tool_private_authority_and_debug_fields" tests/agent/context/test_assembler.py` - found the prompt-safety test.
- `rg -n "test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority" tests/agent/test_memory_evidence_boundary.py` - found the authority-boundary test.
- `uv run ruff check tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py` - passed.
- Focused RED pytest command from `24-02-PLAN.md` - wrapper exited 0; pytest exited 1 as expected with 4 failed and 3 passed.

## Next Phase Readiness

Plan 24-04 can now implement shared conversation and rolling-summary idempotency primitives against exact RED test names.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
