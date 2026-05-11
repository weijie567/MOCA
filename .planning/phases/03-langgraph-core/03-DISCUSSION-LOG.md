# Phase 3: LangGraph Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 03-langgraph-core
**Areas discussed:** LLM 模型与调用方式, 图节点与流转设计, Execution trace 格式, Checkpointer 与线程记忆, AgentState 状态结构, Tool contract 与权限边界, RAG evidence 与 Agent 决策, 错误处理与降级策略, 验收测试范围

---

## LLM 模型与调用方式

### Q1: Agent 的主 LLM 用哪个模型？

| Option | Description | Selected |
|--------|-------------|----------|
| Qwen (DashScope) | 通义千问 qwen-plus/max，和 embedding 同平台 | |
| DeepSeek | 性价比高，中文能力强 | |
| OpenAI GPT-4o | function calling 最成熟，成本高 | |

**User's choice:** GLM-5.1（智谱/BigModel），通过 DashScope 兼容接口调用，API key 复用
**Notes:** 用户指定 DashScope 平台提供的 GLM-5.1 模型

### Q2: 工具调用方式

| Option | Description | Selected |
|--------|-------------|----------|
| Function calling（LLM 自主决定） | LLM 自行决定何时调用哪个工具 | |
| 图路由确定性调用 | 节点硬编码调用顺序 | ✓ |
| 混合：图路由 + function calling | 意图识别后由图路由，工具调用用 function calling | |

**User's choice:** 图路由确定性调用
**Notes:** 确定性更强，更容易调试和评估

### Q3: Prompt 语言策略

| Option | Description | Selected |
|--------|-------------|----------|
| 全中文 | System prompt 和工具描述用中文 | |
| 英文 prompt + 中文输出 | System prompt 英文，模型输出中文 | ✓ |
| You decide | Claude 决定 | |

**User's choice:** 英文 prompt + 中文输出

---

## 图节点与流转设计

### Q1: 节点拆分粒度

| Option | Description | Selected |
|--------|-------------|----------|
| 细粒度（6 节点） | 每步一个节点 | |
| 粗粒度（4 节点） | 合并相关步骤 | |
| You decide | Claude 决定 | ✓ |

**User's choice:** 8 节点细粒度设计（用户自定义方案）
**Notes:** receive_request → classify_intent → extract_slots → load_business_context → retrieve_policy_evidence → generate_recommendation → assess_risk_and_approval → final_response。核心原则：每个节点只做一类事情，结构化 I/O，可独立测试。

### Q2: assess_risk_and_approval 在 Phase 3 的范围

| Option | Description | Selected |
|--------|-------------|----------|
| 只标记风险，不中断 | 输出 risk_level，不触发 interrupt | ✓ |
| 跳过审批节点 | Phase 3 不包含该节点 | |
| You decide | Claude 决定 | |

**User's choice:** 只标记风险，不中断

---

## Execution Trace 格式

### Q1: Trace 存哪里

| Option | Description | Selected |
|--------|-------------|----------|
| 存 DB（agent_runs + agent_steps） | 持久化可回放 | |
| 只返回 response | 简单但不可回放 | |
| 两者都做 | DB 完整记录 + response 摘要 | ✓ |

**User's choice:** 两者都做（用户提供完整字段设计）
**Notes:** DB 用于回放/debug/评估/审计；response 摘要用于当前请求可解释性。不暴露敏感内容。Phase 3 不追求完整 observability。

---

## Checkpointer 与线程记忆

### Q1: Checkpointer 实现

| Option | Description | Selected |
|--------|-------------|----------|
| PostgresSaver | 复用已有 Postgres，持久化 | ✓ |
| MemorySaver（内存） | 简单但重启丢失 | |
| You decide | Claude 决定 | |

**User's choice:** PostgresSaver

### Q2: 线程记忆保留字段

| Option | Description | Selected |
|--------|-------------|----------|
| 全量保留 | slots + evidence + 结论 | |
| 精简保留 | slots + 结论 | |
| You decide | Claude 决定 | ✓ |

**User's choice:** 精简保留 + evidence references（用户自定义方案）
**Notes:** 保留 active_slots、last_intent、last_recommendation_summary、evidence_refs（只引用不存原文）、last_business_context_refs。不保留完整订单/退款/工单/policy chunk 原文。

---

## AgentState 状态结构

### Q1: 哪些字段进 checkpointer

| Option | Description | Selected |
|--------|-------------|----------|
| 全量持久化 | 所有字段都进 checkpointer | |
| 分层：persistent + ephemeral | 区分跨轮保留和本轮临时 | ✓ |
| You decide | Claude 决定 | |

**User's choice:** 分层：persistent + ephemeral（用户提供完整字段列表）

---

## Tool Contract 与权限边界

### Q1: Phase 3 工具是否全部只读

| Option | Description | Selected |
|--------|-------------|----------|
| 全部只读 | get_order, get_refund_case, get_ticket, search_policy | ✓ |
| 包含写工具 | 包含 create_coupon_grant_draft 等 | |

**User's choice:** 全部只读

### Q2: 工具失败时的处理方式

| Option | Description | Selected |
|--------|-------------|----------|
| 结构化错误返回 | 统一 {status, data, error} 格式 | ✓ |
| 抛异常 | 由全局错误处理捕获 | |

**User's choice:** 结构化错误返回（用户提供完整错误处理策略）

---

## RAG Evidence 与 Agent 决策

### Q1: 是否强制引用 evidence

| Option | Description | Selected |
|--------|-------------|----------|
| 强制引用 + 拒答 | 无证据则拒答 | |
| 强制引用 + 降级建议 | 无证据则降级 | |
| You decide | Claude 决定 | ✓ |

**User's choice:** 关键结论强制 evidence，证据不足分级处理（用户提供完整策略）
**Notes:** 业务判断必须引用 evidence。证据不足时不给确定性结论，只输出受限说明。证据完全缺失时拒绝生成业务判断。

---

## 错误处理与降级策略

### Q1: 是否 retry

| Option | Description | Selected |
|--------|-------------|----------|
| Retry 1 次 + 降级响应 | 可恢复错误 retry 1 次 | ✓ |
| 不 retry，直接降级 | 任何失败直接降级 | |
| You decide | Claude 决定 | |

**User's choice:** Retry 1 次 + 降级响应（用户提供完整策略）

---

## 验收测试范围

### Q1: 测试范围

| Option | Description | Selected |
|--------|-------------|----------|
| 单元 + 集成（mock LLM） | CI 不依赖真实 LLM | |
| 单元 + 集成 + live smoke test | 额外本地 smoke test | |
| You decide | Claude 决定 | ✓ |

**User's choice:** CI = 单元 + 集成 + mock LLM；live smoke test 本地手动不进 CI（用户提供完整测试策略）

---

## Claude's Discretion

- LangGraph 具体 API 用法
- PostgresSaver 配置和 migration
- Tool wrapper 实现模式
- Prompt 模板措辞
- Mock LLM 实现方式

## Deferred Ideas

- Human approval / interrupt 机制 → Phase 4
- 写操作工具 → Phase 4
- SSE 流式响应 → Phase 5
- 完整 observability → 后续 Phase
- 指数退避、熔断器 → 后续 Phase
