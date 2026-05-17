# Phase 5: Frontend & SSE - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 18
**Analogs found:** 12 / 18 (6 frontend files have no backend analog — new stack)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/api/routers/agent_runs.py` | router | request-response + streaming | `src/api/routers/agent.py` | exact |
| `src/api/schemas/agent_runs.py` | schema | — | `src/api/schemas/agent.py` | role-match |
| `src/api/main.py` (modify) | config | — | `src/api/main.py` | self |
| `docker-compose.yml` (modify) | config | — | `docker-compose.yml` | self |
| `frontend/src/lib/api.ts` | utility | request-response | `src/api/routers/auth.py` (client side) | partial |
| `frontend/src/lib/sse.ts` | utility | streaming | no analog | none |
| `frontend/src/types/events.ts` | model | — | `src/api/schemas/agent.py` | partial |
| `frontend/src/hooks/useAuth.ts` | hook | request-response | `src/api/routers/auth.py` (demo-token) | partial |
| `frontend/src/hooks/useAgentRun.ts` | hook | streaming + CRUD | no analog | none |
| `frontend/src/App.tsx` | component | event-driven | no analog | none |
| `frontend/src/components/layout/AppLayout.tsx` | component | — | no analog | none |
| `frontend/src/components/layout/TopBar.tsx` | component | — | no analog | none |
| `frontend/src/components/layout/RoleSwitcher.tsx` | component | request-response | no analog | none |
| `frontend/src/components/chat/ChatPanel.tsx` | component | event-driven | no analog | none |
| `frontend/src/components/timeline/AgentTimeline.tsx` | component | event-driven | no analog | none |
| `frontend/src/components/timeline/TimelineStep.tsx` | component | — | no analog | none |
| `frontend/src/components/details/DetailsPanel.tsx` | component | CRUD | no analog | none |
| `frontend/src/components/details/ApprovalTab.tsx` | component | request-response | `src/api/routers/approvals.py` (contract) | partial |

---

## Pattern Assignments

### `src/api/routers/agent_runs.py` (router, request-response + streaming)

**Analog:** `src/api/routers/agent.py` + `src/api/routers/traces.py`

**Imports pattern** (`src/api/routers/agent.py` lines 1-21):
```python
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import build_trace_summary, write_agent_run, write_agent_steps
from src.api.schemas.common import ApiResponse, ErrorDetail, INTERNAL_ERROR
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session
from src.repositories.approval_repo import ApprovalRepository
```

Additional SSE import (new dependency, no existing analog):
```python
from sse_starlette.sse import EventSourceResponse
```

**Auth pattern** (`src/api/routers/agent.py` lines 27-33):
```python
@router.post("/chat", response_model=ApiResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
```
Apply same `Security(get_current_user, scopes=["agent:chat"])` to all new endpoints in `agent_runs.py`.

**input_state + config construction pattern** (`src/api/routers/agent.py` lines 40-52):
```python
input_state = {
    "user_query": body.query,
    "thread_id": body.thread_id,
    "tenant_id": str(user.tenant_id),
    "user_id": str(user.id),
    "role": user.role,
}
config = {
    "configurable": {
        "thread_id": _checkpoint_thread_id(user=user, thread_id=body.thread_id),
        "session": session,
    }
}
```
The new SSE endpoint must construct identical `input_state` and `config` before calling `graph.astream()`.

**GraphInterrupt handling pattern** (`src/api/routers/agent.py` lines 54-67, 98-108):
```python
try:
    final_state = await graph.ainvoke(input_state, config)
except Exception as exc:
    if _is_graph_interrupt(exc):
        return await _handle_interrupt(exc, ...)

if isinstance(final_state, dict) and "__interrupt__" in final_state:
    return await _handle_interrupt(final_state, ...)
```
For SSE, replace `ainvoke` with `astream`. Catch `GraphInterrupt` inside the async generator, emit `approval_required` event, then close the generator. The interrupt data extraction helper `_extract_interrupt_data()` (lines 240-258) can be reused directly.

**Persistence pattern** (`src/api/routers/agent.py` lines 118-136):
```python
try:
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=body.thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query=body.query,
        final_status=final_status,
        final_response=final_response_text,
        started_at=started_at,
        completed_at=completed_at,
        total_latency_ms=total_ms,
        total_tokens=total_tokens,
    )
    await write_agent_steps(session, run_id=run_id, trace_steps=trace_steps)
    await session.commit()
except Exception:
    await session.rollback()
