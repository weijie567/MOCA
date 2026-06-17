---
phase: 11-intent-clarification
plan: 03
subsystem: agent
tags: [slots, graph, routing]
requires:
  - phase: 11-intent-clarification
    provides: Intent policy and pre-route metadata
provides:
  - route_after_intent and route_after_slots
  - Required-slot completeness helper
  - Empty long-term/case memory seam
affects: [phase-12-session-memory, phase-16-memory]
tech-stack:
  added: []
  patterns: [conditional-graph-edge, current-turn-slot-trust]
key-files:
  created:
    - src/agent/nodes/long_term_memory_retrieve.py
    - tests/agent/test_required_slots.py
  modified:
    - src/agent/routing.py
    - src/agent/graph.py
    - src/agent/nodes/extract_slots.py
    - tests/agent/test_graph.py
    - tests/agent/test_intent_routing.py
key-decisions:
  - "Candidate slots are prompt hints only and cannot satisfy required-slot completeness."
  - "Top-level active_slots are ignored for Phase 11 completeness; session slots require trusted continuity metadata."
patterns-established:
  - "Graph routes after intent and slot extraction through deterministic total routers."
requirements-completed: [INTENT-01, INTENT-02]
duration: 0h 0m
completed: 2026-06-14
---

# Phase 11 Plan 03: Slot Routing and Graph Wiring Summary

**Deterministic graph edges block missing required slots before investigation and reserve an empty long-term memory seam**

## Performance

- **Duration:** Inline with Phase 11 execution batch
- **Started:** 2026-06-14
- **Completed:** 2026-06-14
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `missing_required_slots`, `resolve_slots_for_completeness`, `route_after_intent`, and `route_after_slots`.
- Replaced static graph edges after intent/slots with conditional edges.
- Added `long_term_memory_retrieve` as an empty adapter writing empty memory arrays with no continuity claim.

## Task Commits

Inline execution was used in this runtime, so task-level changes are included in the final Phase 11 scoped commit rather than separate per-task commits.

## Deviations from Plan

None beyond inline execution/commit shape.

## Issues Encountered

Existing graph tests assumed the old linear policy QA path always loaded session memory. Tests were updated to reflect the new direct investigate route for zero-slot policy QA.

## User Setup Required

None.

## Next Phase Readiness

Plan 11-04 can rely on missing-slot and approval-chat states reaching `clarification_gate` before tools/actions.

---
*Phase: 11-intent-clarification*
*Completed: 2026-06-14*
