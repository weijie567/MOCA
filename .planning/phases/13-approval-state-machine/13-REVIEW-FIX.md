---
phase: 13-approval-state-machine
fixed_at: 2026-06-15T13:43:26Z
review_path: .planning/phases/13-approval-state-machine/13-REVIEW.md
fix_scope: critical_warning
findings_in_scope: 3
fixed: 3
skipped: 0
iteration: 1
status: all_fixed
verification:
  ruff: passed
  focused_tests: "56 passed, 1 warning"
  phase13_tests: "212 passed, 1 warning"
---

# Phase 13: Code Review Fix Report

**Status:** all_fixed
**Findings in scope:** 3 warnings
**Fixed:** 3
**Skipped:** 0

## Fixes Applied

### WR-01: Malformed edit/info payloads can escape as 500s

Fixed in `src/approvals/service.py`.

`ApprovalService.decide()` and `ApprovalService.attach_info()` now translate snapshot persistence, canonical hash, and Pydantic validation failures into `ApprovalTransitionError("approval_not_executable")`. API callers already map that code to a controlled conflict response, so malformed replacement action or evidence payloads no longer escape as generic server errors.

Regression coverage:
- `tests/approvals/test_service_transitions.py::test_malformed_edit_action_returns_transition_error_without_orphans`
- `tests/approvals/test_needs_info_resume.py::test_attach_info_malformed_changed_payload_fails_closed_without_orphans`

### WR-02: Pending queue includes legacy non-executable rows

Fixed in `src/approvals/service.py`.

`ApprovalService.list_pending_requests()` now returns only executable v2 approval rows by requiring `schema_version == "approval_request.v2"` and `legacy_non_executable is false` in addition to tenant, pending status, and expiry filters.

Regression coverage:
- `tests/test_approval_models.py::test_list_pending_requests_excludes_expired_and_terminal_approvals`
- `tests/test_approval_api.py::test_list_pending_approvals_returns_unexpired_pending_only`

### WR-03: Approval read endpoints skip current-role enforcement

Fixed in `src/api/routers/approvals.py`.

Approval read endpoints now call the same current DB-role guard used by decision and info endpoints. A token with `approvals:review` scope is no longer sufficient if the current `User.role` is not one of the approval reviewer roles.

Regression coverage:
- `tests/test_approval_api.py::test_get_approval_rejects_over_scoped_non_reviewer_token`
- `tests/test_approval_api.py::test_list_pending_approvals_rejects_over_scoped_non_reviewer_token`

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/approvals/service.py src/api/routers/approvals.py tests/approvals/test_service_transitions.py tests/approvals/test_needs_info_resume.py tests/test_approval_models.py tests/test_approval_api.py` — passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_service_transitions.py tests/approvals/test_needs_info_resume.py tests/test_approval_models.py tests/test_approval_api.py -q --tb=short` — 56 passed, 1 upstream LangGraph warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_events.py -q --tb=short` — 212 passed, 1 upstream LangGraph warning.
