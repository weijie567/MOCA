# Review: docs/agent-architecture-spec.md

## Executive Summary

- **总体判断：暂时不能直接作为后续编码实现的主要依据。**
- 它已经是一份方向正确、覆盖面较完整的架构设计草稿，适合用于对齐目标架构。
- 但关键 workflow、state、approval、action、持久化 contract 仍存在矛盾或缺失。不同工程师按当前 spec 实现，较可能得到不兼容的状态机、审批模型和数据模型。
- 建议先完成一轮只改文档的 contract 收敛，再开始目标架构迁移。

### 最大问题

1. **18 节点 workflow 存在不可执行或自相矛盾路径。**
   - `session_memory_load` 位于 slot 完整性检查之后，却要求 session memory 补齐 slot。
   - `approval edit` 没有明确 edited action 如何写回、重新检索证据和重新审批。
   - `respond -> clarification -> final` 无法定义如何继续原审批流程。
   - `trace_close` 无法覆盖 interrupt、异常、取消等未经过正常尾部节点的路径。

2. **Approval 设计尚不是可实现的状态机。**
   - `ignore` 可以保持 pending，也可以 cancelled，语义未定。
   - 多级审批只有 plan 示例，没有 level/step 状态转换、并发决策和冲突规则。
   - 审批结果没有与精确 action payload hash、policy version、evidence snapshot 绑定。

3. **AgentState 仍主要由 `dict[str, Any]` 构成。**
   - 未明确字段所有权、节点读写权限、persistent/turn/run scope。
   - 未定义 merge/reset 策略，存在跨 turn 泄漏和 stale approval/action 风险。
   - `run_id`、当前实现的 `current_run_id`、HTTP request run ID、`trace_id` 语义未统一。

4. **Action draft 与 action execution 语义重叠。**
   - spec 同时规定 demo adapter 创建 draft，又规定 `action_draft -> action_execution`。
   - demo 阶段执行节点究竟做什么、何时算成功、是否产生 `ActionExecution` 尚不明确。

5. **数据与审计 contract 不足以支持 multi-level approval、安全执行和完整 replay。**
   - Approval 不能只靠给现有表增加几个字段完成多级流程。
   - 缺少统一 trace event schema、事件序号、schema version、redaction policy 和 run 状态机。

### 最值得保留的设计

1. LangGraph 只负责 orchestration，能力层通过 service contract 隔离。
2. 明确禁止 LLM 直接控制审批、权限、租户隔离、动作执行和 memory write。
3. Knowledge、Business Tools、Memory、Approval、Actions、Observability 分层方向合理。
4. 优先单仓库、单进程、渐进式 facade 迁移，符合当前 MOCA 阶段。
5. 审计 replay 明确为持久化事件回放，而不是重新执行 LLM。

## Severity Findings

### Critical

#### C1. Workflow 顺序无法实现“session memory 补齐 slots”

- **问题**

  严格节点图中：

  ```text
  slot_extraction -> route_after_slots -> missing slots? clarification
                                   -> slots ok? session_memory_load
  ```

  但 Gate-level routing 又规定：required slots 缺失且无法从 session memory 补齐时才进入 clarification。此时 session memory 尚未加载。

- **位置/章节**

  - 7.3 V2 严格 LangGraph 节点图
  - 9.3 Conditional routing
  - 13.7 Retrieval policy

- **为什么重要**

  工程师无法确定 slot gate 应读取 checkpointer state、调用 MemoryService，还是只能读取当前 turn 提取结果。不同实现会产生不同的跨 turn 行为。

- **建议修改**

  将 session memory load 移到 intent classification 之后、slot gate 之前：

  ```text
  intent_classification
    -> session_memory_load
    -> slot_extraction
    -> resolve_slots
    -> route_after_slots
  ```

  `resolve_slots` 可以是 deterministic helper，不必成为 LangGraph 节点。

- **可直接粘贴文本**

  > `session_memory_load` 必须发生在 required-slot completeness 判断之前。Slot completeness 基于当前 turn 显式提取结果与允许继承的 session slots 合并结果判断。任何继承 slot 必须满足 scope、freshness 和 intent compatibility 规则。

#### C2. Approval 尚未定义为完整、确定的状态机

