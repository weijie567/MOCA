NOTE: This file is ILLUSTRATIVE. The normative contract source is docs/contract-spec.md.

## 1. Title 和目标说明

MOCA 的目标架构是：面向商家运营与售后协同的企业级 Agent 原型。

它不是通用聊天机器人，也不是只为演示 LangGraph 的 demo。目标是把当前“能跑的 LangGraph Agent demo”升级为架构边界清晰、可解释、可扩展、可评估的商家售后 Agent：围绕订单/退款/工单事实、政策证据、处理建议、高风险审批、动作草稿、审计追踪和可回放 timeline 展开。

核心架构判断来自 `docs/agent-architecture-reference-draft.md`：

- LangGraph 只负责状态机编排、节点调度、条件路由、interrupt/resume。
- Knowledge / RAG、Business Tools、Memory、Approvals / SLA / Policy、Actions / Executor / Compensation、Observability / Replay 都应是独立能力层。
- 当前可以继续单 FastAPI app、单 Python 进程、单 repo，但代码边界要向 service contract 靠拢，未来可替换真实系统 API 或拆服务。
- Prompt 不能替代代码层控制。审批、工具权限、租户隔离、动作执行、记忆写入必须由代码和数据 contract 约束。

---

## Refactor Principles

1. F1: AAM is a target-architecture refactor, not a minimal-patch migration.
2. F2: Legacy implementation is adapter/rollback fallback, not a first-class target path.
3. F3: Runtime read-switch required only when persistence/online-safety requires it; service-only refactors default to direct cutover with git-revert + retained-adapter rollback.
4. F4: Shared trusted context is a single canonical contract; ToolCallContext / KnowledgeContext / AgentState identity are projections of it.
5. F5: Canonical schema is owned by its producer; consumers project, never redefine.
6. F6: A minimal observability envelope precedes the phases that emit events; full replay service may be deferred.
7. F7: Foundation contracts (state lifecycle, router seam, trusted context) precede capability facades.
8. F8: Contract tests are mandatory for every new boundary (positive/negative/boundary/forbidden).
9. F9: Deferred capabilities must still reserve a read interface early.
10. F10: Service facade ownership determines schema ownership unless explicitly delegated (e.g. snapshot/hash delegated to Phase 13).

---

## 2. Scope / Non-goals

### Scope

本文覆盖：

- 当前 MOCA 架构事实。
- 参考仓库代码级分析和可借鉴性判断。
- 目标分层架构。
- LangGraph workflow、AgentState 目标 schema、intent classification、tool calling、memory、prompt、approval/SLA/risk policy、action execution、observability/replay、数据模型建议。
- 分阶段迁移路线和测试/eval 计划。

### Non-goals

本文不做以下事情：

- 不修改 `src/` 代码。
- 不更换 MOCA 技术栈。
- 不把 MOCA 拆成微服务。
- 不接真实支付、退款、优惠券、封禁、物流或商家系统 API。
- 不照抄参考仓库目录、代码、prompt 或业务假设。
- 不把自由 ReAct 作为默认执行模型。
- 不让 LLM 直接执行高风险写动作。

---

## 3. 设计依据矩阵

