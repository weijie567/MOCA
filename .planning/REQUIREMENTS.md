# Requirements: MOCA

**Defined:** 2026-05-09
**Core Value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution.

> **Note:** ARCHITECTURE.md + ROADMAP.md are the current source of truth for implementation decisions.
> Research documents (.planning/research/) are historical references only and do not participate in execution decisions.

## v1 Requirements

### Agent Core

- [ ] **AGNT-01**: Agent 能识别用户意图，并路由到对应处理流程，包括规则问答、退款排障、补偿建议、审批请求
- [ ] **AGNT-02**: Agent 基于 LangGraph 状态机编排 happy path 流程，包含：接收请求、意图识别、加载业务上下文、检索规则证据、生成处理建议、风险判断、最终响应节点
- [ ] **AGNT-02a**: Agent 图包含审批中断节点（approval interrupt via `interrupt()`）和执行节点（executor），在高风险动作时中断等待人工决策后恢复执行
- [ ] **AGNT-03**: Agent 能通过结构化工具调用获取订单、退款单、工单数据
- [ ] **AGNT-04**: Agent 能检索知识库，并在回答中引用具体 doc_id、chunk_id 和规则段落摘要
- [ ] **AGNT-05**: Agent 支持同一 thread 内上下文保持（via LangGraph checkpointer），多轮对话中记住 order_id、refund_case_id、ticket_id、已检索证据和上一次处理结论；不支持跨 session 记忆
- [ ] **AGNT-06**: Agent 输出结构化执行轨迹（execution trace），记录经过的图节点、工具调用、证据引用、风险判断和审批状态；不输出模型私有推理链（禁用 chain-of-thought 术语，统一为 decision/evidence/action trace）
- [ ] **AGNT-07**: Agent 支持 SSE 流式响应，逐步展示当前阶段，例如"读取订单""检索规则""判断风险""等待审批"
- [ ] **AGNT-08**: Agent 在证据不足时必须拒绝生成确定性结论，并返回"缺少哪些信息 / 建议下一步补充什么"

### RAG & Knowledge Base

- [x] **RAG-01**: 系统支持导入退款规则、补偿规则、客服 SOP、商家 FAQ 等中文模拟知识文档（15-30 篇）
- [x] **RAG-02**: 系统支持文档切块、embedding 生成、pgvector 入库和检索
- [x] **RAG-03**: 每个知识 chunk 必须包含 doc_id、chunk_id、title、section、text、doc_type、risk_level、effective_date 等元数据
- [x] **RAG-04**: 检索时支持基于 tenant_id、doc_type、risk_level 的元数据过滤
- [ ] **RAG-05**: Agent 回答必须包含 evidence 列表，不能只给自然语言结论
- [x] **RAG-06**: 当检索结果低于置信阈值时，Agent 必须触发 no-evidence fallback，不允许编造规则
- [x] **RAG-07**: Citation validator 必须二次校验 LLM 输出的 doc_id/chunk_id 确实存在于检索结果中

### Tool Calling

- [ ] **TOOL-01**: 系统提供订单查询工具 get_order
- [ ] **TOOL-02**: 系统提供退款单查询工具 get_refund_case
- [ ] **TOOL-03**: 系统提供工单历史查询工具 get_ticket_history
- [ ] **TOOL-04**: 系统提供补偿券草稿工具 create_coupon_grant_draft
- [ ] **TOOL-05**: 系统提供审批单创建工具 create_approval_request
- [ ] **TOOL-06**: 所有工具必须有明确的输入 schema 和输出 schema
- [ ] **TOOL-07**: 所有工具调用必须记录 tool_call_id、run_id、tenant_id、user_id、latency_ms、status 和 error_code
- [ ] **TOOL-08**: 所有写操作必须支持 idempotency_key，避免重复执行
- [ ] **TOOL-09**: 高风险写操作不能由模型直接执行，必须先进入审批流程

### Approval & Safety

