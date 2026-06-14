# Agentic 调查侧讨论纪要

> 用途：记录「把只读调查段从固定链升级为有界 agent（bounded tool loop）」这条路线的讨论结论与依据，供新会话接续。
>
> 状态：**方向已由用户确定 = 做 agentic**。ChatGPT 产品验证结论 = 不是伪需求。当务之急 = 架构（改 spec 上 agentic），不是先验 Phase 8 代码。本次会话（2026-06）已决：调查段合并为单 investigate 节点；落地走 gsd-discuss-phase 提案 → 提升 §9 → plan Phase 10。
>
> 边界：本文不是 normative spec。任何条目要落地，必须先提升进 `docs/contract-spec.md` / `docs/architecture-overview.md` 再进入对应 phase plan。

---

## 一、已拍板的方向

1. **做 agentic 调查侧**（用户确定）。
2. **ChatGPT 验证：不是伪需求**——面向商家运营/售后内部坐席的 agent assist 是成立需求。
3. **当务之急 = 架构,不是 Phase 8 代码**。既然方向已定要做 agentic,就应在写更多固定链代码前先把 spec 改对（此时「早定架构」是正确的,见第四节论证）。Phase 8 代码验证/修 bug 降为次优先级。

## 二、核心设计判断

1. **真正的设计分界线不是「ReAct vs 确定性 graph」,而是「动作有没有副作用」**：
   - 写动作侧（退款/补偿/封禁/解封/工单关闭）→ 必须确定性 + 人审,不让步（`contract-spec.md:838` write tool 不由 LLM 直接调）。
   - 只读调查侧 → 放 agentic,这是 agent 真正创造价值处。

2. **目标三要点形态**：
   - ① 外层骨架只定「相位序列」（调查 → 是否有动作 → 风险 → 审批 → 执行 → 回复）和所有 gate,不为每个 intent 画死路径；
   - ② 调查内核是**有界 agent**（bounded tool loop）,吃长尾意图；
   - ③ 副作用区纯确定性,模型只产出「建议执行什么」,碰不到 write tool。

3. **MOCA 现状 vs 三要点的差异只落在「调查段」**：gate 区两者完全一致；差异是调查段 MOCA 用「固定链 + deterministic router」,三要点用「有界 agent loop」。

## 三、关键事实（已用仓库核对）

- **调查段** = 三个只读节点：`business_context_fetch`（订单/退款/物流/工单/商家风险）、`policy_evidence_retrieve`（政策/SOP）、`case_memory_retrieve`（历史 case）。全只读、可重试、无副作用。
- **客户画像**：面向**商家运营/售后团队的内部坐席**,不是 C 端买家（`README.md:5`、`architecture-overview.md:5,7`）。权限是企业 RBAC（`tenant_id`/`merchant_scope`/`role`/`permissions`）。
- **「为固定链设计」落在文档（spec §9）,不在代码**：`contract-spec.md:195` 把 router 硬定义成 deterministic、side-effect-free；但 §9.4 留了门——「MVP 可合并节点,节点数不是验收标准」。
- **Phase 8 已落地代码**（codex 写,可能有 bug 未修）：`src/knowledge/service.py`、`schemas.py`、`src/agent/nodes/retrieve_policy_evidence.py`（已接 `PolicyKnowledgeService`）,`tests/knowledge/` 有测试。
- **改 agentic 的返工范围**：KnowledgeService **service 层不返工**（无论怎么编排都调它）；只有**节点接线层**（谁调、调几次）会动,不碰 schema/数据库/tool 契约/下游/前端。

## 四、为什么「方向已定就该现在改 spec」

- 限制方向的是 **spec 文档（§9）,不是代码**——代码改起来反而是局部的。
- 「为固定链设计」是一套**咬合的契约**：§9.0 router deterministic 定义 + §9.4/9.5 node/router 表 + Phase 15 ReplayEventV3（怎么回放 loop 内多次 tool call）+ §12.4 node-level allowlist。改 agentic 要同步对齐这一套。
- **既然要做,就该在写更多固定链代码之前改**——否则等 Phase 10 把固定链 router 写完再改才是真返工。从零做也要先写 spec,现在正是那个「先写 spec」的时机。