| 设计主题 | 当前 MOCA 依据 | 参考仓库依据 | 是否采用 | 采用方式 | 不采用内容 |
| --- | --- | --- | --- | --- | --- |
| LangGraph workflow | `src/agent/graph.py` 已有 10 节点 workflow：`receive_request`、`classify_intent`、`extract_slots`、`load_business_context`、`retrieve_policy_evidence`、`generate_recommendation`、`assess_risk_and_approval`、`approval_gate`、`execute_action`、`final_response`。 | `memory-agent/src/memory_agent/graph.py` 展示 tool call 条件分支；`agents-from-scratch-ts/src/email_assistant.ts` 展示 triage -> subgraph；`Human-in-the-Loop-Workflow-LangGraph/src/graph.py` 展示 Command 路由。 | 采用 | 保留 MOCA 主 workflow，增加目标节点：memory load/retrieve/write、clarification、action draft/executor、trace close。 | 不采用完全自由循环 agent，也不把参考仓库 email/news workflow 搬入 MOCA。 |
| Intent classification | `src/agent/schemas.py` 当前 intent 只有 `policy_qa`、`refund_troubleshooting`、`compensation_suggestion`、`approval_request`、`unknown`；`src/agent/nodes/classify_intent.py` 用 structured output。 | `agents-from-scratch-ts/src/email_assistant.ts` triage 把 email 分成 ignore/respond/notify，用于路由。 | 部分采用 | 扩展 MOCA intent taxonomy，并引入 confidence threshold、clarification path、routing hints。 | 不采用 email 领域的 ignore/respond/notify 作为业务 intent。 |
| Tool calling | `src/agent/nodes/load_business_context.py` 直接调用 read tools；`src/agent/nodes/retrieve_policy_evidence.py` 直接调用 `search_policy`；`src/agent/tools/registry.py` 已有 typed registry 和 caller allowlist，但主流程未完全通过 registry/service。 | `memory-agent/src/memory_agent/tools.py` 使用 InjectedToolArg；`agents-from-scratch-ts/src/tools/base.ts` 有中央 tool registry；`agent-inbox` 和 HITL examples 在工具执行前中断。 | 采用 | 采用 graph-controlled tool calling + node-level allowlist + service facade。 | 不采用模型自由选择任意工具并直接写业务系统。 |
| Memory read/write | 当前 `AgentState` 有 checkpointer thread、`active_slots`、`last_intent`、`evidence_refs`、`last_business_context_refs`，README 明确 cross-session long-term memory out of scope。 | `memory-agent/src/memory_agent/graph.py` 读取最近 memory 注入 prompt；`langgraph-memory/memory_service/graph.py` 有 delayed extraction、patch/insert 双路径、schema fan-out；`agents-from-scratch-ts/src/email_assistant_hitl_memory.ts` 根据 HITL feedback 更新 memory。 | 采用 | 区分 working/session/long-term/case memory；先实现 session memory，长期和 case memory 作为独立服务目标。 | 不采用自由 ReAct 写长期记忆；不采用 Pinecone/Fireworks 默认栈；不把历史 case 当政策。 |
| Human-in-the-loop approval | `src/agent/nodes/approval_gate.py` 已有 LangGraph `interrupt`；`src/api/routers/approvals.py` 支持 approve/reject resume；`ApprovalRequest`、`ApprovalStep` 已持久化。 | `agent-inbox/README.md` 定义 HumanInterrupt/HumanResponse schema，支持 accept/edit/respond/ignore；`agent-inbox-langgraph-example/src/agent/graph.py` 有 Python 最小示例；`Human-in-the-Loop-Workflow-LangGraph/src/nodes/human_review_node.py` 支持编辑内容后 approve。 | 采用 | 把 MOCA 审批从 approve/reject 扩展到 accept/edit/reject/respond/ignore，并支持多级审批和 SLA。 | 不采用通用 inbox UI 的全部部署假设；不采用布鲁斯天空发布业务。 |
| Action execution | `src/agent/nodes/execute_action.py` 当前创建 durable action draft；`src/agent/tools/create_coupon_grant_draft.py` 写 `ActionDraft`，有 idempotency key；README 明确无真实支付/退款/券执行。 | `Human-in-the-Loop-Workflow-LangGraph/src/tools.py` 在 publish 前再次 interrupt；`agent-inbox` 支持 edit/accept action args。 | 采用 | 目标为 ActionExecutor facade，demo adapter 仍创建 draft，但 contract 包含 execution result、idempotency、rollback/compensation metadata。 | 不采用在 tool 内直接发布/执行外部动作；真实动作前双确认只作为未来高风险场景。 |
| RAG / Knowledge | `src/rag/retriever.py` 使用 DashScope embedding、pgvector、hybrid rerank、threshold/no-evidence；`src/rag/citation_validator.py` 做 deterministic citation validation；`search_policy` 仍位于 `src/agent/tools`。 | `docs/agent-architecture-reference-draft.md` 要求 Knowledge / RAG 是独立能力层。 | 采用 | 增加 KnowledgeService facade，Agent 节点只看 evidence contract，不直接接触 embedding/repo/pgvector。 | 不采用把 RAG 当 Agent 内部普通 tool 的长期形态。 |
| Observability / Replay | `src/agent/trace.py`、`src/repositories/trace_repo.py`、`src/api/routers/traces.py` 已有 AgentRun/AgentStep、approval/action timeline；`src/api/main.py` 有 request trace_id。 | `fastapi-observability/fastapi_app/main.py`、`utils.py`、`docker-compose.yaml` 展示 FastAPI metrics、OTLP、Tempo、Loki、Prometheus、Grafana 和日志 trace 关联。 | 采用 | 先做 in-process spans/metrics/log correlation，再考虑完整 Grafana stack。 | 不直接搬三 app compose 和 Loki logging driver 到 MOCA。 |
| Prompt organization | 当前 `src/agent/prompts.py` 单文件存 intent、slots、recommendation、risk、final prompts。 | `agents-from-scratch-ts/src/prompts.ts` 按 triage/agent/HITL/memory prompt 拆分；参考草稿要求按节点拆。 | 采用 | 拆成 `src/agent/prompts/intent.py`、`slots.py`、`recommendation.py`、`final_response.py`，memory prompt 放 `src/memory/prompts.py`。 | 不采用超长单 system prompt；不让 prompt 替代 policy/approval/tool 控制。 |
| Service boundary | 当前 repo 有 `src/repositories`、`src/rag`、`src/agent/tools`，但 graph nodes 仍直接依赖 tools/repositories 间接实现。 | `full-stack-fastapi-template/backend/app/api/deps.py`、`core/config.py`、`tests/conftest.py` 展示工程组织、依赖注入、settings、tests；参考草稿强调 in-process service modules。 | 采用 | 在单 app 内新增 service facade：knowledge、business_tools、memory、approvals、actions、observability。 | 不换 SQLAlchemy 为 SQLModel；不照搬模板业务模型或用户 CRUD。 |

---

## 4. 当前 MOCA 架构事实

### 4.1 已实现

当前 MOCA 已实现以下能力：

- FastAPI API 层：`src/api/routers/agent.py` 提供同步 chat；`src/api/routers/agent_runs.py` 提供 run 创建、SSE streaming 和 evidence 查询；`src/api/routers/approvals.py` 提供审批决策；`src/api/routers/traces.py` 提供 run trace。
- LangGraph workflow：`src/agent/graph.py` 定义 10 个节点和两个条件路由函数。
- AgentState：`src/agent/state.py` 区分 persistent memory 与 ephemeral context，包含 thread/user/tenant/role、active slots、last intent、evidence refs、business context、risk、approval、action、trace 等字段。
- Intent / slots / recommendation / risk structured output：`src/agent/schemas.py` 和 `src/agent/nodes/*.py` 使用 Pydantic schema 约束 LLM 输出。
- RAG：`src/rag/retriever.py` 使用 DashScope embedding、pgvector 检索、hybrid rerank、threshold gate；`src/rag/citation_validator.py` 做 citation deterministic validation。
- Business read tools：`get_order`、`get_refund_case`、`get_ticket` 读取 tenant-scoped 本地 demo DB，并对 merchant role 做访问控制。
- Approval interrupt/resume：`approval_gate` 使用 LangGraph `interrupt`；审批 API 用 `Command(resume=...)` 恢复 graph。
- Action draft：`execute_action` 创建 action draft，`ActionDraftRepository.create_or_get` 用 idempotency key 防重复。
- Trace / replay：`AgentRun`、`AgentStep`、`ApprovalRequest`、`ApprovalStep`、`ActionDraft` 持久化；`TraceRepository.build_timeline` 组合 agent step、approval、action draft timeline。
- 测试覆盖：graph happy path/no-evidence/cross-turn reset、routing、approval gate、approval integration、execute_action、trace persistence、tool contract、RAG/eval 等测试已存在。

### 4.2 部分实现

当前 MOCA 部分实现但边界仍不完整：

- Tool contract：`src/agent/tools/contracts.py` 和 `registry.py` 已有 typed registry、risk metadata、caller allowlist，但主 graph nodes 仍直接调用具体 tool 函数，没有统一走 BusinessToolService / KnowledgeService。
- Memory：`AgentState` 和 checkpointer 已支持同 thread 的 active slots、last intent、evidence refs；README 明确 cross-session long-term memory out of scope。尚未有独立 `src/memory` service、长期记忆、case memory、memory write policy。
- Approval：已有 approve/reject、过期处理、自审批限制、resume、审批 step 记录；尚未有 policy-driven multi-level approval、SLA escalation、accept/edit/respond/ignore。
- Observability：已有 DB trace 和 API request trace_id；尚未有 OpenTelemetry spans、Prometheus metrics、LLM token/cost 完整记录、RAG/tool/action 细粒度 metrics。
- Actions：已有 action draft 和幂等；尚未有 ActionExecutor contract、demo adapter/external adapter 分离、compensation/rollback metadata。
- Prompt：已有 `src/agent/prompts.py` 单文件；尚未按节点和能力层拆分。

