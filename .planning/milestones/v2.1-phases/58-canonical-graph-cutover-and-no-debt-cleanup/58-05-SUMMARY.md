---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 05
name: delete slot and memory legacy wrappers
subsystem: agent-graph-slot-memory
tags:
  - canonical-graph
  - slot-resolution
  - memory-context
  - no-debt-cleanup
dependency_graph:
  requires:
    - 58-04
  provides:
    - deleted slot and memory legacy wrapper modules
    - canonical slot-resolution direct tests
    - canonical memory-context-load direct tests
    - strict classifier proof for no active runtime slot/memory legacy wrappers
  affects:
    - src/agent/nodes
    - tests/agent
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN
    - canonical node test ownership
    - private helper ownership behind canonical graph nodes
key_files:
  created:
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-05-SUMMARY.md
  modified:
    - src/agent/nodes/slot_resolution_gate.py
    - tests/agent/test_nodes/test_slot_resolution_gate.py
    - tests/agent/test_memory_context_load.py
    - tests/agent/test_graph.py
    - tests/agent/test_session_memory_integration.py
    - tests/conftest.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
  deleted:
    - src/agent/nodes/extract_slots.py
    - src/agent/nodes/long_term_memory_retrieve.py
    - tests/agent/test_nodes/test_extract_slots.py
key_decisions:
  - Delete slot and memory compatibility wrappers outright rather than retaining public current-run aliases.
  - Move slot prompt assembly helper ownership into the canonical slot_resolution_gate module.
  - Preserve unique direct assertions in canonical test files and drop legacy metrics/output expectations.
requirements-completed:
  - CAGM-09
metrics:
  started_at: 2026-07-08T02:07:33Z
  completed_at: 2026-07-08T02:16:22Z
  duration: 8m49s
  tasks_completed: 2
  files_changed: 12
---

# Phase 58 Plan 05: Delete Slot/Memory Legacy Wrappers Summary

Slot and memory compatibility wrappers were deleted, with prompt assembly and contextual memory coverage now owned by canonical `slot_resolution_gate` and `memory_context_load` tests.

## Performance

- **Duration:** 8m49s
- **Started:** 2026-07-08T02:07:33Z
- **Completed:** 2026-07-08T02:16:22Z
- **Tasks:** 2
- **Files changed:** 12

## Accomplishments

- Deleted `src/agent/nodes/extract_slots.py` and `tests/agent/test_nodes/test_extract_slots.py`.
- Deleted `src/agent/nodes/long_term_memory_retrieve.py`.
- Internalized slot prompt assembly helpers in `src/agent/nodes/slot_resolution_gate.py`.
- Migrated bounded candidate hint and prompt assembly assertions into `tests/agent/test_nodes/test_slot_resolution_gate.py`.
- Migrated memory no-query case-memory skip coverage into `tests/agent/test_memory_context_load.py`.
- Retargeted directly affected fixtures/tests to canonical slot and memory modules.
- Recorded required architecture-debt and local-validation ledger entries in Chinese.

## Task Commits

Each task used RED/GREEN commits:

1. **Task 1 RED: slot deletion guard** - `0b24143` (`test`)
2. **Task 1 GREEN: delete slot legacy wrapper** - `72b2a7d` (`feat`)
3. **Task 2 RED: memory deletion guard** - `d60cef7` (`test`)
4. **Task 2 GREEN: delete memory legacy wrapper** - `7a19ef3` (`feat`)

## Files Created/Modified

- `src/agent/nodes/slot_resolution_gate.py` - Owns slot prompt assembly helpers directly.
- `tests/agent/test_nodes/test_slot_resolution_gate.py` - Canonical slot direct tests with migrated prompt/candidate assertions and deletion guard.
- `tests/agent/test_memory_context_load.py` - Canonical memory direct tests with legacy wrapper deletion guard and no-query case-memory skip coverage.
- `tests/agent/test_graph.py` - Retargeted direct memory wrapper import/test to `memory_context_load`.
- `tests/agent/test_session_memory_integration.py` - Retargeted prompt-context integration coverage to `slot_resolution_gate`.
- `tests/conftest.py` - Retargeted graph fixture LLM patch seam to `slot_resolution_gate`.
- `.planning/ARCHITECTURE-DEBT.md` - Records closure of slot/memory wrapper debt.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records handled Task 2 RED test setup issue.

## Deleted Files

- `src/agent/nodes/extract_slots.py`
- `src/agent/nodes/long_term_memory_retrieve.py`
- `tests/agent/test_nodes/test_extract_slots.py`