- [ ] **SAFE-01**: 系统能自动判定动作风险等级（低/中/高），基于 rules/risk_rules.yaml 配置
- [ ] **SAFE-02**: 高风险动作必须自动触发审批，LangGraph 图执行通过 `interrupt()` 中断并等待人工决策
- [ ] **SAFE-03**: 审批人可以批准或驳回审批请求
- [ ] **SAFE-04**: 审批通过后，Agent 能通过 `Command(resume=...)` 恢复执行
- [ ] **SAFE-05**: 审批驳回后，Agent 必须停止执行高风险动作，并返回驳回原因
- [ ] **SAFE-06**: 每次运行必须产生完整审计日志（via LangGraph callback），可按 run_id 查询和回放
- [ ] **SAFE-07**: 风险阈值、角色权限和审批规则必须通过配置文件管理（rules/risk_rules.yaml），不硬编码
- [ ] **SAFE-08**: 所有工具调用必须进行权限校验（repository 层 + tool 层双重检查），防止越权读取或执行

### Infrastructure

- [ ] **INFR-01**: Docker Compose 一键启动核心服务，包括 Postgres、Redis、API；healthcheck 确保启动顺序正确
- [ ] **INFR-02**: 种子脚本生成真实感中文模拟数据（80+ 订单、30+ 退款、15+ 知识文档、12+ 用户）
- [ ] **INFR-03**: JWT + OAuth2 scopes 实现角色权限控制，至少支持商家运营、平台客服、风险审核员、运营主管、系统管理员
- [ ] **INFR-04**: 系统为每次 Agent 执行生成 run_id、trace_id 和 step_id
- [ ] **INFR-05**: 系统记录基础可观测性数据，包括 latency_ms、token_usage、cost、error_code、tool_call_status
- [x] **INFR-06**: 文档摄取和评估任务通过 CLI 脚本或 FastAPI BackgroundTasks 执行，不引入独立任务队列
- [ ] **INFR-07**: 评估框架支持 golden set 自动评分，并生成 JSON / Markdown 报告
- [ ] **INFR-08**: CI 运行 lint + 单元测试；集成测试和评估 smoke test 提供本地运行脚本，不强制 CI 通过
- [ ] **INFR-09**: LLM/DB/工具调用三层 timeout + graceful degradation；LLM 超时返回 fallback 而非崩溃

### Frontend

- [ ] **FRNT-01**: 对话界面支持提交退款 / 订单问题，并展示带证据引用的回答
- [ ] **FRNT-02**: 审批界面展示待审批列表，支持批准和驳回操作
- [ ] **FRNT-03**: 执行步骤面板展示 Agent 当前阶段、已调用工具、引用证据和审批状态
- [ ] **FRNT-04**: 前端不要求实现复杂图节点动画；图节点高亮和边流转作为 v1.1 增强功能

### Data Model

- [ ] **DATA-01**: 系统包含 tenants、users、roles、user_roles、merchants 表
- [ ] **DATA-02**: 系统包含 orders、refund_cases、tickets 表
- [ ] **DATA-03**: 系统包含 policy_documents、policy_chunks 表
- [ ] **DATA-04**: 系统包含 agent_runs、agent_steps 表
- [ ] **DATA-05**: 系统包含 approval_requests、approval_steps 表
- [ ] **DATA-06**: 系统包含 audit_logs、llm_usage_events 表
- [ ] **DATA-07**: 所有核心业务表必须包含 tenant_id
- [ ] **DATA-08**: MVP 阶段使用应用层 tenant_id 过滤，生产化版本应升级为 PostgreSQL Row-Level Security

### Evaluation

- [x] **EVAL-01**: golden set 至少包含规则问答、退款排障、补偿建议、审批触发、证据不足五类样本（25-40 条）
- [x] **EVAL-02**: 系统评估 RAG Hit@5
- [ ] **EVAL-03**: 系统评估证据引用准确率
- [ ] **EVAL-04**: 系统评估工具选择准确率
- [ ] **EVAL-05**: 系统评估高风险动作拦截率
- [ ] **EVAL-06**: 系统评估任务完成率
- [ ] **EVAL-07**: 系统评估平均延迟和 token 成本
- [ ] **EVAL-08**: 高风险动作拦截率必须达到 100%

## v2 Requirements

### Observability & Monitoring

- **OBS-01**: OTel + Prometheus + Grafana 完整可观测性
- **OBS-02**: 按 run_id 回放完整执行链路的 UI
- **OBS-03**: Token 成本 dashboard

### Advanced Features

- **ADV-01**: 图执行路径可视化（节点高亮、边流转动画）
- **ADV-02**: 多 Agent 协作模式（Planner + Retriever + Executor）
- **ADV-03**: MCP Server 暴露工具和资源
- **ADV-04**: 商家长期画像记忆（跨 session）
- **ADV-05**: 第二场景：创作者申诉与规则咨询