### 4.3 未实现

当前仓库中没有找到以下已实现依据：

- 独立 KnowledgeService facade。
- 独立 BusinessToolService facade。
- 独立 MemoryService、Long-term Memory、Case Memory。
- 多级审批 policy 和 SLA escalation engine。
- accept/edit/respond/ignore 审批响应模型。
- 真实外部 action executor。
- compensation / rollback 执行记录。
- OpenTelemetry graph node spans / tool spans / LLM spans。
- 可重新执行 LLM 的 replay。当前是审计 timeline replay，不是 deterministic rerun。

### 4.4 Current-vs-target evidence

| Capability | Current evidence | Current limitation | Target contract | Migration phase |
| --- | --- | --- | --- | --- |
| AgentState lifecycle | `src/agent/state.py` 定义字段约定；`receive_request` 主动 reset 部分 ephemeral 字段。 | 当前不是 schema-level enforcement；writer、scope、reset/merge 规则未被统一验证。 | 第 10.1 节 lifecycle matrix；trusted fields 不可被 LLM 覆盖；router/state property tests。 | Phase 10 |
| Slot routing | 当前 graph 有 intent、slot extraction 和跨 turn active slots。 | session memory load/slot merge 尚未形成统一目标顺序；`A or B` required slot 无结构化表达。 | `intent -> session_memory_load -> slot_extraction -> resolve_slots -> route_after_slots`；`RequiredSlotExpression`。 | Phase 10, Phase 12 |
| Approval | 已有 interrupt/resume、approve/reject、审批持久化。 | 无 request/level/assignment version CAS、multi-level 聚合和 exact revision execution guard。 | 第 15 节 versioned approval state machine 和 optimistic locking。 | Phase 13 |
| Action | 已有 durable `ActionDraft` 和 idempotency key。 | demo/external outcome contract 未完全分离；无 external executor/reconciliation。 | demo 只写 draft + `draft_outcome`；external 原子校验后执行。 | Phase 14, Phase 17 |
| Replay | 已有 AgentRun/AgentStep 和组合 timeline。 | 事件枚举和 lifecycle coverage 不完整；不是统一 V3 event store。 | ReplayEventV3、稳定 sequence、完整 lifecycle enum 和 retention。 | Phase 15 |

---

## 5. 参考仓库分析结论

| 仓库 | 已检查文件 | 实际实现模式 | 可借鉴点 | 不适合 MOCA 的点 | 是否纳入最终 spec | 纳入方式 |
| --- | --- | --- | --- | --- | --- | --- |
| `langgraph` | `examples/customer-support/customer-support.ipynb`；并搜索 `docs/`、`libs/` 中 customer support 相关实现 | 指定 notebook 当前只有迁移说明：“This file has been moved”，没有 state/routing/tool/HITL 代码。本地 repo 未找到同名 customer support 实现。 | 只能确认：指定文件不能作为代码级模式依据。LangGraph repo README/docs 可作为 StateGraph、interrupt、checkpoint 基础背景，但不是本次 customer-support 代码依据。 | 不能编造 customer support graph 的 state、routing、tool/handoff 细节；不能把已迁移占位文件当实现。 | 不纳入 customer-support 代码级模式 | 在 spec 中明确排除：指定文件未提供代码级参考。 |
| `memory-agent` | `src/memory_agent/graph.py`、`tools.py`、`prompts.py`、`state.py` | ReAct-style memory agent：从 store namespace `("memories", user_id)` 搜索最近 memory，注入 system prompt；LLM bind `upsert_memory` tool；有 tool_calls 则路由 `store_memory`，再回到 `call_model`。`user_id` 和 `store` 用 InjectedToolArg 隐藏。 | memory read/write 作为 graph 节点；namespace 隔离；安全上下文由系统注入；tool call -> dedicated node -> audit/store -> route back。 | 自由 ReAct 写长期记忆不适合 MOCA；scope 只有 user，不足以表达 tenant/merchant/thread/case；无 TTL/source/confidence/review。 | 纳入 | 只借鉴 memory node、namespace、安全注入和 tool-call 条件分支。 |
| `langgraph-memory` | `memory_service/graph.py`、`_schemas.py` | 独立 memory service：`schedule` 延迟抽取；`scatter_schemas` 按 schema fan-out；patch memory 先 fetch existing state，再抽 JSON patch/upsert；semantic memory 抽取 embeddable event 后 insert。 | patch 型适合 user/merchant profile；insert 型适合 case/event memory；memory extraction 可异步/延迟；schema fan-out 支持多记忆类型。 | 默认 Pinecone/Fireworks，不适合直接迁移；抽取所有聊天可能带来隐私/成本风险；不能把 memory 当 policy。 | 纳入 | 采用 patch/insert 概念，存储优先 Postgres + pgvector。 |
| `agents-from-scratch-ts` | `src/email_assistant.ts`、`email_assistant_hitl.ts`、`email_assistant_hitl_memory.ts`、`schemas.ts`、`tools/base.ts`、`tools/default/memory-tools.ts`、`prompts.ts` | TS LangGraph email assistant：triage_router 分类 ignore/respond/notify；response_agent subgraph 通过 ToolNode 或 interrupt_handler 执行工具；HITL 支持 accept/edit/response/ignore；memory 版本按 namespace 读取/更新偏好。 | triage 先分类再路由；response subgraph；工具 registry；HITL 每次处理一个 tool call；基于人工反馈更新 memory。 | email domain 不适合 MOCA；示例里有 `toolChoice: required` 和自由工具循环，不适合高风险售后动作；memory 更新偏好过于个人助理化。 | 部分纳入 | 借鉴 triage/subgraph/HITL response handling/memory feedback 模式，不迁移代码和业务 prompt。 |
| `agent-inbox` | `README.md`、`src/components/agent-inbox/types.ts`、`hooks/use-interrupted-actions.tsx`、`components/interrupt-details-view.tsx` | 前端 inbox 和 LangGraph interrupted threads 管理。核心 schema：HumanInterrupt 包含 `action_request`、`config`、`description`；HumanResponse 类型为 `accept`、`ignore`、`response`、`edit`。UI 根据 config 决定可用动作，并把 response 发送回 graph。 | MOCA 审批流应从 approve/reject 扩到 accept/edit/respond/ignore；description 可用 markdown 解释风险、证据和建议动作；edit 可修改 proposed action args。 | 这是 LangGraph deployment UI，不应直接替换 MOCA frontend/API；不应照搬 local storage/deployment config。 | 纳入 | 采用 schema 概念映射到 MOCA approval API 和 UI。 |
| `agent-inbox-langgraph-example` | `src/agent/graph.py`、`state.py`、README | Python 最小示例：构造 HumanInterruptConfig，`interrupt([request])[0]`，按 response type 写回 state。 | Python 端 accept/edit/respond/ignore 的最小实现方式。 | 示例是 joke，不含权限、审批、SLA、action risk。 | 补充纳入 | 作为 MOCA interrupt payload schema 的 Python 参考。 |
| `Human-in-the-Loop-Workflow-LangGraph` | `src/graph.py`、`state.py`、`nodes/human_review_node.py`、`nodes/content_generation_node.py`、`prompts.py`、`tools.py` | 搜索 -> 内容生成 -> human review -> approve/reject；review node 可接受编辑字符串并自动 approve；`publish_post` tool 内在发布前再次 interrupt 确认。 | two-stage interrupt：草稿 review 和执行前 confirm；Command(goto=...) 路由；编辑后继续 approve。 | 新闻/Bluesky 发布业务不适合；tool 内直接 publish 外部服务不适合当前 MOCA；OpenAI/Tavily 栈不迁移。 | 部分纳入 | 借鉴二阶段审批/确认控制流，未来用于真实高风险动作。 |
| `full-stack-fastapi-template` | `backend/app/main.py`、`api/main.py`、`api/deps.py`、`core/config.py`、`core/db.py`、`models.py`、`tests/conftest.py`、Dockerfile、pyproject | FastAPI 工程模板：settings、CORS、router aggregation、JWT dependencies、DB session deps、Alembic、Docker、tests fixture、lint/type config。 | API deps/settings/tests/Docker/CI 组织可参考；安全依赖注入清晰。 | 使用 SQLModel，同 MOCA 当前 SQLAlchemy 不一致；业务是 users/items，不指导 Agent 架构。 | 部分纳入 | 只借鉴工程组织和测试结构，不换 ORM/模型。 |
| `fastapi-observability` | `fastapi_app/main.py`、`utils.py`、`docker-compose.yaml`、`etc/prometheus/prometheus.yml`、`etc/grafana/datasource.yml`、`etc/tempo/tempo.yml` | FastAPI metrics middleware；OpenTelemetry FastAPI instrumentation；OTLP -> Tempo；Prometheus scrape `/metrics`；Grafana datasource 关联 Prometheus/Tempo/Loki；日志带 trace_id/span_id。 | MOCA 应对 API、graph node、tool call、RAG、LLM、approval、action 建 spans/metrics/log correlation；metrics exemplar 关联 trace。 | 不直接搬多 app compose、Loki docker logging driver；不把部署栈作为 Phase 7。 | 纳入 | 先定义观测 contract，后续逐步接 OTel/Grafana。 |