## Verification

| Command | Result |
| ------- | ------ |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_slot_resolution_gate.py -q --tb=short` | Task 1 RED: `2 failed, 8 passed`; GREEN: `10 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_session_memory_integration.py::test_slot_resolution_gate_loads_agent_runs_prompt_context_from_trusted_config -q --tb=short` | Passed: `1 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_context_load.py -q --tb=short` | Task 2 RED after setup correction: `1 failed, 5 passed`; GREEN: `6 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py::test_memory_context_load_skips_case_memory_without_query -q --tb=short` | Passed: `1 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_memory_context_load.py -q --tb=short` | Passed: `16 passed, 1 warning` |
| `test ! -e tests/agent/test_nodes/test_extract_slots.py` | Passed |
| `test ! -e src/agent/nodes/extract_slots.py && test ! -e src/agent/nodes/long_term_memory_retrieve.py && test ! -e tests/agent/test_nodes/test_extract_slots.py` | Passed |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` | Passed: `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/slot_resolution_gate.py src/agent/nodes/memory_context_load.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_memory_context_load.py tests/agent/test_graph.py tests/agent/test_session_memory_integration.py tests/conftest.py` | Passed |
| `git diff --check` | Passed |

## Decisions Made

- Deleted both wrappers outright because canonical modules own current behavior after Phases 54 and 55.
- Kept slot prompt assembly as private canonical-module support instead of introducing a new helper module.
- Removed legacy `llm_outputs["long_term_memory_retrieve"]` direct-wrapper metrics expectations from current direct tests.
- Treated remaining legacy terms as historical/projection/planning text only, proven by the strict classifier.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Retargeted broader tests that imported deleted wrappers**
- **Found during:** Task 1 and Task 2 GREEN implementation.
- **Issue:** Deleting wrappers would leave directly affected fixtures/tests importing removed modules.
- **Fix:** Retargeted `tests/conftest.py`, `tests/agent/test_session_memory_integration.py`, and `tests/agent/test_graph.py` to canonical `slot_resolution_gate` / `memory_context_load` seams.
- **Files modified:** `tests/conftest.py`, `tests/agent/test_session_memory_integration.py`, `tests/agent/test_graph.py`.
- **Verification:** Focused pytest, static import scan, strict classifier.
- **Commit:** `72b2a7d` and `7a19ef3`

**2. [Rule 2 - Project Rule] Recorded slot/memory architecture debt closure and local validation issue**
- **Found during:** Plan closeout.
- **Issue:** MOCA rules require architecture-debt ledger updates for memory/graph debt fixes, and local validation issue logging for handled validation/test setup problems.
- **Fix:** Added Chinese ledger entries to `.planning/ARCHITECTURE-DEBT.md` and `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Verification:** Manual ledger review and summary self-check passed.
- **Commit:** Final docs commit for this summary.

---

**Total deviations:** 2 auto-fixed (1 blocking import cleanup, 1 project-rule ledger update)
**Impact on plan:** Both were required to keep deleted-wrapper imports from breaking collection and to satisfy project ledger rules. No scope expansion beyond directly affected slot/memory seams and required ledgers.

## Issues Encountered

- Task 2 RED migration initially set only `active_slots["merchant_id"]`, but canonical reviewed-memory scope authority reads `extracted_slots`. The test setup was corrected before the RED commit and logged in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. Stub-pattern scan hits were existing optional defaults, empty-list/dict test assertions, or initialized collection variables; no placeholder runtime or UI data source was introduced.

## Threat Flags

None. This plan deleted compatibility wrappers and migrated tests only; it introduced no new network endpoint, auth path, file-access trust boundary, or schema migration.

## User Setup Required

None.

## Shared State

Per orchestration instruction, this plan did not update `STATE.md`, `ROADMAP.md`, or `REQUIREMENTS.md`, and did not run GSD state mutation commands.

## Next Phase Readiness

Plan 58-05 slot/memory wrapper cleanup is complete. Later Phase 58 plans can continue with routing/test import cleanup, approval retry historical compatibility, API/frontend/eval/docs projection cleanup, and final no-debt closeout.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-05-SUMMARY.md`.
- Task commits `0b24143`, `72b2a7d`, `d60cef7`, and `7a19ef3` exist in git history.
- Deleted legacy wrapper/test files are absent.
- Final plan-local pytest, strict classifier, touched-file ruff, and `git diff --check` passed.

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
