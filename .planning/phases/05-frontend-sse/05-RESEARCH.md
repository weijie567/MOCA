# Phase 5: Frontend & SSE — Research

**Researched:** 2026-05-17
**Status:** Complete

## 1. SSE Streaming Architecture

### Current Execution Model
- `src/api/routers/agent.py` uses `graph.ainvoke(input_state, config)` — blocks until graph completes
- Returns final_state dict with all trace_steps accumulated

### LangGraph `astream` for SSE
- LangGraph compiled graphs support `graph.astream(input, config, stream_mode="updates")` 
- Yields `(node_name, state_update)` tuples as each node completes
- Alternative: `stream_mode="values"` yields full state after each node (heavier)
- `stream_mode="updates"` is ideal — yields only the delta from each node

### SSE Implementation Pattern
```python
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

async def stream_run(run_id, graph, input_state, config):
    async def event_generator():
        yield sse_event("run_started", {...})
        step_index = 0
        async for node_name, update in graph.astream(input_state, config, stream_mode="updates"):
            yield sse_event("step_started", {"node_name": node_name, "step_index": step_index})
            # ... process update
            yield sse_event("step_completed", {"node_name": node_name, ...})
            step_index += 1
        yield sse_event("final_response", {...})
    return EventSourceResponse(event_generator())
```

### GraphInterrupt Handling in Stream
- When `approval_gate` raises GraphInterrupt during `astream`, the async generator terminates
- Need to catch GraphInterrupt, emit `approval_required` event, then close stream
- After approval decision, frontend polls `GET /agent-runs/{run_id}` for final state

### Dependencies
- `sse-starlette` — FastAPI-compatible SSE response (well-maintained, 1.5k+ stars)
- Alternative: raw `StreamingResponse` with `text/event-stream` content type (no extra dep)
- Recommendation: use `sse-starlette` for proper SSE protocol compliance (retry, id, event fields)

## 2. API Design — Existing vs New

### Already Exists at `/api/v1/agent-runs`
- `GET /agent-runs/{run_id}/trace` — full trace with steps, approvals, action_drafts, timeline (traces.py)
- Router registered in main.py: `traces.router` at prefix `/api/v1/agent-runs`

### New Endpoints Needed
| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `POST /api/v1/agent-runs` | Create run, return run_id | Replaces inline run_id generation in agent.py |
| `GET /api/v1/agent-runs/{run_id}/events` | SSE stream | New — core of Phase 5 |
| `GET /api/v1/agent-runs/{run_id}` | Run status (recovery) | New — lightweight status check |
| `GET /api/v1/agent-runs/{run_id}/evidence` | Evidence used | New — extracts from trace |

### Router Organization
- Current `traces.py` handles `/agent-runs/{run_id}/trace` 
- New `agent_runs.py` router should handle the new endpoints
- Both can coexist on same prefix — FastAPI merges routes
- Or: move trace endpoint into new `agent_runs.py` for cohesion

## 3. Graph Node → SSE Event Mapping

| Graph Node | SSE Event | Chinese Message |
|------------|-----------|-----------------|
| receive_request | step_started/completed | 正在接收请求 |
| classify_intent | step_started/completed | 正在识别意图 |
| extract_slots | step_started/completed | 正在提取关键信息 |
| load_business_context | step_started/completed | 正在读取订单信息 |
| retrieve_policy_evidence | step_started/completed | 正在检索退款规则 |
| generate_recommendation | step_started/completed | 正在生成处理建议 |
| assess_risk_and_approval | step_started/completed | 正在评估风险 |
| approval_gate | approval_required | 需要审批 |
| execute_action | step_started/completed | 正在执行操作 |
| final_response | final_response | 已完成 |

### Payload Extraction per Node
- `retrieve_policy_evidence`: evidence_count from `retrieved_evidence.data.evidence`
- `assess_risk_and_approval`: risk_level from `risk_assessment.risk_level`
- `generate_recommendation`: recommended_action from `recommendation_draft`
- `approval_gate`: proposed_action, risk_level, approval_id

## 4. Auth & Demo Token Flow

### Existing Demo Auth
- `POST /api/v1/auth/demo-token` — accepts `{username: string}`, returns JWT
- Gated by `settings.enable_demo_auth` (env: `ENABLE_DEMO_AUTH=true` in docker-compose)
- JWT contains: sub (user_id), username, role, tenant_id
- Scopes are derived from user record, not request