---

## 6. 目标架构总览

MOCA 目标架构：一个 FastAPI app 内的分层 Agent 系统。

当前阶段不拆微服务，但内部必须按能力层组织：

- API / Frontend：负责认证、会话、审批 UI、trace UI、SSE。
- LangGraph Agent Orchestration：只做状态流转、节点编排、条件路由、interrupt/resume。
- Knowledge / RAG：负责政策知识、检索、证据、citation validation。
- Business Tools：负责订单、退款、工单、物流、商家风险等业务事实读取，当前通过本地 demo DB adapter。
- Memory：负责 working/session/long-term/case memory 的读写策略和存储。
- Approvals / SLA / Policy：负责风险规则、审批策略、多级审批、SLA、升级。
- Actions / Executor / Compensation：负责 action draft、demo adapter、idempotency、execution result、compensation metadata。
- Observability / Replay：负责 spans、metrics、logs、AgentRun/AgentStep、timeline replay。
- Persistence：负责 SQLAlchemy models、repositories、Postgres/pgvector、migrations。

### Canonical Schema Ownership

> ILLUSTRATIVE mirror. The normative producer/consumer ownership is defined in `docs/contract-spec.md` (§8.0 TrustedContext, §8.3 EvidenceRefV1, §15.3 CanonicalHashProfile, §17.2 Minimal Event Envelope). On any conflict, contract-spec wins; this table is a reading aid, not an independent source.

| Schema | Producer phase | Consumers | Rule |
| --- | --- | --- | --- |
| EvidenceRefV1 | Phase 8 | Phase 13 snapshot, Phase 15 replay | consumers project, never redefine |
| CanonicalHashProfile v1 | Phase 13 | Phase 14 / 15 / 16 | interface may be specified early, implementation deferred |
| TrustedContext | Phase 7 shared contract | Phase 8 KnowledgeContext, Phase 9 ToolCallContext, Phase 10 AgentState identity | all consumers are projections |
| Minimal Event Envelope | Phase 7/10 shared contract | Phase 12/13/14; full service Phase 15 | Phase 15 owns full replay; earlier phases conform to minimal envelope |

Canonical `TrustedContext` 至少包含 `tenant_id`、`user_id`、`role`、`merchant_scope` 和 correlation identifiers；这些字段来自 trusted API/auth/run boundary，不可由 LLM 或用户 payload 覆盖。

### Module Responsibility & Non-Overlap Matrix

> ILLUSTRATIVE mirror of the layer responsibilities; the normative service/schema contracts are in `docs/contract-spec.md` §8-§18. Use this as a non-overlap reading aid, not an independent normative source.

