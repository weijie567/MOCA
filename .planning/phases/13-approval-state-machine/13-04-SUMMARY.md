---
phase: 13-approval-state-machine
plan: 04
subsystem: approvals
tags: [approval-service, fastapi, langgraph, action-safety-snapshot, trusted-resume]

requires:
  - phase: 13-approval-state-machine
    provides: CanonicalHashProfile, ActionSafetySnapshot persistence, and ApprovalService transitions from Plans 13-01 through 13-03
provides:
  - Approval decision API cut over to ApprovalDecisionCommand and ApprovalService.decide
  - Chat and SSE interrupt approval creation through ApprovalService.create_request
  - Trusted approval_result.v1 graph routing with hash/version fail-closed guards
  - Risk-node ActionSafetySnapshot persistence for approval-required and auto-allowed actions
affects: [phase-13-approval-state-machine, phase-14-demo-action-boundary, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - API routers authenticate/parse only, then call ApprovalService with server-side command objects
    - LangGraph approval resumes are accepted only from service-produced approval_result.v1 payloads
    - Risk node persists durable ActionSafetySnapshot rows before routing to approval or action draft paths

key-files:
  created:
    - .planning/phases/13-approval-state-machine/13-04-SUMMARY.md
  modified:
    - src/api/schemas/approvals.py
    - src/api/routers/approvals.py
    - src/api/routers/agent.py
    - src/api/routers/agent_runs.py
    - src/approvals/schemas.py
    - src/approvals/service.py
    - src/agent/state.py
    - src/agent/graph.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/approval_gate.py
    - src/agent/nodes/execute_action.py
    - src/agent/nodes/final_response.py
    - tests/test_approval_api.py
    - tests/test_approval_integration.py
    - tests/test_approval_gate.py
    - tests/test_graph_routing.py
    - tests/approvals/test_service_transitions.py

key-decisions:
  - "Approval request creation from chat/SSE interrupts reuses ApprovalService.create_request and fails closed when executable snapshot/hash fields are missing."
  - "ApprovalService.create_request can validate and reuse a durable ActionSafetySnapshot row already persisted by the risk node."
  - "Graph routing treats approval_result.v1 as the only trusted approval resume payload and checks exact action/snapshot hashes before action draft routing."

patterns-established:
  - "Interrupt handlers return service wait payloads containing revision refs, expected versions, action_payload_hash, safety_snapshot_ref, safety_snapshot_hash, and allowed decision types."
  - "approval_gate interrupt payloads are display-only and never create approval truth."
  - "Auto-allowed action candidates require a verified durable action_safety_snapshots row before routing to the action draft node."

requirements-completed:
  - APPROVAL-01
  - APPROVAL-03
  - SNAPSHOT-01

duration: 34 min
completed: 2026-06-15
---

# Phase 13 Plan 04: Approval API and Graph Cutover Summary

**Approval API, chat/SSE interrupts, and LangGraph approval routing now use ApprovalService commands, durable ActionSafetySnapshot refs, and trusted approval_result.v1 resumes**

## Performance

- **Duration:** 34 min observed from first 13-04 commit to completion; continuation after compact disconnect resumed at 2026-06-15T08:18:53Z and ran 21 min.
- **Started:** 2026-06-15T08:05:37Z
- **Completed:** 2026-06-15T08:39:45Z
- **Tasks:** 4
- **Files modified:** 17

## Accomplishments

- Rewrote approval API and graph tests around server-side command construction, service-produced resume payloads, stale/self/cross-tenant failures, and untrusted approval-result fail-closed routing.
- Cut `src/api/routers/approvals.py` over to `ApprovalDecisionCommand` and `ApprovalService.decide`; graph resume now wraps only `ApprovalDecisionResult.resume_payload`.
- Replaced legacy chat/SSE `src.repositories.approval_repo` creation with `ApprovalService.create_request`, including fail-closed behavior for missing action/snapshot hashes.
- Updated risk, approval gate, action guard, final response, and graph routing so approval-required and auto-allowed action candidates carry verified durable snapshot refs before action paths.

## Task Commits

1. **Task 1: Rewrite API and graph tests around service-produced commands/results** - `5474ac0` (test)
2. **Task 2: Update approval API schemas and decide route** - `291c9f5` (feat)
3. **Task 3: Cut agent and streaming interrupt handlers over to ApprovalService.create_request** - `2373f0f` (feat)
4. **Task 4: Update graph/state/routing/approval_gate for trusted approval_result.v1** - `e9a1fbd` (feat)

## Files Created/Modified

- `src/api/schemas/approvals.py` - Decision body DTO with decision type, expected versions, expected revision, and hash guards.
- `src/api/routers/approvals.py` - Thin ApprovalService decision adapter and service-produced graph resume wrapper.
- `src/api/routers/agent.py` - Non-streaming interrupt path now delegates approval request creation to the service helper.
- `src/api/routers/agent_runs.py` - SSE interrupt path validates executable snapshot fields and creates service-backed wait payloads.
- `src/approvals/schemas.py` - Create command accepts optional durable snapshot refs/hashes; result schemas carry safe reason text.
- `src/approvals/service.py` - `create_request` validates/reuses pre-persisted ActionSafetySnapshot rows or persists through the snapshot owner helper.
- `src/agent/state.py` - Added approval revision and action/snapshot hash fields.
- `src/agent/graph.py` - Risk and approval routers fail closed unless trusted hashes and snapshot verification are present.
- `src/agent/nodes/assess_risk_and_approval.py` - Builds canonical proposed_action.v1, persists ActionSafetySnapshot rows, and exposes verified refs.
- `src/agent/nodes/approval_gate.py` - Display-only interrupt payload with revision refs/hashes and trusted resume validation.
- `src/agent/nodes/execute_action.py` - Accepts `approval_result.v1` approved decisions as the action guard.
- `src/agent/nodes/final_response.py` - Uses `decision_type` and service reason text for approved/rejected resume messaging.
- `tests/test_approval_api.py` - Service command/resume, conflict, self-approval, and tenant-boundary API tests.
- `tests/test_approval_integration.py` - End-to-end approval interrupt/resume integration tests with wait-payload hashes.
- `tests/test_approval_gate.py` - Display-only payload and trusted resume tests.
- `tests/test_graph_routing.py` - Trusted routing, hash mismatch, auto-allowed snapshot persistence, and missing-row fail-closed tests.
- `tests/approvals/test_service_transitions.py` - Updated service result expectations for trusted reason propagation.

## Verification

- `uv run pytest tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_gate.py tests/test_graph_routing.py -q --tb=short` - **PASS**: 51 passed, 1 existing LangGraph warning.
- `uv run pytest tests/approvals/test_service_transitions.py tests/approvals/test_hash_binding.py -q --tb=short` - **PASS**: 23 passed, 1 existing LangGraph warning.
- `uv run ruff check src/api/routers/approvals.py src/api/routers/agent.py src/api/routers/agent_runs.py src/api/schemas/approvals.py src/agent` - **PASS**.
- Acceptance greps passed for service command fields, absence of `ApprovalRepository` in agent routers, `approval_result.v1`, snapshot refs/hashes, auto-allowed snapshot tests, and display-only `approval_gate` interrupt payloads.

## Decisions Made

- Centralized chat and SSE interrupt approval creation in a shared router helper so both paths validate the same executable fields and return the same service wait payload shape.
- Allowed `ApprovalService.create_request` to validate/reuse an existing durable snapshot row, avoiding a second snapshot with different ref/hash after the risk node has already persisted one.
- Kept graph routing side-effect-free: the risk node persists/verifies snapshots, while routers only inspect trusted state and hashes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Reused pre-persisted snapshots during approval request creation**
- **Found during:** Task 4 (Update graph/state/routing/approval_gate for trusted approval_result.v1)
- **Issue:** The plan requires the risk node to persist an ActionSafetySnapshot row before routing, but `ApprovalService.create_request` always persisted a fresh snapshot, which would produce a different ref/hash from the interrupt payload.
- **Fix:** Extended `ApprovalRequestCreateCommand` with optional `safety_snapshot_ref` and `safety_snapshot_hash`; `ApprovalService.create_request` now validates and reuses an existing row when refs are supplied.
- **Files modified:** `src/approvals/schemas.py`, `src/approvals/service.py`, `src/api/routers/agent_runs.py`, `src/api/routers/agent.py`
- **Verification:** Plan pytest suites and ruff passed.
- **Committed in:** `2373f0f`

**2. [Rule 1 - Bug] Updated action/final response nodes for approval_result.v1**
- **Found during:** Task 4 (Update graph/state/routing/approval_gate for trusted approval_result.v1)
- **Issue:** Approved service resumes use `decision_type`, not legacy `decision`; action drafting could be blocked or final wording could still say approval was needed, and rejected decisions lost the user-visible reason.
- **Fix:** Updated `execute_action` to accept trusted `decision_type in {accept, approve}` with approved status; updated `final_response` to read `decision_type` and service reason text.
- **Files modified:** `src/agent/nodes/execute_action.py`, `src/agent/nodes/final_response.py`, `src/approvals/schemas.py`, `src/approvals/service.py`
- **Verification:** `tests/test_approval_integration.py tests/test_approval_gate.py` and full plan verification passed.
- **Committed in:** `e9a1fbd`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both changes were required to preserve the plan's trusted snapshot/hash and approval_result.v1 contracts. No Phase 14 external execution behavior was added.

## Issues Encountered

- This was a continuation after a compact disconnect. Existing committed work (`5474ac0`, `291c9f5`) was inspected and preserved; no committed changes were reverted or redone.
- Initial sandboxed DB-backed pytest was blocked by local Postgres socket permissions. The same verification commands were rerun with approved local DB access and passed.
- Focused pytest commands emit one existing LangGraph pending-deprecation warning from the dependency stack; tests pass.

## Known Stubs

None - stub scan found only normal empty-list/default handling and fallback strings, not placeholder behavior or unwired UI/data paths.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - new security-relevant approval/API/snapshot surfaces are covered by the plan threat model and verified by the cutover tests.

## Self-Check: PASSED

- All four 13-04 tasks have committed implementation or test coverage.
- Verification commands listed above passed.
- Legacy approval repository decision/create paths were removed from the touched router and graph boundaries.
- Continuation preserved prior committed work after compact disconnect and left the working tree clean except for this SUMMARY before docs commit.

## Next Phase Readiness

Plan 13-05 can build needs_info, edit, and attach_info revalidation on top of the trusted ApprovalService command boundary and graph resume contract. Plan 13-07 still owns static boundary tests and legacy repository quarantine/deletion.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
