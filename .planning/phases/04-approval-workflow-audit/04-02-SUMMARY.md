---
phase: 04-approval-workflow-audit
plan: 02
subsystem: database
tags: [postgres, sqlalchemy, alembic, approvals, audit, repositories]

requires:
  - phase: 04-approval-workflow-audit
    provides: latency metric migration chain and AgentState approval field prerequisite from 04-01
provides:
  - ApprovalRequest, ApprovalStep, and ActionDraft ORM models with migration 005
  - Tenant-filtered approval and action draft repositories
  - Idempotent approval decision and action draft creation semantics
  - Resume trace helpers for updating existing agent runs and appending post-resume steps
affects: [approval-workflow-audit, agent-tracing, write-tools, audit]

tech-stack:
  added: []
  patterns:
    - Repository methods require tenant_id for mutable approval and action draft access
    - Approval decisions use SELECT FOR UPDATE and idempotent terminal-state handling
    - Resume trace persistence reuses the existing AsyncSession and trace normalization helpers

key-files:
  created:
    - src/db/migrations/versions/005_approval_tables.py
    - src/repositories/approval_repo.py
    - src/repositories/action_draft_repo.py
    - tests/test_approval_models.py
  modified:
    - src/db/models.py
    - src/agent/state.py
    - src/agent/trace.py

key-decisions:
  - "Approval repository mutation paths require tenant_id, including mark_expired, to preserve tenant isolation."
  - "Action draft idempotency keys remain globally unique, but cross-tenant reuse raises idempotency_key_conflict instead of returning another tenant's draft."
  - "Task 02-02 was already functionally satisfied by 04-01; this plan added an explicit Phase 4 grouping comment and kept the fields optional."

patterns-established:
  - "Approval state transitions treat repeated same decisions as idempotent and conflicting opposite decisions as ValueError conflicts."
  - "Approval table migrations are hand-written narrow revisions chained after 004_latency_metrics."

requirements-completed: []
requirements-addressed: [SAFE-01, SAFE-07, TOOL-04, TOOL-05]

duration: 8min
completed: 2026-05-16
---

# Phase 4 Plan 2: Approval Tables and State Extensions Summary

**Approval workflow persistence with tenant-scoped repositories, idempotent decisions, action draft dedupe, and trace resume helpers.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-16T07:38:21Z
- **Completed:** 2026-05-16T07:46:15Z
- **Tasks:** 6
- **Files modified:** 7

## Accomplishments

- Added `approval_requests`, `approval_steps`, and `action_drafts` models plus migration `005_approval_tables`, chained after the latency metrics migration.
- Added `ApprovalRepository` with tenant-scoped reads, pending-list filtering, row-level locking, and idempotent approve/reject transitions.
- Added `ActionDraftRepository` with idempotency-key reuse, tenant-scoped run lookup, and tenant-scoped failure updates.
- Added `update_agent_run_status` and `append_agent_steps` for post-approval graph resume trace persistence.
- Added approval repository tests covering decision transitions, thread resume ID storage, tenant isolation, pending expiry filtering, and action draft idempotency.

## Task Commits

Each task was committed atomically:

1. **Task 02-01: Add ApprovalRequest, ApprovalStep, ActionDraft models** - `42a149a` (feat)
2. **Task 02-02: Extend AgentState with approval fields** - `6aef8c4` (docs)
3. **Task 02-03: Create ApprovalRepository with row-level locking** - `01714da` (feat)
4. **Task 02-04: Create ActionDraftRepository** - `a9b3e62` (feat)
5. **Task 02-05: Add trace helpers for run status updates after resume** - `3194b91` (feat)
6. **Task 02-06: Unit tests for models and repositories** - `116dd97` (test)

## Files Created/Modified

