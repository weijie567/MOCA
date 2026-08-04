---
phase: 38-output-schema-declaration-runtime-output-validation-enforcem
plan: 03
subsystem: tools
tags: [tool-runtime, output-schema, invalid-response, tph-01, pytest, ruff]

requires:
  - phase: 38-02
    provides: catalog-owned strict output_schema declarations for the eight TPH-01 scoped tools
provides:
  - runtime fake-executor coverage for valid output pass-through and invalid_response mapping
  - ToolResultV2 envelope field-set guard
  - no-data output schema dispatch coverage for search_sop through the knowledge executor bucket
  - focused high-blast consumer regression evidence with DB-backed paths verified after compose PostgreSQL startup
affects: [phase-38, phase-39, tool-runtime, tool-platform, unified-tool-manager, output-schema-validation]

tech-stack:
  added: []
  patterns:
    - fake-executor ToolPlatform tests for runtime output-schema enforcement
    - exact ToolResultV2.model_fields guard for high-blast envelope stability
    - DB-backed final suite reporting with non-DB proxy coverage separated

key-files:
  created:
    - .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-03-SUMMARY.md
  modified:
    - src/tools/runtime.py
    - tests/tools/test_tool_platform.py
    - tests/agent/test_tools/test_unified_tool_manager.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Runtime output validation now validates success and partial_success results even when data is None, so non-null output schemas cannot be bypassed."
  - "Use fake executors for runtime output validation so TPH-01 behavior is covered independently of local PostgreSQL."
  - "Leave local validation log updates unstaged because the file had large unrelated pre-existing dirty hunks."

patterns-established:
  - "No-data tools can be tested through their real executor bucket with has_tool(...) returning true, forcing the request to reach output validation."
  - "High-blast consumer tests must use schema-conforming fake ToolResultV2.data payloads once strict output_schema declarations exist."

requirements-completed: [TPH-01]

duration: 4 min
completed: 2026-07-02
---

# Phase 38 Plan 03: Runtime Output-Validation Enforcement Summary

**Runtime output-schema enforcement now has facade-level proof for pass-through, fail-closed invalid responses, raw-payload redaction, and stable ToolResultV2 envelope fields.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-02T01:46:10Z
- **Completed:** 2026-07-02T01:50:58Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `ToolPlatform.invoke(...)` tests proving schema-valid `get_order` executor data passes through unchanged.
- Added invalid-output tests proving schema-invalid executor data maps to `invalid_response`, clears `data`, returns `INVALID_EXECUTOR_RESPONSE`, and does not serialize the raw sentinel.
- Fixed the post-review enforcement gap where `status="success"` with `data=None` bypassed non-null object output schemas.
- Added `search_sop` no-data schema coverage with a fake `knowledge` executor whose `has_tool("search_sop")` returns true, so availability/dispatch pass and output validation performs the rejection.
- Added an exact `ToolResultV2.model_fields` guard covering the high-blast envelope.
- Updated a `UnifiedToolManager` regression fixture from a generic fake payload to a schema-conforming `get_order` payload.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add runtime output-validation behavior tests** - `5f748c7` (test)
2. **Task 2: Run final contract and high-blast consumer regression sweep** - `4de704a` (test)
3. **Post-review fix: Validate successful empty tool outputs** - `16a5d8f` (fix)

## Files Created/Modified

- `src/tools/runtime.py` - Validates success and partial_success outputs through descriptor output_schema even when `data` is `None`.
- `tests/tools/test_tool_platform.py` - Adds runtime output-schema success/failure/no-data tests, success-with-missing-data regression coverage, and the exact envelope field-set guard.
- `tests/agent/test_tools/test_unified_tool_manager.py` - Aligns the fake `get_order` success payload with the strict output schema so manager regressions still test manager behavior.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Appended Chinese PostgreSQL/Docker validation records; intentionally left unstaged because the file had unrelated pre-existing dirty local logs.
- `.planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-03-SUMMARY.md` - Records execution, verification, and DB-gated coverage caveats.

## Decisions Made

- `ToolRuntime.invoke` now treats `success` and `partial_success` results as schema-bearing even when `data` is `None`, while preserving validation of non-empty data on other statuses.
- Kept `ToolResultV2` and `ToolCallContext` untouched.
- Treated business/service and memory/search real-path coverage as DB-backed where it depends on `tests/conftest.py::test_engine`; after Docker Desktop was started, compose PostgreSQL made the full relevant suite pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale high-blast fake payload**
- **Found during:** Task 2 (final consumer regression sweep)
- **Issue:** `tests/agent/test_tools/test_unified_tool_manager.py::_success_result()` returned `{"ok": True}` for fake `get_order` success. After strict output schemas, this correctly failed as `invalid_response`, causing two manager tests to fail for fixture shape rather than manager behavior.
- **Fix:** Replaced the fake data with a schema-conforming `get_order` payload.
- **Files modified:** `tests/agent/test_tools/test_unified_tool_manager.py`
- **Verification:** Focused high-blast subset reran as `33 passed, 1 warning`; extra ruff on the file passed.
- **Committed in:** `4de704a`

---

