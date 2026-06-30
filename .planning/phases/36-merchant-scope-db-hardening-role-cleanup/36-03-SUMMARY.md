---
phase: 36-merchant-scope-db-hardening-role-cleanup
plan: 36-03
subsystem: database
tags: [agent-runs, merchant-scope, postgres, sqlalchemy, api]

requires:
  - phase: 36-02
    provides: tenant-aware username identity and role cleanup groundwork
provides:
  - AgentRun run-scope classifier using only authoritative merchant proof
  - AgentRun target merchant fields, scope classification fields, constraints, and indexes
  - Runtime persistence of scope facts on run creation and completion updates
  - Safe AgentRun status metadata without widening owner/admin visibility guards
affects: [phase-36, merchant-scope, agent-runs, replay, approvals]

tech-stack:
  added: []
  patterns:
    - fail-closed run-scope classification
    - SQLAlchemy JSONB SQL-null handling for nullable proof columns
    - safe API projection of non-authorizing run-scope metadata

key-files:
  created:
    - src/agent/run_scope.py
  modified:
    - src/db/models.py
    - src/agent/state.py
    - src/agent/trace.py
    - src/api/routers/agent_runs.py
    - src/api/schemas/agent_runs.py
    - tests/agent/test_phase36_run_scope.py
    - tests/approvals/test_migration_contract.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "AgentRun scope is classified only from TargetMerchantBindingV1, matching approval-plan binding, or validated BusinessFactResultV1 proof."
  - "Target merchant context and replay authorization projection remain non-authorizing metadata and do not promote unknown runs to business_merchant."
  - "AgentRun status responses expose target_merchant_id, scope_classification, and scope_source, but not target_merchant_ref."
  - "AgentRun.target_merchant_ref uses JSONB(none_as_null=True) so unscoped rows satisfy SQL NULL consistency checks."

patterns-established:
  - "Run-scope writes default to unknown_legacy with no_authoritative_scope_proof when no final state is available."
  - "Existing business_merchant bindings are preserved on weak update state and cleared only for explicit mixed-target contradiction."
  - "Run visibility remains owner/admin-only; execute remains owner-only."

requirements-completed: [MSH-04, MSH-07]

duration: 24min
completed: 2026-06-30
---

# Phase 36 Plan 36-03: AgentRun Scope Binding Summary

**AgentRun now stores fail-closed merchant-scope facts from authoritative proof while preserving existing owner/admin run visibility.**

## Performance

- **Duration:** 24 min recorded from first task commit to summary creation
- **Started:** 2026-06-30T07:14:15Z
- **Completed:** 2026-06-30T07:38:32Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added `src/agent/run_scope.py` with `AgentRunScopeFacts` and `classify_agent_run_scope`.
- Added AgentRun scope columns, target consistency checks, and tenant/scope indexes.
- Threaded final graph state into AgentRun create/update paths so persisted rows receive classifier output.
- Extended run status responses with safe scope metadata while keeping visibility guards unchanged.
- Added regression tests for authoritative proof, malformed bindings, weak sources, persistence updates, and API guard behavior.

## Task Commits

1. **Task 1 RED: Define AgentRun scope helper and ORM fields** - `5c1d6b0` (test)
2. **Task 1 GREEN: Define AgentRun scope helper and ORM fields** - `6712de7` (feat)
3. **Task 2 RED: Persist scope facts on run create/update without widening guards** - `856c3a2` (test)
4. **Task 2 GREEN: Persist scope facts on run create/update without widening guards** - `38bf4fc` (feat)

**Plan metadata:** committed by the documentation commit containing this summary.

## Files Created/Modified

- `src/agent/run_scope.py` - Classifies AgentRun scope from strict, trusted merchant proof.
- `src/db/models.py` - Adds AgentRun scope fields, DB constraints, indexes, and SQL-null JSONB target proof handling.
- `src/agent/state.py` - Adds optional run-scope fields to AgentState.
- `src/agent/trace.py` - Persists classifier output on run writes and completion updates.
- `src/api/routers/agent_runs.py` - Threads final state into run completion and exposes safe status metadata without changing guards.
- `src/api/schemas/agent_runs.py` - Adds safe run-scope fields to `RunStatusResponse`.
- `tests/agent/test_phase36_run_scope.py` - Covers classifier behavior and persistence update semantics.
- `tests/approvals/test_migration_contract.py` - Covers AgentRun metadata and constraint contract.
- `tests/test_agent_runs_api.py` - Covers status projection and guard preservation.

## Decisions Made

- Used validated `TargetMerchantBindingV1` and validated service-approved `BusinessFactResultV1` as the only business merchant authorities.
- Kept `target_merchant_ref` out of API responses because it is proof metadata, not required for safe status display.
- Preserved existing `business_merchant` rows on weak state updates to avoid downgrading durable proof from non-authoritative projection state.
- Represented absent target proof as SQL `NULL`, not JSON `null`, so DB check constraints enforce the intended presence/absence rule.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixture proof shape**
- **Found during:** Task 1 GREEN
- **Issue:** The initial RED helper did not populate all fields required by `BusinessFactRefV1`, so classifier tests failed before reaching the intended behavior.
- **Fix:** Updated the test helper to build valid business fact refs.
- **Files modified:** `tests/agent/test_phase36_run_scope.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/approvals/test_migration_contract.py -q --tb=short`
- **Committed in:** `6712de7`

**2. [Rule 1 - Bug] Stored absent AgentRun target proof as SQL NULL**
- **Found during:** Task 2 GREEN
- **Issue:** PostgreSQL JSONB persisted Python `None` as JSON `null`, causing unscoped `unknown_legacy` rows to violate `ck_agent_runs_scope_target_consistency`.
- **Fix:** Set `AgentRun.target_merchant_ref` to `JSONB(none_as_null=True)`.
- **Files modified:** `src/db/models.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/test_agent_runs_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short`
- **Committed in:** `38bf4fc`

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes were required for the planned tests and constraints to reflect the intended run-scope contract. No new feature scope was added.

## Issues Encountered

- The first valid `uv run pytest` attempt hit a stale local pytest entrypoint using Python 3.9 and failed during collection on `datetime.UTC`. Running `UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev` repaired the repo virtualenv, and all subsequent verification used `uv run`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/approvals/test_migration_contract.py -q --tb=short` -> 31 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/db/models.py src/agent/run_scope.py src/agent/state.py tests/agent/test_phase36_run_scope.py tests/approvals/test_migration_contract.py` -> passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/test_agent_runs_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` -> 80 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/db/models.py src/agent/run_scope.py src/agent/state.py src/agent/trace.py src/api/routers/agent_runs.py src/api/schemas/agent_runs.py tests/agent/test_phase36_run_scope.py tests/test_agent_runs_api.py tests/approvals/test_migration_contract.py` -> passed.
- Required positive and negative `rg` acceptance checks passed.

## Known Stubs

None. Stub scan hits were ordinary empty collection initializers, test assertions, or existing model defaults, not unfinished data/UI placeholders.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 36-05 can add the Alembic migration for the AgentRun columns and constraints. The ORM metadata, runtime persistence path, and focused tests are ready.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-03-SUMMARY.md`.
- Task commits found: `5c1d6b0`, `6712de7`, `856c3a2`, `38bf4fc`.
- Protected shared tracking files were not modified: `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`.

---
*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Completed: 2026-06-30*
