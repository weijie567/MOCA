# Phase 5: Frontend & SSE - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 05-frontend-sse
**Areas discussed:** 前端框架选型, SSE 流式实现, 页面布局与导航, 演示登录体验, API 命名和契约, SSE event schema, 审批 API 接入, 错误和超时 UX, 验收标准

---

## 前端框架选型

### 框架选择

| Option | Description | Selected |
|--------|-------------|----------|
| React + Vite | 轻量、快速搭建、无 SSR 开销。对于纯 SPA 演示项目足够。 | ✓ |
| Next.js | 内置路由、SSR、API routes。但本项目后端已有 FastAPI，SSR 无实际价值。 | |
| 你决定 | 框架选型由 Claude 决定。 | |

**User's choice:** React + Vite
**Notes:** 5 天工期内最高效，打包后可用 nginx 或 API 服务静态托管。

### 样式方案

| Option | Description | Selected |
|--------|-------------|----------|
| Tailwind CSS | 轻量 utility-first CSS，无组件库依赖。 | |
| Ant Design | 现成组件多，开箱即用，但打包较大，视觉风格固定。 | |
| shadcn/ui + Tailwind | Tailwind 基础上的无样式组件库，提供常用组件但不强制视觉风格。 | ✓ |

**User's choice:** shadcn/ui + Tailwind
**Notes:** 保留 Tailwind 灵活性，提供常用 UI 组件加快开发，适合做单页多面板 Agent 控制台。用户明确列出需要的组件：Button, Card, Badge, Tabs, Dialog, Textarea, ScrollArea, Toast, Select, Separator, Skeleton。状态管理先用 hooks/context，后续如需再考虑 Zustand。

---

## SSE 流式实现

### 实现方式

| Option | Description | Selected |
|--------|-------------|----------|
| 新建独立 SSE endpoint | 不改造现有 POST /chat，新增流式体验。 | ✓ |
| 改造现有 chat 为流式 | 把现有 POST /chat 改为 text/event-stream。破坏性变更。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 新建独立 SSE endpoint
**Notes:** 采用 run-based 设计：POST 创建 run → GET events 消费 SSE。保留原有同步接口不变。

### 事件粒度

| Option | Description | Selected |
|--------|-------------|----------|
| 节点级事件 | 每个图节点开始/结束时推送事件，与现有 trace_steps 结构对齐。 | ✓ |
| 节点+工具+证据级 | 除节点级外还推送工具调用结果、证据检索结果等细粒度数据。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 节点级事件
**Notes:** step_completed 允许带轻量 summary（evidence_count, tool_name, risk_level）。完整详情通过独立 API 获取。

### 后端架构

| Option | Description | Selected |
|--------|-------------|----------|
| 同步流（请求内执行+推送） | Agent 在 SSE 请求生命周期内执行并 yield 事件。简单直接。 | ✓ |
| 解耦流（后台任务+事件队列） | POST 只创建 run，后台任务执行 Agent，SSE 从 Redis pub/sub 读取。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 同步流
**Notes:** 不引入 Redis pub/sub、后台 worker。断线后通过 GET /agent-runs/{run_id} 恢复状态，不做事件回放。

### SSE 鉴权

| Option | Description | Selected |
|--------|-------------|----------|
| fetch-event-source + Bearer | 前端用 @microsoft/fetch-event-source 携带 Authorization Header。 | ✓ |
| URL query token | SSE endpoint 接受 URL 参数中的短期 token。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** fetch-event-source + Bearer
**Notes:** 与现有 JWT 体系一致，不把 token 放进 URL。后端复用 get_current_user。

---

## 页面布局与导航

### 布局方案

| Option | Description | Selected |
|--------|-------------|----------|
| 三栏并排 | 左侧对话、中间 Timeline、右侧详情。三栏始终可见。 | ✓ |
| 双栏 + Tab | 左侧对话为主，右侧合并 Timeline + 详情（用 Tab 切换）。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 三栏并排
**Notes:** 左栏 30%（Chat）、中栏 35%（Timeline）、右栏 35%（Details Tabs）。右栏内部使用 Tabs：Evidence, Approval, Trace, Run Info。优先服务宽屏面试演示场景。

