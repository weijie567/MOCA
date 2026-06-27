---
phase: 30-businessfactservice-boundary
plan: 02
subsystem: business
tags: [business-facts, tool-platform, service-boundary, no-leak, tdd]

requires:
  - phase: 30-01
    provides: BusinessFactResultV1 schema and BusinessFactService domain boundary
provides:
  - BusinessToolService compatibility wrapper over BusinessFactService
  - BusinessFactResultV1 to ToolResultV2 deterministic status/error mapping
  - BusinessToolExecutor default delegation through BusinessFactService
  - ToolPlatform tests for service-approved refs and domain-scope marker enforcement
  - No-leak ToolPolicyEngine domain identifier binding redaction
affects: [Phase 30 Plan 03, APF-08, ToolPlatform, investigate]

tech-stack:
  added: []
  patterns:
    - Compatibility facade wraps domain BusinessFactResultV1 values into ToolResultV2
    - ToolPlatform policy binding carries domain proof marker without raw business identifiers
    - Unsupported catalog business reads return safe unavailable no-fact/no-ref results

key-files:
  created:
    - .planning/phases/30-businessfactservice-boundary/30-02-SUMMARY.md
  modified:
    - src/business/service.py
    - src/tools/executors/business.py
    - src/tools/policy.py
    - tests/business/test_service.py
    - tests/tools/test_tool_platform.py

key-decisions:
  - "BusinessToolService remains the source-compatible facade, but current business fact authority now flows through BusinessFactService."
  - "BusinessToolExecutor constructs BusinessFactService explicitly and wraps it with BusinessToolService for ToolResultV2 compatibility."
  - "ToolPolicyEngine keeps requires_domain_scope_check for order/refund/ticket identifiers but redacts the identifier values from ToolInvocationOutcome serialization."

patterns-established:
  - "Domain result wrapping: ok/partial domain results become success/partial_success ToolResultV2 with service-approved refs only."
  - "Fail-closed wrapping: permission_denied/stale/unavailable/invalid/not_found domain results emit no data, no business refs, and no policy evidence refs."
  - "ToolPlatform chain tests prove runtime auth allows dispatch while BusinessFactService performs domain proof before facts/refs."

requirements-completed: [APF-08]

duration: 10min
completed: 2026-06-28
---

# Phase 30 Plan 02: BusinessFactService ToolPlatform Compatibility Summary

**BusinessToolService and BusinessToolExecutor now route ToolPlatform business reads through BusinessFactService with no-leak ToolResultV2 wrapping.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-27T19:05:44Z
- **Completed:** 2026-06-27T19:15:31Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Converted `BusinessToolService` into a compatibility facade over `BusinessFactService`.
- Added deterministic `BusinessFactResultV1` to `ToolResultV2` wrapping for success, partial, denied, stale, unavailable, invalid, and not-found statuses.
- Updated `BusinessToolExecutor` so default ToolPlatform business reads are built from `BusinessFactService`.
- Added ToolPlatform chain tests proving order/refund/ticket reads carry `requires_domain_scope_check`, emit exactly one service-approved ref on allow, and emit no facts/refs on service denial.
- Redacted order/refund/ticket identifier values from ToolPolicyEngine resource bindings while preserving the domain-scope proof marker.

## Task Commits

Each TDD task was committed atomically:

