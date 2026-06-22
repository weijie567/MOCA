---
phase: 27-trustedcontextfactory-and-projections
plan: 27-03
subsystem: api
tags: [trusted-context, projections, graph, knowledge, approvals, fastapi, langgraph]

requires:
  - phase: 27-02
    provides: TrustedContextFactory, TrustedContext, and service projection helpers
provides:
  - Route seams build canonical TrustedContext from authenticated/server inputs
  - Graph nodes consume trusted_context through tool-context projection
  - KnowledgeToolExecutor uses centralized ToolCallContext to KnowledgeContext projection
  - Approval resume config remains compatible with action_draft trusted_context requirements
affects: [phase-28-policy, phase-29-tools, phase-31-memory, phase-34-approval-action, replay]

tech-stack:
  added: []
  patterns:
    - TrustedContextFactory at API/auth/run boundaries
    - project_to_tool_context for graph-node tool execution
    - project_tool_context_to_knowledge_context for knowledge executor calls
    - compatibility graph config fields derived from canonical trusted_context

key-files:
  created:
    - .planning/phases/27-trustedcontextfactory-and-projections/27-03-SUMMARY.md
  modified:
    - src/api/routers/search.py
    - src/api/routers/agent.py
    - src/api/routers/agent_runs.py
    - src/api/routers/approvals.py
    - src/platform/trusted_context.py
    - src/agent/nodes/investigate.py
    - src/agent/nodes/action_draft.py
    - src/tools/executors/knowledge.py
    - tests/architecture/test_trusted_context_boundaries.py
    - tests/test_search_integration.py
    - tests/test_agent_runs_api.py
    - tests/test_approval_api.py
    - tests/test_execute_action.py
    - tests/platform/test_trusted_context_factory.py
    - tests/agent/test_nodes/test_investigate.py
    - .planning/phases/27-trustedcontextfactory-and-projections/27-03-PLAN.md

key-decisions:
  - "Graph config keeps legacy permissions, merchant_scope, trace_id, and session_id only as values derived from canonical trusted_context."
  - "Missing or invalid trusted_context in investigate/action_draft fails closed instead of falling back to AgentState authority."
  - "Approval resume grants action_draft permission through an explicit server_tool_permissions factory input, not through AgentState or request payload."

patterns-established:
  - "Route compatibility wrappers may expose legacy graph fields, but they must delegate identity to project_to_legacy_agent_state_identity."
  - "Graph-node tool contexts are projected from configurable['trusted_context']; tool-call-local metadata stays local to the node."
  - "Knowledge executor tenant/scope/run context is derived through project_tool_context_to_knowledge_context."

requirements-completed: [APF-03, APF-04]

duration: 35min
completed: 2026-06-23
---

# Phase 27 Plan 03: TrustedContextFactory and Projections Summary

**Current API, graph-node, and knowledge-tool seams now use canonical TrustedContextFactory/projection boundaries while preserving approval/replay regression behavior.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-22T17:05:00Z
- **Completed:** 2026-06-22T17:37:34Z
- **Tasks:** 2
- **Files modified:** 18

## Accomplishments

- `/api/v1/search`, `/api/v1/agent/chat`, and `/api/v1/agent-runs` now build canonical `TrustedContext` from authenticated/server inputs and project legacy graph identity through `project_to_legacy_agent_state_identity`.
- `investigate` and `action_draft` validate `configurable["trusted_context"]` and use `project_to_tool_context`; permissions and merchant scope no longer come from `AgentState`.
- `KnowledgeToolExecutor` now uses `project_tool_context_to_knowledge_context`, preserving merchant-scope list behavior through the central adapter.
- Approval resume config now supplies canonical `trusted_context` for action draft reconciliation, with legacy compatibility fields derived from that context.

## Task Commits

1. **Task 1 RED: route seam assertions** - `13ac46c` (`test`)
2. **Task 1 GREEN: route trusted context production** - `195e58e` (`feat`)
3. **Task 2 GREEN: graph-node and knowledge projections** - `0bc696a` (`feat`)

_Note: Task 2 RED tests were run before implementation and failed as expected, but the test-only delta was not committed separately; see TDD Gate Compliance._

## Files Created/Modified

- `src/api/routers/search.py` - Builds `TrustedContext` with `TrustedContextFactory` and projects to `KnowledgeContext`.
- `src/api/routers/agent.py` - Adds canonical graph `trusted_context` and legacy identity projection wrappers.
- `src/api/routers/agent_runs.py` - Adds route/run graph `trusted_context` and keeps `_trusted_tool_config` as factory-backed compatibility.
- `src/agent/nodes/investigate.py` - Validates graph trusted context and projects tool calls with `project_to_tool_context`.
- `src/agent/nodes/action_draft.py` - Uses trusted-context projection for action draft tool calls and fails closed when missing.
- `src/tools/executors/knowledge.py` - Uses the central tool-to-knowledge projection adapter.
- `src/api/routers/approvals.py` - Supplies approval resume trusted context and projection-derived `current_run_id` for action draft reconciliation.
- `src/platform/trusted_context.py` - Adds explicit server-granted `tool:*` permissions for trusted server boundaries.
- `tests/...` - Updates seam, integration, approval, action draft, platform, and architecture coverage.

## Decisions Made