### 审批交互位置

| Option | Description | Selected |
|--------|-------------|----------|
| 内嵌在右栏 Approval Tab | approval_required 时右栏自动切换到 Approval Tab，审批人在同一页面操作。 | ✓ |
| 独立审批页面 | 单独的审批列表页，展示所有待审批项。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 内嵌在右栏 Approval Tab
**Notes:** 演示时不需要跳转页面，流程连续。后续版本再增加独立 Approval Queue 页面。

---

## 演示登录体验

| Option | Description | Selected |
|--------|-------------|----------|
| 角色切换器（无登录页） | 页面顶部下拉菜单切换角色，自动获取对应 demo token。 | ✓ |
| 简化登录页 + 预填账号 | 有登录页但预填好 demo 账号，点击即登录。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 角色切换器（无登录页）
**Notes:** 三个角色：Support Agent / Approver / Admin。切换后自动换 demo token。UI 标注 Demo Mode。

---

## API 命名和契约

| Option | Description | Selected |
|--------|-------------|----------|
| /api/v1/agent-runs | 独立资源路径，run 作为一等资源。 | ✓ |
| /api/v1/agent/runs | 放在现有 /agent 前缀下。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** /api/v1/agent-runs
**Notes:** 语义清晰，与现有 /agent/chat 并存不冲突。

---

## SSE Event Schema

| Option | Description | Selected |
|--------|-------------|----------|
| 固定字段 + 可选 payload | 所有事件统一基础字段，payload 可选。 | ✓ |
| 按 event_type 分别定义 schema | 每种事件有不同 schema。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 固定字段 + 可选 payload
**Notes:** 固定字段：event_type, run_id, step_index, node_name, status, message, timestamp, payload。event_type 限制在 6 种。status 限制在 7 种。

---

## 审批 API 接入

| Option | Description | Selected |
|--------|-------------|----------|
| 复用现有审批 API + 轮询结果 | 前端调用 POST /approvals/{id}/decide，审批后轮询 run 状态。 | ✓ |
| 新建 run-scoped 审批 endpoint | 新建 POST /agent-runs/{run_id}/approval 封装审批+恢复。 | |
| 你决定 | Claude 决定。 | |

**User's choice:** 复用现有审批 API + 轮询结果
**Notes:** approval_required event payload 包含 approval_id。审批后轮询 GET /agent-runs/{run_id} 直到终态。

---

## 错误和超时 UX

| Option | Description | Selected |
|--------|-------------|----------|
| 统一 error 状态 + 友好提示 | 所有异常统一展示为 error。 | |
| 分类错误状态 + 分别处理 | 区分 failed/disconnected/rejected/degraded，分别展示。 | ✓ |
| 你决定 | Claude 决定。 | |

**User's choice:** 分类错误状态 + 分别处理
**Notes:** 7 种前端状态：running, completed, waiting_approval, rejected, degraded, failed, disconnected。每种有对应的 Timeline 和 Chat 展示方式。

---

## 验收标准

确认 6 项验收条件：
1. 能从前端创建一次 Agent Run
2. 能通过 SSE 在 Timeline 中看到节点级执行进度
3. 能触发 approval_required 状态
4. 能通过角色切换器切换到审批人角色并完成 Approve / Reject
5. 审批后能看到最终 final_response
6. 右侧详情区能查看 evidence / trace 摘要

**Demo case:** 客服请求"请给 ORD-2024-001 补偿 600 元"，系统触发高风险审批，切换到审批人后批准或拒绝，最后客服侧能看到最终处理结果。

---

## Claude's Discretion

- Loading skeleton and animation details
- Exact color scheme and typography
- Internal component file structure
- Docker Compose frontend service configuration
- Polling interval for post-approval state recovery

## Deferred Ideas

- Independent approval queue page — future version
- SSE event replay — production upgrade
- Redis pub/sub decoupled architecture — production upgrade
- Fine-grained events (tool_called, evidence_retrieved) — v1.1
- Mobile responsive layout — not Phase 5 priority
- Graph node animations — FRNT-04 defers to v1.1
