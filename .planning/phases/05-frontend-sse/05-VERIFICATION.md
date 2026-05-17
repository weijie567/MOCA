---
phase: 05-frontend-sse
verified: 2026-05-17T09:27:58Z
status: gaps_found
score: 22/29 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Chat interface submits refund/order questions and approval operations work in the default demo frontend"
    status: failed
    reason: "The frontend asks /api/v1/auth/demo-token for demo-agent/demo-manager/demo-admin, but seeded demo users are cs_zhang, mgr_li, and admin_user. The failed token exchange leaves the placeholder demo-token:* bearer token installed, so protected chat, SSE, evidence, trace, and approval calls fail in the default demo."
    artifacts:
      - path: "frontend/src/hooks/useAuth.ts"
        issue: "ROLE_USERS maps to usernames that do not exist in seed data and installs placeholder bearer tokens."
      - path: "frontend/src/App.tsx"
        issue: "getDemoToken failure is ignored; no error is surfaced and the invalid placeholder token remains."
      - path: "scripts/seed_demo.py"
        issue: "Seeded users are admin_user, cs_zhang, mgr_li, and mgr_zhou."
    missing:
      - "Map support_agent/manager/admin to seeded usernames."
      - "Stop installing demo-token:* placeholders as Authorization bearer tokens."
      - "Surface demo-token fetch failures before enabling protected run actions."
  - truth: "Approval interface shows pending approval requests with approve/reject buttons; actions update in real time"
    status: partial
    reason: "ApprovalTab can decide the current run approval when an approval_required event is present, but the frontend never calls GET /api/v1/approvals and does not render a pending approvals list required by FRNT-02 and the roadmap success criterion."
    artifacts:
      - path: "frontend/src/components/details/ApprovalTab.tsx"
        issue: "Renders only one approval from the current SSE event; no pending list data source."
      - path: "frontend/src/lib/api.ts"
        issue: "No helper for GET /approvals pending list."
    missing:
      - "Add a pending approvals API helper and list UI."
      - "Keep approve/reject wired to selected pending approval records."
  - truth: "SSE endpoint safely streams progressive status for a run without duplicating execution"
    status: failed
    reason: "GET /agent-runs/{run_id}/events starts graph execution for any visible run and only marks it running inside the event generator. A retry or second tab can execute the same run again, duplicating side effects, approval requests, and trace rows."
    artifacts:
      - path: "src/api/routers/agent_runs.py"
        issue: "stream_agent_run_events does not reject non-pending runs or atomically transition pending -> running before returning EventSourceResponse."
    missing:
      - "Guard /events so only pending runs can start."
      - "Perform an atomic pending-to-running transition before streaming."
      - "Return 409 for already-started or terminal runs."
  - truth: "docker-compose up starts a complete stack where the frontend can reach the API"
    status: failed
    reason: "docker-compose defines VITE_API_URL=http://api:8000, but frontend API/SSE clients hardcode /api/v1 and Vite proxy targets http://localhost:8000. Inside the frontend container localhost is the frontend container, so browser requests through the dev server do not reach the API service."
    artifacts:
      - path: "docker-compose.yml"
        issue: "Provides VITE_API_URL, but the frontend does not consume it."
      - path: "frontend/src/lib/api.ts"
        issue: "Hardcodes API_BASE = '/api/v1'."
      - path: "frontend/vite.config.ts"
        issue: "Proxy target is localhost:8000 instead of the compose service name or env-driven target."
    missing:
      - "Make API/SSE clients or Vite proxy honor VITE_API_URL."
      - "Use http://api:8000 for the dev-server proxy in compose."
  - truth: "SSE disconnect recovery and API failures leave the UI in an observable error/recovery state"
    status: partial
    reason: "useAgentRun calls recovery APIs, but apiFetch throws on network failures and non-JSON responses. submitQuery, recoverRunStatus, polling, evidence, and trace callers do not catch those rejections, so the UI can remain stuck instead of showing failed/disconnected recovery state."
    artifacts:
      - path: "frontend/src/lib/api.ts"
        issue: "apiFetch always awaits response.json() and has no try/catch or response.ok normalization."
      - path: "frontend/src/hooks/useAgentRun.ts"
        issue: "submitQuery/recoverRunStatus/polling await API helpers without rejection handling."
    missing:
      - "Return ApiResult failures for network, non-JSON, and non-2xx responses."
      - "Catch async failures in run, recovery, evidence, trace, and approval flows."
  - truth: "TypeScript event definitions cover all backend SSE event types"
    status: failed
    reason: "Backend emits run_started, step_started, step_completed, final_response, approval_required, and error; frontend types instead include node_started/node_completed/run_completed/run_failed and omit step_started, step_completed, and error."
    artifacts:
      - path: "frontend/src/types/events.ts"
        issue: "SseEventType union does not match emitted backend event_type values."
      - path: "src/api/routers/agent_runs.py"
        issue: "Actual emitted event types are defined in _sse_event call sites."
    missing:
      - "Align frontend SseEventType with backend emitted event types."
