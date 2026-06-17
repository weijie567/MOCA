---
phase: 09-business-tool-facade
plan: 05
subsystem: business-tools
tags: [facade, trusted-context, router-config, read-switch, regression-tests]

requires:
  - phase: 09-04
    provides: BusinessToolService facade, default registry composition, and typed context aggregation
provides:
  - Live graph business reads routed through BusinessToolService.fetch_context
  - Deterministic router projection of trusted tool permissions, merchant scope, and trace identity
  - Retired prior-line investigator whitelist and business registry semantics
affects: [10-state-lifecycle-routing-migration, investigate-loop, agent-run-streaming]

tech-stack:
  added: []
  patterns:
    - Trusted authorization projection stays in run config rather than persisted AgentState
    - Graph tests patch the facade boundary instead of raw business functions

key-files:
  created:
    - tests/agent/test_nodes/test_load_business_context.py
  modified:
    - src/agent/nodes/load_business_context.py
    - src/api/routers/agent_runs.py
    - src/agent/tools/registry.py
    - src/agent/tools/contracts.py
    - tests/agent/test_graph.py
    - tests/agent/test_tools/test_registry.py
    - tests/agent/test_tools/test_tool_contracts.py

key-decisions:
  - "Trusted tool permissions and merchant scope are derived in the agent-runs router and passed only through configurable run config."
  - "The prior-line registry remains only as an isolated policy-search compatibility path; live business reads use the Phase 9 facade."

patterns-established:
  - "load_business_context constructs ToolCallContext from trusted state/config and delegates the complete conditional read set to BusinessToolService."
  - "tool_results carries ToolResultV2 objects directly without the obsolete legacy tool wrapper."

requirements-completed: [TOOL-01, TOOL-03]

duration: 5h 9m
completed: 2026-06-12
---

# Phase 09 Plan 05: Business Tool Read-Switch Summary

**Live agent business reads now cross the typed BusinessToolService boundary with router-derived trusted permissions and merchant scope**

## Performance

- **Duration:** 5h 9m
- **Started:** 2026-06-12T15:43:55Z
- **Completed:** 2026-06-12T20:53:27Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Switched `load_business_context` from direct order/refund/ticket calls to `BusinessToolService.fetch_context` while preserving the load guard, slot selection, state keys, and trace node name.
- Added deterministic `ROLE_SCOPES` to `tool:*` permission projection plus authenticated-user merchant scope and trace injection in trusted run config.
- Removed obsolete investigator whitelist and business dispatch semantics from the prior-line registry, retaining only an isolated policy-search compatibility surface.
- Retargeted graph/node regressions to the facade boundary and proved ToolResultV2 migration, fail-closed trusted config, router projection, and invalid-response no-leak behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate load_business_context to BusinessToolService.fetch_context** - `781cb29` (feat)
2. **Task 2: Retire obsolete prior-line business registry and contract semantics** - `6ff9139` (refactor)
3. **Task 3: Retarget affected tests and add read-switch parity regression** - `bd78849` (test)

## Files Created/Modified

- `src/agent/nodes/load_business_context.py` - Builds trusted ToolCallContext and maps typed facade context back to graph state.
- `src/api/routers/agent_runs.py` - Derives and injects trusted tool permissions, merchant scope, and trace id.
- `src/agent/tools/registry.py` - Removes obsolete business/investigator behavior and keeps policy-search compatibility.
- `src/agent/tools/contracts.py` - Clearly isolates legacy policy/adapter compatibility contracts and removes investigator metadata.
- `tests/agent/test_nodes/test_load_business_context.py` - Covers facade delegation, state parity, fail-closed config, router projection, and no raw invalid sentinel.
- `tests/agent/test_graph.py` - Patches the facade boundary while preserving business-context graph assertions.
- `tests/agent/test_tools/test_registry.py` - Verifies the reduced policy-only compatibility registry.
- `tests/agent/test_tools/test_tool_contracts.py` - Removes obsolete business-contract assertions while preserving unrelated investigation coverage.

## Decisions Made

- Kept `ToolInvocationContext` and `ToolExecutionResult` only as explicitly documented legacy compatibility types because the unmigrated raw policy adapter and adapter tests still import them; no live business node imports them.
- Used the existing authenticated `User.role` and `ROLE_SCOPES` source because token payload scopes are not exposed at the router dependency boundary.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The sandbox blocked the complete suite from connecting to the local PostgreSQL test database; the same command passed with approved local database access.
- The sandbox blocked `.git/index.lock`; all required atomic commits were rerun with approved git access and normal hooks.

## Known Stubs

None. Empty result/context collections are intentional fail-closed or no-load outcomes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 9 is complete and the Phase 10 bounded investigate loop can call the facade through the canonical `investigate` caller identity.
- Search policy ownership and raw business read/authz implementations remain unchanged for their existing owners and rollback path.

## Self-Check: PASSED

- Confirmed all eight plan-owned source/test files exist.
- Confirmed task commits `781cb29`, `6ff9139`, and `bd78849` exist.
- Confirmed compile checks, acceptance greps, and the complete plan suite pass (`128 passed`).
- Confirmed raw `get_order`, `get_refund_case`, `get_ticket`, `authz`, and `search_policy` files were not modified.

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-12*
