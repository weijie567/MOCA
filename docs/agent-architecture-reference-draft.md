# MOCA Agent 架构参考草稿

> 草稿用途：这是后续让 Claude / Claude Code 基于参考仓库和本轮讨论继续设计 MOCA 架构、spec、phase plan 时使用的参考文件。它不是当前实现状态的最终文档，也不是直接执行计划。
>
> 重要约束：参考仓库只能用于提炼架构模式、接口边界、数据模型和实现思路，不能照抄目录、代码或业务假设。MOCA 必须保持自己的业务主线：商家运营与售后协同 Agent，围绕订单/工单问题、规则证据、处理建议、高风险审批、追踪回放和可回滚/可补偿动作展开。

---

## 1. 本文件要解决的问题

本轮讨论的核心不是“重新做一个 Agent demo”，而是把 MOCA 的架构表达和代码边界升级为更清晰的企业 Agent 原型：

- LangGraph 只做 Agent 编排和状态流转。
- Knowledge / RAG 是独立能力层，而不是 LangGraph 内部细节。
- Business Tools 是独立能力层，当前可用本地 demo DB 模拟外部系统。
- Memory 是语义记忆能力层，只承载 session memory、long-term profile memory、case memory 和 memory-specific policy；working memory 属于 LangGraph state，workflow checkpoint 属于 runtime recovery，audit/replay 属于 observability。
- Approval / SLA / Policy 是独立能力层，不靠 prompt 单独控制高风险动作。
- Action Execution 是独立能力层，即使当前不接真实公司 API，也要按可替换 adapter、幂等、补偿/回滚方向设计。
- Observability / Replay 是独立能力层，用于 trace、metrics、audit、timeline replay。
- Prompt 不是一个超长 system prompt，而是按节点拆成 intent、slot、recommendation、memory-write、final-response 等模板。

后续 Claude 生成架构或 spec 时，必须优先使用本文件中的约束，并结合当前 MOCA 仓库和已克隆参考仓库的实际内容验证，不能凭空编造“已实现”。

---

## 2. 一句话目标架构

MOCA 应该被设计为一个基于 LangGraph 的受控状态机 Agent：

> Agent 不直接拥有工具、记忆和业务系统；Agent 只编排它们。工具、记忆、RAG、审批和执行都是独立能力层。

更完整的描述：

> MOCA 是一个企业级商家运营与售后协同 Agent 原型。当前可以使用本地 demo 数据模拟真实业务系统，但架构上应将 LangGraph 编排层、知识检索层、业务工具层、记忆层、审批策略层、动作执行层和可观测层分离。这样既能安全演示，也保留未来替换真实系统 API 或拆成独立服务的边界。

---

## 3. “独立模块优先，未来可拆服务”的含义

不要把“分层架构”和“微服务架构”混为一谈。

- 分层架构：代码职责边界清楚，LangGraph 节点只依赖 service-layer contract，不直接访问底层 DB、pgvector、repository 或外部 API。
- 微服务架构：不同模块独立部署为不同进程/服务，通过 HTTP/gRPC/消息队列交互。

当前推荐：

```text
一个 FastAPI app / 一个 Python 进程 / 一个 repo
但内部按模块边界组织：

agent -> knowledge
agent -> business
agent -> memory
agent -> approvals
agent -> actions
agent -> observability
```

也就是说，当前 demo 中 Knowledge Service 和 Business Tools 可以以内置模块运行，但接口边界要独立，未来可替换成外部服务或真实公司 API，而不需要修改 LangGraph 主流程。

判断是否做到分层的标准：

| 状态 | 判断 |
| --- | --- |
| 没做到分层 | LangGraph node 里直接出现 `PolicyChunkRepository`、`EmbeddingService`、SQL 查询、pgvector 细节、订单 repository 细节 |
| 做到分层 | LangGraph node 只调用 `PolicyKnowledgeService`、`BusinessToolService`、`MemoryService`、`ApprovalService`、`ActionExecutor` 等 service contract |

---

## 4. 推荐的目标代码目录

后续重构时推荐逐步靠近以下结构，不要求一次性大搬目录：

```text
src/
├── agent/
│   ├── graph.py
│   ├── state.py
│   ├── nodes/
│   └── prompts/
│       ├── global_policy.py
│       ├── intent.py
│       ├── slots.py
│       ├── recommendation.py
│       └── final_response.py
│
├── knowledge/
│   ├── service.py
│   ├── schemas.py
│   └── evidence.py
│
├── business/
│   ├── service.py
│   ├── schemas.py
│   └── adapters.py
│
├── memory/
│   ├── service.py
│   ├── schemas.py
│   ├── session_store.py
│   ├── long_term_store.py
│   ├── case_memory.py
│   └── prompts.py
│
├── approvals/
│   ├── service.py
│   ├── policy.py
│   └── sla.py
│
├── actions/
│   ├── executor.py
│   ├── drafts.py
│   └── compensation.py
│
├── observability/
│   ├── tracing.py
│   ├── metrics.py
│   └── replay.py
│
├── api/
├── db/
├── repositories/
└── rag/
```

