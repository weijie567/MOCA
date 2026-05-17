---
phase: 05
slug: frontend-sse
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-17
---

# Phase 05 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest for backend; npm scripts with Vite/TypeScript/ESLint for frontend |
| **Config file** | `pyproject.toml`; `frontend/package.json`; `frontend/eslint.config.js`; `frontend/vite.config.ts` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_approval_api.py -q && cd frontend && npm run lint && npm run build && cd .. && docker compose config --quiet` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific quick command from the PLAN.md `<verify>` block.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 120 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | AGNT-07 | T-05-01 | SSE schemas import and dependency resolves | import/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.api.schemas.agent_runs import CreateRunRequest, RunStatusResponse, SseEventPayload"` | yes | pending |
| 05-01-02 | 01 | 1 | AGNT-07 | T-05-01 | Run endpoints preserve tenant-scoped auth and stream events | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q` | no - created by gap closure | pending |
| 05-02-01 | 02 | 1 | FRNT-01, FRNT-02 | T-05-02 | Frontend client attaches bearer token and builds | build | `cd frontend && npm run build` | yes | pending |
| 05-03-01 | 03 | 2 | FRNT-01, FRNT-03, FRNT-04 | T-05-03 | Chat, timeline, details panel compile and render contracts exist | build | `cd frontend && npm run build` | yes | pending |
| 05-04-01 | 04 | 2 | FRNT-03 | T-05-04 | Compose config contains frontend service and valid proxy wiring | config | `docker compose config --quiet` | yes | pending |
| 05-05-01 | 05 | 3 | AGNT-07 | T-05-05-03 | Non-pending SSE runs return 409 before `graph.astream` | regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q` | no - create in plan | pending |
| 05-05-02 | 05 | 3 | AGNT-07 | T-05-05-04 | Cross-tenant run ids cannot be claimed for streaming | regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q` | no - create in plan | pending |
| 05-06-01 | 06 | 3 | FRNT-01 | T-05-06-01 / T-05-06-02 | Demo UI installs only real seeded-user JWTs | build/grep | `cd frontend && npm run build` | yes | pending |
| 05-06-02 | 06 | 3 | AGNT-07, FRNT-03 | T-05-06-03 | Frontend SSE event types match backend emissions | build/grep | `cd frontend && npm run build` | yes | pending |
| 05-06-03 | 06 | 3 | FRNT-01 | T-05-06-04 | Docker proxy uses `VITE_API_URL` and compose config validates | config | `docker compose config --quiet` | yes | pending |
| 05-07-01 | 07 | 4 | FRNT-02 | T-05-07-01 / T-05-07-02 | Pending approvals list drives selected approval decisions | build/grep | `cd frontend && npm run build` | yes | pending |
| 05-07-02 | 07 | 4 | FRNT-01, FRNT-03 | T-05-07-03 | API/SSE failures become visible UI error or recovery states | build/grep | `cd frontend && npm run build` | yes | pending |
| 05-08-01 | 08 | 3 | FRNT-03 | T-05-08 | Phase 5 frontend lint blockers are resolved | lint/build | `cd frontend && npm run lint && npm run build` | yes | pending |

---

## Wave 0 Requirements

Existing infrastructure covers the initial Phase 5 requirements:

- `pyproject.toml` provides pytest, ruff, FastAPI, and backend test infrastructure.
- `tests/conftest.py` provides database, app, client, and seeded demo fixtures.
- `frontend/package.json` provides `npm run lint` and `npm run build`.
- `docker-compose.yml` provides compose validation via `docker compose config --quiet`.

Gap-closure Plan 05 creates `tests/test_agent_runs_api.py` before relying on it.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser happy-path chat | FRNT-01, FRNT-03 | Requires live API, seeded data, browser EventSource behavior, and LLM/tool execution | Start API/frontend, select Support Agent, submit `请给 ORD-2024-001 补偿 600 元`, confirm timeline progresses, final answer appears, evidence tab shows sources. |
| Cross-role approval | FRNT-02 | Requires human role switching and backend approval resume behavior | Submit a high-risk request, switch to Manager, select the pending approval, approve once and reject a separate run, confirm statuses update. |
| Docker demo stack | FRNT-01, FRNT-02, FRNT-03 | Requires container networking and browser inspection | Run `docker compose up`, open `http://localhost:3000`, complete chat and approval flows through the frontend container. |

---

## Validation Sign-Off

- [x] All planned tasks have automated verify commands or explicit manual-only justification.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers existing infrastructure; gap closure creates missing backend regression tests.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 120 seconds for focused checks.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