- **问题**

  `accept/edit/reject/respond/ignore/expired` 只有自然语言解释，没有明确状态、合法转换和终态定义。`ignore` 甚至允许两种冲突语义。

- **位置/章节**

  - 15.3 Multi-level approval
  - 15.4 accept/edit/reject/respond/ignore
  - 15.5 SLA and escalation

- **为什么重要**

  审批状态机决定高风险动作能否执行。缺少精确转换会造成：

  - 已编辑动作沿用旧审批。
  - 并发审批产生双执行。
  - expired/ignored 审批被恢复执行。
  - 多级审批绕过后续 level。

- **建议修改**

  明确定义：

  - Approval plan、approval level、assignment、decision 分层模型。
  - 合法状态及状态转换。
  - 乐观锁/version。
  - action payload hash、policy version、evidence snapshot 绑定。
  - edit 必须使旧审批失效，并生成新 validation revision。

- **可直接粘贴文本**

  > Approval accept 仅授权审批记录绑定的精确 `action_payload_hash`。任何 action args、target、amount、currency、evidence refs 或 policy version 变化都会使既有授权失效，并创建新的 validation revision。只有所有 required approval levels 均完成后，ActionExecutor 才能执行。

#### C3. AgentState 没有可执行的生命周期和字段所有权规则

- **问题**

  目标 schema 大量使用 `dict[str, Any]`，且未明确：

  - persistent/session/run/turn 字段分类。
  - 哪个节点允许写哪个字段。
  - 新 turn 初始化和 reset 规则。
  - list/dict 字段 merge 或 replace 规则。
  - interrupt 前后允许保留什么。

- **位置/章节**

  - 10. AgentState 目标 schema
  - 13. Memory 设计

- **代码依据**

  当前代码依赖 `receive_request` 手动清空 ephemeral 字段，并非 schema 强制保证：`src/agent/nodes/receive_request.py`。

- **为什么重要**

  Approval、action、evidence、business context 一旦跨 turn 泄漏，可能导致使用旧订单事实或旧审批执行新动作。

- **建议修改**

  增加 State Field Lifecycle Matrix，至少包含：

  | Field | Typed schema | Scope | Writer | Readers | Reset rule | Merge rule |
  | --- | --- | --- | --- | --- | --- | --- |

  身份和权限上下文应来自可信 graph config/service context，而不是依赖可变 state 值作为最终授权依据。

#### C4. `action_draft` 与 `action_execution` 定义冲突

- **问题**

  spec 规定：

  - `action_draft` 持久化草稿。
  - demo adapter “继续写 ActionDraft”。
  - 所有路径仍然执行 `action_draft -> action_execution`。

- **位置/章节**

  - 7.3 严格节点图
  - 16. Action execution 设计

- **代码依据**

  当前 `execute_action` 实际只创建 durable action draft，并不执行真实动作：`src/agent/nodes/execute_action.py`。

- **为什么重要**

  会导致 demo 阶段重复创建草稿，或错误地把“草稿创建成功”表述为“动作执行成功”。

- **建议修改**

  明确两个运行模式：

  ```text
  demo mode:     approved -> action_draft -> final_response
  external mode: approved -> action_draft -> action_execution -> final_response
  ```

  Demo 模式可以生成 `ActionExecutionResult(status="not_executed_demo")`，但不能把 draft creation 叫 execution。

- **可直接粘贴文本**

  > Demo 模式的终点是 durable action draft，不执行外部副作用。`action_execution` 仅在配置了允许的 external adapter，且 action draft、审批绑定和幂等校验全部通过时运行。

#### C5. Run lifecycle、interrupt 与 `trace_close` 不一致

- **问题**

  `trace_close` 被设计成正常尾部节点，但 interrupt、API 取消、异常、进程退出都可能无法到达该节点。

- **位置/章节**

  - 7.3 严格节点图
  - 17. Observability / Replay

- **代码依据**

  当前 run 状态由 API 层在正常完成、interrupt 和异常路径分别更新：`src/api/routers/agent_runs.py`。

- **为什么重要**

  若把关闭 run 的责任仅放在 graph 尾部节点，interrupted/error/cancelled run 会缺失终态和审计事件。

