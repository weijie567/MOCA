---
phase: 08
plan: 08-07
status: complete
started: 2026-06-07T15:45:00Z
completed: 2026-06-07T16:00:00Z
tasks_completed: 2
tasks_total: 2
deviations: none
---

# 08-07 SUMMARY: Gap Closure — allow_partial_evidence + effective-time pre-filter

## What Changed

Two blocking verification gaps closed:

1. **`allow_partial_evidence` flag honored** (`src/knowledge/service.py`): When `request.allow_partial_evidence` is `False` and the adapter returns `partial_evidence`, the service now returns `no_evidence` with empty `evidence_refs`. Previously the flag was silently ignored.

2. **`effective_date` filtered in SQL before LIMIT** (`src/repositories/policy_chunk_repo.py` + `src/knowledge/adapters.py`): Added `effective_date` parameter to `PolicyChunkRepository.search_similar()` with a `PolicyChunk.effective_date <= effective_date` WHERE clause. The adapter now passes `effective_date` down to the repository. Previously, the repository applied SQL LIMIT before effective-date filtering, allowing future-dated high-similarity chunks to crowd out valid current evidence.

Gap 3 (tenant-over-global) disposition recorded in 08-07-PLAN.md — no code change, CONTEXT.md D-D1 explicitly defers it.

## Key Files Modified

- `src/knowledge/service.py` — partial_evidence suppression logic
- `src/repositories/policy_chunk_repo.py` — effective_date SQL filter
- `src/knowledge/adapters.py` — pass effective_date to repository
- `tests/knowledge/test_facade_status.py` — 2 new tests for allow_partial_evidence
- `tests/knowledge/test_effective_time.py` — 1 new test for effective_date passthrough
- `tests/repositories/test_policy_chunk_repo.py` — new repo-level test

## Test Results

- `tests/knowledge/` — 39 passed
- Full suite — 277 passed, 0 failures

## Self-Check: PASSED

- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created
- [x] No deviations from plan
- [x] Full test suite green
