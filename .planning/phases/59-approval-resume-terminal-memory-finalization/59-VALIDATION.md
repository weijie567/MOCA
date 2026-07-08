---
phase: 59
slug: approval-resume-terminal-memory-finalization
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-08
---

# Phase 59 - Validation Strategy

Per-phase validation contract for approval-resume terminal memory finalization.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py -q` |
| Estimated runtime | Focused commands 2s-88s; full combined suite 239s; use focused commands per task first |

## Sampling Rate

- After every task commit: run the focused command listed for that task.
- After every plan wave: run the wave command listed below.
- Before `$gsd-verify-work`: run the full suite command above.
- Max feedback latency: keep focused commands under the shortest practical subset; do not replace them with bare `pytest`.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 59-01-01 | 01 | 1 | MEM-03 | T59-01 | Completed approval-resume memory writes can bypass pending-approval skip only through terminal-finalizer context. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py -q` | W0 | passed |
| 59-01-02 | 01 | 1 | MEM-01/MEM-02/MEM-03 | T59-02 | Shared finalizer trace persistence is idempotent and does not duplicate `agent_run_memory_finalize` steps. | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` | existing | passed |
| 59-02-01 | 02 | 2 | MEM-01/MEM-02/MEM-03/CAGM-08 | T59-03 | Approval-resume completed path uses requester/run identity for terminal finalization, not reviewer identity. | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` | W0 | passed |
| 59-02-02 | 02 | 2 | CAGM-08/CAGM-09 | T59-04 | Interrupted-again approval resumes stay interrupted and do not write terminal memory surfaces. | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt -q` | existing + W0 | passed |
| 59-03-01 | 03 | 3 | MEM-01/MEM-02/MEM-03/CAGM-08/CAGM-09 | T59-05 | Approval retry after partial terminal finalization is idempotency-compatible. | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval -q` | existing + W0 | passed |
| 59-03-02 | 03 | 3 | CAGM-09 | T59-06 | Canonical graph vocabulary and approval/action boundaries remain unchanged. | architecture | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` | existing | passed |

## Wave Commands

| Wave | Command |
|------|---------|
| 1 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` |
| 2 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` |
| 3 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py -q` |

## Wave 0 Requirements

- [x] `tests/test_approval_api.py` - add approval-resume completed finalizer regression.
- [x] `tests/test_approval_api.py` - add interrupted-again no-terminal-finalizer regression if existing coverage is not sufficient.
- [x] `tests/test_approval_api.py` - add retry/dedupe regression for terminal finalizer surfaces.
- [x] `tests/agent/test_memory_write_node.py` - add terminal-finalizer approval-marker eligibility regression if `memory_write` eligibility changes.

## Manual-Only Verifications

All phase behaviors have automated verification. Manual review is limited to reading `.planning/ARCHITECTURE-DEBT.md` and `.planning/LOCAL-VALIDATION-ISSUES.md` when implementation discovers memory/approval lifecycle debt or local validation incidents.

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency recorded during execution.
- [x] `nyquist_compliant: true` set in frontmatter after all planned tests are green.

Approval: complete

## Final Evidence

Recorded after Phase 59 Plan 03 Task 3, using only MOCA-approved command entrypoints:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` -> `35 passed, 1 warning in 88.44s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_skips_non_completed_status tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` -> `4 passed, 1 warning in 11.41s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py -q` -> `57 passed, 1 warning in 27.78s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `31 passed, 1 warning in 1.69s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `193 passed, 1 warning in 239.08s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` -> `All checks passed!`

## Code Review Fix Evidence

Recorded after `59-REVIEW.md` found WR-01/WR-02 and the fixes were applied:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_can_fail_closed -q` -> `2 passed, 1 warning in 5.49s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces tests/test_approval_api.py::test_completed_resume_reconciliation_rechecks_status_under_lock tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval -q` -> `3 passed, 1 warning in 9.89s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_commits_approval_decision_before_graph_resume tests/test_approval_api.py::test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces tests/test_approval_api.py::test_completed_resume_reconciliation_rechecks_status_under_lock tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval -q` -> `4 passed, 1 warning in 12.52s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` -> `37 passed, 1 warning in 94.88s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_can_fail_closed tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` -> `5 passed, 1 warning in 13.54s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `88 passed, 1 warning in 31.05s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` -> `196 passed, 1 warning in 248.48s`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` -> `All checks passed!`
