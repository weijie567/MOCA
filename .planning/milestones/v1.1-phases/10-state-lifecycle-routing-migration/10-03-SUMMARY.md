---
phase: 10-state-lifecycle-routing-migration
plan: 03
subsystem: routing
tags: [langgraph, routing, deterministic-router, totality, pytest]
requires:
  - phase: 10-state-lifecycle-routing-migration
    provides: Plan 10-01 canonical AgentState fields
provides:
  - Pure route_after_investigate router
  - Totality and safe-fallback tests for investigate routing
  - Fine-grained permission-denied routing tests
affects: [phase-10-graph-wiring, phase-10-investigate, phase-11-clarification]
tech-stack:
  added: []
  patterns:
    - State-only pure router in src/agent/routing.py
    - Defensive reads for total=False AgentState compatibility
    - Safe final_response fallback for invalid investigate state
key-files:
  created:
    - src/agent/routing.py
  modified:
    - tests/test_graph_routing.py
key-decisions:
  - "Kept existing route_after_risk and route_after_approval in graph.py; only route_after_investigate moved into the new routing module for this plan."
  - "Used hand-written table tests instead of adding a new property-testing dependency."
patterns-established:
  - "route_after_investigate returns only final_response, clarification_gate, or recommendation_generation."
  - "Denied-resource routing fails closed only when dependency mapping is missing, invalid, required, or answer-blocking."
requirements-completed: [ROUTE-01, ROUTE-02]
duration: 8 min
completed: 2026-06-13
---

# Phase 10 Plan 03: Investigate Router Summary

**State-only `route_after_investigate` with deterministic precedence, safe fallback, and permission-denied dependency handling**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-13T16:06:00Z
- **Completed:** 2026-06-13T16:14:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `src/agent/routing.py` with `route_after_investigate(state)`.
- Implemented defensive state reads so empty, partial, and garbage-typed state falls back safely.
- Added branch coverage for missing facts, fact-only final response, insufficient evidence, sufficient recommendation routing, permission-denied fail-closed behavior, D-08 nonrequired denial preservation, and D-03 max-iteration separation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement route_after_investigate** - `842f300` (`feat`)
2. **Task 2: Totality, per-branch, and fine-grained permission-denied tests** - `60e9478` (`test`)

## Files Created/Modified

- `src/agent/routing.py` - New pure investigate router and defensive helper functions.
- `tests/test_graph_routing.py` - Existing router tests plus investigate routing coverage.

## Decisions Made

- Did not move existing routers out of `graph.py`; keeping that migration for graph wiring avoids unnecessary churn.
- Treated `termination_reason=max_iterations_reached` as independent from evidence sufficiency, as required by D-03.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification

- `uv run pytest tests/test_graph_routing.py -x -q` passed: 25 tests.
- Signature check confirmed `route_after_investigate` is not async and takes only `state`.
- `rg -n "await|config|RunnableConfig|session" src/agent/routing.py` returned no matches.
- Empty state returns `final_response`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 10-04 and Plan 10-05. The investigate node can now hand accumulated state to a tested router, and graph wiring can later map the three canonical return keys.

---
*Phase: 10-state-lifecycle-routing-migration*
*Completed: 2026-06-13*
