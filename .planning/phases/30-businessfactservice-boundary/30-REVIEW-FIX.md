---
phase: 30-businessfactservice-boundary
fixed_at: 2026-06-27T23:36:18Z
review_path: .planning/phases/30-businessfactservice-boundary/30-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 30：代码审查修复报告

**修复时间：** 2026-06-27T23:36:18Z
**源 review：** `.planning/phases/30-businessfactservice-boundary/30-REVIEW.md`
**Iteration：** 1

**汇总：**
- 范围内 findings：5
- 已修复：5
- 已跳过：0

## 已修复问题

### CR-01: Public Business Imports Fail With Circular Import

**状态：** fixed
**修改文件：** `src/tools/__init__.py`, `tests/business/test_schemas.py`
**Commit：** 51ec32c
**应用修复：** 将 `UnifiedToolManager` 的 package-level 导入改为 `__getattr__` 懒加载，避免 `src.business.*` public import 触发 `src.tools.manager` 循环导入；新增新解释器导入回归测试覆盖 `src.business`, `src.business.schemas`, `src.business.service`。

### CR-02: ToolResultV2 Success Can Approve Cross-Tenant BusinessFactRefs

**状态：** fixed: requires human verification
**修改文件：** `src/business/service.py`, `tests/business/test_service.py`
**Commit：** 72b5f31
**应用修复：** 在 `ToolResultV2` 到 `BusinessFactResultV1` 的转换路径上补齐 service-approved refs 校验，要求成功或部分成功结果必须携带 refs 且所有 ref tenant 与当前 `tenant_id` 一致；新增 service 与 tool facade 双入口 wrong-tenant 回归测试。

### CR-03: Verifier Accepts Business Fact Claims From The Wrong Tenant

**状态：** fixed: requires human verification
**修改文件：** `src/agent/rag_context/verifier.py`, `tests/agent/rag_context/test_authority_boundaries.py`
**Commit：** 44ad796
**应用修复：** 在 verifier Level 1 和 `_business_authority_passed()` 中校验 business refs 的 tenant scope，错误 tenant 会产生 `tenant_scope_invalid` 并 fail closed；新增 business fact claim 与 action recommendation claim 的 wrong-tenant 回归测试。

### WR-01: partial_success Facts Are Produced But Dropped By Consumers

**状态：** fixed: requires human verification
**修改文件：** `src/agent/nodes/investigate.py`, `src/business/service.py`, `tests/agent/test_nodes/test_investigate.py`, `tests/business/test_service.py`
**Commit：** f5323a4
**应用修复：** 将 `partial_success` 纳入 fact-bearing statuses，让 investigate 与 `BusinessToolService.fetch_context()` 聚合有 data 和 service-approved refs 的部分成功结果，同时保留 `tool_results` 中的 `partial_success` 状态；新增两个聚合回归测试。

### WR-02: BusinessFactService Rejects Legacy List Merchant Scopes Despite The Tool Context Contract

**状态：** fixed: requires human verification
**修改文件：** `src/business/service.py`, `tests/business/test_service.py`
**Commit：** 2ec2b78
**应用修复：** `_merchant_scope_allows()` 改为复用 `MerchantScopeV1` 解析 dict 与 legacy list scope，和 policy 层保持一致；新增 helper 匹配测试与 `merchant_scope=["*"]` 到达 adapter 的回归测试。

---

_Fixed: 2026-06-27T23:36:18Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