- **建议修改**

  定义统一 Run State Machine：

  ```text
  pending -> running -> interrupted -> running -> completed
                       -> expired/cancelled
          -> error/cancelled
  ```

  `trace_close` 应改为生命周期 service/finalizer，不应仅依赖正常 graph edge。

### Major

#### M1. “当前事实”对 state 隔离保证表述过强

当前 `AgentState` 用注释区分 persistent/ephemeral，但实际隔离依赖节点主动 reset。

建议把“AgentState 区分”改成“AgentState 通过字段约定和 `receive_request` reset 部分区分，目前没有 schema-level enforcement”。

#### M2. 当前审批过期能力不等于 SLA engine

当前只在审批决策到达时标记 expired，并在 pending list 中过滤过期项。没有主动扫描、提醒或升级。

spec 当前部分实现描述应明确这一点。

#### M3. 18 个节点并非都值得成为 LangGraph 节点

建议调整：

- `normalize_input`：若没有独立失败、路由或 checkpoint 需求，作为 helper 即可。
- `session_memory_load`：可并入 `receive_request` 或 `memory_context_load`。
- `long_term_memory_retrieve` 与 `case_memory_retrieve`：MVP 可合并为一个 `memory_context_retrieve`，由 service 返回分类型结果。
- `trace_close`：应优先是 run lifecycle finalizer。
- `action_draft` 与 `action_execution`：保留独立，但 demo graph 应跳过 execution。

MVP 可先控制在约 12–14 个节点。

#### M4. `clarification_gate` 命名和行为不一致

它实际生成澄清回复，不是单纯 gate。建议改为 `build_clarification_response`，router 负责决定是否进入。

同时必须定义下一 turn 如何关联 `clarification_request_id`、缺失 slots 和原任务。

#### M5. Intent taxonomy 存在重叠，没有优先级

重叠示例：

- `compensation_suggestion` 与 `action_request`
- `approval_review` 与 API approval workflow
- `appeal_or_unban` 与 `action_request`
- `complaint_escalation` 与 `ticket_reply_draft`

需要定义 taxonomy precedence、multi-intent 策略、required-slot map 和 deterministic pre-routing。

#### M6. Confidence threshold 没有校准依据

`0.65/0.80` 是固定值，但未定义：

- 模型 confidence 是否可校准。
- 每类 intent 是否使用不同阈值。
- action-related intent 是否使用更高阈值。
- eval 如何选择阈值。

建议通过 golden set 和风险加权 confusion matrix 校准。

#### M7. Tool contract 不足以支撑企业级调用

缺失建议字段：

- `tool_call_id`
- `merchant_scope`
- `permissions/scopes`
- `deadline_at`
- `attempt`
- `schema_version`
- `request_id`
- `policy_snapshot_ref`
- `data_freshness_at`
- `source_system`
- `partial_success`
- `retry_after_ms`

`status` 还应区分 `timeout`、`unavailable`、`conflict`、`invalid_response`。

#### M8. KnowledgeService contract 太粗

`search(query, context, filters)` 没有定义：

- context/filter schema。
- policy effective-time filtering。
- tenant/global policy 优先级。
- query rewrite 的输入来源。
- rerank/threshold 配置版本。
- partial evidence 如何影响回答。
- evidence 与 claim 的绑定。

当前 citation validator 只验证引用 chunk 是否出现在检索结果中，不验证引用是否支持具体 claim。

#### M9. Memory policy 缺少隐私与删除生命周期

还需明确：

- PII 分类和禁止写入字段。
- 用户更正、删除、遗忘权。
- stale memory 检测。
- memory supersede/version。
- 同 merchant 不同用户的可见性。
- delayed extraction 的触发和失败策略。
- long-term memory review 责任人。

`global` scope 对当前阶段风险过高，建议 MVP 不支持。

#### M10. Approval 数据模型不足以支持多级审批

给 `ApprovalRequest` 增加 `approval_level` 等字段无法表达：

- 多级顺序。
- 每级多个审批人。
- `any_one`/`all`。
- 重试与升级。
- 每级 SLA。
- 并发决策。

建议至少拆分：

- `approval_requests`
- `approval_levels`
- `approval_assignments`
- `approval_decisions`
- `approval_events`

#### M11. Action 幂等 contract 不处理“不确定执行结果”

