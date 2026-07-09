---
phase: 62-business-query-and-drilldown-foundation
plan: 04
subsystem: business-query-runtime
tags: [business-query, business-fact-service, tool-platform, investigate, tdd]

requires:
  - phase: 62-business-query-and-drilldown-foundation
    plan: 03
    provides: trusted business_query ToolPlatform descriptor and policy boundary
provides:
  - BusinessFactService-owned business_query runtime for aggregate, list, detail, breakdown, and compare
  - registry-backed SQLAlchemy statement compiler without raw SQL or generic list helpers
  - ToolPlatform business_query dispatch through BusinessToolExecutor and BusinessToolService
  - investigate business_context accumulation for fact["business_query"] with business_metric compatibility preserved
  - static architecture backstops for agent/executor/compiler ownership boundaries
affects: [business-query-runtime, business-fact-service, tool-platform, investigate, phase-62]

tech-stack:
  added: []
  patterns:
    - BusinessQueryCompiler compiles only registry-owned query shapes into SQLAlchemy select statements
    - BusinessFactService returns stable fact["business_query"] envelope for downstream drilldown projection
    - ToolPlatform validates the business_query fact envelope, not raw executor dictionaries

key-files:
  created:
    - src/business/query/compiler.py
    - tests/business/test_business_query_service.py
    - tests/architecture/test_business_query_boundaries.py
    - .planning/phases/62-business-query-and-drilldown-foundation/62-04-SUMMARY.md
  modified:
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - src/business/query/__init__.py
    - src/business/service.py
    - src/tools/contracts.py
    - src/tools/executors/business.py
    - src/tools/catalog.py
    - src/agent/nodes/investigate.py
    - tests/business/test_service.py
    - tests/tools/test_tool_platform.py
    - tests/tools/test_catalog.py
    - tests/agent/test_nodes/test_investigate.py

key-decisions:
  - "Keep business_query compilation and execution inside BusinessFactService/BusinessQueryCompiler; investigate and ToolPlatform do not build SQL or import repositories."
  - "Use fact[\"business_query\"] as the stable runtime envelope for ToolResultV2.data and downstream drilldown consumers."
  - "Preserve query_business_metric as a compatibility tool by validating legacy metric input, converting to BusinessQuerySpec, delegating to query_business, then rehydrating the old business_metric result shape."
  - "Update the business_query ToolCatalog output schema to validate the fact envelope produced by the runtime."

patterns-established:
  - "No-existence-leak detail queries sanitize out-of-scope resource ids before returning empty business_query results."
  - "business_query list queries fetch limit+1 within trusted merchant scope before producing opaque cursor metadata."
  - "Architecture tests protect the service/compiler ownership boundary from future agent or executor coupling."

requirements-completed: [BQ-62-03, BQ-62-04, BQ-62-08]

duration: 28 min
completed: 2026-07-09
---

# Phase 62 Plan 04: Business Query Runtime Service Summary

**BusinessFactService-owned `business_query` runtime with controlled compiler, ToolPlatform dispatch, investigate accumulation, and static boundary backstops**

## Performance

- **Duration:** 28 min
- **Started:** 2026-07-09T13:48:22Z
- **Completed:** 2026-07-09T14:16:05Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- Added `BusinessQueryCompiler` for registry-owned aggregate, list, detail, breakdown, and compare query shapes using SQLAlchemy `select()` statements only.
- Added `BusinessFactService.query_business(...)` with trusted merchant scope derivation, safe no-existence-leak detail behavior, cursor-safe list execution, and stable `fact["business_query"]` output.
- Reworked `query_business_metric(...)` into a compatibility path that delegates through the new business_query runtime while preserving existing `business_metric` result consumers.
- Wired `business_query` through `BusinessToolExecutor` and `BusinessToolService`; removed the 62-03 deferred unavailable executor path.
- Updated investigate accumulation so `business_context.facts["business_query"]` carries the service-normalized payload, while `business_metric` compatibility remains intact.
- Added static architecture tests that prevent agent/executor layers from importing service/compiler/repository/DB dependencies or introducing raw SQL/generic list helpers.