目录和架构层对应关系：

| 架构层 | 推荐目录 | 职责 |
| --- | --- | --- |
| API / Frontend Layer | `src/api/`, `frontend/` | REST/SSE、auth、审批 UI、trace UI、chat UI |
| LangGraph Orchestration | `src/agent/` | graph、state、nodes、routing、LLM prompt 调用，不碰底层存储细节 |
| Knowledge / RAG | `src/knowledge/`, `src/rag/` | policy search、evidence、embedding、rerank、citation validation |
| Business Tools | `src/business/` | 订单、工单、退款、券、物流等业务能力 contract + demo adapters |
| Memory | `src/memory/` | 语义记忆 domain：session memory、long-term profile memory、reviewed case memory、memory read/write policy、PII、identity、tombstone、review rules |
| Approvals | `src/approvals/` | approval policy、approval plan、SLA、升级、审批状态流转 |
| Actions | `src/actions/` | action draft、executor、idempotency、compensation/rollback metadata |
| Observability | `src/observability/` | traces、metrics、logs、run replay、timeline |
| Persistence | `src/db/`, `src/repositories/` | SQLAlchemy models、migrations、tenant-scoped data access |

---

## 5. 当前 MOCA 与目标架构的对照

> 注意：以下基于本轮对当前仓库的局部检查，后续写 spec 前必须重新检查当前文件，不能把本表当成永远正确的事实。

| 目标模块 | 当前 MOCA 相关结构 | 当前问题/差距 | 建议方向 |
| --- | --- | --- | --- |
| LangGraph 编排 | `src/agent/graph.py`, `src/agent/nodes/*`, `src/agent/state.py` | 主流程已存在，read/retrieval 已合并到 `investigate` bounded loop，写动作仍在 deterministic executor 节点 | 保留现有 graph；继续让 node 变薄，只调用 manager/service contract |
| Knowledge / RAG | `src/knowledge/retrieval.py`, `src/knowledge/service.py`, `src/rag/embedder.py`, `src/rag/ingestion.py`, policy repos | Retrieval orchestration 已归 Knowledge；`src/rag` 保留底层 embed/chunk/ingest infra | 保持 Agent 节点只通过 manager/service contract 获取 evidence |
| Business Tools | `src/business/service.py`, `src/business/adapters.py`, `src/integrations/demo_business/*`, repos | 业务读 facade 已独立；当前 adapter 仍是本地 demo DB | 保持 `BusinessToolService` 只承载 business scope、retry、fact projection 和 adapter 调用；agent-facing 校验归 `UnifiedToolManager` |
| Approval / HITL | `approval_gate`, `approvals router`, `ApprovalRequest`, `ApprovalStep` | 已有 interrupt/resume、approve/reject；审批计划、多级审批、SLA 策略仍可增强 | 增加 `rules/approval_policies.yaml`, `src/approvals/policy.py`, `src/approvals/sla.py` |
| Actions | `execute_action`, `src/tools/executors/action.py`, `src/actions/service.py`, `ActionDraft` | 当前执行动作主要创建草稿，无真实执行和补偿 contract | 后续增加 external execution / compensation metadata；demo 仍只创建 draft |
| Memory | `src/memory/service.py`, `repository.py`, `schemas.py`, `search.py`, `session_memory_load`, `memory_write` | PostgreSQL-authoritative session memory 已落地；`search_case_memory` 当前只检索 session-derived precedent；`long_term_memory_retrieve` 仍是 empty adapter；长期 profile memory、reviewed case memory 独立表、Redis hot cache 仍未实现 | 保持 working memory、workflow checkpoint、session memory、long-term profile memory、case memory、audit/replay 分层；`src/memory` 只承载语义记忆 domain；Redis 仅可作为非权威 hot cache；再扩 long-term/case memory |
| Intent | 当前已有 classify/extract nodes | 需要明确 intent taxonomy、confidence threshold、低置信度澄清路径 | 拆出 `src/agent/prompts/intent.py` 和 typed output schema |
| Prompt | 当前可有 prompts 文件 | 容易混成一个大 prompt 或散落节点 | 建议按节点拆 prompt：global_policy, intent, slots, recommendation, final_response；memory write 放 `src/memory/prompts.py` |
| Observability / Replay | `AgentRun`, `AgentStep`, traces API | 已有 trace 表；还可增强 timeline replay、OTel spans、metrics | 增加 `src/observability/replay.py`；后续参考 FastAPI observability 接 OTel/Grafana |

