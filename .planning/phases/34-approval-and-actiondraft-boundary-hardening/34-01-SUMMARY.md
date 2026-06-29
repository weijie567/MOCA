---
phase: 34-approval-and-actiondraft-boundary-hardening
plan: 34-01
subsystem: contracts
tags: [approval, action-draft, pydantic, sqlalchemy, alembic]

requires:
  - phase: 33-rag-context-build-and-claim-verification
    provides: verified evidence refs, claim verification summaries, and business fact refs consumed by Phase 34 bindings
provides:
  - Strict approval/action binding DTOs for target merchant, business facts, verified evidence, claim verification, risk decision, hashes, snapshots, and idempotency
  - Nullable legacy-safe approval_requests and action_drafts binding columns
  - Alembic migration 018 for Phase 34 approval/action binding persistence
affects: [risk_gate, approval_gate, approval-api, agent-runs, action-draft, replay-eval]

tech-stack:
  added: []
  patterns: [strict Pydantic DTOs, nullable legacy-safe JSONB binding columns, contract-first migration tests]

key-files:
  created:
    - tests/approvals/test_phase34_boundary_bindings.py
    - tests/actions/test_phase34_action_draft_bindings.py
    - src/db/migrations/versions/018_phase34_approval_action_bindings.py
  modified:
    - src/approvals/schemas.py
    - src/actions/schemas.py
    - src/db/models.py
    - tests/approvals/test_migration_contract.py
    - tests/actions/test_action_draft_v2.py

key-decisions:
  - "Approval and action draft binding fields use the same public names in DTOs, ORM metadata, and migration columns."
  - "Phase 34 persistence columns are nullable to keep legacy rows safe while later plans enforce exact binding checks at service boundaries."

patterns-established:
  - "Contract DTOs validate authority refs with BusinessFactRefV1, EvidenceRefV1, TargetMerchantBindingV1, and RiskDecisionV1 instead of raw dict authority."
  - "Migration contract tests require ORM metadata and Alembic migration source to declare matching Phase 34 binding columns."

requirements-completed: [APF-15]

duration: 7 min
completed: 2026-06-29
---

# Phase 34 Plan 01: Contract and Persistence Foundation Summary

**Approval and action draft binding contracts with nullable persistence columns and migration coverage**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-29T04:57:07Z
- **Completed:** 2026-06-29T05:04:38Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added strict Phase 34 approval DTOs: `RiskDecisionV1`, `TargetMerchantBindingV1`, `AutoAllowedActionBindingV1`, and binding fields on approval command/result/resume contracts.
- Enriched `ActionDraftV2Data` with typed target merchant, business fact, verified evidence, claim verification, risk decision, and auto-allowed binding refs.
- Added nullable legacy-safe ORM columns and migration 018 for `approval_requests` and `action_drafts`, with tests proving no real-execution table family was introduced.

## Task Commits

1. **Task 1 RED: Approval/action binding contract tests** - `d0a9f0f` (test)
2. **Task 1 GREEN: Approval/action binding DTOs** - `fc175ea` (feat)
3. **Task 2 RED: Persistence binding tests** - `463d33a` (test)
4. **Task 2 GREEN: ORM columns and migration 018** - `81791d2` (feat)

## Files Created/Modified

- `tests/approvals/test_phase34_boundary_bindings.py` - Contract tests for approval binding DTOs and trusted resume payload fields.
- `tests/actions/test_phase34_action_draft_bindings.py` - Contract tests for typed Phase 34 action draft binding refs.
- `src/approvals/schemas.py` - Approval/risk/auto-allowed binding models and command/result fields.
- `src/actions/schemas.py` - Enriched `ActionDraftV2Data` with typed Phase 34 refs.
- `src/db/models.py` - Nullable binding columns on approval requests and action drafts.
- `src/db/migrations/versions/018_phase34_approval_action_bindings.py` - Alembic expansion for Phase 34 persistence fields.
- `tests/approvals/test_migration_contract.py` - Migration/ORM contract coverage for Phase 34 approval/action columns.
- `tests/actions/test_action_draft_v2.py` - Action draft ORM/migration coverage for Phase 34 binding columns.

## Decisions Made

- Column names mirror DTO field names directly (`business_fact_refs`, `verified_evidence_refs`, `risk_decision_ref`, etc.) to avoid service-layer remapping in later plans.
- Binding columns are nullable at the persistence layer; fail-closed enforcement belongs to risk/approval/action service logic in later plans.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first executor did not return a completion signal before shutdown, but filesystem/git spot-checks showed Task 1 RED/GREEN commits had landed on `main`. Execution continued inline from Task 2 without losing work.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase34_boundary_bindings.py tests/actions/test_phase34_action_draft_bindings.py tests/approvals/test_migration_contract.py tests/actions/test_action_draft_v2.py -q --tb=short` -> `38 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/approvals/schemas.py src/actions/schemas.py src/db/models.py src/db/migrations/versions/018_phase34_approval_action_bindings.py tests/approvals/test_phase34_boundary_bindings.py tests/actions/test_phase34_action_draft_bindings.py tests/approvals/test_migration_contract.py tests/actions/test_action_draft_v2.py` -> passed
- `git diff --check` -> passed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 34-02. The graph/risk-gate work can consume typed DTO fields and persistence column names without introducing real execution surfaces.

## Self-Check: PASSED

- Key created files exist.
- `git log --oneline --grep="34-01"` returns RED/GREEN commits for both tasks.
- Focused pytest and ruff checks pass through the MOCA-approved `uv run` entrypoint.

---
*Phase: 34-approval-and-actiondraft-boundary-hardening*
*Completed: 2026-06-29*
