---
phase: 36-merchant-scope-db-hardening-role-cleanup
plan: 36-04
subsystem: approvals-actions-database
tags: [merchant-scope, approvals, action-drafts, safety-snapshots, sqlalchemy]

requires:
  - phase: 36-03
    provides: AgentRun target merchant binding and scope classification
provides:
  - Hash-bound ActionSafetySnapshot target merchant proof
  - ApprovalRequest creation and revision gates against linked AgentRun scope
  - ActionDraft run/approval/snapshot target consistency validation
  - Focused contradiction regressions for MSH-05 and MSH-07
affects: [phase-36, migration-preflight, action-drafts, approval-service, trace-replay-readiness]

tech-stack:
  added: []
  patterns:
    - Typed target merchant proof is persisted beside immutable snapshot JSON/hash.
    - ApprovalService validates business-scoped AgentRun target binding before persistence.
    - ActionService validates run scope and snapshot proof before draft insert/reuse.

key-files:
  created:
    - tests/approvals/test_phase36_scope_consistency.py
    - .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-04-SUMMARY.md
  modified:
    - src/db/models.py
    - src/approvals/snapshots.py
    - src/approvals/snapshot_service.py
    - src/approvals/repository.py
    - src/approvals/service.py
    - src/actions/service.py
    - tests/actions/test_phase34_action_draft_bindings.py

key-decisions:
  - "ActionSafetySnapshot target merchant fields are typed columns and hash material; raw snapshot_json is not standalone authorization proof."
  - "ApprovalService owns business validation before repository persistence; ApprovalRepository remains a low-level persistence helper."
  - "ActionService returns stable safe error codes for run-scope and snapshot-scope mismatches before draft creation."

patterns-established:
  - "Snapshot hash projection includes target_merchant_id, canonical target_merchant_ref, and canonical business_fact_refs."
  - "Run scope gate precedes approval/action persistence for business-targeted approval and draft roots."
  - "Existing Phase 34 approval binding comparison remains active after run and snapshot consistency gates."

requirements-completed: [MSH-05, MSH-07]

duration: 18 min
completed: 2026-06-30
---

# Phase 36 Plan 36-04: Approval/Action/Snapshot Target Consistency Summary

**Approval requests, action drafts, and safety snapshots now fail closed when their target merchant proof contradicts a linked business-scoped AgentRun.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-30T07:47:46Z
- **Completed:** 2026-06-30T08:05:49Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added ActionSafetySnapshot target merchant proof fields to the Pydantic contract, ORM model, immutable hash projection, repository write path, and persistence reload verification.
- Added ApprovalService gates so business-scoped AgentRun target binding must match ApprovalRequest target binding before request creation or revision snapshot creation.
- Added ActionService gates so action drafts validate linked run scope and snapshot target proof before draft insert/reuse.
- Added focused tests for missing, mismatched, non-business, unknown-legacy, snapshot-mismatched, and exact-match paths while preserving Phase 34 action draft behavior.

## Task Commits

1. **Task 1 RED: snapshot target proof tests** - `26280b8` (test)
2. **Task 1 GREEN: snapshot target proof implementation** - `95613c6` (feat)
3. **Task 2 RED: scope contradiction tests** - `5f78675` (test)
4. **Task 2 GREEN: run/approval/action/snapshot gates** - `d6e2813` (feat)

## Files Created/Modified

- `src/db/models.py` - Added ActionSafetySnapshot target merchant columns and tenant/target index.
- `src/approvals/snapshots.py` - Added target proof fields and canonical hash projection material.
- `src/approvals/snapshot_service.py` - Persists and reload-verifies typed target proof columns.
- `src/approvals/repository.py` - Writes snapshot target proof columns.
- `src/approvals/service.py` - Validates AgentRun scope and snapshot scope before approval persistence/revision paths.
- `src/actions/service.py` - Validates run scope and snapshot proof before action draft creation.
- `tests/approvals/test_phase36_scope_consistency.py` - New cross-table contradiction test suite.
- `tests/actions/test_phase34_action_draft_bindings.py` - Keeps existing Phase 34 exact/mismatch coverage aligned with business-scoped runs.

## Decisions Made

- Kept business validation in ApprovalService/ActionService rather than moving it into repository helpers.
- Used typed snapshot target columns and immutable hash material as proof; `snapshot_json` remains persisted audit material but is not used as a shortcut.
- Kept owner/admin run visibility untouched; no trace, replay, status, evidence, or stream access guard was widened.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase36_scope_consistency.py -q --tb=short` -> 5 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase36_scope_consistency.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` -> 19 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/db/models.py src/approvals/service.py src/approvals/snapshots.py src/approvals/snapshot_service.py src/actions/service.py tests/approvals/test_phase36_scope_consistency.py tests/actions/test_phase34_action_draft_bindings.py` -> passed.
- Required positive and negative acceptance `rg` checks passed, including no `snapshot_json` or requested-by merchant shortcut matches in production approval/action services.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Canonicalized expected BusinessFactRef timestamps in snapshot hash tests**
- **Found during:** Task 1 GREEN
- **Issue:** The RED test expected nested business fact `_at` timestamp strings without fixed millisecond precision, but CanonicalHashProfile requires fixed-millisecond UTC strings in hash material.
- **Fix:** Updated the test helper to expect canonical fixed-millisecond timestamp projection while leaving persisted typed JSON assertions unchanged.
- **Files modified:** `tests/approvals/test_phase36_scope_consistency.py`
- **Verification:** Task 1 focused pytest passed.
- **Committed in:** `95613c6`

**2. [Rule 1 - Test Bug] Kept Phase 34 approval mismatch test below the new run-scope gate**
- **Found during:** Task 2 GREEN
- **Issue:** The existing Phase 34 mismatch test changed `target_merchant_id`, which now correctly fails earlier with `RUN_SCOPE_BINDING_MISMATCH`.
- **Fix:** Changed that test to mismatch `verified_evidence_refs`, preserving coverage for `_approval_phase34_binding_matches` after run/snapshot gates pass.
- **Files modified:** `tests/actions/test_phase34_action_draft_bindings.py`
- **Verification:** Combined focused pytest passed.
- **Committed in:** `d6e2813`

---

**Total deviations:** 2 auto-fixed test issues.
**Impact on plan:** No scope expansion. Both fixes aligned tests with the planned canonical hash profile and new validation order.

## Issues Encountered

- Initial `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` resolved to a stale Python 3.9 pytest entrypoint in the fresh worktree and failed on `datetime.UTC` during collection. I ran `UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev`, then reran the exact `uv run pytest` commands successfully. `.planning/LOCAL-VALIDATION-ISSUES.md` was not touched per orchestrator instruction.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Stub scan hits were type hints, nullable parameters, empty-list assertions, or existing model defaults, not placeholder behavior.

## Threat Flags

None. The new security-relevant surface matches the plan threat model: snapshot proof persistence and approval/action consistency gates.

## Next Phase Readiness

Plan 36-05 can add Alembic migration and preflight/backfill gates for the new ActionSafetySnapshot columns/index and the cross-table consistency facts now represented in ORM/service code.

## Self-Check: PASSED

- Summary file exists.
- Task commits found: `26280b8`, `95613c6`, `5f78675`, `d6e2813`.
- Key files exist on disk.
- Protected orchestrator artifacts remain unchanged: `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`.

---
*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Completed: 2026-06-30*
