---
phase: 49-investigate-bounded-react-loop-migration
plan: "01"
subsystem: agent-graph
tags: [investigate, react, planner, validation, fallback]
requires: []
provides:
  - strict investigate planner action/stop schema
  - default structured LLM planner path
  - deterministic plan_next_step fallback safety net
  - read-only allowlist and args validation before ToolPlatform dispatch
affects: [investigate, tool-platform, graph-react]
tech-stack:
  added: []
  patterns:
    - "planner structured-output contract validated before dispatch"
    - "deterministic planner retained as fallback only"
key-files:
  created:
    - src/agent/nodes/investigate_planner.py
  modified:
    - src/agent/nodes/investigate.py
    - src/agent/prompts.py
    - tests/agent/test_nodes/test_investigate.py
key-decisions:
  - "LLM planner is the normal main path; deterministic plan_next_step is fallback for unavailable/invalid planner behavior."
  - "Planner output cannot carry routing, evidence, approval, action, or memory authority fields."
patterns-established:
  - "Planner decisions are exactly one `{next_tool,args,reason}` action or one `{stop,stop_reason}` decision."
  - "Fallback output is validated by the same read-only allowlist and descriptor schema gate."
requirements-completed: [GAD-01-IMPL]
duration: 1 commit
completed: 2026-07-04
---

# Phase 49 Plan 01 Summary

**Investigate now has a strict structured planner contract with a validated deterministic fallback shell.**

## Performance

- **Duration:** 1 implementation commit
- **Completed:** 2026-07-04
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `InvestigatePlannerDecision` and default structured LLM planner wrapper.
- Routed normal investigate planning through planner validation before dispatch.
- Preserved deterministic `plan_next_step` as fallback only, with the same read-only validation boundary.
- Added invalid schema, malformed output, write-tool, unknown-tool, invalid-args, stop, and fallback tests.

## Task Commits

1. **Planner schema / validation / fallback shell** - `c3d3da6` (`feat: add investigate planner validation fallback`)

## Files Created/Modified

- `src/agent/nodes/investigate_planner.py` - planner schema, allowlist, structured LLM wrapper, validation helpers.
- `src/agent/nodes/investigate.py` - planner invocation seam and fallback integration.
- `src/agent/prompts.py` - investigate planner prompt constants.
- `tests/agent/test_nodes/test_investigate.py` - planner validation and fallback regression coverage.
- `.planning/ARCHITECTURE-DEBT.md` - Phase 49-01 subsystem debt/fix record.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - local validation issue log.

## Decisions Made

- Kept the old deterministic planner available under fallback semantics instead of deleting it.
- Rejected extra planner authority fields fail-closed before any tool dispatch.

## Deviations from Plan

None - plan executed within the intended file scope.

## Issues Encountered

Local validation initially exposed expected Phase 49-01 gaps; they were fixed and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` -> `46 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/agent/nodes/investigate_planner.py src/agent/prompts.py tests/agent/test_nodes/test_investigate.py` -> pass

## Next Phase Readiness

49-02 can build the actual bounded multi-iteration runtime and loop-local discovered slot scratchpad on top of this validated planner shell.

---
*Phase: 49-investigate-bounded-react-loop-migration*
*Completed: 2026-07-04*
