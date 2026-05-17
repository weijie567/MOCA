---
phase: 05-frontend-sse
plan: 03
subsystem: ui
tags: [react, typescript, sse, approvals, shadcn-compatible]
requires:
  - phase: 05-frontend-sse
    provides: Backend run APIs, frontend scaffold, API client, SSE client, auth hook, and UI spec
provides:
  - SSE-driven useAgentRun lifecycle hook with disconnect recovery and approval polling
  - Three-column demo console with chat, realtime timeline, and details tabs
  - Evidence, Approval, Trace, and Run Info panels wired to run APIs
  - Local shadcn-compatible UI primitives needed by the console
affects: [frontend, demo-console, sse, approvals]
tech-stack:
  added: []
  patterns:
    - Hook-owned agent run state machine around createRun, connectToRunEvents, and getRunStatus
    - Dense operational console layout using local shadcn-compatible primitives
key-files:
  created:
    - frontend/src/hooks/useAgentRun.ts
    - frontend/src/components/layout/TopBar.tsx
    - frontend/src/components/chat/ChatPanel.tsx
    - frontend/src/components/chat/ChatInput.tsx
    - frontend/src/components/chat/MessageList.tsx
    - frontend/src/components/timeline/AgentTimeline.tsx
    - frontend/src/components/timeline/TimelineStep.tsx
    - frontend/src/components/details/DetailsPanel.tsx
    - frontend/src/components/details/EvidenceTab.tsx
    - frontend/src/components/details/ApprovalTab.tsx
    - frontend/src/components/details/TraceTab.tsx
    - frontend/src/components/ui/badge.tsx
    - frontend/src/components/ui/card.tsx
    - frontend/src/components/ui/dialog.tsx
    - frontend/src/components/ui/scroll-area.tsx
    - frontend/src/components/ui/tabs.tsx
    - frontend/src/components/ui/textarea.tsx
  modified:
    - frontend/src/App.tsx
key-decisions:
  - "ApprovalTab accepts polling-aware approve/reject handlers from useAgentRun, with direct decideApproval fallback for component reuse."
  - "App fetches the real backend demo JWT for the selected role before protected run and approval API calls."
patterns-established:
  - "SSE stream closure is treated as expected after final_response or approval_required, avoiding false disconnected states."
  - "DetailsPanel auto-switches to Approval when status becomes waiting_approval."
requirements-completed: [FRNT-01, FRNT-02, FRNT-03, FRNT-04]
duration: 10min
completed: 2026-05-17
---

# Phase 05 Plan 03: Frontend Demo Console Summary

**React support console with SSE chat execution, realtime timeline, evidence/approval/trace panels, and real demo-role JWT setup**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-17T08:33:20Z
- **Completed:** 2026-05-17T08:43:02Z
- **Tasks:** 5
- **Files modified:** 19

## Accomplishments

- Added `useAgentRun` to create runs, stream SSE events, collect timeline steps, recover disconnected status, and poll after approval decisions.
- Built the complete three-column console: chat input/history, Agent Timeline, and Details panel tabs.
- Added Evidence, Approval, Trace, and Run Info views backed by the existing API client functions.
- Wired `App.tsx` to role switching, real demo JWT retrieval, chat submission, timeline rendering, and approval actions.

## Task Commits

1. **Task 1: 创建 useAgentRun hook（SSE 状态机）** - `4c04631` (feat)
2. **Task 2: 创建 TopBar 和 Chat 组件** - `e461642` (feat)
3. **Task 3: 创建 AgentTimeline 组件** - `eb91bc0` (feat)
4. **Task 4: 创建 DetailsPanel 和 Tabs（Evidence, Approval, Trace）** - `e0e694a` (feat)
5. **Task 5: 组装 App.tsx 完整布局** - `9bb9c7f` (feat)
6. **Auth correctness fix** - `cea30a2` (fix)
7. **Plan metadata:** this summary commit

## Files Created/Modified

- `frontend/src/hooks/useAgentRun.ts` - Run lifecycle hook using `createRun`, `connectToRunEvents`, `getRunStatus`, and `decideApproval`.
- `frontend/src/components/layout/TopBar.tsx` - Console top bar with Demo Mode role switcher.
- `frontend/src/components/chat/*` - Chat panel, message list, and Enter-to-submit input.
- `frontend/src/components/timeline/*` - SSE step list with status dots, timestamps, and disconnected banner.
- `frontend/src/components/details/*` - Details tabs for evidence, approval decisions, trace rows, and run metadata.
- `frontend/src/components/ui/*` - Local shadcn-compatible primitives for textarea, scroll area, card, badge, tabs, and dialog.
- `frontend/src/App.tsx` - Complete app assembly and real demo JWT fetch on role changes.

## Decisions Made

- Kept the console visually dense and IDE-like, consistent with the Phase 5 UI spec and demo-support workflow.
- Used local primitives instead of adding a generator dependency during this plan.
- Routed approval decisions through `useAgentRun` from the assembled app so post-approval polling stays centralized.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Fetched real demo JWTs before protected API calls**
- **Found during:** Task 5 verification
- **Issue:** The existing `useAuth` hook sets a local `demo-token:*` string. Protected run, SSE, and approval endpoints require a backend JWT from `POST /api/v1/auth/demo-token`.
- **Fix:** `App.tsx` now exchanges the selected demo username for a real token with `getDemoToken()` and installs it via `setAuthToken()`.
- **Files modified:** `frontend/src/App.tsx`
- **Verification:** `npx tsc --noEmit` passed; `App.tsx` still satisfies Task 5 acceptance criteria.
- **Committed in:** `cea30a2`

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality)
**Impact on plan:** Required for the demo console to authenticate protected backend calls. Scope stayed inside owned `App.tsx`.

## Issues Encountered

- A separate executor committed Phase 05 Plan 04 while this plan was executing. There was no file overlap with this plan's owned frontend files, and no shared tracking files were modified here.

## Verification

| Command | Result |
| --- | --- |
| `cd frontend && npx tsc --noEmit` | PASS |
| `ls src/hooks/useAgentRun.ts src/components/layout/TopBar.tsx src/components/chat/ChatPanel.tsx src/components/timeline/AgentTimeline.tsx src/components/details/DetailsPanel.tsx src/components/details/ApprovalTab.tsx` | PASS |
| Acceptance string checks for all five tasks | PASS |

## Known Stubs

None. Empty arrays/nulls are initial runtime state, and textarea placeholders are user input hints rather than unwired data.

## Threat Flags

None. This plan added frontend consumers for existing authenticated APIs and did not introduce new network endpoints or backend trust boundaries.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The frontend console is assembled and type-checks. It is ready for browser-level UAT against the Phase 05 backend and compose integration.

## Self-Check: PASSED

- Created files exist: `frontend/src/hooks/useAgentRun.ts`, `frontend/src/components/layout/TopBar.tsx`, `frontend/src/components/chat/ChatPanel.tsx`, `frontend/src/components/timeline/AgentTimeline.tsx`, `frontend/src/components/details/DetailsPanel.tsx`, `frontend/src/components/details/ApprovalTab.tsx`.
- Task commits exist: `4c04631`, `e461642`, `eb91bc0`, `e0e694a`, `9bb9c7f`, `cea30a2`.
- Verification passed with `cd frontend && npx tsc --noEmit`.
- `.planning/STATE.md` and `.planning/ROADMAP.md` were not updated, per wave-executor constraint.

---
*Phase: 05-frontend-sse*
*Completed: 2026-05-17*