---

## 6. 推荐 LangGraph 主流程

目标流程：

```text
receive_request
  ↓
normalize_input
  ↓
intent_classification
  ↓
slot_extraction
  ↓
session_memory_load
  ↓
long_term_memory_retrieve
  ↓
investigate
  ↓
case_analysis / recommendation_generation
  ↓
risk_gate
  ↓
approval_gate 或 action_draft/action_execution
  ↓
final_response
  ↓
memory_write
  ↓
trace_close
```

简化表达：

```text
Input -> Intent -> Memory -> Tools -> RAG -> Analysis -> Risk -> Approval/Action -> Response -> Memory Write
```

设计原则：

- `intent_classification` 只分类和提取 routing hints，不生成最终答案，不决定审批。
- `investigate` 在 bounded loop 内只调用统一 manager 暴露的只读 business / knowledge / memory capability。
- `recommendation_generation` 生成建议和 `proposed_action`，但不执行动作。
- `risk_gate` 使用规则/策略引擎判断风险与审批需求，不能只靠 LLM prompt。
- `approval_gate` 使用 LangGraph interrupt/resume，支持 accept/reject/edit/respond 方向。
- `action_execution` 只能执行已允许动作，必须有 idempotency 和 audit。
- `memory_write` 只写经过筛选的摘要/候选记忆，不保存所有聊天为长期记忆。

---

## 7. 工具调用设计

### 7.1 不推荐完全开放 ReAct

客服/售后/退款/补偿场景不适合让模型自由执行任意工具。推荐：

> Graph-controlled tool calling + limited planner + typed tools

也就是“图控制的受限工具调用模式”。

### 7.2 工具分类

| 工具类别 | 示例 | 是否可自动调用 | 风险控制 |
| --- | --- | --- | --- |
| Read tools | `get_order`, `get_ticket`, `get_refund_case`, `get_logistics` | 可以，由指定 graph node 调用 | tenant/user 权限、审计、只读 |
| Retrieval tools | `search_policy`, `search_sop`, `search_past_cases` | 可以，由 RAG/Knowledge node 调用 | 必须返回 evidence / no-evidence fallback |
| Write / Action tools | `create_refund`, `issue_coupon`, `close_ticket`, `unban_account` | 不能由模型直接调用 | 先 proposed_action，再 risk gate，再 approval，再 executor |

### 7.3 节点级工具权限

| Graph node | 允许调用 |
| --- | --- |
| `investigate` | `get_order`, `get_ticket`, `get_refund_case`, `get_logistics`, `search_policy`, `search_sop`, `search_case_memory` |
| `memory_load_node` | `memory_service.load_context` |
| `recommendation_node` | 通常不直接调用工具，只使用已有 context/evidence/memory |
| `risk_gate_node` | `risk_policy.evaluate`, `approval_policy.plan` |
| `action_execution_node` | `action_executor.execute`，且只接受已审批或低风险允许动作 |

### 7.4 Tool contract 建议

```python
class ToolCallContext:
    tenant_id: str
    user_id: str
    role: str
    session_id: str
    run_id: str
    trace_id: str
    idempotency_key: str | None

class ToolResult:
    status: Literal["success", "error", "not_found", "permission_denied"]
    data: dict
    evidence_refs: list[EvidenceRef]
    error: ToolError | None
    latency_ms: int
```

高风险动作建议结构：

```python
class ProposedAction:
    action_type: Literal[
        "issue_coupon",
        "partial_refund",
        "full_refund",
        "close_ticket",
        "manual_review",
    ]
    target_type: str
    target_id: str
    amount: Decimal | None
    currency: str | None
    reason: str
    evidence_refs: list[EvidenceRef]
    risk_level: Literal["low", "medium", "high"]
```

### 7.5 从参考仓库提炼的工具调用经验

- `memory-agent` 使用 LLM `bind_tools([upsert_memory])`，如果最后一条消息有 tool_calls，就路由到 `store_memory` node，再把 tool result 返回给模型。这说明“工具调用可以作为 graph 条件分支”。但 MOCA 不应照搬自由 ReAct 写法，只借鉴“tool call -> dedicated node -> store/audit -> route back”的模式。
- `agents-from-scratch-ts` 的 email assistant 使用 triage node、response subgraph、ToolNode/HITL interrupt handler，说明工具调用可以被限制在响应 subgraph 中，并在执行前插入人工 review。
- `agent-inbox` 提供 human interrupt schema，强调 accept/edit/respond/ignore，不应只做 approve/reject。

---

## 8. 记忆设计

记忆不能只有一个 vector store。目标设计按语义分层：