## Task Commits

1. **Task 1 RED: Service runtime tests** - `204b2db` (test)
2. **Task 1 GREEN: Business query runtime** - `8b553e8` (feat)
3. **Task 2 RED: ToolPlatform/investigate dispatch tests** - `b23e98d` (test)
4. **Task 2 GREEN: business_query dispatch and envelope validation** - `a195dec` (feat)
5. **Task 3: Static ownership backstops** - `cd74138` (test)

**Plan metadata:** included in the final docs/state commit for this plan.

## Files Created/Modified

- `src/business/query/compiler.py` - New compiler for controlled BusinessQuerySpec query shapes.
- `src/business/query/__init__.py` - Exports compiler/runtime query types.
- `src/business/service.py` - Adds `query_business`, compiler execution paths, safe result conversion, and metric compatibility delegation.
- `src/tools/contracts.py` - Adds `business_query` as an allowed `BusinessFactRefV1.resource_type`.
- `src/tools/executors/business.py` - Delegates all business tool calls, including `business_query`, through `BusinessToolService`.
- `src/tools/catalog.py` - Validates the `{"business_query": BusinessQueryResultV1}` ToolResultV2 data envelope.
- `src/agent/nodes/investigate.py` - Accumulates business_query payloads under `business_context.facts["business_query"]`.
- `tests/business/test_business_query_service.py` - Covers aggregate/list/detail/breakdown/compare, scope, cursor, no-leak, and compiler safety behavior.
- `tests/business/test_service.py` - Updates metric compatibility tests for the new delegated path.
- `tests/tools/test_tool_platform.py` - Covers business_query runtime dispatch through ToolPlatform.
- `tests/tools/test_catalog.py` - Covers business_query output envelope schema.
- `tests/agent/test_nodes/test_investigate.py` - Covers business_query fact accumulation and metric compatibility.
- `tests/architecture/test_business_query_boundaries.py` - Adds static ownership guards.
- `.planning/ARCHITECTURE-DEBT.md` - Records verified runtime/executor boundary fixes and remaining downstream projection risks.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records handled local validation failures from Task 2/3.

## Decisions Made

- Kept all compilation in `BusinessQueryCompiler` and all execution in `BusinessFactService`; graph nodes remain ToolPlatform callers only.
- Kept `query_business_metric` as a compatibility surface instead of forcing immediate downstream migration to `business_query`.
- Treated the ToolCatalog output schema mismatch as a Rule 1 bug because ToolPlatform validates `ToolResultV2.data`, which is now the stable `fact["business_query"]` envelope.
- Did not modify `src/business/adapters.py`; the planned runtime work did not need adapter changes after service/compiler ownership was added.

## TDD Gate Compliance