```
`POST /agent-runs` creates the run record with `final_status="pending"` immediately. The SSE generator updates it to `"running"` then `"completed"/"interrupted"/"error"` as execution progresses.

**ApiResponse wrapper pattern** (`src/api/routers/traces.py` lines 72-76):
```python
return ApiResponse(
    success=True,
    data=trace_data.model_dump(mode="json"),
    trace_id=getattr(request.state, "trace_id", None),
)
```
All non-streaming endpoints (`POST /agent-runs`, `GET /agent-runs/{run_id}`, `GET /agent-runs/{run_id}/evidence`) return `ApiResponse`. The SSE endpoint returns `EventSourceResponse` directly — no `ApiResponse` wrapper.

**404 / UUID parse pattern** (`src/api/routers/traces.py` lines 79-83):
```python
def _parse_run_id(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"}) from exc
```
Copy this helper verbatim into `agent_runs.py`.

**Ownership + role check pattern** (`src/api/routers/traces.py` lines 35-37):
```python
if run.user_id != user.id and user.role not in SUPERVISOR_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```
Apply same check in `GET /agent-runs/{run_id}` and `GET /agent-runs/{run_id}/events`.

**checkpoint_thread_id helper** (`src/api/routers/agent.py` lines 149-150):
```python
def _checkpoint_thread_id(*, user: User, thread_id: str) -> str:
    return f"{user.tenant_id}:{user.id}:{thread_id}"
```
Copy into `agent_runs.py` — same format required for `graph.astream()` config.

**Error handling pattern** (`src/api/routers/agent.py` lines 68-96):
```python
total_ms = round((time.perf_counter() - t0) * 1000)
completed_at = datetime.now(timezone.utc)
fallback_response = "系统处理出现问题，请稍后重试或联系人工客服。"
# ... persist error run
return ApiResponse(
    success=False,
    data=...,
    error=ErrorDetail(code=INTERNAL_ERROR, message=fallback_response),
    trace_id=request.state.trace_id,
)
```
For SSE, errors inside the generator must yield an `error` event before closing:
```python
yield {"event": "error", "data": json.dumps({"event_type": "error", "run_id": run_id, "message": "..."})}
```

---

### `src/api/schemas/agent_runs.py` (schema, —)

**Analog:** `src/api/schemas/agent.py`

**Pydantic pattern** (`src/api/schemas/agent.py` lines 1-30):
```python
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="...")
    thread_id: str = Field(min_length=1, max_length=128, description="...")


class TraceSummary(BaseModel):
    run_id: str
    intent: str
    ...