- `src/db/models.py` - Adds approval request, approval step, and action draft ORM models.
- `src/db/migrations/versions/005_approval_tables.py` - Creates and drops approval workflow tables and operational indexes.
- `src/agent/state.py` - Marks the optional Phase 4 approval workflow state fields.
- `src/repositories/approval_repo.py` - Provides tenant-filtered approval CRUD, pending list, locked decisions, expiry, and step insertion.
- `src/repositories/action_draft_repo.py` - Provides action draft idempotent create-or-get, run lookup, and failure marking.
- `src/agent/trace.py` - Adds helpers for updating an existing agent run and appending post-resume steps.
- `tests/test_approval_models.py` - Covers approval state transitions, tenant isolation, action draft idempotency, thread ID persistence, and expiry filtering.

## Decisions Made

- `mark_expired` requires `tenant_id` even though the plan sketch omitted it; status mutation must stay tenant-scoped.
- `ActionDraftRepository.create_or_get` raises `ValueError("idempotency_key_conflict")` if a duplicate idempotency key belongs to another tenant.
- No requirement was marked complete from this plan alone. The plan lays approval persistence groundwork but does not yet ship the graph interrupt node or write tools.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Enforced tenant filtering on mutable repository paths**
- **Found during:** Tasks 02-03 and 02-04
- **Issue:** The plan sketch had `ApprovalRepository.mark_expired(approval_id)` and `ActionDraftRepository.mark_failed(draft_id, error)` without tenant filters. It also reused drafts by global idempotency key without checking tenant ownership.
- **Fix:** Required `tenant_id` for approval expiry and draft failure updates; duplicate idempotency keys from another tenant now raise `idempotency_key_conflict`.
- **Files modified:** `src/repositories/approval_repo.py`, `src/repositories/action_draft_repo.py`, `tests/test_approval_models.py`
- **Verification:** `uv run pytest tests/test_approval_models.py -q`; `uv run ruff check src/repositories/ tests/test_approval_models.py`
- **Committed in:** `01714da`, `a9b3e62`, `116dd97`

**2. [Rule 2 - Missing Critical] Validated approval decision input**
- **Found during:** Task 02-03
- **Issue:** A decision other than `approve` or `reject` would otherwise fall through to rejection.
- **Fix:** `ApprovalRepository.decide` raises `ValueError("invalid_decision")` for unsupported decisions before acquiring the row lock.
- **Files modified:** `src/repositories/approval_repo.py`
- **Verification:** `uv run ruff check src/repositories/approval_repo.py`; existing decision matrix tests passed.
- **Committed in:** `01714da`

---

**Total deviations:** 2 auto-fixed (Rule 2: 2)
**Impact on plan:** Both changes enforce correctness and the plan threat model; no feature scope was expanded beyond approval persistence safety.

## Issues Encountered

- The plan referenced `tests/test_assess_risk.py`, but that file does not exist. Existing related tests live under `tests/agent/test_nodes/test_assess_risk_and_approval.py`; approval tests used the established `tests/conftest.py` async DB fixtures.
- Running `tests/test_approval_models.py` and `tests/agent` at the same time caused the known shared `moca_test` drop/create collision. Rerunning `tests/agent` sequentially passed.

## Verification

- `uv run alembic upgrade head` - passed, including `004_latency_metrics -> 005_approval_tables`
- `uv run pytest tests/test_approval_models.py -q` - 13 passed, 1 warning
- `uv run ruff check src/db/models.py src/agent/state.py src/agent/trace.py src/repositories/ tests/test_approval_models.py` - passed
- `uv run pytest tests/agent -q` - 39 passed, 1 warning

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 04-03 can build the approval interrupt and resume workflow on top of durable approval records, tenant-scoped repository methods, idempotent decisions, and post-resume trace helpers.

## Self-Check: PASSED

- Verified summary, migration, repositories, and approval test file exist.
- Verified task commits are reachable: `42a149a`, `6aef8c4`, `01714da`, `a9b3e62`, `3194b91`, `116dd97`.
- Verified key symbols exist: `ApprovalRequest`, `ApprovalRepository`, `ActionDraftRepository`, `update_agent_run_status`, and `append_agent_steps`.

---
*Phase: 04-approval-workflow-audit*
*Completed: 2026-05-16*
