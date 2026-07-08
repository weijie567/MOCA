---
phase: 59-approval-resume-terminal-memory-finalization
plan: 03
subsystem: memory
tags: [approval-resume, terminal-finalizer, session-memory, cwc, validation, canonical-graph]

requires:
  - phase: 59-approval-resume-terminal-memory-finalization
    provides: Shared terminal finalizer utilities from 59-01 and approval-resume wiring from 59-02
  - phase: 58-canonical-graph-cutover-and-no-debt-cleanup
    provides: Final canonical graph vocabulary and approval/action boundary guardrails
provides:
  - Approval-resume completed terminal finalizer regression coverage
  - Interrupted-again no-terminal-memory regression coverage
  - Completed-run retry/dedupe regression coverage after terminal finalizer surfaces
  - Direct memory_write approval-marker skip guard
  - Phase 59 validation sign-off and Memory architecture-debt closure entry
affects: [phase-59, phase-60, approval-resume, agent-run-memory, session-memory, case-working-context]

tech-stack:
  added: []
  patterns:
    - Real DB surface assertions for terminal memory finalizer regression tests
    - Diff-scoped validation for no new bare pytest command text

key-files:
  created:
    - .planning/phases/59-approval-resume-terminal-memory-finalization/59-03-SUMMARY.md
  modified:
    - tests/test_approval_api.py
    - tests/agent/test_memory_write_node.py
    - .planning/phases/59-approval-resume-terminal-memory-finalization/59-VALIDATION.md
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Used real terminal memory_write in approval-resume regression tests to prove durable session-memory MemoryWriteEvent rows."
  - "Verified requester ownership through ConversationThread.user_id because ConversationMessage does not carry a user_id column."
  - "Kept src/agent/nodes/memory_write.py without terminal-finalizer bypass flags; direct approval-marked states still skip."

patterns-established:
  - "Approval-resume retry tests should inject failure after terminal finalizer surfaces, then assert graph/action/finalizer side effects are not rerun."
  - "Validation artifacts should record exact UV_CACHE_DIR=/tmp/uv-cache uv run commands only after final verification passes."

requirements-completed: [MEM-01, MEM-02, MEM-03, CAGM-08, CAGM-09]

duration: 17min
completed: 2026-07-08
---

# Phase 59 Plan 03: Approval Resume Terminal Finalizer Regression Summary

**Regression and validation evidence now proves approval-resume completed runs finalize terminal memory surfaces, interrupted paths skip them, and retries do not duplicate side effects.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-08T09:39:18Z
- **Completed:** 2026-07-08T09:56:24Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added approval-resume completed-path regression assertions for one assistant message, one thread summary, one session-memory `MemoryWriteEvent`, one `agent_run_memory_finalize` step, completed memory status, non-`not_completed_path` reason, and CWC metrics.
- Strengthened interrupted-again and retry/dedupe coverage so no terminal memory/finalizer surfaces are written for interrupted paths and completed-run retry reconciliation does not rerun graph/action side effects or duplicate surfaces.
- Locked direct `memory_write(...)` approval-marker behavior so approval-marked direct states still skip as `not_completed_path`.
- Marked Phase 59 validation complete and recorded final uv pytest / ruff evidence plus Memory architecture-debt closure and local validation incident entries.

## Task Commits

1. **Task 1: Add approval-resume terminal finalizer regressions** - `748c040` (test)
2. **Task 2: Guard direct memory_write approval skips and canonical graph boundaries** - `ba484cd` (test)
3. **Task 3: Final validation artifact, mandatory architecture-debt entry, and conditional local issue ledger** - `a9533a7` (docs)

## Files Created/Modified

- `tests/test_approval_api.py` - Approval-resume completed/interrupted/retry terminal finalizer regressions with concrete DB surface assertions.
- `tests/agent/test_memory_write_node.py` - Direct approval-marked `memory_write(...)` skip regression with explicit approved marker payload.
- `.planning/phases/59-approval-resume-terminal-memory-finalization/59-VALIDATION.md` - Phase 59 validation sign-off and final command evidence.
- `.planning/ARCHITECTURE-DEBT.md` - Memory-section Phase 59 Plan 03 lifecycle closure entry.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Local validation incident for the initial `ConversationMessage.user_id` test assumption.

## Decisions Made

- Used real session-memory persistence in approval-resume tests instead of the fake memory writer when asserting `MemoryWriteEvent`, because the requirement is durable event evidence.
- Verified finalizer message requester ownership through `ConversationThread.user_id`; the message row itself has no `user_id` field.
- Treated full-file bare command grep hits in `LOCAL-VALIDATION-ISSUES.md` as historical text outside this plan, and verified the current diff adds no bare `pytest` or `python -m pytest` commands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Fixed assistant-message requester assertion**
- **Found during:** Task 1 RED verification
- **Issue:** The new completed-path regression asserted `ConversationMessage.user_id`, but `ConversationMessage` has no such column.
- **Fix:** Loaded `ConversationThread` through `assistant_message.conversation_thread_id` and asserted `ConversationThread.user_id == AgentRun.user_id`.
- **Files modified:** `tests/test_approval_api.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Focused command rerun returned `3 passed, 1 warning`; full approval API command returned `35 passed, 1 warning`.
- **Committed in:** `748c040` for test fix; `a9533a7` for local validation incident log.

**Total deviations:** 1 auto-fixed (1 test bug).  
**Impact on plan:** No production behavior scope change. The fix aligns the test with the real conversation schema.

## Issues Encountered

- Task 1 initial focused run failed on a test-only schema assumption; documented in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Task 2's RED-style focused test passed immediately because 59-01 had already preserved the direct approval-marker skip behavior. No production implementation was needed.
- The full-document bare-command grep matched historical text in `.planning/LOCAL-VALIDATION-ISSUES.md`; a diff-scoped grep confirmed this plan added no new bare test commands.

## Known Stubs

None. Stub scan found only historical local-validation example snippets outside the current diff; no new placeholder code, mock-only data path, or unimplemented production surface was introduced.

## Threat Flags

None. This plan added tests and planning evidence only; no new network endpoint, auth path, file access pattern, schema boundary, or production trust boundary was introduced.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` -> `35 passed, 1 warning in 88.44s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_skips_non_completed_status tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` -> `4 passed, 1 warning in 11.41s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py -q` -> `57 passed, 1 warning in 27.78s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `31 passed, 1 warning in 1.69s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `193 passed, 1 warning in 239.08s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` -> pass

## TDD Gate Compliance

- Task 1 produced a failing focused run before test correction, but the failure was a test schema assumption rather than missing production behavior.
- Task 2's focused RED check passed immediately because the direct approval-marker skip behavior already existed from 59-01.
- No production GREEN commit was required in this plan; commits are test/docs only by plan design.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 59 is validated and ready for Phase 60 archive evidence closure. The approval-resume terminal finalizer gap is covered by regression tests, validation sign-off, and Memory architecture-debt ledger evidence.

## Self-Check: PASSED

- Key files exist on disk: `tests/test_approval_api.py`, `tests/agent/test_memory_write_node.py`, and this SUMMARY.
- Task commits found in git log: `748c040`, `ba484cd`, `a9533a7`.
- No file deletions were introduced by task commits.

---
*Phase: 59-approval-resume-terminal-memory-finalization*
*Completed: 2026-07-08*