仅定义 payload hash 不够。外部系统 timeout 后可能已经执行成功。

需定义：

- dispatch attempt。
- `unknown`/`reconciling` 状态。
- external idempotency support。
- reconciliation query。
- outbox/transaction boundary。
- compensation 状态机。

#### M12. Observability 缺少统一事件 schema 与脱敏规则

当前列出了 spans、metrics、logs，但没有规定：

- 哪些事件必须持久化。
- 事件顺序和唯一 ID。
- schema version。
- redacted payload。
- prompt/output 是否保存。
- retention policy。
- metrics 计算公式。

#### M13. 数据模型建议缺少约束、索引和版本字段

新增表普遍缺少：

- 外键。
- `updated_at`。
- `schema_version`。
- 状态枚举或 check constraint。
- tenant 复合唯一约束。
- source run / audit ref。
- soft delete / retention。
- 常用查询复合索引。

应避免将核心可查询状态全部放进 JSONB。

#### M14. Phase 1–8 没有真正覆盖目标 graph 迁移

路线中没有独立 phase 负责：

- 从当前线性 10 节点 graph 迁移到目标条件路由。
- AgentState contract migration。
- 数据库 migration。
- run lifecycle/status migration。
- security context contract。
- replay event schema。

每个 phase 也缺少明确前置依赖、退出标准和回滚边界。

#### M15. 测试计划仍偏功能清单，不是可验收 contract

还应补充：

- 每个 node 的 input/output contract test。
- router totality test：所有合法状态必须返回合法 node。
- router determinism test。
- approval transition table test。
- edited action invalidates old approval test。
- replay event completeness/order test。
- state reset/property-based test。
- tenant/merchant scope negative tests。
- tool timeout/partial failure tests。

### Minor

1. `security_context` 在 7.2 和 9.2 图中出现，但不在严格 18 节点列表中，容易误读。
2. “V1/V2”同时表示能力图版本和目标演进版本，建议改成“Capability View / Workflow View / Node View”。
3. `approval_request`、`approval_review`、`approve`、`accept` 混用，需术语表。
4. `session_id` 与 `thread_id` 未解释差异，当前代码主要使用 `thread_id`。
5. `run_id` 与当前 `current_run_id` 命名不一致。
6. `ActionExecutor.create_draft` 命名不自然，draft 应由 `ActionDraftService` 或 executor 的 `prepare` 阶段处理。
7. `manual_review` 更像路由/处置结果，不应与退款、发券等 action type 完全同类。
8. Metrics 中应避免 tenant/user 等高基数字段成为 Prometheus labels。
9. “18 个目标节点”容易变成不必要的硬性目标，应强调节点数不是验收标准。
10. “Intent taxonomy 不宜过大，先 10 个以内”与当前列出的 11 个 intent 不一致。

## Missing Contracts

