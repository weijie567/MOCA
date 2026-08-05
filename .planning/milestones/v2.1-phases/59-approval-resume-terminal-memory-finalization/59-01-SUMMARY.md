---
phase: 59-approval-resume-terminal-memory-finalization
plan: 01
subsystem: memory
tags: [agent-runs, approval-resume, terminal-finalizer, session-memory, cwc, trace]

requires:
  - phase: 45-memory-lifecycle-wiring-for-case-working-context
    provides: Terminal assistant-message, thread-summary, session memory, and CWC finalizer lifecycle
  - phase: 57-risk-gate-and-approval-gate-canonicalization
    provides: Canonical approval/risk separation and approval resume state machine
  - phase: 58-canonical-graph-cutover-and-no-debt-cleanup
    provides: Final canonical graph vocabulary and no active legacy graph aliases
provides:
  - Shared requester finalizer input-state builder
  - Terminal-only approval marker sanitizer for memory_write state
  - Idempotent shared agent_run_memory_finalize trace persistence helper
  - Normal agent-runs completion migrated to shared finalizer trace helper
affects: [phase-59, approval-resume, agent-run-memory, session-memory, case-working-context]

tech-stack:
  added: []
  patterns:
    - TDD RED/GREEN commits per task
    - Service-owned finalizer trace persistence with AgentStep duplicate guard
    - Terminal finalizer state sanitization without changing graph-node approval skip policy

key-files:
  created:
    - .planning/phases/59-approval-resume-terminal-memory-finalization/59-01-SUMMARY.md
  modified:
    - src/api/services/agent_run_memory.py
    - src/api/routers/agent_runs.py
    - tests/test_agent_runs_api.py
    - tests/agent/test_memory_write_node.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Kept src/agent/nodes/memory_write.py approval/interrupted skip predicate unchanged."
  - "Sanitized approval gating markers only inside completed terminal finalizer memory_write state."
  - "Moved finalizer trace persistence into agent_run_memory service with an AgentStep FINALIZER_NODE duplicate guard."

patterns-established:
  - "Approval-resume finalization should construct memory identity from persisted AgentRun + requester User."
  - "Retry-safe finalizer trace persistence checks existing agent_run_memory_finalize rows before appending."

requirements-completed: [MEM-01, MEM-02, MEM-03]

duration: 8min
completed: 2026-07-08
---

# Phase 59 Plan 01: Terminal Finalizer Shared Seam Summary

**Shared terminal memory finalizer utilities with approval-marker sanitization and idempotent finalizer trace persistence.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-08T09:10:44Z
- **Completed:** 2026-07-08T09:18:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `build_agent_run_finalizer_input_state(...)` so approval-resume can later finalize memory under the original run requester identity.
- Added terminal-only approval marker sanitization before `memory_write(...)`, while leaving pending/interrupted approval skips intact in `memory_write.py`.
- Added `persist_agent_run_memory_finalize_trace_steps(...)` with an `AgentStep` duplicate guard and migrated normal `agent-runs` completion to it.
- Added focused RED/GREEN coverage for requester identity, approval marker handling, direct memory-write skips, finalizer trace idempotency, and rollback suppression.

## Task Commits

1. **Task 1 RED:** `98a2482` test(59-01): add failing tests for terminal finalizer memory state
2. **Task 1 GREEN:** `d2edef0` feat(59-01): add terminal finalizer memory state utilities
3. **Task 2 RED:** `4e034ba` test(59-01): add failing tests for idempotent finalizer traces
4. **Task 2 GREEN:** `b22dd5e` feat(59-01): make finalizer trace persistence idempotent

## Files Created/Modified

