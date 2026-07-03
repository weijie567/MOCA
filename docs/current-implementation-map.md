# 当前仓库实现地图

> 生成日期：2026-06-17
>
> 本文基于当前仓库静态审阅整理，用于对齐 MOCA 的记忆、状态、日志、审计与业务状态实现边界。本文只描述当前实现，不代表目标架构。

## 总体判断

当前 MOCA 更接近业务型 Agent，而不是通用个人助手。仓库里已经有较完整的业务流程状态、审批、安全快照、动作草稿、policy KB、redacted replay trace、窄版 session memory，以及 prompt-safe conversation context；但尚未实现可完整重建 raw prompt / raw tool payload 的原始 transcript 存储。

当前实现可以粗略分为：

- **Working memory**：主要是 `AgentState` + LangGraph checkpoint + 节点间传递的 runtime fields。
- **Short-term memory**：主要是 `session_memories` 表与 `MemoryService`，用于同 thread 的 slot / intent / unresolved questions 延续。
- **Conversation context log**：已实现 thread/message/tool/summary 的 prompt-safe 投影；raw prompt、raw tool payload 与完整 run transcript reconstruction 仍缺失。
- **Trace / replay / audit**：已有 `agent_runs`、`agent_steps`、`agent_trace_events`、approval/action events，但这些是 redacted trace，不保存 raw prompt / raw tool output。
- **Business state**：orders、refund cases、tickets、policy docs/chunks、approval requests、safety snapshots、action drafts 是业务事实或业务动作状态。

## 实现地图

