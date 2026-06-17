---
phase: 14-demo-action-executor-boundary
plan: 02
subsystem: actions
tags: [actions, idempotency, approvals, demo-mode, langgraph-state]
requires:
  - phase: 14-demo-action-executor-boundary
    provides: action_draft.v2 ORM columns, DraftOutcomeV1 schema, and tenant-scoped draft idempotency uniqueness from 14-01
  - phase: 13-approval-state-machine
    provides: ActionSafetySnapshot, ApprovalRequest revision, and exact hash binding fields
provides:
  - exact-binding ActionDraftStore and ActionDraftRepository create-or-get semantics
  - ActionService-owned draft idempotency key construction
  - missing target_id fail-closed validation before draft persistence
  - draft_outcome.v1 and action_draft service success payloads
  - AgentState action_draft, draft_outcome, and execution_mode fields reset per turn
affects: [phase-14, phase-15, action-drafts, approval-resume, replay]
tech-stack:
  added: []
  patterns: [service-owned idempotency, exact binding reuse, draft-only compatibility output]
key-files:
  created:
    - .planning/phases/14-demo-action-executor-boundary/14-02-SUMMARY.md
  modified:
    - src/actions/drafts.py
    - src/repositories/action_draft_repo.py
    - src/actions/service.py
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - tests/actions/test_action_draft_v2.py
    - tests/agent/test_tools/test_create_coupon_grant_draft.py
    - tests/agent/test_nodes/test_receive_request.py
key-decisions:
  - "ActionService owns the final draft idempotency key; caller-provided keys are ignored for persistence."
  - "Auto-allowed drafts use the exact auto_allowed marker; approval-backed drafts use approval_revision_{revision} plus approval_request/{id}@rev{revision}."
  - "action_result remains only a deprecated draft-only compatibility payload and does not use status=success inside the service result."
patterns-established:
  - "Repository/store idempotent reuse checks tenant, run, action type, target id, action payload hash, safety snapshot ref, and safety snapshot hash before returning an existing draft."
  - "Draft creation service responses expose canonical action_draft and draft_outcome data while preserving legacy flat draft_id/status fields."
requirements-completed: [DEMO-01, DEMO-02]
duration: 29 min
completed: 2026-06-16
---

# Phase 14 Plan 02: Action Service Draft Boundary Summary

**Service-owned action draft keys with exact snapshot binding, durable draft outcomes, and per-turn draft state reset**

## Performance

- **Duration:** 29 min
- **Started:** 2026-06-15T22:43:21Z
- **Completed:** 2026-06-15T23:11:50Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Enforced exact binding reuse in `ActionDraftStore` and `ActionDraftRepository`; an idempotency key hit with a mismatched safety snapshot hash now raises `idempotency_binding_conflict`.
- Moved final idempotency key construction into `ActionService` with the shape `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}`.
- Added `TARGET_ID_REQUIRED` validation so missing or blank `payload["target_id"]` cannot collapse distinct drafts into an unsafe key.
- Added service success payloads for `action_draft`, `draft_outcome`, and `execution_mode`, with `draft_outcome.status="not_executed_demo"` and `external_side_effect=false`.
- Added `AgentState.action_draft`, `AgentState.draft_outcome`, and `AgentState.execution_mode`, and reset those fields in `receive_request` on each turn.

## Task Commits

1. **Task 1 RED: Exact binding tests** - `51676cf` (test)
2. **Task 1 GREEN: Exact binding store/repository reuse** - `9fec4d7` (feat)
3. **Tasks 2-3: Service-owned key and state reset** - `19f417c` (feat)

## Files Created/Modified

- `src/actions/drafts.py` - Store signature now requires Phase 14 binding, outcome, lifecycle, and retention fields.
- `src/repositories/action_draft_repo.py` - Existing-key reuse validates exact tenant/run/action/target/payload/snapshot binding.
- `src/actions/service.py` - Validates `target_id`, builds trusted draft idempotency keys, persists v2 draft fields, and returns `action_draft`/`draft_outcome`.
- `src/agent/state.py` - Adds `action_draft`, `draft_outcome`, and `execution_mode` state fields.
- `src/agent/nodes/receive_request.py` - Resets stale draft state at turn start.
- `tests/actions/test_action_draft_v2.py` - Covers exact reuse and mismatched snapshot conflict behavior.
- `tests/agent/test_tools/test_create_coupon_grant_draft.py` - Covers target validation, auto marker, approval revision marker, caller-key ignoring, and draft outcome response semantics.
- `tests/agent/test_nodes/test_receive_request.py` - Covers per-turn draft state reset.

## Decisions Made

- Caller-supplied idempotency keys are not part of the persisted draft identity. They may exist in older tool context compatibility paths, but `ActionService` ignores them when constructing the durable key.
- Cross-tenant reuse of the same caller key is not a conflict because the durable key is tenant-scoped and service-owned.
- Approval-backed draft keys use the approved request revision marker, while `approval_revision_ref` stores the request/revision reference used by downstream replay and audit work.

## Deviations from Plan

None - plan executed as written.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- The first pytest run inside the filesystem/network sandbox could not open the local PostgreSQL socket (`PermissionError: [Errno 1] Operation not permitted`). The same test command passed after running with approved local database access.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_create_coupon_grant_draft.py tests/actions/test_action_draft_v2.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` - passed, 31 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/service.py src/tools/executors/action.py src/agent/state.py src/agent/nodes/receive_request.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/agent/test_nodes/test_receive_request.py tests/actions/test_action_draft_v2.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_unified_tool_manager.py -q --tb=short` - passed, 22 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py -q --tb=short` - passed, 18 tests.
- Acceptance `rg` checks for `TARGET_ID_REQUIRED`, `auto_allowed`, `approval_revision_ref`, service-owned idempotency key construction, absent `unknown` fallback in service/executor, and state reset fields all passed.

## Self-Check: PASSED

- Key files modified by this plan exist on disk.
- Plan-level pytest and ruff gates passed.
- `14-02-SUMMARY.md` documents the recovery point and the existing Task 1 commits from before interruption.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `14-03-PLAN.md`: canonical `action_draft` graph node naming, tool allowlist update, and `execute_action` shim quarantine can now build on a service boundary that owns draft identity and returns draft outcome data.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
