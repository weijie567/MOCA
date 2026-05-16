# Phase 4: Approval Workflow & Audit - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

高风险动作触发审批中断（`interrupt()`），人工决策后恢复或终止执行，写操作工具上线，完整审计链可查询可回放。前置要求：先诊断 agent 各节点 latency，再规划优化策略。

</domain>

<decisions>
## Implementation Decisions

### D-01: Latency 诊断策略（Phase 4 前置计划）
- **D-01a:** 扩展现有 trace_steps，在 agent_steps 表增加 `latency_ms`（节点总耗时）、`provider_latency_ms`（LLM provider 调用耗时）、`retry_count` 字段
- **D-01b:** 预留 `metrics_json` 字段存放轻量诊断指标：model、provider、prompt_tokens、completion_tokens、context_chars
- **D-01c:** 不引入完整 OTel span，不记录每次 DB 查询耗时，不把完整 prompt 或敏感数据写入 metrics
- **D-01d:** 提供轻量诊断脚本 `scripts/diagnose_latency.py`，按 run_id 分析已有 agent_run，输出 JSON 报告
- **D-01e:** 报告内容：每节点 latency_ms、provider_latency_ms、retry_count、prompt_tokens、context_chars，自动标记最慢节点和疑似瓶颈原因
- **D-01f:** 支持 demo/mock diagnostic scenario（CI 可用），真实 provider 多次诊断作为本地手动命令
- **D-01g:** 诊断完成后再规划优化策略，候选策略包括：classify/extract/risk 使用更小模型、合并相邻 LLM 节点、no-evidence 分支跳过后续 LLM、streaming/progress status、合理 timeout 和 graceful degradation
- **D-01h:** 保持 Phase 3 correctness gates 不变：evidence-cited answer、no-evidence fallback、same-thread evidence gating、trace/audit persistence

### D-02: Approval 中断机制
- **D-02a:** 新增独立 `approval_gate` 节点，与 `assess_risk_and_approval` 职责分离
- **D-02b:** `assess_risk_and_approval` 只负责判断 risk_level、approval_required、approval_reason、proposed_action，不直接 interrupt
- **D-02c:** `approval_gate` 负责：创建 approval_request → 写入审计日志 → 调用 `interrupt()` 暂停图执行 → 等待外部 `Command(resume=structured_decision_payload)` 恢复
- **D-02d:** 审批人通过 REST API 提交决策：`POST /api/v1/approvals/{approval_id}/decide`，请求体 `{"decision": "approve"|"reject", "reason": "..."}`
- **D-02e:** resume payload 为结构化对象：`{approval_id, decision, reason, decided_by, decided_at}`，approval_gate 恢复后写回 state.approval_result
- **D-02f:** reject 是正常业务结果，不是系统错误。reject 后流程继续进入 final_response，说明"审批未通过，不执行该动作"
- **D-02g:** 默认 24h 审批超时。approval_request 创建时写入 `expires_at = created_at + 24h`。超时后 status → expired，agent_run → expired，图不恢复
- **D-02h:** 权限边界：只有 supervisor / admin / approval_manager 角色可审批。审批人不能审批自己发起的高风险请求

### D-03: 写操作工具设计
- **D-03a:** 新增独立 `execute_action` 节点，审批通过后进入，final_response 不承担写操作
- **D-03b:** 图拓扑条件边：
  - `assess_risk_and_approval` → no action needed → `final_response`
  - `assess_risk_and_approval` → action allowed without approval → `execute_action` → `final_response`
  - `assess_risk_and_approval` → approval required → `approval_gate` → approved → `execute_action` → `final_response`
  - `approval_gate` → rejected → `final_response`
- **D-03c:** `execute_action` 职责：读取 state.proposed_action → 检查 approval_result → 调用 create_coupon_grant_draft → 写入 action_result + agent_steps + audit → 失败时记录 error 不伪装成功
- **D-03d:** `create_coupon_grant_draft` 是 draft 写入，不是直接发券。Agent 只能创建补偿草稿，真正发放留后续
- **D-03e:** 幂等性：`idempotency_key = run_id + approval_id + action_type + target_id`。相同 key 已创建过 draft 时不重复创建，返回已有结果，记录为 idempotent_reused
- **D-03f:** Phase 4 新增写工具：`create_coupon_grant_draft`、`create_approval_request`。遵循 Phase 3 工具统一格式 `{"status": "success"|"error", "data": {}, "error": {...}}`

