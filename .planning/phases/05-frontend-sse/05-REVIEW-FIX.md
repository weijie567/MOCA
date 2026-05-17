---
phase: 05-frontend-sse
source_review: 05-REVIEW.md
status: fixed
fixed: 2026-05-17
review_rerun: blocked
review_rerun_reason: code review subagent hit usage limit during execute-phase gate
---

# Phase 5 Code Review Fixes

## Fixed Findings

- **CR-01:** `/api/v1/agent-runs/{run_id}/events` now claims a run with a tenant-scoped row lock before returning `EventSourceResponse`. Non-pending runs return `409 RUN_ALREADY_STARTED`, and the generator no longer performs the first `pending -> running` transition.
- **WR-01:** Demo roles now map to seeded users `cs_zhang`, `mgr_li`, and `admin_user`. The frontend no longer installs `demo-token:*` placeholder bearer tokens and disables protected chat submit until a real demo JWT is fetched.
- **WR-02:** Vite proxy routing now uses `process.env.VITE_API_URL || 'http://localhost:8000'`, so the compose frontend container can route `/api` requests to `http://api:8000` while browser code keeps relative `/api/v1` paths.
- **WR-03:** `apiFetch` now normalizes non-2xx, invalid-envelope, non-JSON, and network failures into `ApiResult` errors. Run creation, status recovery, polling, approvals, evidence, and trace flows expose visible error states.
- **WR-04:** The approval panel now loads real pending approvals from `GET /api/v1/approvals` and acts on a selected pending approval record. Backend self-approval/role failures are surfaced through normalized API errors.
- **IN-01:** Frontend lint blockers are fixed: derived approval tab selection, typed UI primitive props, ESM Tailwind plugin import, and React effect lint cleanup.

## Verification

- `uv run pytest tests/test_agent_runs_api.py -q` - 3 passed
- `uv run ruff check src tests` - passed
- `npm run lint` from `frontend/` - passed
- `npm run build` from `frontend/` - passed
- `docker compose config --quiet` - passed
- `gsd-sdk query verify.key-links .planning/phases/05-frontend-sse/05-07-PLAN.md` - 2/2 links verified

## Review Gate Note

The execute-phase code review rerun was attempted after fixes, but the `gsd-code-reviewer` subagent failed with an account usage-limit error. Per the execute-phase workflow, code review failures are nonblocking. This artifact records the fixes against the stale `05-REVIEW.md` findings.
