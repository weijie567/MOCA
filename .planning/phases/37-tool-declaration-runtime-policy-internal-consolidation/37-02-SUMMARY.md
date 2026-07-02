---
phase: 37-tool-declaration-runtime-policy-internal-consolidation
plan: 02
subsystem: tools
tags: [tool-runtime, failure-helper, projection, decision-events, pytest, ruff]

requires:
  - phase: 37-01
    provides: single-source tool declarations used by runtime/catalog tests
provides:
  - shared ToolRuntime._fail helper for runtime failure exits
  - structural coverage for runtime failure helper usage
  - low-payload runtime-auth event regression using captured redacted_payload
affects: [phase-37, phase-38, tool-runtime, tool-platform, replay-events]

tech-stack:
  added: []
  patterns:
    - shared async failure helper assembling safe result, projection, decision event, and return tuple
    - monkeypatched decision-event capture for non-DB redaction regression

key-files:
  created:
    - .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-02-SUMMARY.md
  modified:
    - src/tools/runtime.py
    - tests/tools/test_tool_platform.py
    - tests/replay/test_tool_policy_events.py

key-decisions:
  - "Keep descriptor-missing handling as a not_found decision path, while enforcing input validation before runtime_auth for descriptor-present invocations."
  - "Keep _safe_denial_result(decision) as the policy-denial mapping source and pass its result through _fail(result=...)."
  - "Do not mark global TPH-04 complete until 37-03 lands the declarative runtime_auth gate sequence and final sweep."

patterns-established:
  - "Runtime failure exits should return await self._fail(...) instead of duplicating safe_result/projection/event tuple assembly."
  - "Runtime-auth replay payload tests should inspect actual redacted_payload dictionaries, not broad source substrings."

requirements-completed: [TPH-04]

duration: 6 min
completed: 2026-07-02
---

# Phase 37 Plan 02: Runtime Failure Helper Summary

**Runtime failure exits now share one helper that assembles safe results, projections, decision events, and return tuples.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-02T00:12:37Z
- **Completed:** 2026-07-02T00:18:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added structural regression coverage requiring `ToolRuntime._fail` and at least seven `await self._fail(` calls from `ToolRuntime.invoke`.
- Added non-DB behavior coverage proving invalid-input and missing-tool failures still produce `ToolResultProjectionV1` and do not leak `RAW-RUNTIME-SENTINEL`.
- Added runtime-auth event redaction coverage by monkeypatching `emit_decision_event` and inspecting the actual `redacted_payload` dict.
- Refactored descriptor missing, invalid input, policy denial, executor unavailable, executor exception, invalid executor response, and output schema failure paths through `_fail(...)`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add runtime helper and event payload regression tests** - `87d506f` (test)
2. **Task 2: Refactor all ToolRuntime failure exits through _fail** - `e9d09e0` (refactor)

## Files Created/Modified

- `src/tools/runtime.py` - Adds `_fail(...)` and routes seven runtime failure exits through it while preserving the success path.
- `tests/tools/test_tool_platform.py` - Adds helper structural coverage and failure-projection redaction coverage.
- `tests/replay/test_tool_policy_events.py` - Adds actual runtime-auth `redacted_payload` key regression without broad `"data"` substring checks.

## Decisions Made

- Kept `_safe_denial_result(decision)` as the single policy-denial status/code/source mapper.
- Kept `_emit_decision_event(...)` payload keys unchanged: decision metadata only, including valid `data_classification`.
- Kept `ToolRuntime.invoke` success behavior outside `_fail(...)`.
- Treated TPH-04 as partially delivered by this plan; global requirement status remains pending until 37-03 completes the policy gate sequence.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

- The exact 37-02 focused command is blocked by local PostgreSQL absence: `48 passed, 1 warning, 14 errors`, all in DB fixture setup under `tests/conftest.py::test_engine`.
- A first ad hoc structural check for input-validation-before-runtime-auth was too broad and falsely included the descriptor-missing branch. The corrected check targets descriptor-present runtime auth and passes. Both events were recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `uv run pytest tests/tools/test_tool_platform.py::test_tool_runtime_failure_paths_use_shared_fail_helper tests/tools/test_tool_platform.py::test_tool_runtime_failure_projection_redacts_raw_sentinel_inputs tests/replay/test_tool_policy_events.py::test_tool_runtime_event_payload_source_omits_raw_descriptor_and_args -q` -> `3 passed, 1 warning`
- `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/tools/test_tool_platform.py::test_tool_runtime_failure_paths_use_shared_fail_helper tests/tools/test_tool_platform.py::test_tool_runtime_failure_projection_redacts_raw_sentinel_inputs tests/replay/test_tool_policy_events.py::test_tool_runtime_event_payload_source_omits_raw_descriptor_and_args -q` -> `32 passed, 1 warning`
- `uv run ruff check src/tools/runtime.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py` -> passed
- `uv run python -c "...runtime structural checks..."` -> `runtime structural checks passed`
- `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py -q` -> blocked by local PostgreSQL connection refusal, not product-code failure evidence

## User Setup Required

Local PostgreSQL must be installed/running and reachable at `moca:moca_dev@localhost:5432` before the exact 37-02 focused suite and Phase 37 full relevant suite can be marked fully green.

## Next Phase Readiness

Ready for `37-03-PLAN.md`. Runtime failure assembly is now centralized, so the next plan can refactor `ToolPolicyEngine.runtime_auth` gate sequencing and run the final contract/regression sweep.

---
*Phase: 37-tool-declaration-runtime-policy-internal-consolidation*
*Completed: 2026-07-02*
