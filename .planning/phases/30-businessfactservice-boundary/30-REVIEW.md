---
phase: 30-businessfactservice-boundary
reviewed: 2026-06-27T23:48:55Z
depth: deep
files_reviewed: 15
files_reviewed_list:
  - src/agent/nodes/investigate.py
  - src/agent/rag_context/verifier.py
  - src/business/__init__.py
  - src/business/schemas.py
  - src/business/service.py
  - src/tools/__init__.py
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
  critical: 1
  warning: 0
  info: 1
  total: 2
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-06-27T23:48:55Z
**Depth:** deep
**Files Reviewed:** 15
**Status:** issues_found

## Summary

本次 deep re-review 覆盖 prompt 指定的 15 个文件，包括 review-fix 后新增进入范围的 `src/tools/__init__.py`。prior 五项已逐项复核：public `src.business` import cycle 已由 lazy `src.tools.__getattr__` 解除；`ToolResultV2` wrong-tenant `BusinessFactRefV1` 已在 `BusinessFactService` 转换层 fail closed；business fact/action recommendation 中 wrong-tenant business refs 的既有回归测试通过；`partial_success` 已进入 fact-bearing 聚合路径；legacy list merchant scope 已在 policy 与 business service 两侧支持。

验证记录：

- `uv run python -c "import src.business; import src.business.schemas; import src.business.service; import src.tools; print('imports-ok')"` -> `imports-ok`
- `uv run pytest tests/business/test_schemas.py tests/business/test_service.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/tools/test_tool_platform.py -q` -> `157 passed, 1 warning`
- `git diff --check d1755d9168ff751e29608afcf947dba7d68dd1fb^..HEAD -- <reviewed files>` -> passed

但 verifier 仍有一个相邻的 tenant-scope fail-open：action recommendation 分支会忽略 Level 1 的 tenant scope failure，且 business fact authority 在缺失 trusted tenant 时会把匹配的 business refs 当作有效 authority。

## Critical Issues

### CR-01: Action/Business Fact Verifier Can Support Claims Without Passing Tenant Scope

**File:** `src/agent/rag_context/verifier.py:467-494`, `src/agent/rag_context/verifier.py:616-627`

**Issue:** `_check_level1()` 已能把 wrong-tenant evidence/business refs 标为 `tenant_scope_invalid`，但 `_verify_action_recommendation_claim()` 不检查 `level1.authority_passed` 或 `level1.tenant_scope_passed`。因此只要 dependency results 是 `supported` 且 business refs 可匹配，即使 cited policy evidence 属于其他 tenant，action recommendation 仍会返回 `supported`、`allows_action_recommendation=True`、`blocks_proposed_action=False`，reason_codes 里甚至会同时带着 `tenant_scope_invalid`。

同一边界还有一个 fail-open：`_business_authority_passed()` 只有在 `trusted_tenant` 非空时才检查 business refs 的 tenant；如果 `trusted_context.tenant_id` 缺失，claim refs 与 context refs 只要 key 相同就会被支持。最小复现中 `trusted_context={}`、business ref tenant 为 `tenant-other`，业务事实 claim 返回 `supported True []`。

**Fix:**

```python
def _verify_action_recommendation_claim(...):
    if not level1.tenant_scope_passed or "tenant_scope_invalid" in reason_codes:
        return self._result(
            claim,
            VerificationOutcome.UNAUTHORIZED,
            level1=level1,
            reason_codes=reason_codes,
        )
    ...

def _business_authority_passed(claim: MaterialClaim, context: Mapping[str, Any]) -> bool:
    trusted_tenant = str(_trusted_context(context).get("tenant_id") or "")
    if not trusted_tenant:
        return False
    if not claim.business_fact_refs:
        return False
    if any(ref.tenant_id != trusted_tenant for ref in claim.business_fact_refs):
        return False
    context_refs = [ref for ref in _context_business_refs(context) if ref.tenant_id == trusted_tenant]
    context_keys = {_business_ref_key(ref) for ref in context_refs}
    return all(_business_ref_key(ref) in context_keys for ref in claim.business_fact_refs)
```

同时在 `_check_level1()` 中对 business fact / action recommendation claims 缺失 trusted tenant 的情况追加 `tenant_scope_invalid`，并增加两条回归测试：

- action recommendation 使用 wrong-tenant policy evidence、correct-tenant business ref、supported dependencies 时不得支持 action。
- business fact claim 在 `trusted_context.tenant_id` 缺失时不得支持，即使 claim/context business refs 完全匹配。

## Info

### IN-01: Projection Migration Left Dead Helpers Behind

**File:** `src/agent/nodes/investigate.py:716`, `src/tools/projection.py:38`

**Issue:** `investigate._case_memory_items()` 及其 helper `_without_raw_payload()` 已无调用方；`ToolResultProjector` 中 `_BUSINESS_FACT_REF_KEYS` 也已无调用方。当前实现已经改为从 projector-normalized surface 和 ToolResult envelope refs 聚合，这些残留会让后续读代码的人误以为 data-only business identifiers 或 raw-data case-memory projection 仍是活路径。

**Fix:** 删除未调用的 `_case_memory_items()`、`_without_raw_payload()` 和 `_BUSINESS_FACT_REF_KEYS`。保留现有覆盖 projector-normalized case memory 与 envelope-only business refs 的测试即可。

---

_Reviewed: 2026-06-27T23:48:55Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