---

# Phase 5: Frontend & SSE Verification Report

**Phase Goal:** Minimal frontend provides a complete demo experience with chat interface, approval operations, and execution step visibility; SSE or polling for progressive updates.
**Verified:** 2026-05-17T09:27:58Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Chat interface submits refund/order questions and displays evidence-cited answers with source attribution | FAILED | UI path exists, but default demo auth is broken: `useAuth.ts:6-10` uses nonexistent demo usernames, `App.tsx:14-20` ignores token fetch failure, and protected calls require real JWT scopes. |
| 2 | Approval interface shows pending approval requests with approve/reject buttons; actions update in real time | PARTIAL | `ApprovalTab.tsx` has approve/reject buttons and calls `decideApproval`, but no frontend code calls `GET /api/v1/approvals` or renders a pending approvals list. |
| 3 | Execution step panel shows Agent current stage, tools called, evidence retrieved, and approval status | VERIFIED | `AgentTimeline.tsx` renders streamed `steps`; `TimelineStep.tsx` shows message/status; SSE payload extraction includes `tool_name`, `evidence_count`, and `risk_level`. |
| 4 | SSE or polling endpoint streams progressive status updates | FAILED | `/events` streams events through `graph.astream(..., stream_mode="updates")`, but the critical duplicate-execution guard is missing in `stream_agent_run_events`. |
| 5 | No complex graph node animations; simple status indicators are used | VERIFIED | Timeline uses simple status dots/icons and `animate-pulse` for running state only. |
| 6 | POST `/api/v1/agent-runs` creates a pending run | VERIFIED | `create_agent_run` writes an AgentRun and returns `{run_id, status: "pending"}`. |
| 7 | GET `/api/v1/agent-runs/{run_id}/events` returns text/event-stream SSE events | VERIFIED | FastAPI route returns `EventSourceResponse`; route import spot-check listed `/events`. |
| 8 | SSE event envelope has event_type, run_id, step_index, node_name, status, message, timestamp, payload | VERIFIED | `_sse_event` constructs the full JSON envelope before yielding SSE data. |
| 9 | Approval interrupt produces `approval_required` event | VERIFIED | `_handle_approval_required` creates approval record, persists interrupted run state, and yields `approval_required`. |
| 10 | Status and evidence endpoints return persisted run data | VERIFIED | `get_agent_run_status` and `get_agent_run_evidence` use `TraceRepository` with tenant-scoped run lookup. |
| 11 | New run endpoints use scoped auth and tenant isolation | VERIFIED | All four new endpoints use `Security(get_current_user, scopes=["agent:chat"])`; run lookup filters by tenant and owner/supervisor role. |
| 12 | Vite React TypeScript frontend scaffold exists and builds | VERIFIED | `frontend/` exists and `npm run build` passed. |
| 13 | API and SSE clients attach bearer auth | VERIFIED | `apiFetch` and `connectToRunEvents` attach Authorization when a token is present. |
| 14 | Demo role switching maps support_agent/manager/admin to working demo identities | FAILED | `useAuth.ts` maps roles to `demo-agent`, `demo-manager`, and `demo-admin`, which are not seeded users. |
| 15 | Frontend event types cover backend SSE event types | FAILED | Frontend type union omits `step_started`, `step_completed`, and `error`, and includes event names backend does not emit. |
| 16 | Chat submit creates run, connects SSE, and displays final response | FAILED | Hook wiring exists, but default token acquisition fails; `apiFetch` can also throw and leave status stuck. |
| 17 | Timeline updates from streamed events | VERIFIED | `useAgentRun` appends every parsed SSE event to `state.steps`; `AgentTimeline` renders those steps. |
| 18 | Details panel auto-switches to Approval on approval_required | VERIFIED | `DetailsPanel.tsx:40-44` switches active tab when status is `waiting_approval`; approval event payload supplies proposed action/risk. |
| 19 | Approval buttons call decision endpoint | VERIFIED | `ApprovalTab` and `useAgentRun` call `decideApproval`; backend endpoint exists with `approvals:review` scope. |
| 20 | Evidence tab displays run evidence list | VERIFIED | `EvidenceTab` calls `getRunEvidence(runId)` and renders doc/chunk/confidence fields. |
| 21 | Trace tab displays execution steps and error fields | VERIFIED | `TraceTab` calls `getRunTrace(runId)` and renders node/status/tool/latency/error fields. |
| 22 | SSE disconnect shows disconnected state and calls recovery API | PARTIAL | `useAgentRun` sets `disconnected` and calls `getRunStatus`, but unhandled API rejections can bypass recovery state. |
| 23 | docker-compose defines frontend service | VERIFIED | `docker-compose.yml` has frontend build context, target, port 3000, healthcheck, and api health dependency. |
| 24 | docker-compose up can run complete stack with working frontend-to-api path | FAILED | Compose config is syntactically valid, but frontend hardcoded `/api/v1` plus Vite proxy to localhost breaks container-to-API routing. |
| 25 | shadcn/Tailwind dark operational theme foundation exists | VERIFIED | Tailwind config, dark HTML class, UI primitives, and status tokens are present. |
| 26 | Run status polling after approval exists | VERIFIED | `startPolling` calls `getRunStatus` every 2s after approve/reject. |
| 27 | Backend status/evidence/trace links are registered in FastAPI | VERIFIED | Route spot-check listed trace, create/status/events/evidence under `/api/v1/agent-runs`. |
| 28 | Code review critical correctness finding is resolved or non-blocking | FAILED | CR-01 remains present: no guard/atomic transition before SSE execution starts. |
| 29 | Frontend handles network/non-JSON API failure without stranding state | FAILED | `apiFetch` has no try/catch and always parses JSON. |

