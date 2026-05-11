# Phase 3: LangGraph Core - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

用户提交退款/订单问题 → Agent 通过 LangGraph 状态机编排只读 happy path：意图识别、槽位抽取、工具调用加载业务上下文、检索知识库证据、生成结构化处理建议、风险标记、最终响应。包含完整执行 trace 持久化和同线程多轮记忆。不涉及审批中断、写操作工具或 SSE 流式响应。

</domain>

<decisions>
## Implementation Decisions

### D-01: LLM 模型选择
- **D-01a:** 主模型：GLM-5.1（智谱/BigModel），通过 DashScope 兼容接口调用
- **D-01b:** API endpoint：复用 DashScope OpenAI-compatible endpoint
- **D-01c:** API key：复用 `DASHSCOPE_API_KEY`
- **D-01d:** 不使用 OpenAI GPT-4o、DeepSeek 或 Qwen 作为主模型

### D-02: 工具调用方式
- **D-02a:** 图路由确定性调用：节点硬编码调用顺序，不依赖 LLM 自主 function calling
- **D-02b:** 每个节点只调用预定义的工具集，不由 LLM 动态选择
- **D-02c:** 优势：确定性强、可测试、可追踪、可评估

### D-03: Prompt 语言策略
- **D-03a:** System prompt 和工具描述使用英文
- **D-03b:** 模型输出使用中文（面向中文用户）
- **D-03c:** 业务数据（订单、退款、知识库）为中文

### D-04: 图节点设计（8 节点细粒度）
- **D-04a:** `receive_request` — 接收用户输入，初始化 trace_id、thread_id、user_id、tenant_id、role
- **D-04b:** `classify_intent` — 识别意图：policy_qa、refund_troubleshooting、compensation_suggestion、approval_request、unknown
- **D-04c:** `extract_slots` — 抽取 order_id、refund_case_id、ticket_id、merchant_id、金额、问题类型等槽位
- **D-04d:** `load_business_context` — 根据 slots 调用只读工具加载订单、退款单、工单
- **D-04e:** `retrieve_policy_evidence` — 根据 intent + business_context 检索规则证据
- **D-04f:** `generate_recommendation` — 生成结构化处理建议（recommended_action、reasoning_summary、evidence_refs、confidence）
- **D-04g:** `assess_risk_and_approval` — 标记风险等级（low/medium/high），Phase 3 不触发 interrupt
- **D-04h:** `final_response` — 将结构化建议转为用户可读回复，引用证据，说明限制
- **D-04i:** 核心原则：每个节点只做一类事情，结构化 I/O，可独立测试

### D-05: Execution Trace
- **D-05a:** 完整 trace 写入 DB：agent_runs（run 级）+ agent_steps（节点级）
- **D-05b:** agent_runs 字段：run_id, thread_id, tenant_id, user_id, input_query, final_status, final_response, started_at, completed_at, total_latency_ms, total_tokens, total_cost, error_summary
- **D-05c:** agent_steps 字段：step_id, run_id, node_name, step_index, status, input_summary, output_summary, tool_name, tool_input_summary, tool_output_summary, model_name, prompt_tokens, completion_tokens, latency_ms, evidence_refs, error_message, started_at, completed_at
- **D-05d:** API response 返回简化 trace_summary：run_id, intent, nodes_executed, tools_called, evidence_count, risk_level, total_latency_ms, final_status
- **D-05e:** 不暴露完整 prompt、完整 tool output、内部错误堆栈、用户隐私字段
- **D-05f:** Phase 3 不追求完整 observability（OTel/Prometheus/Grafana 留后续）

### D-06: Checkpointer
- **D-06a:** 使用 LangGraph PostgresSaver，复用已有 PostgreSQL 实例
- **D-06b:** 支持同线程多轮对话状态持久化
- **D-06c:** 服务重启不丢失线程状态

