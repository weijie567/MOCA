---
phase: 34-approval-and-actiondraft-boundary-hardening
plan: 34-03
subsystem: approval-service-api-scope
tags: [approval-service, approval-api, manager-scope, trusted-resume, target-merchant]

requires:
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-01
    provides: Phase 34 approval binding contracts and persistence columns
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-02
    provides: risk_gate approval_plan and durable binding state
provides:
  - ApprovalService/repository persistence and trusted resume propagation for Phase 34 binding fields
  - approval_gate interrupt payload pass-through for structured approval_plan and safe binding refs
  - same-merchant manager approval list/get/decide access with missing/cross-target fail-closed behavior
affects: [approval-service, approval-api, approval-gate, action-draft-resume, manager-scope]

tech-stack:
  added: []
  patterns: [TDD, persisted-binding projection, same-merchant authorization, no-wildcard resume]

key-files:
  created: []
  modified:
    - src/approvals/repository.py
    - src/approvals/service.py
    - src/approvals/policy.py
    - src/agent/nodes/approval_gate.py
    - src/api/routers/approvals.py
    - src/api/schemas/approvals.py
    - tests/approvals/test_service_transitions.py
    - tests/test_approval_api.py
    - tests/test_approval_gate.py

key-decisions:
  - "ApprovalService copies Phase 34 binding fields only from ApprovalRequestCreateCommand and never reconstructs them from prompt text, memory, final response, or raw tool data."
  - "Manager approval access is restored only through persisted `ApprovalRequest.target_merchant_id == user.merchant_id`."
  - "Human approval resume injects `tool:create_coupon_grant_draft` permission without adding `server_merchant_scope`."

patterns-established:
  - "Trusted approval resume payloads are projected from persisted request binding fields for the active revision."
  - "API list filters manager-visible approvals rather than leaking out-of-scope approval ids."

requirements-completed: [APF-15, APF-16]

duration: 35 min
completed: 2026-06-29
---

# Phase 34 Plan 03: Approval Service/API Scope Summary

**Approval requests and trusted resume payloads now carry persisted Phase 34 bindings, and manager approval access is restored only for same-merchant targets**

## Performance

- **Duration:** 35 min
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Extended `ApprovalRepository.create_request_with_single_level(...)` and `ApprovalService.create_request(...)` to persist target merchant, business fact refs, verified evidence refs, claim verification refs/summaries, risk decision refs/payloads, and approval idempotency keys.
- Updated approval create/decision result and recoverable retry resume payloads to include exact persisted Phase 34 binding fields.
- Updated `approval_gate` to pass through structured `approval_plan` and safe binding refs, and to fail closed when a required approval plan lacks a trusted idempotency key.
- Restored manager review role support in approval policy/API while enforcing same-merchant access with persisted `target_merchant_id`.
- Kept approval resume permission injection scoped to `server_tool_permissions=[tool:create_coupon_grant_draft]` without `server_merchant_scope`.

## Task Commits

1. **Task 1 RED: Approval binding propagation tests** - `bae1356` (test)
2. **Task 1 GREEN: Approval binding propagation** - `727ae67` (feat)
3. **Task 2 RED: Manager approval scope tests** - `0b77fc4` (test)
4. **Task 2 GREEN: Same-merchant manager approval scope** - `0108ef5` (feat)

## Files Created/Modified

- `src/approvals/repository.py` - Persists Phase 34 binding fields on approval requests.
- `src/approvals/service.py` - Copies command bindings into persistence and trusted resume results.
- `src/approvals/policy.py` - Allows `manager` as an approval reviewer role.
- `src/agent/nodes/approval_gate.py` - Passes structured approval plan/binding refs and validates idempotency before interrupt.
- `src/api/routers/approvals.py` - Enforces same-merchant approval scope and projects binding fields in API/resume paths.
- `src/api/schemas/approvals.py` - Returns Phase 34 binding fields in approval API responses.
- `tests/approvals/test_service_transitions.py` - Service persistence/resume and manager role transition coverage.
- `tests/test_approval_api.py` - Same/cross/missing-target manager API coverage and binding-aware approval fixtures.
- `tests/test_approval_gate.py` - Approval gate structured payload and fail-closed idempotency coverage.

## Decisions Made

- Missing `target_merchant_id` is invisible to managers in list and forbidden for get/decide.
- Cross-merchant approvals return 403 for manager get/decide and are filtered from list.
- API retry resume reuses the same persisted binding projection as normal decision resume.

## Deviations from Plan

None - plan executed as written. The API-side action draft reconciliation path required a safe `claim_verification_bundle` placeholder when replaying from a fake graph state in tests, because the real graph checkpoint would normally retain prior claim state.

## Issues Encountered

- Existing approval API fixtures created pre-Phase-34 approvals without target merchant binding; fixtures were updated to create binding-aware approvals by default, with explicit opt-out for missing-target tests.
- Pydantic model fields return canonical typed objects in service results, so tests compare JSON dumps for exact persisted equality.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/approvals/test_service_transitions.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/test_approval_gate.py -q --tb=short` -> `71 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/approvals/schemas.py src/approvals/repository.py src/approvals/service.py src/approvals/policy.py src/agent/nodes/approval_gate.py src/api/routers/approvals.py src/api/schemas/approvals.py tests/test_approval_api.py tests/approvals/test_service_transitions.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/test_approval_gate.py` -> passed
- `git diff --check` -> passed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 34-04. Agent-runs approval interrupt bridge can now consume structured approval payloads and pass Phase 34 binding fields into `ApprovalRequestCreateCommand`.

## Self-Check: PASSED

- Focused pytest and ruff checks pass through the MOCA-approved `uv run` entrypoint.
- Approval binding fields are present in repository, service, and approval_gate.
- Approval API has `_assert_approval_scope` and no `server_merchant_scope` usage.
- No `requested_by` merchant inference pattern is present in approval code or tests.

---
*Phase: 34-approval-and-actiondraft-boundary-hardening*
*Completed: 2026-06-29*
