---
phase: 05-frontend-sse
reviewed: 2026-05-17T09:21:54Z
depth: standard
files_reviewed: 35
files_reviewed_list:
  - docker-compose.yml
  - frontend/Dockerfile
  - frontend/components.json
  - frontend/index.html
  - frontend/package.json
  - frontend/src/App.tsx
  - frontend/src/components/chat/ChatInput.tsx
  - frontend/src/components/chat/ChatPanel.tsx
  - frontend/src/components/chat/MessageList.tsx
  - frontend/src/components/details/ApprovalTab.tsx
  - frontend/src/components/details/DetailsPanel.tsx
  - frontend/src/components/details/EvidenceTab.tsx
  - frontend/src/components/details/TraceTab.tsx
  - frontend/src/components/layout/TopBar.tsx
  - frontend/src/components/timeline/AgentTimeline.tsx
  - frontend/src/components/timeline/TimelineStep.tsx
  - frontend/src/components/ui/badge.tsx
  - frontend/src/components/ui/card.tsx
  - frontend/src/components/ui/dialog.tsx
  - frontend/src/components/ui/scroll-area.tsx
  - frontend/src/components/ui/tabs.tsx
  - frontend/src/components/ui/textarea.tsx
  - frontend/src/hooks/useAgentRun.ts
  - frontend/src/hooks/useAuth.ts
  - frontend/src/index.css
  - frontend/src/lib/api.ts
  - frontend/src/lib/sse.ts
  - frontend/src/types/events.ts
  - frontend/tailwind.config.ts
  - frontend/tsconfig.app.json
  - frontend/tsconfig.json
  - pyproject.toml
  - src/api/main.py
  - src/api/routers/agent_runs.py
  - src/api/schemas/agent_runs.py
findings:
  critical: 1
  warning: 4
  info: 1
  total: 6
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-17T09:21:54Z
**Depth:** standard
**Files Reviewed:** 35
**Status:** issues_found

## Summary

Reviewed the Phase 05 frontend/SSE changes, excluding generated lock files per review rules. The main concern is that the SSE execution endpoint is not idempotent or guarded against duplicate/concurrent stream connections, which can re-run the same agent request and duplicate side effects. The frontend also cannot authenticate against the seeded demo users as written, the Compose frontend cannot proxy API calls to the backend container, and network/non-JSON API failures leave the UI in an unhandled async state.

Verification run: `npm run lint` in `frontend/` failed with 8 ESLint errors.

## Critical Issues

### CR-01: SSE stream endpoint can execute the same run multiple times

**File:** `src/api/routers/agent_runs.py:102`

**Issue:** `GET /{run_id}/events` starts graph execution for any visible run without checking or atomically transitioning from `pending` to `running`. A client retry, double-opened tab, or second caller with access to the run can enter `_event_generator`, call `_mark_run_running`, and invoke `graph.astream` again for the same persisted run. For low-risk flows this can duplicate action execution; for high-risk flows it can create duplicate approval requests and trace rows.

**Fix:**
```python
@router.get("/{run_id}/events")
async def stream_agent_run_events(...):
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)
    _ensure_can_view_run(run, user=user)

    if run.final_status != "pending":
        raise HTTPException(
            status_code=409,
            detail={"code": "RUN_ALREADY_STARTED", "message": "Run event stream has already been started"},
        )

    run.final_status = "running"
    await session.commit()
    return EventSourceResponse(_event_generator(...))
```

For production correctness, make the transition atomic with a row lock or conditional update, and do not perform the same transition again inside `_event_generator`.

## Warnings

### WR-01: Demo frontend requests tokens for users that do not exist

**File:** `frontend/src/hooks/useAuth.ts:6`

**Issue:** The frontend maps roles to `demo-agent`, `demo-manager`, and `demo-admin`, but the demo seed data uses `cs_zhang`, `mgr_li`/`mgr_zhou`, and `admin_user`. `/api/v1/auth/demo-token` returns 404 for the configured usernames, so `App.tsx` never stores a real JWT and API/SSE calls continue with the invalid `demo-token:*` placeholder set by `useAuth`.

**Fix:** Align the role map with seeded users and avoid installing non-JWT placeholders as bearer tokens.

```ts
const ROLE_USERS: Record<DemoRole, string> = {
  support_agent: 'cs_zhang',
  manager: 'mgr_li',
  admin: 'admin_user',
}

// Remove the effect that calls setAuthToken(`demo-token:${...}`).
```

### WR-02: Docker frontend cannot reach the API backend

**File:** `docker-compose.yml:60`

**Issue:** Compose sets `VITE_API_URL=http://api:8000`, but `frontend/src/lib/api.ts` hardcodes `API_BASE = '/api/v1'` and the Vite proxy is configured outside the reviewed diff to target `http://localhost:8000`. Inside the frontend container, `localhost:8000` is the frontend container, not the API service, so browser calls to `/api/v1` through the dev server fail in Docker.

**Fix:** Either make the Vite proxy use the Compose service name, or make the client honor `VITE_API_URL`.

```ts
const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : '/api/v1'
```

If using a dev-server proxy in Compose, set the proxy target to `http://api:8000`.

### WR-03: API helper throws on network or non-JSON responses and strands UI state

**File:** `frontend/src/lib/api.ts:34`

**Issue:** `apiFetch` always calls `response.json()` and has no `try/catch`. Network failures, Docker proxy failures, 502s, or HTML error pages reject instead of returning `ApiResult`. Callers such as `submitQuery` await `createRun` without catching, so the UI can remain stuck in `running` with no error message.

**Fix:**
```ts
export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
    const body = await response.json().catch(() => null)
    if (!response.ok || !body?.success) {
      return { success: false, data: undefined as T, error: body?.error ?? { code: 'HTTP_ERROR', message: 'Request failed' } }
    }
    return body as ApiResult<T>
  } catch (error) {
    return { success: false, data: undefined as T, error: { code: 'NETWORK_ERROR', message: error instanceof Error ? error.message : 'Network error' } }
  }
}
```

### WR-04: Approving as the submitting user fails in the default demo flow

**File:** `frontend/src/hooks/useAgentRun.ts:195`

**Issue:** The approval API rejects self-approval, but the frontend exposes approve/reject for the same current role/session that submitted the run. If a manager/admin creates a run that requires approval and then clicks approve in the same UI, `POST /approvals/{id}/decide` returns `SELF_APPROVAL`. The UI presents this as a generic failure instead of requiring a different approver identity.

**Fix:** Track the run submitter separately from the selected approver role, disable approval actions for the submitting user, or switch to a separate reviewer token before calling `decideApproval`.

```ts
if (currentUsername === submittedByUsername) {
  setState((current) => ({ ...current, error: '审批人不能审批自己提交的请求' }))
  return
}
```

## Info

### IN-01: Frontend lint currently fails

**File:** `frontend/src/components/details/DetailsPanel.tsx:42`

**Issue:** `npm run lint` fails on 8 errors: synchronous `setState` inside effects, empty interfaces equivalent to supertypes, unused destructured parameters in `Tabs`, and `require()` in `tailwind.config.ts`.

**Fix:** Resolve the lint violations or adjust the configured lint rules intentionally. For example, convert empty interfaces to type aliases, avoid unused destructuring in `Tabs`, and replace `require('tailwindcss-animate')` with an ESM import.

---

_Reviewed: 2026-05-17T09:21:54Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
