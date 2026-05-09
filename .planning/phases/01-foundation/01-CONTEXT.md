# Phase 1: Foundation - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Docker Compose 启动所有基础服务（Postgres + pgvector, Redis, FastAPI），数据库 schema 完整（业务基础表），FastAPI 提供带真实鉴权的 CRUD 端点，seed data 灌入 6 个固定高质量中文业务场景，repository layer 建立。

</domain>

<decisions>
## Implementation Decisions

### D-01: Seed 数据策略
- 6 个固定高质量业务场景，手写 fixtures，不用 Faker
- 场景覆盖：未发货退款、签收后破损、虚拟商品不支持退款、超售后期、高金额需审批、多次异常退款风险提示
- 全中文业务数据（商家名、商品名、退款原因）
- 商家名示例：星河数码旗舰店、知味零食铺、青木家居生活馆、云舟在线课程、南山户外用品店
- 商品名示例：蓝牙降噪耳机 Pro、儿童学习平板 S3、即食鸡胸肉组合装、人体工学办公椅、Python 数据分析入门课程
- 退款原因示例：未按约定时间发货、收到商品破损、商品与描述不符、不想要了、课程内容不符合预期、重复下单
- Seed 必须确定性可重置：`uv run python scripts/seed_demo.py --reset`
- PK 保持 UUID（用 UUID v5 从确定性 namespace 生成），可读标识放 `order_no`/`refund_case_no` 等业务字段
- Phase 2/3 再考虑 Faker 批量生成补充数据量

### D-02: Demo 鉴权体验
- 优先企业级实践，不依赖预生成固定 token
- 实现真实 login 流程：POST /api/v1/auth/login（username + hashed password）
- JWT 包含：sub, username, role, tenant_id, exp
- get_current_user 作为 FastAPI dependency 解析 Bearer token
- require_roles([...]) 依赖实现基础 RBAC
- POST /api/v1/auth/demo-token 仅限 ENABLE_DEMO_AUTH=true 环境
- GET /api/v1/auth/me 验证当前 token
- 4 个角色：support, manager, merchant, admin
- 测试覆盖：login success/failure, missing token, invalid token, expired token, role-based denial

### D-03: Python 工具链
- 包管理器：uv
- Python 版本：3.12
- Linter + Formatter：ruff（同时做 lint 和 format）
- 测试框架：pytest（Claude's Discretion 选择具体插件）

### D-04: API 语言策略
- 接口路径、字段名、错误码、错误 message 全部英文
- 业务数据内容（商家名、商品名、退款原因、工单摘要、知识文档）中文
- 中文展示留给前端 i18n，后端不做多语言

### D-05: 数据库边界
- Phase 1 只建业务基础表 + audit_logs：
  - tenants, users, roles, user_roles, merchants
  - orders, refund_cases, tickets
  - policy_documents, policy_chunks
  - audit_logs
- Phase 1 不建 Agent runtime 表（agent_runs, agent_steps, approval_requests, llm_usage_events）
- Agent runtime 表留到 Phase 3（LangGraph Core）再建
- 原因：不要提前把 Agent workflow 的表设计死

### D-06: 多租户策略
- 所有核心表加 tenant_id
- Repository 查询必须带 tenant scope：current_user.tenant_id → query filter
- 不做：tenant 管理后台、tenant 注册、跨租户配置
- 这是"权限隔离"的工程意识体现

### D-07: RBAC 粒度
- Phase 1 用固定角色枚举 + dependency-based RBAC
- support: 查看订单/退款单/工单
- manager: support 权限 + 审批高风险退款
- merchant: 查看与自己店铺相关的订单/退款/工单
- admin: 全部查看 + seed/debug/admin API
- 不做：permissions 表、role_permissions 表、后台动态配置权限

### D-08: 审计日志
- Phase 1 做轻量版：记录关键 API 操作
- 字段：id, tenant_id, user_id, role, action, resource_type, resource_id, trace_id, created_at
- 不记录完整 request/response body
- Phase 4 再扩展为完整审计链路

