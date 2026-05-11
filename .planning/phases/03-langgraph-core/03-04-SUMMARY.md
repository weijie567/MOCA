---
phase: 03-langgraph-core
plan: "04"
subsystem: agent-api
tags: [fastapi, langgraph, postgres-checkpointer, trace-persistence, oauth2-scopes]

requires:
  - phase: 03-langgraph-core
    provides: "Plan 03-03 compiled LangGraph graph, trace_steps contract, and safe node fallbacks"
  - phase: 03-langgraph-core
    provides: "Plan 03-01 AgentRun/AgentStep models and checkpointer database URL"
provides:
  - "POST /api/v1/agent/chat endpoint with agent:chat OAuth scope"
  - "AgentRun and AgentStep trace persistence helpers"
  - "FastAPI lifespan setup for AsyncPostgresSaver and compiled agent graph"
  - "Safe trace_summary response containing run_id, intent, nodes, tools, evidence count, risk, latency, and status"
affects: [03-langgraph-core, approval-workflow, frontend-chat, testing]

tech-stack:
  added: []
  patterns:
    - "FastAPI lifespan owns one AsyncPostgresSaver and compiled graph instance."
    - "Agent endpoint injects the request DB session into LangGraph configurable state for tool nodes."
    - "Checkpointer thread IDs are scoped by tenant and user while preserving the user-supplied thread_id in AgentState and trace rows."

key-files:
  created:
    - src/agent/trace.py
    - src/api/schemas/agent.py
    - src/api/routers/agent.py
  modified:
    - src/api/main.py
    - src/auth/permissions.py

key-decisions:
  - "The checkpointer thread key is tenant_id:user_id:thread_id to prevent same thread_id memory sharing across users or tenants."
  - "Graph invocation failures still attempt to persist an AgentRun error row, but trace persistence failures are rolled back and never exposed to the caller."
  - "A narrow OAuth2 model scopes alias preserves compatibility with the plan verification while keeping FastAPI's canonical password-flow scopes intact."

patterns-established:
  - "API responses expose only summarized trace fields and never raw prompts, raw tool output, stack traces, or full business context."
  - "Agent trace writes are best effort after graph execution; user-facing responses are not failed by trace database write errors."

requirements-completed: [AGNT-02, AGNT-05, AGNT-06, INFR-09, SAFE-06, SAFE-08]

duration: 5m
completed: 2026-05-11
---

# Phase 03 Plan 04: Agent API and Trace Persistence Summary

**FastAPI agent chat endpoint with LangGraph checkpointer lifespan and database-backed execution traces**

## Performance

- **Duration:** 5m
- **Started:** 2026-05-11T08:12:16Z
- **Completed:** 2026-05-11T08:16:57Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `POST /api/v1/agent/chat`, protected by the new `agent:chat` OAuth2 scope.
- Added `ChatRequest`, `ChatResponse`, and `TraceSummary` schemas for the agent API response contract.
- Added trace persistence helpers for `AgentRun` and `AgentStep`, plus a safe `build_trace_summary()` response projection.
- Registered the agent router and initialized `AsyncPostgresSaver` in FastAPI lifespan, calling `checkpointer.setup()` once at startup.
- Preserved graceful degradation: graph failures return a structured fallback response and attempt to persist an error run.

## Task Commits

Each planned task was committed atomically:

1. **Task 1: Trace persistence + API schemas + agent:chat scope** - `8f65bb8` (feat)
2. **Task 2: Agent router + FastAPI lifespan with checkpointer** - `ca1f1d1` (feat)

## Files Created/Modified

- `src/agent/trace.py` - Persists run/step trace rows and builds the public trace summary.
- `src/api/schemas/agent.py` - Defines chat request, chat response, and trace summary schemas.
- `src/api/routers/agent.py` - Implements the authenticated agent chat endpoint, graph invocation, trace writes, and fallback response path.
- `src/api/main.py` - Adds FastAPI lifespan for `AsyncPostgresSaver`, builds the graph, and registers the agent router.
- `src/auth/permissions.py` - Adds the `agent:chat` OAuth2 scope.

## Decisions Made

- Scoped the LangGraph checkpointer key by tenant and user because raw caller-provided `thread_id` is not an authorization boundary.
- Kept trace write failures best-effort: rollback the write and return the already generated agent response.
- Added a compatibility alias for `oauth2_scheme.model.scopes` because this FastAPI version stores scopes at `oauth2_scheme.model.flows.password.scopes`, while the plan verification checks the former.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... trace + schemas + scope OK"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... agent router registered OK"` - passed, with a non-failing LangGraph checkpointer deprecation warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/agent.py src/api/main.py src/agent/trace.py src/api/schemas/agent.py src/auth/permissions.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... full integration wiring OK"` - passed, with a non-failing LangGraph checkpointer deprecation warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 50 tests, 1 existing LangGraph deprecation warning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added OAuth2 scopes compatibility alias**
- **Found during:** Task 1 verification.
- **Issue:** The plan verification expected `oauth2_scheme.model.scopes`, but the installed FastAPI version exposes scopes through the password flow model.
- **Fix:** Added a narrow alias from `oauth2_scheme.model.scopes` to `oauth2_scheme.model.flows.password.scopes`.
- **Files modified:** `src/auth/permissions.py`
- **Verification:** Task 1 import/scope verification passed.
- **Committed in:** `8f65bb8`

**2. [Rule 2 - Missing Critical] Scoped checkpointer thread IDs by tenant and user**
- **Found during:** Task 2 threat model review for `ChatRequest.thread_id`.
- **Issue:** A raw caller-supplied thread ID could collide across users or tenants in the checkpointer namespace.
- **Fix:** Used `tenant_id:user_id:thread_id` for LangGraph checkpointer config while storing the original `thread_id` in state and trace rows.
- **Files modified:** `src/api/routers/agent.py`
- **Verification:** Route import check, ruff, integration wiring check, and full pytest passed.
- **Committed in:** `ca1f1d1`

**3. [Rule 2 - Missing Critical] Persisted error AgentRun rows on graph invocation failure**
- **Found during:** Task 2 implementation against the must-have that each call writes an `AgentRun`.
- **Issue:** The plan's fallback snippet returned a degraded response before writing any trace row.
- **Fix:** Added best-effort error-run persistence before returning the structured fallback response.
- **Files modified:** `src/api/routers/agent.py`
- **Verification:** Route import check, ruff, integration wiring check, and full pytest passed.
- **Committed in:** `ca1f1d1`

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 missing critical)
**Impact on plan:** All changes preserve the planned API contract while tightening verification compatibility, tenant isolation, and trace completeness.

## Issues Encountered

- Importing the LangGraph Postgres checkpointer emits a package deprecation warning about future serializer defaults. It does not fail verification.

## Known Stubs

None. Stub scan found only local empty-list initialization and optional `None` defaults; no placeholder output or mock data path was introduced.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None. New HTTP and trace surfaces are the exact surfaces covered by the plan threat model.

## Next Phase Readiness

Plan 03-05 can now test the HTTP agent path, trace row creation, same-thread memory through the scoped checkpointer key, and graph failure fallback behavior.

## Self-Check: PASSED

- Found `.planning/phases/03-langgraph-core/03-04-SUMMARY.md`.
- Found `src/agent/trace.py`.
- Found `src/api/schemas/agent.py`.
- Found `src/api/routers/agent.py`.
- Found task commit `8f65bb8`.
- Found task commit `ca1f1d1`.

---
*Phase: 03-langgraph-core*
*Completed: 2026-05-11*
