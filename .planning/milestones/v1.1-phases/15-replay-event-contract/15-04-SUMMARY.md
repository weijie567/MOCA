---
phase: 15-replay-event-contract
plan: 04
subsystem: replay
tags: [replay, lifecycle, approval, sse, pytest]

requires:
  - phase: 15-02
    provides: ReplayService append/projection boundary and shared sequence allocator
  - phase: 15-03
    provides: operation pairing validation for ReplayEventV3
provides:
  - RunLifecycleService finalizer for run_status_changed replay events
  - Lifecycle-aware AgentRun trace persistence helpers
  - SSE/chat/approval resume and needs-info lifecycle event wiring
  - Lifecycle writer allocator coverage
  - SLA scanner disabled-by-default verification
affects: [15-05-replay-api, 15-06-replay-safety, post-Phase-15-SLA-scanner-enablement]

tech-stack:
  added: []
  patterns:
    - RunLifecycleService appends lifecycle replay events through ReplayService
    - AgentRun remains the durable run-status truth while replay records append-only lifecycle facts
    - Needs-info respond emits a same-status interrupted lifecycle event without fabricated completion

key-files:
  created:
    - src/replay/lifecycle.py
    - tests/replay/test_lifecycle_finalizer.py
  modified:
    - src/replay/__init__.py
    - src/agent/trace.py
    - src/api/routers/agent.py
    - src/api/routers/agent_runs.py
    - src/api/routers/approvals.py
    - src/approvals/service.py
    - tests/replay/test_sequence_allocator.py
    - tests/replay/test_replay_service.py
    - tests/test_agent_runs_api.py
    - tests/approvals/test_needs_info_resume.py

key-decisions:
  - "RunLifecycleService owns run_status_changed replay event appends; AgentRun remains the durable run-status source of truth."
  - "Approval respond/needs-info appends interrupted with reason_code=needs_info_response and never emits completed."
  - "ApprovalSlaScanner remains disabled by default; active enablement stays deferred to post-Phase 15 SLA Scanner Enablement."

patterns-established:
  - "Lifecycle-aware status updates flow through src.agent.trace.write_agent_run() and update_agent_run_status()."
  - "Lifecycle writer participates in the same ReplayService allocator as graph, memory_write, approval, action draft, and replay/backfill writers."

requirements-completed: [REPLAY-01, REPLAY-02]

duration: 22 min
completed: 2026-06-16
---

# Phase 15 Plan 04: Run Lifecycle Finalizer Summary

**RunLifecycleService-backed lifecycle replay events across normal, interrupted, resumed, needs-info, terminal, error, and cancelled run paths**

## Performance

- **Duration:** 22 min
- **Started:** 2026-06-16T14:48:28Z
- **Completed:** 2026-06-16T15:10:42Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Added `RunLifecycleService` with running, interrupted, resumed, completed, rejected, expired, error, and cancelled lifecycle event methods.
- Routed `write_agent_run()` and `update_agent_run_status()` through lifecycle replay events while keeping `AgentRun.final_status` as the durable status truth.
- Wired chat, SSE, approval resume, and approval respond/needs-info flows to append lifecycle status changes without fabricating completed status.
- Completed lifecycle writer allocator coverage and verified the SLA scanner still defaults disabled.

## Task Commits

1. **Task 1 RED: lifecycle matrix tests** - `b58460b` (test)
2. **Task 1 GREEN: RunLifecycleService** - `a421897` (feat)
3. **Task 2 RED: lifecycle wiring tests** - `10fe128` (test)
4. **Task 2 GREEN: trace/API/approval wiring** - `263a021` (feat)
5. **Task 3: SLA scanner disabled verification** - `1638438` (chore, empty verification commit)

## Files Created/Modified

