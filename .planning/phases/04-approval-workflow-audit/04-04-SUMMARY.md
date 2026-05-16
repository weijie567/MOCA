---
phase: 04-approval-workflow-audit
plan: 04
subsystem: approval-api
tags: [fastapi, approvals, langgraph, resume, audit, rbac]

requires:
  - phase: 04-approval-workflow-audit
    provides: approval repositories, graph approval interrupt/resume topology
provides:
  - Approval decide, get, and list REST endpoints
  - Chat interrupt persistence into approval_requests and approval_steps
  - Graph resume on both approve and reject decisions
  - AgentRun status and post-resume trace updates after approval decisions
affects: [approval-workflow-audit, api, agent-chat, audit]

tech-stack:
  added: []
  patterns:
    - Approval decisions require approvals:review plus an approver role
    - Resume config reconstructs checkpoint thread IDs as tenant_id:user_id:thread_id
    - Chat interrupt handling supports both GraphInterrupt exceptions and __interrupt__ result payloads

key-files:
  created:
    - src/api/schemas/approvals.py
    - src/api/routers/approvals.py
    - tests/test_approval_api.py
  modified:
    - src/api/main.py
    - src/api/routers/agent.py

key-decisions:
  - "The approval router allows admin and manager roles, matching the current seeded test users."
  - "Idempotent repeat decisions return success without resuming the graph a second time."
  - "The chat endpoint persists interrupted runs before returning an approval_id to the caller."

patterns-established:
  - "Approval API tests use fake graph implementations to verify resume commands and interrupt persistence without live LLM calls."
  - "Post-resume trace persistence appends only steps after approval_gate to avoid duplicating pre-interrupt steps."

requirements-completed: []
requirements-addressed: [SAFE-03, SAFE-04, SAFE-05, EVAL-05]

duration: 18min
completed: 2026-05-16
---

# Phase 4 Plan 4: Approval REST API and Resume Integration Summary

**Approval review APIs now enforce tenant and role boundaries, resume the approval graph on both approve and reject decisions, and persist chat interrupts as auditable approval requests.**

## Performance

- **Duration:** 18 min
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Added approval API schemas for decide requests, approval details, and pending approval lists.
- Added `POST /api/v1/approvals/{id}/decide`, `GET /api/v1/approvals/{id}`, and `GET /api/v1/approvals` with tenant-scoped repository access.
- Integrated decision resume via `Command(resume=...)` for both approve and reject decisions using the existing scoped checkpoint thread key format.
- Updated `POST /api/v1/agent/chat` to detect both `GraphInterrupt` and `__interrupt__`, persist the interrupted `AgentRun`, write pre-interrupt steps, create an `ApprovalRequest`, and return an approval payload.
- Added API tests covering approval decision success, reject resume, self-approval, role denial, expiry, idempotency, conflicts, tenant isolation, run status updates, and chat interrupt persistence.

## Task Commits

Each task was committed atomically:

1. **Task 04-01: Create approval API schemas** - `660bc4a` (feat)
2. **Task 04-02: Create approvals router with decide/get/list endpoints** - `cdd9450` (feat)
3. **Task 04-03: Integrate chat endpoint interrupt detection and approval creation** - `7e23584` (feat)
4. **Task 04-04: Unit tests for approval API and resume flow** - `54ed57e` (test)

## Files Created/Modified

- `src/api/schemas/approvals.py` - Adds request and response models for approval endpoints.
- `src/api/routers/approvals.py` - Adds tenant-scoped approval review, decision, and resume endpoints.
- `src/api/main.py` - Registers the approvals router.
- `src/api/routers/agent.py` - Persists approval interrupts from chat execution.
- `tests/test_approval_api.py` - Adds focused approval API and interrupt persistence coverage.

## Decisions Made

- Approval review is guarded by both `approvals:review` scope and role membership.
- Repeated same-direction decisions are idempotent and do not resume the graph again.
- Expired approvals are marked expired before returning conflict.

## Deviations from Plan

### Plan Adaptations

**1. Approver role set follows current seed data**
- **Found during:** API tests
- **Issue:** The plan mentioned checking actual role names. Current fixtures provide `admin_user` for approval review.
- **Adjustment:** The router allows `admin` and `manager`; tests verify support users with the review scope still fail the role gate.
- **Files modified:** `src/api/routers/approvals.py`, `tests/test_approval_api.py`
- **Commit:** `cdd9450`, `54ed57e`

No Rule 1-3 auto-fixes were required.

## Issues Encountered

- The sandbox blocked local PostgreSQL socket access for API tests with `PermissionError: [Errno 1] Operation not permitted`. The same command passed when rerun outside the sandbox with approval.
- The original executor process stopped returning completion signals after partial commits. The remaining test and summary work was completed inline from the clean partial state.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q --tb=short` - 15 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py src/api/routers/agent.py src/api/schemas/approvals.py tests/test_approval_api.py` - passed

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-05 can build trace/timeline replay over persisted agent steps, approval requests, approval decision events, and action drafts.

## Self-Check: PASSED

- Verified summary, router, schema, and API test file exist.
- Verified task commits are reachable: `660bc4a`, `cdd9450`, `7e23584`, `54ed57e`.
- Verified focused API tests and lint pass.

---
*Phase: 04-approval-workflow-audit*
*Completed: 2026-05-16*