| Layer | Owns | Does NOT own | Exposes | Forbidden |
| --- | --- | --- | --- | --- |
| Knowledge/RAG | retrieval, chunk ranking, KnowledgeContext | policy decisions, identity fields | EvidenceRefV1 (producer) | producing CanonicalHashProfile; overriding trusted context |
| Memory (session/long-term/case) | session state persistence, long-term/case read seam | policy evidence | read seam interface (empty adapter until Phase 16) | producing EvidenceRefV1; acting as policy evidence |
| Approval/Snapshot | approval state machine, ActionSafetySnapshot, CanonicalHashProfile (Phase 13) | replay storage, routing | CanonicalHashProfile v1 (producer) | storing business objects in replay; score in snapshot |
| Replay/Observability | event log, redaction, retention, /replay API | business logic | replay read API | storing business objects; redefining minimal envelope fields |
| Action executor | executing actions, draft_outcome in demo-mode | approval logic | action result | writing non-draft outcomes in demo-mode |

---

## 7. 架构图

### 7.1 V1 分层能力图

这张图表达的是 MOCA 的目标能力边界，不表达每个 Agent run 的节点顺序。`AuthN/AuthZ + Tenant Scope` 是横切安全上下文：API 在进入 Agent、tools、approval、trace 前先确认用户身份、OAuth2 scope、role、tenant_id 和 merchant scope，并把这些字段注入后续 `AgentState`、tool context、repository query 和 checkpoint thread。

```mermaid
graph TB
    FE[Frontend: Chat / Approval / Trace UI] --> API[FastAPI API]
    API --> Auth[AuthN/AuthZ + Tenant Scope]
    API --> Runs[Agent Run / SSE / Approval APIs]
    Runs --> Graph[LangGraph Orchestration]

    Graph --> Intent[Intent + Slot Nodes]
    Graph --> Memory[Memory Service]
    Graph --> Biz[Business Tools Service]
    Graph --> Knowledge[Knowledge Service / RAG]
    Graph --> Policy[Risk + Approval Policy Service]
    Graph --> Actions[Action Executor]
    Graph --> Obs[Observability + Replay]

    Biz --> DemoAdapters[Demo DB Adapters]
    DemoAdapters --> DB[(PostgreSQL Business Data)]

    Knowledge --> Retriever[RAG Retriever + Citation Validator]
    Retriever --> Vector[(PostgreSQL + pgvector)]
    Retriever --> Embedder[Embedding Provider]

    Memory --> SessionMem[(Session Memory)]
    Memory --> LongMem[(Long-term Memory + pgvector)]
    Memory --> CaseMem[(Case Memory)]

    Policy --> ApprovalDB[(Approval Requests / Steps)]
    Actions --> ActionDB[(Action Drafts / Execution Results)]
    Obs --> TraceDB[(AgentRun / AgentStep / Timeline)]
    Obs --> OTel[OTel Spans / Metrics / Logs]

    DB --> Persistence[Repositories]
    Vector --> Persistence
    ApprovalDB --> Persistence
    ActionDB --> Persistence
    TraceDB --> Persistence
```

### 7.2 V2 细粒度流程路由图

这张图表达目标 graph 的流程分支、intent routing、gate 和 service 调用关系。它不是严格的 `StateGraph.add_node(...)` 节点图，因为里面混合了节点、条件 router、path label 和 service 调用说明。当前 `src/agent/graph.py` 仍是较线性的 10 节点主链。V2 设计的目标是：先按 intent 做粗路由，再按是否需要业务事实、政策证据、记忆、审批和动作执行决定是否进入对应节点。

第 7 节图仅是 illustrative view。第 9.4 节 node contract table 和第 9.5 节 router contract table 是 normative source；图中不得引入与其冲突的 edge。

图中的 `security_context` 是 trusted context injection / API-auth boundary；`resolve_slots`、`revalidate_edited_action` 是 deterministic helper；`*_path` 是 path label；`small_talk_response`、`unsupported_or_manual_review`、`business_fact_response`、`insufficient_evidence_response` 是由 `final_response.response_type` 表达的 response mode。它们均不是额外注册的 LangGraph node。

严格的 LangGraph node-only 图见下一节 `7.3 V2 严格 LangGraph 节点图`。

设计来源：

- 当前 MOCA：保留 `receive_request -> classify/extract/context/RAG/recommend/risk/approval/action/final` 的可运行主干。
- `agents-from-scratch-ts`：借鉴 triage router 先分类再进入 response subgraph 的模式。
- `agent-inbox` / `agent-inbox-langgraph-example`：借鉴 interrupt payload 和 accept/edit/respond/ignore 分支。
- `memory-agent` / `langgraph-memory`：借鉴 memory read/write 作为独立节点，并把长期记忆写入放到后置策略控制。
- `Human-in-the-Loop-Workflow-LangGraph`：借鉴 review 后 approve/reject/edit 分支，以及真实高风险执行前可二次确认的思想。