### D-09: Docker Compose
- Phase 1 包含：api (FastAPI + Uvicorn) + postgres (16 + pgvector) + redis (7-alpine)
- Redis Phase 1 只启动，暂不使用（或仅做简单 rate limiting）
- 不加：celery, prometheus, grafana, otel collector
- 启动方式：`docker compose up --build`
- 本地开发也支持：`uv run fastapi dev src/api/main.py`

### D-10: 统一错误格式
- 统一响应结构：`{"success": bool, "data": {...}, "error": {...}}`
- 错误结构：`{"code": "FORBIDDEN", "message": "Insufficient permissions", "details": {...}}`
- 所有响应包含 trace_id
- 预定义错误码：UNAUTHORIZED, FORBIDDEN, VALIDATION_ERROR, ORDER_NOT_FOUND, REFUND_CASE_NOT_FOUND, TICKET_NOT_FOUND, POLICY_DOCUMENT_NOT_FOUND, TENANT_SCOPE_VIOLATION, INTERNAL_ERROR

### D-11: Tool 返回结构
- Phase 1 的 read tools（get_order, get_refund_case, get_ticket_history）通过 API 端点暴露
- tool call 日志写入 audit_logs（含 trace_id），Phase 3 再建完整 agent_runs/agent_steps
- 具体返回字段由 Claude's Discretion 决定

### D-12: 测试门槛
- Phase 1 完成标准必须通过以下测试：
  - health check
  - login success / login failure
  - demo-token disabled in non-dev env
  - auth/me success
  - protected API without token returns 401
  - role forbidden returns 403
  - seed orders query succeeds
  - tenant isolation check
  - unified error response format

### D-13: Seed 重置
- 提供 `uv run python scripts/seed_demo.py --reset` 命令
- 行为：清空 demo tenant 数据 → 重新插入用户 → 重新插入 6 个场景 → 重新插入 policy documents/chunks
- 所有 demo ID 稳定可读（业务字段层面）

### Claude's Discretion
- pytest 具体插件选择（pytest-asyncio, httpx 等）
- Alembic migration 的具体组织方式
- Repository base class 的具体实现模式
- Docker 镜像的具体 base image 选择
- Tool 返回的具体字段设计

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `.planning/ARCHITECTURE.md` — Design Contract (single source of truth), DB schema, directory structure, state enumerations, MVP scope contract

### Requirements
- `.planning/REQUIREMENTS.md` — Full requirement list with IDs (DATA-*, INFR-*, TOOL-*)

### Roadmap
- `.planning/ROADMAP.md` — Phase 1 success criteria and requirement mapping

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — Phase 1 establishes all patterns

### Integration Points
- None — this is the first phase

</code_context>

<specifics>
## Specific Ideas

- 商家名风格参考美团/饿了么/淘宝店铺命名
- 退款场景要能支撑后续 Agent 的 evidence-based reasoning（每个场景有明确的规则依据）
- 鉴权设计要能支撑后续 Phase 4 的审批流（manager 角色审批高风险操作）

</specifics>

<deferred>
## Deferred Ideas

### Phase 2/3 待建表
- agent_runs, agent_steps — Phase 3 (LangGraph Core)
- approval_requests, approval_steps — Phase 4 (Approval Workflow)
- llm_usage_events — Phase 3

### Phase 2+ 待做功能
- Redis 实际使用（session cache, rate limiting）— Phase 2+
- 完整审计链路（request/response body, tool call 级别）— Phase 4
- 动态 RBAC（permissions 表, role_permissions 表）— v2
- Faker 批量数据生成 — Phase 2/3
- 前端 i18n — Phase 5

### 已确认不做
- tenant 管理后台
- Celery / async workers
- Prometheus / Grafana / OTel collector
- 跨租户配置

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-05-09*
