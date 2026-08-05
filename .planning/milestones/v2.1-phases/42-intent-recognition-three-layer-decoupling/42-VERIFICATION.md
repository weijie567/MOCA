---
phase: 42-intent-recognition-three-layer-decoupling
verified: 2026-07-02
status: passed_retroactive
score: IDR-01 verified only
workflow: retroactive_record
metadata_normalized_by: phase-60-plan-03
metadata_normalized_at: 2026-07-08
---

# Phase 42 Verification — Intent Recognition Three-Layer Decoupling

> 本 phase 是**回溯式登记**：代码在正式建立 phase 记录前已由 Codex 实现、Claude 审核、并跑绿。
> 本文件锚定该实现的验证证据，不代表一次 plan-then-execute 的执行验证。

## 验证性质说明

- 代码基线 commit：`a0a98e4` — `refactor(intent): decouple intent recognition into three explicit layers`（4 files, +774/-92）。
- 验证时间：2026-07-02。
- 验证由 Claude 在建立本 phase 记录前**实跑**得出，非引用旧记录。

## 目标回溯（对应 ARCHITECTURE-DEBT.md 第 2 节）

| 缺陷 | 处理 | 状态 |
|------|------|------|
| ID-01 关键词候选覆盖 LLM 语义判断 | 拆 `derive_keyword_signals`（只产候选）+ `arbitrate_intent`（唯一显式仲裁）；关键词仅在 LLM 低置信或 LLM 自身列出该意图时可覆盖 | ✅ 已修复并验证 |
| ID-03 意图/操作/风险三维耦合 | 新增 `RiskDecision` + 声明式 `RISK_POLICY_TABLE`，`resolve_risk_decision` 查表；删除旧同值死分支 | ✅ 已修复并验证 |
| 三层解耦（语义/风险/澄清）目标态第一步 | 新增 `SemanticIntent` / `RiskDecision` / `ClarificationDecision` 三层契约，`classification_trace` 记全三层 | ✅ 单意图路径已落地 |

**明确未覆盖（不在本 phase 范围，仍 🔴）**：
- ID-02 置信度校准：`decide_clarification` 只留 `calibrated_confidence` 入参占位，未实现真实校准。
- ID-04 多意图 / TaskPlan：本 phase 未做，属后续 phase（多意图档位 A）。

## 验证证据（实跑）

**测试**（遵守 MOCA 禁裸 pytest 硬规则，用 `uv run pytest`）：

```
uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py \
  tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py \
  tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py \
  tests/architecture/test_phase32_static_contract.py -q
```

结果：`1230 passed, 1 skipped, 22 warnings`（2026-07-02 实跑）。

**Lint**：

```
uv run ruff check src/agent tests/agent
```

结果：`All checks passed!`

## 行为变化登记（唯一一条）

- Query `"这个不算投诉吧，我就是问下退款进度"`：旧行为被关键词 `"投诉"` 误抬为 `complaint_escalation`；新行为保持 LLM 高置信的 `refund_troubleshooting`。此为 ID-01 仲裁规则的有意修正，已由 `tests/agent/test_intent_routing.py` 锁定。

## 验证边界（未验证项，如实标注）

- DB-backed 套件未在本次纳入（本 phase 改动集中在 `src/agent/intent_policy.py` / `classify_intent.py`，为纯内存分类/策略逻辑，上列测试已覆盖其行为）。
- 未做置信度校准的统计验证（ID-02 未实现，无从验证）。
- 未验证多意图路径（ID-04 本 phase 不涉及）。

## 关联

- 执行规格：`.planning/intent-layering-codex-brief.md`
- 台账：`.planning/ARCHITECTURE-DEBT.md` 第 2 节 ID-01 / ID-03 / ID-DESIGN
- 后续：多意图档位 A（`.planning/intent-multi-a-codex-brief.md`），将作为下一个整数 phase 立项
