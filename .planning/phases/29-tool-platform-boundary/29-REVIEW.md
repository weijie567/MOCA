---
phase: 29-tool-platform-boundary
reviewed: 2026-06-23T12:08:07Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - src/agent/nodes/investigate.py
  - src/conversation/service.py
  - src/tools/manager.py
  - src/tools/manager_results.py
  - src/tools/platform.py
  - src/tools/policy.py
  - src/tools/projection.py
  - src/tools/runtime.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/architecture/test_tool_boundaries.py
  - tests/conversation/test_service.py
  - tests/replay/test_decision_events.py
  - tests/replay/test_replay_migration_contract.py
  - tests/replay/test_tool_policy_events.py
  - tests/tools/test_tool_platform.py
  - tests/tools/test_tool_result_storage.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-23T12:08:07Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the tool-platform facade, runtime policy chain, result projection, conversation tool-result storage, investigate integration, replay policy events, and the scoped tests. The main platform boundary is present, but two correctness/security issues remain: nested case-memory refs can bypass the projector's raw-sentinel stripping, and runtime auth can crash for the legacy list-form merchant scope still allowed by `ToolCallContext`.

## Critical Issues

### CR-01: Nested Case-Memory Refs Can Leak Raw Payload Keys Into Normalized Graph State

**File:** `src/tools/projection.py:198`
**Issue:** `_sanitize_case_memory()` strips top-level case-memory item fields, but for nested `policy_refs` and `source_refs` it copies every scalar key/value without checking `_RAW_SENTINEL_KEYS`. A `search_case_memory` result such as `policy_refs=[{"doc_key": "refund", "raw_payload": "secret"}]` is projected into `normalized_result["_case_memory_items"]` with `raw_payload` intact. `src/agent/nodes/investigate.py:552` then copies that projection into graph state, violating the projector contract that raw sentinel keys must never appear in normalized graph/service surfaces.
**Fix:**
```python
def _sanitize_ref_list(self, refs: list[Any]) -> list[dict[str, Any]]:
    safe_refs: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        safe_ref = {
            str(key): value
            for key, value in ref.items()
            if str(key).lower() not in _RAW_SENTINEL_KEYS
            and isinstance(value, (str, int, float, bool))
        }
        if safe_ref:
            safe_refs.append(safe_ref)
    return safe_refs
```
Then call this helper for `policy_refs` and `source_refs`, and add a regression test with a nested `raw_payload` / `secret` ref asserting neither key nor value appears in `projection.normalized_result` or `investigate()` state.

## Warnings

### WR-01: Runtime Auth Raises Instead Of Denying Legacy List Merchant Scope

**File:** `src/tools/policy.py:411`
**Issue:** `ToolCallContext.merchant_scope` explicitly allows `dict[str, Any] | list[str]`, and legacy call paths/tests still use list-form scopes. When a tool call includes an explicit `merchant_id`, `_build_resource_binding()` calls `MerchantScopeV1.model_validate(merchant_scope)` for any non-`MerchantScopeV1` value. A list such as `["M-ALLOWED"]` raises `ValidationError`, escaping `ToolRuntime.invoke()` instead of returning an allowed/denied `ToolInvocationOutcome`.
**Fix:** Normalize list-form scopes before validation and fail closed on malformed scopes.
```python
try:
    if isinstance(merchant_scope, MerchantScopeV1):
        scope = merchant_scope
    elif isinstance(merchant_scope, list):
        scope = MerchantScopeV1(merchant_ids=merchant_scope)
    else:
        scope = MerchantScopeV1.model_validate(merchant_scope)
except ValueError:
    scope_denied = True
else:
    if not scope.allows(merchant_id=str(value)):
        scope_denied = True
```
Add regression coverage for both `merchant_scope=["M-ALLOWED"]` and `merchant_scope=["M-OTHER"]` with `get_merchant_risk`.

---

_Reviewed: 2026-06-23T12:08:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
