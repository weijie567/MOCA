<!-- generated-by: gsd-doc-writer -->
# MOCA 当前系统架构总览

> **文档类型：** CURRENT
> **描述范围：** 当前工作区的系统边界、分层与主要运行组件
> **最后核验：** 2026-08-04（当前工作区）
> **权威来源：** 当前源码、迁移、配置与架构边界测试
> **更新触发：** 部署边界、运行时分层、核心服务职责或权威数据源发生变化

## 阅读边界

本文描述当前仓库已经落地的运行架构。判断优先级为源码、测试、数据库模型与迁移、配置；[跨边界契约](../reference/contracts.md)中的 `TARGET` / `DEFERRED` 条目只有在源码或测试存在对应实现时，本文才把它写成现状。

状态标记：**已实现**表示当前主路径可达；**部分实现**表示接口或存储已经存在，但能力范围受限或尚未覆盖全部主路径；**目标态**表示仅有契约或设计意图，当前运行时没有完整实现依据。

## 系统概览

MOCA 当前是一个**模块化单体**：同一个 Python 应用进程承载 FastAPI 接入、LangGraph 编排、工具能力面与领域服务，PostgreSQL/pgvector 是主要权威存储；React/Vite 前端作为独立容器调用后端。运行时没有 Redis、消息总线或拆分后的业务微服务。FastAPI lifespan 创建 `AsyncPostgresSaver` 并将其注入 `build_graph()`，因此 API、Agent graph 与持久化恢复仍位于一个部署边界内（[`src/api/main.py:29`](../../src/api/main.py#L29)、[`src/agent/graph.py:224`](../../src/agent/graph.py#L224)、[`docker-compose.yml`](../../docker-compose.yml)）。

当前主图是 15 个 registered nodes 的 LangGraph 工作流，节点只负责状态流转和受控调用；业务事实、政策证据、记忆、审批和动作各自由独立 service boundary 持有。API/auth/run 边界先构造 `TrustedContext`；Agent 的工具发现与调用路径再把它投影为 `ToolCallContext`，并通过 `ToolPlatform` 做可见性、输入校验、运行时授权、执行、结果投影和审计。Reviewed case memory 的 planner 搜索也经 `ToolPlatform → MemoryToolExecutor`；memory context load、写入与 review lifecycle 则直接使用 memory service contract。审批、会话、safety snapshot 与 capability 同样通过各自 service boundary 调用（[`src/platform/trusted_context.py:90`](../../src/platform/trusted_context.py#L90)、[`src/tools/platform.py:28`](../../src/tools/platform.py#L28)、[`src/tools/executors/memory.py`](../../src/tools/executors/memory.py)、[`src/api/routers/approvals.py`](../../src/api/routers/approvals.py)）。

## 当前分层架构

下图强调当前实现的真实调用边界：实线表示主调用路径，虚线表示横切调用或经 `ToolPlatform` 的工具调用。`ToolPlatform` 只治理工具发现与调用；记忆上下文、审批和回放仍保留 Agent 运行时直接调用路径。图中的 PostgreSQL 是同一数据平台，不表示多个独立数据库；DashScope 是供 Agent 运行时与 RAG 使用的外部模型 API。

![MOCA 后端分层架构总览 V3（真实调用边界）](../moca-backend-overview-v3.png)

| 层 | 当前职责 | 主要实现与证据 | 状态 |
| --- | --- | --- | --- |
| 接入与协议层 | HTTP/SSE、统一错误格式、`trace_id`/`run_id`、JWT/OAuth2 scope、tenant/merchant scope、Agent run 与控制 API | [`src/api/main.py:49`](../../src/api/main.py#L49)、[`src/api/routers/agent.py:41`](../../src/api/routers/agent.py#L41)、[`src/api/routers/agent_runs.py:139`](../../src/api/routers/agent_runs.py#L139)、[`src/platform/trusted_context.py:123`](../../src/platform/trusted_context.py#L123) | 已实现 |
| Agent 运行时与编排层 | `StateGraph(AgentState)`、条件路由、LLM retry、PostgreSQL checkpoint、interrupt/resume | [`src/agent/graph.py:224`](../../src/agent/graph.py#L224)、[`src/agent/state.py:65`](../../src/agent/state.py#L65)、[`src/agent/nodes/approval_gate.py:96`](../../src/agent/nodes/approval_gate.py#L96) | 已实现 |
| 能力与安全平台层 | trusted context 投影、prompt context 预算、统一工具 catalog/policy/runtime、prompt-safe 投影、replay/redaction/lifecycle | [`src/platform/context_projections.py:86`](../../src/platform/context_projections.py#L86)、[`src/agent/context/assembler.py:28`](../../src/agent/context/assembler.py#L28)、[`src/tools/platform.py:84`](../../src/tools/platform.py#L84)、[`src/replay/validators.py:60`](../../src/replay/validators.py#L60) | 已实现；`ContextAssembler` 仅接入部分 LLM 节点 |
| 领域服务层 | 业务事实与查询、Knowledge/RAG、记忆、审批/风险、动作草稿、会话与 trace | `src/business/`、`src/knowledge/`、`src/memory/`、`src/approvals/`、`src/actions/`、`src/conversation/`、`src/replay/` | 已实现，能力范围见下文 |
| 数据与基础设施层 | PostgreSQL/pgvector、Alembic、LangGraph checkpoint、Demo business adapters、DashScope LLM/Embedding | [`src/db/models.py`](../../src/db/models.py)、[`src/db/migrations/versions/`](../../src/db/migrations/versions/)、[`src/integrations/demo_business/`](../../src/integrations/demo_business/)、[`src/config.py:7`](../../src/config.py#L7) | 已实现；外部业务动作执行未实现 |

### 当前 15 节点运行骨架

`build_graph()` 注册的节点可按职责分成四段，但真实执行由条件路由决定，并非每次请求都经过所有节点（[`src/agent/graph.py:228`](../../src/agent/graph.py#L228)、[`tests/architecture/test_canonical_graph_baseline.py:44`](../../tests/architecture/test_canonical_graph_baseline.py#L44)）：

1. **Intake & Safety**：`receive_request` → `safety_pre_route` → `session_context_load`。
2. **Understand & Context**：`contextual_intent_resolve` → `slot_resolution_gate`；需要 reviewed memory 时进入 `memory_context_load`。
3. **Investigate & Evidence**：`investigate` → 可选 `rag_context_build` → `recommendation_generation` → 可选 `claim_verify`。
4. **Govern & Respond**：`risk_gate` → `approval_gate` 或 `action_draft`，澄清分支经过 `clarification_gate`，所有终态汇入 `final_response`。

`AgentState` 同时保存可跨 turn 的 checkpoint 字段和每轮重置的 ephemeral 字段；它是运行时工作副本，不是业务、政策、审批或记忆的权威存储（[`src/agent/state.py:68`](../../src/agent/state.py#L68)、[`src/agent/state.py:86`](../../src/agent/state.py#L86)、[`src/agent/nodes/receive_request.py`](../../src/agent/nodes/receive_request.py)）。

## 核心模块职责

| 模块 | 拥有的职责 | 明确不拥有的职责 | 关键锚点 |
| --- | --- | --- | --- |
| `src/api` | 协议、认证依赖、SSE、Agent/approval/memory/trace API、run terminal finalizer | 领域规则与工具执行实现 | [`src/api/main.py:104`](../../src/api/main.py#L104)、[`src/api/services/agent_run_memory.py:105`](../../src/api/services/agent_run_memory.py#L105) |
| `src/agent` | graph、节点、router、`AgentState`、working-state/prompt 投影，以及当前 session/memory wiring 与 trace persistence helper | raw integration、tool executor 实现和领域权威；当前部分 wiring/helper 仍直接访问 repository/ORM | [`src/agent/graph.py:224`](../../src/agent/graph.py#L224)、[`src/agent/trace.py`](../../src/agent/trace.py)、[`tests/architecture/test_tool_boundaries.py:33`](../../tests/architecture/test_tool_boundaries.py#L33) |
| `src/platform` | canonical `TrustedContext`、deny-first `MerchantScopeV1` 与各服务投影 | prompt 内容和领域决策 | [`src/platform/trusted_context.py:42`](../../src/platform/trusted_context.py#L42)、[`tests/architecture/test_trusted_context_boundaries.py:33`](../../tests/architecture/test_trusted_context_boundaries.py#L33) |
| `src/tools` | `ToolCatalog`、`ToolPolicyEngine`、`ToolRuntime`、`ToolPlatform`、统一 `ToolResultV2` 投影 | 业务查询、RAG、记忆或动作领域逻辑 | [`src/tools/platform.py:28`](../../src/tools/platform.py#L28)、[`src/tools/runtime.py:26`](../../src/tools/runtime.py#L26) |
| `src/business` | tenant/merchant-scoped 业务事实、结构化业务查询 registry/compiler/projection、Demo adapter 投影 | 政策解释、记忆和审批授权 | [`src/business/service.py:127`](../../src/business/service.py#L127)、[`src/business/service.py:1536`](../../src/business/service.py#L1536)、[`src/business/query/compiler.py:51`](../../src/business/query/compiler.py#L51) |
| `src/knowledge` + `src/rag` | policy ingest、hybrid retrieval、rerank、provenance、`EvidenceRefV1`、verified package、claim verification | 业务事实和用户偏好 | [`src/knowledge/service.py:122`](../../src/knowledge/service.py#L122)、[`src/knowledge/schemas.py:32`](../../src/knowledge/schemas.py#L32)、[`src/rag/ingestion.py:126`](../../src/rag/ingestion.py#L126) |
| `src/memory` + `src/conversation` | same-thread continuity、prompt-safe conversation context、显式偏好、reviewed case precedent、active CWC、review/tombstone/write policy | 政策证据、当前业务事实和审批/动作权威 | [`src/memory/context_service.py:53`](../../src/memory/context_service.py#L53)、[`src/memory/case_working_context_schemas.py:74`](../../src/memory/case_working_context_schemas.py#L74)、[`src/conversation/service.py:30`](../../src/conversation/service.py#L30) |
| `src/approvals` | 风险绑定后的审批状态机、snapshot/hash、版本校验、trusted resume payload | Agent 路由和动作执行 | [`src/approvals/service.py:101`](../../src/approvals/service.py#L101)、[`src/approvals/snapshots.py:48`](../../src/approvals/snapshots.py#L48) |
| `src/actions` | 受审批或低风险 capability 绑定的 durable action draft 与幂等 | 真实退款、支付、优惠券发放或外部补偿执行 | [`src/actions/service.py:66`](../../src/actions/service.py#L66)、[`src/actions/capabilities.py:96`](../../src/actions/capabilities.py#L96)、[`tests/architecture/test_action_draft_boundaries.py:209`](../../tests/architecture/test_action_draft_boundaries.py#L209) |
| `src/replay` + trace repositories | append-only sequence、redaction、retention、run/step/approval/draft timeline | raw prompt/raw tool payload 与 deterministic rerun | [`src/replay/service.py:24`](../../src/replay/service.py#L24)、[`src/replay/validators.py:8`](../../src/replay/validators.py#L8)、[`src/repositories/trace_repo.py:28`](../../src/repositories/trace_repo.py#L28) |

## 事实、证据、记忆与决策权边界

| 信息类别 | 当前权威源 | 允许的用途 | 禁止替代 |
| --- | --- | --- | --- |
| 业务事实 | `BusinessFactService`、受 scope 约束的 Demo adapters、`orders/refund_cases/tickets` 等表；跨层只传 `BusinessFactRefV1` 或受控投影 | 回答订单/退款/工单状态，形成 risk/snapshot 的事实引用 | Memory、LLM 文本、历史 trace 不得充当最新业务事实 |
| 政策证据 | `PolicyKnowledgeService`、policy documents/blocks/chunks、`EvidenceRefV1`、`VerifiedEvidencePackageV1` | 政策回答、material claim 校验、审批 snapshot 的 verified evidence refs | Memory 或 prior policy mention 只能作为检索提示，不能成为证据 |
| 记忆与会话上下文 | `session_memories`、prompt-safe conversation tables、reviewed long-term preference/case memory、active CWC | slot continuity、最近对话、显式软偏好、已审核先例与 active case 工作上下文 | 不得授予 policy、approval 或 action authority；统一标记为 `contextual_only` |
| Graph/checkpoint state | `AgentState` + `AsyncPostgresSaver` | turn/run 恢复和节点间工作副本 | 不得覆盖 service/database 的权威记录 |
| 审批与动作状态 | approval request/level/assignment/decision/event、safety snapshot、action draft/capability | 决定是否允许恢复，以及生成何种 durable draft | 普通聊天文本和 LLM 自报“已批准”不得形成 trusted approval |
| LLM 输出 | intent/recommendation/material claim 草稿 | 提议、解释和生成回复 | 未经 claim/risk/approval gate 不得成为事实、证据或执行授权 |

该边界有直接测试保护：memory domain 不定义 `EvidenceRefV1`，session memory 不能补足缺失 policy evidence；reviewed memory 会按 tenant/merchant、review status、过期/删除/PII 状态过滤（[`tests/agent/test_memory_evidence_boundary.py:153`](../../tests/agent/test_memory_evidence_boundary.py#L153)、[`tests/memory/test_reviewed_memory_context_boundary.py:227`](../../tests/memory/test_reviewed_memory_context_boundary.py#L227)）。

## 关键数据流

### 普通查询与有证据回答

1. 客户端调用 `POST /api/v1/agent/chat` 或创建 `POST /api/v1/agent-runs`；middleware 分配 trace/run 标识，认证边界构造 `TrustedContext`。SSE 路径通过 `GET /api/v1/agent-runs/{run_id}/events` 输出运行事件。
2. Graph 先做安全预路由，加载同 thread 的 prompt-safe session context，再进行 intent/slot 裁决。缺少必要信息时 fail closed 到澄清或最终回复。
3. `investigate` 只通过 `ToolPlatform` 调用可见工具。业务读取进入 `BusinessToolService/BusinessFactService`；政策查询进入 `PolicyKnowledgeService`；reviewed case memory 进入 `MemoryToolExecutor`。
4. 需要政策依据时，`rag_context_build` 把候选 ref 重建为 verified evidence package；`recommendation_generation` 生成 material claims，`claim_verify` 决定是否允许进入动作路径。
5. `risk_gate` 绑定业务事实、verified evidence、claim verification、目标 merchant 与 action payload hash；无动作或任何关键校验失败时直接收敛到 `final_response`。
6. API finalizer 持久化 assistant message、run/step/trace 投影，并在完成路径触发 memory write。`memory_write` 不是 15 节点 graph 的 registered node，而是终态后的受策略控制副作用（[`src/api/services/agent_run_memory.py:105`](../../src/api/services/agent_run_memory.py#L105)、[`src/agent/nodes/memory_write.py:42`](../../src/agent/nodes/memory_write.py#L42)）。

### 审批中断、恢复与动作草稿

1. `risk_gate` 为 proposed action 生成并持久化 safety snapshot、payload hash 和 risk decision；高风险路径创建 versioned approval request。
2. `approval_gate` 调用 LangGraph `interrupt()`。审批只能通过受认证的 approvals API 和 `ApprovalService` 转换；普通聊天中的批准语句不构成 trusted result。
3. API 使用 `Command(resume=...)` 恢复同一 thread checkpoint。graph 会重新核对 tenant/run、request/level/assignment version、revision、payload hash 和 snapshot hash，再决定回到 `risk_gate`、继续等待、创建 draft 或结束。
4. 通过审批的动作，或满足严格低风险 capability 的窄路径，均只进入 `action_draft`。当前 `draft_outcome.status` 为 `not_executed_demo`，没有真实外部副作用（[`src/agent/graph.py:312`](../../src/agent/graph.py#L312)、[`src/agent/nodes/action_draft.py`](../../src/agent/nodes/action_draft.py)、[`tests/architecture/test_action_draft_boundaries.py:74`](../../tests/architecture/test_action_draft_boundaries.py#L74)）。

### 上下文、记忆与 replay 旁路

- `session_context_load` 聚合同 thread 的 slot continuity、rolling summary、recent messages 和 tool summaries；`memory_context_load` 只在路由需要时增加 reviewed explicit preferences、reviewed case precedents 与 active CWC。
- `ContextAssembler` 对 system/current message、安全约束、业务标识、verified policy refs、working state、会话与记忆做 prompt-safe 投影和预算裁剪；当前接入 `slot_resolution_gate`、`recommendation_generation`、`risk_gate`，其他 LLM 路径仍可能使用局部组装（[`src/agent/context/assembler.py:32`](../../src/agent/context/assembler.py#L32)）。
- replay 持久化 node/tool/RAG/LLM/memory/approval/action 的受控事件、sequence、resource refs 和 redacted payload。validator 明确拒绝 raw prompt、raw args、raw tool output、secret 与 PII，因此 replay 是审计 timeline，不是原始 transcript 或可重跑 LLM 的输入仓库（[`src/replay/validators.py:60`](../../src/replay/validators.py#L60)、[`tests/replay/test_replay_redaction_retention.py:54`](../../tests/replay/test_replay_redaction_retention.py#L54)）。

## 当前实现与目标态差异

| 能力 | 当前结论 | 不能写成现状的目标态 |
| --- | --- | --- |
| 部署边界 | 单 FastAPI 后端 + 前端 + PostgreSQL/pgvector 的模块化单体 | 独立业务微服务或消息驱动平台 |
| Prompt context | `ContextAssembler` 已在三个关键 LLM 节点使用 | 所有 LLM path 已统一接入同一 assembler |
| Long-term memory | 仅显式软偏好；可由显式用户/管理员输入进入，并受 review/source/scope/PII 规则限制 | 通用 profile、业务事实、policy authority 或任意 run summary 长期记忆 |
| Case memory | reviewed closed-case precedent 已实现；active CWC 是独立的 `contextual_only` 工作状态 | 未审核历史或 active CWC 直接作为跨 case 权威先例 |
| Approval | 版本化 request/level/assignment、六类 decision、hash/snapshot 绑定、interrupt/resume 已实现；当前 policy/runtime 是 single-level | policy-driven multi-level aggregation 已完整运行 |
| SLA | scanner 和 expiration event shape 已存在，但 `APPROVAL_SLA_SCANNER_ENABLED=false` 是默认配置 | reminder/escalation worker 已在生产式常驻运行 |
| Action | coupon grant durable draft、幂等和窄版低风险 capability 已实现 | 真实退款/支付/优惠券执行、outbox、reconciliation、compensation/rollback |
| Conversation/replay | prompt-safe messages/tool summaries/thread summary 与 redacted replay 已实现 | raw prompt/raw payload 对象存储、完整 transcript reconstruction、deterministic LLM rerun |
| Observability | request header、DB run/step/event、SSE timeline 已实现 | OpenTelemetry/Prometheus 等完整 telemetry pipeline |

## 数据落点

MOCA 产品表由 [`src/db/models.py`](../../src/db/models.py) 和 [`src/db/migrations/versions/`](../../src/db/migrations/versions/) 管理，覆盖以下逻辑数据域：

- tenant/user/merchant 与 orders/refund cases/tickets；
- policy documents/document blocks/policy chunks/RAG ingestion jobs 与 pgvector embedding；
- session/long-term/case memory、CWC、thread/case links、conversation messages、tool calls/results、thread summaries；
- approval requests/levels/assignments/decisions/events、safety snapshots、action drafts 与 auto-action capabilities；
- AgentRun、AgentStep 与 AgentTraceEvent。

LangGraph checkpoint 与产品表共用 PostgreSQL，但 checkpoint schema 不属于 MOCA ORM/Alembic 链；应用启动时由 `langgraph-checkpoint-postgres` 的 `AsyncPostgresSaver.setup()` 初始化和维护（[`src/api/main.py:29`](../../src/api/main.py#L29)、[`pyproject.toml`](../../pyproject.toml)）。PostgreSQL 是上述产品状态与 checkpoint 的持久化落点，但两类 schema 的 owner 不同。

DashScope 的 `glm-5.1` 与 `text-embedding-v4` 仅作为可替换的推理/向量化依赖，配置锚点见 [`src/config.py:19`](../../src/config.py#L19) 与 [`.env.example`](../../.env.example)；它们不拥有 tenant、业务事实、政策版本、审批或动作状态。

## 核验依据

- 主源码：`src/api/`、`src/agent/`、`src/platform/`、`src/tools/`、各领域 service、`src/db/models.py` 与迁移。
- 测试边界：canonical graph baseline、ToolPlatform import boundary、TrustedContext ownership、memory/evidence authority、action draft-only、replay redaction/retention。
- 配置与依赖：[`pyproject.toml`](../../pyproject.toml)、[`docker-compose.yml`](../../docker-compose.yml)、[`src/config.py`](../../src/config.py)。
- 交叉阅读：[`README.md`](../../README.md)、[Agent 工作流](agent-workflow.md)、[跨边界契约](../reference/contracts.md)。旧设计稿中的旧节点名或较早能力判断未作为当前事实复用。

代表性验证入口包括 canonical graph、ToolPlatform、TrustedContext、memory/evidence、approval/action 与 replay 边界测试；这些测试只证明所选边界断言成立，不替代数据库集成、外部模型或 UI 端到端验证。
