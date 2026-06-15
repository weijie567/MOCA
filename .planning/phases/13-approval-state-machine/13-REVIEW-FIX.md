---
phase: 13-approval-state-machine
fixed_at: 2026-06-15T14:25:13Z
review_path: .planning/phases/13-approval-state-machine/13-REVIEW.md
review_commit: f67485e
fix_scope: critical_warning
findings_in_scope: 4
fixed: 4
skipped: 0
iteration: 1
status: all_fixed
verification:
  ruff: passed
  focused_tests: "43 passed, 1 warning"
  phase13_tests: "215 passed, 1 warning"
---

# Phase 13: Code Review Fix Report

**Status:** all_fixed
**Findings in scope:** 4 warnings
**Fixed:** 4
**Skipped:** 0

## Fixes Applied

### WR-01: Graph resume checkpoint and approval decision are not in the same transaction

Fixed in `src/api/routers/approvals.py`.

`decide_approval()` now commits the approval decision transaction before invoking `graph.ainvoke(...)`. Graph resume still uses a second transaction for run/action updates, but the approval decision can no longer roll back after the LangGraph checkpointer has advanced. This makes the failure boundary explicit: approval decision persistence happens before resume side effects.

Regression coverage:
- `tests/test_approval_api.py::test_decide_commits_approval_decision_before_graph_resume`

### WR-02: Broad result-projection `ValidationError` mapping hides schema failures

Fixed in `src/approvals/service.py`.

Malformed edit/info material still maps to `approval_not_executable`, but result projection failures from `TrustedApprovalResultV1` or `ApprovalInfoResult` now map to `approval_invalid_result`. This keeps input executability errors separate from internal result-schema regressions.

Regression coverage:
- `tests/approvals/test_service_transitions.py::test_result_projection_validation_error_is_not_reported_as_non_executable`
- Existing malformed payload tests still assert `approval_not_executable`.

### WR-03: Reviewer reason is not returned in approval API responses

Fixed in `src/approvals/service.py` and covered in `tests/test_approval_api.py`.

`ApprovalService._result()` now persists `request.reason = reason` alongside `decision`, `decided_by`, and `decided_at`, so `_to_response()` can return the reviewer-provided reason.

Regression coverage:
- `tests/test_approval_api.py::test_decide_reject_resumes_graph_with_trusted_rejected_result`

### WR-04: SLA scanner can expire legacy/non-executable requests

Fixed in `src/approvals/sla_scanner.py` and `src/approvals/service.py`.

`ApprovalSlaScanner.scan()` now filters for executable v2 approvals only, matching `list_pending_requests()`. `ApprovalService.expire_due_request()` also asserts executable v2 request state before transitioning, so direct service calls fail closed for legacy rows.

Regression coverage:
- `tests/approvals/test_sla_scanner.py::test_enabled_scanner_skips_legacy_non_executable_requests`

## Additional Cleanup

- Reused a single `ApprovalService` instance in `attach_approval_info()`, addressing the related IN-01 maintainability note without changing behavior.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py src/approvals/service.py src/approvals/sla_scanner.py tests/test_approval_api.py tests/approvals/test_service_transitions.py tests/approvals/test_sla_scanner.py` — passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/approvals/test_service_transitions.py tests/approvals/test_sla_scanner.py -q --tb=short` — 43 passed, 1 upstream LangGraph warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_events.py -q --tb=short` — 215 passed, 1 upstream LangGraph warning.
