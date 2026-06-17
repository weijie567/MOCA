---
phase: 13-approval-state-machine
plan: 05
subsystem: approvals
tags: [approval-service, needs-info, edit-reroute, action-safety-snapshot, fastapi, langgraph]

requires:
  - phase: 13-approval-state-machine
    provides: ApprovalService command boundary, v2 revision/hash fields, and trusted approval_result.v1 routing from Plan 13-04
provides:
  - Approval respond transitions that persist response_text, enter needs_info, bind clarification_request_id, and return no graph resume payload
  - Trusted attach_info command that validates clarification scope/version and revalidates or supersedes approval revisions
  - Approval edit transitions that persist edited_action_json, supersede old revisions, create replacement candidates, and reroute to risk validation
  - API validation for respond response_text and edit edited_action
affects: [phase-13-approval-state-machine, phase-14-demo-action-boundary, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - ApprovalService owns respond, attach_info, and edit revision lifecycle under the existing request/level/assignment version guards
    - Changed action/evidence/config material creates replacement approval revisions with fresh action and snapshot hashes
    - API validation uses PydanticCustomError so FastAPI 422 responses remain serializable by the project error handler

key-files:
  created:
    - tests/approvals/test_needs_info_resume.py
    - .planning/phases/13-approval-state-machine/13-05-SUMMARY.md
  modified:
    - src/approvals/schemas.py
    - src/approvals/repository.py
    - src/approvals/service.py
    - src/api/schemas/approvals.py
    - src/api/routers/approvals.py
    - src/agent/graph.py
    - tests/approvals/test_needs_info_resume.py
    - tests/test_approval_api.py
    - tests/test_graph_routing.py
    - tests/agent/test_graph.py

key-decisions:
  - "Approval respond writes needs_info and clarification_request_id but intentionally returns resume_payload=None so the old interrupted run cannot enter action_draft."
  - "Approval attach_info updates the same revision only for non-material info with bumped versions; changed payload/evidence/config supersedes the old revision and creates a pending replacement."
  - "Approval edit persists edited_action_json and exposes a risk-reroute approval_result payload, while the API endpoint does not treat edit as an action-authorizing graph resume."
  - "route_after_approval lives in src/agent/graph.py in this codebase, so the plan's routing change was applied there instead of src/agent/routing.py."

patterns-established:
  - "Old approval revisions are invalidated by status/version changes before any replacement revision can become the sole active pending revision."
  - "Replacement revision creation reuses canonical ActionSafetySnapshot persistence and normalizes evidence refs before hashing proposed_action.v1."
  - "Approval API response mapping exposes clarification_request_id, superseded_by_request_id, new_action_payload_hash, and resume_route when present."

requirements-completed:
  - APPROVAL-02
  - APPROVAL-01
  - SNAPSHOT-01

duration: 16 min
completed: 2026-06-15
---

# Phase 13 Plan 05: Needs Info and Edit Revision Semantics Summary

**Approval respond, attach_info, and edit now preserve trusted revision/hash boundaries and prevent old approval revisions from authorizing action drafts**

## Performance

- **Duration:** 16 min
- **Started:** 2026-06-15T08:49:32Z
- **Completed:** 2026-06-15T09:06:23Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added APPROVAL-02 tests for respond, attach_info scope/version failures, stale old revisions, replacement revision uniqueness, edit hash changes, and route safety.
- Implemented `ApprovalService.decide(... respond ...)` with `approval_decisions.response_text`, `needs_info`, server clarification ids, post-transition version bumps, and no resume payload.
- Added `ApprovalInfoCommand` and `ApprovalService.attach_info` to validate tenant/thread/clarification/version/actor scope and either revalidate or supersede exactly one active revision.
- Implemented `edit` decisions with durable `edited_action_json`, old-request supersede, fresh replacement approval request/snapshot/action hash, and risk reroute metadata.
- Added API validation and response fields for respond/edit, plus graph routing from edit results back to risk validation instead of action draft.

## Task Commits

1. **Task 1: Add needs_info and edit tests** - `15162b0` (test)
2. **Task 2: Implement respond and attach_info commands in ApprovalService** - `4b7ab76` (feat)
3. **Task 3: Implement edit command and API/routing support** - `fe9555b` (feat)

## Files Created/Modified

- `tests/approvals/test_needs_info_resume.py` - New focused APPROVAL-02 service tests for respond, attach_info, edit, stale revisions, and supersede behavior.
- `src/approvals/schemas.py` - Added `ApprovalInfoCommand`, `ApprovalInfoResult`, and optional trusted result fields for clarification/supersede/edit reroutes.
- `src/approvals/repository.py` - Added pending assignment lock helper used by `attach_info`.
- `src/approvals/service.py` - Implemented respond, attach_info, same-revision revalidation, replacement revision creation, and edit supersede/reroute semantics.
- `src/api/schemas/approvals.py` - Added respond/edit body validation and response fields for clarification and replacement revision refs.
- `src/api/routers/approvals.py` - Exposes new response fields and resumes the graph only for action/final decisions, not edit or needs_info.
- `src/agent/graph.py` - Routes trusted edit/superseded results to `assess_risk_and_approval`.
- `tests/test_approval_api.py` - Added respond/edit API validation and no-action-resume coverage.
- `tests/test_graph_routing.py` - Added edit risk-reroute routing coverage.
- `tests/agent/test_graph.py` - Updated router edge-key expectations for the new edit route.

## Verification

- `uv run pytest tests/approvals/test_needs_info_resume.py tests/test_approval_api.py tests/test_graph_routing.py -q --tb=short` - **PASS**: 60 passed, 1 existing LangGraph warning.
- `uv run pytest tests/approvals/test_service_transitions.py tests/approvals/test_hash_binding.py -q --tb=short` - **PASS**: 23 passed, 1 existing LangGraph warning.
- `uv run ruff check src/approvals src/api/schemas/approvals.py src/api/routers/approvals.py src/agent/routing.py tests/approvals/test_needs_info_resume.py` - **PASS**.

## Decisions Made

- `respond` is a safe interruption path: it stores reviewer text in `approval_decisions.response_text`, moves the request to `needs_info`, binds `clarification_request_id`, and returns no graph resume payload.
- `attach_info` treats material changes conservatively: payload/evidence/config changes supersede the old request and create a fresh pending revision with new hashes; non-material info only revalidates by bumping versions.
- `edit` creates a replacement candidate and risk-reroute metadata but never approves the edited action or sends the old approval revision to action draft.
- The route-after-approval implementation target is `src/agent/graph.py`; `src/agent/routing.py` does not own that function in this codebase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Normalized replacement snapshot inputs for attach_info**
- **Found during:** Task 2 (Implement respond and attach_info commands)
- **Issue:** Replacement revision snapshots initially used a raw `datetime.now(UTC)` and Pydantic `EvidenceRefV1.model_dump()` output, causing fixed-millisecond timestamp and nullable `score` hash failures.
- **Fix:** Added fixed-millisecond timestamp normalization and used canonical evidence projections when building replacement proposed actions.
- **Files modified:** `src/approvals/service.py`
- **Verification:** `uv run pytest tests/approvals/test_needs_info_resume.py -k "respond or attach_info" -q --tb=short` passed.
- **Committed in:** `4b7ab76`

**2. [Rule 1 - Bug] Used serializable Pydantic custom errors for API validation**
- **Found during:** Task 3 (Implement edit command and API/routing support)
- **Issue:** Plain `ValueError` from the API body validator produced a FastAPI 422 validation error containing an unserializable exception object under the project's custom error handler.
- **Fix:** Switched respond/edit body validation to `PydanticCustomError`.
- **Files modified:** `src/api/schemas/approvals.py`
- **Verification:** `uv run pytest tests/approvals/test_needs_info_resume.py tests/test_approval_api.py tests/test_graph_routing.py -q --tb=short` passed.
- **Committed in:** `fe9555b`

**3. [Rule 3 - Blocking] Applied route_after_approval changes to the actual graph owner**
- **Found during:** Task 3 (Implement edit command and API/routing support)
- **Issue:** The plan listed `src/agent/routing.py`, but `route_after_approval` is implemented and wired in `src/agent/graph.py`.
- **Fix:** Updated `src/agent/graph.py` and the graph edge-key test to add the edit risk-reroute edge.
- **Files modified:** `src/agent/graph.py`, `tests/agent/test_graph.py`
- **Verification:** The plan graph routing pytest and ruff checks passed.
- **Committed in:** `fe9555b`

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All fixes were required to satisfy the specified APPROVAL-02 semantics and existing project validation/routing ownership. No external execution behavior was added.

## Issues Encountered

- Focused replacement-revision tests exposed canonical snapshot input normalization requirements; fixed in Task 2 before proceeding.
- API validation initially returned the correct 422 class but failed project error serialization; fixed in Task 3.
- Verification emits one existing LangGraph pending-deprecation warning from the dependency stack; all requested checks pass.

## Known Stubs

None - stub scan found only typed optional defaults, normal empty test fixtures, and existing fallback values. No placeholder behavior or unwired UI/data path was introduced.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the touched approval/API/routing surfaces are the planned threat-model surfaces for APPROVAL-02 and were covered by the verification suites.

## Self-Check: PASSED

- Found `.planning/phases/13-approval-state-machine/13-05-SUMMARY.md`.
- Found `tests/approvals/test_needs_info_resume.py`.
- Verified task commits `15162b0`, `4b7ab76`, and `fe9555b` resolve in git history.
- Working tree contained only this summary before metadata updates.

## Next Phase Readiness

Plan 13-06 can add approval event envelope/redaction coverage on top of durable respond/edit/attach_info decisions and replacement revision refs. Plan 13-07 can still quarantine legacy paths and add static owner-boundary tests.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
