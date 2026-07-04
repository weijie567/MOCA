---
phase: 49-investigate-bounded-react-loop-migration
plan: "03"
subsystem: agent-graph
tags: [investigate, tool-platform, projection, replay, trace]
requires:
  - phase: 49-02
    provides: bounded planner loop and loop-local discovered slots
provides:
  - exact eight-tool investigate read/retrieval surface
  - planner observation raw-payload boundary tests
  - per-iteration operation identity and replay metadata
  - search_sop real executor visibility as read-only unavailable/no-data retrieval
affects: [investigate, tool-platform, replay, graph-react]
tech-stack:
  added: []
  patterns:
    - "ToolPlatform exact-set smoke tests for planner-visible tools"
    - "event emitters pass parent_operation_id, attempt, and tool_call_id through existing replay fields"
key-files:
  created: []
  modified:
    - src/agent/events.py
    - src/agent/nodes/investigate.py
    - src/replay/decision_events.py
    - src/tools/executors/knowledge.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/replay/test_operation_pairing.py
    - tests/tools/test_tool_platform.py
key-decisions:
  - "search_sop is executor-visible but remains read-only unavailable until a real SOP backend exists."
  - "Parent operation identity is emitted when node_operation_id or investigate_operation_id is supplied by configurable."
patterns-established:
  - "Every loop tool/RAG event carries distinct operation_id, iteration, attempt, and tool_call_id."
  - "Planner input tests capture fake planner context to prove raw payload sentinel text is absent."
requirements-completed: [GAD-01-IMPL]
duration: 1 commit
completed: 2026-07-04
---

# Phase 49 Plan 03 Summary

**Investigate now exposes the full eight-tool read-only surface and emits replay-distinguishable loop tool events.**

## Performance

- **Duration:** 1 implementation commit
- **Completed:** 2026-07-04
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added exact-set and ToolPlatform smoke coverage for all eight §12.4 investigate tools.
- Made `search_sop` visible to the real knowledge executor while preserving safe unavailable/no-data semantics.
- Proved planner context sees projected observations rather than raw payload sentinel content.
- Passed `parent_operation_id`, `attempt`, and `tool_call_id` through event/replay helper APIs and investigate event emission.
- Added replay pairing coverage for multiple loop operations under the same investigate parent operation.

## Task Commits

1. **Eight-tool surface, projection boundary, and trace/replay metadata** - `495e2fa` (`feat: harden investigate tool surface tracing`)

## Files Created/Modified

- `src/tools/executors/knowledge.py` - `search_sop` executor visibility while preserving read-only unavailable result.
- `src/agent/nodes/investigate.py` - per-call attempt/tool_call_id/parent metadata emission.
- `src/agent/events.py` - event helper passthrough for existing replay fields.
- `src/replay/decision_events.py` - decision event passthrough for existing replay fields.
- `tests/tools/test_tool_platform.py` - exact 8-tool visibility and invoke smoke tests.
- `tests/agent/test_nodes/test_investigate.py` - projection raw-boundary and event metadata tests.
- `tests/replay/test_operation_pairing.py` - replay-distinguishable loop operation coverage.
- `.planning/ARCHITECTURE-DEBT.md` - Phase 49-03 subsystem debt/fix record.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - DB-backed pytest parallelism issue and sequential rerun record.

## Decisions Made

- Did not change event schema or database schema; only passed existing replay fields through local helper APIs.
- Did not expose raw tool payload to the planner to recover more context.

## Deviations from Plan

None. Parent node operation identity is available only when supplied by graph/configurable context; 49-04 must decide whether that closes as fully implemented or with a replay limitation.

## Issues Encountered

Running multiple DB-backed pytest commands in parallel caused Postgres schema DDL conflicts. The commands were rerun sequentially and passed; the incident is recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` -> `52 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` -> `79 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q` -> `23 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/replay/test_decision_events.py -q` -> `68 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/agent/events.py src/replay/decision_events.py src/tools/executors/knowledge.py tests/agent/test_nodes/test_investigate.py tests/tools/test_tool_platform.py tests/replay/test_operation_pairing.py` -> pass
- `rg -n 'ToolPlatform\.invoke|tool_platform\.invoke|BusinessFactService|BusinessToolService|KnowledgeToolExecutor|PolicyKnowledgeService|MemoryService|CaseMemoryService|create_coupon_grant_draft|action_' src/agent/nodes/investigate.py` -> only `tool_platform.invoke(...)` and redaction policy string

## Next Phase Readiness

49-04 can run graph-level safety regression, no-go diff checks, and GAD-01 closeout. The parent-operation caveat should be recorded as a limitation unless graph-level node operation identity is wired in 49-04.

---
*Phase: 49-investigate-bounded-react-loop-migration*
*Completed: 2026-07-04*
