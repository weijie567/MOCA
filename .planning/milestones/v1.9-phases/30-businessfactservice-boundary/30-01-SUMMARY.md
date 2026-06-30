---
phase: 30-businessfactservice-boundary
plan: 01
subsystem: business
tags: [business-facts, pydantic, service-boundary, merchant-scope, tdd]

requires:
  - phase: 29.5-03
    provides: Phase 29.5 merchant-bound role semantics and interim raw business-read guard
provides:
  - BusinessFactResultV1 strict domain result schema
  - BusinessFactService public methods for order, refund case, ticket, logistics, merchant-risk, and fetch_context
  - No-leak service-level denied, stale, unavailable, invalid, unsupported, and not-found domain result behavior
affects: [Phase 30 Plan 02, Phase 30 Plan 03, APF-08]

tech-stack:
  added: []
  patterns:
    - Strict Pydantic domain result contracts with extra="forbid"
    - Domain service maps private adapter ToolResultV2 values into BusinessFactResultV1
    - Fail-closed no-fact/no-ref service results for denied, stale, unavailable, invalid, unsupported, and not-found reads

key-files:
  created:
    - .planning/phases/30-businessfactservice-boundary/30-01-SUMMARY.md
  modified:
    - src/business/schemas.py
    - src/business/service.py
    - src/business/__init__.py
    - tests/business/test_schemas.py
    - tests/business/test_service.py

key-decisions:
  - "BusinessFactService is introduced beside BusinessToolService; BusinessToolService remains the compatibility/tool-facing facade for later Plan 30-02 wrapping."
  - "Unsupported logistics and merchant-risk reads return typed unavailable BusinessFactResultV1 values with no facts or refs."
  - "BusinessFactService.fetch_context populates approved facts, refs, missing facts, and safe errors; ToolResultV2 compatibility wrapping remains deferred to Plan 30-02."

patterns-established:
  - "BusinessFactResultV1 is the stable domain result contract before ToolResultV2 wrapping."
  - "Adapter permission_denied/status failures are remapped into generic no-leak BusinessFactResultV1 safe errors."
  - "Domain fetch_context aggregates only ok/partial service-approved facts with non-empty refs."

requirements-completed: [APF-08]

duration: 10min
completed: 2026-06-27
---

# Phase 30 Plan 01: Domain Contract and BusinessFactService Boundary Summary

**BusinessFactResultV1 and BusinessFactService now provide the current-business-fact domain boundary before ToolPlatform compatibility wrapping.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-27T18:43:04Z
- **Completed:** 2026-06-27T18:53:16Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added strict `BusinessFactResultV1` with the normative status, freshness/version, scope-check, safe-error, and `BusinessFactRefV1` fields.
- Added `BusinessFactService` public methods for `fetch_context`, `get_order`, `get_refund_case`, `get_ticket`, `get_logistics`, and `get_merchant_risk`.
- Mapped existing order/refund/ticket adapter results into domain `BusinessFactResultV1` values with generic no-leak denial and fail-closed stale/unavailable behavior.
- Added focused tests for strict schema behavior, explicit null metadata, allowed domain facts/refs, generic denial, unsupported reads, stale doubles, and service-approved aggregation.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: BusinessFactResultV1 schema tests** - `95e2b90` (test)
2. **Task 1 GREEN: BusinessFactResultV1 schema and exports** - `367b0ec` (feat)
3. **Task 2 RED: BusinessFactService boundary tests** - `87b7f1a` (test)
4. **Task 2 GREEN: BusinessFactService boundary** - `0362476` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/business/schemas.py` - Adds strict `BusinessFactResultV1` while preserving `BusinessContextV1` compatibility exports.
- `src/business/service.py` - Adds `BusinessFactService` beside `BusinessToolService` and maps private adapter reads into domain results.
- `src/business/__init__.py` - Exports `BusinessFactResultV1` and `BusinessFactService`.
- `tests/business/test_schemas.py` - Covers schema statuses, strict fields, explicit null metadata, and business-ref/evidence separation.
- `tests/business/test_service.py` - Covers service allow/deny/no-leak/unavailable/stale/fetch_context domain behavior.

## Decisions Made

- Kept `BusinessToolService` untouched as the current compatibility facade; Plan 30-02 owns ToolResultV2 wrapping and executor integration.
- Returned typed unavailable domain results for logistics and merchant-risk because this codebase has no real data support for those reads yet.
- Left API routes unchanged to preserve Phase 29.5 tenant-first 404 and same-tenant 403 semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fail-closed non-dict merchant scope handling**
- **Found during:** Task 2 (BusinessFactService service boundary)
- **Issue:** `ToolCallContext.merchant_scope` accepts `dict | list`, but the shared `_merchant_scope_allows(...)` helper called `.get(...)` without first verifying a dict. A list-shaped scope could raise instead of failing closed.
- **Fix:** `_merchant_scope_allows(...)` now returns `False` for non-dict scope values.
- **Files modified:** `src/business/service.py`
- **Verification:** `uv run pytest tests/business/test_schemas.py tests/business/test_service.py -q --tb=short`; focused Phase 30 regression suite.
- **Committed in:** `0362476`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix is fail-closed and directly supports the service no-leak scope boundary. No scope expansion.

## Issues Encountered

None unresolved. TDD RED failures were expected missing-symbol failures before implementation.

## Known Stubs

- `src/business/service.py:229` - `BusinessFactService.fetch_context(...)` returns `tool_results=[]` while populating approved facts, refs, missing facts, and safe errors. This is intentional because Plan 30-02 owns ToolResultV2 compatibility wrapping from domain `BusinessFactResultV1` values.

## Authentication Gates

None.

## Verification

- `uv run pytest tests/business/test_schemas.py tests/business/test_service.py -q --tb=short` - passed (`49 passed`, 1 existing LangGraph deprecation warning).
- `uv run ruff check src/business/schemas.py src/business/service.py src/business/__init__.py tests/business/test_schemas.py tests/business/test_service.py` - passed.
- `git diff --check` - passed.
- Phase 30 focused regression: `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` - passed (`160 passed`, 1 existing LangGraph deprecation warning).

## TDD Gate Compliance

- Task 1 RED commit exists before GREEN: `95e2b90` -> `367b0ec`.
- Task 2 RED commit exists before GREEN: `87b7f1a` -> `0362476`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 30-02. The domain schema and service boundary are in place; the next plan can wrap service-approved `BusinessFactResultV1` values into ToolResultV2 compatibility outputs and wire the business executor through `BusinessFactService`.

---
*Phase: 30-businessfactservice-boundary*
*Completed: 2026-06-27*

## Self-Check: PASSED

- Found summary file at `.planning/phases/30-businessfactservice-boundary/30-01-SUMMARY.md`.
- Found task commits `95e2b90`, `367b0ec`, `87b7f1a`, and `0362476` in git history.
- No unexpected tracked file deletions were detected in task commits.
