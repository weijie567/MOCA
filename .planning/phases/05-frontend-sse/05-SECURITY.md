---
phase: 05
slug: frontend-sse
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-18
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser -> API | Frontend REST and SSE requests use demo JWT bearer auth. | Chat queries, run IDs, approval decisions, evidence/trace reads |
| API -> Auth Context | FastAPI dependency validates JWT scopes and derives user identity. | tenant_id, user_id, role, scopes |
| API -> Database | Run, trace, evidence, approval, and action draft records are persisted and queried. | Tenant-scoped operational records |
| API -> LangGraph | SSE endpoint and approval resume invoke the agent graph. | User query, thread ID, tenant/user/role context, approval resume payload |
| Frontend Role Switch -> Demo Auth | UI role selector maps only to seeded demo users and requests a real JWT. | Demo username, access token |
| Frontend Container -> API Container | Compose frontend proxies relative `/api/v1` browser calls to the API service. | Authenticated API requests over compose network |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-05-01 | Spoofing | `GET /agent-runs/{run_id}/events` | mitigate | Endpoint uses `Security(get_current_user, scopes=["agent:chat"])`; tenant/user/role are derived from JWT user context. Evidence: `src/api/routers/agent_runs.py:107-123`. | closed |
| T-05-02 | Information Disclosure | `GET /agent-runs/{run_id}` | mitigate | Status lookup uses tenant-scoped `TraceRepository.get_run`, then owner/supervisor authorization. Evidence: `src/api/routers/agent_runs.py:80-91`, `src/repositories/trace_repo.py:16-18`. | closed |
| T-05-03 | Elevation of Privilege | `POST /agent-runs` | mitigate | Run records are created with tenant/user from authenticated `user`; request body only supplies query and thread id. Evidence: `src/api/routers/agent_runs.py:50-65`. | closed |
| T-05-04 | Denial of Service | SSE long connections | accept | Demo scope accepts long-lived SSE connections; production rate limits remain out of scope for Phase 5. Evidence: `05-01-PLAN.md` accepted risk. | closed |
| T-05-05 | Information Disclosure | SSE payload | mitigate | Step payload extraction emits summary fields only; final answer is emitted only in the terminal `final_response` event. Evidence: `src/api/routers/agent_runs.py:469-496`, `src/api/routers/agent_runs.py:252-260`. | closed |
| T-05-05-01 | Spoofing | `stream_agent_run_events` auth/RBAC | mitigate | SSE route requires `agent:chat`; regression tests use bearer JWT auth. Evidence: `src/api/routers/agent_runs.py:107-112`, `tests/test_agent_runs_api.py`. | closed |
| T-05-05-02 | Information Disclosure | Token handling | mitigate | SSE client sends JWT in `Authorization` header; no query-string token path is used. Evidence: `frontend/src/lib/sse.ts:15-18`, `src/auth/permissions.py`. | closed |
| T-05-05-03 | Tampering / Denial of Service | Duplicate SSE execution | mitigate | Pending run is claimed with `SELECT ... FOR UPDATE` before streaming; non-pending runs return `409 RUN_ALREADY_STARTED`. Evidence: `src/api/routers/agent_runs.py:375-395`, `tests/test_agent_runs_api.py:165-208`. | closed |
| T-05-05-04 | Information Disclosure / Elevation of Privilege | Tenant isolation | mitigate | Claim query filters by `AgentRun.tenant_id == user.tenant_id`; cross-tenant stream attempts return 404 before mutation. Evidence: `src/api/routers/agent_runs.py:375-383`, `tests/test_agent_runs_api.py:211-233`. | closed |
| T-05-05-05 | Elevation of Privilege | Approval authorization | mitigate | Approval creation occurs only after the claimed run reaches interrupt; decisions require `approvals:review`, approved roles, tenant filtering, and self-approval rejection. Evidence: `src/api/routers/agent_runs.py:337-350`, `src/api/routers/approvals.py:25-46`. | closed |
| T-05-05-06 | Information Disclosure | Docker/API routing exposure | accept | Plan 05-05 did not touch Docker routing; duplicate-run errors use stable API codes, not service names. Evidence: `05-05-PLAN.md` accepted risk, `src/api/routers/agent_runs.py:385-390`. | closed |
| T-05-06-01 | Spoofing / Elevation of Privilege | Demo auth/RBAC | mitigate | UI role selector maps only to seeded users; protected submit is disabled until a real demo JWT is fetched. Evidence: `frontend/src/hooks/useAuth.ts:5-9`, `frontend/src/App.tsx:16-35`, `frontend/src/components/chat/ChatInput.tsx:15-18`. | closed |
| T-05-06-02 | Information Disclosure / Spoofing | Token handling | mitigate | Frontend installs only `access_token` from `/auth/demo-token`; implementation no longer uses `demo-token:*` bearer placeholders. Evidence: `frontend/src/App.tsx:25-31`, `frontend/src/lib/api.ts:126-130`. | closed |
| T-05-06-03 | Tampering / Denial of Service | SSE duplicate execution | transfer | Frontend-visible failures and aligned event types are implemented here; backend duplicate execution mitigation is owned and verified under T-05-05-03. Evidence: `src/api/routers/agent_runs.py:375-395`, `frontend/src/types/events.ts:13-19`. | closed |
| T-05-06-04 | Information Disclosure | Docker/API routing exposure | mitigate | Browser API paths remain relative; Vite proxy target reads `VITE_API_URL`; compose routes frontend to `http://api:8000`. Evidence: `frontend/src/lib/api.ts:1-35`, `frontend/vite.config.ts`, `docker-compose.yml`. | closed |
| T-05-07-01 | Information Disclosure / Elevation of Privilege | Pending approval tenant isolation | mitigate | Frontend calls the backend pending approvals list only; backend filters by tenant and pending/unexpired status. Evidence: `frontend/src/lib/api.ts:122-123`, `src/repositories/approval_repo.py:64-74`. | closed |
| T-05-07-02 | Elevation of Privilege / Repudiation | Approval authorization | mitigate | UI decisions act on selected pending approval IDs; backend enforces role, scope, tenant, expiry, idempotency, and self-approval checks. Evidence: `frontend/src/components/details/ApprovalTab.tsx:49-140`, `src/api/routers/approvals.py:31-63`. | closed |
| T-05-07-03 | Denial of Service | Network/proxy failures | mitigate | REST helper normalizes HTTP, non-JSON, invalid API, and network failures into visible `ApiResult` failures; hook callers catch and surface errors. Evidence: `frontend/src/lib/api.ts:50-83`, `frontend/src/hooks/useAgentRun.ts`. | closed |
| T-05-08-01 | Tampering | `DetailsPanel` tab state | mitigate | Approval auto-selection is derived from status without overwriting user tab state. Evidence: `frontend/src/components/details/DetailsPanel.tsx:41-68`. | closed |
| T-05-08-02 | Denial of Service | Frontend lint/build gate | mitigate | Final verification passed full backend tests, ruff, frontend lint/build, and compose health. Evidence: `05-VERIFICATION.md:90-98`. | closed |
| T-05-08-03 | Elevation of Privilege | Tailwind plugin config | accept | No new plugin was introduced; existing Tailwind animation plugin uses ESM import instead of `require`. Evidence: `frontend/tailwind.config.ts`. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party or separately owned mitigation)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-04 | Long-lived SSE connections are acceptable for the demo-scale Phase 5 environment; production connection limits remain future hardening. | Phase 5 plan | 2026-05-17 |
| AR-05-02 | T-05-05-06 | Plan 05-05 did not change Docker routing; duplicate stream error responses expose stable API error codes only. | Phase 5 plan | 2026-05-17 |
| AR-05-03 | T-05-08-03 | No new Tailwind plugin was introduced; existing plugin usage was converted to ESM import. | Phase 5 plan | 2026-05-17 |

---

## Transferred Mitigations

| Transfer ID | Threat Ref | Owner | Evidence |
|-------------|------------|-------|----------|
| TR-05-01 | T-05-06-03 | Backend SSE duplicate execution guard from Plan 05-05 | `_claim_pending_run_for_stream` locks and claims pending runs before `EventSourceResponse`; duplicate/terminal runs return 409. |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-18 | 22 | 22 | 0 | Codex + gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-18
