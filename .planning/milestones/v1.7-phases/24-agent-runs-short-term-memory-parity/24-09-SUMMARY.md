---
phase: 24-agent-runs-short-term-memory-parity
plan: 09
subsystem: agent-runs-regression-smoke
tags: [agent-runs, legacy-chat, regression, three-turn-smoke, short-term-memory]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: Safe prompt context loading and authority-boundary protections
provides:
  - Legacy chat compatibility regression coverage
  - Three-turn provider-free Agent Console memory smoke
  - Focused Phase 24 regression and lint gate
affects: [agent-runs-api, legacy-chat, conversation-service, session-memory, regression-tests]

tech-stack:
  added: []
  patterns: [provider-free ASGI/SSE smoke, deterministic memory graph, create-before-stream test contract]

key-files:
  created:
    - .planning/phases/24-agent-runs-short-term-memory-parity/24-09-SUMMARY.md
  modified:
    - tests/test_agent_runs_api.py
    - tests/conversation/test_service.py

key-decisions:
  - "Keep legacy /api/v1/agent/chat behavior intact; verify its successful path persists user/assistant messages and rolling summaries."
  - "Make the final three-turn smoke use the real create + SSE + finalizer memory path with a deterministic fake graph."
  - "Align stream tests with the Phase 24 create-before-stream conversation-message contract."

patterns-established:
  - "ThreeTurnMemoryGraph records prompt context, session memory, tool prompt summaries, and authority refs without live provider credentials."
  - "Agent-runs stream tests should create pending runs through POST /api/v1/agent-runs unless intentionally testing missing-message fail-closed behavior."

requirements-completed:
  - STM-08
  - STM-13
  - STM-14

duration: 42 min
completed: 2026-06-20
---

# Phase 24 Plan 09: Final Regression And Smoke Summary

**Legacy chat remains compatible while `/agent-runs + SSE` proves three-turn short-term memory continuity**

## Performance

- **Duration:** 42 min
- **Started:** 2026-06-20T15:15:00Z
- **Completed:** 2026-06-20T15:57:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Strengthened the legacy `/api/v1/agent/chat` focused test to prove successful-path user/assistant persistence, trusted conversation IDs in graph config, and rolling-summary creation.
- Completed the three-turn `/agent-runs + SSE` smoke with deterministic prompt-context loading, tool prompt summaries, trusted session-slot inheritance, explicit current-turn override, and negative authority-boundary assertions.
- Ran the final focused Phase 24 pytest gate and full `ruff check src/ tests/` gate successfully.

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify legacy chat compatibility with shared helpers** - `9241b15` (test)
2. **Task 2: Complete three-turn Agent Console smoke** - `02a8c3a` (test)
3. **Task 3: Run focused Phase 24 regression gate** - `90066a6` (test)

## Files Created/Modified

- `tests/test_agent_runs_api.py` - Adds deterministic three-turn memory graph, strengthens legacy chat assertions, and aligns stream permission test with the create contract.
- `tests/conversation/test_service.py` - Updates a prompt-context fixture to respect the one user message per run/role idempotency contract.
- `.planning/phases/24-agent-runs-short-term-memory-parity/24-09-SUMMARY.md` - Records final plan completion.

## Decisions Made

- Did not change legacy interrupted/error assistant-message behavior; Plan 24-09 only verifies the successful compatibility path.
- Did not require live model/provider credentials or browser automation for STM-14; the ASGI/SSE smoke drives backend persistence deterministically.
- Kept missing user conversation message as an explicit fail-closed stream precondition; tests that need a valid stream now create runs through the API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Conversation-service fixture violated new run-role uniqueness**
- **Found during:** Task 1 focused pytest
- **Issue:** One service test inserted two user messages for the same `(tenant_id, run_id, role)` after Phase 24 introduced run-role idempotency.
- **Fix:** Changed the second current-turn recent-message fixture from user to assistant, preserving two recent messages while respecting the run-role contract.
- **Files modified:** `tests/conversation/test_service.py`
- **Verification:** Task 1 focused pytest passed with `10 passed, 1 warning`.
- **Committed in:** `9241b15`

**2. [Rule 3 - Blocking] Stream permission test bypassed the create contract**
- **Found during:** Task 3 focused regression gate
- **Issue:** The test inserted `AgentRun` directly, so SSE correctly failed closed because no user conversation message existed.
- **Fix:** Changed the test to create the pending run through `POST /api/v1/agent-runs` before opening `/events`.
- **Files modified:** `tests/test_agent_runs_api.py`
- **Verification:** Targeted test passed, then the full focused regression gate passed with `91 passed, 9 warnings`.
- **Committed in:** `90066a6`

---

**Total deviations:** 2 auto-fixed (blocking test-contract issues)
**Impact on plan:** Both fixes aligned stale tests with Phase 24 contracts; no production behavior or out-of-scope feature was added.

## Issues Encountered

- Local validation issue #18 records the same-run duplicate user-message fixture failure.
- Local validation issue #19 records the direct-run stream permission fixture failure.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/test_agent_runs_api.py::test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions tests/conversation/test_service.py -q` - passed with `10 passed, 1 warning`.
- `uv run pytest tests/test_agent_runs_api.py::test_three_turn_agent_runs_smoke_uses_slots_and_summary_context -q` - passed with `1 passed, 1 warning`.
- `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q` - passed with `91 passed, 9 warnings`.
- `uv run ruff check src/ tests/` - passed.

## Next Phase Readiness

Phase 24 has all nine summaries and is ready for phase-level verification/closeout. The remaining work is GSD bookkeeping: advance/repair state if the known state writer regression recurs, then run the phase verification workflow.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