| Contract | 建议字段 |
| --- | --- |
| Node contract | `node_name`, `purpose`, `required_inputs`, `optional_inputs`, `outputs`, `state_writes`, `services_called`, `side_effects`, `error_outputs`, `retry_policy`, `timeout`, `next_routes` |
| Router decision contract | `router_name`, `reads`, `decision_enum`, `precedence`, `default_route`, `invalid_state_behavior`, `totality_requirement` |
| State lifecycle contract | `field`, `typed_schema`, `scope`, `trusted_source`, `writer`, `readers`, `reset_rule`, `merge_rule`, `persisted`, `redaction` |
| Run lifecycle contract | `status`, `allowed_from`, `trigger`, `terminal`, `completed_at_rule`, `resume_allowed`, `audit_event` |
| Intent result | `intent`, `confidence`, `secondary_intents`, `required_slots`, `risk_signals`, `routing_hints`, `classifier_version`, `reason_codes` |
| Required-slot policy | `intent`, `required_slots`, `optional_slots`, `inheritable_slots`, `freshness`, `clarification_template` |
| Service facade | `request_schema`, `response_schema`, `errors`, `timeout`, `idempotency`, `authorization`, `audit obligations` |
| Tool call context | `tenant_id`, `merchant_scope`, `user_id`, `role`, `permissions`, `run_id`, `trace_id`, `tool_call_id`, `caller_node`, `deadline_at`, `attempt` |
| Tool result | `status`, `data`, `summary`, `source_system`, `freshness_at`, `evidence_refs`, `error`, `retryable`, `latency_ms`, `audit_ref` |
| Evidence contract | `evidence_id`, `tenant_id`, `doc_key`, `chunk_id`, `policy_version`, `effective_from/to`, `text_hash`, `score`, `retrieved_at`, `retrieval_config_version` |
| Citation validation result | `claim_id`, `evidence_ids`, `membership_valid`, `support_valid`, `validation_reason`, `validator_version` |
| Memory record | `memory_id`, `scope`, `type`, `content`, `source_ref`, `confidence`, `valid_from`, `expires_at`, `review_status`, `supersedes`, `audit_ref` |
| Memory write decision | `candidate`, `decision`, `reason_code`, `pii_classification`, `review_required`, `written_memory_id` |
| Approval state machine | `request_status`, `level_status`, `decision_type`, `revision`, `action_payload_hash`, `policy_version`, `version`, `sla_due_at` |
| Action draft | `draft_id`, `action_type`, `payload`, `payload_hash`, `policy_snapshot_ref`, `approval_refs`, `created_by`, `expires_at`, `status` |
| Action execution result | `execution_id`, `draft_id`, `status`, `attempt`, `external_ref`, `idempotency_key`, `started_at`, `completed_at`, `error`, `reconciliation_status` |
| Trace event | `event_id`, `sequence`, `schema_version`, `event_type`, `occurred_at`, `run_id`, `trace_id`, `node`, `actor`, `resource_refs`, `redacted_payload` |

## Suggested Spec Additions

### 1. Terminology and Identifier Semantics

- **位置**：第 2 节后。
- **原因**：统一 `run_id/thread_id/session_id/trace_id`、draft/execution、accept/approve。
- **内容**：术语、唯一性范围、可信来源、生命周期。

### 2. Current-vs-Target Evidence Table

- **位置**：第 4 节末尾。
- **原因**：避免把部分实现描述成已完成保障。
- **内容**：能力、状态、代码依据、限制、目标差距。

### 3. Node and Router Contract Tables

- **位置**：第 9 节。
- **原因**：使 graph 可直接实现和测试。
- **内容**：18 个节点逐项 I/O、side effect、error、retry、routes。

### 4. AgentState Lifecycle Matrix

- **位置**：第 10 节。
- **原因**：防止跨 turn 状态污染。
- **内容**：scope、writer、reset、merge、trusted source、persistence。

### 5. Intent Routing Decision Table

- **位置**：第 11 节。
- **原因**：解决 taxonomy 重叠。
- **内容**：precedence、required slots、deterministic rules、confidence threshold、golden cases。

### 6. Approval State Machine

- **位置**：第 15 节。
- **原因**：高风险安全核心。
- **内容**：状态图、transition table、并发/version、edit revision、SLA。

### 7. Action Safety and Execution Modes

- **位置**：第 16 节。
- **原因**：区分 demo draft 和真实执行。
- **内容**：action allowlist、demo/external mode、idempotency、unknown result、compensation。

### 8. Run Lifecycle and Trace Event Schema

- **位置**：第 17 节。
- **原因**：保证 interrupt/error/replay 完整。
- **内容**：run 状态机、必持久化事件、顺序、redaction、retention。

### 9. Phase Dependency and Acceptance Matrix

- **位置**：第 19 节。
- **原因**：使迁移路线可执行。
- **内容**：phase 输入、依赖、输出、验收、回滚点、禁止事项。

## Ambiguity Checklist

后续工程师会问：