**2. [Post-review Warning] Closed success-with-missing-data schema bypass**
- **Found during:** Phase 38 code review gate
- **Issue:** `ToolRuntime.invoke` only validated output schemas when `tool_result.data is not None`, so a `get_order` executor could return `status="success", data=None` and bypass the non-null object schema.
- **Fix:** Validate output schemas whenever status is `success` or `partial_success`, even when `data` is `None`; added a facade-level regression test proving the result maps to `invalid_response`.
- **Files modified:** `src/tools/runtime.py`, `tests/tools/test_tool_platform.py`
- **Verification:** New regression node plus existing runtime output-schema nodes pass.
- **Committed in:** `16a5d8f`

---

**Total deviations:** 2 auto-fixed (Rule 1 / post-review warning).
**Impact on plan:** The fixes keep high-blast regression intent intact and strengthen Phase 38 runtime enforcement without changing external contract fields.

## Issues Encountered

- Task 1 tests passed immediately after being added because the runtime enforcement path already existed after Phase 37 and Phase 38 plan 38-02. This plan therefore produced a test-only coverage commit rather than a RED/GREEN production change.
- Earlier DB-backed quick/full relevant pytest commands were blocked by local PostgreSQL unavailability on `localhost:5432`, not by product-code failures. After Docker Desktop was started and `docker compose up -d postgres` made PostgreSQL healthy, the full relevant suite passed.

## TDD Gate Compliance

- Task 1 was marked `tdd="true"`, but the four new tests passed immediately after being added because the production runtime behavior already existed. No separate GREEN implementation commit was necessary.
- RED/GREEN strict sequence warning: this task produced a test-only commit (`5f748c7`) and no following `feat(38-03)` commit. The summary records this as pre-existing implementation coverage, not a skipped failure.

## Verification

- `uv run pytest tests/tools/test_tool_platform.py::test_output_schema_success_passes_tool_result_unchanged tests/tools/test_tool_platform.py::test_output_schema_failure_returns_invalid_response_without_raw_data tests/tools/test_tool_platform.py::test_no_data_output_schema_rejects_accidental_unavailable_tool_payload tests/tools/test_tool_platform.py::test_tool_result_v2_envelope_fields_are_unchanged -q` -> `4 passed, 1 warning`
- `uv run pytest tests/tools/test_tool_platform.py::test_output_schema_success_with_missing_data_returns_invalid_response tests/tools/test_tool_platform.py::test_output_schema_success_passes_tool_result_unchanged tests/tools/test_tool_platform.py::test_output_schema_failure_returns_invalid_response_without_raw_data tests/tools/test_tool_platform.py::test_no_data_output_schema_rejects_accidental_unavailable_tool_payload tests/tools/test_tool_platform.py::test_tool_result_v2_envelope_fields_are_unchanged -q` -> `5 passed, 1 warning`
- `uv run pytest tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope -q` -> `2 passed, 1 warning`
- `uv run ruff check tests/tools/test_tool_platform.py` -> passed
- `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` -> `54 passed, 1 warning, 6 errors`; all errors are PostgreSQL fixture setup connection refusals in `tests/conftest.py::test_engine`
- `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory tests/agent/rag_context/test_verifier.py::test_business_fact_claim_requires_current_tool_system_refs tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q` -> `33 passed, 1 warning` after the fixture fix
- `uv run ruff check src/tools/catalog.py src/tools/validation.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py` -> passed
- `uv run ruff check tests/agent/test_tools/test_unified_tool_manager.py` -> passed
- `git diff -- docs/contract-spec.md src/tools/contracts.py` -> no diff
- `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_verifier.py tests/conversation/test_service.py tests/test_execute_action.py tests/architecture/test_trusted_context_boundaries.py -q` -> `166 passed, 1 warning, 17 errors`; all errors are PostgreSQL fixture setup connection refusals in `tests/conftest.py::test_engine`
- After `docker compose up -d postgres`: `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_verifier.py tests/conversation/test_service.py tests/test_execute_action.py tests/architecture/test_trusted_context_boundaries.py -q` -> `184 passed, 1 warning`

## Known Stubs

None. The scan found only intentional test fixture empty lists, `None` fields, and `{}` payloads.

## Threat Flags

None. The only production change tightens the existing runtime output-validation condition; it introduced no new network endpoint, auth path, file access pattern, schema migration, or trust-boundary surface.

## User Setup Required

None. Compose PostgreSQL is running and the DB-backed full relevant pytest gate passed.

## Next Phase Readiness

Phase 38 implementation is complete for TPH-01 with DB-backed verification passing. Phase 39 can reconcile `docs/contract-spec.md` against the final implemented output-schema behavior, while preserving the protected `ToolResultV2` envelope and `ToolCallContext` identity fields.

## Self-Check: PASSED

- Created/modified files exist: `src/tools/runtime.py`, `tests/tools/test_tool_platform.py`, `tests/agent/test_tools/test_unified_tool_manager.py`, and this summary.
- Task/review-fix commits found in git history: `5f748c7`, `4de704a`, `16a5d8f`.
- Protected files remain untouched: `docs/contract-spec.md` and `src/tools/contracts.py`.
- Summary validation commands use project-approved `uv run pytest` / `uv run ruff` entrypoints.
- `.planning/LOCAL-VALIDATION-ISSUES.md` remains unstaged by design because it had pre-existing unrelated dirty hunks.

---
*Phase: 38-output-schema-declaration-runtime-output-validation-enforcem*
*Completed: 2026-07-02*
