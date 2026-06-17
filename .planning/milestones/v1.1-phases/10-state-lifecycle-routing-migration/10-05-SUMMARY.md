---
phase: 10-state-lifecycle-routing-migration
plan: 05
subsystem: graph-wiring
tags: [langgraph, routing, investigate, session-memory, clarification, pytest]
requires:
  - phase: 10-state-lifecycle-routing-migration
    provides: Plan 10-03 route_after_investigate router
  - phase: 10-state-lifecycle-routing-migration
    provides: Plan 10-04 investigate bounded-loop node and UnifiedToolManager seam
provides:
  - Live graph wiring for the merged investigate node
  - Minimal clarification_gate safe fallback stub
  - Empty session_memory_load adapter with no continuity claim
  - Migrated graph integration tests for the post-merge investigate path
affects: [phase-11-clarification, phase-12-session-memory, phase-15-replay]
tech-stack:
  added: []
  patterns:
    - Graph-level router-key totality tests
    - Config-injected UnifiedToolManager seam for full-graph tests
    - Safe fallback stubs for future owner phases
key-files:
  created:
    - src/agent/nodes/clarification_gate.py
    - src/agent/nodes/session_memory_load.py
    - tests/agent/test_empty_session_adapter.py
  modified:
    - src/agent/graph.py
    - src/agent/nodes/investigate.py
    - src/agent/trace.py
    - src/api/routers/agent.py
    - tests/agent/test_graph.py
    - tests/conftest.py
    - tests/test_embedder.py
key-decisions:
  - "Replaced the live load_business_context -> retrieve_policy_evidence linear path with extract_slots -> investigate -> route_after_investigate."
  - "Mapped canonical recommendation_generation route key to the existing live generate_recommendation node name."
  - "Kept clarification and session memory behavior minimal and deterministic; Phase 11 and Phase 12 own full implementations."
patterns-established:
  - "Full-graph tests patch the injected tool_manager seam rather than service internals or removed legacy nodes."
  - "session_memory_load writes an empty adapter view with continuity_claimed=False."
  - "clarification_gate never echoes tool errors, permission details, or denied resources."
requirements-completed: [ROUTE-01, ROUTE-02]
duration: 36 min
completed: 2026-06-14
---

# Phase 10 Plan 05: Graph Wiring Summary

**Live graph migration to the unified investigate node with total routing keys, safe fallback targets, and migrated full-graph integration tests**

## Performance

- **Duration:** 36 min
- **Started:** 2026-06-13T16:07:00Z
- **Completed:** 2026-06-13T16:43:00Z
- **Tasks:** 6
- **Files modified:** 9

## Accomplishments

- Added `clarification_gate` as a deterministic safe fallback stub that writes a clarification request and final-response candidate without exposing denied resources or tool error details.
- Added `session_memory_load` as the Phase 10 SC-3 empty adapter; it writes an empty session memory view and explicitly does not claim continuity.
- Rewired the compiled graph to register `session_memory_load`, `investigate`, and `clarification_gate`, then route `investigate` through `route_after_investigate`.
- Removed the old live linear investigation path from graph wiring while preserving legacy nodes as importable rollback/test targets.
- Migrated `tests/agent/test_graph.py` to the post-merge graph by patching the injected `tool_manager` seam and asserting the new D-08 `business_context` shape.
- Added graph-level router key coverage and empty session adapter tests.
- Fixed API chat persistence so Phase 10 DB-backed trace events have a parent `AgentRun` before `investigate` emits tool/RAG events.
- Migrated the shared approval integration `mock_graph` fixture to the post-merge `UnifiedToolManager` seam.

## Task Commits

Each task was committed atomically:

1. **Task 1: Safe fallback nodes** - `361bdc5` (`feat`)
2. **Task 2: Graph route wiring** - `a1060e5` (`feat`)
3. **Task 3: Expose retrieved evidence refs for graph routing** - `1e19bf7` (`fix`)
4. **Task 4: Migrate graph tests to investigate** - `0467ef7` (`test`)

