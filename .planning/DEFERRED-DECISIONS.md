# Deferred Architecture Decisions (Gray-Area Register)

> 用途：记录已讨论清楚、但**当前阶段不实现**的架构选项与准入规则，作为后续 phase 规划的输入。
>
> 状态语义沿用 `docs/agent-architecture-phase-decomposition.md` §1 Deviation Handling Protocol 的字段。
>
> 重要边界：本文件不是 normative spec。其中任何一条若将来被采纳，必须按对应 Owner 列指向的 phase 流程，提升进 `docs/contract-spec.md` / `docs/architecture-overview.md` 后才生效。本文件只负责"不丢失决策"，不替代 spec。

约束依据（讨论时已从仓库核对）：

- 用户画像：MOCA 使用者是**商家运营/售后团队的内部坐席**，不是 C 端买家（`README.md:5`、`docs/architecture-overview.md:5,7`）。权限模型为企业内部 RBAC（`tenant_id` / `merchant_scope` / `role` / `permissions`，`docs/contract-spec.md:20-38`）。买家在系统里是被处理的**对象**（订单中的 customer），不是 Agent 的对话方。
- 业务主线动作：退款、补偿、封禁/解封、工单关闭（`docs/architecture-overview.md:627`）——全部为高风险、不可逆、需审计动作。
- spec 既有立场：不采用完全开放 ReAct 作为默认执行模型（`docs/architecture-overview.md:54,625-627`、`docs/migration-plan.md:16`）；write/action tools 不由 LLM 直接调用（`docs/contract-spec.md:838`）；router 必须 deterministic、side-effect-free（`docs/contract-spec.md:195`、§9.5）；普通聊天入口的任何 `approval_decision` 值均视为 untrusted invalid state（`docs/contract-spec.md:370`）。

---

## GAD-01：只读调查段的 bounded tool loop（deferred option）

| 字段 | 内容 |
| --- | --- |
| ID | GAD-01 |
| Source requirement | 用户提出"混合 ReAct"：外层确定性 graph，仅在低风险只读节点内允许受控 tool 循环；原则是"只读/调查阶段允许 bounded 自由，一旦触及写动作就强制切回确定性 + 人审" |
| Conflicting evidence | **【2026-07-06 复核订正】此前记录的「`investigate.py` 仍是 legacy 确定性实现、LLM 决策 loop 从未落地」已过时。当前 `docs/contract-spec.md` §9.4 已完成 agentic 提升，Phase 49 也已把 `src/agent/nodes/investigate.py` 迁移为 bounded read-only ReAct planner 主路径：planner 每轮输出 `{next_tool, args, reason}` 或 `{stop, stop_reason}`，经 strict validation 与 `ToolPlatform.invoke` 单步调用；legacy deterministic `plan_next_step` 仅作为 timeout / invalid / unavailable fallback。当前剩余冲突不再是“ReAct 未实现”，而是 graph-level node operation emission、trace/replay parent-operation 语义和目标 graph canonical node 边界仍需后续 phase 收敛。 |
| Type | RESOLVED_IMPLEMENTATION_DEBT（bounded-loop 主契约已就位于 §9.4；Phase 49 已完成实现迁移；observation→slot 回流按已定 A/loop-local 落地，不入 spec、不写 `active_slots`）。前身为 UNSUPPORTED_ASSUMPTION（spec 未覆盖），随 §9 提升完成而收敛为实现迁移欠账，并于 Phase 49 关闭。 |
| Recommended handling | **方向已由用户采纳并由 Phase 49 实现：`investigate` 内部 bounded read-only ReAct 是当前主路径。** 后续不再规划“把 `investigate` 从 legacy 迁到 ReAct”的 phase；应改为规划 ReAct hardening / graph canonical migration：补 graph-level node operation emission，完善 trace/replay parent-operation 语义，并把外部 graph 入口与出口节点继续收敛到 `safety_pre_route`、`contextual_intent_resolve`、`slot_resolution_gate`、`memory_context_load`、`risk_gate` 等 canonical boundary。observation→slot 回流保持 Phase 49 决策 **A：loop-local**：回流值只存在于 investigate planner 工作记忆，不写入 graph 全局 `active_slots` / `extracted_slots` / `candidate_slots`；全局 resolved slot writer 以当前目标契约中的 `slot_resolution_gate` / MemoryService 语义为准。 |
| Readiness impact | NON_BLOCKING（不阻塞其他 phase）。**前置依赖已满足**：spec §9.4/§9.5 已提升、§17.2 已定义 loop 内 tool/RAG 事件的 `iteration` 标注与回放规则。实现迁移可随时立为独立执行 phase。 |
| Owner | Phase 49: Investigate Bounded ReAct Loop Migration（v2.1）。旧记录的 Phase 10/11 属已归档的 v1.9 milestone 编号，不再作为 owner。 |
| Status | IMPLEMENTED_WITH_LIMITATIONS（2026-07-04 Phase 49 验证关闭）：`investigate` 默认主路径已迁移为 structured LLM planner → strict validation → one read/retrieval tool or stop；legacy deterministic `plan_next_step` 保留为 timeout/invalid/unavailable fallback，不再是并列主控。loop-local discovered slots 已支持 order→ticket 链式调查且不写 `active_slots` / `extracted_slots` / `candidate_slots`；§12.4 八个 read/retrieval tools exact-set + ToolPlatform invoke smoke 已覆盖；planner 只看 projected observation；write/action tool 被拒绝；outer graph routers / intent / memory / risk / approval / action 回归通过。限制：每轮 tool/RAG event 已带 `iteration`、distinct `operation_id`、`attempt`、`tool_call_id`，且在 `configurable["node_operation_id"]` / `investigate_operation_id` 存在时写 `parent_operation_id`；Phase 49 未新增 graph-level node operation emission，因此 replay parent-operation 语义按“可接收 parent、未强制 graph 自动提供 parent”记录为 limitation。后续 `docs/contract-spec.md` §9 已另行同步目标 graph / canonical node 边界，不改变 Phase 49 的代码交付边界。 |

