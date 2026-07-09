---
phase: 62-business-query-and-drilldown-foundation
plan: 03
subsystem: tool-platform-business-query
tags: [business-query, tool-platform, trusted-context, permissions, tdd]

requires:
  - phase: 62-business-query-and-drilldown-foundation
    plan: 02
    provides: registry-backed BusinessQuerySpec and BusinessQueryResultV1 contracts
provides:
  - trusted business:query to tool:business_query permission projection
  - read-only business_query ToolCatalog descriptor with strict registry/schema-derived input and output shape
  - ToolPlatform policy tests for caller, permission, authority-field, raw SQL, arbitrary filter, and raw cursor denial before dispatch
  - safe deferred business_query executor behavior pending 62-04 runtime execution
affects: [business-query-runtime, tool-platform-policy, trusted-context, investigate-planner, phase-62]

tech-stack:
  added: []
  patterns:
    - trusted OAuth/app scope mapped one-to-one to tool permission
    - ToolCatalog descriptor schema derived from BusinessQuerySpec, BusinessQueryResultV1, and BUSINESS_QUERY_REGISTRY
    - executor-level safe deferred unavailable result for planned-but-not-runtime-connected tools

key-files:
  created:
    - .planning/phases/62-business-query-and-drilldown-foundation/62-03-SUMMARY.md
  modified:
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - src/auth/jwt.py
    - src/auth/permissions.py
    - src/platform/trusted_context.py
    - src/tools/catalog.py
    - src/tools/executors/business.py
    - src/agent/nodes/investigate_planner.py
    - tests/platform/test_trusted_context_factory.py
    - tests/tools/test_catalog.py
    - tests/tools/test_tool_platform.py

key-decisions:
  - "Keep `business:query -> tool:business_query` separate from `metrics:read -> tool:query_business_metric`; the deprecated merchant role keeps metric compatibility only by default."
  - "Expose `business_query` as the primary planner-visible read descriptor for investigate while keeping `query_business_metric` as compatibility."
  - "Return safe `unavailable` for valid `business_query` executor calls until 62-04 connects runtime execution; do not add DB runtime work in this plan."
  - "Patch the current static investigate planner allowlist and add parity coverage so the new catalog-visible tool is not rejected by planner validation."

patterns-established:
  - "Business-query ToolPlatform args reject authority-bearing and free-form database fields through descriptor schema before executor dispatch."
  - "TrustedContext permissions for business query are projected only from verified token scopes intersected with role scopes."

requirements-completed: [BQ-62-02, BQ-62-04]

duration: 11 min
completed: 2026-07-09
---

# Phase 62 Plan 03: ToolPlatform Policy And Trusted Scope Boundary Summary

**Trusted `business_query` ToolPlatform boundary with separate `business:query` permission, strict read-only descriptor, and pre-dispatch policy denials**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-09T13:30:14Z
- **Completed:** 2026-07-09T13:41:35Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Added `business:query` as a trusted scope for support, manager, and admin, and projected it to `tool:business_query` only through `TrustedContextFactory`.
- Preserved the Phase 61 compatibility boundary: `metrics:read` still maps only to `tool:query_business_metric`; deprecated merchant role defaults remain metric-only.
- Registered a read-only `business_query` ToolCatalog descriptor for investigate with registry/schema-derived strict input and `BusinessQueryResultV1` output shape.
- Added ToolPlatform tests proving wrong caller, missing permission, authority-bearing fields, raw SQL keys, arbitrary filters, and raw cursor strings fail before executor dispatch.
- Added deferred safe executor behavior for `business_query` without database runtime work, preserving the 62-04 runtime boundary.

## Task Commits

1. **Task 1 RED: Project trusted business-query permission tests** - `e3ed32d` (test)
2. **Task 1 GREEN: Project trusted business-query permission** - `5d50515` (feat)
3. **Task 2 RED: Add business_query descriptor and policy denial tests** - `31cdb6a` (test)
4. **Task 2 GREEN: Add business_query ToolPlatform boundary** - `ba3d7af` (feat)

**Plan metadata:** included in the final docs/state commit for this plan

## Files Created/Modified

- `src/auth/jwt.py` - Adds `business:query` to support, manager, and admin role scopes while leaving merchant metric compatibility unchanged.
- `src/auth/permissions.py` - Advertises `business:query` in OAuth password flow scopes.
- `src/platform/trusted_context.py` - Maps trusted `business:query` to `tool:business_query`.
- `src/tools/catalog.py` - Adds strict `business_query` read descriptor and schema helpers.
- `src/tools/executors/business.py` - Recognizes `business_query` and returns safe deferred `unavailable` after schema validation.
- `src/agent/nodes/investigate_planner.py` - Adds `business_query` to the current static investigate planner allowlist.
- `tests/platform/test_trusted_context_factory.py` - Covers trusted permission projection and untrusted injection denial.
- `tests/tools/test_catalog.py` - Covers descriptor strictness, registry/schema derivation, and compatibility descriptor retention.
- `tests/tools/test_tool_platform.py` - Covers visibility, runtime denials before dispatch, and planner allowlist parity.
- `.planning/ARCHITECTURE-DEBT.md` - Records verified ToolPlatform boundary fixes and remaining runtime/allowlist risks.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records the handled catalog schema helper import failure.

