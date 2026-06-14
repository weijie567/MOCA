---
phase: 12-session-memory
status: clean
depth: standard
files_reviewed: 24
finding_counts:
  critical: 0
  warning: 0
  info: 0
  total: 0
fixed_findings: 1
reviewed_at: 2026-06-14T10:22:30Z
---

# Phase 12 Code Review

## Scope

Reviewed the Phase 12 source and test files from plan summaries, excluding planning-only artifacts:

- `src/db/models.py`
- `src/db/migrations/versions/007_session_memories.py`
- `src/memory/__init__.py`
- `src/memory/schemas.py`
- `src/memory/repository.py`
- `src/memory/service.py`
- `src/config.py`
- `src/agent/state.py`
- `src/agent/events.py`
- `src/agent/nodes/session_memory_load.py`
- `src/agent/nodes/extract_slots.py`
- `src/agent/nodes/receive_request.py`
- `src/agent/nodes/investigate.py`
- `src/agent/nodes/memory_write.py`
- `src/agent/routing.py`
- `src/api/routers/agent.py`
- `src/api/routers/agent_runs.py`
- `tests/memory/*`
- `tests/agent/test_session_memory_load.py`
- `tests/agent/test_memory_write_node.py`
- `tests/agent/test_required_slots.py`
- `tests/agent/test_session_memory_integration.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/test_agent_runs_api.py`
- `tests/agent/test_events.py`

Note: the working tree contains unrelated uncommitted changes outside the Phase 12 review commits. One overlapping file, `src/agent/nodes/investigate.py`, also has uncommitted worktree changes, so review conclusions are based on Phase 12 committed behavior and the focused verification matrix.

## Findings

No open findings remain.

## Fixed During Review

### FR-001: Context-only session memory rows could expire immediately after merge

- **Severity:** warning
- **File:** `src/memory/service.py`
- **Issue:** `_max_expiry()` returned `now` when a merge produced no active slots. For an existing row carrying only `session_summary` and/or `unresolved_questions`, a later merge could set `expires_at` to the merge time and make the row expire immediately on the next load.
- **Fix:** Return `None` when no slot expiries exist, matching insert behavior for context-only rows.
- **Regression:** Added `test_service_merge_without_slots_does_not_expire_context_only_memory`.
- **Commit:** `ca627a2` (`fix(12): preserve context-only session memory rows`)

## Verification

- `uv run pytest tests/memory/test_session_memory_service.py tests/memory/test_session_memory_concurrency.py -q --tb=short` -> 10 passed, 1 warning.
- `uv run ruff check src/memory/service.py tests/memory/test_session_memory_service.py` -> passed.
- `uv run pytest tests/memory tests/agent/test_session_memory_load.py tests/agent/test_memory_write_node.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_memory_evidence_boundary.py -q --tb=short` -> 40 passed, 1 warning.
- `uv run pytest tests/agent/test_graph.py tests/test_agent_runs_api.py tests/agent/test_events.py -q --tb=short` -> 44 passed, 1 warning.
- `uv run ruff check src/memory src/agent/nodes/session_memory_load.py src/agent/nodes/memory_write.py src/agent/routing.py tests/memory tests/agent/test_session_memory_load.py tests/agent/test_memory_write_node.py tests/agent/test_session_memory_integration.py tests/agent/test_memory_evidence_boundary.py` -> passed.

## Result

Phase 12 passes code review at standard depth after the review fix above. No critical, warning, or info findings remain open.
