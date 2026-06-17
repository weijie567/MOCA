---
phase: 13-approval-state-machine
plan: 02
subsystem: database
tags: [alembic, sqlalchemy, approvals, migration, postgres]

requires:
  - phase: 13-approval-state-machine
    provides: CanonicalHashProfile v1 and ActionSafetySnapshot hash contract from Plan 13-01
provides:
  - Phase 13 approval state machine ORM target schema
  - Alembic migration 008 with deterministic legacy approval revision backfill
  - Migration contract tests for approval/snapshot tables, constraints, and report readiness
  - Migration report with current/head, legacy handling, read-switch owner, fallback, rollback, and verification commands
affects: [phase-13-approval-state-machine, phase-14-demo-action-boundary, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - Expand/backfill/enforce migration with legacy rows quarantined before unique indexes
    - SQLAlchemy metadata mirrors stable Alembic constraint and partial-index names
    - Redundant decision binding fields support one-transaction ownership validation

key-files:
  created:
    - src/db/migrations/versions/008_approval_state_machine.py
    - tests/approvals/test_migration_contract.py
    - tests/approvals/test_multi_level_contract.py
    - .planning/phases/13-approval-state-machine/13-MIGRATION-REPORT.md
  modified:
    - src/db/models.py

key-decisions:
  - "Legacy v1 approval rows are backfilled with row_number() per (tenant_id, run_id) and marked legacy_non_executable before revision uniqueness is enforced."
  - "The active approval-request revision partial unique excludes legacy_non_executable rows so quarantined history cannot block a new executable v2 revision."
  - "approval_decisions carries redundant level_mode so the winning-accept partial unique applies only to any_one levels and does not break all-mode assignments."

patterns-established:
  - "Migration 008 creates target tables before service cutover and keeps old v1 display fields as compatibility-only data."
  - "Contract tests inspect both SQLAlchemy metadata and Alembic source for stable schema names and backfill behavior."

requirements-completed:
  - APPROVAL-01
  - APPROVAL-03
  - SNAPSHOT-01

duration: 1h 15m
completed: 2026-06-15
---

# Phase 13 Plan 02: Approval State Machine Schema Summary

**Approval state machine persistence with snapshot table, v2 request fields, multi-level tables, deterministic legacy quarantine, and migration verification**

## Performance

- **Duration:** 1h 15m
- **Started:** 2026-06-15T06:14:17Z
- **Completed:** 2026-06-15T07:29:27Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Added ORM target schema for `action_safety_snapshots`, `approval_levels`, `approval_assignments`, `approval_decisions`, `approval_events`, and v2 `approval_requests` fields.
- Added Alembic migration `008_approval_state_machine` with deterministic legacy revision backfill using `row_number()` per `(tenant_id, run_id)`.
- Added migration contract tests covering stable constraint/index names, status/decision checks, event/decision binding fields, legacy non-executable rows, and `any_one`/`all` schema compatibility.
- Ran the live DB upgrade from `005_approval_tables` through `008_approval_state_machine` and recorded current/head plus legacy counts in the migration report.

## Task Commits

1. **Task 1: Add migration contract tests and report skeleton** - `1d81ff6` (test)
2. **Task 2: Add ORM models and v2 ApprovalRequest fields** - `d1e6dae` (feat)
3. **Task 3: Add Alembic migration 008 for approval state machine schema** - `ba4325c` (feat)
4. **Task 4: Verify migration command path and update migration report values** - `31c1ce1` (docs)

## Files Created/Modified

- `src/db/models.py` - Approval v2 ORM fields, snapshot/level/assignment/decision/event models, stable constraints and partial indexes.
- `src/db/migrations/versions/008_approval_state_machine.py` - Expand/backfill/enforce migration and explicit downgrade.
- `tests/approvals/test_migration_contract.py` - Metadata/source/report contract tests for migration readiness and legacy quarantine.
- `tests/approvals/test_multi_level_contract.py` - Multi-level compatibility tests for `any_one`, `all`, CAS version fields, and partial uniqueness.
- `.planning/phases/13-approval-state-machine/13-MIGRATION-REPORT.md` - Observed current/head, legacy counts, read-switch owner, fallback, rollback, and verification commands.

## Verification

- `uv run alembic upgrade head` - **PASS**.
- `uv run pytest tests/approvals/test_migration_contract.py tests/approvals/test_multi_level_contract.py -q --tb=short` - **PASS**: 10 passed, 1 existing LangGraph deprecation warning.
- `uv run ruff check src/db/models.py src/db/migrations/versions/008_approval_state_machine.py tests/approvals/test_migration_contract.py tests/approvals/test_multi_level_contract.py` - **PASS**.

## Decisions Made

- Used deterministic `row_number()` backfill instead of a constant revision, preserving `uq_approval_requests_tenant_run_revision` for duplicate legacy approvals within a run.
- Kept legacy v1 rows non-executable and excluded them from active-revision uniqueness rather than allowing historical pending rows to block new v2 active revisions.
- Added redundant `level_mode` to `approval_decisions` so the `uq_approval_decisions_winning_accept_level` partial unique protects `any_one` levels without preventing multiple accepted assignments for `all` levels.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Excluded legacy rows from active revision uniqueness**
- **Found during:** Task 3 (Add Alembic migration 008 for approval state machine schema)
- **Issue:** A partial unique on active `(tenant_id, run_id)` without `legacy_non_executable IS FALSE` could let quarantined v1 pending rows block creation of a new executable v2 revision.
- **Fix:** Added `legacy_non_executable IS FALSE` to the ORM and Alembic active revision partial unique predicate.
- **Files modified:** `src/db/models.py`, `src/db/migrations/versions/008_approval_state_machine.py`
- **Verification:** Focused migration pytest and ruff checks passed.
- **Committed in:** `d1e6dae` and `ba4325c`

**2. [Rule 2 - Missing Critical] Added decision-level mode binding for correct any_one uniqueness**
- **Found during:** Task 3 (Add Alembic migration 008 for approval state machine schema)
- **Issue:** A level-wide winning-accept unique index cannot be limited to `any_one` levels unless the decision row carries the level mode; without that, `all` mode would be limited to one accepted assignment.
- **Fix:** Added redundant `approval_decisions.level_mode`, a check constraint, and a partial unique predicate scoped to `level_mode = 'any_one'`.
- **Files modified:** `src/db/models.py`, `src/db/migrations/versions/008_approval_state_machine.py`, `tests/approvals/test_multi_level_contract.py`
- **Verification:** Focused migration pytest and ruff checks passed.
- **Committed in:** `d1e6dae` and `ba4325c`

---

**Total deviations:** 2 auto-fixed (2 missing critical)
**Impact on plan:** Both changes tighten the planned correctness and security boundary. No runtime service behavior was added.

## Issues Encountered

- One inline Python count command had a `-c` syntax issue before migration verification; it was rerun successfully with a multiline snippet.
- Focused pytest emits one existing LangGraph deprecation warning from the dependency stack; tests pass.

## Known Stubs

None - stub scan found no placeholder values, TODO/FIXME markers, or unwired UI/data paths in files created or modified by this plan.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: redundant_decision_mode_binding | `src/db/models.py`, `src/db/migrations/versions/008_approval_state_machine.py` | `approval_decisions.level_mode` is an added redundant binding field used to make the `any_one` winning-accept partial unique enforceable without breaking `all` mode. It is guarded by a check constraint and contract test. |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-03 can implement `src/approvals/repository.py` and `ApprovalService` transitions against the v2 schema. The local DB is upgraded to Alembic head `008_approval_state_machine`; legacy local approval count was `0`.

## Self-Check: PASSED

- Verified created files exist: `src/db/migrations/versions/008_approval_state_machine.py`, `tests/approvals/test_migration_contract.py`, `tests/approvals/test_multi_level_contract.py`, `.planning/phases/13-approval-state-machine/13-MIGRATION-REPORT.md`, and this summary.
- Verified task commits exist: `1d81ff6`, `d1e6dae`, `ba4325c`, and `31c1ce1`.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
