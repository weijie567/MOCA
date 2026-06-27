---
phase: 30-businessfactservice-boundary
reviewed: 2026-06-27T23:19:50Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - src/agent/nodes/investigate.py
  - src/agent/rag_context/verifier.py
  - src/business/__init__.py
  - src/business/schemas.py
  - src/business/service.py
  - src/tools/executors/business.py
  - src/tools/policy.py
  - src/tools/projection.py
  - tests/agent/rag_context/test_authority_boundaries.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_policy_retrieval_ownership.py
  - tests/business/test_schemas.py
  - tests/business/test_service.py
  - tests/tools/test_tool_platform.py
findings:
  critical: 3
  warning: 2
  info: 0
  total: 5
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-06-27T23:19:50Z
**Depth:** deep
**Files Reviewed:** 14
**Status:** issues_found

## Summary

本次 deep review 覆盖 Phase 30 新增的 BusinessFactService 边界、ToolPlatform 接入、投影、investigate 累积逻辑、verifier authority checks 和对应测试。默认 order/refund/ticket adapters 的主路径测试通过，但跨文件检查发现 3 个会破坏边界安全或直接导致导入崩溃的问题，以及 2 个 contract/状态语义不一致问题。

验证记录：

- `uv run pytest tests/business/test_service.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py tests/business/test_schemas.py -q` -> `147 passed, 1 warning`
- `git diff --check -- <reviewed files>` -> passed
- 裸 `pytest` 使用了本机 Python 3.9 入口而失败，已按项目规则记录到 `.planning/LOCAL-VALIDATION-ISSUES.md`。

## Critical Issues

### CR-01: Public Business Imports Fail With Circular Import

**File:** `src/business/schemas.py:10`

**Issue:** `src.business.schemas` imports `src.tools.contracts`, but importing any `src.tools.*` submodule first executes `src/tools/__init__.py`, which eagerly imports `UnifiedToolManager`. That pulls `src.tools.manager -> src.tools.executors.business -> src.business.service -> src.business.schemas` while `schemas.py` is still initializing. Direct public imports now crash:

```text
uv run python -c "import src.business"
uv run python -c "import src.business.schemas"
uv run python -c "import src.business.service"
```

All three fail with `ImportError: cannot import name 'BusinessContextV1' from partially initialized module 'src.business.schemas'`.

**Fix:** Break the eager package import cycle. Prefer making `UnifiedToolManager` lazy in `src/tools/__init__.py` or removing that package-level export.

```python
# src/tools/__init__.py
from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import ToolCallContext, ToolError, ToolRequest, ToolResultV2

def __getattr__(name: str):
    if name == "UnifiedToolManager":
        from src.tools.manager import UnifiedToolManager
        return UnifiedToolManager
    raise AttributeError(name)
```

Add a regression test that imports `src.business`, `src.business.schemas`, and `src.business.service` in a fresh interpreter or importlib path.

### CR-02: ToolResultV2 Success Can Approve Cross-Tenant BusinessFactRefs

**File:** `src/business/service.py:350`

**Issue:** `_to_business_fact_result()` requires `ToolResultV2.business_fact_refs` to be non-empty, but it does not verify that those refs belong to the current `tenant_id`. A `ToolResultV2(status="success")` with `tenant_id="tenant-other"` in its `BusinessFactRefV1` is converted to `BusinessFactResultV1(status="ok")` and returned as service-approved. I reproduced this after preloading contracts to bypass CR-01: `wrong_tenant_status= ok ref_tenant= tenant-other`.

This undercuts the service boundary: `BusinessFactResultV1` inputs are tenant-checked in `_sanitize_domain_result()`, but the default adapter shape is `ToolResultV2`, and that path is not tenant-checked.

**Fix:** Apply the same tenant/ref validation to `ToolResultV2` success and partial-success conversion.

```python
if result.status in {"success", "partial_success"} and result.data is not None:
    has_service_approved_refs = (
        bool(result.business_fact_refs)
        and all(ref.tenant_id == tenant_id for ref in result.business_fact_refs)
    )
    if not has_service_approved_refs:
        return self._safe_result(
            "unavailable",
            resource_name=resource_name,
            tenant_id=tenant_id,
            source_system=result.source_system,
            scope_check_result="unknown",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="adapter",
        )
```

Add a regression test with a `ToolResultV2` adapter returning a wrong-tenant `BusinessFactRefV1`; assert no fact/ref is exposed by both `BusinessFactService.get_order()` and `BusinessToolService.invoke_tool()`.