```mermaid
graph TD
    START([START]) --> Receive[receive_request\ncreate run context]
    Receive --> Security[security_context\nAuthN/AuthZ + tenant scope]
    Security --> Normalize[normalize_input\nclean query + locale]
    Normalize --> Intent[intent_classification\nintent + confidence + routing hints]

    Intent --> Confidence{confidence >= threshold?}
    Confidence -->|no| Clarify[clarification_gate\nask missing intent/slots]
    Clarify --> Final[final_response]

    Confidence -->|yes| IntentRoute{route by intent}

    IntentRoute -->|small_talk| SmallTalk[small_talk_response]
    SmallTalk --> Final

    IntentRoute -->|unsupported| Unsupported[unsupported_or_manual_review]
    Unsupported --> Final

    IntentRoute -->|policy_qa| PolicyPath[policy_qa_path]
    PolicyPath --> PolicyRetrieve[policy_evidence_retrieve\nKnowledgeService.search]
    PolicyRetrieve --> EvidenceGate{strong or partial evidence?}
    EvidenceGate -->|no| NoEvidence[insufficient_evidence_response]
    NoEvidence --> Final
    EvidenceGate -->|yes| PolicyAnswer[recommendation_generation\nanswer grounded by citations]
    PolicyAnswer --> OptionalRisk{proposed action exists?}
    OptionalRisk -->|no| Final
    OptionalRisk -->|yes| RiskGate[risk_gate\nRiskPolicy + ApprovalPolicy]

    IntentRoute -->|order_status_inquiry| OrderPath[order_status_path]
    OrderPath --> SessionLoad[session_memory_load\nactive slots + summary]
    SessionLoad --> SlotExtract[slot_extraction\norder/refund/ticket/amount]
    SlotExtract --> ResolveSlots[resolve_slots\ndeterministic helper]
    ResolveSlots --> SlotRoute{route_after_slots}
    SlotRoute -->|missing required group| Clarify
    SlotRoute -->|complete| BizFetch[business_context_fetch\nBusinessToolService read tools]
    BizFetch --> ContextGate{context sufficient?}
    ContextGate -->|no| Clarify
    ContextGate -->|yes| OrderResponse[business_fact_response]
    OrderResponse --> Final

    IntentRoute -->|refund_troubleshooting| RefundPath[refund_troubleshooting_path]
    IntentRoute -->|compensation_suggestion| RefundPath
    IntentRoute -->|ticket_reply_draft| RefundPath
    RefundPath --> SessionLoad
    BizFetch --> NeedPolicy{needs policy evidence?}
    NeedPolicy -->|no| ContextOnlyReco[recommendation_generation\nfrom business facts only]
    NeedPolicy -->|yes| PolicyRetrieve
    PolicyAnswer --> CaseRetrieve[case_memory_retrieve\nprecedent only]
    CaseRetrieve --> Reco[recommendation_generation\nfacts + evidence + memory]
    ContextOnlyReco --> RiskGate
    Reco --> RiskGate

    IntentRoute -->|action_request| ActionPath[action_request_path]
    ActionPath --> SessionLoad
    ContextGate --> ActionEvidence[policy_evidence_retrieve\nrequired for action]
    ActionEvidence --> ActionEvidenceGate{evidence sufficient?}
    ActionEvidenceGate -->|no| NoEvidence
    ActionEvidenceGate -->|yes| ActionReco[recommendation_generation\nproposed_action candidate]
    ActionReco --> RiskGate

    RiskGate --> RiskRoute{approval/action route}
    RiskRoute -->|no proposed action| Final
    RiskRoute -->|auto allowed low risk| Draft[action_draft\ndurable draft]
    RiskRoute -->|approval required| Approval[approval_gate\ninterrupt/resume]

    Approval --> ApprovalDecision{human response}
    ApprovalDecision -->|accept/approve + request approved| Draft
    ApprovalDecision -->|accept/approve + next level pending| Approval
    ApprovalDecision -->|edit| Revalidate[revalidate_edited_action\nrisk + policy again]
    Revalidate --> RiskGate
    ApprovalDecision -->|respond/request info| NeedsInfo[approval_needs_info lifecycle finalizer\nrun remains interrupted]
    NeedsInfo --> TraceClose
    ApprovalDecision -->|reject| Final
    ApprovalDecision -->|ignore/expired| Final

    Draft --> ExecutionMode{execution mode}
    ExecutionMode -->|demo| Final
    ExecutionMode -->|external| Execute[action_execution\nexternal adapter]
    Execute --> Final
    Final --> MemoryWrite[memory_write\nsession now; long-term/case candidates]
    MemoryWrite --> TraceClose[trace_close\nAgentRun timeline + metrics]
    TraceClose --> END([END])
```

### 7.3 V2 严格 LangGraph 节点图

这张图只展示建议在目标实现中通过 `StateGraph.add_node(...)` 注册的 LangGraph 节点。菱形 router 不是节点，而是 `add_conditional_edges(...)` 使用的路由函数。KnowledgeService、BusinessToolService、MemoryService、ApprovalPolicy、ActionExecutor、Observability 也不是 LangGraph 节点，而是节点内部调用的分层 service。

目标 V2 建议注册 **18 个 LangGraph 节点**：

1. `receive_request`
2. `normalize_input`
3. `intent_classification`
4. `clarification_gate`
5. `slot_extraction`
6. `session_memory_load`
7. `long_term_memory_retrieve`
8. `business_context_fetch`
9. `policy_evidence_retrieve`
10. `case_memory_retrieve`
11. `recommendation_generation`
12. `risk_gate`
13. `approval_gate`
14. `action_draft`
15. `action_execution`
16. `final_response`
17. `memory_write`
18. `trace_close`

这份 node list 是概念能力清单，不表示执行顺序；实际顺序由 intent-specific path 和 deterministic routers 决定。

`security_context` 不建议作为独立 LangGraph 节点注册。它应由 API/auth dependency 和 graph input/config 注入，作为 `ToolCallContext`、`AgentState` 和 checkpoint thread scope 的一部分。如果后续要把 tenant/role/scope 校验放入 graph，也可以新增 `security_context` 节点，但那会把目标节点数从 18 增加到 19。

```mermaid
graph TD
    START([START]) --> N1[receive_request]
    N1 --> N2[normalize_input]
    N2 --> N3[intent_classification]

    N3 --> R1{route_after_intent}
    R1 -->|low confidence / missing required intent| N4[clarification_gate]
    R1 -->|needs slots| N6[session_memory_load]
    R1 -->|policy_qa without slots| N9[policy_evidence_retrieve]
    R1 -->|small_talk / unsupported| N16[final_response]

    N4 --> N16

    N6 --> N5[slot_extraction]

    N5 --> R2{route_after_slots}
    R2 -->|missing after session merge| N4
    R2 -->|slots ok + needs long-term memory| N7[long_term_memory_retrieve]
    R2 -->|slots ok + skip long-term memory| N8[business_context_fetch]

    N7 --> N8

    N8 --> R4{route_after_business_context}
    R4 -->|context insufficient| N4
    R4 -->|business fact answer only| N16
    R4 -->|needs policy evidence| N9[policy_evidence_retrieve]
    R4 -->|can recommend without policy| N11[recommendation_generation]

    N9 --> R5{route_after_policy_evidence}
    R5 -->|no evidence| N16
    R5 -->|needs case memory| N10[case_memory_retrieve]
    R5 -->|skip case memory| N11

    N10 --> N11

    N11 --> R6{route_after_recommendation}
    R6 -->|no proposed action| N16
    R6 -->|proposed action or risk signal| N12[risk_gate]

    N12 --> R7{route_after_risk}
    R7 -->|blocked / no action| N16
    R7 -->|approval required| N13[approval_gate]
    R7 -->|auto allowed| N14[action_draft]

    N13 --> R8{route_after_approval}
    R8 -->|accept / approve + request approved| N14
    R8 -->|accept / approve + next level pending| N13
    R8 -->|edit| N12
    R8 -->|respond / request info| N18
    R8 -->|reject / ignore / expired| N16

    N14 --> R9{route_after_action_draft}
    R9 -->|demo| N16
    R9 -->|external| N15[action_execution]
    N15 --> N16

    N16 --> N17[memory_write]
    N17 --> N18[trace_close]
    N18 --> END([END])
```

