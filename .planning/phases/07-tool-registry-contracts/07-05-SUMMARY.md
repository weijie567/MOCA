---
phase: 07-tool-registry-contracts
plan: 05
subsystem: agent-tools
tags: [langgraph, pydantic, tool-registry, state, testing]
requires:
  - phase: 07-02
    provides: Registry invocation boundary and caller-aware allowlist policy.
  - phase: 07-03
    provides: Tool adapters and prompt-facing result sanitization.
  - phase: 07-04
    provides: Dormant investigation state fields.
provides:
  - Strict ToolOutput status validation and wrapper schema checks.
  - Structured registry containment for output conversion failures.
  - Non-investigator side-effect policy enforcement.
  - Per-turn reset of dormant investigation fields.
affects: [phase-08-routing, phase-09-investigator, registry-runtime, graph-state]
tech-stack:
  added: []
  patterns: [TDD regression gap closure, structured registry rejection, checkpoint stale-state regression]
key-files:
  created:
    - .planning/phases/07-tool-registry-contracts/07-05-SUMMARY.md
  modified:
    - src/agent/tools/registry.py
    - src/agent/nodes/receive_request.py
    - tests/agent/test_tools/test_registry.py
    - tests/agent/test_graph.py
key-decisions:
  - "Treat adapter output as untrusted runtime data and convert malformed wrappers to structured validation_error results."
  - "Keep dormant investigation fields internal but reset them to None every graph turn to avoid checkpoint leakage."
patterns-established:
  - "Registry result conversion is guarded separately from adapter execution so malformed outputs do not escape invoke."
  - "Same-thread graph regressions seed checkpointed state to prove ephemeral fields are actually cleared."
requirements-completed: [REG-01, REG-02, REG-03, REG-04, REG-05, REG-06, REG-07, REG-08, REG-09, STATE-01, STATE-02, STATE-03, STATE-04, TEST-01]
duration: 5min
completed: 2026-06-04
---

# Phase 7 Plan 5: Gap Closure Summary

**Strict registry output validation and checkpoint-safe dormant investigation state reset for Phase 7 contracts**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-04T10:35:49Z
- **Completed:** 2026-06-04T10:41:42Z
- **Tasks:** 5
- **Files modified:** 5

## Accomplishments

- Added RED registry regressions for malformed `status="pending"`, output conversion containment, and caller-specific side-effect mismatches.
- Hardened `ToolRegistry.invoke` so malformed adapter outputs return structured `validation_error` results instead of success or uncaught exceptions.
- Added and satisfied a same-thread `MemorySaver` regression proving stale dormant investigation fields reset to `None` on the next graph turn.
- Ran focused, broad Phase 7, and Ruff verification successfully.

## Task Commits

1. **Task 1: Add registry RED regressions for malformed outputs and caller side effects** - `47ca6a5` (test)
2. **Task 2: Contain registry output conversion and enforce non-investigator side effects** - `4a3f471` (fix)
3. **Task 3: Add graph RED regression for checkpointed stale investigation state** - `fd41933` (test)
4. **Task 4: Reset dormant investigation fields in receive_request** - `3b9a244` (fix)
5. **Task 5: Run targeted Phase 7 gap-closure verification** - no code commit; verification-only task

## Files Created/Modified

- `src/agent/tools/registry.py` - Typed `ToolOutput.status`, output wrapper validation, conversion containment, and stricter caller side-effect checks.
- `src/agent/nodes/receive_request.py` - Resets `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, and `investigation_path` to `None` each turn.
- `tests/agent/test_tools/test_registry.py` - Adds malformed output and non-investigator side-effect regressions.
- `tests/agent/test_graph.py` - Adds checkpointed stale-state regression and aligns internal state assertion with reset-to-`None`.
- `.planning/phases/07-tool-registry-contracts/07-05-SUMMARY.md` - Execution summary and verification record.

## Verification

- `uv run pytest tests/agent/test_tools/test_registry.py -q` after Task 1: expected RED with 4 failures and 9 passes.
- `uv run pytest tests/agent/test_tools/test_registry.py -q` after Task 2: 13 passed, 1 warning.
- `uv run pytest tests/agent/test_graph.py -q` after Task 3: expected RED with 1 failure and 9 passes.
- `uv run pytest tests/agent/test_graph.py -q` after Task 4: 10 passed, 1 warning.
- `uv run pytest tests/agent/test_tools/test_registry.py tests/agent/test_graph.py -q`: 23 passed, 1 warning.
- `uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q --tb=short`: 69 passed, 1 warning.
- `uv run ruff check src/ tests/`: All checks passed.

## Decisions Made

- Used `ToolResultStatus` for the registry output wrapper so malformed runtime statuses are rejected by Pydantic before prompt-facing conversion.
- Required registry output schemas to inherit `ToolOutput`, preserving the wrapper contract while still allowing future specialized subclasses.
- Returned `validation_error` for output validation and conversion failures because the adapter executed but produced data outside the registry contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Contract Bug] Updated internal graph assertion for reset-to-None behavior**
- **Found during:** Task 4 (Reset dormant investigation fields in receive_request)
- **Issue:** An existing graph test asserted dormant investigation fields were absent from internal graph state, but the gap-closure contract requires `receive_request` to explicitly reset them to `None`.
- **Fix:** Changed the assertion to require all dormant investigation fields to be `None`.
- **Files modified:** `tests/agent/test_graph.py`
- **Verification:** `uv run pytest tests/agent/test_graph.py -q` passed.
- **Committed in:** `3b9a244`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The change aligns the existing graph regression with the required reset contract. No graph routing, API response schema, approval behavior, or direct tool signatures changed.

## Issues Encountered

None. The broader API regression suite passed in the current environment, so no DB sandbox fallback was needed.

## Known Stubs

None.

## Auth Gates

None.

## Threat Flags

None. The plan addressed the declared Phase 7 trust boundaries without introducing new endpoints, auth paths, file access, or schema changes.

## User Setup Required

None.

## Next Phase Readiness

Phase 7 registry and dormant-state contracts are strict enough for downstream routing and investigator execution phases. Future phases can rely on registry invocation returning structured safe errors and graph turn startup clearing dormant investigation state.

## Self-Check: PASSED

- Found `.planning/phases/07-tool-registry-contracts/07-05-SUMMARY.md`.
- Verified task commits exist: `47ca6a5`, `4a3f471`, `fd41933`, `3b9a244`.

---
*Phase: 07-tool-registry-contracts*
*Completed: 2026-06-04*
