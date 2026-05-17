---
phase: 05-frontend-sse
plan: 06
subsystem: frontend
tags: [react, vite, jwt, sse, demo-auth]
requires:
  - phase: 05-frontend-sse
    provides: frontend run console, SSE client, demo auth hook
provides:
  - Seeded demo-role username mapping for cs_zhang, mgr_li, and admin_user
  - Real JWT gating before protected chat and SSE actions
  - Frontend SSE event union aligned to backend emissions
  - VITE_API_URL-driven Vite proxy target for compose
affects: [frontend, sse, docker-compose-demo, auth]
tech-stack:
  added: []
  patterns: [relative API paths with Vite proxy, authReady-gated protected actions, shared apiUrl helper]
key-files:
  created:
    - .planning/phases/05-frontend-sse/05-06-SUMMARY.md
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/lib/sse.ts
    - frontend/src/hooks/useAuth.ts
    - frontend/src/types/events.ts
    - frontend/src/App.tsx
    - frontend/src/components/chat/ChatPanel.tsx
    - frontend/src/components/chat/ChatInput.tsx
    - frontend/vite.config.ts
key-decisions:
  - "Browser clients keep relative /api/v1 paths while Vite proxy resolves the API service through VITE_API_URL."
  - "Protected chat submit is gated on a successful /auth/demo-token response, not on role selection alone."
patterns-established:
  - "Use apiUrl(path) for REST and SSE client paths so frontend URL construction stays consistent."
  - "Clear bearer auth and authReady before each demo role token exchange."
requirements-completed: [AGNT-07, FRNT-01, FRNT-03]
duration: 3min
completed: 2026-05-17T10:22:57Z
---

# Phase 05 Plan 06: Frontend Auth, SSE Contract, and Proxy Summary

**Seeded demo JWT gating, backend-aligned SSE event types, shared API path construction, and compose-aware Vite proxy routing.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-17T10:19:49Z
- **Completed:** 2026-05-17T10:22:57Z
- **Tasks:** 1
- **Files modified:** 9

## Accomplishments

- Demo roles now resolve to seeded users `cs_zhang`, `mgr_li`, and `admin_user`; no frontend code installs `demo-token:*` placeholders.
- `App.tsx` clears auth on role changes, fetches a real demo JWT, and keeps protected chat disabled unless token acquisition succeeds.
- `ChatPanel` displays demo-token failures above the input; `ChatInput` blocks submit while auth is not ready.
- Frontend SSE event names now match backend emissions: `run_started`, `step_started`, `step_completed`, `final_response`, `approval_required`, and `error`.
- REST and SSE URL construction share `apiUrl()`, and Vite proxy routing uses `process.env.VITE_API_URL`.

## Task Commits

1. **Task 1: Fix demo auth, API routing, and SSE event contracts** - `ff54b77` (fix)

Note: During Wave 3 concurrency, commit `f5ff49f` already contained the primary file updates for this plan before the task commit was made. The `ff54b77` task commit added scoped correctness hardening for failed demo-token states and visible auth status.

## Files Created/Modified

- `frontend/src/lib/api.ts` - Exports `apiUrl(path)` and uses it in `apiFetch`.
- `frontend/src/lib/sse.ts` - Uses `apiUrl()` for run event streams.
- `frontend/src/hooks/useAuth.ts` - Maps roles to seeded demo usernames and no longer installs placeholder bearer tokens.
- `frontend/src/types/events.ts` - Aligns `SseEventType` with backend emitted event names.
- `frontend/src/App.tsx` - Adds `authReady` and `authError` state around real demo-token exchange.
- `frontend/src/components/chat/ChatPanel.tsx` - Shows auth failures and forwards auth readiness to the input.
- `frontend/src/components/chat/ChatInput.tsx` - Disables submit when auth is not ready.
- `frontend/vite.config.ts` - Uses `process.env.VITE_API_URL || 'http://localhost:8000'` as proxy target.
- `.planning/phases/05-frontend-sse/05-06-SUMMARY.md` - Records execution outcome.

## Decisions Made

- Kept frontend API calls relative (`/api/v1`) so the browser never receives Docker-internal service names.
- Used Vite proxy configuration, not client-side absolute API URLs, to bridge the frontend container to `http://api:8000`.
- Treated demo-token failure as a protected-action blocker instead of allowing UI submission with a missing or placeholder token.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Explicitly retained disabled auth state on token failure**
- **Found during:** Task 1
- **Issue:** The planned flow set `authReady=false` before the request, but failure branches did not explicitly restate the invariant.
- **Fix:** Added `setAuthReady(false)` in failed API result and promise rejection branches.
- **Files modified:** `frontend/src/App.tsx`
- **Verification:** `cd frontend && npm run build`
- **Committed in:** `ff54b77`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Narrow correctness hardening only; no expanded feature scope.

## Issues Encountered

- The plan task was marked `tdd="true"`, but this Wave 3 executor was given a write scope that did not allow creating or modifying test files. Verification used the plan acceptance greps and `npm run build`.
- Concurrent commit `f5ff49f` touched the same frontend files and already contained the main 05-06 changes. No unrelated concurrent files were reverted or staged.

## Verification

- `cd frontend && npm run build` - passed
- `rg -n "cs_zhang|mgr_li|admin_user" frontend/src/hooks/useAuth.ts` - matched seeded users
- `rg -n "demo-token:" frontend/src frontend/vite.config.ts` - no matches
- `rg -n "authReady|authError|Demo token 获取失败" frontend/src/App.tsx frontend/src/components/chat/ChatPanel.tsx frontend/src/components/chat/ChatInput.tsx` - matched auth gating
- `rg -n "step_started|step_completed|event_type: SseEventType" frontend/src/types/events.ts` - matched backend event contract
- `rg -n "node_started|node_completed|run_completed|run_failed|tool_called|evidence_retrieved" frontend/src/types/events.ts` - no matches
- `rg -n "process\\.env\\.VITE_API_URL|apiProxyTarget|target: apiProxyTarget" frontend/vite.config.ts` - matched proxy config

## Known Stubs

None. Stub scan found only the chat input placeholder attribute and nullable auth token state; neither is a functional data stub.

## Threat Flags

None. This plan removed placeholder bearer tokens and did not introduce new network endpoints, schema changes, or file access paths.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Verification gaps 1, 4, and 6 are closed for the frontend files in this plan. Remaining Phase 5 gaps outside this plan, such as pending approval list behavior and backend duplicate SSE execution guard, remain owned by their respective gap plans.

## Self-Check: PASSED

- Found summary file: `.planning/phases/05-frontend-sse/05-06-SUMMARY.md`
- Found task commit: `ff54b77`
- Confirmed no tracked file deletions in task commit.
- Confirmed `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified by this executor.

---
*Phase: 05-frontend-sse*
*Completed: 2026-05-17T10:22:57Z*
