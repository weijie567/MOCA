---
phase: 04-approval-workflow-audit
plan: 05
subsystem: trace-api
tags: [fastapi, audit, trace, timeline, rbac]

requires:
  - phase: 04-approval-workflow-audit
    provides: agent approval graph, approval API, action draft persistence, agent trace tables
provides:
  - Tenant-scoped TraceRepository for agent runs, agent steps, approval requests, approval steps, and action drafts
  - GET /api/v1/agent-runs/{run_id}/trace endpoint
  - Sanitized unified trace timeline sorted by event time
  - Trace API tests for timeline replay, ordering, ownership, supervisor access, and tenant isolation
affects: [approval-workflow-audit, audit, api, frontend-trace-panel, evaluation]

tech-stack:
  added: []
  patterns:
    - Trace replay reads the tenant-scoped AgentRun first, then assembles related event tables by run_id.
    - Timeline entries use structured event metadata and omit raw prompt, raw model output, and action payload data.

key-files:
  created:
    - src/repositories/trace_repo.py
    - src/api/routers/traces.py
    - tests/test_trace_api.py
  modified:
    - src/api/main.py
    - src/api/schemas/approvals.py

key-decisions:
  - "TraceResponse intentionally excludes AgentRun.input_query and AgentRun.final_response to reduce trace information leakage."
  - "Trace access is owner-or-supervisor within tenant; cross-tenant lookups return 404 before ownership checks."
  - "Supervisor access includes admin, manager, supervisor, and approval_manager roles to align with the existing approval API role vocabulary."

patterns-established:
  - "Trace timeline assembly keeps detail payloads safe for replay UI: node/tool/status/latency, approval metadata, and draft identifiers only."
  - "Trace API tests seed real AgentRun, AgentStep, ApprovalRequest, ApprovalStep, and ActionDraft rows through the async test database."

requirements-completed: []
requirements-addressed: [EVAL-08]

duration: 7min
completed: 2026-05-16
---

# Phase 4 Plan 5: Audit Trail API and Trace Timeline Summary

**Run-level trace replay now merges agent steps, approval events, and action drafts into a tenant-scoped audit timeline.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-16T12:13:15Z
- **Completed:** 2026-05-16T12:19:56Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `TraceRepository` to retrieve an agent run, its ordered steps, approval requests, approval decision events, action drafts, and a unified sorted timeline.
- Added `GET /api/v1/agent-runs/{run_id}/trace` with `agent:chat` scope, tenant filtering, owner access, and supervisor/admin access.
- Added `TraceResponse` and registered the traces router under `/api/v1/agent-runs`.
- Added seven focused tests covering full timeline replay, sorting, non-owner denial, admin access, cross-tenant 404s, repository merge behavior, and empty-run timelines.

## Task Commits

Each task was committed atomically:

1. **Task 05-01: Create TraceRepository for timeline assembly** - `a57f14d` (feat)
2. **Task 05-02: Create trace API endpoint** - `c35e570` (feat)
3. **Task 05-03: Tests for trace API** - `828885f` (test)

## Files Created/Modified

- `src/repositories/trace_repo.py` - Adds trace read methods and sanitized timeline assembly.
- `src/api/routers/traces.py` - Adds tenant-scoped trace replay endpoint with owner/supervisor authorization.
- `src/api/schemas/approvals.py` - Adds `TraceResponse`.
- `src/api/main.py` - Registers the traces router at `/api/v1/agent-runs`.
- `tests/test_trace_api.py` - Adds trace API and timeline tests.

## Decisions Made

- The trace endpoint omits `input_query` and `final_response`, even though the plan sketch included them, because the threat model explicitly requires preventing raw prompt/LLM output leakage through trace replay.
- Cross-tenant run IDs are indistinguishable from missing runs and return 404.
- `manager` remains a supervisor-equivalent trace role because the existing approval API uses `admin` and `manager` as approval reviewer roles.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Removed raw query and final response from trace response**
- **Found during:** Task 05-02 (Create trace API endpoint)
- **Issue:** The plan sketch included `input_query` and `final_response` in `TraceResponse`, but the plan threat model requires avoiding raw prompt and LLM output leakage through traces.
- **Fix:** `TraceResponse` returns run metadata, safe step summaries, approval responses, action draft identifiers, and timeline events, but not raw user query or final model text.
- **Files modified:** `src/api/routers/traces.py`, `src/api/schemas/approvals.py`, `tests/test_trace_api.py`
- **Verification:** `tests/test_trace_api.py` asserts the response omits these fields and does not leak seeded secret text.
- **Committed in:** `c35e570`, `828885f`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The API still delivers replayable audit chains while reducing trace leakage risk. No scope creep.

## Issues Encountered

- The plan referenced `tests/test_agent_chat.py`, but the repository now stores the relevant chat/approval API coverage in `tests/test_approval_api.py`; implementation followed the current test structure.
- The sandbox blocked local PostgreSQL test DB socket access with `PermissionError: [Errno 1] Operation not permitted`; the same focused pytest command passed after rerunning with approved local DB access.
- Initial trace test fixture setup inserted an `ActionDraft` before its referenced `ApprovalRequest`; the fixture was corrected to flush the approval before adding dependent rows.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_trace_api.py -q --tb=short` - 7 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/repositories/trace_repo.py src/api/routers/traces.py src/api/main.py src/api/schemas/approvals.py tests/test_trace_api.py` - passed

## Known Stubs

None.

## Threat Flags

None - the new trace endpoint is the planned threat surface and is covered by tenant filtering, ownership checks, role checks, and response sanitization.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 04-06 can now validate high-risk interception and audit replay by querying `/api/v1/agent-runs/{run_id}/trace` for the complete approval/action chain.

## Self-Check: PASSED

- Verified summary, repository, router, schema, registration, and test files exist.
- Verified task commits are reachable: `a57f14d`, `c35e570`, `828885f`.
- Verified focused tests and lint pass.

---
*Phase: 04-approval-workflow-audit*
*Completed: 2026-05-16*