### CR-03: Verifier Accepts Business Fact Claims From The Wrong Tenant

**File:** `src/agent/rag_context/verifier.py:610`

**Issue:** `_business_authority_passed()` only checks that every claim ref key exists in the context refs. It never checks those `BusinessFactRefV1.tenant_id` values against `trusted_context.tenant_id`. If the context contains a matching wrong-tenant business ref, a business fact claim is marked `supported` with `allows_claim=True`; I reproduced this with trusted tenant `tenant-good` and business ref tenant `tenant-other`.

That makes the verifier weaker than the policy evidence path, which does check tenant scope in `_check_level1()`.

**Fix:** Enforce trusted tenant matching for business refs and emit `tenant_scope_invalid` on mismatch.

```python
trusted_tenant = str(_trusted_context(context).get("tenant_id") or "")
if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
    if trusted_tenant and any(ref.tenant_id != trusted_tenant for ref in claim.business_fact_refs):
        reason_codes.append("tenant_scope_invalid")

def _business_authority_passed(claim: MaterialClaim, context: Mapping[str, Any]) -> bool:
    trusted_tenant = str(_trusted_context(context).get("tenant_id") or "")
    if not claim.business_fact_refs:
        return False
    if trusted_tenant and any(ref.tenant_id != trusted_tenant for ref in claim.business_fact_refs):
        return False
    context_refs = [
        ref for ref in _context_business_refs(context)
        if not trusted_tenant or ref.tenant_id == trusted_tenant
    ]
    context_keys = {_business_ref_key(ref) for ref in context_refs}
    return all(_business_ref_key(ref) in context_keys for ref in claim.business_fact_refs)
```

Add tests for business fact and action recommendation claims where `trusted_context.tenant_id` differs from the cited `BusinessFactRefV1.tenant_id`; both should fail closed.

## Warnings

### WR-01: partial_success Facts Are Produced But Dropped By Consumers

**File:** `src/agent/nodes/investigate.py:549`

**Issue:** `BusinessToolService._wrap_business_fact_result()` maps domain `status="partial"` to `ToolResultV2.status="partial_success"`, with data and refs. But both `investigate._accumulate_tool_result()` and `BusinessToolService.fetch_context()` only aggregate facts when `result.status == "success"`. A partial business fact becomes `insufficient` / missing even when service-approved refs exist; reproduced result: `partial_context_status= insufficient facts= {} missing= ['order']`.

**Fix:** Treat `partial_success` as a fact-bearing success for accumulation, while preserving partial status semantics.

```python
FACT_STATUSES = {"success", "partial_success"}
if result.status in FACT_STATUSES and result.data is not None and result.business_fact_refs:
    facts[resource_name] = result.data
    ...

# In investigate:
if result.status in FACT_STATUSES:
    ...  # accumulate refs/facts/policy refs
if result.status not in FACT_STATUSES:
    ...  # append error
```

Also update `src/business/service.py:591` in `BusinessToolService.fetch_context()` so compatibility aggregation does not lose partial facts.

### WR-02: BusinessFactService Rejects Legacy List Merchant Scopes Despite The Tool Context Contract

**File:** `src/business/service.py:66`

**Issue:** `ToolCallContext.merchant_scope` allows `dict[str, Any] | list[str]`, and `ToolPolicyEngine._build_resource_binding()` explicitly supports legacy list scopes. `BusinessFactService._merchant_scope_allows()` only accepts dicts, so a runtime-authorized legacy list scope such as `["*"]` is denied before the adapter runs. This is a contract mismatch at the ToolCallContext -> BusinessFactService boundary.

**Fix:** Parse merchant scope through the same canonical model used by policy, including legacy list support.

```python
from src.platform.trusted_context import MerchantScopeV1

def _merchant_scope_allows(merchant_scope: dict[str, Any] | list[str] | None, **kwargs: Any) -> bool:
    if merchant_scope is None:
        return False
    try:
        scope = (
            MerchantScopeV1(merchant_ids=merchant_scope)
            if isinstance(merchant_scope, list)
            else MerchantScopeV1.model_validate(merchant_scope)
        )
    except (TypeError, ValueError):
        return False
    return scope.allows(**kwargs)
```

Add a regression test with `ToolCallContext(merchant_scope=["*"])` and assert the service reaches the adapter instead of returning `BUSINESS_FACT_PERMISSION_DENIED`.

---

_Reviewed: 2026-06-27T23:19:50Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
