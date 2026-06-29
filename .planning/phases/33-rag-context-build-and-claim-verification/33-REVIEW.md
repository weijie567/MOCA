---
phase: 33-rag-context-build-and-claim-verification
reviewed: 2026-06-29T01:27:17Z
depth: deep
files_reviewed: 3
files_reviewed_list:
  - src/knowledge/service.py
  - src/agent/rag_context/verifier.py
  - tests/knowledge/test_claim_verification_bundle.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-06-29T01:27:17Z
**Depth:** deep
**Files Reviewed:** 3
**Status:** issues_found

## Summary

本次按 deep 深度只复核指定的 3 个文件，重点追踪 `PolicyKnowledgeService.verify_claims`、`MaterialClaimVerifier._action_dependency_reason_codes` 与回归测试之间的 cross-file 行为。

WR-01 的核心修复已成立：`PolicyKnowledgeService.verify_claims()` 现在把 canonical `claim_type` 写入 `dependency_results`，`_action_dependency_reason_codes()` 优先按 `claim_type` 判定 policy/business dependency role；当 legacy `dependency_results` 缺失 `claim_type` 时，仍回退到 `claim_id` substring 兼容旧用例。

不过 deep review 发现一个相邻边界问题：action dependency 验证仍依赖 `material_claims` 输入顺序。当前 `generate_recommendation` 主路径会先产出 policy/business claim 再产出 action claim，因此 happy path 通过；但 `MaterialClaimV1`/service contract 没有声明 action claim 必须排在依赖之后。若 canonical opaque claim 输入顺序为 `c3` action、`c1` policy、`c2` business，service 会先验证 action，此时 `dependency_results` 为空，错误阻断为 `dependency_results_required`。

验证命令：

- `uv run pytest tests/knowledge/test_claim_verification_bundle.py -q` -> 11 passed, 1 warning
- `uv run pytest tests/agent/rag_context/test_verifier.py::test_action_recommendation_requires_supported_policy_and_business_dependencies tests/agent/rag_context/test_authority_boundaries.py::test_action_recommendation_rejects_memory_or_model_supported_dependencies -q` -> 2 passed, 1 warning
- `uv run python -m py_compile src/knowledge/service.py src/agent/rag_context/verifier.py tests/knowledge/test_claim_verification_bundle.py` -> passed
- 临时 `uv run python` 只读复现：同一组 `c1/c2/c3` claims 改为 action-first 后得到 `blocked final_response ['c3'] ['dependency_results_required', 'lexical_span_supported']`

## Warnings

### WR-01: Action dependency verification is order-sensitive

**File:** `src/knowledge/service.py:550`

**Issue:** `verify_claims()` 按输入顺序逐条调用 `MaterialClaimVerifier.verify_claim()`，但只在当前 claim 验证完成后才把结果追加到 `dependency_results`。同时 `_legacy_claim_from_material_v1()` 会为 action claim 收集全量 policy/business claim IDs（`src/knowledge/service.py:978`），`_action_dependency_reason_codes()` 又要求这些依赖已经存在于 `dependency_results`（`src/agent/rag_context/verifier.py:905`）。因此 action claim 只要排在 policy/business claim 之前，即使所有 claim 都使用 canonical `claim_type` 且最终都能 supported，也会被错误标记为缺少依赖结果。

**Fix:** 在 service 层改成两阶段验证：先验证所有非 `action_recommendation` claims 并构建 typed `dependency_results`，再验证 action claims；最后按原始输入顺序组装 `claim_results` 和 `blocked_claims`，避免改变输出顺序契约。

```python
ordered_claims = list(claims)
verification_order = [
    *[claim for claim in ordered_claims if claim.claim_type != "action_recommendation"],
    *[claim for claim in ordered_claims if claim.claim_type == "action_recommendation"],
]

results_by_claim_id = {}
dependency_results = []
for claim in verification_order:
    result = await verifier.verify_claim(
        _legacy_claim_from_material_v1(claim, ordered_claims),
        context_bundle=context_bundle,
        dependency_results=dependency_results,
    )
    results_by_claim_id[claim.claim_id] = result
    dependency_results.append(
        {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "outcome": _outcome_value(result.outcome),
        }
    )

for claim in ordered_claims:
    result = results_by_claim_id[claim.claim_id]
    # existing aggregation logic
```

同时补一个 regression test：输入顺序为 `[action, policy, business]`，claim IDs 使用 `c3/c1/c2`，预期仍为 `overall_status == "verified"`、`route == "continue"`、`blocked_claims == []`。

---

_Reviewed: 2026-06-29T01:27:17Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