| 记忆层 | 生命周期 | 内容 | 存储 | 是否给模型 |
| --- | --- | --- | --- | --- |
| Working Memory / Graph State | 单次 run | 当前状态、中间结果、审批状态、工具结果 | LangGraph `AgentState` + checkpoint snapshot | 是 |
| Workflow Checkpoint | run 恢复 | 当前节点、interrupt、幂等状态、副作用边界 | PostgreSQL checkpointer；Redis 仅可做 active-run hot cache | 否 |
| Session Memory / Conversation Memory | 同一 tenant/user/thread | active slots、last intent、session summary、unresolved questions | PostgreSQL `session_memories` + CAS；可选 Redis hot cache | 是 |
| Long-term Profile Memory | 跨会话 | 用户偏好、商家长期模式、稳定事实 | Postgres + pgvector，可带 TTL/review | 选择性给 |
| Case Memory / Episodic Memory | 历史案例 | 相似 case、处理结果、审批结果、outcome | Postgres metadata + pgvector summary | 作为参考，不作为政策依据 |
| Audit / Replay Log | 长期审计 | 输入、证据、工具调用、审批链、模型版本 | PostgreSQL append-only events/tables | 不作为 memory 注入 |

### 8.1 Working Memory

用于当前 graph run：

```python
class AgentState(TypedDict):
    tenant_id: str
    user_id: str
    session_id: str
    thread_id: str
    run_id: str
    user_query: str
    normalized_query: str | None
    intent: str | None
    intent_confidence: float | None
    extracted_slots: dict
    business_context: dict
    policy_evidence: list[Evidence]
    memory_context: dict
    recommendation: dict | None
    proposed_action: dict | None
    risk_assessment: dict | None
    approval_status: str | None
    action_result: dict | None
    final_response: str | None
```

### 8.2 Session Memory

用于同一 tenant/user/thread 内多轮上下文：

```json
{
  "active_slots": {
    "order_no": "ORD123",
    "ticket_no": "TKT7788"
  },
  "last_intent": "refund_troubleshooting",
  "session_summary": "用户正在处理 ORD123 未收到货退款争议，物流显示已签收但买家否认签收。",
  "unresolved_questions": ["需要确认是否有签收凭证"]
}
```

### 8.3 Long-term Memory

长期记忆必须克制，不能每轮都写，不能把临时聊天变成永久事实。写入条件：

- 跨会话仍然有用。
- 来自工具结果、明确用户陈述或人工标注。
- 非敏感或已脱敏。
- scope 明确：tenant/user/merchant/thread/case；不使用 global scope。
- 有 source_refs、confidence、expires_at/review 机制。
- 不把历史经验当政策规则。

### 8.4 Case Memory

历史案例只能作为 precedent，不是 policy。最终建议仍必须引用当前有效 policy evidence 和业务事实。

### 8.5 参考仓库经验

#### `langchain-ai/memory-agent`

事实依据：

- README 说明这是 ReAct-style agent with a tool to save memories。
- memory 按 configurable `user_id` scope 存储。
- `graph.py` 在 `call_model` 中从 store 按 `("memories", user_id)` 检索最近记忆，再把格式化记忆注入 system prompt。
- LLM 绑定 `upsert_memory` tool；如果产生 tool_calls，路由到 `store_memory` node。
- `tools.py` 的 `upsert_memory` 使用 `InjectedToolArg` 隐藏 `user_id` 和 store，避免模型直接控制这些安全上下文。

可借鉴：

- memory read/write 作为 graph 节点。
- store namespace 按 user/tenant/scope 隔离。
- tool args 中安全上下文由系统注入，不暴露给模型。
- memory 需要 eval，README 明确建议从 evaluation set 调优 memory 频率和质量。

不可照抄：

- MOCA 不应把长期记忆写入交给完全自由 ReAct。
- MOCA 的记忆 scope 要更复杂：tenant/user/merchant/thread/case。
- MOCA 的长期记忆必须有 TTL、source、confidence、review/audit。

#### `langchain-ai/langgraph-memory`

事实依据：

- README 说明这是可独立部署的 memory service，用于从 chat interactions 中提取 memories 并持久化，后续可语义查询。
- 它区分 continuous updates to a single memory schema 和 event-based memories。
- `memory_service/graph.py` 中有 patch memory 和 semantic memory 两种路径：
  - patch：fetch existing state -> extract JSON patch -> upsert。
  - insert：extract embeddable events -> insert memories。
- `schedule` node 会延迟处理完整 conversation，避免会话未结束就重复抽取。
- `scatter_schemas` 根据 schema update_mode 并行路由到 patch 或 insert。

可借鉴：

