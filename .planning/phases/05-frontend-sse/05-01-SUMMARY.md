---
phase: 05-frontend-sse
plan: 01
subsystem: api
tags: [fastapi, sse, langgraph, approvals, rbac]

requires:
  - phase: 03-langgraph-core
    provides: LangGraph agent graph, trace persistence helpers, and agent run tables
  - phase: 04-approval-workflow-audit
    provides: Approval interrupt handling, approval repository, and trace replay API
provides:
  - Run-based backend API for creating agent runs and streaming LangGraph progress over SSE
  - Status and evidence endpoints for frontend recovery and detail panels
  - sse-starlette dependency locked for EventSourceResponse support
affects: [frontend-sse, agent-runs, approvals, traces]

tech-stack:
  added: [sse-starlette]
  patterns:
    - FastAPI EventSourceResponse streaming from LangGraph astream updates
    - Tenant-scoped run access with owner-or-supervisor authorization
    - Existing AgentRun row updated during SSE lifecycle instead of reinserted

key-files:
  created:
    - src/api/schemas/agent_runs.py
    - src/api/routers/agent_runs.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/api/main.py

key-decisions:
  - "SSE execution updates the pending AgentRun row created by POST /agent-runs, avoiding duplicate primary-key inserts."
  - "The new router shares the existing /api/v1/agent-runs prefix with the trace router."
  - "uv.lock was refreshed because uv resolved the newly declared sse-starlette dependency during verification."

patterns-established:
  - "Run API endpoints use Security(get_current_user, scopes=[\"agent:chat\"]) and TraceRepository tenant filtering."
  - "SSE events carry a stable JSON data envelope with event_type, run_id, step_index, node_name, status, message, timestamp, and payload."

requirements-completed: [AGNT-07]

duration: 8min
completed: 2026-05-17
---

# Phase 05 Plan 01: Backend SSE Run API Summary

**Run-based FastAPI SSE API for streaming LangGraph node progress, approval interrupts, run status, and evidence references**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-17T08:07:32Z
- **Completed:** 2026-05-17T08:15:09Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `POST /api/v1/agent-runs`, `GET /api/v1/agent-runs/{run_id}`, `GET /api/v1/agent-runs/{run_id}/events`, and `GET /api/v1/agent-runs/{run_id}/evidence`.
- Added run request/status/SSE payload schemas and registered the new router in FastAPI.
- Streamed LangGraph `astream(..., stream_mode="updates")` progress as SSE data events, including `approval_required` handling.
- Preserved tenant isolation and owner-or-supervisor run access checks on all new endpoints.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sse-starlette dependency and schemas** - `198c7ad` (feat)
2. **Task 2: Implement agent_runs router** - `c40d014` (feat)
3. **Task 3: Register agent_runs router in main.py** - `a5c80b6` (feat)

## Files Created/Modified

- `src/api/schemas/agent_runs.py` - Defines `CreateRunRequest`, `RunStatusResponse`, and `SseEventPayload`.
- `src/api/routers/agent_runs.py` - Adds run creation, status, SSE event streaming, and evidence endpoints.
- `src/api/main.py` - Registers the new router on `/api/v1/agent-runs`.
- `pyproject.toml` - Declares `sse-starlette>=1.6`.
- `uv.lock` - Locks resolved `sse-starlette` package metadata.

## Decisions Made

- Updated existing pending `AgentRun` rows during SSE execution rather than calling `write_agent_run()` a second time for the same `run_id`.
- Normalized LangGraph stream items defensively so both tuple-style and dict-style `astream` updates can be handled.
- Kept SSE payloads lightweight: evidence counts, risk levels, summaries, approval metadata, final response, and error messages only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Avoided duplicate AgentRun insert during SSE completion**
- **Found during:** Task 2 (Implement agent_runs router)
- **Issue:** The plan reused `write_agent_run()` after POST had already inserted a pending row. That helper inserts a new row and would collide on the existing `run_id`.
- **Fix:** The SSE lifecycle now updates the existing `AgentRun` object for `running`, terminal, interrupted, and error states while still using `write_agent_steps()` for trace steps.
- **Files modified:** `src/api/routers/agent_runs.py`
- **Verification:** Router import passed, route count was 4, ruff passed, and full pytest passed.
- **Committed in:** `c40d014`

**2. [Rule 3 - Blocking] Refreshed uv.lock for the new dependency**
- **Found during:** Task 1 (Add sse-starlette dependency and schemas)
- **Issue:** `uv run` needed to resolve/download `sse-starlette` before imports involving `EventSourceResponse` could pass.
- **Fix:** Allowed uv to refresh `uv.lock` while installing the declared dependency.
- **Files modified:** `uv.lock`
- **Verification:** Schema import passed after dependency resolution.
- **Committed in:** `198c7ad`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking issue)
**Impact on plan:** Both changes were required for a working dependency install and correct run persistence. API scope stayed within the backend SSE plan.

## Issues Encountered

- Initial dependency verification failed under sandboxed network restrictions with `Operation not permitted` while fetching from PyPI. Reran the same schema import verification with approved network access; it passed.
- Task 1 was marked `tdd="true"`, but the plan and user constraints scoped ownership to backend implementation files only. No separate test file was added; behavior was verified through imports, route checks, ruff, and the full existing test suite.

## Verification

| Command | Result |
| --- | --- |
| `grep "sse-starlette" pyproject.toml` | PASS - matched `sse-starlette>=1.6` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.api.schemas.agent_runs import CreateRunRequest, RunStatusResponse, SseEventPayload; ..."` | PASS - imports succeeded and listed `/api/v1/agent-runs` routes |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/schemas/agent_runs.py src/api/routers/agent_runs.py src/api/main.py` | PASS |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | PASS - 166 passed, 1 LangGraph deprecation warning |

## Known Stubs

None. Optional `None` defaults and local empty accumulators in the new code are schema defaults or runtime collection state, not unwired UI or data-source stubs.

## Threat Flags

None. New security-relevant surfaces match the plan threat model: all new endpoints use `Security(get_current_user, scopes=["agent:chat"])`, tenant-scoped run lookup, and owner-or-supervisor authorization.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The frontend can now create a run, connect to `/events` with a Bearer token, render streamed execution events, recover status from `GET /agent-runs/{run_id}`, and load run evidence from `GET /agent-runs/{run_id}/evidence`.

## Self-Check: PASSED

- Created files exist: `src/api/schemas/agent_runs.py`, `src/api/routers/agent_runs.py`, `.planning/phases/05-frontend-sse/05-01-SUMMARY.md`.
- Task commits exist: `198c7ad`, `c40d014`, `a5c80b6`.
- Shared tracking files were not updated by this executor; `.planning/STATE.md` remained an unrelated pre-existing modification.

---
*Phase: 05-frontend-sse*
*Completed: 2026-05-17*
