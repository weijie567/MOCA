---
phase: 49-investigate-bounded-react-loop-migration
plan: "02"
subsystem: agent-graph
tags: [investigate, react, loop, slots, projection]
requires:
  - phase: 49-01
    provides: strict planner schema and fallback validation
provides:
  - planner-driven bounded investigate loop
  - loop-local discovered slot scratchpad
  - projection-only identifier discovery
  - max_iterations/deadline/max_attempts termination coverage
affects: [investigate, tool-projection, graph-react]
tech-stack:
  added: []
  patterns:
    - "loop-local scratchpad feeds later planner iterations without graph state writes"
    - "identifier discovery uses projected structured fields only"
key-files:
  created: []
  modified:
    - src/agent/nodes/investigate.py
    - src/tools/projection.py
    - tests/agent/test_nodes/test_investigate.py
key-decisions:
  - "Discovered identifiers stay inside the current investigate loop and never write active_slots/extracted_slots/candidate_slots."
  - "ToolPlatform errors terminate fail-closed instead of escaping from the node."
patterns-established:
  - "Local slot merge reads base state plus discovered_slots but returns only a local planner view."
  - "Relation hints in projection are narrow prompt-safe scalar hints."
requirements-completed: [GAD-01-IMPL]
duration: 1 commit
completed: 2026-07-04
---

# Phase 49 Plan 02 Summary

**Investigate now runs as a bounded planner-driven loop with loop-local discovered slots.**

## Performance

- **Duration:** 1 implementation commit
- **Completed:** 2026-07-04
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added local loop context with base slots, discovered slots, observations, attempted keys, and per tool+args attempt counts.
- Implemented order-to-ticket chaining through projected relation hints.
- Ensured discovered identifiers are visible to later planner iterations without mutating graph state.
- Added max iteration, deadline, duplicate/attempt, and platform error termination coverage.

## Task Commits

1. **Bounded loop runtime and loop-local discovery** - `8326e5d` (`feat: add investigate loop-local slot discovery`)

## Files Created/Modified

- `src/agent/nodes/investigate.py` - bounded loop context, local slot merge, discovery, termination behavior.
- `src/tools/projection.py` - prompt-safe `relation_hints` projection surface.
- `tests/agent/test_nodes/test_investigate.py` - chained investigation, no-state-mutation, termination, and injection regressions.
- `.planning/ARCHITECTURE-DEBT.md` - Phase 49-02 subsystem debt/fix record.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - local validation issue log.

## Decisions Made

- Slot discovery is explicitly not a graph writer, memory writer, or session memory feature.
- Projection is the only trusted identifier-discovery boundary; raw text regex discovery was not introduced.

## Deviations from Plan

None - plan executed within the intended file scope.

## Issues Encountered

One discovered-slot overreach risk was fixed by scoping direct identifier discovery by tool type. Details are recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` -> `51 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py -q` -> `47 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/tools/projection.py tests/agent/test_nodes/test_investigate.py` -> pass
- `rg -n 'active_slots\s*=|active_slots\]|active_slots\.' src/agent/nodes/investigate.py || true` -> no output

## Next Phase Readiness

49-03 can complete the exact 8-tool surface, prompt projection boundary tests, and per-iteration trace/replay metadata.

---
*Phase: 49-investigate-bounded-react-loop-migration*
*Completed: 2026-07-04*