### Production Hardening

- **PROD-01**: PostgreSQL Row-Level Security 替代应用层过滤
- **PROD-02**: Kubernetes 部署配置
- **PROD-03**: k6 压测脚本与 SLO 阈值断言
- **PROD-04**: 灰度发布策略

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real payment/refund execution | All tools are simulated; no real money movement |
| Real SMS/email sending | Simulated notification tool only |
| Mobile app | Web-first portfolio project |
| Fine-tuning models | Use prompt engineering + RAG |
| Multi-language i18n | Chinese demo data, English README only |
| Real-time chat/WebSocket | SSE sufficient for streaming |
| Document upload UI | CLI ingestion script sufficient for MVP |
| Complex analytics dashboard | Basic metrics in API response sufficient |
| Cross-session memory | Same-thread only via checkpointer; cross-session is v2 |
| Chain-of-thought output | Expose decision/evidence/action trace only; no raw LLM reasoning |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGNT-01 | 3 | Not started |
| AGNT-02 | 3 | Not started |
| AGNT-02a | 4 | Not started |
| AGNT-03 | 3 | Not started |
| AGNT-04 | 3 | Not started |
| AGNT-05 | 3 | Not started |
| AGNT-06 | 3 | Not started |
| AGNT-07 | 5 | Not started |
| AGNT-08 | 3 | Not started |
| RAG-01 | 2 | Complete |
| RAG-02 | 2 | Complete |
| RAG-03 | 2 | Complete |
| RAG-04 | 2 | Complete |
| RAG-05 | 3 | Not started |
| RAG-06 | 2 | Complete |
| RAG-07 | 2 | Complete |
| TOOL-01 | 1 | Not started |
| TOOL-02 | 1 | Not started |
| TOOL-03 | 1 | Not started |
| TOOL-04 | 4 | Not started |
| TOOL-05 | 4 | Not started |
| TOOL-06 | 1 | Not started |
| TOOL-07 | 1 | Not started |
| TOOL-08 | 1 | Not started |
| TOOL-09 | 4 | Not started |
| SAFE-01 | 4 | Not started |
| SAFE-02 | 4 | Not started |
| SAFE-03 | 4 | Not started |
| SAFE-04 | 4 | Not started |
| SAFE-05 | 4 | Not started |
| SAFE-06 | 3 | Not started |
| SAFE-07 | 4 | Not started |
| SAFE-08 | 3 | Not started |
| INFR-01 | 1 | Not started |
| INFR-02 | 1 | Not started |
| INFR-03 | 1 | Not started |
| INFR-04 | 1 | Not started |
| INFR-05 | 1 | Not started |
| INFR-06 | 2 | Complete |
| INFR-07 | 6 | Not started |
| INFR-08 | 6 | Not started |
| INFR-09 | 3 | Not started |
| FRNT-01 | 5 | Not started |
| FRNT-02 | 5 | Not started |
| FRNT-03 | 5 | Not started |
| FRNT-04 | 5 | Not started |
| DATA-01 | 1 | Not started |
| DATA-02 | 1 | Not started |
| DATA-03 | 1 | Not started |
| DATA-04 | 1 | Not started |
| DATA-05 | 1 | Not started |
| DATA-06 | 1 | Not started |
| DATA-07 | 1 | Not started |
| DATA-08 | 1 | Not started |
| EVAL-01 | 2 | Complete |
| EVAL-02 | 2 | Complete |
| EVAL-03 | 6 | Not started |
| EVAL-04 | 6 | Not started |
| EVAL-05 | 4 | Not started |
| EVAL-06 | 6 | Not started |
| EVAL-07 | 6 | Not started |
| EVAL-08 | 4 | Not started |

**Coverage:**
- v1 requirements: 62 total (AGNT-02a, RAG-07, INFR-09 added)
- Mapped to phases: 62
- Unmapped: 0

**Phase distribution:**
- Phase 1 (Foundation): 19
- Phase 2 (RAG): 9
- Phase 3 (LangGraph Core): 11
- Phase 4 (Approval): 12
- Phase 5 (Frontend + SSE): 5
- Phase 6 (Eval + Polish): 6

---
*Requirements defined: 2026-05-09*
*Last updated: 2026-05-09 after design convergence review — AGNT-02 split, traceability synced to 6-phase, Phase 3 scope reduced, terminology unified*
