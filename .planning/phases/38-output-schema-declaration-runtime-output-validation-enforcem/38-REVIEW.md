---
phase: 38-output-schema-declaration-runtime-output-validation-enforcem
reviewed: 2026-07-02T02:21:23Z
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
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 38: Code Review Report

**Reviewed:** 2026-07-02T02:21:23Z
**Depth:** deep
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 38 output schema declarations, JSON-schema subset validator changes, runtime enforcement path, and regression tests. Deep call-path tracing covered `UnifiedToolManager.invoke` -> `ToolPlatform.invoke` -> `ToolRuntime.invoke`, plus the business, knowledge, memory, and action executor payload shapes consumed by the declared schemas.

The previous `status="success", data=None` bypass is fixed in implementation: `ToolRuntime.invoke` now validates outputs when `tool_result.status in {"success", "partial_success"}` or when non-success results carry `data`. The remaining correctness gap is in numeric validation for the newly declared output schemas.

Protected files `docs/contract-spec.md` and `src/tools/contracts.py` are not changed in the reviewed diff.

## Warnings

### WR-01: Number Schema Accepts Non-Finite Floats

**File:** `src/tools/validation.py:55`
**Issue:** `validate_json_value` treats any non-bool `int` or `float` as a valid JSON Schema `number`, so `float("nan")`, `float("inf")`, and `float("-inf")` pass validation. Phase 38 now declares numeric output fields (`best_score`, `threshold`, and case-memory `score`), which means an executor can return a non-finite score and still be accepted as a successful tool response instead of being mapped to `invalid_response`. This violates the JSON output contract and can also produce non-portable serialized results.
**Fix:**
```python
from math import isfinite

elif expected_type == "number":
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError("Expected number")
    if not isfinite(value):
        raise ValueError("Expected finite number")
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        raise ValueError("Number is below exclusive minimum")
```

Add a regression in `tests/tools/test_catalog.py` that rejects `float("nan")`, `float("inf")`, and `float("-inf")` for `{"type": "number"}` and for at least one scoped output payload such as `search_policy.best_score`.

## Info

### IN-01: Missing Partial-Success Data-None Regression

**File:** `tests/tools/test_tool_platform.py:278`
**Issue:** The implementation validates both `success` and `partial_success` outputs when `data is None`, but the regression test only covers the `success` status by copying `_success_result()` with `data=None`. A future refactor could preserve the success case while accidentally dropping the `partial_success` branch.
**Fix:** Parameterize `test_output_schema_success_with_missing_data_returns_invalid_response` over `status in ("success", "partial_success")`, or add a sibling test that sets `status="partial_success"` and asserts `invalid_response`.

## Verification

Deep review included source tracing across `UnifiedToolManager`, `ToolPlatform`, `ToolRuntime`, `ToolPolicyEngine`, and the business/knowledge/memory/action executors. I did not re-run the full DB-backed suite during this review; the phase context reports the full relevant suite passed as `184 passed, 1 warning`.

Additional targeted check with the MOCA-approved environment entrypoint confirmed the warning:

```bash
uv run python -c "from src.tools.validation import validate_json_value; schema={'type':'number'}; validate_json_value(float('nan'), schema); validate_json_value(float('inf'), schema); print('non-finite accepted')"
```

Result: `non-finite accepted`.

---

_Reviewed: 2026-07-02T02:21:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