### D-04: 审计链与回放
- **D-04a:** 复用现有 agent_runs + agent_steps 作为 Agent 执行链事实来源，不新增完整事件流替代
- **D-04b:** 新增 `approval_requests` 表（run_id 关联）：status、requested_by、assigned_to、proposed_action、risk_rule_ref、expires_at、decision、reason、decided_by、decided_at
- **D-04c:** 新增 `approval_steps` 表（approval_request_id 关联）：记录审批生命周期事件 created / approved / rejected / expired / resumed
- **D-04d:** 新增 `action_drafts` 表：id、run_id、approval_request_id、idempotency_key、action_type、status（draft_created / failed / cancelled）、payload、created_by_agent_run、created_at
- **D-04e:** 回放 API：`GET /api/v1/agent-runs/{run_id}/trace` 返回完整执行链路，包含 run 基本信息 + steps + approvals + action_drafts + 统一 timeline
- **D-04f:** timeline 按时间排序，每条包含 type（agent_step / approval_request / approval_decision / action_draft）、time、title、status、detail
- **D-04g:** 权限校验：同 tenant + 普通用户看自己发起的 run + supervisor/admin 看审批相关 run
- **D-04h:** Phase 4 不做前端页面，但接口结构支持 Phase 5 前端步骤面板
- **D-04i:** Phase 4 暂不做完整 audit_logs 事件流表，后续如需安全审计事件可增加轻量表

### D-05: 状态机设计
- **D-05a:** `agent_runs.final_status`: running → interrupted → completed / failed / expired
  - interrupted: approval_gate 调用 interrupt() 后
  - completed: approve + execute_action 成功 / reject 后正常结束 / 无需审批正常结束
  - failed: execute_action 系统级失败（非业务拒绝）
  - expired: 审批超时未处理
- **D-05b:** `approval_requests.status`: pending → approved / rejected / expired / cancelled
  - pending: 创建后等待审批人决策
  - approved: 审批人批准
  - rejected: 审批人驳回（正常业务结果）
  - expired: 超过 expires_at 未处理
  - cancelled: 用户主动取消（预留，Phase 4 可不实现）
- **D-05c:** `approval_steps.event_type`: created / viewed / approved / rejected / expired / resumed
- **D-05d:** `action_drafts.status`: draft_created / failed / cancelled
- **D-05e:** `agent_steps.status`: running / completed / error / skipped
- **D-05f:** 关键原则：reject ≠ failed（业务拒绝是正常结果）；expired ≠ failed（业务超时不是系统错误）

### D-06: 失败与恢复策略
- **D-06a:** approve/reject 幂等性：
  - pending + approve → 成功
  - pending + reject → 成功
  - approved + approve → 幂等返回成功
  - approved + reject → 409 Conflict
  - rejected + reject → 幂等返回成功
  - rejected + approve → 409 Conflict
  - expired + any → 409 Conflict
- **D-06b:** 重复 resume：如果 approval_request 已非 pending 状态，不重复调用 Command(resume=...)
- **D-06c:** execute_action 重试：通过 idempotency_key 保证 create_coupon_grant_draft 不重复创建
- **D-06d:** 系统重启恢复：DB 中 interrupted run + pending approval 的状态持久化在 PostgresSaver checkpointer 中，重启后审批人仍可通过 REST API 提交决策并 resume 图执行
- **D-06e:** 超时处理：后台定时任务或 API 调用时检查 expires_at，过期的 approval_request 标记为 expired，关联 agent_run 标记为 expired

### D-07: 验收标准
- **D-07a:** Latency 诊断：每个节点记录 latency_ms + provider_latency_ms + retry_count，诊断脚本按 run_id 输出 JSON 报告并标记瓶颈
- **D-07b:** High-risk 场景触发 approval_gate interrupt，图执行暂停
- **D-07c:** REST API `POST /api/v1/approvals/{id}/decide` 可提交 approve/reject
- **D-07d:** approve 后进入 execute_action，成功创建 coupon_grant_draft
- **D-07e:** reject 后不执行写操作，final_response 说明审批被拒绝
- **D-07f:** expired 后不执行写操作，agent_run 标记为 expired
- **D-07g:** `GET /api/v1/agent-runs/{run_id}/trace` 返回完整执行链路 + timeline
- **D-07h:** 幂等性：重复 approve 返回成功，重复 execute_action 不创建重复 draft
- **D-07i:** CI 集成测试使用 mock LLM + mock tool，不依赖真实 DashScope API
- **D-07j:** 可选 live smoke test 验证真实 LLM 链路（本地手动运行）
- **D-07k:** 高风险动作拦截率 100%（EVAL-05, EVAL-08）

