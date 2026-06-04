---
phase: 07-tool-registry-contracts
plan: 02
subsystem: agent-tools
tags: [tool-registry, allowlist, pydantic, safety-boundary]

requires:
  - phase: 07-01
    provides: strict tool contract models for registry metadata, invocation context, and execution results
provides:
  - Safe ToolRegistry construction with locked investigator allowlist validation.
  - Caller-aware ToolRegistry.invoke boundary returning structured rejection results.
  - Registry tests proving unsafe exclusion, fail-fast validation, and non-execution behavior.
affects: [phase-07-tool-registry-contracts, phase-08-routing, phase-09-investigator]

tech-stack:
  added: []
  patterns:
    - Dataclass RegisteredTool wraps ToolRegistryEntry metadata with async adapters.
    - ToolRegistry.invoke validates tool name, caller policy, and input schema before awaiting adapters.

key-files:
  created:
    - src/agent/tools/registry.py
    - tests/agent/test_tools/test_registry.py
  modified:
    - src/agent/tools/registry.py
    - tests/agent/test_tools/test_registry.py

key-decisions:
  - "Keep default registry adapters inside src/agent/tools/registry.py for Plan 07-02 so existing graph nodes and direct tool functions remain untouched."
  - "Use ToolExecutionResult(status='error') with not_found, unsafe_tool_request, validation_error, and tool_error codes for structured rejection results."

patterns-established:
  - "Investigator-visible registry names are checked against a locked constant set: get_order, get_refund_case, get_ticket, search_policy."
  - "Disallowed and schema-invalid invocations return ToolExecutionResult without awaiting the registered adapter."

requirements-completed: [REG-02, REG-03, REG-04, REG-05, REG-07]

duration: 7min
completed: 2026-06-04
---

# Phase 07 Plan 02: Safe Tool Registry Boundary Summary

**Caller-aware ToolRegistry now enforces the locked read/retrieval allowlist and rejects unsafe requests before adapter execution.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-04T05:12:35Z
- **Completed:** 2026-06-04T05:19:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `src/agent/tools/registry.py` with `ToolRegistry`, default registry entries for the four allowed read/retrieval tools, construction-time metadata validation, caller-aware policy checks, and structured invocation results.
- Added `tests/agent/test_tools/test_registry.py` covering exact investigator allowlist, unsafe/action/approval exclusions, invalid metadata construction failures, unknown-tool rejection, disallowed invocation rejection, schema validation rejection, and non-execution via `AsyncMock.assert_not_awaited`.
- Confirmed this plan did not touch `src/agent/graph.py`, `src/agent/nodes/`, or public API files.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing registry boundary tests** - `3fd4b86` (test)
2. **Task 1 GREEN: safe registry boundary** - `4659f64` (feat)
3. **Task 2: allowlist and non-execution proof** - `70c6092` (test)

## Files Created/Modified

- `src/agent/tools/registry.py` - Default registry definitions, metadata validation, caller-aware invoke policy, structured rejections, and safe result conversion.
- `tests/agent/test_tools/test_registry.py` - Registry safety tests for exact allowlist, unsafe exclusions, fail-fast invalid definitions, structured rejections, and mock non-execution.

## Decisions Made

- Default adapters remain in `registry.py` for this plan to avoid introducing the separate adapter module before Plan 07-03 and to keep existing graph/runtime wiring untouched.
- Structured rejection uses the existing Plan 07-01 `ToolExecutionResult` error shape rather than adding a new result status literal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Malformed registry metadata raised AttributeError instead of fail-fast ValueError**
- **Found during:** Task 2 (Prove exact allowlist, unsafe exclusion, and non-execution behavior)
- **Issue:** A deliberately incomplete `ToolRegistryEntry.model_construct(...)` without `input_schema` raised `AttributeError` during registry construction.
- **Fix:** `ToolRegistry._validate_registered_tool(...)` now uses `getattr(..., None)` for schema fields and raises a clear `ValueError` for missing Pydantic schemas.
- **Files modified:** `src/agent/tools/registry.py`
- **Verification:** `uv run pytest tests/agent/test_tools/test_registry.py -q` passed with `8 passed`.
- **Committed in:** `70c6092`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** The fix strengthens the planned REG-05 fail-fast validation behavior. No scope expansion.

## Issues Encountered

- None beyond the auto-fixed validation bug documented above.

## Verification

- `uv run pytest tests/agent/test_tools/test_registry.py -q` - PASSED (`8 passed`, one existing LangGraph deprecation warning).
- `uv run ruff check src/agent/tools/registry.py tests/agent/test_tools/test_registry.py` - PASSED.
- `git diff --name-only bef7d27..HEAD` showed only:
  - `src/agent/tools/registry.py`
  - `tests/agent/test_tools/test_registry.py`
- Confirmed no changes to `src/agent/graph.py`, node routing files under `src/agent/nodes/`, or public API files.

## Stub Scan

No blocking stubs found. Matches were intentional optional/test defaults:

- `src/agent/tools/registry.py` uses optional `doc_type` and `risk_level` defaults for `SearchPolicyInput`.
- `src/agent/tools/registry.py` uses `default_factory` for empty tool output and evidence ref containers.
- `tests/agent/test_tools/test_registry.py` uses empty dict defaults in a local test helper output model.

## Threat Flags

None - the new registry invocation boundary and fail-fast validation are exactly the threat mitigations planned for T-07-04, T-07-05, and T-07-06.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 07-03 can add dedicated typed adapters and sanitization tests on top of the `ToolRegistry.invoke(...)` shape without changing existing graph nodes.

## Self-Check: PASSED

- Found `src/agent/tools/registry.py`.
- Found `tests/agent/test_tools/test_registry.py`.
- Found `.planning/phases/07-tool-registry-contracts/07-02-SUMMARY.md`.
- Found commits `3fd4b86`, `4659f64`, and `70c6092` in git log.

---
*Phase: 07-tool-registry-contracts*
*Completed: 2026-06-04*
