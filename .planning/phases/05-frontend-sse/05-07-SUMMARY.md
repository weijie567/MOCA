---
phase: 05-frontend-sse
plan: 07
subsystem: frontend
tags: [approvals, api-client, recovery, react]
requires:
  - phase: 05-frontend-sse
    provides: frontend console, real demo auth, SSE client
provides:
  - Pending approvals list loaded from GET /api/v1/approvals
  - Selected approval decision handling
  - Normalized REST client failures for HTTP, invalid JSON/envelope, and network errors
  - Visible failed/disconnected/recovery states for async failures
affects: [frontend, approvals-ui, api-client, run-state]
tech-stack:
  added: []
  patterns: [discriminated ApiResult, selected approval state, guarded async UI recovery]
key-files:
  created:
    - .planning/phases/05-frontend-sse/05-07-SUMMARY.md
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/hooks/useAgentRun.ts
    - frontend/src/components/details/ApprovalTab.tsx
    - frontend/src/components/details/EvidenceTab.tsx
    - frontend/src/components/details/TraceTab.tsx
key-decisions:
  - "REST helpers normalize all transport and envelope failures into ApiResult instead of throwing through UI callers."
  - "Approval decisions target the selected pending approval record; current-run approval callbacks are preserved for SSE/polling recovery."
requirements-completed: [FRNT-01, FRNT-02, FRNT-03]
duration: 6min
completed: 2026-05-17T10:48:00Z
---

# Phase 05 Plan 07: Approval List and Failure Recovery Summary

The frontend now shows real pending approvals and moves API/SSE failure paths into visible UI states.

## Accomplishments

- Replaced the loose `ApiResult` interface with a discriminated success/failure union.
- Added `NETWORK_ERROR`, `INVALID_RESPONSE`, and `HTTP_*` fallback error normalization.
- Added `ApprovalRecord` and `getPendingApprovals()` for `/api/v1/approvals`.
- Updated `ApprovalTab` to render pending approval records, select a target approval, and approve/reject the selected pending record.
- Wrapped run creation, status recovery, polling, and approval decisions in catch guards.
- Preserved current-run approval callbacks so approval-required SSE flows still resume polling after approve/reject.
- Evidence and Trace loader catch paths were added during Wave 3 lint recovery and verified as part of this plan.

## Task Commits

1. **Task 1: Add pending approvals list and normalize async failure recovery** - `6cb7a09`
2. **Related recovery: Evidence/Trace loader catch paths** - `5aa7e62`

## Files Created/Modified

- `frontend/src/lib/api.ts` - Normalizes API failures and exports pending approval helpers.
- `frontend/src/hooks/useAgentRun.ts` - Adds try/catch recovery for create, status recovery, polling, and approval decisions.
- `frontend/src/components/details/ApprovalTab.tsx` - Renders pending approvals and acts on the selected record.
- `frontend/src/components/details/EvidenceTab.tsx` - Shows evidence loader failures.
- `frontend/src/components/details/TraceTab.tsx` - Shows trace loader failures.
- `.planning/phases/05-frontend-sse/05-07-SUMMARY.md` - Records execution outcome.

## Deviations from Plan

- `EvidenceTab.tsx` and `TraceTab.tsx` catch paths were implemented in the preceding lint recovery commit because `npm run lint` exposed those effect loaders before Wave 4 started. The final repository state satisfies the plan criteria.

## Verification

- `npm run build` from `frontend/` - passed
- `npm run lint` from `frontend/` - passed
- `gsd-sdk query verify.key-links .planning/phases/05-frontend-sse/05-07-PLAN.md` - passed, 2/2 links verified
- Acceptance greps for `NETWORK_ERROR`, `INVALID_RESPONSE`, `getPendingApprovals`, `ApprovalRecord`, `selectedApprovalId`, `activeApproval`, `risk_rule_ref`, `连接中断，状态恢复失败`, `审批提交失败`, evidence catch, and trace catch - passed

## Self-Check: PASSED

- Summary exists.
- Task commit exists.
- Key links verify.
- Build and lint pass.
- No shared tracking artifacts were committed by the executor.
