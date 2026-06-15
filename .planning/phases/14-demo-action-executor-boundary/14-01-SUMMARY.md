---
phase: 14-demo-action-executor-boundary
plan: 01
subsystem: database
tags: [actions, postgres, alembic, pydantic, demo-mode]
requires:
  - phase: 13-approval-state-machine
    provides: ActionSafetySnapshot and approval hash binding fields consumed by action drafts
provides:
  - action_draft.v2 typed schema helpers
  - draft_outcome.v1 not-executed demo outcome contract
  - action_drafts ORM columns for Phase 14 binding and outcome persistence
  - 009_action_draft_v2 Alembic expansion migration
  - tenant-scoped action draft idempotency uniqueness
affects: [phase-14, phase-15, phase-17, action-drafts, replay]
tech-stack:
  added: []
  patterns: [nullable legacy expansion migration, tenant-scoped idempotency, strict pydantic contracts]
key-files:
  created:
    - tests/actions/test_action_draft_v2.py
    - src/db/migrations/versions/009_action_draft_v2.py
    - .planning/phases/14-demo-action-executor-boundary/14-01-SUMMARY.md
  modified:
    - src/actions/schemas.py
    - src/db/models.py
key-decisions:
  - "Contract proposed_action remains stored in the existing ActionDraft.payload JSONB column."
  - "Legacy action_drafts rows keep new v2 columns nullable; Phase 14-created rows must populate the complete contract."
  - "Database idempotency uniqueness is tenant-scoped as unique(tenant_id, idempotency_key)."
patterns-established:
  - "DraftOutcomeV1 is the canonical demo outcome: draft_outcome.v1, not_executed_demo, external_side_effect=false."
  - "ActionDraftV2Data forbids unknown fields and requires Phase 14 binding fields before downstream service work."
requirements-completed: [DEMO-01, DEMO-02]
duration: 5 min
completed: 2026-06-16
---

# Phase 14 Plan 01: Action Draft V2 Persistence Contract Summary

**Action draft v2 persistence with strict demo outcome schemas, tenant-scoped idempotency, and a live Alembic head upgrade**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-15T22:37:00Z
- **Completed:** 2026-06-15T22:42:10Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added strict Pydantic v2 contracts for `DraftOutcomeV1` and `ActionDraftV2Data`.
- Expanded `ActionDraft` with Phase 14 binding, lifecycle, retention, execution mode, and `draft_outcome` fields while preserving nullable legacy rows.
- Added `009_action_draft_v2` and upgraded the live PostgreSQL schema to Alembic head.
- Replaced global draft idempotency uniqueness with tenant-scoped `unique(tenant_id, idempotency_key)`.
- Added contract tests documenting that contract `proposed_action` is stored in the existing `payload` JSONB column.

## Task Commits

1. **Task 1 RED: Define draft outcome and schema contract tests** - `249f962` (test)
2. **Task 1 GREEN: Add action draft v2 schema helpers** - `706889e` (feat)
3. **Task 2 RED: Add persistence contract tests** - `a4bf494` (test)
4. **Task 2 GREEN: Add ORM and Alembic expansion** - `b576dbc` (feat)
5. **Task 3: Blocking schema readiness gate** - no code commit; verified by Alembic head upgrade.

## Files Created/Modified

- `tests/actions/test_action_draft_v2.py` - Schema, ORM metadata, migration source, idempotency, and external-surface negative contract tests.
- `src/actions/schemas.py` - `DraftOutcomeV1` and `ActionDraftV2Data` strict Pydantic models.
- `src/db/models.py` - `ActionDraft` v2 columns and tenant-scoped idempotency uniqueness.
- `src/db/migrations/versions/009_action_draft_v2.py` - Alembic expansion migration from `008_approval_state_machine`.
- `.planning/phases/14-demo-action-executor-boundary/14-01-SUMMARY.md` - Plan completion record.

## Decisions Made

- Contract `proposed_action` maps to the existing `ActionDraft.payload` storage column; no new `proposed_action` ORM column was added.
- `target_id`, `approval_revision_ref`, `execution_mode`, `draft_version`, `lifecycle_status`, `retention_policy`, and `draft_outcome` remain Phase 14 implementation fields unless the normative spec is revised.
- `009_action_draft_v2` only expands `action_drafts`; it does not create external execution, outbox, reconciliation, or compensation surfaces.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_action_draft_v2.py -q --tb=short` - passed, 14 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/schemas.py src/db/models.py src/db/migrations/versions/009_action_draft_v2.py tests/actions/test_action_draft_v2.py` - passed.

## Self-Check: PASSED

- Key files created/modified by this plan exist on disk.
- The live database upgraded to Alembic head with `009_action_draft_v2`.
- Plan-level pytest and ruff gates passed after the schema upgrade.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 2 can now build service, repository, idempotency, and state reset behavior on a live PostgreSQL schema that includes the Phase 14 `action_draft.v2` columns.

---
*Phase: 14-demo-action-executor-boundary*
*Completed: 2026-06-16*
