---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 04
name: delete intent/session legacy wrappers
subsystem: agent-graph-intent-session
tags:
  - canonical-graph
  - intent-recognition
  - session-context
  - no-debt-cleanup
dependency_graph:
  requires:
    - 58-03
  provides:
    - deleted intent/session legacy wrapper modules
    - canonical direct intent/session tests
    - strict classifier proof for no active runtime legacy intent/session wrappers
  affects:
    - src/agent/nodes
    - tests/agent
    - .planning/ARCHITECTURE-DEBT.md
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN
    - canonical node test ownership
key_files:
  created:
    - tests/agent/test_nodes/test_session_context_load.py
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-04-SUMMARY.md
  modified:
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - tests/agent/test_empty_session_adapter.py
    - tests/agent/test_intent_adapter.py
    - tests/agent/test_intent_golden_contract.py
    - tests/agent/test_intent_routing.py
    - tests/agent/test_memory_evidence_boundary.py
    - tests/agent/test_nodes/test_contextual_intent_resolve.py
    - tests/conftest.py
  deleted:
    - src/agent/nodes/classify_intent.py
    - src/agent/nodes/session_memory_load.py
    - tests/agent/test_nodes/test_classify_intent.py
    - tests/agent/test_session_memory_load.py
key_decisions:
  - Delete intent/session compatibility wrappers rather than retaining internal helpers because canonical modules already own current behavior.
  - Preserve unique direct assertions in canonical test files and drop legacy-only llm output mirroring expectations.
  - Keep historical legacy strings classified by the strict classifier, not by current runtime imports or patch seams.
requirements-completed:
  - CAGM-09
metrics:
  started_at: 2026-07-08T01:48:00Z
  completed_at: 2026-07-08T02:03:24Z
  duration: 15m24s
  tasks_completed: 2
  files_changed: 14
---

# Phase 58 Plan 04: Delete Intent/Session Legacy Wrappers Summary

Intent and session compatibility wrappers were deleted, and direct tests now target canonical `contextual_intent_resolve` and `session_context_load` modules only.

## Performance

- **Duration:** 15m24s
- **Started:** 2026-07-08T01:48:00Z
- **Completed:** 2026-07-08T02:03:24Z
- **Tasks:** 2
- **Files changed:** 14

## Accomplishments

- Deleted `src/agent/nodes/classify_intent.py` and `src/agent/nodes/session_memory_load.py`.
- Deleted legacy direct tests `tests/agent/test_nodes/test_classify_intent.py` and `tests/agent/test_session_memory_load.py`.
- Migrated non-duplicative intent assertions into `tests/agent/test_nodes/test_contextual_intent_resolve.py`.
- Created `tests/agent/test_nodes/test_session_context_load.py` with migrated session-context direct coverage.
- Retargeted affected test fixtures and broader tests to canonical import/patch seams.
- Recorded the required Chinese architecture-debt and local validation entries.

## Task Commits

Each task used RED/GREEN commits:

1. **Task 1 RED: intent deletion guard** - `7a45cba` (`test`)
2. **Task 1 GREEN: delete intent legacy wrapper** - `4029e9b` (`feat`)
3. **Task 2 RED: session deletion guard** - `ac6af9c` (`test`)
4. **Task 2 GREEN: delete session legacy wrapper** - `0034a4e` (`feat`)

## Files Created/Modified

- `tests/agent/test_nodes/test_session_context_load.py` - Canonical session-context direct test suite.
- `tests/agent/test_nodes/test_contextual_intent_resolve.py` - Canonical intent direct test suite with migrated assertions.
- `tests/agent/test_intent_adapter.py` - Uses canonical `intent_result_to_state` and `contextual_intent_resolve` output.
- `tests/agent/test_intent_golden_contract.py` - Imports canonical intent state adapter.
- `tests/agent/test_intent_routing.py` - Patches canonical contextual intent module.
- `tests/agent/test_memory_evidence_boundary.py` - Removes legacy classifier patch seam.
- `tests/agent/test_empty_session_adapter.py` - Calls canonical session context node.
- `tests/conftest.py` - Patches canonical contextual intent node in graph fixture.
- `.planning/ARCHITECTURE-DEBT.md` - Records closure of intent/session wrapper debt.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records handled Task 2 RED expectation mismatch.

## Deleted Files

