# Phase 5: Frontend & SSE - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Minimal frontend provides a complete demo experience with chat interface, approval operations, and execution step visibility. SSE streams progressive updates during Agent execution. No complex graph node animations.

</domain>

<decisions>
## Implementation Decisions

### Frontend framework
- **D-01:** React + Vite + TypeScript. No Next.js, no SSR.
- **D-02:** shadcn/ui + Tailwind CSS for styling. Components needed: Button, Card, Badge, Tabs, Dialog, Textarea, ScrollArea, Toast, Select, Separator, Skeleton.
- **D-03:** State management via React hooks/context. No Zustand or Redux unless complexity demands it later.
- **D-04:** Frontend lives in a new `frontend/` directory, separate from the Python backend.

### SSE streaming architecture
- **D-05:** New independent SSE endpoint. Existing `POST /api/v1/agent/chat` remains unchanged.
- **D-06:** Run-based design: `POST /api/v1/agent-runs` creates a run and returns `run_id`; `GET /api/v1/agent-runs/{run_id}/events` streams SSE events.
- **D-07:** Synchronous flow — Agent executes within the SSE request lifecycle (StreamingResponse yields events). No background tasks, no Redis pub/sub, no event queue.
- **D-08:** Node-level event granularity. Events: `run_started`, `step_started`, `step_completed`, `approval_required`, `final_response`, `error`.
- **D-09:** SSE event schema — fixed fields + optional payload:
  ```json
  {
    "event_type": "step_started",
    "run_id": "uuid",
    "step_index": 3,
    "node_name": "retrieve_policy",
    "status": "running",
    "message": "正在检索退款规则",
    "timestamp": "2026-05-17T12:00:00Z",
    "payload": { "evidence_count": 3, "risk_level": "medium" }
  }
  ```
- **D-10:** `step_completed` payload carries lightweight summary (evidence_count, tool_name, risk_level, short_summary). Full details via separate APIs.
- **D-11:** SSE auth via `@microsoft/fetch-event-source` + Authorization Bearer token. No URL query tokens. Backend reuses existing JWT/RBAC/tenant isolation.
- **D-12:** Disconnection strategy: no event replay. Frontend shows "连接中断" and calls `GET /agent-runs/{run_id}` to recover state. If run completed, show final_response. If still running, user can re-initiate.

### API design
- **D-13:** New resource path: `/api/v1/agent-runs`. Endpoints:
  - `POST /api/v1/agent-runs` — create run, return run_id
  - `GET /api/v1/agent-runs/{run_id}` — run status (for recovery/polling)
  - `GET /api/v1/agent-runs/{run_id}/events` — SSE stream
  - `GET /api/v1/agent-runs/{run_id}/trace` — full trace details
  - `GET /api/v1/agent-runs/{run_id}/evidence` — evidence used in run
- **D-14:** Approval uses existing `POST /api/v1/approvals/{approval_id}/decide`. No new approval endpoint.
- **D-15:** After approval, frontend polls `GET /api/v1/agent-runs/{run_id}` until run reaches terminal state (completed/failed/rejected/degraded).

### Page layout
- **D-16:** Three-column layout for desktop (optimized for wide-screen interview demos):
  - Left (30%): Chat input, message history, final response
  - Center (35%): Agent Timeline with SSE-driven step status
  - Right (35%): Details panel with internal Tabs (Evidence, Approval, Trace, Run Info)
- **D-17:** When `approval_required` event arrives, right panel auto-switches to Approval Tab.
- **D-18:** Single-page app, no multi-page routing. No mobile optimization in Phase 5.
- **D-19:** Responsive fallback for narrower screens: collapse to two columns (Chat + Timeline/Details Tab). Not a priority.

### Demo login experience
- **D-20:** Top-bar Demo Role Switcher (Support Agent / Approver / Admin). No login page.
- **D-21:** Switching role auto-fetches corresponding demo JWT. All subsequent API and SSE requests use that token.
- **D-22:** UI clearly labels "Demo Mode" with current role indicator.