| 模块 | 当前文件路径 | 当前作用 | 分类 | 判断 |
|---|---|---|---|---|
| API 应用入口 | `src/api/main.py:29` | FastAPI lifespan 中创建 `AsyncPostgresSaver`，通过 `build_graph(checkpointer)` 构建 Agent graph；middleware 写入 `trace_id` / `run_id` | runtime / trace | checkpoint 已接入 Postgres；不是 conversation log |
| Chat endpoint | `src/api/routers/agent.py:31` | `/api/v1/agent/chat` 接收 `query/thread_id`，构造 `input_state`，调用 graph，写 `AgentRun/AgentStep`，触发后台 memory write | run trace / runtime | 只保存本轮 query 和 final response；不是完整消息日志 |
| SSE run endpoint | `src/api/routers/agent_runs.py:83` | 创建 pending run，SSE 流式执行 graph，发送节点事件、完成事件和 interrupt 事件 | run trace / UI stream | 可支持前端运行态展示；不是 raw conversation log |
| Agent request schema | `src/api/schemas/agent.py:8` | `ChatRequest` 仅包含 `query` 和 `thread_id` | conversation input | 没有 message id、role、attachments、tool message 等 conversation log schema |
| Graph 编排 | `src/agent/graph.py:118` | 定义 `receive_request -> classify -> session_memory_load -> extract -> retrieve/investigate -> recommendation -> approval/action/final` 流程 | working memory runtime | 当前 Agent 运行依赖 `AgentState` 在各节点间传递 |
| AgentState | `src/agent/state.py:48` | 统一 TypedDict，包含 identity、slots、intent、business context、policy evidence、recommendation、risk、approval、trace 等字段 | working memory 混合体 | 是当前最核心的 working memory，但混入 business state copy、trace/debug、approval/action runtime copy |
| 每轮状态重置 | `src/agent/nodes/receive_request.py:13` | 每轮开始重置 per-turn fields；保留 trusted identity，不直接依赖旧 ephemeral state | working memory 生命周期 | 说明当前 working memory 是 run/turn 工作副本，不是长期事实源 |
| Intent 分类 | `src/agent/nodes/classify_intent.py:143` | prompt 主要由 system + 当前 user query 组成；写入 intent 相关状态和 `llm_outputs.intent_classification.raw` | working memory / LLM output trace | 不使用 conversation history；`llm_outputs` 更像 debug/trace，不应算 memory |
| Slot 抽取 | `src/agent/nodes/extract_slots.py:60` | prompt 主要由当前 user query 和 classifier hints 组成 | working memory | 与历史上下文的衔接主要依赖后续 session memory / active slots，不是 recent messages |
| Session memory load | `src/agent/nodes/session_memory_load.py:18` | 通过 `MemoryService.load_session_memory` 加载同 thread session memory | short-term memory | 当前已有的短期记忆入口 |
| Memory write | `src/agent/nodes/memory_write.py:35` | 后台写入 session memory；跳过 approval/interrupted/high-risk；候选内容包括 explicit slots、unresolved questions、last intent、机械 summary | short-term memory 派生数据 | 明确不写 raw message、raw tool result、approval/action/evidence |
| Session memory schema | `src/memory/schemas.py:10` | `SessionSlotV1`、`SessionMemoryView`、`SessionMemoryWriteCandidate` 等 | short-term memory schema | 结构偏 slot continuity，不是 general assistant rolling summary |
| Session memory repository | `src/memory/repository.py:17` | 读写 `session_memories`，支持 active record、search、CAS update、soft delete | short-term memory persistence | Postgres 是当前 session memory 权威存储 |
| Session memory service | `src/memory/service.py:29` | TTL、intent compatibility、slot merge、CAS 冲突处理、summary cap | short-term memory logic | 没有 LLM rolling summary；summary 是轻量字符串 |
| Session precedent search | `src/memory/search.py:15` | `LegacySessionPrecedentSearchService` 基于 `session_memories` 做 legacy/debug-only read-only projection | legacy short-term projection | 不是 planner-facing case memory；不得支撑生产 `search_case_memory` |
| Case memory tool | `src/tools/executors/memory.py:32` | `search_case_memory` 由 `MemoryToolExecutor -> CaseMemoryService.retrieve_reviewed(...)` 服务，返回 reviewed case memory `ToolResultV2` | tool / reviewed case memory | planner-facing 工具使用 reviewed case memory；`case_memories` 是 reviewed closed-case precedent，不使用 active CWC 或 legacy session-derived precedent |
| Closed-case precedent generation | `src/memory/case_precedent.py:47` | `ClosedCasePrecedentService -> CaseMemoryService.submit_case_memory_candidate(...)` 将 finalized CWC 投影为 `closed_case_cwc_candidate`，进入现有 case-memory review flow | memory / case precedent candidate | 只提供 trusted internal seam；生成项默认 `needs_review`，source case identity 在 `source_ref_json`，retrieval scope 在 `CaseMemory.scope_type/scope_id` |
| Long-term memory retrieve | `src/agent/nodes/long_term_memory_retrieve.py:14` | 返回空 `long_term_memory` 和 `case_memory` | long-term memory placeholder | 长期记忆实际未实现 |
| Investigation node | `src/agent/nodes/investigate.py:141` | 调用业务工具和 policy retrieval，聚合 `business_context`、`policy_evidence`、`tool_results`、refs | working memory / business context | 当前 tool results 进入 AgentState；需要区分 raw result、normalized result、summary |
| Recommendation node | `src/agent/nodes/generate_recommendation.py:154` | 重新校验 policy evidence 内容，组装 prompt 生成 recommendation | prompt context assembly 局部实现 | 仍有节点内局部摘要和裁剪；统一 `ContextAssembler` 已存在但 adoption 取决于各 agent path |
| Risk / approval assessment | `src/agent/nodes/assess_risk_and_approval.py:434` | 以 recommendation 和 business context 生成风险判断；必要时创建 approval request | working memory / business state transition | 业务关键节点；prompt context 仍是节点内散装生成 |
| Final response | `src/agent/nodes/final_response.py:184` | 根据 state、business context、approval/action outcome 生成最终响应 | assistant final response | final response 会写入 `AgentRun`，但没有独立 message row |
| Tool contract | `src/tools/contracts.py:71`, `src/tools/contracts.py:111` | `ToolResultV2` 是 prompt-safe result envelope；`ToolResultStorageV1` / `tool_results` 持有 normalized result、prompt summary、`raw_result_ref` / `raw_result_hash` | tool result projection / storage contract | raw result ref/hash 已有 schema 与落库路径；raw payload 对象存储、访问策略和生命周期仍未确认 |
| Tool manager | `src/tools/manager.py:73` | 工具权限、schema、approval、安全、幂等控制 | business tool runtime | 是业务 Agent 核心能力，不是 memory |
| Tool catalog | `src/tools/catalog.py:14` | 定义工具描述、风险级别、planner visibility、approval requirement | business tool policy | 可作为 tool call 审计和 ContextAssembler 的元数据来源 |
| Business adapters | `src/business/adapters.py:175` | 从业务 integration 读取 raw response 后投影为受控 `_OrderData/_RefundCaseData/_TicketData` | business state projection | 已避免上游 raw response 直接进入 Agent，但 raw result 未独立保存 |
| Business service | `src/business/service.py:121` | 业务工具 facade、重试、上下文聚合 | business state access | 业务事实应来自这里或业务 DB，不应来自 memory |
| Policy executor | `src/tools/executors/knowledge.py:32` | `search_policy` 调用 knowledge service，返回 policy evidence refs 和摘要 | policy KB / RAG | policy 是 versioned knowledge，不是 memory |
| Policy DB models | `src/db/models.py:160` | `PolicyDocument`、`PolicyChunk`，包含 pgvector embedding | versioned knowledge | pgvector 当前服务 policy retrieval，不是用户长期记忆 |
| Business DB models | `src/db/models.py:28` | `Tenant/User/Order/RefundCase/Ticket` | business state | 这些是业务事实源；`Ticket.messages` 是业务工单消息，不是 Agent conversation log |
| AgentRun model | `src/db/models.py:220` | `agent_runs` 保存 run id、tenant/user/thread、input query、final response、status 等 | run trace / final response | 不是 threads/messages；无法完整还原多 role conversation |
| AgentStep model | `src/db/models.py:611` | `agent_steps` 保存 node、summary、tool name、tool output summary、evidence refs、tokens/latency | step trace | 保存摘要，不保存 raw prompt / raw LLM output / raw tool output |
| AgentTraceEvent model | `src/db/models.py:645` | `agent_trace_events` append-only replay event envelope，包含 redacted payload、resource refs、retention | replay trace / audit-adjacent | redacted trace，不是 raw log |
| Replay service | `src/replay/service.py:49` | 校验 replay event、分配 sequence、写入 `agent_trace_events` | replay trace | 支持安全 replay timeline；禁止 raw payload 类字段 |
| Replay validators | `src/replay/validators.py:56` | 禁止 `raw_prompt/raw_args/raw_tool_output/secret/pii` 等进入 redacted payload | replay safety | 进一步证明 trace 不能替代 raw conversation/tool log |
| Trace writer | `src/agent/trace.py:16` | 写 `AgentRun`、`AgentStep`，并追加 lifecycle status event | trace persistence | 适合运行态追踪，不是完整 conversation persistence |
| Trace API | `src/api/routers/traces.py:22` | 提供 run trace、replay 查询 | trace/replay read API | 可回放高层事件，不能重建完整 prompt 或 tool raw result |
| Trace repository | `src/repositories/trace_repo.py:26` | 聚合 `AgentRun/AgentStep/ApprovalRequest/ApprovalStep/ActionDraft` 为 timeline | trace/audit view | 是安全投影视图，不是 raw log |
| Approval models | `src/db/models.py:310` | `ApprovalRequest`、approval levels、assignments、decisions、events、steps | business state / audit | 审批是业务状态与合规事件，不应归入 memory |
| Approval service | `src/approvals/service.py:77` | 创建 approval request，绑定 snapshot/hash，执行 decision | business state / audit | 是业务流程权威状态 |
| Approval events | `src/approvals/events.py:23` | 发出 approval requested/decided/expired/resumed 等 redacted event | audit / replay | 不保存 raw prompt/tool payload |
| Safety snapshot | `src/approvals/snapshot_service.py:54` | 持久化 immutable action safety snapshot 和 payload hash | business state / audit | 是审批依据，不是 memory |
| Action draft | `src/actions/service.py:51` | 创建 coupon grant draft，校验 approval/snapshot/hash | business action state | 业务动作权威记录，不是 memory |
| AuditLog model | `src/db/models.py:199` | `audit_logs` 表，字段包括 action、resource、metadata | audit | 表存在，但当前未看到它作为 tool manager 主审计链路稳定接入 |
| Audit repository | `src/repositories/audit_repo.py:14` | `record_tool_call` 写 `AuditLog` | audit | 当前使用范围有限，需要和 replay/action/approval 职责重新对齐 |
| Redis 配置 | `src/config.py:14`, `docker-compose.yml:18` | 配置 Redis URL 与服务 | cache candidate | 当前仓库中没有找到实际 Redis client 使用依据 |
| Conversation threads/messages | `src/db/models.py:1212`, `src/db/models.py:1305`, `src/conversation/*` | 保存 thread-scoped user / assistant / tool messages 与 prompt context metadata | conversation log projection | 已实现 redacted / prompt-safe conversation context；不是 raw prompt 或完整 raw transcript |
| Tool calls/results tables | `src/db/models.py:1357`, `src/db/models.py:1401`, `src/conversation/repository.py:436` | 保存 tool call summaries、normalized result JSON、prompt summaries、raw result refs / hashes | tool log projection | 已实现 prompt-safe tool context 与 raw result 引用字段；仍不保存 raw payload 本体 |
| Thread summaries | `src/db/models.py:1448`, `src/conversation/repository.py:398` | 保存 rolling thread summaries、source message ids、source tool result ids | short-term conversation context | 已实现 thread_rolling summary；`session_memories` 仍只承担 slot continuity |
| ContextAssembler | `src/agent/context/assembler.py:28` | 统一组装 system、working state、summary、recent messages、policy refs、tool summaries、memory context 并应用预算 | prompt context assembly | 已实现；剩余差异是各 agent path 的接入范围 |