- Task 1 RED commit present: `204b2db`; focused suite failed as expected with missing `src.business.query.compiler`.
- Task 1 GREEN commit present after RED: `8b553e8`; business service/runtime suite passed.
- Task 2 RED commit present: `b23e98d`; focused suite failed as expected on deferred `business_query` runtime and missing `business_query` fact accumulation.
- Task 2 GREEN commit present after RED: `a195dec`; tool/agent/catalog suite passed after fixing the envelope schema mismatch.
- Task 3 RED command failed before the backstop file existed; after adding static tests, the code already satisfied the required boundaries from Tasks 1/2, so the task landed as a test-only backstop commit `cd74138`.
- REFACTOR commits: not needed.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/business/test_service.py -q --tb=short` -> Task 1 GREEN: `57 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/compiler.py src/business/query/__init__.py src/business/service.py src/tools/contracts.py tests/business/test_business_query_service.py tests/business/test_service.py` -> `All checks passed!`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py -q --tb=short` -> Task 2 RED: `2 failed, 104 passed, 1 warning`; expected failures
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/tools/test_catalog.py -q --tb=short` -> Task 2 GREEN: `155 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_business_query_boundaries.py -q --tb=short` -> Task 3 GREEN: `4 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/business/test_service.py tests/tools/test_tool_platform.py tests/tools/test_catalog.py tests/agent/test_nodes/test_investigate.py tests/architecture/test_business_query_boundaries.py -q --tb=short` -> `216 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/compiler.py src/business/query/__init__.py src/business/service.py src/tools/contracts.py src/tools/executors/business.py src/tools/catalog.py src/agent/nodes/investigate.py tests/business/test_business_query_service.py tests/business/test_service.py tests/tools/test_tool_platform.py tests/tools/test_catalog.py tests/agent/test_nodes/test_investigate.py tests/architecture/test_business_query_boundaries.py .planning/ARCHITECTURE-DEBT.md .planning/LOCAL-VALIDATION-ISSUES.md` -> `All checks passed!`
- `rg -n "async def query_business|BusinessQueryCompiler|metric_input_to_business_query" src/business/service.py src/business/query/compiler.py` -> required runtime symbols found
- `rg -n "business_query|query_business" src/tools/executors/business.py src/business/adapters.py src/agent/nodes/investigate.py` -> investigate business_query accumulation path found; executor delegates through `invoke_tool` without a special deferred branch

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Contract Functionality] Added `business_query` BusinessFactRef resource type**
- **Found during:** Task 1 GREEN implementation
- **Issue:** `BusinessFactResultV1` could return `fact["business_query"]`, but `BusinessFactRefV1.resource_type` did not allow `business_query`, preventing the stable fact ref contract from validating.
- **Fix:** Added `business_query` to the allowed business fact ref resource types.
- **Files modified:** `src/tools/contracts.py`
- **Verification:** Task 1 service suite passed.
- **Committed in:** `8b553e8`

**2. [Rule 1 - Bug] Fixed ToolCatalog output schema mismatch for runtime envelope**
- **Found during:** Task 2 GREEN verification
- **Issue:** After connecting `business_query` runtime, ToolRuntime output validation returned `invalid_response` because `src/tools/catalog.py` still expected the inner `BusinessQueryResultV1` directly instead of `{"business_query": BusinessQueryResultV1}`.
- **Fix:** Updated the descriptor output schema and catalog tests to validate the stable fact envelope.
- **Files modified:** `src/tools/catalog.py`, `tests/tools/test_catalog.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Task 2 suite passed with `155 passed, 1 warning`.
- **Committed in:** `a195dec`

**Total deviations:** 2 auto-fixed (1 Rule 2 contract gap, 1 Rule 1 schema bug)

## Issues Encountered

- Expected Task 1 and Task 2 RED failures occurred before implementation.
- Task 2 GREEN initially exposed the output schema mismatch above; fixed and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Task 3 first run failed due the new test passing `ToolCatalog()` where `investigate_tool_names(...)` expects descriptors; corrected and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No authentication gates or unresolved validation failures occurred.

## Known Stubs

None. Stub scan hits were normal empty containers/defaults in runtime aggregation paths, safe no-data results, and tests. No stub blocks the 62-04 business_query runtime goal.

## Threat Flags

None. The new DB read runtime is the planned BusinessFactService surface for this plan; no unplanned network endpoint, auth path, file access pattern, schema migration, or agent-owned SQL path was introduced.

## User Setup Required

None.

## Next Phase Readiness

Plan 62-05 can build drilldown derivation against the stable `fact["business_query"]` payload and ToolPlatform runtime. Plan 62-06/62-07 still need final/API/frontend projection work, which remains intentionally outside 62-04.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/62-business-query-and-drilldown-foundation/62-04-SUMMARY.md`
- Task commits found: `204b2db`, `8b553e8`, `b23e98d`, `a195dec`, `cd74138`
- No unexpected tracked file deletions were detected across the plan commits.

---
*Phase: 62-business-query-and-drilldown-foundation*
*Completed: 2026-07-09*
