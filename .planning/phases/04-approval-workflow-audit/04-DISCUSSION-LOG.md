# Phase 4: Approval Workflow & Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 04-approval-workflow-audit
**Areas discussed:** Latency 诊断策略, Approval 中断机制, 写操作工具设计, 审计链与回放

---

## Latency 诊断策略

| Option | Description | Selected |
|--------|-------------|----------|
| CLI 脚本 + JSON 报告 | 每个节点记录 started_at/completed_at/latency_ms，输出 JSON 报告到 stdout 或文件 | |
| 扩展现有 trace_steps（推荐） | 在 agent_steps 表增加 latency_ms 字段，通过已有持久化机制存储，API 可查询 | ✓ |
| OTel spans + 外部 UI | 引入 OpenTelemetry span 给每个节点打 trace，用 Jaeger/Zipkin 可视化 | |

**User's choice:** 扩展现有 trace_steps
**Notes:** 节点级 + provider 级拆分。agent_steps.latency_ms 记录节点总耗时，provider_latency_ms 记录 LLM provider 调用耗时，retry_count 记录重试次数。预留 metrics_json 存放轻量诊断指标。不引入完整 OTel，不记录每次 DB 查询耗时。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 节点级 + provider 级拆分（推荐） | latency_ms + provider_latency_ms + retry_count + metrics_json | ✓ |
| 仅节点级总耗时 | 只记录每个节点总耗时，不区分内部分层 | |

**User's choice:** 节点级 + provider 级拆分
**Notes:** 完整 prompt 和敏感业务数据不进入 latency metrics。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 诊断脚本 + 结论报告（推荐） | 按 run_id 分析，输出 JSON 报告，自动标记最慢节点和瓶颈原因 | ✓ |
| 仅采集，不分析 | 只记录数据，人工看 agent_steps 表判断 | |

**User's choice:** 诊断脚本 + 结论报告
**Notes:** CI 不依赖真实 LLM API，支持 demo/mock scenario。真实 provider 多次诊断作为本地手动命令。

---

## Approval 中断机制

| Option | Description | Selected |
|--------|-------------|----------|
| 独立 approval_gate 节点（推荐） | assess_risk_and_approval 判定后，下一个节点 approval_gate 调用 interrupt() | ✓ |
| 在现有节点内 interrupt | 直接在 assess_risk_and_approval 内部调用 interrupt() | |
| 条件边 + 分叉路径 | 用条件边分叉：high_risk 走 interrupt 分支 | |

**User's choice:** 独立 approval_gate 节点
**Notes:** 风险判断和人工审批中断职责分离，更方便测试、审计、回放和后续扩展。

---

| Option | Description | Selected |
|--------|-------------|----------|
| REST API 审批端点（推荐） | POST /api/v1/approvals/{id}/decide，审批人登录后调用 | ✓ |
| 通过 chat 线程消息审批 | 审批人在 agent chat 线程发送"批准/驳回"消息 | |

**User's choice:** REST API 审批端点
**Notes:** resume payload 为结构化对象。幂等性规则详细定义。reject 是正常业务结果。权限边界：supervisor/admin/approval_manager。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 24h 超时自动过期（推荐） | expires_at = created_at + 24h，超时后 status → expired | ✓ |
| 无超时，永久等待 | 审批请求永久等待直到人工处理 | |
| 可配置超时（写入 YAML） | 超时时间写在 risk_rules.yaml 中 | |

**User's choice:** 24h 超时自动过期
**Notes:** 超时后 agent_run → expired，图不恢复。后续需重新发起。

---

## 写操作工具设计

| Option | Description | Selected |
|--------|-------------|----------|
| 新增 execute_action 节点（推荐） | approve 后进入独立节点执行写操作，再进 final_response | ✓ |
| 在 final_response 内执行写操作 | final_response 内部调用写工具 | |
| 图外异步执行 | approve 后图结束，写操作由外部服务异步执行 | |

**User's choice:** 新增 execute_action 节点
**Notes:** 详细条件边拓扑设计。create_coupon_grant_draft 是 draft 写入不是直接发券。幂等性通过 idempotency_key 保证。审批状态和 action 执行状态分开管理。

---

## 审计链与回放

| Option | Description | Selected |
|--------|-------------|----------|
| 复用现有表 + 新增审批表（推荐） | agent_runs + agent_steps + 新增 approval_requests + approval_steps + action_drafts | ✓ |
| 独立 audit_logs 事件流表 | 新增完整事件流表记录所有事件 | |

**User's choice:** 复用现有表 + 新增审批表
**Notes:** 避免 agent_steps 和 audit_logs 重复记录。后续可增加轻量 audit_logs 表只记录安全审计事件。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 单个 trace API 端点（推荐） | GET /api/v1/agent-runs/{run_id}/trace 返回完整链路 + 统一 timeline | ✓ |
| 多个独立查询端点 | 分别查询 steps、approvals、action_drafts，前端自己拼装 | |

**User's choice:** 单个 trace API 端点
**Notes:** 返回两层结构：原始结构化数据 + 统一 timeline。后端负责拼装排序，前端只负责展示。权限校验：同 tenant + 角色权限。

---

## Claude's Discretion

- LangGraph interrupt()/Command(resume=...) 具体 API 用法
- 条件边具体实现方式
- SQLAlchemy model 字段类型
- 诊断脚本瓶颈判断阈值
- Alembic migration 实现

## Deferred Ideas

- 多级审批
- 审批通知系统（Slack/企业微信/邮件）
- 审批前端页面（Phase 5）
- chat 消息审批
- 完整 audit_logs 事件流表
- OTel + Prometheus + Grafana
- 真正发放优惠券（Phase 4 只创建 draft）