**实现时必须同时满足（缺一不可）：**

1. **写动作侧坚决确定性，别碰。** 这是 demo 的安全卖点，也是 `docs/contract-spec.md:838` 的硬约束（write tool 不由 LLM 直接调）。loop 内即使 LLM 判断"需要退款/补偿"，也只能产出 `proposed_action` 候选，由 `route_after_recommendation` 强制送入 `risk_gate`；loop 本身不得触达任何 write tool。
2. **只读调查侧的 bounded tool loop 三护栏：**
   - `max_iterations` 上限（建议 3–5），防止无限循环；
   - tool allowlist 仅含只读 tool（继承 §12.4 allowlist 思想，只含 `get_*` / `search_*`）；
   - 每次 tool call 仍发**独立 trace 事件**（满足 §9 / Phase 15 ReplayEventV3，避免 loop 内部成为回放黑盒）。
3. 对外仍是 graph 中**一个确定性节点**：入边/出边固定，仍走对应 `route_after_*`；不得让 loop 改变节点的对外路由契约。
4. 不可触发任何写动作；不得绕过 `risk_gate` / `approval` / executor。

**结构决议（2026-06，方向确定后）：** 调查段采用「合并为单 `investigate` bounded-loop 节点」方案，而非「三节点各自内部 loop」。理由：GAD-01 的目标场景是「查完物流再决定要不要查政策」这类跨数据源动态调查，三节点固定串联在 router 层无法表达跨节点动态；合并后对外仍是确定性单节点（固定入边/出边 + 单一 `route_after_investigate`），内部 bounded loop 受三护栏约束。ReplayEventV3 已具备表达能力（node operation 下挂多个 tool operation，tool 事件 parent_operation_id 指向 node operation），提升时仅需显式声明「同一 node operation 下允许多个 tool operation」并加 iteration 标注，非 schema breaking change。

**引入时机判据（2026-07 更新，取代原保守判据）：** 原判据为「仅当只读调查路径变得高度动态时才评估引入，路径相对固定时优先保留固定链」。**该判据已被用户 2026-07 决策取代**——用户已明确「直接设计成 ReAct、真正实现一个 agent」，不再以「路径是否已变高度动态」作为触发条件。方向即为直接推进 `investigate` 的 ReAct loop 实现迁移；固定链仅作为 LLM 超时 / 输出非法时的**确定性 fallback 安全网**保留（即当前 `plan_next_step` 逻辑降级为 fallback，而非主决策路径），不再作为默认优先形态。

**地基约束（2026-07 用户确认，三段信任边界）：** 与 `docs/target-agent-platform-architecture-plan.md` §6 的信任边界分组一致——① 入口确定性（身份/授权/安全 tier 为 a-priori 规则判断，LLM 不参与鉴权）；② 只读认知环自由（`investigate` bounded loop 内 LLM 自由选只读工具、可链式、可发现 slot）；③ 出口确定性（evidence 校验 / claim 校验 / risk / approval / 写动作全部 fail-closed、LLM 不可覆盖）。自由严格限定在 ② 只读环内；spec 落点为：① 入口：deterministic 节点（`safety_pre_route` / `slot_resolution_gate` 等）+ `contextual_intent_resolve` 的 LLM 候选 + deterministic IntentPolicyEngine 混合裁决（非纯 deterministic）；② 认知环：§9.4 investigate loop 契约；③ 出口：完整 fail-closed 硬约束需联合 §9.4/§9.5 + §11.2 + §12 + §15，§9 单独只是 partial coverage。