#### 节点与 service 边界

| LangGraph 节点 | 节点职责 | 调用的 service / contract |
| --- | --- | --- |
| `receive_request` | 初始化 run、thread、ephemeral state、trace step | Run context / trace helper |
| `normalize_input` | 清洗 query、语言/渠道标准化 | 无或 InputNormalizer |
| `intent_classification` | 输出 primary_intent、requested_operation、confidence、routing hints | LLM structured output / IntentPrompt |
| `clarification_gate` | 生成澄清问题或缺失信息说明 | Clarification policy / Final response template |
| `slot_extraction` | 提取订单、退款、工单、金额、商家等 slots | LLM structured output / SlotPrompt |
| `session_memory_load` | 读取同 thread active slots、summary、unresolved questions | MemoryService session read |
| `long_term_memory_retrieve` | 读取稳定偏好或商家长期模式 | MemoryService long-term search |
| `business_context_fetch` | 拉取订单/退款/工单/物流/商家风险事实 | BusinessToolService read tools |
| `policy_evidence_retrieve` | 检索政策/SOP 证据并做 no-evidence gate | KnowledgeService / RAG / citation validator |
| `case_memory_retrieve` | 检索历史类似 case，作为 precedent | MemoryService case search |
| `recommendation_generation` | 生成处理建议和 proposed_action candidate | LLM structured output / RecommendationPrompt |
| `risk_gate` | 评估风险、审批需求、动作是否可自动草稿 | RiskPolicy + ApprovalPolicy |
| `approval_gate` | 创建 interrupt，等待 accept/edit/respond/reject/ignore | ApprovalService / LangGraph interrupt |
| `action_draft` | 持久化动作草稿；demo mode 同时写非执行 outcome | ActionExecutor.create_draft |
| `action_execution` | 仅 external adapter 执行 | ActionExecutor.execute |
| `final_response` | 生成面向用户的最终回复 | Deterministic template or FinalResponsePrompt |
| `memory_write` | 写 session memory，生成 long-term/case candidates | MemoryService write policy |
| `trace_close` | 关闭 run，补全 timeline、metrics、audit | Observability / Replay service |

#### Router 函数不计入节点数

Canonical router 函数包括：

- `route_after_intent`
- `route_after_slots`
- `route_after_business_context`
- `route_after_policy_evidence`
- `route_after_recommendation`
- `route_after_risk`
- `route_after_approval`
- `route_after_action_draft`

这些函数只读取 `AgentState` 并返回下一个 node key，不应调用 LLM、tools、repositories 或外部 API。

### 7.4 V2 读法和可回退边界

- V1 分层能力图用于说明模块边界。
- V2 节点路由图用于说明一个 Agent run 如何按 intent 和风险条件流转。
- 第 7 节图是 illustrative；第 9.5/9.6 节 contract table 是 normative source，任何实现和 review 冲突均以第 9 节为准。
- 所有 Mermaid 图均为 illustrative；第 9-18 节 contract tables 是 normative source。
- V2 是目标设计，不要求一次性实现全部节点。
- 若需要回退第二版，只删除 `7.2 V2 细粒度流程路由图`、`7.3 V2 严格 LangGraph 节点图`、`7.4 V2 读法和可回退边界`，以及第 9 节中的 V2 routing 表，不影响 V1 spec 主体。

---

## 8. 模块分层设计

### 8.1 API / Frontend

当前依据：`src/api/routers/agent.py`、`agent_runs.py`、`approvals.py`、`traces.py`、README。

目标职责：

- 接收 chat/run 请求，创建或执行 AgentRun。
- 提供 SSE node-level progress。
- 提供 approval list/detail/decision API。
- 提供 trace timeline/replay API。
- 统一处理 auth、OAuth2 scopes、tenant/user/role 注入。
- 前端展示 chat、evidence、approval、action draft、timeline。

边界：

- API 层不做 Agent 推理。
- API 层不直接执行 action。
- API 层可以调用 ApprovalService/RunService，但不直接拼装复杂 graph state。

### 8.2 LangGraph Agent Orchestration

当前依据：`src/agent/graph.py` 和 `src/agent/nodes/*`。

目标职责：

- 定义节点顺序和条件路由。
- 维护 `AgentState`。
- 调用 service contract。
- 管理 interrupt/resume。
- 收集 node outputs 和 trace events。

边界：

- 不直接访问 repository、pgvector、embedding、SQL 查询。
- 不直接执行真实写动作。
- 不把 Memory/Knowledge/Business Tools 的内部实现塞进节点。

### 8.3 Knowledge / RAG

当前依据：`src/rag/retriever.py`、`schemas.py`、`citation_validator.py`、`ingestion.py`、`search_policy.py`。

目标职责（叙述性）：

- KnowledgeService facade 管理 query rewrite、embedding、hybrid rerank、threshold、no-evidence fallback、EvidenceRef、claim/evidence binding 和 citation validation。
- 对 Agent 只暴露 evidence contract，不暴露 pgvector/repo 细节。
- KnowledgeService 只看 `KnowledgeContext`（canonical `TrustedContext` 的最小投影），Phase 8 不直接依赖 Phase 9 `ToolCallContext`。

> Normative 接口契约（`PolicyKnowledgeService.search` 签名、`knowledge_search_request.v2` / `knowledge_search_result.v2`、canonical EvidenceRefV1 字段表与 hash projection、Knowledge rules）见 `docs/contract-spec.md` §8.3。本小节仅为叙述性概览。

### 8.4 Business Tools

当前依据：`get_order.py`、`get_refund_case.py`、`get_ticket.py`、`authz.py`、`registry.py`。

目标职责（叙述性）：

- BusinessToolService 统一读工具：order/refund/ticket/logistics/merchant risk；当前 adapter 为本地 demo DB，未来替换为真实系统。
- 只读工具可以自动调用；写工具不能由 business tool read node 执行。
- tenant/user/role/idempotency/trace context 必须由系统注入，不由模型生成。

> Normative 接口契约（`BusinessToolService.fetch_context` 签名、`ToolCallContext` / `ToolResultV2`）见 `docs/contract-spec.md` §8.4 与 §12.5。本小节仅为叙述性概览。