## Files Created/Modified

- `src/agent/nodes/clarification_gate.py` - Minimal safe clarification fallback stub.
- `src/agent/nodes/session_memory_load.py` - Empty session-memory adapter with `continuity_claimed=False`.
- `src/agent/graph.py` - Registers the merged investigate path and maps router keys to real graph targets.
- `src/agent/nodes/investigate.py` - Exposes retrieved evidence refs for route-after-investigate decisions.
- `src/agent/trace.py` - Allows `write_agent_run` to update the pre-created run row used by DB-backed trace events.
- `src/api/routers/agent.py` - Creates the run row before graph invocation and passes the same `current_run_id` into state.
- `tests/agent/test_graph.py` - Migrated full-graph tests from legacy investigation nodes to the UnifiedToolManager seam.
- `tests/agent/test_empty_session_adapter.py` - SC-3 empty adapter coverage.
- `tests/conftest.py` - Migrated shared approval integration graph fixture to the injected `UnifiedToolManager` seam.
- `tests/test_embedder.py` - Clears proxy env vars in an API-key precedence unit test so it is independent of local SOCKS proxy setup.

## Decisions Made

- The canonical router key `recommendation_generation` remains a route label and maps to the existing `generate_recommendation` implementation node.
- The session-memory adapter returns `{"active_slots": {}, "source": "empty_adapter", "continuity_claimed": False}` rather than inheriting or fabricating slots.
- Graph tests assert old investigation nodes are not registered in the compiled graph, while leaving their modules in place for rollback and focused legacy-node tests.
- API chat now pre-creates a `running` run row and uses idempotent `write_agent_run` update semantics so event rows can keep the `agent_runs` FK.

## Deviations from Plan

- Added one small fix commit so `investigate` surfaces retrieved evidence refs needed by `route_after_investigate` and the migrated graph tests.
- During resume verification, added a follow-up integration fix for API chat run pre-creation because DB-backed Phase 10 event emission otherwise violates the `agent_trace_events.run_id -> agent_runs.id` FK before final run persistence.

**Total deviations:** 2 auto-fixed.
**Impact on plan:** No scope expansion; the fixes close the planned route-after-investigate and graph/API integration contracts.

## Issues Encountered

- Existing graph tests were coupled to legacy node monkeypatches and exact `business_context` shapes. They were migrated to use the `tool_manager` seam and D-08 `business_context["facts"]` structure.
- The shared approval integration fixture still patched `retrieve_policy_evidence`, which is no longer live after Phase 10 wiring. Fixed by injecting a fake `UnifiedToolManager`.
- Full-suite verification exposed local proxy inheritance in `tests/test_embedder.py`; the test now clears proxy env vars because it only verifies API key precedence.

## Verification

- `uv run pytest tests/agent/test_graph.py tests/agent/test_empty_session_adapter.py -q` passed: 10 tests.
- `uv run pytest tests/agent/test_graph.py tests/agent/test_empty_session_adapter.py tests/test_approval_integration.py tests/test_embedder.py -q` passed: 17 tests.
- `uv run pytest -q` passed: 443 tests.
- `uv run ruff check src/agent/trace.py src/api/routers/agent.py tests/conftest.py tests/test_embedder.py` passed.
- Acceptance greps confirmed `route_after_investigate`, `add_node("investigate")`, `recommendation_generation -> generate_recommendation`, `clarification_gate`, and `session_memory_load` are present.
- Grep confirmed `clarification_gate.py` does not mention `errors`, `FORBIDDEN`, or `permission`.
- Grep confirmed `load_business_context` and `retrieve_policy_evidence` are not live graph nodes; remaining mentions are only test assertions that they are absent.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 10 is complete. Phase 11 can now plan intent precedence, required-slot policy, confidence gates, and full clarification behavior on top of the migrated state and routing foundation.

---
*Phase: 10-state-lifecycle-routing-migration*
*Completed: 2026-06-14*