- `src/agent/nodes/classify_intent.py`
- `src/agent/nodes/session_memory_load.py`
- `tests/agent/test_nodes/test_classify_intent.py`
- `tests/agent/test_session_memory_load.py`

## Verification

| Command | Result |
| ------- | ------ |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_intent_adapter.py -q --tb=short` | Task 1 RED: `1 failed, 5 passed`; GREEN: `19 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_session_context_load.py -q --tb=short` | Task 2 RED after test correction: `1 failed, 11 passed`; GREEN: `12 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_session_context_load.py tests/agent/test_intent_adapter.py -q --tb=short` | Passed: `31 passed, 1 warning` |
| `test ! -e tests/agent/test_nodes/test_classify_intent.py && test ! -e tests/agent/test_session_memory_load.py && test ! -e src/agent/nodes/classify_intent.py && test ! -e src/agent/nodes/session_memory_load.py` | Passed |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` | Passed: `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_empty_session_adapter.py -q --tb=short` | Passed: `1191 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/session_context_load.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_session_context_load.py tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_empty_session_adapter.py tests/conftest.py` | Passed |
| `git diff --check` | Passed |

## Decisions Made

- Deleted wrappers outright; no helper needed to move because canonical modules already owned behavior.
- Did not preserve `llm_outputs["intent_classification"]` mirror assertions because that was legacy wrapper compatibility, not canonical current-runtime behavior.
- Kept legacy `session_memory` and `session_memory_bundle` output fields where canonical `session_context_load` still intentionally emits them; only the legacy wrapper module/test entrypoint was removed in this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Retargeted broader tests that imported deleted wrappers**
- **Found during:** Task 1 and Task 2 GREEN implementation.
- **Issue:** Deleting wrappers would leave broader tests and fixtures importing removed modules.
- **Fix:** Moved affected imports/patch seams to `src.agent.nodes.contextual_intent_resolve` and `src.agent.nodes.session_context_load`.
- **Files modified:** `tests/conftest.py`, `tests/agent/test_intent_routing.py`, `tests/agent/test_intent_golden_contract.py`, `tests/agent/test_memory_evidence_boundary.py`, `tests/agent/test_empty_session_adapter.py`.
- **Verification:** Focused pytest, broader retargeted pytest, import scan, strict classifier.
- **Commit:** `4029e9b` and `0034a4e`

**2. [Rule 2 - Project Rule] Recorded closed subsystem architecture debt**
- **Found during:** Plan closeout.
- **Issue:** MOCA rules require architecture-debt ledger updates when intent/memory subsystem debt is fixed.
- **Fix:** Added a Chinese Phase 58-04 entry documenting wrapper deletion, evidence, verification, and residual historical-text risk.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Manual ledger review and strict classifier remained green.
- **Commit:** Final docs commit for this summary.

---

**Total deviations:** 2 auto-fixed (1 blocking import cleanup, 1 project-rule ledger update)
**Impact on plan:** Both were required to keep the codebase collectable and compliant after the planned deletions. No scope expansion beyond directly affected wrapper import seams and required ledgers.

## Issues Encountered

- Task 2 RED migration initially copied a service-error fallback expectation too narrowly. The canonical path may still report `source="empty_adapter"` while preserving fail-closed semantics. The test was corrected before the RED commit, and the incident was logged in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. Stub-pattern scan hits were existing test assertions for empty lists/dicts and optional/default values; no placeholder runtime or UI data source was introduced.

## Threat Flags

None. This plan deleted compatibility wrappers and migrated tests only; it introduced no new network endpoint, auth path, file-access trust boundary, or schema migration.

## User Setup Required

None.

## Shared State

Per orchestration instruction, this plan did not update `STATE.md`, `ROADMAP.md`, or `REQUIREMENTS.md`, and did not run GSD state mutation commands.

## Next Phase Readiness

Plan 58-04 intent/session wrapper cleanup is complete. Later Phase 58 plans can continue with slot, long-term-memory, approval retry, API/frontend/eval/docs, and final no-debt closeout surfaces.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-04-SUMMARY.md`.
- Created canonical test file exists at `tests/agent/test_nodes/test_session_context_load.py`.
- Deleted legacy wrapper/test files are absent.
- Task commits `7a45cba`, `4029e9b`, `ac6af9c`, and `0034a4e` exist in git history.
- `git diff --check` passed before final docs commit.

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