### D-07: AgentState 分层设计
- **D-07a:** persistent_memory（进 checkpointer，跨轮保留）：
  - thread_id, tenant_id, user_id
  - active_slots（order_id, refund_case_id, ticket_id, merchant_id, customer_id, issue_type）
  - last_intent
  - last_recommendation_summary（recommended_action, reasoning_summary, confidence, risk_level, approval_required, created_at）
  - evidence_refs（doc_key, chunk_id, title, confidence, retrieved_at）
  - last_business_context_refs（order_id, refund_case_id, ticket_id, loaded_at）
- **D-07b:** ephemeral_context（本轮临时，下轮清空/重建）：
  - user_query, normalized_query, current_intent, extracted_slots
  - business_context, retrieved_evidence, recommendation_draft
  - risk_assessment, final_response, tool_results, llm_outputs
  - node_errors, retry_count, current_run_id, trace_steps
- **D-07c:** 不保留完整订单/退款/工单详情、完整 policy chunk 原文、完整 prompt/tool output
- **D-07d:** 每轮需要时通过工具重新加载最新业务数据，通过 RAG 重新检索最新规则

### D-08: Tool Contract 与权限
- **D-08a:** Phase 3 所有工具只读：get_order, get_refund_case, get_ticket, search_policy
- **D-08b:** 写操作工具（create_coupon_grant_draft, create_approval_request）留给 Phase 4
- **D-08c:** 所有工具必须带 tenant_id / user_id / role 进行权限校验
- **D-08d:** 工具返回统一格式：`{"status": "success"|"error", "data": {}, "error": {"error_code", "message", "retryable", "should_stop"}}`
- **D-08e:** 业务可预期错误（ORDER_NOT_FOUND, PERMISSION_DENIED）返回结构化错误，不抛异常
- **D-08f:** 系统级异常（DB_TIMEOUT, CONNECTION_ERROR）在 tool wrapper 层捕获并转换为结构化错误

### D-09: RAG Evidence 与 Agent 决策
- **D-09a:** 业务判断、政策解释、处理建议必须引用至少一个 doc_key/chunk_id
- **D-09b:** 无 evidence_refs 时不允许输出确定性业务结论
- **D-09c:** 不要求 evidence 的内容：问题复述、订单事实陈述、补充信息请求、流程说明
- **D-09d:** 证据充足时：结论 + 理由 + evidence_refs + confidence + risk_level
- **D-09e:** 证据不足时：不给确定性结论，输出已知事实 + 缺失信息 + 建议人工确认
- **D-09f:** 证据完全缺失时：拒绝生成业务判断，要求用户补充信息
- **D-09g:** final_response 硬约束：禁止无依据表达（"通常可以补偿""应该退款"等）

### D-10: 错误处理与降级
- **D-10a:** 可恢复错误（timeout, rate_limit, network_error, empty_response）retry 1 次
- **D-10b:** 结构化输出解析失败：retry 1 次并反馈 schema error 给模型
- **D-10c:** retry 后仍失败：返回结构化降级响应，不继续使用不合格结果
- **D-10d:** 不可恢复业务错误（NOT_FOUND, PERMISSION_DENIED, VALIDATION_ERROR）不 retry
- **D-10e:** 用户侧只看到安全、业务化的降级说明，不暴露内部错误细节
- **D-10f:** trace 必须记录所有失败和 retry（error_code, retry_count, fallback_action）
- **D-10g:** Phase 3 不引入指数退避、熔断器、任务队列、异步恢复

### D-11: 验收测试
- **D-11a:** CI 必须通过：单元测试每个节点 + 工具测试 + mock LLM 确定性测试 + 图级集成测试 + 失败路径测试
- **D-11b:** CI 不依赖真实 LLM API，使用 deterministic fake LLM / fake structured output
- **D-11c:** 图级集成测试断言：final_response 存在、intent 正确、tools 被调用、evidence_refs 存在、risk_level 存在、agent_runs/agent_steps 写入、checkpointer 保留 persistent_memory
- **D-11d:** 失败路径覆盖：order_not_found、policy_no_result、LLM parse failed、DB timeout → structured error、evidence insufficient → 不输出确定性结论
- **D-11e:** 可选 live smoke test（本地手动运行，不进 CI）：验证真实 LLM 链路可用

