---
phase: 38-output-schema-declaration-runtime-output-validation-enforcem
plan: 02
subsystem: tools
tags: [tool-catalog, output-schema, tph-01, pytest, ruff]

requires:
  - phase: 38-01
    provides: nullable/type-union validation support and the locked TPH-01 scoped read/retrieval tool set
provides:
  - declaration-owned output_schema values for the eight TPH-01 scoped tools
  - strict no-data output schemas for currently unavailable logistics, merchant-risk, and SOP tools
  - current payload acceptance and unsafe payload rejection coverage for catalog output schemas
  - preserved generic output schema for create_coupon_grant_draft action output hardening scope
affects: [phase-38, tool-platform, tool-catalog, runtime-output-validation]

tech-stack:
  added: []
  patterns:
    - declaration-owned catalog output schemas passed through _descriptor(...)
    - strict additionalProperties false schemas for current implemented ToolResultV2.data shapes
    - strict empty-object no-data schemas for declared-but-unavailable tools

key-files:
  created:
    - .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-02-SUMMARY.md
  modified:
    - src/tools/catalog.py
    - tests/tools/test_catalog.py

key-decisions:
  - "Use _ToolDeclaration.output_schema as the single catalog source for ToolDescriptor.output_schema."
  - "Keep get_logistics, get_merchant_risk, and search_sop on strict no-data schemas until future executor/product scope defines real success payloads."
  - "Keep create_coupon_grant_draft generic and node-only because action output hardening is outside TPH-01."

patterns-established:
  - "Catalog output schema edits belong beside input schema declarations in _TOOL_DECLARATIONS and are passed through by _descriptor(...)."
  - "Catalog schema tests prove both current payload acceptance and rejection of raw/sentinel fields, invalid enums, missing required fields, and non-empty no-data payloads."

requirements-completed: [TPH-01]

duration: 3 min
completed: 2026-07-02
---

# Phase 38 Plan 02: Catalog Output Schema Declaration Summary

**Catalog declarations now provide strict output schemas for the eight scoped read/retrieval tools, with payload tests proving current data passes and unsafe data fails.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-02T01:38:08Z
- **Completed:** 2026-07-02T01:41:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `_ToolDeclaration.output_schema` and changed `_descriptor(...)` to pass `output_schema=declaration.output_schema`.
- Declared strict output schemas for `get_order`, `get_refund_case`, `get_ticket`, `search_policy`, and `search_case_memory`.
- Declared strict empty-object schemas for `get_logistics`, `get_merchant_risk`, and `search_sop`.
- Preserved `create_coupon_grant_draft` as a generic, node-only write action output schema.
- Added catalog tests for schema declaration quality, current payload acceptance, and unsafe payload rejection.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing catalog output schema tests** - `b4d2f55` (test)
2. **Task 1 GREEN: Declare catalog output schemas** - `f9af07c` (feat)
3. **Task 2: Cover catalog output schema payloads** - `292a2a0` (test)

## Files Created/Modified

- `src/tools/catalog.py` - Adds output schema constants, `_ToolDeclaration.output_schema`, per-tool declaration assignments, and descriptor pass-through.
- `tests/tools/test_catalog.py` - Replaces the generic-schema drift assertion and adds schema declaration, action-preservation, current-payload acceptance, and invalid-payload rejection coverage.
- `.planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-02-SUMMARY.md` - Records execution, verification, and next-plan readiness.

## Decisions Made

- Used the plan `<interfaces>` block as the source of truth for `get_order`; its schema includes all 10 fields: `order_no`, `merchant_id`, `status`, `amount`, `currency`, `buyer_name`, `item_name`, `paid_at`, `delivered_at`, and `relation_hints`.
- Used strict empty-object output schemas for unavailable tools instead of inventing future logistics, merchant-risk, or SOP success payloads.
- Kept action output hardening deferred by leaving only `create_coupon_grant_draft` on `_GENERIC_OBJECT_SCHEMA`.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

- Task 1 RED failed as intended: `get_order` still exposed the generic `{"type": "object"}` output schema before catalog implementation.
- Task 2's payload tests passed immediately because Task 1 had already implemented the schema behavior they prove. This task was committed as test-evidence work rather than a separate GREEN implementation.

## TDD Gate Compliance

- Task 1 produced a RED test commit (`b4d2f55`) followed by a GREEN implementation commit (`f9af07c`).
- Task 2 produced a test-only commit (`292a2a0`). Its tests were green immediately after Task 1, so no additional production change was required.

## Verification

- `uv run pytest tests/tools/test_catalog.py::test_tph01_scoped_output_schema_tool_names_match_registered_tools tests/tools/test_catalog.py::test_catalog_registry_derives_identifier_schemas_without_drift tests/tools/test_catalog.py::test_scoped_tools_declare_real_output_schemas tests/tools/test_catalog.py::test_action_output_schema_remains_generic_until_action_output_hardening -q` -> `4 passed, 1 warning`
- `uv run pytest tests/tools/test_catalog.py::test_output_schema_helper_accepts_current_tool_payloads tests/tools/test_catalog.py::test_output_schema_helper_rejects_invalid_tool_payloads -q` -> `15 passed, 1 warning`
- `uv run pytest tests/tools/test_catalog.py -q` -> `32 passed, 1 warning`
- `uv run ruff check src/tools/catalog.py tests/tools/test_catalog.py` -> passed
- `git diff -- src/tools/contracts.py docs/contract-spec.md` -> no diff
- `rg -n "output_schema=_GENERIC_OBJECT_SCHEMA" src/tools/catalog.py` -> one match at the planned `create_coupon_grant_draft` action declaration only
- `rg -n "output_schema: dict\\[str, Any\\]|output_schema=declaration\\.output_schema" src/tools/catalog.py` -> found the dataclass field and descriptor pass-through
- `rg -n "_ORDER_OUTPUT_SCHEMA|_REFUND_CASE_OUTPUT_SCHEMA|_TICKET_OUTPUT_SCHEMA|_SEARCH_POLICY_OUTPUT_SCHEMA|_SEARCH_CASE_MEMORY_OUTPUT_SCHEMA|_NO_DATA_OUTPUT_SCHEMA" src/tools/catalog.py` -> found all required schema constants
- `rg -n "test_output_schema_helper_accepts_current_tool_payloads|test_output_schema_helper_rejects_invalid_tool_payloads" tests/tools/test_catalog.py` -> found payload tests

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `38-03-PLAN.md`. The catalog now supplies strict output schemas; the next plan can focus on runtime invalid-response enforcement and high-blast consumer regression coverage.

## Self-Check: PASSED

- Created/modified files exist: `src/tools/catalog.py`, `tests/tools/test_catalog.py`, and this summary.
- Task commits found in git history: `b4d2f55`, `f9af07c`, `292a2a0`.
- Protected files remain untouched: `src/tools/contracts.py` and `docs/contract-spec.md`.
- Summary validation commands use `uv run pytest` / `uv run ruff`; no bare test command is recorded.

---
*Phase: 38-output-schema-declaration-runtime-output-validation-enforcem*
*Completed: 2026-07-02*
