---
phase: 32-intent-graph-migration
plan: 32-01
subsystem: agent-graph
tags: [graph-vocabulary, compatibility-aliases, langgraph, apf-11]
requires:
  - phase: 31-memory-platform-boundary
    provides: session_context_load and reviewed memory compatibility wrappers
provides:
  - Typed target graph vocabulary for legacy node/router aliases
  - Deferred/non-runnable Phase 33 target entries for rag_context_build and claim_verify
  - Graph compilation tests proving legacy runtime node compatibility
affects: [phase-32, phase-33-rag-context-build, trace-projection, eval-projection]
tech-stack:
  added: []
  patterns:
    - Immutable graph vocabulary helper with additive contract projection fields
key-files:
  created:
    - src/agent/graph_vocabulary.py
    - tests/agent/test_graph_vocabulary.py
  modified:
    - tests/agent/test_graph.py
key-decisions:
  - "Kept legacy LangGraph node/router names as runtime/debug names and exposed target names through a typed helper."
  - "Cataloged rag_context_build and claim_verify only as deferred_non_runnable Phase 33 targets."
patterns-established:
  - "GraphVocabularyEntry maps implementation names to target names without mutating trace_steps[].node or graph registration."
requirements-completed: [APF-11]
duration: 7min
completed: 2026-06-28
---

# Phase 32 Plan 01: Graph Vocabulary and Projection Helper Summary

**Typed legacy-to-target graph vocabulary with non-runnable Phase 33 target entries and compatibility tests for the existing LangGraph runtime names**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-28T13:27:26Z
- **Completed:** 2026-06-28T13:34:08Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `src/agent/graph_vocabulary.py` with immutable node/router alias entries and `project_trace_step_for_contract(...)`.
- Covered `slot_resolution_gate`, `safety_pre_route`, `contextual_intent_resolve`, `session_context_load`, `memory_context_load`, and router target names.
- Pinned `rag_context_build` and `claim_verify` as `deferred_non_runnable` only; no runnable graph nodes were added.

## Task Commits

1. **Task 1 RED:** `c75042b` (test) add failing graph vocabulary projection tests.
2. **Task 1 GREEN:** `671ccfe` (feat) implement graph vocabulary helper.
3. **Task 1 REFACTOR:** `fa44e74` (refactor) align the `extract_slots -> slot_resolution_gate` alias with the planned acceptance scan.
4. **Task 2:** `3f43348` (test) pin graph vocabulary compatibility in `tests/agent/test_graph.py`.

## Files Created/Modified

- `src/agent/graph_vocabulary.py` - Typed graph vocabulary entries, lookup helpers, deferred target checks, and trace-step projection.
- `tests/agent/test_graph_vocabulary.py` - Alias, target identity, unknown passthrough, trace projection, and Phase 33 deferred tests.
- `tests/agent/test_graph.py` - Compiled graph compatibility and no-runnable-Phase-33 assertions.

## Decisions Made

- Unknown graph names project as `unknown_passthrough` in trace projection, not as known runtime entries.
- `classify_intent:pre_route` is represented as projection metadata for `safety_pre_route`, not as a registered graph node.

## Deviations from Plan

None - plan scope was followed. One refactor commit only made an existing required alias visible to the exact planned `rg` acceptance pattern.

## Issues Encountered

- Task 2's TDD RED gate passed immediately because Task 1 had already implemented the vocabulary helper and the existing graph already omitted runnable Phase 33 nodes. The task was completed as a test-pinning task with no production edit.

## Known Stubs

None. Empty list literals found by the stub scan are existing test fixture values, not UI/data-source stubs.

## Auth Gates

None.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py -q --tb=short` - 20 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_graph.py -q --tb=short` - 45 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py tests/agent/test_graph_vocabulary.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py` - passed.

## Next Phase Readiness

Plan 32-02 can consume the graph vocabulary while migrating effective intent routing to `IntentPolicyRegistry`. Phase 33 names remain cataloged only as deferred/non-runnable targets.

## Self-Check: PASSED

- Found `src/agent/graph_vocabulary.py`.
- Found `tests/agent/test_graph_vocabulary.py`.
- Found `.planning/phases/32-intent-graph-migration/32-01-SUMMARY.md`.
- Found commits `c75042b`, `671ccfe`, `fa44e74`, and `3f43348`.

---
*Phase: 32-intent-graph-migration*
*Completed: 2026-06-28*
