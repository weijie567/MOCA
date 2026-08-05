---
phase: 59-approval-resume-terminal-memory-finalization
source_review: 59-REVIEW.md
status: fixed
fixed_findings:
  warning: 2
  total: 2
completed: 2026-07-08
---

# Phase 59 Code Review Fix

## Summary

`59-REVIEW.md` reported two warning-level issues in the approval-resume terminal finalizer path. Both were confirmed against source code and fixed before phase completion.

## Fixes

### WR-01: Completed resume event could be recorded without durable finalizer evidence

- Added `suppress_errors` to `persist_agent_run_memory_finalize_trace_steps(...)`; normal `agent-runs` keeps suppressing trace append failures, while approval resume calls it with `suppress_errors=False`.
- Approval resume now commits terminal assistant/thread summary/session memory/CWC surfaces before requiring finalizer trace persistence, so trace failure does not roll back CWC rows.
- A trace persistence failure now records `approval_resumed/failed` and returns the existing retryable HTTP error instead of recording `approval_resumed/completed`.
- Added regression coverage proving terminal surfaces remain durable, finalizer trace is absent, and no completed resume event is recorded when finalizer trace persistence fails.

### WR-02: Completed-run retry reconciliation could double-write completed events under concurrent retry

- Added `_lock_approval_request_for_resume(...)` using `SELECT ... FOR UPDATE`.
- Added `_record_resume_completed_event_once(...)`, which locks the approval row, rechecks latest same-key resume status inside the lock, and skips writing when another caller already recorded `completed`.
- Added regression coverage for the locked recheck path.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` -> `37 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_can_fail_closed tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` -> `5 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `88 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `196 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` -> pass
