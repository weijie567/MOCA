---
phase: 30-businessfactservice-boundary
fixed_at: 2026-06-27T23:56:53Z
review_path: .planning/phases/30-businessfactservice-boundary/30-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 30：代码审查修复报告

**修复时间：** 2026-06-27T23:56:53Z
**源 review：** `.planning/phases/30-businessfactservice-boundary/30-REVIEW.md`
**Iteration：** 1

**汇总：**
- 范围内 findings：2
- 已修复：2
- 已跳过：0

## 已修复问题

### CR-01: Action/Business Fact Verifier Can Support Claims Without Passing Tenant Scope

**状态：** fixed: requires human verification
**修改文件：** `src/agent/rag_context/verifier.py`, `tests/agent/rag_context/test_authority_boundaries.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
**Commit：** cc046a4
**应用修复：** `_business_authority_passed()` 在缺失 trusted tenant 时 fail closed；business fact / action recommendation 的 Level 1 检查在缺失 trusted tenant 时追加 `tenant_scope_invalid`；action recommendation 在 tenant scope 未通过时直接返回 `UNAUTHORIZED`，同时保留 business fact authority 失败的诊断码。新增 wrong-tenant policy evidence 与缺失 trusted tenant 的 business fact 两条回归测试，并记录本地验证过程中已处理的诊断码回归。
**验证：** `python -c "import ast; ..."` 解析通过；`uv run pytest tests/agent/rag_context/test_authority_boundaries.py -q` 结果为 `11 passed, 1 warning`。

### IN-01: Projection Migration Left Dead Helpers Behind

**状态：** fixed
**修改文件：** `src/agent/nodes/investigate.py`, `src/tools/projection.py`
**Commit：** c51b174
**应用修复：** 删除未调用的 `_case_memory_items()`、`_without_raw_payload()` 和 `_BUSINESS_FACT_REF_KEYS`，保留现有 projector-normalized case memory 与 envelope business refs 活路径。
**验证：** 精确 `rg` 检查确认 deleted helpers/constant 无剩余定义；AST 解析通过；`uv run pytest tests/agent/test_nodes/test_investigate.py tests/tools/test_tool_platform.py -q` 结果为 `56 passed, 1 warning`。

---

_Fixed: 2026-06-27T23:56:53Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