## 当前边界梳理

### Working memory

当前 working memory 主要由 `AgentState` 承担，并通过 LangGraph checkpoint 具备恢复能力。它包含：

- 当前用户输入和归一化查询。
- intent、slot、routing hints。
- `session_memory` 加载结果。
- business context、policy evidence、tool results。
- recommendation、risk assessment、approval/action runtime copy。
- trace/debug 字段。

问题是它目前是一个“大状态包”，没有明确区分：

- 当前运行需要的轻量 working state。
- 权威 business state 的 runtime copy。
- prompt context 投影。
- trace/debug 输出。
- tool raw / normalized / summary 的不同层级。

### Short-term memory

当前 short-term memory 是窄版 session memory：

- 表：`session_memories`。
- 服务：`MemoryService`。
- 用途：同 thread slot 延续、last intent、unresolved questions、轻量 session summary。
- 存储：Postgres，带 CAS/version/TTL/soft delete。

它不是：

- recent messages。
- rolling conversation summary。
- case summary。
- 长期用户记忆。

### Conversation context log

当前已有 prompt-safe conversation context log，可覆盖部分上下文需求：

- `agent_runs.input_query`：保存本轮用户输入。
- `agent_runs.final_response`：保存本轮最终回复。
- `conversation_threads` / `conversation_messages`：保存 thread、role、content、prompt context metadata。
- `tool_calls` / `tool_results`：保存工具摘要、normalized result JSON、prompt summary、raw result ref/hash。
- `summaries`：保存 `thread_rolling` summary 与来源 message / tool result ids。
- `ContextAssembler`：把 summary、recent messages、tool summaries、policy refs 与 memory context 组装成 prompt-safe context。
- `agent_steps`：保存节点摘要和工具摘要。
- `agent_trace_events`：保存 redacted replay events。

