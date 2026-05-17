---
phase: 05-frontend-sse
plan: 05
subsystem: backend
tags: [sse, fastapi, concurrency, regression-tests]
requires:
  - phase: 05-frontend-sse
    provides: run-based SSE endpoint
provides:
  - Atomic pending-to-running claim before SSE execution starts
  - 409 RUN_ALREADY_STARTED responses for duplicate or terminal run streams
  - Regression tests for duplicate, terminal, and cross-tenant SSE start attempts
affects: [agent-runs-api, langgraph-streaming, trace-persistence]
tech-stack:
  added: []
  patterns: [route-boundary claim, row lock, ApiResponse error envelope]
key-files:
  created:
    - tests/test_agent_runs_api.py
    - .planning/phases/05-frontend-sse/05-05-SUMMARY.md
  modified:
    - src/api/routers/agent_runs.py
key-decisions:
  - "SSE execution is claimed before EventSourceResponse is returned, not inside the generator."
  - "Already-started and terminal runs return 409 RUN_ALREADY_STARTED before graph.astream can be called."
requirements-completed: [AGNT-07]
duration: recovered
completed: 2026-05-17T10:39:00Z
---

# Phase 05 Plan 05: SSE Duplicate Execution Guard Summary

Backend SSE starts now require an atomic pending-run claim before the graph is built or streamed.

## Accomplishments

- Added focused regression coverage for already-running, terminal, and cross-tenant `/events` calls.
- Added `_claim_pending_run_for_stream()` with tenant-scoped locked select and owner-or-supervisor authorization.
- Moved the `pending -> running` transition to the route boundary.
- Removed the generator-side status transition so duplicate streams cannot enter `graph.astream`.

## Task Commits

1. **Task 1: Add regression tests for duplicate SSE starts** - `bda6b10`
2. **Task 2: Claim pending runs before streaming** - `ce42be2`

## Files Created/Modified

- `tests/test_agent_runs_api.py` - Covers 409 duplicate/terminal rejection and cross-tenant no-claim behavior.
- `src/api/routers/agent_runs.py` - Claims pending runs before streaming and returns `RUN_ALREADY_STARTED` for non-pending runs.
- `.planning/phases/05-frontend-sse/05-05-SUMMARY.md` - Records plan completion.

## Deviations from Plan

- Initial subagent became unresponsive after creating the test file. The orchestrator closed the worker, completed the implementation locally, and preserved the test work.
- The RED test run before implementation was not captured by the stuck subagent. Final targeted regression and lint checks passed after implementation.

## Verification

- `uv run pytest tests/test_agent_runs_api.py -q` - passed, 3 tests
- `uv run ruff check src/api/routers/agent_runs.py tests/test_agent_runs_api.py` - passed
- `rg -n "RUN_ALREADY_STARTED|_claim_pending_run_for_stream|with_for_update|final_status != \"pending\"" src/api/routers/agent_runs.py tests/test_agent_runs_api.py` - matched expected guard and tests

## Self-Check: PASSED

- Summary exists.
- Task commits exist.
- Key files exist.
- No shared tracking artifacts were committed by the executor.
