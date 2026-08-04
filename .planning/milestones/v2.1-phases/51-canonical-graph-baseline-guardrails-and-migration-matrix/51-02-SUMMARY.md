---
phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix
plan: "02"
subsystem: testing
tags: [agent-graph, architecture-tests, canonical-graph, migration-guardrails]

requires:
  - phase: 51-01
    provides: graph baseline helper and constants
provides:
  - current active graph node guardrail
  - target canonical graph node-set guardrail
  - migration-mode legacy mapping guardrail
  - router map baseline guardrail
  - forbidden registered-node drift guardrail
  - Phase 58 final no-debt marker
affects: [phase-52, phase-53, phase-54, phase-55, phase-56, phase-57, phase-58]

tech-stack:
  added: []
  patterns: [source-verified architecture tests]

key-files:
  created:
    - tests/architecture/test_canonical_graph_baseline.py
  modified: []

key-decisions:
  - "Treat `generate_recommendation -> recommendation_generation` as mandatory migration matrix coverage independent of vocabulary completeness."
  - "Keep final exact target equality as a skipped Phase 58 marker until runtime cutover completes."

patterns-established:
  - "Guard forbidden helper/lifecycle names by parsing actual `builder.add_node(...)` registrations."
  - "Test current runtime facts and target contract facts separately."

requirements-completed: [CAGM-02]

duration: 8min
completed: 2026-07-06
---

# Phase 51 Plan 02 Summary

**Canonical graph architecture tests for current nodes, target nodes, migration mapping, route maps, forbidden drift, and Phase 58 no-debt scope**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-07-06T05:42:00Z
- **Completed:** 2026-07-06T05:50:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added focused architecture tests for the current 14-node source graph baseline.
- Added target 15-node graph set checks that keep helper/lifecycle names out of the final canonical graph.
- Added migration-mode checks that require all active legacy nodes to have explicit target mappings and owner phases.
- Added exact conditional-edge map tests, including canonical route labels that currently map to legacy destinations.
- Added router return-value coverage checks so route labels returned by deterministic routers must be covered by registered path maps.
- Added forbidden registered-node drift checks and a skipped Phase 58 final no-debt marker.

## Task Commits

1. **Task 1-2: Canonical graph baseline guardrails** - `f3ce778` (`test(51-02): add canonical graph baseline guardrails`)

## Files Created/Modified

- `tests/architecture/test_canonical_graph_baseline.py` - CAGM-02 architecture guardrail suite.

## Decisions Made

- The vocabulary gap for `generate_recommendation` is treated as a current landmine, not as a permanent requirement that vocabulary must remain missing.
- `memory_write` is forbidden only as a registered main-chain graph node; its vocabulary/runtime concept status does not fail these tests.
- Code review warnings were accepted as valid and closed by making AST parsing fail closed for unsupported graph/route shapes and by exact-asserting migration ownership metadata.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

Initial code review found warning-level guardrail false-negative risks in router return parsing, conditional-edge parser fail-open behavior, and loose migration metadata assertions. These were fixed during Phase 51 execution and re-reviewed clean.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` passed: `9 passed, 1 skipped, 1 warning`.
- `uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase34_approval_action_boundaries.py -q` passed: `23 passed, 2 skipped, 1 warning`.
- `uv run pytest tests/architecture -q` passed: `79 passed, 2 skipped, 1 warning`.
- `uv run ruff check tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py` passed.
- `git diff --check` passed.

## Next Phase Readiness

Plan 51-03 can record the guardrail coverage in the architecture debt ledger and validation artifact without claiming runtime graph migration is complete.

---
*Phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix*
*Completed: 2026-07-06*