- session/user profile 一类可用 patch 型记忆。
- case/event 一类可用 insert 型语义记忆。
- memory extraction 可以是异步/延迟任务，不必阻塞主 Agent 回复。
- memory service 可以从主 Agent 分离；MOCA 当前先做 in-process module，未来可拆服务。

不可照抄：

- 它默认 Pinecone/Fireworks，不适合直接迁入 MOCA。
- MOCA 可优先用 Postgres + pgvector，与当前技术栈一致。

---

## 9. 意图识别设计

### 9.1 两阶段意图识别

推荐：

```text
Stage 1: deterministic / rule-based pre-routing
Stage 2: LLM structured classification
```

原因：意图会影响工具调用、RAG、审批、执行路径，不能完全靠自由文本判断。

Stage 1 可检查：

- 是否包含订单号/工单号/退款单号。
- 是否包含退款、补偿、券、封禁、解封、投诉、申诉等关键词。
- 是否包含金额。
- 是否明显是 small talk 或 unsupported。

Stage 2 用 LLM 输出结构化 JSON。

### 9.2 推荐 intent taxonomy

MVP 不要几十个 intent，一开始 8-10 个即可：

```python
Intent = Literal[
    "policy_qa",
    "order_status_inquiry",
    "refund_troubleshooting",
    "compensation_suggestion",
    "ticket_reply_draft",
    "appeal_or_unban",
    "complaint_escalation",
    "action_request",
    "small_talk",
    "unsupported",
]
```

### 9.3 Intent output schema

```json
{
  "intent": "refund_troubleshooting",
  "confidence": 0.86,
  "secondary_intents": ["compensation_suggestion"],
  "required_slots": ["order_no"],
  "extracted_slots": {
    "order_no": "ORD123",
    "ticket_no": null,
    "refund_case_no": null,
    "amount": 200
  },
  "risk_signals": ["refund_requested", "compensation_amount_present"],
  "needs_business_context": true,
  "needs_policy_retrieval": true,
  "needs_human_approval": "unknown"
}
```

关键约束：

- intent node 不生成最终答案。
- intent node 不决定审批。
- `needs_human_approval` 最多是 unknown/hint，真实审批由 risk gate 决定。
- confidence 低于阈值，例如 0.65，进入 clarification node。

### 9.4 从参考仓库提炼的意图/triage 经验

- `agents-from-scratch-ts` 的 email assistant 有 `triage_router`，把 email 分成 `respond`、`notify`、`ignore`，然后 graph 按分类结果路由。
- 对 MOCA 的借鉴：先做粗分类和 routing hints，再进入具体业务流程；不要让 triage 节点负责完整分析。
- `langgraph/examples/customer-support/customer-support.ipynb` 是客服场景官方示例，后续应打开 notebook 具体看 state、routing、tool use，而不是只凭路径推断。

---

## 10. Prompt 设计与插入位置

### 10.1 Prompt 文件不是节点本身

示例：

```text
src/agent/prompts/intent.py
```

含义：这是存放意图识别 prompt 模板的 Python 文件，不是 graph node。文件里的字符串模板才是 prompt。调用关系：

```text
src/agent/prompts/intent.py
        │ 提供 prompt 模板
        ▼
src/agent/nodes/intent_classification.py
        │ 调用 LLM
        ▼
AgentState.intent / slots / routing hints
```

### 10.2 Prompt 按节点拆分

不要把所有规则塞进一个超长 system prompt。推荐：

| Prompt | 推荐位置 | 使用节点 | 作用 |
| --- | --- | --- | --- |
| Global Agent Policy | `src/agent/prompts/global_policy.py` | 多个 LLM 节点共享 | 事实优先级、安全边界、禁止编造 |
| Intent Classification | `src/agent/prompts/intent.py` | `intent_classification_node` | 分类、confidence、slots、routing hints |
| Slot Extraction | `src/agent/prompts/slots.py` | `slot_extraction_node` | 提取订单号、工单号、金额等 |
| Recommendation | `src/agent/prompts/recommendation.py` | `recommendation_node` | 基于业务事实 + policy evidence + memory 生成建议 |
| Final Response | `src/agent/prompts/final_response.py` | `final_response_node` | 生成用户可读响应 |
| Memory Write | `src/memory/prompts.py` | `memory_write_node` 或 memory service | 生成 session summary / memory candidates |

### 10.3 Global policy prompt 建议内容

```text
You are a merchant operations support agent.

Rules:
- Use current business facts from tools as the source of truth.
- Use policy evidence from the knowledge service as the source of policy truth.
- Do not invent policy rules, order facts, refund status, or approval status.
- Historical case memory is precedent only, not policy.
- Long-term memory is auxiliary context, not final authority.
- Any proposed refund, coupon grant, ban removal, or account-sensitive action must be represented as a proposed_action.
- Do not execute high-risk actions directly.
- If evidence is insufficient, say what is missing and recommend manual review.
```