## 五、改 spec 需要同步对齐的契约清单（下次讨论起点）

| 契约位置 | 现状（线性确定） | agentic 改动方向 |
| --- | --- | --- |
| `contract-spec.md` §9.0 | router = deterministic、side-effect-free | 需定义「调查段节点内允许 bounded tool loop」的例外,且 loop 仍不改对外路由 |
| §9.4 / §9.5 node/router 表 | 调查段三节点 + 固定 router 链 | 是否合并为一个 `investigate` agent 节点 + 其内部 loop 契约 |
| §12.4 node-level allowlist | 每节点绑定只读 tool | loop 内 allowlist 仍只含只读 tool（继承） |
| Phase 15 ReplayEventV3 | 一节点一次 tool call 的回放 | loop 内多次 tool call 的事件编号/配对/回放 |
| 三护栏 | —— | max_iterations(3–5)、只读 allowlist、每步独立 trace、不可触发写动作、对外仍是确定性节点 |

## 六、已记录的 deferred 决策（`.planning/DEFERRED-DECISIONS.md`,需随方向更新）

- **GAD-01**：只读调查段 bounded tool loop。**已升级：GAD-01 状态 DEFERRED_WITH_OWNER → OPEN（合法枚举，非自创值），措辞改为「方向已采纳、活跃推进、待 spec 化、尚未实现」，见 DEFERRED-DECISIONS.md。** 范围仍严格限定 `business_context_fetch`/`policy_evidence_retrieve`/`case_memory_retrieve`,不含 write/risk/approval/executor。
- **GAD-02**：未来新增 intent 准入规则（risk_level/response_mode/tool_allowlist/bounded_loop_allowed/max_iterations/routing precedence/audit·replay）。
- **GAD-03**：policy_qa / 事实问答 / advise 纯问答终态,spec 已覆盖。

## 七、关键问题决议（本次会话 2026-06）

1. 调查段是**合并成一个 `investigate` agent 节点**,还是**保留三节点但各自允许内部 loop**？
   【已决】合并为单 investigate 节点。理由见 DEFERRED-DECISIONS.md 结构决议。
2. ReplayEventV3 怎么表达「一个节点内多次 tool call」？（影响 Phase 15 契约）
   【已决】ReplayEventV3 无需 schema breaking change。V3 已有 operation_id/parent_operation_id/attempt，node operation 下可挂多个 tool operation；提升时仅需显式声明该合法性 + 在 redacted_payload 加 iteration 标注。
3. 改 spec 的落地路径：直接改 `contract-spec.md` §9,还是先走 `gsd-discuss-phase` 形成提案？
   【已决】先走 gsd-discuss-phase 形成提案，不直接裸改 §9。理由：跨 7 处 normative 区块（§9.0/9.1/9.3/9.4/9.5/§12.4/§17.2），属结构性大改，须走 GSD plan + Codex 双审，且 GAD-01 提升程序要求经 phase 流程。
4. 改 spec 后,Phase 10（routing 迁移）的范围是否要重写为「相位骨架 + 有界调查内核」而非「固定链 + deterministic router」？
   【已决】不整体重写 Phase 10。MOCA 外层已是相位骨架（§9.2），只需把 10b 调查段三节点固定串联换成单 investigate 节点 + bounded loop；10a（trusted context）/10c（minimal event foundation）不动，10c 反而是承载 loop 内多 tool 事件的前置依赖。注意：migration-plan.md:16 Phase 10 acceptance「不引入自由 ReAct」需在 discuss 阶段改写为「调查节点内允许 bounded loop，仍受三护栏约束、不引入自由 ReAct」。
5. GAD-01 从 deferred 升级为正式变更后,owner 仍是 Phase 10/11,还是需要新 phase？
   【已决】不开新 phase，owner 维持 Phase 10（主，调查段编排）+ Phase 11（次，GAD-02 bounded_loop_allowed/max_iterations 准入字段）。Phase 10 尚未 plan，是提升 spec 的有利时机。