---

## GAD-02：未来新增 intent 的准入规则（intent taxonomy admission rule）

| 字段 | 内容 |
| --- | --- |
| ID | GAD-02 |
| Source requirement | 用户要求：当前 MVP **不新增**新的问答/业务 intent；但需明确"未来一定可以新增 intent"的准入规则，避免将来无约束扩张，也避免把 bounded loop 默认扩展到所有未来 intent |
| Conflicting evidence | intent precedence / required-slot 由 Phase 11 owner（`docs/migration-plan.md:17`、`docs/contract-spec.md` §11.2）；当前 intent 表未包含 taxonomy 准入字段 |
| Type | UNSUPPORTED_ASSUMPTION（流程性准入规则，spec 未显式定义） |
| Recommended handling | 登记为 Phase 11 规划时需纳入的准入规则。未来新增任何 intent，必须逐个评估并显式定义下列字段后才能进入 intent taxonomy；**不得默认继承、不得批量放开**。 |
| Readiness impact | NON_BLOCKING（当前不新增 intent） |
| Owner | Phase 11（intent / clarification）；若形成 normative taxonomy 字段，提升进 `docs/contract-spec.md` §11 |
| Status | DEFERRED_WITH_OWNER |

**新增 intent 的必填准入字段：**

| 字段 | 取值 / 含义 |
| --- | --- |
| `risk_level` | `read_only` / `advisory` / `write_action` / `high_risk_write` |
| `response_mode` | `direct_answer` / `advisory_answer` / `recommendation_with_approval` / `deterministic_execution` |
| `tool_allowlist` | 允许调用的 tool 集合；是否全部只读 |
| `bounded_loop_allowed` | 是否允许 bounded tool loop（默认 false；仅 read-only investigation 类可考虑 true，且仍受 GAD-01 三护栏约束） |
| `max_iterations` | 若允许 loop，必须给出上限 |
| `routing_precedence` | 与现有 intent 冲突时的优先级裁决 |
| `audit/replay requirements` | 该 intent 的 trace event 与 replay 契约要求 |

**红线（因用户为内部坐席而强化）：** 任何新增问答/聊天类 intent 都不得产生"已审批"信号。坐席在问答中说"就按全额退吧"只能转为 `proposed_action` 候选，审批只能走 trusted approval API（`docs/contract-spec.md:421`，独立入口，不经 `receive_request -> intent_classification -> route_after_intent`）。对应 `docs/contract-spec.md:370`：普通入口任何 `approval_decision` 视为 untrusted invalid state。

---

## GAD-03：policy_qa / 事实问答等纯问答终态（已存在，标记未来可多步取证）

| 字段 | 内容 |
| --- | --- |
| ID | GAD-03 |
| Source requirement | 用户提出加"客服问答（不含动作）"。讨论确认：当前所指的纯问答终态 spec **已覆盖**，本次不新增 intent |
| Conflicting evidence | 已存在的只读终态：`policy_qa_path`（`docs/architecture-overview.md:270`）、`order_status` 业务事实问答 `business_fact_response`（`docs/architecture-overview.md:280`）、`advise` 且无 proposed action 可跳过 action（`docs/contract-spec.md:317`） |
| Type | CODE_MISMATCH（实为"已覆盖"澄清，非缺口） |
| Recommended handling | 当前阶段：Phase 11 规划时**确认** intent 表已覆盖 `policy_qa` + 订单事实问答 + `advise / support advice` 这些只读终态即可，不新增 intent、不改 response mode。**未来选项（与 GAD-01 分离登记）：** 若问答路径本身也需要多步只读取证，再作为**单独的 deferred option** 重新评估，并同样套用 GAD-01 三护栏 + GAD-02 准入规则。 |
| Readiness impact | NON_BLOCKING |
| Owner | Phase 11（确认覆盖）；未来问答多步取证为独立 deferred option，owner 同 GAD-01 |
| Status | RESOLVED（已覆盖部分）/ 未来扩展部分 DEFERRED_WITH_OWNER |

---

## 规划时的引用指引

- Plan **Phase 10** 时：读 GAD-01（routing 是否为未来只读 bounded loop 预留节点边界，但本期不实现）。
- Plan **Phase 11** 时：读 GAD-02（intent taxonomy 准入规则）+ GAD-03（确认现有只读问答终态覆盖）。
- 任何一条被采纳实现前，先按 Owner 列把它提升进 `docs/contract-spec.md` / `docs/architecture-overview.md`，再进入对应 phase plan 的 coverage 矩阵。