- Approval resume keeps permissions narrow: only server-granted `tool:create_coupon_grant_draft` is added, avoiding widening resume graph permissions from reviewer token scopes.
- `server_tool_permissions` accepts only `tool:*` strings and de-duplicates permissions in `TrustedContextFactory`.
- The plan key-link pattern was corrected from an over-escaped regex to the verifier-compatible literal pattern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed invalid search fixture user**
- **Found during:** Task 1
- **Issue:** `tests/test_search_integration.py` referenced a nonexistent seeded `merchant_li` user.
- **Fix:** Switched the override-attempt fixture to seeded `merchant_wang`.
- **Files modified:** `tests/test_search_integration.py`
- **Verification:** `uv run pytest tests/test_search_integration.py tests/test_agent_runs_api.py -q`
- **Committed in:** `195e58e`

**2. [Rule 1 - Bug] Preserved approval resume after action_draft trusted_context gate**
- **Found during:** Task 2 verification
- **Issue:** `action_draft` correctly failed closed without `trusted_context`, causing approval resume reconciliation to mark runs `error`.
- **Fix:** Approval resume config now builds canonical trusted context through the factory, derives compatibility fields from it, and projects `current_run_id` through `project_to_legacy_agent_state_identity`.
- **Files modified:** `src/api/routers/approvals.py`, `src/platform/trusted_context.py`, `tests/test_approval_api.py`, `tests/platform/test_trusted_context_factory.py`
- **Verification:** Approval API regression tests and full plan gate passed.
- **Committed in:** `0bc696a`

**3. [Rule 1 - Bug] Updated action_draft regression fixtures for trusted_context**
- **Found during:** Task 2 verification
- **Issue:** Existing direct action_draft tests supplied legacy permissions only.
- **Fix:** Test configs now include canonical `TrustedContext` payloads aligned to each test state.
- **Files modified:** `tests/test_execute_action.py`
- **Verification:** `uv run pytest tests/test_execute_action.py -q`
- **Committed in:** `0bc696a`

**4. [Rule 3 - Blocking] Corrected key-link verifier pattern**
- **Found during:** Plan-level verification
- **Issue:** GSD key-link verification treated the escaped dot pattern as over-escaped and failed despite real `TrustedContextFactory.create_from_request` usage in `agent_runs.py`.
- **Fix:** Updated the plan key-link pattern to `TrustedContextFactory.create_from_request`.
- **Files modified:** `.planning/phases/27-trustedcontextfactory-and-projections/27-03-PLAN.md`
- **Verification:** `gsd-sdk query verify.key-links .planning/phases/27-trustedcontextfactory-and-projections/27-03-PLAN.md`
- **Committed in:** metadata commit

---

**Total deviations:** 4 auto-fixed (3 bugs, 1 blocking verification issue)
**Impact on plan:** All fixes were directly required for correctness or required verification. No Phase 28-35 deferred services were implemented.

## TDD Gate Compliance

- Task 1 followed RED/GREEN with separate commits: `13ac46c` then `195e58e`.
- Task 2 RED command was run and failed as expected before implementation, but the test-only delta was not committed separately due continuation context; Task 2 tests and implementation landed together in `0bc696a`.

## Verification

- `uv run pytest tests/test_search_integration.py tests/test_agent_runs_api.py -q` - passed (`42 passed, 1 warning`)
- `uv run pytest tests/test_search_integration.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/replay/test_replay_service.py -q` - passed (`78 passed, 1 warning`)
- `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py -q` - passed (`89 passed, 1 warning`)
- `uv run pytest tests/platform -q` - passed (`46 passed, 1 warning`)
- `uv run pytest tests/test_execute_action.py -q` - passed (`22 passed, 1 warning`)
- `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py -q` - passed (`131 passed, 1 warning`)
- `uv run ruff check ...` - passed
- `gsd-sdk query verify.key-links .planning/phases/27-trustedcontextfactory-and-projections/27-03-PLAN.md` - passed (`3/3`)

## Known Stubs

None. Stub scan found only test empty-list assertions, typed optional defaults, and existing optional local variables; no placeholder implementation blocks this plan.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: server_tool_permission_grant | `src/platform/trusted_context.py` | `TrustedContextFactory` now accepts explicit server-granted `tool:*` permissions for trusted server boundaries such as approval resume. The input is restricted to `tool:*` strings and verified by tests. |

## Auth Gates

None.

## Issues Encountered

- Only known runtime warning is `LangChainPendingDeprecationWarning` from `langgraph.checkpoint.serde.encrypted`; it is pre-existing and non-blocking.
- No local PostgreSQL or environment blocker occurred, so `.planning/LOCAL-VALIDATION-ISSUES.md` was not updated.

## User Setup Required

None.

## Next Phase Readiness

APF-03/APF-04 current runtime seams are covered for the route, graph-node, and knowledge-tool migration scope in 27-03. Future phases can build policy/runtime hardening on top of canonical trusted context without adding permissions or merchant scope to `AgentState`.

## Self-Check: PASSED

- Found summary file: `.planning/phases/27-trustedcontextfactory-and-projections/27-03-SUMMARY.md`
- Found task commit: `13ac46c`
- Found task commit: `195e58e`
- Found task commit: `0bc696a`

---
*Phase: 27-trustedcontextfactory-and-projections*
*Completed: 2026-06-23*
