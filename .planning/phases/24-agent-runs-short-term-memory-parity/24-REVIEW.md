---
phase: 24-agent-runs-short-term-memory-parity
phase_number: 24
reviewed: 2026-06-20T21:47:53Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - src/agent/context/assembler.py
  - src/agent/context/projectors.py
  - src/agent/nodes/extract_slots.py
  - src/api/routers/agent_runs.py
  - src/api/services/__init__.py
  - src/api/services/agent_run_memory.py
  - src/conversation/repository.py
  - src/conversation/service.py
  - src/db/migrations/versions/016_agent_run_memory_idempotency.py
  - src/db/models.py
  - src/memory/thread_summary.py
  - tests/agent/context/test_assembler.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_session_memory_integration.py
  - tests/conversation/test_service.py
  - tests/memory/test_thread_summary.py
  - tests/test_agent_runs_api.py
findings:
  critical: 2
  warning: 0
  info: 0
  total: 2
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-06-20T21:47:53Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the committed Phase 24 state through `HEAD` using line-numbered `git show HEAD:<path>` reads because the working tree has unrelated unstaged edits in several scoped files. The review covered the new agent-runs conversation memory finalizer, prompt-context loading, projection/redaction boundaries, idempotency indexes, migration shape, and test coverage around SSE duplicate streams and multi-turn memory.

The migration/index additions are structurally aligned with the SQLAlchemy models, and the prompt projectors avoid the obvious raw/debug/authority markers covered by tests. Two critical behavior risks remain in the committed code: cross-user SSE execution can run with the caller's authority, and the terminal memory finalizer can silently lose conversation rows when session-memory write handling rolls back the shared transaction.

## Critical Issues

### CR-01: SSE Stream Execution Uses Viewer Authorization For Run Execution

**File:** `src/api/routers/agent_runs.py:168`

**Issue:** `_claim_pending_run_for_stream` reuses `_ensure_can_view_run`, whose check permits `SUPERVISOR_ROLES` to access runs they do not own (`src/api/routers/agent_runs.py:1053`). After the claim, the stream builds `input_state` and tool permissions from the current caller (`src/api/routers/agent_runs.py:189-206`), while the conversation message lookup uses `run.user_id`. A same-tenant supervisor/admin can therefore start another user's pending run and execute the graph/tools with the supervisor's role, scopes, and merchant scope. The finalizer then persists conversation rows for `run.user_id` while memory state uses the caller's `user.id`, creating an authority-boundary and memory-contamination risk.

**Fix:**
```python
async def _claim_pending_run_for_stream(session: AsyncSession, run_id: UUID, user: User) -> AgentRun:
    result = await session.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id).with_for_update()
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.user_id != user.id:
        await session.rollback()
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot execute this run"})
    ...
```

If delegated execution is intended, load the run owner explicitly and use one consistent execution principal for `input_state`, checkpoint IDs, tool permissions, assistant messages, summaries, and memory writes; record the supervisor only as an audit actor. Add a same-tenant cross-user stream test that proves the graph is not called and the pending run is not claimed.

### CR-02: Session-Memory Fallback Can Roll Back Completed Conversation Writes

**File:** `src/api/services/agent_run_memory.py:74`

**Issue:** `finalize_completed_agent_run_memory` appends the assistant message and thread summary, then calls `_run_terminal_memory_write` with the same `AsyncSession` (`src/api/services/agent_run_memory.py:59-83`, `src/api/services/agent_run_memory.py:132-135`). The imported session-memory service performs `session.rollback()` on handled failures and insert-race paths. Because all of this shares the outer SSE transaction, a memory-write fallback or concurrency race can roll back already-flushed assistant messages, summaries, and tool-result rows while `_run_terminal_memory_write` returns a normal `"fallback"`/`"error"` result. `_complete_run` can then commit the run as completed with finalizer metrics pointing at rows that no longer exist.

**Fix:**
```python
# The memory writer must not be allowed to rollback the outer finalization transaction.
# Prefer changing memory_write/MemoryService so handled fallback paths rollback only a savepoint,
# then call it from an explicit savepoint owned by the finalizer.
try:
    async with session.begin_nested():
        result_state = await memory_write(
            memory_state,
            {"configurable": {"session": session, "trace_id": trace_id or ""}},
        )
except Exception as exc:
    return {"status": "error", "reason_code": "write_failed", "error_type": type(exc).__name__}
```

As a defensive guard, detect if the call rolled back the ambient transaction and fail the run instead of committing a completed run with missing conversation memory. Add a regression where `memory_write` triggers a rollback/fallback after assistant and summary flushes, then assert either all terminal rows persist or the run is marked error consistently.

---

_Reviewed: 2026-06-20T21:47:53Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