### Claude's Discretion
- LangGraph `interrupt()` 和 `Command(resume=...)` 的具体 API 用法
- approval_requests / approval_steps / action_drafts 的具体 SQLAlchemy model 字段类型
- 条件边的具体 LangGraph 实现方式（conditional_edges vs router function）
- 诊断脚本的具体输出格式和瓶颈判断阈值
- execute_action 节点内部的具体错误处理和 retry 逻辑
- Alembic migration 的具体实现

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Data Model
- `.planning/ARCHITECTURE.md` — Design Contract, DB schema, directory structure
- `src/db/models.py` — Existing model definitions (AgentRun, AgentStep)

### Requirements
- `.planning/REQUIREMENTS.md` — AGNT-02a, EVAL-05, EVAL-08, SAFE-01 to SAFE-05, SAFE-07, TOOL-04, TOOL-05, TOOL-09

### Prior Phase Context
- `.planning/phases/03-langgraph-core/03-CONTEXT.md` — Graph node design (D-04), state design (D-07), tool contract (D-08), error handling (D-10)
- `.planning/phases/01-foundation/01-CONTEXT.md` — DB schema, tenant_id scoping, error format

### Existing Code (Phase 4 builds on)
- `src/agent/graph.py` — Current linear graph topology (8 nodes, no conditional edges)
- `src/agent/nodes/assess_risk_and_approval.py` — Risk assessment node (Phase 3: label only)
- `src/agent/state.py` — AgentState TypedDict (persistent + ephemeral fields)
- `src/agent/trace.py` — Trace persistence helpers
- `rules/risk_rules.yaml` — Risk classification rules (HR-01/02/03, MR-01/02/03, LR-01)
- `src/agent/tools/` — Existing read-only tool wrappers (get_order, get_refund_case, get_ticket, search_policy)
- `src/auth/permissions.py` — Permission/scope definitions

### API Patterns
- `src/api/routers/` — Existing router patterns (agent chat endpoint)
- `src/api/deps.py` — Authentication dependency injection

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/nodes/assess_risk_and_approval.py`: 已有 `_deterministic_rule_match()` 和 `_load_risk_rules()`，Phase 4 复用风险判断逻辑
- `src/agent/trace.py`: 已有 trace persistence helpers，扩展支持 latency_ms 和 approval 事件
- `src/agent/tools/authz.py`: 已有工具层权限校验模式，写工具复用
- `rules/risk_rules.yaml`: 已定义 high_risk 规则，注释明确 "Phase 4: high_risk triggers interrupt()"
- `src/agent/state.py`: AgentState TypedDict 需扩展 approval_result、proposed_action、action_result 字段

### Established Patterns
- 每个节点返回 dict 更新 state（reducer 模式）
- trace_steps 列表追加模式
- _get_llm() 工厂函数模式
- 统一错误格式 `{"status": "success"|"error", "data": {}, "error": {...}}`
- SQLAlchemy 2.0 mapped_column + UUID PK + TimestampMixin
- uv + ruff + pytest toolchain

### Integration Points
- `src/agent/graph.py`: 需从线性 add_edge 改为条件边（approval_required 分支）
- `src/api/routers/`: 新增 approvals router（decide API + trace API）
- `src/db/models.py`: 新增 ApprovalRequest、ApprovalStep、ActionDraft models
- Alembic migration: 新增 approval_requests、approval_steps、action_drafts 表，扩展 agent_steps 表

</code_context>

<specifics>
## Specific Ideas

- 图拓扑变更：从线性 8 节点变为带条件边的 10 节点（新增 approval_gate + execute_action）
- 新增 API 端点：`POST /api/v1/approvals/{id}/decide`、`GET /api/v1/approvals/{id}`、`GET /api/v1/agent-runs/{run_id}/approvals`、`GET /api/v1/agent-runs/{run_id}/trace`
- 新增写工具：`create_coupon_grant_draft`、`create_approval_request`
- 诊断脚本命令：`uv run python scripts/diagnose_latency.py --run-id <uuid>`
- approval_requests.expires_at 默认 24h
- idempotency_key 格式：`{run_id}_{approval_id}_{action_type}_{target_id}`
- agent_runs.final_status 新增值：interrupted、expired

</specifics>

<deferred>
## Deferred Ideas

- 多级审批（Phase 4 只做单级）
- 审批通知系统（Slack/企业微信/邮件集成）
- 审批前端页面（Phase 5）
- chat 消息审批（通过对话线程审批）
- 完整 audit_logs 事件流表（后续安全审计增强）
- OTel + Prometheus + Grafana 完整可观测性
- 指数退避、熔断器、异步恢复
- 真正发放优惠券（Phase 4 只创建 draft）
- cancelled 状态实现（用户主动取消审批）

</deferred>

---

*Phase: 04-approval-workflow-audit*
*Context gathered: 2026-05-16*