**Score:** 22/29 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/api/schemas/agent_runs.py` | Run request/status/SSE payload schemas | VERIFIED | Exists; gsd artifact check passed. |
| `src/api/routers/agent_runs.py` | 4 run endpoints and SSE stream | PARTIAL | Exists and wired, but `/events` lacks duplicate-run guard. |
| `src/api/main.py` | Router registration | VERIFIED | Registers traces and agent_runs under `/api/v1/agent-runs`. |
| `frontend/src/lib/api.ts` | Authenticated REST client | PARTIAL | Bearer auth exists; no env base URL or failure normalization. |
| `frontend/src/lib/sse.ts` | Authenticated SSE client | VERIFIED | Uses `fetchEventSource` with Authorization header. |
| `frontend/src/hooks/useAuth.ts` | Demo role switching | FAILED | Role map points at nonexistent demo users and installs placeholder tokens. |
| `frontend/src/hooks/useAgentRun.ts` | SSE run state machine | PARTIAL | Core state machine exists; API rejection handling incomplete. |
| `frontend/src/components/chat/ChatPanel.tsx` | Chat panel | PARTIAL | UI exists; default demo cannot authenticate to submit. |
| `frontend/src/components/timeline/AgentTimeline.tsx` | Step status display | VERIFIED | Renders streamed steps and disconnected banner. |
| `frontend/src/components/details/ApprovalTab.tsx` | Approval operations | PARTIAL | Can decide current approval; no pending approval list. |
| `frontend/src/components/details/EvidenceTab.tsx` | Evidence list | VERIFIED | Calls evidence endpoint and renders source metadata. |
| `frontend/src/components/details/TraceTab.tsx` | Trace details | VERIFIED | Calls trace endpoint and renders step/error fields. |
| `docker-compose.yml` | Frontend service in full stack | PARTIAL | Service exists and compose config passes; API routing from container is broken. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/api/main.py` | `agent_runs.router` | `app.include_router(...)` | VERIFIED | Route spot-check listed all new run routes. |
| `src/api/routers/agent_runs.py` | LangGraph | `request.app.state.agent_graph` | VERIFIED | Manual grep found `request.app.state.agent_graph` and lifespan builds `app.state.agent_graph`. |
| `src/api/routers/agent_runs.py` | `graph.astream()` | `stream_mode="updates"` | VERIFIED | SSE generator iterates `graph.astream(input_state, config, stream_mode="updates")`. |
| `frontend/src/hooks/useAgentRun.ts` | Run API + SSE | `createRun` then `connectToRunEvents` | VERIFIED | `submitQuery` creates a run, stores run_id, then attaches stream. |
| `frontend/src/components/details/ApprovalTab.tsx` | Approval decision API | `decideApproval` | VERIFIED | Button confirmation calls approve/reject handlers or direct API fallback. |
| `frontend/src/components/details/ApprovalTab.tsx` | Pending approvals list API | none | FAILED | No `GET /approvals` helper or list rendering. |
| `frontend` in Docker | API service | Vite proxy/env | FAILED | `VITE_API_URL` is unused and proxy targets localhost. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `ChatPanel` / `MessageList` | `finalResponse` | SSE `final_response` payload and `getRunStatus` recovery | Yes, after auth works | PARTIAL |
| `AgentTimeline` | `steps` | Parsed SSE events from `/agent-runs/{run_id}/events` | Yes | VERIFIED |
| `DetailsPanel` / `ApprovalTab` | `approvalId`, `proposedAction`, `riskLevel` | `approval_required` SSE event payload | Yes for current run only | PARTIAL |
| `EvidenceTab` | `evidence` | `GET /agent-runs/{run_id}/evidence` | Yes | VERIFIED |
| `TraceTab` | `steps` | `GET /agent-runs/{run_id}/trace` | Yes | VERIFIED |
| `useAuth` / `App` | `username`, JWT token | `ROLE_USERS` -> `/auth/demo-token` | No in default demo | FAILED |
| Docker frontend API calls | API base URL | Vite proxy / `VITE_API_URL` | No in compose container | FAILED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| FastAPI registers run routes | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.api.main import app; print([r.path for r in app.routes if 'agent-runs' in getattr(r, 'path', '')])"` | Listed trace, create, status, events, and evidence routes | PASS |
| Frontend production build | `npm run build` in `frontend/` | Built Vite bundle successfully | PASS |
| Compose syntax | `docker compose config --quiet` | Exited 0 | PASS |
| Frontend lint | `npm run lint` in `frontend/` | 8 ESLint errors | FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AGNT-07 | 05-01 | Agent supports SSE streaming of current stages such as reading order/searching rules/waiting approval | PARTIAL | SSE endpoint streams progressive events, but duplicate stream execution risk remains. |
| FRNT-01 | 05-02, 05-03 | Chat submits refund/order questions and displays evidence-cited answer | FAILED | Chat UI/hook exists, but default demo auth prevents protected submit/SSE path from working. |
| FRNT-02 | 05-03 | Approval interface shows pending list and supports approve/reject | PARTIAL | Current-run approve/reject exists; pending approval list is missing. |
| FRNT-03 | 05-03, 05-04 | Execution step panel shows current stage, called tools, evidence, approval status | VERIFIED | Timeline renders stages/status; details tabs render evidence, trace tool names, and approval status. |
| FRNT-04 | 05-03 | No complex graph animation required | VERIFIED | Simple status indicators used. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/api/routers/agent_runs.py` | 102 | SSE execution endpoint lacks run-state guard | Blocker | Can re-run the same agent request and duplicate side effects. |
| `frontend/src/hooks/useAuth.ts` | 6 | Hardcoded nonexistent demo users | Blocker | Default demo cannot authenticate. |
| `frontend/src/hooks/useAuth.ts` | 19 | Placeholder bearer token installed | Blocker | Failed token exchange leaves invalid auth state. |
| `frontend/src/lib/api.ts` | 1 | Hardcoded API base | Warning | Compose frontend cannot use configured API service URL. |
| `frontend/vite.config.ts` | 17 | Docker-incompatible localhost proxy | Warning | Frontend container proxy points to itself, not API service. |
| `frontend/src/lib/api.ts` | 34 | No network/non-JSON error normalization | Warning | UI can remain stuck on failed requests. |
| `frontend/src/types/events.ts` | 12 | Event type drift | Warning | Frontend type contract does not match backend events. |
| `frontend/src/components/details/DetailsPanel.tsx` | 42 | Lint: setState in effect | Info | Lint fails; not primary goal blocker. |

### Human Verification Required

After the gaps above are fixed, run browser UAT against the local or compose stack:

1. **Happy path chat**
   - **Test:** Select support agent, submit a refund/order question, watch streamed timeline, and verify final answer plus evidence attribution.
   - **Expected:** Run starts, timeline progresses through stages, answer appears, evidence tab shows cited sources.
   - **Why human:** Requires live browser, seeded database, LLM/tool behavior, and visual confirmation.

2. **Approval flow**
   - **Test:** Submit a high-risk compensation request as support, switch to manager/admin, approve and reject separate pending approvals.
   - **Expected:** Approval tab/list shows pending request, decision succeeds with reviewer token, run status updates after polling.
   - **Why human:** Cross-role interaction and LangGraph resume behavior need end-to-end UAT.

3. **Docker demo stack**
   - **Test:** Start `docker compose up`, open `http://localhost:3000`, and complete happy path plus approval path.
   - **Expected:** Frontend reaches API through the container network and all healthchecks pass.
   - **Why human:** Requires live container stack and browser/network inspection.

### Gaps Summary

The backend and frontend artifacts are substantial and mostly wired, but the phase goal is not achieved yet. The default demo cannot authenticate because the frontend maps roles to nonexistent users and leaves placeholder bearer tokens installed. The approval UI supports deciding a current SSE-derived approval, but it does not show the pending approvals list required by FRNT-02 and the roadmap. The SSE stream endpoint has a critical correctness gap: repeated `/events` connections can execute the same run again. The compose stack is syntactically valid, but the frontend cannot reach the API from inside Docker because the configured `VITE_API_URL` is unused and the Vite proxy targets localhost.

No deferred item in Phase 6 specifically covers these frontend/SSE correctness gaps. Phase 6 is evaluation, polish, README, demo script, and CI baseline, so these remain actionable Phase 5 gaps.

---

_Verified: 2026-05-17T09:27:58Z_
_Verifier: Claude (gsd-verifier)_
