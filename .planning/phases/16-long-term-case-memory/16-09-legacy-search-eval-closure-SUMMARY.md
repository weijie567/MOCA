---
phase: 16-long-term-case-memory
plan: 09
subsystem: memory-tools
tags: [case-memory, tools, legacy-search, coverage, eval-closure]

requires:
  - phase: 16-06-reviewed-case-memory
    provides: reviewed case memory retrieval service
  - phase: 16-08-memory-retrieval-integration
    provides: reviewed memory graph and prompt integration
provides:
  - planner-visible search_case_memory backed by reviewed case memory
  - legacy session-derived precedent search quarantined as debug/legacy only
  - Phase 16 requirement coverage manifest and coverage test
  - final Phase 16 execution summary with focused and full-suite results
affects: [tools, memory, phase-16-verification]

key-files:
  created:
    - .planning/phases/16-long-term-case-memory/16-COVERAGE.md
    - .planning/phases/16-long-term-case-memory/16-SUMMARY.md
    - tests/memory/test_phase16_requirement_coverage.py
  modified:
    - src/tools/catalog.py
    - src/tools/executors/memory.py
    - src/tools/manager.py
    - src/agent/events.py
    - tests/tools/test_catalog.py
    - tests/agent/test_policy_retrieval_ownership.py
    - tests/agent/test_tools/test_unified_tool_manager.py
    - tests/memory/test_session_precedent_search.py
    - tests/agent/test_memory_evidence_boundary.py
    - tests/approvals/test_migration_contract.py
    - tests/replay/test_memory_foundation_alignment.py
    - .planning/phases/16-long-term-case-memory/16-VALIDATION.md

requirements-completed: [CASEMEM-03, CASEMEM-02, MEMCTX-02, MEMREVIEW-01, MEMEVAL-01]

duration: 24 min implementation plus 9 min full-suite gate
completed: 2026-06-18
---

# Phase 16 Plan 09: Legacy Search Transition And Eval Closure Summary

Planner-visible `search_case_memory` now routes to reviewed case memory, while the old session-derived precedent behavior is legacy/debug-only. Phase 16 now has a coverage manifest, coverage test, validation update, and final phase summary.

## Task Commits

1. **Task 16-09-01: Add legacy search transition tests** - `fc18bca` (test)
2. **Task 16-09-02: Implement reviewed search_case_memory transition** - `ae7bc0b` (feat)
3. **Task 16-09-03: Preserve retrieval event classification** - `604ba11` (test)
4. **Full-suite stale guard fix** - `419b935` (test)
5. **Task 16-09-04: Coverage and eval closure artifacts** - final docs/test commit for this summary

## Verification

- `uv run pytest tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_tools/test_unified_tool_manager.py tests/memory/test_session_precedent_search.py -q` - passed, 55 tests.
- `uv run pytest tests/memory/test_memory_schema.py tests/conversation/test_models.py -q` - passed, 17 tests.
- `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/memory/test_phase16_requirement_coverage.py -q` - passed, 114 tests.
- `uv run pytest -q` - passed, 974 tests, 6 warnings, 511.65s.

## Deviations From Plan

The full-suite gate initially failed on two stale cross-phase tests unrelated to the new reviewed-memory behavior. Commit `419b935` updated those tests:

- Phase 13 migration report lookup now accepts the archived v1.1 artifact path.
- Phase 15.1 memory-foundation alignment now continues to guard Phase 15.1 and Phase 17 scope while allowing Phase 16 memory tables to exist after Phase 16 execution.

## Known Stubs

None.

## Self-Check: PASSED

- Coverage manifest exists and lists all 14 Phase 16 requirement IDs.
- `tests/memory/test_phase16_requirement_coverage.py` validates manifest rows and commands.
- Full suite passed after stale cross-phase guard update.

