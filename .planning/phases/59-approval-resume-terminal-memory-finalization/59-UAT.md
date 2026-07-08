---
status: complete
phase: 59-approval-resume-terminal-memory-finalization
source:
  - 59-01-SUMMARY.md
  - 59-02-SUMMARY.md
  - 59-03-SUMMARY.md
started: 2026-07-08T10:49:24Z
updated: 2026-07-08T10:49:24Z
mode: self-detected
---

## Current Test

[testing complete]

## Tests

### 1. Completed approval resume produces terminal user-visible memory surfaces
expected: Completed approval-resume runs persist the same terminal assistant message, thread summary, session-memory write, finalizer trace row, and CWC status surface as ordinary completed agent runs.
result: pass
evidence:
  - `tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer`

### 2. Interrupted and error approval resumes do not leak terminal surfaces
expected: Approval resumes that interrupt again or end in error leave no terminal assistant message, thread summary, session-memory event, CWC write, or finalizer trace row.
result: pass
evidence:
  - `tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt`
  - `tests/test_approval_api.py::test_approval_resume_error_skips_terminal_finalizer_surfaces`

### 3. Retry after partial terminal finalization is idempotent and fail-closed
expected: If completed-event recording fails after terminal surfaces are durable, retry records the missing completion without rerunning graph/action/finalizer side effects; finalizer trace failures fail closed without a completed event.
result: pass
evidence:
  - `tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval`
  - `tests/test_approval_api.py::test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces`
  - `tests/test_approval_api.py::test_completed_resume_reconciliation_rechecks_status_under_lock`

### 4. Terminal finalizer uses requester identity, not reviewer identity
expected: Trusted graph resume may use the reviewer/admin actor, but terminal assistant/thread/memory/CWC finalization binds to the original `AgentRun.user_id` requester.
result: pass
evidence:
  - `tests/test_agent_runs_api.py::test_build_agent_run_finalizer_input_state_uses_requester_identity`
  - `tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer`

### 5. Approval-marker sanitizer is terminal-only
expected: Completed terminal finalization strips approval markers only before session memory write; direct `memory_write(...)` calls with approval markers still skip as `not_completed_path`.
result: pass
evidence:
  - `tests/test_agent_runs_api.py::test_terminal_memory_write_state_strips_only_terminal_approval_markers`
  - `tests/agent/test_memory_write_node.py::test_memory_write_node_skips_approval_marked_states`

### 6. Finalizer trace rows are not duplicated
expected: Repeated finalizer trace persistence for the same run does not append duplicate `agent_run_memory_finalize` rows.
result: pass
evidence:
  - `tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent`

### 7. Phase gates remain clean after self-detected UAT
expected: Phase 59 review, verification, validation, and security artifacts all support completion; security has `threats_open: 0`.
result: pass
evidence:
  - `59-REVIEW.md` status is clean.
  - `59-VERIFICATION.md` status is passed with `18/18` must-haves verified.
  - `59-SECURITY.md` status is verified with `threats_open: 0`.
  - Current self-check pytest and ruff commands passed.

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Automated Self-Check Evidence

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_approval_resume_error_skips_terminal_finalizer_surfaces tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces tests/test_approval_api.py::test_completed_resume_reconciliation_rechecks_status_under_lock tests/test_agent_runs_api.py::test_build_agent_run_finalizer_input_state_uses_requester_identity tests/test_agent_runs_api.py::test_terminal_memory_write_state_strips_only_terminal_approval_markers tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent tests/agent/test_memory_write_node.py::test_memory_write_node_skips_approval_marked_states -q` -> `12 passed, 1 warning in 21.40s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` -> `All checks passed!`
- Artifact scan for the current phase found no open Phase 59 UAT, verification, or context-question items.

The warning is the existing LangGraph `LangChainPendingDeprecationWarning`; it is unrelated to Phase 59 behavior.

## Gaps

No UAT gaps.
