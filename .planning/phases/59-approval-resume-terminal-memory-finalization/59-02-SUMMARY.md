---
phase: 59-approval-resume-terminal-memory-finalization
plan: 02
subsystem: memory
tags: [approval-resume, terminal-finalizer, session-memory, cwc, canonical-graph]

requires:
  - phase: 59-approval-resume-terminal-memory-finalization
    provides: Shared terminal finalizer helpers and idempotent finalizer trace persistence from Plan 59-01
  - phase: 57-risk-gate-and-approval-gate-canonicalization
    provides: Canonical risk_gate and approval resume semantics
  - phase: 58-canonical-graph-cutover-and-no-debt-cleanup
    provides: Final canonical graph vocabulary and historical retry compatibility scope
provides:
  - Approval-resume completed path terminal finalizer invocation
  - Requester-owned terminal memory/CWC finalization for approval resumes
  - Completed-run retry reconciliation from finalizer evidence without graph replay
  - Explicit interrupted/error no-finalizer regression coverage
affects: [phase-59, approval-resume, agent-run-memory, session-memory, case-working-context]

tech-stack:
  added: []
  patterns:
    - Approval resume finalization after durable status and trace persistence
    - Completed-run retry reconciliation guarded by agent_run_memory_finalize evidence
    - Requester identity for terminal memory surfaces, reviewer identity for trusted graph resume

key-files:
  created:
    - .planning/phases/59-approval-resume-terminal-memory-finalization/59-02-SUMMARY.md
  modified:
    - src/api/routers/approvals.py
    - tests/test_approval_api.py
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Terminal finalizer identity is fetched from persisted AgentRun.user_id; reviewer/admin actor identity remains scoped to trusted graph resume."
  - "Completed-run retry reconciliation records only the missing approval_resumed/completed event when finalizer evidence already exists."
  - "Interrupted and error approval resume paths remain explicit non-finalizer boundaries."

patterns-established:
  - "Approval resume completed branch must finalize after update_agent_run_status and post-approval append_agent_steps."
  - "Retrying a completed approval resume requires existing agent_run_memory_finalize evidence before recording completion."

requirements-completed: [MEM-01, MEM-02, MEM-03, CAGM-08, CAGM-09]

duration: 10min
completed: 2026-07-08
---

# Phase 59 Plan 02: Approval Resume Terminal Finalizer Wiring Summary

**Completed approval resumes now run the shared terminal memory finalizer with requester identity and retry-safe completion-event reconciliation.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-08T09:24:10Z
- **Completed:** 2026-07-08T09:34:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Wired `_resume_graph_after_decision(...)` to call `finalize_completed_agent_run_memory(...)` only after run status and post-approval trace rows are persisted.
- Ensured terminal memory/CWC finalization uses `requester = await session.get(User, run.user_id)`, not reviewer/admin `actor_user`.
- Added completed-run retry reconciliation that checks existing `agent_run_memory_finalize` evidence and records only the missing `approval_resumed/completed` event.
- Added regression coverage proving interrupted-again and error resume paths do not create assistant messages, thread summaries, or finalizer trace rows.

## Task Commits

1. **Task 1 RED:** `1959a12` test(59-02): add failing approval resume finalizer tests
2. **Task 1 GREEN:** `288d2a5` feat(59-02): finalize completed approval resumes
3. **Task 2:** `c54db83` test(59-02): preserve approval resume skip boundaries

## Files Created/Modified

- `src/api/routers/approvals.py` - Approval resume terminal finalizer wiring, completed-run retry evidence gate, and explicit non-completed reason boundary.
- `tests/test_approval_api.py` - Approval resume finalizer identity/retry coverage plus interrupted/error no-finalizer regressions.
- `.planning/ARCHITECTURE-DEBT.md` - Memory subsystem debt ledger entry for Phase 59-02.
- `.planning/phases/59-approval-resume-terminal-memory-finalization/59-02-SUMMARY.md` - This execution summary.

## Decisions Made

- Kept `_reconcile_approved_action_draft(...)` ordering before status update/finalizer and left its existing-draft guard unchanged.
- Used `AgentStep` finalizer evidence (`node_name == "agent_run_memory_finalize"` and `memory_write_status == "completed"`) as the only safe completed-run retry proof.
- Preserved `risk_gate` as canonical route authority and kept historical `assess_risk_and_approval` compatibility scoped to persisted retry metadata.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project Rule] Updated memory architecture debt ledger**
- **Found during:** Plan closeout
- **Issue:** MOCA project rules require memory subsystem fixes to be recorded in `.planning/ARCHITECTURE-DEBT.md`.
- **Fix:** Added a Phase 59 Plan 02 entry with root cause, impact, status, evidence, verification, and remaining risk.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Ledger entry references real commits/files/tests from this plan.
- **Committed in:** Final metadata commit

**Total deviations:** 1 auto-fixed (project-rule documentation update).  
**Impact on plan:** No behavior scope expansion; documentation follows repository hard rules for memory lifecycle fixes.

## Issues Encountered

- Intentional TDD RED failures occurred before Task 1 implementation: completed approval resumes did not call the finalizer, and completed-run retry after missing completion event rolled back to `interrupted`.
- No unexpected validation failures occurred after implementation.

## Known Stubs

None. Stub scan found only existing optional `None`/empty-list initializers and historical ledger examples; no placeholder production path or unimplemented UI/data flow was introduced.

## Threat Flags

None. New security-relevant behavior matches the plan threat model: requester identity for terminal finalization, completed-only finalizer invocation, retry evidence gating, and canonical route preservation.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_agent_run_status_updates_to_completed_after_service_resume tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_approval_resume_reconciliation_accepts_not_executed_demo_draft_outcome -q` -> `3 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_approval_resume_error_skips_terminal_finalizer_surfaces tests/test_approval_api.py::test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `34 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` -> `35 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `31 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py` -> pass

## TDD Gate Compliance

- RED gate present: `1959a12`
- GREEN gate present after RED: `288d2a5`
- Task 2 was preservation coverage after Task 1's completed-only implementation; no production refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 59-03 can perform final approval/memory regression verification, update Phase 59 validation sign-off, and close the remaining milestone-audit evidence for this gap.

## Self-Check: PASSED

- Key files exist on disk: `src/api/routers/approvals.py`, `tests/test_approval_api.py`, `.planning/ARCHITECTURE-DEBT.md`, and this SUMMARY.
- Task commits found in git log: `1959a12`, `288d2a5`, `c54db83`.

---
*Phase: 59-approval-resume-terminal-memory-finalization*
*Completed: 2026-07-08*
