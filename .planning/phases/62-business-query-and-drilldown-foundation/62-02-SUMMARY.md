---
phase: 62-business-query-and-drilldown-foundation
plan: 02
subsystem: business-query-contract-schema
tags: [business-query, pydantic, contract-spec, compatibility, tdd]

requires:
  - phase: 62-business-query-and-drilldown-foundation
    plan: 01
    provides: immutable BUSINESS_QUERY_REGISTRY descriptors for operation/resource/time/status/field/sort validation
provides:
  - accepted Phase 62 business_query target contract semantics in docs/contract-spec.md
  - strict registry-backed BusinessQuerySpec and related result/context/cursor models
  - business_metric_query compatibility mapping into BusinessQuerySpec(operation="aggregate")
  - schema tests for authority-field rejection, descriptor parity, current_snapshot gating, and metric compatibility
affects: [business-query-runtime, tool-platform-policy, drilldown, projection, api, frontend, phase-62]

tech-stack:
  added: []
  patterns:
    - Pydantic v2 strict models with ConfigDict(extra="forbid")
    - Registry-backed dynamic validation instead of hand-written schema enum source-of-truth
    - TDD RED/GREEN gate for schema contract behavior

key-files:
  created:
    - src/business/query/schemas.py
    - tests/business/test_business_query_schemas.py
    - .planning/phases/62-business-query-and-drilldown-foundation/62-02-SUMMARY.md
  modified:
    - docs/contract-spec.md
    - src/business/query/__init__.py
    - src/business/schemas.py
    - tests/business/test_schemas.py

key-decisions:
  - "Validate BusinessQuerySpec operation/resource/time/status/field/sort values against BUSINESS_QUERY_REGISTRY instead of duplicating Literal enum source-of-truth."
  - "Keep business_metric_query as a compatibility entry that maps into BusinessQuerySpec(operation='aggregate') and applies the same strict validation."
  - "Treat current_snapshot as descriptor-owned: accepted for pending_ticket_count and rejected for event/rate metrics."

patterns-established:
  - "Business-query schema boundary rejects authority-bearing fields, raw query shapes, raw cursor strings, wildcard merchant filters, and descriptor-incompatible values before runtime."
  - "Business-query public contracts are exported from src.business.query and re-exported from src.business.schemas for compatibility."

requirements-completed: [BQ-62-02, BQ-62-04]

duration: 8m
completed: 2026-07-09
---

# Phase 62 Plan 02: Safe Business Query Contract And Schema Summary

**Registry-backed `BusinessQuerySpec` contract with strict validation and `business_metric_query` compatibility mapping**

## Performance

- **Duration:** 8m
- **Started:** 2026-07-09T13:14:54Z
- **Completed:** 2026-07-09T13:22:51Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added the accepted `business_query` target contract delta to `docs/contract-spec.md`, including operation/resource taxonomy, BusinessFactService ownership, no-existence-leak semantics, descriptor gates, answer context constraints, projection responsibilities, authority separation, and named Phase 63-67 deferrals.
- Added strict Pydantic models for `BusinessQuerySpec`, filters, sort, cursor, result cursor, answer context, result, and scope summary.
- Added `metric_input_to_business_query`, mapping all five Phase 61 metric inputs into validated aggregate `BusinessQuerySpec` instances.
- Added schema tests covering authority-field rejection, raw SQL/filter/cursor rejection, registry parity, current_snapshot descriptor behavior, limits, fields, sort, compare, breakdown, result/context strictness, and compatibility re-exports.

## Task Commits

1. **Task 1: Record business_query contract semantics** - `bc672b4` (docs)
2. **Task 2 RED: Add failing BusinessQuerySpec schema tests** - `07dee47` (test)
3. **Task 2 GREEN: Implement BusinessQuerySpec schema contract** - `e2f3f05` (feat)

**Plan metadata:** included in the final docs/state commit for this plan

## Files Created/Modified

- `docs/contract-spec.md` - Adds Phase 62 `business_query` target contract semantics and explicit deferred phase boundaries.
- `src/business/query/schemas.py` - Defines strict registry-backed business-query schema/result/context/cursor models and metric compatibility mapping.
- `src/business/query/__init__.py` - Exports the schema contracts from the query package.
- `src/business/schemas.py` - Re-exports business-query contracts for compatibility with existing business schema imports.
- `tests/business/test_business_query_schemas.py` - Covers schema strictness, descriptor parity, and metric compatibility mapping.
- `tests/business/test_schemas.py` - Verifies compatibility re-exports.

## Decisions Made

- Used registry-backed string validation instead of duplicating operation/resource/time/status/field/sort values as schema-local `Literal` unions.
- Kept `BusinessMetricQueryInput` unchanged and introduced a mapping helper so Phase 61 callers can transition without widening tool args.
- Modeled result/context/cursor schemas now, while leaving ToolPlatform registration, runtime execution, projection/API, drilldown state, and UI behavior to later Phase 62 plans.

## TDD Gate Compliance

- RED commit present: `07dee47` failed as expected with `ModuleNotFoundError: No module named 'src.business.query.schemas'`.
- GREEN commit present after RED: `e2f3f05` passed the focused schema suite.
- REFACTOR commit: not needed; no behavior-preserving cleanup remained after GREEN.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_schemas.py tests/business/test_schemas.py -q --tb=short` -> `39 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/schemas.py src/business/query/__init__.py src/business/schemas.py tests/business/test_business_query_schemas.py tests/business/test_schemas.py` -> `All checks passed!`
- `rg -n "class BusinessQuerySpec|class BusinessQueryResultV1|class BusinessQueryAnswerContext|def metric_input_to_business_query" src/business/query/schemas.py` -> required symbols found
- `rg -n "class BusinessQuerySpec|BusinessQuerySpec|business_query|no-existence" src/business/query/schemas.py docs/contract-spec.md` -> schema and contract hits found
- `gsd-sdk query verify.key-links .planning/phases/62-business-query-and-drilldown-foundation/62-02-PLAN.md` -> `all_verified: true`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Expected TDD RED failure occurred before implementation: `tests/business/test_business_query_schemas.py` could not import `src.business.query.schemas`.
- The first SUMMARY self-check command used zsh variable name `path`, which shadowed `PATH` and made `git` / `grep` unavailable inside that shell. Re-ran with `file_path` / `commit_hash`; self-check passed and the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No authentication gates, blockers, or unresolved validation failures occurred.

## Known Stubs

None. The stub scan only found legitimate optional `None` fields, schema defaults, and existing empty-list assertions; no placeholder or unwired data-source stub was introduced.

## Threat Flags

None. The new schema trust boundary is the planned T-62-04 mitigation surface and introduces no unplanned network endpoint, auth path, file access pattern, SQL execution surface, tenant authority field, merchant-scope authority field, raw cursor surface, draft operation, or execute operation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 62-03 can register ToolPlatform policy and trusted-scope boundaries against `BusinessQuerySpec` without inventing new operation/resource/time/status/field/sort literals. Runtime execution remains intentionally deferred to later Phase 62 plans.

## Self-Check: PASSED

- Created/modified files claimed in this summary exist.
- Task commits found: `bc672b4`, `07dee47`, `e2f3f05`.
- No unexpected tracked file deletions were detected after task commits.

---
*Phase: 62-business-query-and-drilldown-foundation*
*Completed: 2026-07-09*