1. **Task 1 RED: compatibility wrapper tests** - `a280bfb` (test)
2. **Task 1 GREEN: BusinessToolService wraps BusinessFactService results** - `6824258` (feat)
3. **Task 2 RED: ToolPlatform service-boundary tests** - `52a0959` (test)
4. **Task 2 GREEN: BusinessToolExecutor delegates through BusinessFactService** - `f009b4d` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/business/service.py` - Makes `BusinessToolService` delegate to `BusinessFactService` and wrap domain results into safe `ToolResultV2` envelopes.
- `src/tools/executors/business.py` - Constructs default executor service through `BusinessFactService` and keeps executor dispatch thin.
- `src/tools/policy.py` - Redacts domain-lookup identifier values from marker bindings while keeping `requires_domain_scope_check`.
- `tests/business/test_service.py` - Pins compatibility wrapping, no-leak failure mapping, unsupported catalog reads, and preserved adapter raw-discard behavior.
- `tests/tools/test_tool_platform.py` - Adds ToolPlatform chain coverage for service-approved refs, marker enforcement, denial no-leak, and unsupported reads.

## Decisions Made

- Kept ToolPlatform descriptor, caller, permission, schema, side-effect, approval, and idempotency gates outside BusinessFactService.
- Kept raw demo adapters private and unchanged; no `src/business/adapters.py` edit was required.
- Preserved old `fetch_context` not-found safe error codes for compatibility while direct denied/stale/unavailable wrappers use generic no-leak messages.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Redacted domain lookup identifiers from ToolPolicyEngine bindings**
- **Found during:** Task 2 (ToolPlatform service-boundary RED tests)
- **Issue:** `requires_domain_scope_check` was present, but `resource_scope_binding` also serialized `order_no`, `refund_case_no`, or `ticket_id`, which could leak denied identifiers through `ToolInvocationOutcome`.
- **Fix:** For order/refund/ticket domain lookup identifiers, `ToolPolicyEngine` now records only `requires_domain_scope_check=True`; explicit `merchant_id` runtime scope checks are unchanged.
- **Files modified:** `src/tools/policy.py`
- **Verification:** `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/tools/test_tool_platform.py -q --tb=short`; ruff including `src/tools/policy.py`; `git diff --check`.
- **Committed in:** `f009b4d`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The deviation tightens the planned no-leak boundary without moving ToolPlatform authorization responsibilities into BusinessFactService. No Phase 31+ scope was added.

## Issues Encountered

- Task 1 GREEN initially dropped the adapter not-found safe error code in `BusinessToolService.fetch_context(...)`; this was corrected so compatibility aggregation still sees the old safe code while direct domain wrappers stay generic.
- Task 2 RED failures were expected TDD failures for executor source integration and domain marker redaction.

## Known Stubs

- `src/business/service.py:229` - `BusinessFactService.fetch_context(...)` still returns `tool_results=[]`. This remains intentional for the domain service because compatibility `ToolResultV2` wrapping now lives in `BusinessToolService.fetch_context(...)`; Plan 30-03 can consume the compatibility/tool path without requiring domain service tool envelopes.

## Authentication Gates

None.

## Verification

- `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/tools/test_tool_platform.py -q --tb=short` - passed (`63 passed`, 1 existing LangGraph deprecation warning).
- `uv run ruff check src/business/service.py src/tools/executors/business.py tests/business/test_service.py tests/business/test_adapters.py tests/tools/test_tool_platform.py` - passed.
- Additional changed-file lint: `uv run ruff check src/business/service.py src/tools/executors/business.py src/tools/policy.py tests/business/test_service.py tests/business/test_adapters.py tests/tools/test_tool_platform.py` - passed.
- `git diff --check` - passed.

## TDD Gate Compliance

- Task 1 RED commit exists before GREEN: `a280bfb` -> `6824258`.
- Task 2 RED commit exists before GREEN: `52a0959` -> `f009b4d`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 30-03. ToolPlatform business reads now reach facts through BusinessFactService and emit service-approved refs only after domain proof; Plan 30-03 can focus on graph/projection/authority-boundary verification without starting Wave 3 here.

---
*Phase: 30-businessfactservice-boundary*
*Completed: 2026-06-28*

## Self-Check: PASSED

- Found summary file at `.planning/phases/30-businessfactservice-boundary/30-02-SUMMARY.md`.
- Found task commits `a280bfb`, `6824258`, `52a0959`, and `f009b4d` in git history.
- Found all key created/modified files referenced by this summary.
- No unexpected tracked file deletions were detected in task commits.