## Decisions Made

- Did not grant `business:query` by default to the deprecated `merchant` role; it keeps `metrics:read` compatibility for the existing metric path.
- Used descriptor schema validation for malformed/authority-bearing business_query args so invalid requests stop before runtime auth dispatch.
- Kept `business_query` runtime as a safe deferred executor path; 62-04 remains the owner for `BusinessFactService` execution and no-existence-leak runtime semantics.

## TDD Gate Compliance

- Task 1 RED commit present: `e3ed32d`; focused suite failed as expected with missing `business:query` scope and missing `tool:business_query` projection.
- Task 1 GREEN commit present after RED: `5d50515`; trusted context suite passed.
- Task 2 RED commit present: `31cdb6a`; focused suite failed as expected because `business_query` was not registered.
- Task 2 GREEN commit present after RED: `ba3d7af`; catalog/platform/schema suite passed.
- REFACTOR commits: not needed.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py -q --tb=short` -> RED before implementation: `8 failed, 32 passed, 1 warning`; GREEN after implementation: `40 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py tests/integration/test_auth.py::test_agent_chat_scope_is_issued_to_agent_roles tests/integration/test_auth.py::test_metrics_read_scope_is_issued_to_metric_roles tests/integration/test_auth.py::test_oauth_password_flow_advertises_metrics_read_scope -q --tb=short` -> `43 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/business/test_business_query_schemas.py -q --tb=short` -> RED before implementation: `16 failed, 87 passed, 1 warning`; GREEN after implementation: `103 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/business/test_business_query_schemas.py -q --tb=short` -> `143 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/auth/jwt.py src/auth/permissions.py src/platform/trusted_context.py src/tools/catalog.py src/tools/policy.py src/tools/executors/business.py src/agent/nodes/investigate_planner.py tests/platform/test_trusted_context_factory.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py` -> `All checks passed!`
- `rg -n "business:query|tool:business_query|name=\"business_query\"|raw_sql|merchant_scope|tenant_id" src/auth/jwt.py src/auth/permissions.py src/platform/trusted_context.py src/tools/catalog.py src/tools/policy.py tests/tools/test_tool_platform.py` -> required permission, descriptor, and denial coverage found
- `gsd-sdk query verify.key-links .planning/phases/62-business-query-and-drilldown-foundation/62-03-PLAN.md` -> `all_verified: true`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Synchronized investigate planner static allowlist**
- **Found during:** Task 2 (Add read-only business_query descriptor and policy denials)
- **Issue:** `business_query` is planner-visible through ToolCatalog, but `src/agent/nodes/investigate_planner.py` still has a static allowlist. Without updating it, ToolPlatform could expose the tool while planner output validation rejected it.
- **Fix:** Added `business_query` to `INVESTIGATE_ALLOWED_TOOL_NAMES` and added a parity test that `investigate_tool_names()` stays covered by the planner allowlist.
- **Files modified:** `src/agent/nodes/investigate_planner.py`, `tests/tools/test_tool_platform.py`, `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Task 2 focused suite and final plan suite passed.
- **Committed in:** `ba3d7af`

**2. [Rule 1 - Bug] Fixed catalog schema helper import failure**
- **Found during:** Task 2 GREEN verification
- **Issue:** The new `business_query` group_by schema helper referenced `BusinessQueryFieldDescriptor.field_id`, but the registry field descriptor uses `id`; this caused pytest collection to fail on `src.tools.catalog` import.
- **Fix:** Replaced `descriptor.field_id` with `descriptor.id` and recorded the local validation incident.
- **Files modified:** `src/tools/catalog.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Rerun of Task 2 focused suite passed with `103 passed, 1 warning`.
- **Committed in:** `ba3d7af`

---

**Total deviations:** 2 auto-fixed (1 Rule 2 missing critical, 1 Rule 1 bug)
**Impact on plan:** Both fixes were required to make the planned ToolPlatform boundary usable and verifiable without expanding runtime scope.

## Issues Encountered

- Expected TDD RED failures occurred before implementation for both tasks.
- The Task 2 GREEN import-time bug was fixed and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No authentication gates or unresolved validation failures occurred.

## Known Stubs

None. Stub scan hits were legitimate empty containers/default values in existing tests, catalog initialization, safe result constructors, or trusted-context fail-closed paths. The `business_query` executor returns a deliberate safe deferred `unavailable` result because 62-04 owns runtime execution.

## Threat Flags

None. The new trusted permission and ToolCatalog/ToolPolicy surfaces are the planned T-62-08 through T-62-11 mitigation surfaces; no unplanned network endpoint, auth path, file access pattern, SQL execution surface, DB schema change, or runtime query path was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 62-04 can connect `business_query` runtime execution behind `BusinessFactService` using the trusted `tool:business_query` permission and strict descriptor schema added here. The current valid-spec executor response is intentionally `unavailable` until that runtime plan lands.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/62-business-query-and-drilldown-foundation/62-03-SUMMARY.md`
- Task commits found: `e3ed32d`, `5d50515`, `31cdb6a`, `ba3d7af`
- No unexpected tracked file deletions were detected across the plan commits.

---
*Phase: 62-business-query-and-drilldown-foundation*
*Completed: 2026-07-09*