当前仍无法仅凭这些 prompt-safe 投影完整回答：

- 本轮完整 prompt 是什么。
- 工具完整 raw 入参和 raw result payload 是什么。
- assistant intermediate message 是什么。
- 是否能从 raw prompt / raw payload 级别完整重建一次 Agent run。

### Trace / audit

当前 trace/replay 体系相对成熟，但它是 redacted projection：

- `agent_trace_events` 用于安全 replay。
- `agent_steps` 用于节点级 timeline。
- approval/action 事件用于业务状态变化追踪。
- `audit_logs` 表存在，但与主执行链路的边界尚不清晰。

这些都不应被当作 raw conversation log。

### Business state

当前业务事实源包括：

- `orders`
- `refund_cases`
- `tickets`
- `policy_documents`
- `policy_chunks`
- `approval_requests`
- `action_safety_snapshots`
- `action_drafts`

这些表和对应 service 是业务权威状态；memory 只能引用或摘要它们，不能替代它们。

## 关键缺口

1. **缺少 raw prompt / raw payload transcript**：已有 `conversation_threads` / `conversation_messages` / `tool_calls` / `tool_results` prompt-safe 投影，但不能恢复完整 raw prompt、raw tool args 或 raw tool output。
2. **raw result ref/hash 的后端契约仍需落地**：`tool_results.raw_result_ref` / `raw_result_hash` 字段已存在，但 raw payload 对象存储、访问策略和生命周期不是本文确认的已实现事实。
3. **ContextAssembler adoption 仍不完整**：`ContextAssembler` 已实现，仍需逐条 agent path 确认是否统一使用预算、redaction 和 raw/summary 分层。
4. **thread summary 与 session memory 边界需继续保持清晰**：`summaries.thread_rolling` 已实现；`session_memories.session_summary` 仍是 slot continuity 的轻量摘要，不替代 rolling conversation summary。
5. **`search_case_memory` 命名历史上容易误导**：当前 planner-facing 实现已由 `MemoryToolExecutor -> CaseMemoryService.retrieve_reviewed(...)` 服务 reviewed case memory；`case_memories` 是 reviewed closed-case precedent，不是 active CWC；`ClosedCasePrecedentService -> CaseMemoryService.submit_case_memory_candidate(...)` 只生成 `closed_case_cwc_candidate` review candidate；`LegacySessionPrecedentSearchService` 仅是 legacy/debug-only 的 session-derived projection，不是真正 case memory，也不得作为生产工具后端。
6. **`AgentState` 边界偏宽**：working memory、business runtime copy、trace/debug、approval/action copy 混在同一个 TypedDict。
7. **audit/log 体系职责需对齐**：`agent_trace_events`、`agent_steps`、`audit_logs`、approval/action events 的权责边界需要明确。

## 推荐后续整理方向

MVP 阶段优先补齐或收敛：

- raw prompt / raw tool payload 的对象存储、访问控制与 retention 策略。
- `tool_results.raw_result_ref` / `raw_result_hash` 与对象存储的端到端契约。
- 各 agent path 对 `ContextAssembler` 的统一接入。
- prompt-safe conversation context 与 raw reconstruction 边界的测试覆盖。

同时保留当前已有体系：

- `AgentState` 继续作为 runtime working copy。
- `session_memories` 继续作为同 thread slot continuity。
- policy KB 继续作为 versioned knowledge source。
- approval/action/safety snapshot 继续作为业务状态和审计依据。
- `agent_trace_events` 继续作为 redacted replay timeline。
