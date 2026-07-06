---
phase: 52-safety-pre-route-node
plan: "02"
subsystem: agent-graph
tags: [safety-pre-route, langgraph, deterministic-routing, architecture-guardrails, tdd]

requires:
  - phase: 52-01
    provides: deterministic safety_pre_route node and state fields
  - phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix
    provides: static graph baseline and migration guardrail framework
provides:
  - fail-closed route_after_safety router with Phase 52 compatibility allowlist
  - active graph edge START -> receive_request -> safety_pre_route
  - static architecture baseline proving safety_pre_route is active and route maps are total
  - graph smoke coverage proving unsafe pre-route inputs stop before classifier, memory, tools, approval, and action paths
affects: [phase-52, phase-53, phase-58, agent-graph, intent-routing]

tech-stack:
  added: []
  patterns:
    - deterministic route allowlist wrapper
    - AST-based direct-edge and conditional-edge guardrails
    - TDD red/green commits for routing and static baseline changes

key-files:
  created:
    - .planning/phases/52-safety-pre-route-node/52-02-SUMMARY.md
  modified:
    - src/agent/routing.py
    - src/agent/graph.py
    - tests/architecture/graph_baseline.py
    - tests/architecture/test_canonical_graph_baseline.py
    - tests/test_graph_routing.py
    - tests/agent/test_graph.py

key-decisions:
  - "Phase 52 safe continuation remains safety_pre_route -> classify_intent; Phase 53 still owns session_context_load/contextual_intent_resolve cutover."
  - "Unsafe, approval-like, multi-target, clarification-required, and untrusted approval paths route to clarification_gate; this plan introduced no direct final_response refusal branch."
  - "Architecture guardrails now parse direct add_edge calls as well as conditional route maps."

patterns-established:
  - "route_after_safety mirrors existing router wrappers: call private router, catch exceptions, allowlist route keys, and fail closed to clarification_gate."
  - "Static baseline tests assert both direct graph entry edges and conditional route-totality for newly active canonical nodes."

requirements-completed: [CAGM-03]

duration: 6min
completed: 2026-07-06
---

# Phase 52 Plan 02: Safety Pre-route Graph Wiring Summary

**Fail-closed `safety_pre_route` graph insertion with deterministic routing and static route-totality guardrails.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-06T09:03:14Z
- **Completed:** 2026-07-06T09:09:29Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `SAFETY_ROUTES` and `route_after_safety` in `src/agent/routing.py`, failing closed to `clarification_gate` on exceptions, unregistered route values, untrusted approval chat, multi-target requests, approval-decision operations, and clarification-required safety state.
- Wired the active LangGraph source path to `START -> receive_request -> safety_pre_route`, then conditionally to `classify_intent`, `clarification_gate`, or `final_response`.
- Updated Phase 51 static guardrails so `safety_pre_route` is an active canonical node, its route map is source-checked, and direct `add_edge(...)` calls are parsed.
- Added graph smoke tests proving `approve APR-1` and `同意` stop before `classify_intent`, memory, investigate, approval, action, tool calls, or RAG events.

## Task Commits

1. **Task 1 RED: safety graph routing tests** - `8151723` (test)
2. **Task 1 GREEN: active graph wiring and route_after_safety** - `d0aa258` (feat)
3. **Task 2 RED: static safety baseline checks** - `c03f6b4` (test)
4. **Task 2 GREEN: architecture baseline/helper update** - `16ba560` (feat)

## Files Created/Modified

- `src/agent/routing.py` - Added `SAFETY_ROUTES`, public `route_after_safety`, and private `_route_after_safety` fail-closed logic.
- `src/agent/graph.py` - Registered `safety_pre_route` and inserted its conditional route map after `receive_request`.
- `tests/test_graph_routing.py` - Added router behavior tests for safe compatibility, unsafe clarification routing, exception handling, and unregistered route fallback.
- `tests/agent/test_graph.py` - Added graph compile/router coverage and unsafe pre-route graph smoke tests.
- `tests/architecture/graph_baseline.py` - Added `safety_pre_route` to current active baseline, conditional edge baseline, direct-edge parser, and route extraction.
- `tests/architecture/test_canonical_graph_baseline.py` - Added direct entry-edge assertion and explicit `route_after_safety` route-totality assertion.
- `.planning/phases/52-safety-pre-route-node/52-02-SUMMARY.md` - This execution summary.

## Decisions Made

- Safe continuation intentionally remains `classify_intent` for Phase 52 compatibility. No `session_context_load` or `contextual_intent_resolve` runtime cutover was implemented.
- Unsafe/bypass branches use `clarification_gate` only. The plan allowed direct `final_response` refusal with explicit reason and tests, but implementation did not need that branch.

## TDD Gate Compliance

- **Task 1 RED:** `8151723` failed as expected with `ImportError: cannot import name 'route_after_safety'`.
- **Task 1 GREEN:** `d0aa258` made `tests/test_graph_routing.py tests/agent/test_graph.py` pass.
- **Task 2 RED:** `c03f6b4` failed as expected with missing `graph_direct_edge_pairs`.
- **Task 2 GREEN:** `16ba560` made the architecture baseline and route-totality tests pass.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_graph.py -q --tb=short` - `93 passed, 27 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/routing.py src/agent/graph.py tests/test_graph_routing.py tests/agent/test_graph.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py tests/agent/test_graph.py -q --tb=short` - `103 passed, 1 skipped, 27 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/routing.py src/agent/graph.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py tests/agent/test_graph.py` - passed

Warnings were pre-existing LangGraph/checkpoint deprecation/config typing warnings surfaced by the focused graph suite.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope expansion; Phase 53/54/58 graph cutover work remains untouched.

## Issues Encountered

None. The failing runs were expected TDD RED gates.

## Known Stubs

None. Stub scan found only existing test fixture empty collections/`None` values and initialized route collections.

## Threat Flags

None. This plan changed an existing graph trust boundary already covered by T-52-03/T-52-05 and added the planned mitigations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 52-03 compatibility/docs/validation closeout. The runtime graph now enters `safety_pre_route`, but remaining compatibility documentation and final Phase 52 validation artifacts still belong to the next plan.

## Self-Check: PASSED

- Found created/modified files: `.planning/phases/52-safety-pre-route-node/52-02-SUMMARY.md`, `src/agent/routing.py`, `src/agent/graph.py`, `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `tests/test_graph_routing.py`, `tests/agent/test_graph.py`
- Found task commits: `8151723`, `d0aa258`, `c03f6b4`, `16ba560`
- Confirmed `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified

---
*Phase: 52-safety-pre-route-node*
*Completed: 2026-07-06*
