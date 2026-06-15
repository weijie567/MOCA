---
phase: 13-approval-state-machine
fixed_at: 2026-06-15T15:03:07Z
review_path: .planning/phases/13-approval-state-machine/13-REVIEW.md
review_commit: ae93763
fix_scope: critical_warning
findings_in_scope: 1
fixed: 1
skipped: 0
iteration: 1
status: all_fixed
verification:
  ruff: passed
  api_event_tests: "45 passed, 1 warning"
  integration_tests: "5 passed, 1 warning"
  phase13_tests: "216 passed, 1 warning"
---

# Phase 13: Code Review Fix Report

**Status:** all_fixed
**Findings in scope:** 1 warning
**Fixed:** 1
**Skipped:** 0

## Fixes Applied

### WR-01: Graph resume can still advance checkpoint before action/run side effects commit

Fixed in `src/api/routers/approvals.py` and `src/approvals/events.py`.

`decide_approval()` now treats graph resume as a recoverable lifecycle after the approval decision commit:

- Commits the approval decision before any graph resume attempt.
- Persists an `approval_resumed` attempt marker keyed by `approval_id` + `revision` before invoking LangGraph.
- Commits graph resume side effects together with a completed marker.
- Rolls back failed graph side effects and persists a failed marker when the final resume transaction fails.
- Allows the same `decide` endpoint to retry a terminal approval only when the latest resume marker is incomplete and the run side effects are still unfinished.

The resume path also reconciles approved action side effects: if LangGraph has already checkpointed past `execute_action` but the action draft is missing, it reruns the deterministic `execute_action` node against the trusted approval payload. The existing action draft idempotency key prevents duplicate drafts.

Regression coverage:

- `tests/test_approval_api.py::test_decide_commits_approval_decision_before_graph_resume`
- `tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval`
- `tests/test_approval_integration.py::test_idempotent_approve_does_not_duplicate_action_draft`

## Verification

- `uv run ruff check src/api/routers/approvals.py src/approvals/events.py src/approvals/service.py src/approvals/sla_scanner.py tests/test_approval_api.py tests/approvals/test_events.py tests/approvals/test_service_transitions.py tests/approvals/test_sla_scanner.py` - passed.
- `uv run pytest tests/test_approval_api.py tests/approvals/test_events.py -q --tb=short` - 45 passed, 1 upstream LangGraph warning.
- `uv run pytest tests/test_approval_integration.py -q --tb=short` - 5 passed, 1 upstream LangGraph warning.
- `uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_events.py -q --tb=short` - 216 passed, 1 upstream LangGraph warning.
