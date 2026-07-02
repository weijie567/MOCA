---
phase: 38-output-schema-declaration-runtime-output-validation-enforcem
plan: 01
subsystem: tools
tags: [tool-validation, output-schema, tph-01, pytest, ruff]

requires:
  - phase: 37-tool-declaration-runtime-policy-internal-consolidation
    provides: single-source tool declaration rows and catalog-derived descriptor metadata
provides:
  - validate_json_value support for JSON Schema null and type-list union forms
  - focused regression coverage for nullable/type-union validation
  - executable TPH-01 scoped read/retrieval tool-set contract
  - explicit exclusion of create_coupon_grant_draft from 38-01 output-schema scope
affects: [phase-38, tool-platform, tool-catalog, output-schema-validation]

tech-stack:
  added: []
  patterns:
    - recursive local validator support for nullable/type-union schema subsets
    - test-locked scoped tool set before real catalog output_schema declarations

key-files:
  created:
    - .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-01-SUMMARY.md
  modified:
    - src/tools/validation.py
    - tests/tools/test_catalog.py

key-decisions:
  - "Use the existing local validate_json_value helper for null/type-list support instead of adding jsonschema."
  - "Keep TPH-01 scoped to the eight read/retrieval planner-visible tools and keep create_coupon_grant_draft out of this plan."
  - "Return immediately from the first successful union candidate validation branch."

patterns-established:
  - "Type-list schemas are evaluated recursively candidate-by-candidate and accepted on the first full successful candidate."
  - "TPH-01 scoped tool names live in a focused test constant until later plans replace generic catalog output schemas."

requirements-completed: [TPH-01]

duration: 3 min
completed: 2026-07-02
---

# Phase 38 Plan 01: Validator and Scoped Tool-Set Summary

**Nullable/type-union schema validation plus an executable TPH-01 read/retrieval tool boundary for later real output schemas.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-02T01:31:00Z
- **Completed:** 2026-07-02T01:33:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added local validator support for `{"type": "null"}` and list-valued `type` schemas such as `{"type": ["string", "null"]}`.
- Preserved first-success union behavior: validation returns immediately after a candidate schema succeeds.
- Added focused nullable/type-union tests, including rejection coverage for mismatched union values.
- Locked the TPH-01 scoped set to the eight planner-visible read/retrieval tools and verified `create_coupon_grant_draft` remains a node-only write action outside this plan.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add nullable/type-union schema tests** - `41372a4` (test)
2. **Task 1 GREEN: Implement nullable/type-union validation** - `877ae04` (feat)
3. **Task 2: Lock TPH-01 scoped tool set** - `46604ee` (test)

## Files Created/Modified

- `src/tools/validation.py` - Adds list-valued `type` union validation and explicit `"null"` handling.
- `tests/tools/test_catalog.py` - Adds validator tests and the `TPH01_OUTPUT_SCHEMA_TOOL_NAMES` scoped contract test.
- `.planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-01-SUMMARY.md` - Records plan execution, verification, and next-plan readiness.

## Decisions Made

- Extended the project-owned validator rather than adding a new JSON Schema dependency.
- Kept the action tool output schema out of TPH-01 scope for this plan; action output hardening remains future work.
- Treated Task 2 as test-evidence work because the descriptor metadata behavior already existed after Phase 37.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 1 RED failed as intended: the existing validator silently accepted mismatched list-valued `type` schemas.
- Task 2's new scoped-set test passed immediately because Phase 37 had already established the required registry metadata. No production code change was needed for that test-evidence task.

## TDD Gate Compliance

- Task 1 produced a RED test commit (`41372a4`) followed by a GREEN implementation commit (`877ae04`).
- Task 2 produced a test-only commit (`46604ee`). The behavior under test already existed, so there was no separate GREEN implementation commit.

## Verification

- `uv run pytest tests/tools/test_catalog.py::test_json_schema_helper_accepts_nullable_union_and_null tests/tools/test_catalog.py::test_json_schema_helper_rejects_nullable_union_mismatches -q` -> `2 passed, 1 warning`
- `uv run pytest tests/tools/test_catalog.py::test_tph01_scoped_output_schema_tool_names_match_registered_tools tests/tools/test_catalog.py::test_catalog_registry_derives_identifier_schemas_without_drift -q` -> `2 passed, 1 warning`
- `uv run pytest tests/tools/test_catalog.py -q` -> `15 passed, 1 warning`
- `uv run ruff check src/tools/validation.py tests/tools/test_catalog.py` -> passed
- `rg -n "isinstance\\(expected_type, list\\)|expected_type == \"null\"" src/tools/validation.py` -> found both branches
- `rg -n "TPH01_OUTPUT_SCHEMA_TOOL_NAMES|test_tph01_scoped_output_schema_tool_names_match_registered_tools" tests/tools/test_catalog.py` -> found the scoped constant and test
- `git diff -- docs/contract-spec.md src/tools/contracts.py src/tools/catalog.py` -> no diff

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `38-02-PLAN.md`. The validator now accepts nullable current-output fields, and the scoped read/retrieval tool set is locked before replacing generic catalog output schemas.

## Self-Check: PASSED

- Created/modified files exist: `src/tools/validation.py`, `tests/tools/test_catalog.py`, and this summary.
- Task commits found in git history: `41372a4`, `877ae04`, `46604ee`.
- Summary validation commands use `uv run pytest`; no bare test command is recorded.

---
*Phase: 38-output-schema-declaration-runtime-output-validation-enforcem*
*Completed: 2026-07-02*