### Error and status UX
- **D-23:** Frontend status types: `running`, `completed`, `waiting_approval`, `rejected`, `degraded`, `failed`, `disconnected`.
- **D-24:** LLM/tool failure → Timeline node shows `failed`, Chat shows friendly retry prompt.
- **D-25:** SSE disconnect → shows "连接中断，正在恢复状态", calls recovery API.
- **D-26:** Approval rejected → Timeline shows `rejected`, Chat shows rejection reason.
- **D-27:** Insufficient evidence → shows `degraded`, Chat explains no definitive conclusion.
- **D-28:** Right panel Trace tab preserves detailed error_message, error_code, node_name, timestamp for interview explanation.

### Claude's Discretion
- Loading skeleton and animation details
- Exact color scheme and typography within shadcn/ui defaults
- Internal component file structure within `frontend/`
- Docker Compose integration for frontend service (nginx or dev server)
- Exact polling interval for post-approval state recovery

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend API contracts
- `src/api/routers/agent.py` — Existing POST /agent/chat endpoint, interrupt handling, trace persistence pattern
- `src/api/routers/approvals.py` — Existing approval decide endpoint, role checks, resume logic
- `src/api/routers/traces.py` — Existing trace API pattern
- `src/api/schemas/agent.py` — ChatRequest, ChatResponse, TraceSummary schemas

### Agent execution
- `src/agent/` — LangGraph graph nodes, state structure, trace_steps format
- `rules/risk_rules.yaml` — Risk classification rules that trigger approval

### Auth and permissions
- `src/auth/permissions.py` — get_current_user, OAuth2 scopes, role checks
- `src/api/routers/auth.py` — Demo auth token generation

### Infrastructure
- `docker-compose.yml` — Existing services (postgres, redis, api). Frontend service to be added.

### Requirements
- `.planning/REQUIREMENTS.md` §Frontend — FRNT-01 through FRNT-04, AGNT-07

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `POST /api/v1/approvals/{approval_id}/decide` — fully functional approval endpoint with role checks, resume logic
- `GET /api/v1/agent-runs/{run_id}/trace` — existing trace endpoint pattern to extend
- `build_trace_summary()` in `src/agent/trace.py` — generates trace summary from final_state
- `write_agent_run()` / `write_agent_steps()` — persistence helpers for run/step records
- `ENABLE_DEMO_AUTH=true` — existing demo auth mode in docker-compose

### Established Patterns
- FastAPI routers with `Security(get_current_user, scopes=[...])` for auth
- `ApiResponse` wrapper for all API responses
- `AsyncSession` dependency injection via `get_session`
- LangGraph `graph.ainvoke()` for synchronous execution; needs adaptation to `graph.astream()` or callback-based streaming for SSE

### Integration Points
- New `src/api/routers/agent_runs.py` router to be added to FastAPI app
- Frontend service to be added to `docker-compose.yml`
- Frontend consumes existing approval API + new agent-runs API

</code_context>

<specifics>
## Specific Ideas

- "Agent Workflow Console" — not a generic admin dashboard, but a purpose-built demo for showing Agent execution process
- Demo flow: 客服请求"请给 ORD-2024-001 补偿 600 元" → Agent 分析 → 风险判断 → 审批中断 → 人工审批 → Agent 完成响应
- Timeline should show Chinese status messages: "正在识别意图", "正在读取订单信息", "正在检索退款规则", "正在生成处理建议", "需要审批", "已完成"
- Visual style: clean, modern, similar to IDE layout. Not a heavy enterprise admin panel.

</specifics>

<deferred>
## Deferred Ideas

- Independent approval queue page (list all pending approvals) — future version
- SSE event replay / persistent event log — production upgrade
- Redis pub/sub decoupled architecture — production upgrade
- Fine-grained events (tool_called, tool_completed, evidence_retrieved) — v1.1
- Mobile responsive layout — not Phase 5 priority
- Graph node visualization with animations — explicitly FRNT-04 defers this to v1.1
- Multi-consumer SSE subscription — production upgrade

</deferred>

---

*Phase: 05-frontend-sse*
*Context gathered: 2026-05-17*
