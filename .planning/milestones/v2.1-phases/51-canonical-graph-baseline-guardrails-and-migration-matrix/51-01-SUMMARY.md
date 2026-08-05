---
phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix
plan: "01"
subsystem: testing
tags: [agent-graph, architecture-tests, ast, migration-matrix]

requires:
  - phase: 50-canonical-agent-graph-migration-spec-and-guardrails
    provides: canonical graph migration charter and target node set
provides:
  - static graph source inspection helpers
  - target/current graph node constants
  - migration-mode legacy node map
  - forbidden registered-node drift sentinels
affects: [phase-51, phase-52, phase-53, phase-54, phase-55, phase-56, phase-57, phase-58]

tech-stack:
  added: []
  patterns: [AST-backed architecture guardrails]

key-files:
  created:
    - tests/architecture/__init__.py
    - tests/architecture/graph_baseline.py
  modified: []

key-decisions:
  - "Keep Phase 51 migration matrix test-local rather than editing runtime graph vocabulary."
  - "Represent final no-debt target and migration-mode current facts as separate constants."

patterns-established:
  - "Architecture tests can parse `src/agent/graph.py` source without importing runtime graph modules."
  - "Migration-mode baselines include canonical route labels that still map to legacy destinations."

requirements-completed: [CAGM-02]

duration: 10min
completed: 2026-07-06
---

# Phase 51 Plan 01 Summary

**AST-backed graph baseline helper with current/target node sets, route maps, migration aliases, and forbidden registered-node sentinels**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-06T05:29:50Z
- **Completed:** 2026-07-06T05:42:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `tests/architecture/graph_baseline.py` with AST helpers for `builder.add_node(...)` and `builder.add_conditional_edges(...)`.
- Captured the exact current 14-node runtime baseline separately from the target 15-node canonical graph.
- Added the six active legacy-to-target migration rows, including `generate_recommendation -> recommendation_generation`.
- Added forbidden main-chain registered-node sentinels for `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, and `action_execution`.

## Task Commits

1. **Task 1-2: Graph baseline helper and constants** - `6fc8b7d` (`test(51-01): add canonical graph baseline helper`)

## Files Created/Modified

- `tests/architecture/__init__.py` - Comment-only package marker for deterministic helper imports.
- `tests/architecture/graph_baseline.py` - Test-local constants and AST parser helpers for graph baseline guardrails.

## Decisions Made

- Kept Phase 51 graph migration mappings in `tests/architecture/graph_baseline.py`; no runtime graph or vocabulary behavior changed.
- Preserved the migration-mode edge behavior where canonical route key `recommendation_generation` still maps to legacy node `generate_recommendation`.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `git diff --check` passed.
- `uv run pytest tests/architecture/test_phase32_static_contract.py::test_phase32_required_mapping_entries_match_graph_vocabulary -q` passed: `1 passed, 1 warning`.
- `tests/architecture/__init__.py` is comment-only.
- `tests/architecture/graph_baseline.py` does not import or compile `src.agent.graph`.

## Next Phase Readiness

Plan 51-02 can import `tests.architecture.graph_baseline` to assert current graph source facts, target graph constants, migration-mode mappings, router baselines, and forbidden-node drift.

---
*Phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix*
*Completed: 2026-07-06*
