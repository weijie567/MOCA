---
phase: 07-tool-registry-contracts
plan: 01
subsystem: agent-tools
tags: [pydantic, tool-registry, contracts, validation]

requires:
  - phase: 06
    provides: v1.0 deterministic LangGraph workflow and existing read/retrieval tools
provides:
  - Strict Pydantic tool contract models for registry metadata, invocation context, and prompt-facing results.
  - Contract tests proving required metadata, literal validation, investigator safety checks, and raw payload rejection.
affects: [phase-07-tool-registry-contracts, phase-08-routing, phase-09-investigator]

tech-stack:
  added: []
  patterns:
    - Pydantic v2 BaseModel contracts with Literal aliases and ConfigDict(extra="forbid")

key-files:
  created:
    - src/agent/tools/contracts.py
    - tests/agent/test_tools/test_tool_contracts.py
  modified: []

key-decisions:
  - "Use a summary dictionary inside ToolExecutionResult as the declared prompt-facing summary container while forbidding undeclared top-level and evidence-ref fields."
  - "Validate investigator-allowed registry entries fail fast unless risk and side-effect metadata are read/retrieval safe."

patterns-established:
  - "Tool contract models live in src/agent/tools/contracts.py as the canonical import point for future registry and adapter plans."
  - "Prompt-facing tool result models use extra='forbid' to prevent raw payload fields from crossing into investigator prompts."

requirements-completed: [REG-01]

duration: 5min
completed: 2026-06-04
---

# Phase 07 Plan 01: Tool Contract Models Summary

**Strict Pydantic tool contracts now enforce required registry metadata, safe literals, and prompt-facing raw payload rejection.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-04T05:03:42Z
- **Completed:** 2026-06-04T05:08:54Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `src/agent/tools/contracts.py` as the canonical tool contract module with literal aliases, invocation context, registry metadata, evidence refs, errors, and execution results.
- Enforced `extra="forbid"` on prompt-facing result models so undeclared fields like raw payloads or raw policy text fail validation.
- Added focused contract tests covering complete read/retrieval metadata, missing required fields, invalid literals, unsafe investigator metadata, and prompt-facing field rejection.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing contract tests** - `9aa824e` (test)
2. **Task 1 GREEN: strict tool contracts** - `927dd96` (feat)
3. **Task 2: strict validation proof** - `a3ba5db` (test)

## Files Created/Modified

- `src/agent/tools/contracts.py` - Canonical strict Pydantic contract module for registry metadata, invocation context, and prompt-facing tool execution results.
- `tests/agent/test_tools/test_tool_contracts.py` - Contract-layer tests for required metadata, strict literals, investigator safety validation, and unknown prompt-facing field rejection.

## Decisions Made

- `ToolExecutionResult.summary` is the declared summary-field container for future registry/adapters; top-level undeclared raw payload keys remain forbidden.
- Investigator-allowed entries validate safety consistency immediately: only read/retrieval risk levels and non-writing side effects are accepted.

## Deviations from Plan

None - plan scope executed exactly as written. The TDD flow necessarily created the contract test file during Task 1 RED, then Task 2 extended that same file with the remaining strict-validation proof cases.

## Issues Encountered

- The system `python` executable is broken due to a missing Homebrew Python framework. Verification used the project-supported `uv run python` and `uv run pytest` commands successfully.

## Verification

- `uv run pytest tests/agent/test_tools/test_tool_contracts.py -q` - PASSED (`21 passed`, one existing LangGraph deprecation warning).
- Confirmed committed code scope only touched:
  - `src/agent/tools/contracts.py`
  - `tests/agent/test_tools/test_tool_contracts.py`
- Confirmed no graph, API, or DB files were touched by this plan.

## Stub Scan

No blocking stubs found. Matches were intentional contract/test values:

- `tests/agent/test_tools/test_tool_contracts.py` uses `required_identifiers=[]` to prove retrieval tools may have no required explicit identifier.
- `src/agent/tools/contracts.py` uses `default=None` for optional evidence confidence.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 7 Plan 02 can import `ToolRegistryEntry`, `ToolInvocationContext`, and `ToolExecutionResult` from `src/agent/tools/contracts.py` to build registry validation and caller-aware invocation boundaries.

## Self-Check: PASSED

- Found `src/agent/tools/contracts.py`.
- Found `tests/agent/test_tools/test_tool_contracts.py`.
- Found commits `9aa824e`, `927dd96`, and `a3ba5db` in git log.

---
*Phase: 07-tool-registry-contracts*
*Completed: 2026-06-04*