### 10.4 Intent prompt 示例

```text
Classify the user's request into one primary intent.

Allowed intents:
- policy_qa
- order_status_inquiry
- refund_troubleshooting
- compensation_suggestion
- ticket_reply_draft
- appeal_or_unban
- complaint_escalation
- action_request
- small_talk
- unsupported

Return JSON only.
Do not generate the final answer.
Do not decide approval. Approval is handled by the risk gate.
Extract only explicitly mentioned slots.
```

### 10.5 Recommendation prompt 的事实优先级

必须明确告诉模型：

```text
Priority of truth:
1. Current business facts from tools
2. Current policy evidence
3. Session memory
4. Long-term memory
5. Historical case memory

Historical case memory is precedent only. It is not policy.
If policy evidence is missing or weak, do not produce a definitive policy answer.
```

### 10.6 Prompt 不能替代代码控制

- 高风险审批不能只靠 prompt 控制。
- 工具权限不能只靠 prompt 控制。
- 记忆写入不能只靠 prompt 控制。
- 租户隔离不能靠 prompt 控制。

这些必须由代码层：policy engine、tool registry、authz、service contract、DB scope、audit log 控制。

---

## 11. 审批、SLA、策略配置

当前可以做、且适合增强企业级感的能力：

### 11.1 Risk 与 Approval 分开

```text
risk_rules.yaml:
  判断风险等级、风险原因、rule_ref。

approval_policies.yaml:
  判断是否需要审批、几级审批、谁审批、SLA 多久。
```

不要把风险判断和审批计划混在一个巨大 node 里。

### 11.2 Approval Plan 示例

```json
{
  "approval_required": true,
  "approval_plan": {
    "policy_id": "refund_high_value_v1",
    "levels": [
      {
        "level": 1,
        "required_role": "manager",
        "mode": "any_one",
        "sla_hours": 4
      },
      {
        "level": 2,
        "required_role": "finance",
        "mode": "any_one",
        "sla_hours": 8
      }
    ]
  }
}
```

### 11.3 规则示例

```yaml
approval_policies:
  - id: coupon_low_value
    match:
      action_type: issue_coupon
      amount_lte: 50
    approval:
      required: false

  - id: coupon_medium_value
    match:
      action_type: issue_coupon
      amount_gt: 50
      amount_lte: 200
    approval:
      required: true
      levels:
        - role: manager
          sla_hours: 4

  - id: refund_high_value
    match:
      action_type: full_refund
      amount_gt: 500
    approval:
      required: true
      levels:
        - role: manager
          sla_hours: 4
        - role: finance
          sla_hours: 8
```

### 11.4 参考仓库经验

- `agent-inbox` 明确提出 HumanInterrupt / HumanResponse schema，支持 `accept`、`edit`、`response`、`ignore`。MOCA 审批不应只停留在 approve/reject，可以逐步支持 edit proposed action 和 request more info。
- `Human-in-the-Loop-Workflow-LangGraph` 展示两阶段 interrupt：先 human review，再 publish confirmation。MOCA 可借鉴“双确认”用于真实高风险写动作，但不能照搬 Bluesky 发布业务。
- `agents-from-scratch-ts` 在 triage 后和工具执行前设置 interrupt，说明 HITL 可以放在多个风险点，不必只有一个 approval gate。

---

## 12. Action Executor 设计

即使不能接真实公司 API，也要按真实执行架构设计。

推荐流程：

```text
execute_action_node
  -> ActionExecutor.execute(proposed_action, approval_result)
      -> create_action_draft
      -> execute_with_demo_adapter
      -> record_execution_result
      -> register_compensation_action
```

ActionExecutionResult 示例：

```json
{
  "action_id": "act_123",
  "action_type": "issue_coupon",
  "execution_mode": "demo",
  "status": "executed",
  "external_ref": "demo_coupon_456",
  "rollback_supported": true,
  "compensation_action": {
    "action_type": "revoke_coupon",
    "target_id": "demo_coupon_456"
  }
}
```

关键点：

- 当前本地 DB 可以继续模拟外部系统。
- ActionDraft 不等于最终 ActionExecutor，但可以作为 executor 的第一步。
- 幂等键必须存在。
- 每个高风险动作要说明是否支持 rollback；如果不支持，需要 compensation/manual review。

---

## 13. Observability / Replay

### 13.1 应该观测什么

- 每个 LangGraph node 的 span。
- 每次 tool call 的 span。
- 每次 RAG retrieval 的 span。
- 每次 LLM call 的 model、latency、token、cost。
- 每个 approval decision 的 event。
- 每个 action execution 的 status 和 idempotency key。
- RAG no-evidence rate、best_score 分布。
- approval interception rate。
- tool error rate。
- route/intent accuracy。