### 8.5 Memory

当前依据：`AgentState` thread memory；参考 `memory-agent`、`langgraph-memory`。

目标职责：

- Working memory：当前 run/checkpoint state。
- Session memory：同一 thread 的 active slots、last intent、case summary、unresolved questions。
- Long-term memory：跨会话稳定偏好/商家模式，带 scope/source/confidence/TTL/review。
- Case memory：历史类似 case、处理结果、审批结果、outcome。

边界：

- Memory 是辅助上下文，不是政策依据。
- Long-term memory 不应每轮写入。
- Case memory 只能作为 precedent，不能覆盖当前 policy evidence。

### 8.6 Approvals / SLA / Policy

当前依据：`approval_gate.py`、`approvals.py`、`ApprovalRepository`、`rules/risk_rules.yaml`、`ApprovalRequest`/`ApprovalStep`。

目标职责：

- RiskPolicy：判断风险等级和 rule refs。
- ApprovalPolicy：判断是否审批、审批级别、审批角色、SLA。
- SLAService：审批超时、升级、提醒、自动转人工。
- ApprovalService：创建审批、处理 accept/edit/reject/respond/ignore、多级状态流转。

### 8.7 Actions / Executor / Compensation

当前依据：`execute_action.py`、`create_coupon_grant_draft.py`、`ActionDraftRepository`、`ActionDraft`。

目标职责：

- 生成 action draft。
- 校验 approval result。
- 根据 action type 选择 demo adapter 或 future external adapter。
- external mode 写 `ActionExecutionResult`；demo mode 只写 `draft_outcome`。
- 生成 rollback/compensation metadata。

当前只能创建 demo draft：创建草稿，不创建 `ActionExecutionResult`，也不真实发券/退款。

### 8.8 Observability / Replay

当前依据：`trace.py`、`trace_repo.py`、`traces.py`、`fastapi-observability`。

目标职责：

- 每个 graph node 建 span。
- 每次 tool/RAG/LLM/approval/action 建 span 或 event。
- 记录 run_id/thread_id/trace_id/tenant_id/user_id。
- Prometheus metrics：latency、error rate、no-evidence rate、approval interception rate、tool error rate、action draft success rate。
- Timeline replay：基于 persisted events 展示审计回放。

### 8.9 Persistence

当前依据：`src/db/models.py`、`src/repositories/*`。

目标职责：

- SQLAlchemy models。
- Tenant-scoped repositories。
- Postgres business data。
- pgvector policy chunks。
- AgentRun/AgentStep/Approval/Action audit data。
- 后续新增 Memory、ActionExecution、SLA event models。

---

## 22. 风险和取舍

- 分层会增加文件和 contract，但可以降低 graph node 直接耦合 repository/pgvector/demo DB 的风险。
- Memory 增强会带来隐私、成本和错误记忆风险，所以先做 session memory，再做长期/case memory。
- 多级审批和 SLA 会增加状态复杂度，但对企业售后场景必要。
- OTel/Grafana 全量部署会增加本地环境复杂度，所以先做 spans/metrics contract 和 DB timeline。
- Action executor 先保持 demo adapter，避免误接真实外部动作。
- Intent taxonomy 不宜过大，先 10 个以内，避免 eval 不稳定。

---

## 23. 明确不采用的参考模式和原因

1. 不采用 `langgraph/examples/customer-support/customer-support.ipynb` 的代码模式。

   原因：当前本地指定文件只有迁移说明，没有实现代码。不能编造 state/routing/tool/HITL 模式。

2. 不采用完全开放 ReAct 作为 MOCA 默认执行模式。

   原因：商家售后涉及退款、补偿、封禁/解封、工单关闭等高风险动作，必须 graph-controlled、node-level allowlist、approval/action executor 控制。

3. 不采用 `memory-agent` 的自由 memory upsert 策略。

   原因：MOCA 需要 tenant/user/merchant/thread/case scope、source refs、confidence、TTL、review/audit；不能让模型每轮自由写长期记忆。

4. 不采用 `langgraph-memory` 的 Pinecone/Fireworks 默认存储和模型栈。

   原因：MOCA 当前是 PostgreSQL + pgvector + DashScope/兼容接口，直接迁移会增加技术栈和部署复杂度。

5. 不采用 `agents-from-scratch-ts` 的 email domain prompt、tool set 和 `toolChoice: required` 执行假设。

   原因：MOCA 业务主线是商家运营与售后协同，不是个人 email assistant；高风险动作不能要求模型每轮必须调用工具。

6. 不直接采用 `agent-inbox` 的前端部署和 LangGraph Platform 假设。

   原因：MOCA 已有 FastAPI/React demo 和审批 API，应借鉴 HumanInterrupt/HumanResponse schema，而不是替换系统。

7. 不采用 `Human-in-the-Loop-Workflow-LangGraph` 的发布工具业务。

   原因：Bluesky 发布与 MOCA 业务无关。只借鉴 two-stage interrupt，不迁移 Tavily/OpenAI/publish flow。

8. 不采用 `full-stack-fastapi-template` 的 SQLModel/Users/Items 模型。

   原因：MOCA 已使用 SQLAlchemy、现有 tenant/business/agent models。只借鉴工程组织、deps、settings、tests、Docker 思路。

9. 不直接采用 `fastapi-observability` 的完整 Docker Compose 和 Loki logging driver。

   原因：MOCA 当前应先做观测 contract 和最小 instrumentation，避免把部署复杂度提前引入。

---

## 24. 结论

MOCA 应保留当前 LangGraph 主流程和 FastAPI/Postgres/pgvector 技术栈，以目标架构边界为优先、并保留可验证 rollback 的方式推进架构边界（不是 minimal-patch migration，见 Refactor Principle F1）：先把 Knowledge 和 Business Tools 从 `agent/tools` 语义中抬成 service facade，再补 Memory、Approval/SLA、ActionExecutor、Observability/Replay。

最终架构不是“更多节点”本身，而是让每个节点只编排独立能力层：

```text
Input -> Intent -> Memory -> Business Context -> Knowledge Evidence -> Recommendation -> Risk/Approval -> Action -> Response -> Memory Write -> Replay
```

这条线能服务 MOCA 的业务主线：商家运营与售后协同 Agent，既能安全演示，也为真实企业系统接入保留清晰替换边界。
