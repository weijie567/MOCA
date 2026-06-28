---
phase: 30-businessfactservice-boundary
reviewed: 2026-06-28T00:23:48Z
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
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 30: Code Review Report

**Reviewed:** 2026-06-28T00:23:48Z
**Depth:** deep
**Files Reviewed:** 15
**Status:** clean

## Summary

本次是 Phase 30 post-fix re-review，范围为当前 workflow 传入的 15 个文件。深度检查覆盖 BusinessFactService boundary、ToolPlatform/ToolPolicy/ToolResultProjection 调用链、investigate 的 tool-result 聚合、MaterialClaimVerifier 的 policy/business/action authority gates，以及对应测试。

All reviewed files meet quality standards. No issues found.

专项复核结论：

- `ACTION_RECOMMENDATION_CLAIM` 在 `cited_evidence_ids=[]` 时会得到 `membership_passed=False` 和 `policy_evidence_required`，并在 action 分支返回非 supported；`allows_action_recommendation` 不会打开。
- `policy_evidence_required`、`tenant_scope_invalid`、`business_fact_ref_required` 路径均保持 fail-closed；allow flags 由 `_result()` 再次按 `outcome == supported` 约束，未发现与 allow 状态冲突的路径。
- 既有 Phase 30 修复保持 intact：`src.tools.__getattr__` 避免 import cycle；BusinessFactService 校验 `ToolResultV2.business_fact_refs` tenant；verifier 对 trusted tenant 缺失/错租户 fail-closed；service 只聚合 service-approved facts；`partial_success` 进入 facts/refs 聚合；legacy list merchant scope 仍被支持。
- Policy retrieval 仍归 ToolPlatform/Knowledge executor 边界所有，未回流到 BusinessToolService 或 raw repository seam。

验证：

- `.venv/bin/pytest -q tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/business/test_schemas.py tests/business/test_service.py tests/tools/test_tool_platform.py`
- 结果：160 passed, 1 warning。
- 备注：系统默认 `pytest` 指向 Python 3.9，因项目要求 Python 3.12 且代码使用 `datetime.UTC`，初次运行在环境加载阶段失败；按 `.python-version`/`.venv` 切到 Python 3.12.13 后通过。

---

_Reviewed: 2026-06-28T00:23:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
