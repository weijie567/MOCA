---
phase: 14-demo-action-executor-boundary
plan: 05
subsystem: actions-trace
tags: [action-draft, trace-events, fastapi, sqlalchemy, pytest]

requires:
  - phase: 13-approval-state-machine
    provides: ActionSafetySnapshot and approval hash binding consumed by demo drafts
  - phase: 14-demo-action-executor-boundary
    provides: action_draft node, durable draft_outcome persistence, and tool path from plans 14-01 through 14-03
provides:
  - action_draft_created minimal event registration and emission with safe refs only
  - ToolCallContext thread_id and trace_id passthrough to ActionService draft creation
  - /trace action_drafts and timeline draft detail projection with draft_outcome and no raw ActionDraft.payload
affects: [phase-14-final-boundary-audit, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - Minimal AgentTraceEvent emission from the action service after new draft creation
    - Safe trace read projection helpers for draft_outcome without raw payload

key-files:
  created:
    - .planning/phases/14-demo-action-executor-boundary/14-05-SUMMARY.md
  modified:
    - src/agent/events.py
    - src/actions/service.py
    - src/tools/executors/action.py
    - src/api/routers/traces.py
    - src/repositories/trace_repo.py
    - tests/agent/test_events.py
    - tests/agent/test_tools/test_create_coupon_grant_draft.py
    - tests/test_trace_api.py

key-decisions:
  - "action_draft_created is a Phase 14 minimal event only; no action_execution_* event types were registered."
  - "ActionService emits action_draft_created only for newly created draft rows, preventing duplicate events on idempotent reuse."
  - "/trace exposes draft_outcome through the existing compatibility read model; Phase 15 still owns ReplayEventV3 and event-store-first reads."

patterns-established:
  - "Safe action draft event refs: draft_id, target_id, action_payload_hash, safety_snapshot_hash."
  - "Trace draft projection includes draft_outcome while excluding raw ActionDraft.payload."

requirements-completed: [DEMO-01, DEMO-02]

duration: 25 min
completed: 2026-06-16
---

# Phase 14 Plan 05: Safe Draft Event and Trace Projection Summary

**Minimal action draft trace events now expose safe draft refs and /trace read models expose draft_outcome without raw action payloads.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-16T01:22:38Z
- **Completed:** 2026-06-16T01:47:16Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Registered `action_draft_created` as a minimal event with `minimal_event` retention classification.
- Emitted `action_draft_created` after new draft creation with only safe refs and safe demo metadata.
- Passed `thread_id` and `trace_id` from `ToolCallContext` through `ActionToolExecutor` to `ActionService`.
- Extended `/trace` action draft summaries and timeline action draft details with `draft_outcome`.
- Added tests proving raw draft payloads and `action_execution_*` demo events are absent from this surface.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Safe draft event tests** - `cdf3d61` (test)
2. **Task 1 GREEN: Safe draft event implementation** - `eb02276` (feat)
3. **Task 2 RED: Trace draft_outcome projection tests** - `dd0d42a` (test)
4. **Task 2 GREEN: Trace draft_outcome projection implementation** - `7202797` (feat)

**Plan metadata:** committed separately after this summary.

## Files Created/Modified

- `src/agent/events.py` - Registers `action_draft_created`.
- `src/actions/service.py` - Emits safe action draft events after newly created draft rows.
- `src/tools/executors/action.py` - Passes thread and trace context into draft creation.
- `src/api/routers/traces.py` - Adds `draft_outcome` to `/trace` action draft summaries.
- `src/repositories/trace_repo.py` - Adds safe `draft_outcome` timeline projection.
- `tests/agent/test_events.py` - Covers event registration, retention, redaction, and no demo execution events.
- `tests/agent/test_tools/test_create_coupon_grant_draft.py` - Covers safe event emission through the action executor.
- `tests/test_trace_api.py` - Covers `/trace` and timeline `draft_outcome` projection without raw payload.

## Decisions Made

- Used the existing Phase 10 `emit_event` helper and per-run sequence allocator instead of introducing a Phase 15 replay service.
- Kept raw `ActionDraft.payload` out of both the event envelope and `/trace` read model.
- Returned an empty safe projection for legacy drafts with no `draft_outcome`, preserving compatibility without inventing replay data.

## TDD Gate Compliance

- **RED gates:** `cdf3d61`, `dd0d42a`
- **GREEN gates:** `eb02276`, `7202797`
- **REFACTOR gate:** Not needed; no cleanup-only changes were required after GREEN.
- **Status:** Passed.

## Verification

Passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/test_trace_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/events.py src/actions/service.py src/tools/executors/action.py src/api/routers/traces.py src/repositories/trace_repo.py tests/agent/test_events.py tests/test_trace_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py
```

Additional acceptance checks passed:

```bash
rg -n "action_draft_created|draft_id|target_id|action_payload_hash|safety_snapshot_hash|external_side_effect" src/agent/events.py src/actions/service.py src/tools/executors/action.py tests/agent/test_events.py tests/agent/test_tools/test_create_coupon_grant_draft.py
rg -n "raw_payload|raw_args|arguments|payload" tests/agent/test_events.py
rg -n "action_execution_" src/agent/events.py src/actions/service.py tests/agent/test_events.py
rg -n "draft_outcome" src/api/routers/traces.py src/repositories/trace_repo.py tests/test_trace_api.py
rg -n "\"payload\"|payload\\]" src/api/routers/traces.py src/repositories/trace_repo.py
```

The final payload projection grep returned no matches in trace router/repository source.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first fresh-worktree pytest run fell through to a system Python 3.9 pytest because the `dev` extra had not been installed. Running `uv run --extra dev ...` installed the dev tools; the plan's exact `uv run pytest ...` command passed afterward.
- One Task 1 retry hit a transient PostgreSQL deadlock while another parallel executor was using the shared test database. Retrying the same command passed; no code change was needed.

## Known Stubs

None. Stub scan hits were type-defaults or tests expecting empty lists on empty trace runs, not UI/data-flow stubs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 14-05 is ready for Phase 14 final boundary coverage in 14-06. Phase 15 replay work can consume the new `action_draft_created` minimal event and the existing `/trace` compatibility projection without treating it as a ReplayEventV3 read switch.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/14-demo-action-executor-boundary/14-05-SUMMARY.md`.
- Key source/test files exist.
- Task commits found: `cdf3d61`, `eb02276`, `dd0d42a`, `7202797`.
- `.planning/STATE.md` and `.planning/ROADMAP.md` have no modifications in this worktree.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
