---
phase: 04-approval-workflow-audit
source_review: 04-REVIEW.md
status: fixed
fixed: 2026-05-16
---

# Phase 4 Code Review Fixes

## Fixed Findings

- **CR-01:** `ApprovalRepository.decide()` now returns `(approval, transitioned)` from inside the row-locked decision path. The approval API adds decision events and resumes the graph only when `transitioned` is true, preventing duplicate graph resumes for idempotent or racing same-direction decisions.
- **WR-01:** Chat interrupt persistence now appends an explicit `approval_gate` trace step with `interrupted` status when the LangGraph state snapshot does not already include it.
- **WR-02:** Trace timeline and trace approval payloads now sanitize `proposed_action` to `action_type`, `amount`, and `currency`, avoiding model-derived reasoning and target identifiers in trace replay.
- **IN-01:** Approval resume latency is added to the already persisted interrupted run latency instead of overwriting it with resume-only latency.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py src/api/routers/agent.py src/api/routers/traces.py src/repositories/approval_repo.py src/repositories/trace_repo.py tests/test_approval_models.py tests/test_approval_api.py tests/test_trace_api.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_models.py tests/test_approval_api.py tests/test_trace_api.py -q --tb=short` - 35 passed, 1 warning