### 13.2 Replay

MOCA 不一定先做“重新执行 LLM”的 replay。先做审计回放：

```text
GET /api/v1/agent-runs/{run_id}/replay
```

返回 timeline：

```json
{
  "run_id": "...",
  "timeline": [
    {"node": "receive_request", "input": "...", "output": "..."},
    {"node": "investigate", "tool": "search_policy", "evidence_refs": []},
    {"node": "approval_gate", "status": "interrupted", "approval_id": "..."}
  ]
}
```

### 13.3 参考仓库经验

- `fastapi-observability` 的 docker-compose 包含 Loki、Prometheus、Tempo、Grafana，多 FastAPI app，并配置 Loki logging driver。这适合参考完整 logs/metrics/traces 可观测栈。
- MOCA 不应一开始照搬整套部署，但可以先引入 OpenTelemetry instrumentation 和 trace_id/run_id/thread_id 日志关联。
- `full-stack-fastapi-template` 适合参考企业工程结构、Docker Compose、auth、测试、CI，但不指导 Agent 架构。

---

## 14. 已克隆参考仓库状态

本轮检查到 `/Users/ming/projects/reference-repos` 下已有：

| 仓库 | 路径 | 主要参考用途 | 使用方式 |
| --- | --- | --- | --- |
| `langchain-ai/langgraph` | `/Users/ming/projects/reference-repos/langgraph` | 官方 LangGraph，customer-support notebook | 重点看 `examples/customer-support/customer-support.ipynb` 的 state/routing/tool/HITL 思路 |
| `langchain-ai/memory-agent` | `/Users/ming/projects/reference-repos/memory-agent` | ReAct + memory tool + store namespace | 借鉴 memory read/write 作为 graph node；不要照搬自由 ReAct |
| `langchain-ai/langgraph-memory` | `/Users/ming/projects/reference-repos/langgraph-memory` | 独立 memory service、patch vs insert memory | 借鉴 memory service 分层、延迟抽取、schema 分发 |
| `langchain-ai/agents-from-scratch-ts` | `/Users/ming/projects/reference-repos/agents-from-scratch-ts` | triage、HITL、memory、typed state | 借鉴 triage/HITL/memory 思路；代码是 TS，不迁移 |
| `langchain-ai/agent-inbox` | `/Users/ming/projects/reference-repos/agent-inbox` | HITL inbox schema 和 UX | 借鉴 interrupt schema：accept/edit/respond/ignore |
| `fastapi/full-stack-fastapi-template` | `/Users/ming/projects/reference-repos/full-stack-fastapi-template` | FastAPI 工程、auth、Docker、CI | 借鉴工程结构，不换 MOCA 技术栈 |
| `blueswen/fastapi-observability` | `/Users/ming/projects/reference-repos/fastapi-observability` | FastAPI + OTel/Grafana/Loki/Prometheus/Tempo | 借鉴观测栈和 trace/log/metrics 关联 |
| `Human-in-the-Loop-Workflow-LangGraph` | `/Users/ming/projects/reference-repos/Human-in-the-Loop-Workflow-LangGraph` | 最小 interrupt + two-stage approval 示例 | 只参考 HITL 控制流，不参考业务域 |

---

## 15. 未克隆但可考虑的仓库

本轮讨论中提到但当前没有在 reference-repos 里看到：

| 仓库 | 是否必须 | 原因 |
| --- | --- | --- |
| `lhh737/LangChain-ReAct-Agent` | 可选 | 可参考 Agent/RAG/tools/prompts 模块化，但不是企业后台架构；在线看也够 |
| `webscit/opentelemetry-demo-python` | 可选 | 与 `fastapi-observability` 类似；如果已有 blueswen，可暂不 clone |
| `hyperdxio/fastapi-opentelemetry-example` | 可选 | 最小 FastAPI OTel 接入示例，较薄；不必优先 clone |
| `langchain-ai/agent-inbox-langgraph-example` | 建议考虑 | `agent-inbox` README 提到 Python 最小 working version，可能比 UI repo 更直接帮助 MOCA 的 interrupt schema 接入 |

如果要补 clone，建议优先：

```bash
cd /Users/ming/projects/reference-repos
git clone https://github.com/langchain-ai/agent-inbox-langgraph-example.git
```

说明：

- 运行目录：`/Users/ming/projects/reference-repos`
- 安全性：只下载公开仓库
- 不影响 MOCA branch/worktree/commit

`LangChain-ReAct-Agent` 可选：

```bash
cd /Users/ming/projects/reference-repos
git clone https://github.com/lhh737/LangChain-ReAct-Agent.git
```