### Claude's Discretion
- LangGraph 具体 API 用法（StateGraph 构建方式、节点函数签名）
- PostgresSaver 的具体配置和 migration
- Tool wrapper 的具体实现模式
- Prompt 模板的具体措辞
- Mock LLM 的具体实现方式
- agent_runs/agent_steps 的具体 SQLAlchemy model 字段类型

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Data Model
- `.planning/ARCHITECTURE.md` — Design Contract, DB schema (agent_runs, agent_steps tables), directory structure
- `src/db/models.py` — Existing model definitions including AgentRun, AgentStep

### Requirements
- `.planning/REQUIREMENTS.md` — AGNT-01 to AGNT-06, AGNT-08, RAG-05, SAFE-06, SAFE-08, INFR-09

### Prior Phase Context
- `.planning/phases/01-foundation/01-CONTEXT.md` — DB schema, tenant_id scoping, error format, API language
- `.planning/phases/02-rag-pipeline/02-CONTEXT.md` — Retriever contract (D-09), confidence thresholds (D-05), citation validator (D-06), stable IDs (D-07)

### Existing Code
- `src/rag/retriever.py` — Retriever implementation (reuse for retrieve_policy_evidence node)
- `src/rag/citation_validator.py` — Citation validation logic
- `src/rag/schemas.py` — RAG schema definitions
- `src/repositories/order_repo.py` — Order repository (reuse for get_order tool)
- `src/repositories/refund_repo.py` — Refund repository (reuse for get_refund_case tool)
- `src/repositories/ticket_repo.py` — Ticket repository (reuse for get_ticket tool)
- `src/repositories/audit_repo.py` — Audit repository pattern
- `src/auth/permissions.py` — Permission/scope definitions
- `src/config.py` — Configuration pattern (DashScope settings)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/repositories/order_repo.py`, `refund_repo.py`, `ticket_repo.py`: 已有 repository 层，可直接包装为 Agent 工具
- `src/rag/retriever.py`: 已有检索器，返回结构化 evidence + score + retrieval_status
- `src/rag/citation_validator.py`: 已有 citation 校验逻辑
- `src/auth/permissions.py`: 已有权限 scope 定义，工具层可复用
- `src/config.py`: 已有 DashScope 配置模式，LLM client 配置可沿用

### Established Patterns
- SQLAlchemy 2.0 mapped_column + UUID PK + TimestampMixin
- Repository 层 tenant_id scoping via current_user dependency
- 统一错误格式：`{"success", "data", "error"}` + trace_id
- uv + ruff + pytest toolchain
- CI 使用 deterministic fake（不依赖外部 API）

### Integration Points
- `src/api/routers/` — 新增 agent router（POST /api/v1/agent/chat）
- `src/db/models.py` — 已有 AgentRun, AgentStep model 定义
- Docker Compose postgres — PostgresSaver 复用同一实例
- `src/api/deps.py` — 认证依赖注入，agent endpoint 复用

</code_context>

<specifics>
## Specific Ideas

- 意图类型：policy_qa, refund_troubleshooting, compensation_suggestion, approval_request, unknown
- 工具名称：get_order, get_refund_case, get_ticket, search_policy
- 风险等级：low, medium, high（Phase 3 只标记，Phase 4 接入审批）
- 降级响应示例："当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"
- evidence 引用格式示例："根据 policy_refund_timeout / chunk_003，该订单已超过自动退款处理时限"
- live smoke test 命令：`uv run python scripts/smoke_agent_live.py`

</specifics>

<deferred>
## Deferred Ideas

- Human approval / interrupt 机制（Phase 4）：高金额补偿、规则冲突、证据不足但用户要求执行、跨权限操作触发审批中断
- 写操作工具：create_coupon_grant_draft, create_approval_request（Phase 4）
- SSE 流式响应（Phase 5）
- 完整 observability：OTel + Prometheus + Grafana（后续 Phase）
- 指数退避、熔断器、异步恢复（后续 Phase）
- Redis 缓存热门 query 的检索结果
- RBAC-scoped retrieval（按角色限制可检索文档）

</deferred>

---

*Phase: 03-langgraph-core*
*Context gathered: 2026-05-11*
