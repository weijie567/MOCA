---
phase: 33-rag-context-build-and-claim-verification
reviewed: 2026-06-29T00:55:39Z
depth: standard
files_reviewed: 55
files_reviewed_list:
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/claim_verify.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/rag_context_build.py
  - src/agent/nodes/receive_request.py
  - src/agent/rag_claim_summary.py
  - src/agent/rag_context/claims.py
  - src/agent/rag_context/domain_rules.py
  - src/agent/rag_context/schemas.py
  - src/agent/rag_context/verifier.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/agent/working_state.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/traces.py
  - src/api/schemas/agent.py
  - src/api/schemas/agent_runs.py
  - src/api/schemas/approvals.py
  - src/knowledge/schemas.py
  - src/knowledge/service.py
  - src/replay/schemas.py
  - src/replay/service.py
  - src/repositories/trace_repo.py
  - tests/agent/rag_context/test_leakage.py
  - tests/agent/rag_context/test_material_claims.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/rag_context/test_semantic_verifier.py
  - tests/agent/rag_context/test_verifier.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_nodes/test_assess_risk_and_approval.py
  - tests/agent/test_nodes/test_claim_verify.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_nodes/test_rag_context_build.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_final_response.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/agent/test_rag_context_routing.py
  - tests/agent/test_trace.py
  - tests/agent/test_working_state.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/architecture/test_phase33_rag_claim_boundaries.py
  - tests/knowledge/test_claim_verification_bundle.py
  - tests/knowledge/test_tenant_scope.py
  - tests/knowledge/test_verified_evidence_package.py
  - tests/replay/test_replay_api.py
  - tests/test_agent_runs_api.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-06-29T00:55:39Z
**Depth:** standard
**Files Reviewed:** 55
**Status:** issues_found

## Summary

按 standard 深度审查了 Phase 33 的 RAG context build、material claim 校验、路由、最终响应、trace/API/replay 投影以及相关测试。当前代码已经覆盖了 verified action recommendation 进入 risk gate、stale evidence ref 不进入 generation/final trace 等边界；本轮发现 1 个仍然成立的 correctness 问题：action claim 的 policy/business 依赖类型依赖 `claim_id` 命名约定，可能误拦截合法 canonical claims。

验证时使用了 `uv run python` 做最小复现；未运行完整 pytest 套件。

## Warnings

### WR-01: Action claim dependency role is inferred from opaque claim_id

**File:** `/Users/ming/projects/MOCA/src/agent/rag_context/verifier.py:933`
**Issue:** `_action_dependency_reason_codes` 通过 `dependency_claim_ids` 字符串里是否包含 `policy` / `business` 来判断 action recommendation 是否具备 policy 和 business 依赖。但 `MaterialClaimV1.claim_id` 在 `/Users/ming/projects/MOCA/src/knowledge/schemas.py:151` 只是普通字符串，契约没有要求 ID 必须携带类型；`/Users/ming/projects/MOCA/src/knowledge/service.py:557` 写入 `dependency_results` 时也只保留 `claim_id` 和 `outcome`，而 `_legacy_claim_from_material_v1` 在 `/Users/ming/projects/MOCA/src/knowledge/service.py:972` 只把 policy/business claim 的 ID 放进 action 依赖，丢失了原始 `claim_type`。因此当合法 claims 使用 `c1` / `c2` / `c3` 这类 opaque ID 时，policy 与 business 依赖已经是 `supported`，action claim 仍会被追加 `policy_dependency_required` 和 `business_dependency_required`，最终变成 `blocked -> final_response`。我用最小 `uv run python` 复现得到：`c1 supported`、`c2 supported`、`c3 unsupported`，bundle reason codes 包含 `policy_dependency_required` 与 `business_dependency_required`。
**Fix:**
```python
# src/knowledge/service.py
dependency_results.append(
    {
        "claim_id": claim.claim_id,
        "claim_type": claim.claim_type,
        "outcome": _outcome_value(result.outcome),
    }
)
```

```python
# src/agent/rag_context/verifier.py
dependencies = {
    str(item.get("claim_id")): {
        "claim_type": str(item.get("claim_type") or ""),
        "outcome": str(item.get("outcome") or ""),
    }
    for item in dependency_results
    if item.get("claim_id")
}
required_roles = {
    "policy"
    if dependencies[dep]["claim_type"] == "policy"
    else "business"
    for dep in claim.dependency_claim_ids
    if dep in dependencies and dependencies[dep]["claim_type"] in {"policy", "business_fact"}
}
```

保留基于 ID substring 的 fallback 只能作为 legacy 兼容，不能作为 canonical 路径的唯一判定。建议新增回归测试：`MaterialClaimV1(claim_id="c1", claim_type="policy")`、`claim_id="c2", claim_type="business_fact"`、`claim_id="c3", claim_type="action_recommendation"` 在依赖均 supported 时应 `route == "continue"` 且 `blocked_claims == []`。

---

_Reviewed: 2026-06-29T00:55:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