---

## 16. 后续 Claude 生成 spec 时必须遵守的规则

### 16.1 必须先检查事实

在写任何架构 spec 前，Claude 必须：

1. 检查当前 MOCA 文件结构。
2. 检查相关模块代码片段。
3. 检查参考仓库的 README 和关键实现。
4. 明确区分：
   - 当前已实现。
   - 当前部分实现。
   - 当前未实现。
   - 参考仓库提供的模式。
   - 建议新增的设计。

不得把参考仓库能力说成 MOCA 已实现。

### 16.2 必须用“参考而不是照抄”原则

参考仓库的作用：

- 帮助理解 LangGraph/HITL/memory/tool calling 的实现模式。
- 帮助设计 contract、state、routing、schema、eval。
- 帮助找出 MOCA 当前架构边界不清的地方。

禁止：

- 直接复制参考仓库目录到 MOCA。
- 因参考仓库使用某个技术就更换 MOCA 技术栈。
- 把不属于商家售后业务的概念强塞进 MOCA。
- 用参考仓库的 README 替代对 MOCA 当前代码的检查。

### 16.3 Spec 应该输出的内容

后续如果让 Claude 生成架构 spec，建议包含：

1. 背景与目标。
2. 当前 MOCA 状态概览。
3. 目标分层架构图。
4. 模块职责边界。
5. 关键数据模型与状态 schema。
6. Tool contract。
7. Memory contract。
8. Intent taxonomy 和 output schema。
9. Prompt 文件组织。
10. Approval/SLA policy。
11. Action executor / compensation。
12. Observability / replay。
13. 迁移步骤，按最小 diff 分阶段。
14. 测试和 eval 计划。
15. 不做什么：不拆微服务、不接真实公司 API、不大规模推翻现有 graph。

---

## 17. 建议实施顺序

不要新建仓库，不要推翻 MOCA。直接在当前仓库渐进式重构。

推荐顺序：

1. 文档更新：README / `docs/architecture.md` 先改成目标分层架构。
2. Knowledge facade：新增 `src/knowledge/service.py`，让 policy retrieval node 调它。
3. Business Tools facade：新增 `src/business/service.py`，让 business context node 调它。
4. Memory module：新增 `src/memory/`，先做 session memory + active slots + summary。
5. Intent prompt/schema：明确 intent taxonomy、confidence threshold、clarification path。
6. Approval policy/SLA：新增 `rules/approval_policies.yaml`, `src/approvals/policy.py`, `src/approvals/sla.py`。
7. Action executor：新增 `src/actions/executor.py`，包住当前 ActionDraft，补 execution/compensation metadata。
8. Replay：新增 `src/observability/replay.py`，先做基于 AgentRun/AgentStep 的 timeline。
9. OpenTelemetry：参考 `fastapi-observability`，逐步给 node/tool/RAG/LLM/approval 添加 spans/metrics。

---

## 18. 面试/项目叙事建议

推荐说法：

> 当前实现没有拆成多个微服务，因为这是一个可本地运行的 demo。但我在架构上把 LangGraph 编排、Knowledge Service、Business Tools、Memory Service、Approval Service、Action Executor 和 Observability 做了清晰模块边界。LangGraph 节点只依赖这些 service 的 contract，不依赖 RAG、pgvector 或本地业务表的内部实现。因此未来如果要接真实订单系统或把 RAG 拆成独立服务，只需要替换 service adapter，不需要改 graph workflow。

更短版：

> MOCA 当前用本地 demo data 模拟外部业务系统，但架构上通过 service contract 隔离了 Agent 编排层和业务能力层。这样既保证 demo 可运行，也保留了生产系统的替换边界。

---

## 19. 核心结论

- 不建议新建仓库；当前 MOCA 已有主干闭环，应该在现有仓库上做架构边界重构。
- 不建议现在拆微服务；先做 in-process service modules，未来可拆服务。
- 不建议继续把所有东西都放在 `agent/tools` 语义下；应区分 Knowledge、Business Tools、Memory、Approvals、Actions。
- 不建议完全开放 ReAct；应采用 graph-controlled tool calling。
- 不建议把所有 prompt 合成一个大 system prompt；应按节点拆 prompt。
- 不建议长期记忆无条件写入；必须有 scope、source、confidence、TTL/review、audit。
- 不建议让历史 case 或 long-term memory 凌驾于 policy evidence。
- 不建议让 prompt 单独控制审批；审批必须由 risk/approval policy 和 action executor 控制。

最终目标：

> 把 MOCA 从“能跑的 LangGraph Agent demo”升级成“架构边界清晰、可解释、可扩展、可评估的企业级商家售后 Agent 原型”。
