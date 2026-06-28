---
phase: 31-memory-platform-boundary
plan: 31-02
subsystem: testing
tags: [memory, trusted-context, merchant-isolation, red-tests, pytest]

requires: []
provides:
  - Wave 0 RED tests for reviewed memory trusted-scope fail-closed behavior
  - Wave 0 RED tests for cross-merchant session, long-term, and case memory prompt isolation
  - Wave 0 RED tests for memory_write_decision.v2 status and lifecycle metadata
affects: [31-05, 31-06, APF-10]

tech-stack:
  added: []
  patterns:
    - RED-only pytest coverage against planned memory boundary modules and fields
    - TrustedContext/MerchantScopeV1 fixtures for merchant-scoped memory retrieval tests

key-files:
  created:
    - tests/agent/test_reviewed_memory_context_retrieve.py
    - tests/memory/test_reviewed_memory_context_boundary.py
    - .planning/phases/31-memory-platform-boundary/31-02-SUMMARY.md
  modified:
    - tests/memory/test_session_memory_isolation.py
    - tests/agent/test_memory_write_node.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Kept 31-02 as a RED-only test plan; no production src files were changed."
  - "Pinned reviewed memory and memory write outputs as contextual_only authority, not policy/business/action/replay authority."

patterns-established:
  - "RED tests import planned nodes/services inside helpers so current production remains unchanged while future plans get precise contracts."
  - "Memory boundary tests assert empty fail-closed bundles and explicit status_ref/reason codes instead of permissive fallback behavior."

requirements-completed: [APF-10]

duration: 10min recorded executor window
completed: 2026-06-28
---

# Phase 31 Plan 02: Memory Platform Boundary RED Tests Summary

**Wave 0 RED tests for reviewed memory scope isolation, lifecycle filtering, session prompt contamination, and memory_write_decision.v2 metadata.**

## Performance

- **Duration:** 10 min recorded executor window
- **Started:** 2026-06-28T05:55:00Z
- **Completed:** 2026-06-28T06:05:36Z
- **Tasks:** 2
- **Files modified:** 6 including this summary

## Accomplishments

- Added RED tests for `reviewed_memory_context_retrieve` fail-closed behavior when trusted context, actor merchant scope, or in-scope merchant selection is missing.
- Added DB-backed reviewed-memory boundary tests for cross-merchant isolation, tenant/global unsupported scope, deleted/expired/rejected/superseded/needs_review/PII exclusion, tombstone blocking, and supersede visibility.
- Added same tenant/user/thread session prompt-contamination RED tests for merchant-scoped slots, rolling summaries, recent messages, and tool summaries.
- Extended memory write node tests to require `memory_write_decision.v2` beside legacy `memory_write_result` for write, skip, timeout, and PII-block paths.

## Task Commits

1. **Task 1: Add RED reviewed-memory trusted-scope and merchant-isolation tests** - `2fec234` (test)
2. **Task 2: Add RED memory write decision status tests** - `c9f9d97` (test)

## Files Created/Modified

- `tests/agent/test_reviewed_memory_context_retrieve.py` - New RED tests for planned reviewed memory retrieval node fail-closed contract and legacy alias compatibility.
- `tests/memory/test_reviewed_memory_context_boundary.py` - New/extended DB-backed RED tests for reviewed long-term/case memory isolation, lifecycle exclusion, write decision projection, tombstone, and supersede behavior.
- `tests/memory/test_session_memory_isolation.py` - Added same-thread cross-merchant session prompt-contamination tests.
- `tests/agent/test_memory_write_node.py` - Added `memory_write_decision.v2` assertions beside legacy session write result assertions.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Appended the required Chinese local validation issue entry for the handled Task 1 fixture failure.

## Verification

- `uv run ruff check tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_session_memory_isolation.py` passed.
- `bash -lc 'set +e; uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_session_memory_isolation.py -q; status=$?; test "$status" -ne 0'` passed as a RED gate: pytest failed with planned missing modules `src.agent.nodes.reviewed_memory_context_retrieve`, `src.memory.context_service`, and `src.agent.nodes.session_context_load`.
- `uv run ruff check tests/agent/test_memory_write_node.py tests/memory/test_reviewed_memory_context_boundary.py` passed.
- `bash -lc 'set +e; uv run pytest tests/agent/test_memory_write_node.py tests/memory/test_reviewed_memory_context_boundary.py -q; status=$?; test "$status" -ne 0'` passed as a RED gate: pytest failed on missing `memory_write_decision` fields and missing planned `src.memory.context_service`.
- Required `rg` acceptance checks for fail-closed reasons, structured bundle fields, merchant isolation fixtures, session contamination fields, write decision metadata, lifecycle cases, and legacy `memory_write_result` assertions all passed.

## Decisions Made

- RED assertions deliberately target planned modules/fields rather than adding compatibility shims in production.
- Reviewed memory context assertions keep `status`, `fallback_reason`, `trusted_scope_inputs`, `effective_scopes`, `filter_reasons`, and `retrieved_refs` under `status_ref`.
- Session memory cannot create merchant authority: stored active slots are tested as continuity-only and must not override current explicit trusted merchant context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Fixture Bug] Added required LongTermMemory confidence in direct ORM fixture**
- **Found during:** Task 1
- **Issue:** The direct `LongTermMemory` ORM fixture omitted non-null `confidence`, causing a DB `NotNullViolation` before reaching the intended RED failure.
- **Fix:** Set `confidence=Decimal("0.9000")` in the `_long_term_row` test helper.
- **Files modified:** `tests/memory/test_reviewed_memory_context_boundary.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Re-ran the Task 1 RED pytest command; remaining failures were only the intended missing planned implementation modules.
- **Committed in:** `2fec234`

---

**Total deviations:** 1 auto-fixed Rule 1 issue.
**Impact on plan:** The fix preserved the RED-only scope and removed a blocking fixture error so the tests now fail for the intended planned implementation gaps.

## Issues Encountered

- Expected RED failures remain by design. No production `src/` files were changed.
- No authentication gates occurred.
- Stub scan found only intentional empty test fixtures/expected empty outputs; no unresolved stubs block the plan goal.
- Threat surface scan found no new production endpoints, auth paths, file access paths, or schema changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 31-05 and 31-06 can now implement the planned reviewed memory context service/node, session context loading projection, and `memory_write_decision.v2` output against these RED tests.

## TDD Gate Compliance

This plan is intentionally RED-only Wave 0. It has test commits and no GREEN production implementation commit, matching the user instruction not to implement production `src/` changes in 31-02.

## Self-Check: PASSED

- Verified all created/modified plan files exist.
- Verified task commits `2fec234` and `c9f9d97` exist in git history.
- Verified no `STATE.md` or `ROADMAP.md` changes were made by this executor.