- `src/replay/lifecycle.py` - New lifecycle finalizer service appending `run_status_changed` through `ReplayService`.
- `src/replay/__init__.py` - Exports `RunLifecycleService`.
- `src/agent/trace.py` - Adds lifecycle-aware `write_agent_run()` and `update_agent_run_status()` status event appends.
- `src/api/routers/agent.py` - Passes trace context into lifecycle-aware run persistence.
- `src/api/routers/agent_runs.py` - Uses lifecycle-aware status helper for SSE claim, completion, interruption, and error paths.
- `src/api/routers/approvals.py` - Passes approval resume trace context into lifecycle-aware status update.
- `src/approvals/service.py` - Emits needs-info respond lifecycle event as interrupted with clarification ref.
- `tests/replay/test_lifecycle_finalizer.py` - Lifecycle matrix and trace-helper contract tests.
- `tests/replay/test_sequence_allocator.py` - Adds lifecycle/finalizer writer allocator coverage.
- `tests/replay/test_replay_service.py` - Adjusts sequence fixtures for initial lifecycle running event and keeps deferred external execution negative coverage.
- `tests/test_agent_runs_api.py` - SSE lifecycle event assertions for completed, interrupted, and error timelines.
- `tests/approvals/test_needs_info_resume.py` - Needs-info respond lifecycle assertions.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py -q --tb=short` - PASS, 8 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/lifecycle.py tests/replay/test_lifecycle_finalizer.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py tests/replay/test_sequence_allocator.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py -q --tb=short` - PASS, 46 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_sla_scanner.py -q --tb=short` - PASS, 8 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py tests/replay/test_sequence_allocator.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py -q --tb=short` - PASS, 54 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay src/agent/trace.py src/api/routers/agent.py src/api/routers/agent_runs.py src/api/routers/approvals.py src/approvals tests/replay tests/approvals tests/test_agent_runs_api.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay -q --tb=short` - PASS, 36 passed.

## Decisions Made

- Kept lifecycle replay append-only: `RunLifecycleService` records status facts in `agent_trace_events`; it does not become a second business status store.
- Used `reason_code=needs_info_response` and `clarification_ref` for approval respond so the run remains interrupted and replayable.
- Kept active SLA scanning disabled in Phase 15; this plan verifies the gate but does not enable scanner scheduling.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated replay service sequence fixtures for lifecycle running events**
- **Found during:** Task 2 (trace/API/approval wiring)
- **Issue:** Existing replay-service and allocator tests assumed a run created with `final_status="running"` had no lifecycle event at sequence 1. After wiring `write_agent_run()` correctly, sequence 1 is now the `run_status_changed: running` event.
- **Fix:** Updated affected test expectations and legacy manual-row fixture sequences to account for the initial running event. Kept deferred external execution negative coverage without adding `action_execution_*` production behavior.
- **Files modified:** `tests/replay/test_replay_service.py`, `tests/replay/test_sequence_allocator.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay -q --tb=short` passed.
- **Committed in:** `263a021`

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** No scope expansion. The fixture updates align prior tests with the lifecycle event behavior required by this plan.

## Issues Encountered

- Running multiple DB-backed pytest commands in parallel caused a PostgreSQL schema setup race (`pg_type_typname_nsp_index` on `tenants`). Sequential reruns passed.
- The plan acceptance grep for `compensation` still matches pre-existing intent/prompt/action-draft source text in `src/agent`; a diff-scoped guard confirmed this plan added no deferred execution/outbox/reconciliation/compensation production behavior.

## Known Stubs

None. Stub scan found only normal optional defaults, empty test collections, and explicit no-row assertions.

## Threat Flags

None. The new lifecycle replay write surface is the planned mitigation for the lifecycle threat model, and no new network endpoint, auth path, file access pattern, schema change, or external execution surface was introduced.

## TDD Gate Compliance

- RED and GREEN commits are present for Task 1 and Task 2.
- Task 3 required no code changes because disabled-by-default SLA scanner behavior was already covered; an empty verification commit records the task outcome.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 15-05. Lifecycle events now exist in the replay event store for normal, interrupted, responded, resumed, terminal, and error paths; `/replay` can read these V3 lifecycle facts without relying only on legacy trace composition.

## Self-Check: PASSED

- Verified key files exist on disk.
- Verified task commit hashes exist in git history.
- No missing summary claims found.

---
*Phase: 15-replay-event-contract*
*Completed: 2026-06-16*
