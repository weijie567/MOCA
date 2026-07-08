---
phase: 59-approval-resume-terminal-memory-finalization
reviewed: 2026-07-08T10:07:28Z
depth: deep
files_reviewed: 6
files_reviewed_list:
  - src/api/services/agent_run_memory.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/agent/test_memory_write_node.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 59: Code Review Report

**Reviewed:** 2026-07-08T10:07:28Z
**Depth:** deep
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Deep review covered the Phase 59 approval resume, terminal memory finalizer, CWC, retry reconciliation, and related tests. The requester identity handoff for terminal memory/CWC is correct, and the direct `memory_write(...)` approval-marker skip predicate remains intact. I found two warning-level correctness risks in the new approval-resume finalization/retry path.

Focused verification run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure tests/agent/test_memory_write_node.py::test_memory_write_node_skips_approval_marked_states -q
```

Result: 6 passed, 1 warning.

## Warnings

### WR-01: Approval resume can record completion without durable finalizer evidence

**File:** `src/api/routers/approvals.py:395-400`
**Issue:** The approval resume path calls `persist_agent_run_memory_finalize_trace_steps(...)` before `_run_resume_lifecycle` records `approval_resumed/completed`, but the helper catches all append failures and rolls back without raising (`src/api/services/agent_run_memory.py:89-99`). If finalizer trace append fails, `_run_resume_lifecycle` still records a completed resume event. That leaves a completed run without the finalizer evidence required by `_completed_resume_finalizer_reconciliation_ready`, while future retries will stop at `_latest_resume_status == "completed"` and never fail closed. The same rollback can also discard pending CWC writes made just before trace persistence.
**Fix:** Make approval resume treat finalizer evidence persistence as required before emitting `resume_status="completed"`. A small API change keeps existing SSE behavior while making approval resume fail closed:

```python
async def persist_agent_run_memory_finalize_trace_steps(
    *,
    session: AsyncSession,
    run: AgentRun,
    prior_trace_steps: list[dict[str, Any]],
    finalizer_trace_steps: list[dict[str, Any]],
    suppress_errors: bool = True,
) -> None:
    ...
    except Exception:
        await session.rollback()
        if not suppress_errors:
            raise
```

Then call it from `approvals.py` with `suppress_errors=False`, and either commit the CWC write before this suppressible trace append or perform the trace append in an isolated transaction/session so trace failure cannot roll back terminal CWC rows.

### WR-02: Completed-run retry reconciliation is not concurrency-safe

**File:** `src/api/routers/approvals.py:249-256`
**Issue:** The new completed-run retry reconciliation path reads the latest resume status, checks finalizer evidence, and appends `approval_resumed/completed` without locking the approval/retry key or using a uniqueness constraint. Two concurrent retries after an `attempted` or `failed` resume event can both observe the same incomplete latest status, both pass `_completed_resume_finalizer_reconciliation_ready`, and both append completed events. The serial tests assert only one completed event, but the implementation does not enforce that under concurrency.
**Fix:** Serialize reconciliation per approval revision before checking `_latest_resume_status` and before emitting the completed event. For example, lock the `ApprovalRequest` row or take an advisory lock on `_resume_key(...)`, then re-check `_latest_resume_status` inside that lock before `_record_resume_event(...)`. If the re-check sees `"completed"`, return without appending another event.

---

_Reviewed: 2026-07-08T10:07:28Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