### Demo Users (from seed data)
- Need to verify seed users exist with roles: support_agent, manager/admin (approver)
- Frontend role switcher calls `/auth/demo-token` with different usernames

### SSE Auth
- `@microsoft/fetch-event-source` sends Authorization header on SSE connection
- Backend: same `Security(get_current_user, scopes=[...])` pattern
- No URL query token needed

## 5. Frontend Stack Decisions (from CONTEXT.md)

### Confirmed Stack
- React 18+ with Vite + TypeScript
- shadcn/ui + Tailwind CSS (dark theme per UI-SPEC)
- `@microsoft/fetch-event-source` for SSE with auth headers
- No SSR, no Next.js, no state management library

### Project Structure
```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── components.json          (shadcn config)
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── ui/             (shadcn components)
│   │   ├── chat/           (ChatPanel, MessageList, ChatInput)
│   │   ├── timeline/       (AgentTimeline, TimelineStep)
│   │   ├── details/        (DetailsPanel, EvidenceTab, ApprovalTab, TraceTab)
│   │   └── layout/         (AppLayout, TopBar, RoleSwitcher)
│   ├── hooks/
│   │   ├── useAgentRun.ts  (SSE connection, state management)
│   │   └── useAuth.ts      (demo token, role switching)
│   ├── lib/
│   │   ├── api.ts          (fetch wrapper with auth)
│   │   └── sse.ts          (SSE client with reconnection)
│   └── types/
│       └── events.ts       (SSE event type definitions)
```

## 6. Docker Integration

### Current Services
- postgres (pgvector:pg16), redis (7-alpine), api (custom Dockerfile)
- API at port 8000

### Frontend Service Options
1. **Dev mode**: `node:20-alpine` running `npm run dev` with Vite (hot reload, good for demo)
2. **Production**: multi-stage build → nginx serving static files

Recommendation: Dev mode for Phase 5 (demo-focused), with Vite proxy to API:
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "3000:3000"
  depends_on:
    api:
      condition: service_healthy
  environment:
    VITE_API_URL: http://api:8000
```

Vite config proxies `/api` to backend — avoids CORS in development.

## 7. Disconnection & Recovery Strategy

### Per CONTEXT.md D-12
- No event replay
- Frontend shows "连接中断" on SSE disconnect
- Calls `GET /agent-runs/{run_id}` to check current state
- If completed → show final_response
- If still running → user can re-initiate (no reconnect to existing stream)

### Implementation
- `@microsoft/fetch-event-source` has built-in retry with `onerror` callback
- Override retry behavior: on disconnect, switch to polling mode
- Poll interval: 2s (per UI-SPEC)

## 8. Post-Approval Flow

### Per CONTEXT.md D-15
- After approval decision, frontend polls `GET /agent-runs/{run_id}` 
- Terminal states: completed, failed, rejected, degraded
- No new SSE stream after approval — simple polling until terminal

### Why Not Re-stream
- Approval resume is fast (only execute_action + final_response nodes)
- Adding SSE for 2 nodes adds complexity without demo value
- Polling at 2s interval catches completion within seconds

## 9. Key Technical Risks

| Risk | Mitigation |
|------|-----------|
| `astream` + GraphInterrupt interaction | Test with approval_gate; catch interrupt in generator |
| SSE connection timeout (proxy/nginx) | Set appropriate timeouts; send keepalive comments |
| Race condition: run created but stream not connected | POST creates run, returns run_id; GET /events starts execution |
| LangGraph checkpoint + streaming | Ensure checkpointer works with astream (same config pattern) |

## 10. Validation Architecture

### Testable Contracts
1. **SSE event format**: Each event matches schema from D-09
2. **Node coverage**: All 10 graph nodes emit step_started + step_completed
3. **Approval interrupt**: approval_required event contains approval_id, proposed_action
4. **Recovery API**: GET /agent-runs/{run_id} returns correct status after completion
5. **Auth flow**: Demo token → SSE connection succeeds with Bearer header
6. **Frontend renders**: Timeline shows all steps, Chat shows final response

### Integration Test Approach
- Start full stack (docker-compose)
- Create run via POST, connect SSE, verify event sequence
- Trigger approval flow, verify interrupt event + recovery polling
