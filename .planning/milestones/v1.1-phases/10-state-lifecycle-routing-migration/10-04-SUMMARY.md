---
phase: 10-state-lifecycle-routing-migration
plan: 04
subsystem: investigate-loop
tags: [langgraph, unified-tools, bounded-loop, trace-events, policy-retrieval, pytest]
requires:
  - phase: 10-state-lifecycle-routing-migration
    provides: Plan 10-01 state fields and Plan 10-02 event emitter
  - phase: 09-business-tool-facade
    provides: BusinessToolService facade and ToolResultV2 contracts
provides:
  - UnifiedToolManager node-facing dispatch path
  - Bounded investigate loop using unified dispatch only
  - Guardrail tests for allowlist, resource caps, permission denial, events, and retrieval semantics
affects: [phase-10-graph-wiring, phase-15-replay, phase-12-memory, phase-13-approval]
tech-stack:
  added: []
  patterns:
    - Manager/executor split for read/retrieval tools
    - Structured one-step planner seam for investigate
    - Config-injected event emitter for testability with DB-backed default emitter
key-files:
  created:
    - src/agent/tools/unified.py
    - src/agent/nodes/investigate.py
    - tests/agent/test_tools/test_unified_tool_manager.py
    - tests/agent/test_nodes/test_investigate.py
  modified: []
key-decisions:
  - "Used ToolRegistry().descriptors() as the temporary canonical descriptor catalog; no second descriptor table was introduced."
  - "Kept service-specific dependencies behind manager executors; investigate imports only UnifiedToolManager, ToolCallContext/ToolResultV2, and event helpers."
  - "Supported config-injected tool_manager and event_emitter for deterministic node tests while preserving live defaults."
patterns-established:
  - "investigate executes one manager-visible read/retrieval tool per iteration."
  - "Unavailable tools are marked unusable for the current run and are not retried with identical args."
  - "Policy retrieval status and best_score survive ToolResultV2 flattening."
requirements-completed: [ROUTE-02]
duration: 35 min
completed: 2026-06-13
---

# Phase 10 Plan 04: Unified Investigate Loop Summary

**Unified tool dispatch layer and bounded investigate loop with manager-only execution, event emission, and guardrail coverage**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-13T16:15:00Z
- **Completed:** 2026-06-13T16:50:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `UnifiedToolManager` with business, knowledge, and memory/future executors behind one node-facing dispatch path.
- Added `investigate` as a bounded loop with structured planner seam, max-iteration/deadline/attempt controls, manager-only invocation, and per-call event emission.
- Added tests covering descriptor discovery, event-family agreement, business delegation, policy search, unavailable tools, write blocking, invalid input, malformed executor returns, max-iteration behavior, permission denial, claim dependencies, retrieval semantics, and event redaction shape.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build unified tool manager and executors** - `c96743c` (`feat`)
2. **Task 2: Implement investigate as bounded loop** - `173e72d` (`feat`)
3. **Task 3: Guardrail and integration tests** - `c70aa1e` (`test`)

## Files Created/Modified

- `src/agent/tools/unified.py` - Unified manager, executor protocol, business/knowledge/memory executors, descriptor and rejection handling.
- `src/agent/nodes/investigate.py` - Bounded investigate node with planner seam, manager calls, event emission, and state accumulation.
- `tests/agent/test_tools/test_unified_tool_manager.py` - Manager and executor dispatch contract tests.
- `tests/agent/test_nodes/test_investigate.py` - Loop guardrail and manager integration tests.

## Decisions Made

- Used a deterministic scripted planner seam for tests and fallback behavior; the schema remains replaceable by a future LLM planner.
- Treated memory/SOP/logistics/merchant-risk missing backends as declared-but-unavailable through the same manager path, rather than building new data sources in Phase 10.
- Raised invalid planner output to `termination_reason=unrecoverable_error` before dispatch.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- Initial scripted planner fallback continued into `search_policy` after explicit test plans were exhausted. Fixed loop control so scripted plans stop with `no_more_useful_tools`.
- `max_attempts=0` was initially coerced to default 1 via `or`; fixed to preserve explicit zero and map it to `unrecoverable_error`.

## Verification

- `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py -q` passed: 30 tests.
- Greps confirmed `investigate.py` has no direct service imports or raw legacy registry/tool imports.
- Greps confirmed `investigate.py` does not return authoritative citation refs or write proposed/risk/approval/action state fields.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 10-05 graph wiring. The graph can now register `investigate`, use `route_after_investigate`, and map the three canonical route keys to real nodes/stubs.

---
*Phase: 10-state-lifecycle-routing-migration*
*Completed: 2026-06-13*
