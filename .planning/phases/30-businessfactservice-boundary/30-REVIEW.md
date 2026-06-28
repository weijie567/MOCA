---
phase: 30-businessfactservice-boundary
reviewed: 2026-06-28T00:08:56Z
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
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-06-28T00:08:56Z
**Depth:** deep
**Files Reviewed:** 15
**Status:** issues_found

## Summary

本次按 deep 深度复审 15 个显式 scoped 文件，并额外核对了最新两个 post-fix commit 的目标边界。`cc046a4` 的 tenant-scope 修复仍在：action recommendation 在 Level 1 tenant scope 失败时会返回 unauthorized，不会打开 `allows_action_recommendation`；business fact authority 在 `trusted_context.tenant_id` 缺失时 fail closed；wrong-tenant policy evidence / business refs 不会产生可用 action。`c51b174` 删除的旧 projection helper/constant 已无残留调用点，`_without_raw_payload`、旧 `_case_memory_items`、`_BUSINESS_FACT_REF_KEYS` 均未在 `src/` / `tests/` 中出现。

既有 Phase 30 修复也保持有效：`src.business` / `src.tools` import smoke 通过；`ToolResultV2` 只接受 service-approved business refs；`partial_success` 会聚合 facts/refs；legacy list merchant scope 仍按 canonical scope 处理。目标测试通过。

发现 1 个新 Warning：verifier API 在 action claim 没有 cited policy evidence 时，可能同时输出 blocking reason code 和 action allow flags。当前生产 `generate_recommendation` route map 会用 `policy_evidence_required` 阻断最终 draft，但 verifier 边界对象自身不应暴露自相矛盾的 allow 状态。

## Warnings

### WR-01: Action Recommendation 可在 Level 1 membership 失败时打开 allow flags

**File:** `src/agent/rag_context/verifier.py:485`

**Issue:** `_check_level1()` 会在 action recommendation 缺少有效 policy evidence membership 时加入 `policy_evidence_required`，但 `_verify_action_recommendation_claim()` 只在 `claim.cited_evidence_ids` 非空且 membership 失败时阻断。若 action claim 没有 `cited_evidence_ids`，但带有 supported policy/business dependency results 和有效 business fact ref，会落到 `SUPPORTED` 分支，并返回 `allows_claim=True`、`allows_action_recommendation=True`、`blocks_proposed_action=False`，同时 reason_codes 里仍包含 `policy_evidence_required`。

**Fix:**

```python
if not level1.membership_passed:
    if "policy_evidence_required" not in reason_codes:
        reason_codes.append("policy_evidence_required")
    return self._result(
        claim,
        VerificationOutcome.INSUFFICIENT,
        level1=level1,
        reason_codes=reason_codes,
    )
```

同时增加回归测试：action recommendation 在 `cited_evidence_ids=[]`、dependencies 均为 `supported`、business refs 有效时，必须 `outcome != supported`、`allows_action_recommendation is False`、`blocks_proposed_action is True`。

## Verification

- `uv run python -c "import src.business; import src.business.schemas; import src.business.service; import src.tools; print('imports-ok')"` -> `imports-ok`
- `git diff --check d1755d9168ff751e29608afcf947dba7d68dd1fb^..HEAD -- <15 reviewed files>` -> passed
- `uv run pytest tests/business/test_schemas.py tests/business/test_service.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/tools/test_tool_platform.py -q` -> `159 passed, 1 warning`

---

_Reviewed: 2026-06-28T00:08:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
