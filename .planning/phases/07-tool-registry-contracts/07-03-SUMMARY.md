---
phase: 07-tool-registry-contracts
plan: 03
subsystem: agent-tools
tags: [tool-adapters, registry, sanitization, pydantic, pytest]

requires:
  - phase: 07-01
    provides: strict tool contract models for registry metadata, invocation context, and prompt-facing results
  - phase: 07-02
    provides: caller-aware safe ToolRegistry boundary and default allowlist entries
provides:
  - Typed adapter module wrapping the four approved read/retrieval tool functions.
  - Registry default entries routed through public adapter callables.
  - Prompt-facing sanitization tests proving raw policy evidence text is excluded.
affects: [phase-07-tool-registry-contracts, phase-08-routing, phase-09-investigator]

tech-stack:
  added: []
  patterns:
    - Public adapter callables accept typed Pydantic input models plus ToolInvocationContext and delegate to existing async tools.
    - ToolRegistry default entries reuse adapter models/callables instead of duplicating forwarding logic.

key-files:
  created:
    - src/agent/tools/adapters.py
    - tests/agent/test_tools/test_tool_adapters.py
  modified:
    - src/agent/tools/registry.py
    - tests/agent/test_tools/test_registry.py

key-decisions:
  - "Keep direct tool function signatures unchanged and make adapters the compatibility layer for registry invocation."
  - "Sanitize registry success results to ToolExecutionResult.summary and evidence_refs only; raw payload data remains outside prompt-facing model dumps."

patterns-established:
  - "Adapter tests patch src.agent.tools.adapters tool imports with AsyncMock and assert exact forwarded tenant_id, user_id, role, session, and tool-specific parameters."
  - "Registry tests can patch adapter module dependencies to verify default registry entries use public adapters."

requirements-completed: [REG-06, REG-08, REG-09, TEST-01]

duration: 7min
completed: 2026-06-04
---

# Phase 07 Plan 03: Tool Adapters and Sanitization Summary

**Typed read/retrieval adapters now back the safe registry boundary while prompt-facing tool results exclude raw policy evidence text.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-04T05:57:43Z
- **Completed:** 2026-06-04T06:04:25Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `src/agent/tools/adapters.py` with `GetOrderInput`, `GetRefundCaseInput`, `GetTicketInput`, `SearchPolicyInput`, and public async adapter callables for the four approved tools.
- Updated `ToolRegistry` default entries to reuse the public adapter input models and callables, removing duplicate internal adapter forwarding.
- Added tests proving exact adapter forwarding and registry prompt-facing sanitization, including absence of raw policy evidence `text`.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing adapter forwarding tests** - `b560eae` (test)
2. **Task 1 GREEN: typed adapter module** - `623733a` (feat)
3. **Task 2 RED: failing registry sanitization/wiring test** - `fd20272` (test)
4. **Task 2 GREEN: registry routed through adapters** - `7e73a53` (feat)

## Files Created/Modified

- `src/agent/tools/adapters.py` - Typed adapter input models and async callables that delegate to existing tool functions with `ToolInvocationContext`.
- `src/agent/tools/registry.py` - Default registry entries now import adapter models and callables instead of owning duplicate adapter code.
- `tests/agent/test_tools/test_tool_adapters.py` - Adapter forwarding tests with `AsyncMock.assert_awaited_once_with(...)`.
- `tests/agent/test_tools/test_registry.py` - Sanitization test proving raw policy evidence text does not cross the prompt-facing result boundary.

## Decisions Made

- Direct tool functions remain unchanged. Existing graph nodes can keep direct calls while the registry uses adapter callables for future investigator execution.
- `ToolExecutionResult.model_dump()` remains limited to `status`, `error`, `evidence_refs`, and `summary`; raw tool payload data is not returned by registry invocation.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED commit present before adapter implementation: `b560eae`.
- GREEN commit present after RED for adapter implementation: `623733a`.
- RED commit present before registry wiring implementation: `fd20272`.
- GREEN commit present after RED for registry wiring: `7e73a53`.

## Issues Encountered

- Direct tool compatibility command with DB-backed authz cases could not complete because PostgreSQL was not listening on `localhost:5432`. The DB-free direct tool subset passed (`10 passed, 3 deselected`), confirming unchanged direct-call behavior for the mocked/unit cases.

## Verification

- `uv run pytest tests/agent/test_tools/test_tool_adapters.py tests/agent/test_tools/test_registry.py -q` - PASSED (`13 passed`, one existing LangGraph deprecation warning).
- `uv run pytest tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/test_tools/test_search_policy.py -q -k 'not forbids_other_same_tenant_merchant'` - PASSED (`10 passed, 3 deselected`, one existing LangGraph deprecation warning).
- `uv run ruff check src/agent/tools/adapters.py src/agent/tools/registry.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_tools/test_registry.py` - PASSED.

## Stub Scan

No blocking stubs found. Matches were intentional:

- `src/agent/tools/adapters.py` uses `doc_type: str | None = None` and `risk_level: str | None = None` to preserve existing `search_policy` optional parameters.
- `tests/agent/test_tools/test_registry.py` uses empty dict defaults in local test output models and includes raw evidence text only as a negative assertion fixture.

## Threat Flags

None - the new adapter and sanitization surfaces directly implement planned mitigations T-07-07, T-07-08, and T-07-09.

## User Setup Required

None - no external service configuration required for the required plan tests.

## Next Phase Readiness

Plan 07-04 can build dormant investigation contracts and state fields on top of the now-complete contract, registry, adapter, and sanitized result boundary.

## Self-Check: PASSED

- Found `src/agent/tools/adapters.py`.
- Found `tests/agent/test_tools/test_tool_adapters.py`.
- Found `.planning/phases/07-tool-registry-contracts/07-03-SUMMARY.md`.
- Found commits `b560eae`, `623733a`, `fd20272`, and `7e73a53` in git log.

---
*Phase: 07-tool-registry-contracts*
*Completed: 2026-06-04*
