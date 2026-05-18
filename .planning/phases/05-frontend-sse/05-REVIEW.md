---
phase: 05-frontend-sse
reviewed: 2026-05-18T08:19:05Z
depth: standard
files_reviewed: 53
files_reviewed_list:
  - Dockerfile
  - docker-compose.yml
  - frontend/Dockerfile
  - frontend/components.json
  - frontend/eslint.config.js
  - frontend/index.html
  - frontend/package.json
  - frontend/postcss.config.js
  - frontend/src/App.css
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
  - frontend/src/components/ui/button.tsx
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
  - frontend/src/lib/utils.ts
  - frontend/src/main.tsx
  - frontend/src/types/events.ts
  - frontend/tailwind.config.ts
  - frontend/tsconfig.app.json
  - frontend/tsconfig.json
  - frontend/tsconfig.node.json
  - frontend/vite.config.ts
  - pyproject.toml
  - scripts/seed_demo.py
  - src/agent/nodes/execute_action.py
  - src/agent/nodes/receive_request.py
  - src/api/main.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/schemas/agent_runs.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_execute_action.py
  - tests/test_seed_demo.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-18T08:19:05Z
**Depth:** standard
**Files Reviewed:** 53
**Status:** issues_found

## Summary

Reviewed the frontend SSE console, run/approval APIs, Docker/config files, seed script, and related tests. No critical security issue was found. The main risks are status handling mismatches around non-happy-path agent completions and swallowed persistence failures that can leave the UI or stored run state inconsistent.

Verification run during review: `npm run lint --prefix frontend`, `npm run build --prefix frontend`, and `uv run ruff check ...` all passed.

## Warnings

### WR-01: Frontend polling never terminates for insufficient-evidence runs

**File:** `frontend/src/hooks/useAgentRun.ts:26`
**Issue:** The backend can persist `final_status == "insufficient_evidence"` via `build_trace_summary`, but the frontend status model and `TERMINAL_STATUSES` do not include it. If the SSE stream is recovered through polling, or an approval resume returns that status, `normalizeStatus()` casts it into state while `startPolling()` never clears the interval because the status is not terminal.
**Fix:**
```ts
// frontend/src/types/events.ts
export type RunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'insufficient_evidence'
  | 'waiting_approval'
  | 'interrupted'
  | 'rejected'
  | 'degraded'
  | 'failed'
  | 'error'
  | 'disconnected'

// frontend/src/hooks/useAgentRun.ts
const TERMINAL_STATUSES = new Set<AgentRunStatus>([
  'completed',
  'insufficient_evidence',
  'rejected',
  'degraded',
  'failed',
  'error',
])
```

### WR-02: Approval resume can mark a run completed without a final response

**File:** `src/api/routers/approvals.py:84`
**Issue:** After approval resume, `final_status` is set to `"completed"` whenever `node_errors` is absent, even if the graph returns no `final_response`. That leaves the persisted run as completed with `final_response = None`; the frontend then has no terminal response or error to show. The SSE execution path handles this case as an error, so the approval path should use the same invariant.
**Fix:**
```python
final_response_text = final_state.get("final_response")
final_status = "completed"
if final_state.get("node_errors") or not final_response_text:
    final_status = "error"

await update_agent_run_status(
    session,
    run_id=run_id,
    final_status=final_status,
    final_response=final_response_text,
    completed_at=datetime.now(UTC),
    total_latency_ms=total_latency_ms,
)
```

### WR-03: Run completion persistence failures are swallowed

**File:** `src/api/routers/agent_runs.py:412`
**Issue:** `_complete_run()` catches all exceptions, rolls back, and returns without surfacing the failure. Callers then continue and can emit `final_response` or `approval_required` events even though the run status, trace steps, or approval state were not durably stored. This can strand the run in `"running"` and make later status recovery disagree with what the client already saw.
**Fix:**
```python
async def _complete_run(...) -> None:
    try:
        run.final_status = final_status
        run.final_response = final_response
        run.completed_at = completed_at
        run.total_latency_ms = total_latency_ms
        run.total_tokens = _count_tokens(trace_steps)
        if trace_steps:
            await write_agent_steps(session, run_id=str(run.id), trace_steps=trace_steps)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
```

## Info

### IN-01: Unused template stylesheet remains in the frontend source

**File:** `frontend/src/App.css:1`
**Issue:** `App.css` contains Vite/template selectors such as `.counter`, `.hero`, and `#next-steps`, but it is not imported by `main.tsx` or `App.tsx` and does not apply to the current console UI.
**Fix:** Delete `frontend/src/App.css`, or import it only if those selectors are intentionally used.

---

_Reviewed: 2026-05-18T08:19:05Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
