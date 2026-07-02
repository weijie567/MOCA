---
phase: 38-output-schema-declaration-runtime-output-validation-enforcem
reviewed: 2026-07-02T02:38:18Z
depth: deep
files_reviewed: 6
files_reviewed_list:
  - src/tools/catalog.py
  - src/tools/runtime.py
  - src/tools/validation.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/tools/test_catalog.py
  - tests/tools/test_tool_platform.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 38: Code Review Report

**Reviewed:** 2026-07-02T02:38:18Z
**Depth:** deep
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 38 output schema declarations, JSON-schema subset validator, runtime enforcement path, and regression tests after the code-review-fix commits. Deep tracing covered `ToolCatalog` descriptors through `UnifiedToolManager.invoke` -> `ToolPlatform.invoke` -> `ToolRuntime.invoke`, plus the business, knowledge, memory, and action executor payload shapes consumed by the declared schemas.

The previous WR-01 is fixed: `src/tools/validation.py` rejects non-finite `number` values with `math.isfinite`, and `tests/tools/test_catalog.py` covers both direct `{"type": "number"}` validation and a real scoped `search_policy.best_score` payload. The earlier successful-output `data=None` bypass is also fixed in implementation: `src/tools/runtime.py` validates both `success` and `partial_success` outputs even when `data is None`.

Protected files `src/tools/contracts.py` and `docs/contract-spec.md` were not changed by the Phase 38 diff from `41372a4^..HEAD`.

## Info

### IN-01: Missing Partial-Success Data-None Regression

**File:** `tests/tools/test_tool_platform.py:279`
**Issue:** The runtime implementation now validates both `success` and `partial_success` outputs when `data is None`, but the regression test only covers the `success` status by copying `_success_result()` with `data=None`. A future refactor could preserve the success case while accidentally dropping the `partial_success` branch.
**Fix:** Parameterize `test_output_schema_success_with_missing_data_returns_invalid_response` over `status in ("success", "partial_success")`, or add a sibling test that sets `status="partial_success"` and asserts `invalid_response`.

## Verification

Targeted review suite passed with the project-approved entrypoint:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py
```

Result: `97 passed, 1 warning`.

Diff scope check:

```bash
git diff --name-only 41372a4^..HEAD -- src/tools/catalog.py src/tools/runtime.py src/tools/validation.py tests/agent/test_tools/test_unified_tool_manager.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py src/tools/contracts.py docs/contract-spec.md
```

Result: only the six reviewed files were listed; the protected files were absent.

---

_Reviewed: 2026-07-02T02:38:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