- `session_id` 和 `thread_id` 有什么区别？
- graph state 中的 tenant/user/role 是否可作为授权依据？
- 新 turn 开始时，哪些字段必须清空？
- session slot 可以跨哪些 intent 复用？多久过期？
- `required_slots` 由分类器决定，还是 deterministic policy 决定？
- 多 intent 请求选一个主 intent，还是拆成多个任务？
- confidence 是模型自报值还是校准后的值？
- `clarification_gate` 后原 run 结束还是保持 pending？
- 用户补充信息后，是新 run 还是 resume 原 run？
- partial evidence 是否允许生成建议或动作？
- citation validation 只验证 chunk membership，还是验证 claim support？
- tool timeout 后 graph 应重试、澄清还是转人工？
- `respond` 后审批记录保持 pending 还是创建 revision？
- `ignore` 是 pending、cancelled 还是终态？
- edit 可以修改哪些字段？
- edit 后旧审批是否立即失效？
- 多级审批是顺序执行还是并行？
- 同级审批采用 `any_one` 时，其他 pending assignment 如何关闭？
- SLA escalation 后原审批人还能否决策？
- action draft 是否会过期？
- demo 模式是否创建 action execution 记录？
- 外部执行 timeout 后如何判断是否实际成功？
- compensation 是自动执行还是只生成建议？
- `trace_close` 如何覆盖 interrupt 和进程崩溃？
- replay 是否包含 prompt/model/policy/tool schema version？
- 哪些 trace payload 必须脱敏？
- memory 中错误事实如何更正和删除？
- case memory 何时写入，谁确认 outcome？
- Phase 何时真正迁移到目标条件路由 graph？

## Implementation Readiness Score

| 维度 | 分数 | 判断 |
| --- | ---: | --- |
| 架构边界清晰度 | 7.5/10 | 分层方向清楚，service contracts 不够细 |
| LangGraph workflow 可实现性 | 5.0/10 | 存在顺序矛盾、死路和生命周期缺口 |
| State/schema 明确度 | 4.0/10 | 大量 Any，缺生命周期和字段所有权 |
| Tool/action 安全性 | 6.0/10 | 原则正确，执行 contract 不完整 |
| Memory 安全性 | 5.5/10 | 分类合理，隐私/更正/过期策略不足 |
| Approval/SLA 完整度 | 4.0/10 | 尚未形成可实现状态机 |
| Observability/replay 可实施性 | 5.5/10 | 目标明确，事件与 run contract 缺失 |
| 测试/eval 完整度 | 6.0/10 | 覆盖方向较好，缺 contract/transition tests |
| 迁移路线可执行性 | 5.0/10 | 渐进方向合理，但遗漏 graph/state/data migration |
| **总分** | **5.4/10** | **适合作为目标架构草稿，尚不适合作为主要实现 spec** |

## Recommended Patch Plan

### 1. 先修正事实边界和核心语义

修改第 4、7、9、15、16、17 节。

目标：

- 收紧当前实现事实描述。
- 修复 session memory/slot 顺序。
- 区分 demo draft 与真实 execution。
- 定义 run 和 approval 状态机。

验收标准：

- 每条“当前已实现”都有代码依据和限制说明。
- 所有 graph 路径都有明确终点或 resume 语义。
- Approval 所有状态只有唯一、确定含义。

### 2. 补齐核心 contract 表

补充：

- Node contract 表。
- Router contract 表。
- State lifecycle matrix。
- Tool/Knowledge/Memory/Approval/Action/Trace contract。
- Run lifecycle transition table。

验收标准：

- 工程师不需要自行发明字段、错误状态或状态转换。
- 每个 router 对所有合法输入都有确定输出。
- 每个 state 字段都有 writer、scope、reset 和 persistence 定义。

### 3. 重写迁移路线和数据模型建议

将 Phase 细分为：

1. Contract baseline。
2. Knowledge facade。
3. Business tool facade。
4. State lifecycle 与 routing migration。
5. Intent/clarification。
6. Session memory。
7. Approval state machine。
8. Demo action executor boundary。
9. Replay event contract。
10. Long-term/case memory 与外部 action 作为后续 milestone。

验收标准：

- 每个 phase 有前置依赖、输出、测试、退出条件和回滚点。
- MVP 不依赖 long-term memory、多级 SLA 或真实外部执行才能完成。

### 4. 最后补示例和 golden cases

补充：

- 典型 intent routing 示例。
- missing slot 跨 turn 示例。
- no-evidence 示例。
- approval accept/edit/respond/expired 示例。
- demo draft 示例。
- external execution unknown-result 示例。
- replay timeline 示例。

验收标准：

- 每条核心安全规则至少有一个正例和一个反例。
- 示例 payload 全部符合前述 contract。
- 示例流程与严格节点图完全一致。

---

本审阅基于 `docs/agent-architecture-spec.md` 及当前仓库实现证据。审阅过程中未修改代码或原始 spec，未运行测试。