- `src/api/services/agent_run_memory.py` - Shared input-state builder, terminal memory sanitizer, and idempotent finalizer trace persistence helper.
- `src/api/routers/agent_runs.py` - Normal completion paths now call the shared finalizer trace persistence helper.
- `tests/test_agent_runs_api.py` - TDD coverage for finalizer input identity, sanitizer behavior, trace idempotency, and rollback suppression.
- `tests/agent/test_memory_write_node.py` - Explicit coverage that direct approval-marked memory_write calls still skip as `not_completed_path`.
- `.planning/ARCHITECTURE-DEBT.md` - Memory subsystem debt ledger entry for Phase 59-01.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Local validation incident for the rollback test MissingGreenlet issue.

## Decisions Made

- Used a service-local sanitizer instead of changing `memory_write._approval_or_interrupted(...)`, preserving the global approval/interrupted skip boundary.
- Left CWC finalization on the unsanitized `final_state`, preserving approval/action context for terminal projection.
- Kept finalizer trace idempotency in the shared memory service rather than retaining a router-private helper.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Cached run_id before rollback assertions**
- **Found during:** Task 2 GREEN verification
- **Issue:** The rollback suppression test read `run.id` after helper rollback, causing SQLAlchemy expired-attribute async IO and `MissingGreenlet`.
- **Fix:** Cached `run_id = run.id` before commit/rollback and used the cached UUID in assertions.
- **Files modified:** `tests/test_agent_runs_api.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure -q` -> `2 passed, 1 warning`
- **Committed in:** `b22dd5e`

**2. [Rule 2 - Project Hard Rule] Recorded memory subsystem debt and local validation incident**
- **Found during:** Task 2 closeout
- **Issue:** `AGENTS.md`/`CLAUDE.md` require memory subsystem architecture fixes and local validation failures to be recorded in project ledgers.
- **Fix:** Added Phase 59-01 memory debt entry and MissingGreenlet validation incident.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Ledger entries were added with evidence, commands, status, and remaining risk.
- **Committed in:** `b22dd5e` for local validation issue; architecture debt entry pending final metadata commit.

**Total deviations:** 2 auto-fixed (1 test bug, 1 project-rule documentation update).  
**Impact on plan:** No behavior scope expansion. The added documentation follows project hard rules for memory subsystem work.

## Issues Encountered

- Intentional TDD RED failures occurred before implementation and were committed as RED gate commits.
- Task 2 initially failed on a test-only `MissingGreenlet` caused by reading expired ORM state after rollback; fixed by caching the primary key before rollback.

## Known Stubs

None. Stub scan found only existing optional `None`/empty-list initializers and test fakes; no new placeholder UI/data flow or unimplemented production path was introduced.

## Threat Flags

None. New security-relevant surfaces match the plan threat model: terminal memory-write sanitization, requester identity construction, and `AgentStep` finalizer trace duplicate guard.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_build_agent_run_finalizer_input_state_uses_requester_identity tests/test_agent_runs_api.py::test_terminal_memory_write_state_strips_only_terminal_approval_markers tests/test_agent_runs_api.py::test_terminal_memory_write_applies_approval_marker_sanitizer tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure tests/agent/test_memory_write_node.py::test_memory_write_node_skips_pending_approval_markers -q` -> `8 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/agent/test_memory_write_node.py::test_memory_write_node_skips_when_final_response_missing -q` -> `3 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context -q` -> `3 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/agent/test_memory_write_node.py::test_memory_write_node_skips_when_final_response_missing -q` -> `4 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py` -> pass

## TDD Gate Compliance

- RED gate present: `98a2482`, `4e034ba`
- GREEN gate present after RED: `d2edef0`, `b22dd5e`
- REFACTOR gate: not needed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 59-02 can wire approval-resume completed paths through `build_agent_run_finalizer_input_state(...)`, `finalize_completed_agent_run_memory(...)`, and `persist_agent_run_memory_finalize_trace_steps(...)`. The finalizer helper is retry-safe for normal agent-run completion and preserves the global approval skip boundary.

## Self-Check: PASSED

- Key files exist on disk.
- Task commits found in git log: `98a2482`, `d2edef0`, `4e034ba`, `b22dd5e`.

---
*Phase: 59-approval-resume-terminal-memory-finalization*
*Completed: 2026-07-08*