```
New schemas to define in `agent_runs.py`:
- `CreateRunRequest` — `query: str`, `thread_id: str` (same fields as `ChatRequest`)
- `RunStatusResponse` — `run_id`, `final_status`, `started_at`, `completed_at`, `final_response`
- `SseEvent` — matches D-09 schema: `event_type`, `run_id`, `step_index`, `node_name`, `status`, `message`, `timestamp`, `payload`

---

### `src/api/main.py` (modify — router registration)

**Self-analog** (`src/api/main.py` lines 101-108):
```python
app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth")
app.include_router(orders.router, prefix=f"{settings.api_v1_prefix}/orders")
app.include_router(agent_router.router, prefix=f"{settings.api_v1_prefix}/agent")
app.include_router(approvals.router, prefix=f"{settings.api_v1_prefix}/approvals")
app.include_router(traces.router, prefix=f"{settings.api_v1_prefix}/agent-runs")
```
Add one line after the `traces.router` line:
```python
app.include_router(agent_runs_router.router, prefix=f"{settings.api_v1_prefix}/agent-runs")
```
Both `traces.router` and `agent_runs_router.router` share the same prefix — FastAPI merges routes from both.

---

### `docker-compose.yml` (modify — add frontend service)

**Self-analog** (`docker-compose.yml` lines 28-47, `api` service):
```yaml
api:
  build: .
  ports:
    - "8000:8000"
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  environment:
    DATABASE_URL: postgresql+asyncpg://moca:moca_dev@postgres:5432/moca
    REDIS_URL: redis://redis:6379/0
    JWT_SECRET: dev-secret-change-in-prod-32-bytes-min
    ENABLE_DEMO_AUTH: "true"
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s
```
New `frontend` service follows same structure: `build`, `ports`, `depends_on` (api with `service_healthy`), `environment` (VITE_API_URL). No healthcheck required for dev mode.

---

### `frontend/src/lib/api.ts` (utility, request-response)

**Analog:** `src/api/routers/auth.py` demo-token endpoint (lines 70-90) — defines the contract this client calls.

No TypeScript analog exists in the codebase. Pattern from RESEARCH.md:
```typescript
// Fetch wrapper that injects Authorization header from stored token
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const res = await fetch(`${import.meta.env.VITE_API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err?.error?.code, err?.error?.message);
  }
  return res.json();
}
```
The `ApiResponse` envelope from `src/api/schemas/common.py` (lines 23-27) defines the response shape:
```typescript
interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: { code: string; message: string; details: Record<string, unknown> } | null;
  trace_id: string | null;
}
```

---

### `frontend/src/lib/sse.ts` (utility, streaming)

**No analog in codebase.** New pattern required.

Key contract from CONTEXT.md D-11 and RESEARCH.md §7:
- Use `@microsoft/fetch-event-source` to send `Authorization: Bearer <token>` header
- On `onerror`: switch to polling mode instead of retrying SSE
- On `onmessage`: parse `event.data` as JSON matching D-09 schema

```typescript
import { fetchEventSource } from "@microsoft/fetch-event-source";

export async function connectSse(
  url: string,
  token: string,
  onEvent: (event: SseEvent) => void,
  onDisconnect: () => void,
): Promise<() => void> {
  const ctrl = new AbortController();
  fetchEventSource(url, {
    headers: { Authorization: `Bearer ${token}` },
    signal: ctrl.signal,
    onmessage(msg) {
      try {
        onEvent(JSON.parse(msg.data) as SseEvent);
      } catch { /* ignore malformed */ }
    },
    onerror() {
      onDisconnect();
      throw new Error("sse_disconnect"); // stops retry
    },
  });
  return () => ctrl.abort();
}
```

---

### `frontend/src/types/events.ts` (model, —)

**Partial analog:** `src/api/schemas/agent.py` TraceSummary (lines 17-25) and D-09 schema.

TypeScript types mirror the Python Pydantic schemas. D-09 defines the canonical SSE event shape:
```typescript
export type SseEventType =
  | "run_started"
  | "step_started"
  | "step_completed"
  | "approval_required"
  | "final_response"
  | "error";

export interface SseEvent {
  event_type: SseEventType;
  run_id: string;
  step_index?: number;
  node_name?: string;
  status?: string;
  message?: string;
  timestamp: string;
  payload?: {
    evidence_count?: number;
    tool_name?: string;
    risk_level?: string;
    short_summary?: string;
    approval_id?: string;
    proposed_action?: Record<string, unknown>;
    final_response?: string;
    error_code?: string;
    error_message?: string;
  };
}

// Frontend run status (D-23)
export type RunStatus =
  | "idle"
  | "running"
  | "completed"
  | "waiting_approval"
  | "rejected"
  | "degraded"
  | "failed"
  | "disconnected";
```

---

### `frontend/src/hooks/useAuth.ts` (hook, request-response)

**Partial analog:** `src/api/routers/auth.py` demo-token endpoint (lines 70-90).

The hook calls `POST /api/v1/auth/demo-token` with `{ username }` and stores the returned JWT. Demo usernames map to roles per D-20/D-21:

```typescript
const DEMO_USERS: Record<DemoRole, string> = {
  support_agent: "agent_alice",   // verify against seed data
  approver: "manager_bob",
  admin: "admin_carol",
};

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<DemoRole>("support_agent");

  async function switchRole(newRole: DemoRole) {
    const res = await apiFetch<{ access_token: string }>(
      "/api/v1/auth/demo-token",
      { method: "POST", body: JSON.stringify({ username: DEMO_USERS[newRole] }) }
    );
    setToken(res.access_token);
    setRole(newRole);
  }

  return { token, role, switchRole };
}
```
Note: `TokenResponse.access_token` is the field name from `src/api/schemas/auth.py` — confirm before implementing.

---

### `frontend/src/hooks/useAgentRun.ts` (hook, streaming + CRUD)

**No analog in codebase.** Orchestrates the full run lifecycle.

State machine mirrors D-23 status types. Key transitions:
1. `POST /api/v1/agent-runs` → get `run_id`
2. Connect SSE `GET /api/v1/agent-runs/{run_id}/events`
3. On `approval_required` event → set status `waiting_approval`, surface `approval_id`
4. On SSE disconnect → set status `disconnected`, call `GET /api/v1/agent-runs/{run_id}` for recovery
5. After approval decision → poll `GET /api/v1/agent-runs/{run_id}` at 2s until terminal state

```typescript
export function useAgentRun(token: string | null) {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [steps, setSteps] = useState<SseEvent[]>([]);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const [finalResponse, setFinalResponse] = useState<string | null>(null);

  async function startRun(query: string, threadId: string) { ... }
  async function recoverRun(id: string) { ... }
  function startApprovalPolling(id: string) { ... }

  return { runId, status, steps, approvalId, finalResponse, startRun };
}
```

---

### `frontend/src/components/details/ApprovalTab.tsx` (component, request-response)

**Partial analog:** `src/api/routers/approvals.py` decide endpoint (lines 25-116) — defines the API contract this component calls.

The component calls `POST /api/v1/approvals/{approval_id}/decide` with `{ decision: "approve" | "reject", reason: string }`. Key contract details from `approvals.py`:
- Requires `approvals:review` scope → only `approver`/`admin` roles can submit
- Returns `ApiResponse` with updated approval object
- 403 if `user.role not in {"admin", "manager"}` (line 33)
- 409 if expired (line 52) or already decided (line 63)

The component must disable the approve/reject buttons when the current demo role is `support_agent`.

---

## Shared Patterns

### Authentication (apply to all backend endpoints in `agent_runs.py`)

**Source:** `src/auth/permissions.py` lines 33-66, `src/api/routers/agent.py` line 32

```python
user: User = Security(get_current_user, scopes=["agent:chat"])
```
- `get_current_user` validates JWT, checks `is_active`, enforces scopes
- Tenant isolation is automatic: `user.tenant_id` is always available after auth
- All DB queries must filter by `user.tenant_id` — see `traces.py` line 31: `repo.get_run(run_uuid, user.tenant_id)`

### Error Response Format (apply to all backend endpoints)

**Source:** `src/api/schemas/common.py` lines 17-27, `src/api/main.py` lines 37-43

```python
# All error responses use this shape:
ApiResponse(
    success=False,
    error=ErrorDetail(code="NOT_FOUND", message="Run not found"),
    trace_id=getattr(request.state, "trace_id", None),
)
# HTTPException detail must be a dict with "code" and "message" keys:
raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
```

### DB Session Dependency (apply to all backend endpoints)

**Source:** `src/api/routers/traces.py` line 26, `src/db/session.py`

```python
session: AsyncSession = Depends(get_session)
```
Always use `Depends(get_session)` — never instantiate sessions directly. Commit at the end of write operations; rollback on exception.

### trace_id Propagation (apply to all backend endpoints)

**Source:** `src/api/main.py` lines 50-52, all routers

```python
trace_id=getattr(request.state, "trace_id", None)
```
`request.state.trace_id` is set by the `trace_middleware` in `main.py`. Always pass it through to `ApiResponse`.

### graph Access Pattern (apply to SSE endpoint)

**Source:** `src/api/routers/agent.py` line 35, `src/api/routers/approvals.py` line 68

```python
graph = request.app.state.agent_graph
```
The compiled LangGraph instance lives on `app.state.agent_graph`, initialized in the `lifespan` context manager (`main.py` lines 29-34). Access it via `request.app.state.agent_graph` — never import or instantiate it directly in a router.

### Frontend Token Storage (apply to all frontend API calls)

**Source:** `src/api/routers/auth.py` lines 70-90 (contract), CONTEXT.md D-11/D-21

All API requests and SSE connections must include `Authorization: Bearer <token>`. Token is obtained from `POST /api/v1/auth/demo-token`. Store in React state (not localStorage) for demo simplicity — token is ephemeral per session.

---

## No Analog Found

Files with no close match in the codebase (use RESEARCH.md patterns):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `frontend/src/lib/sse.ts` | utility | streaming | No SSE client code exists; use `@microsoft/fetch-event-source` pattern from RESEARCH.md §1 |
| `frontend/src/hooks/useAgentRun.ts` | hook | streaming + CRUD | No React hooks exist; new state machine pattern |
| `frontend/src/App.tsx` | component | event-driven | No frontend exists; three-column layout per D-16 |
| `frontend/src/components/layout/AppLayout.tsx` | component | — | No frontend exists |
| `frontend/src/components/layout/TopBar.tsx` | component | — | No frontend exists |
| `frontend/src/components/layout/RoleSwitcher.tsx` | component | request-response | No frontend exists; calls demo-token API |
| `frontend/src/components/chat/ChatPanel.tsx` | component | event-driven | No frontend exists |
| `frontend/src/components/timeline/AgentTimeline.tsx` | component | event-driven | No frontend exists; node→message map from RESEARCH.md §3 |
| `frontend/src/components/timeline/TimelineStep.tsx` | component | — | No frontend exists |
| `frontend/src/components/details/DetailsPanel.tsx` | component | CRUD | No frontend exists |

---

## Metadata

**Analog search scope:** `src/api/routers/`, `src/api/schemas/`, `src/auth/`, `src/agent/`, `docker-compose.yml`
**Files scanned:** 12 backend files
**Pattern extraction date:** 2026-05-17
