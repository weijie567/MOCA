---
phase: 13-approval-state-machine
plan: 01
subsystem: approvals
tags: [canonical-hash, action-safety-snapshot, pydantic, pytest]

requires:
  - phase: 08-knowledge-facade
    provides: Canonical EvidenceRefV1 and canonical_evidence_projection
provides:
  - CanonicalHashProfile v1 shared hash helper
  - ActionSafetySnapshot v1 schema, hash projection, and builder
  - Golden byte tests for proposed_action.v1 and action_safety_snapshot.v1
affects: [phase-13-approval-state-machine, phase-14-demo-action-boundary, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - Recursive structured validation before canonical JSON serialization
    - Pydantic extra-forbid schemas for hashable approval snapshot contracts
    - EvidenceRefV1 projection reuse with score stripping and rank-aware sorting

key-files:
  created:
    - src/common/__init__.py
    - src/common/canonical_hash.py
    - src/approvals/__init__.py
    - src/approvals/schemas.py
    - src/approvals/snapshots.py
    - tests/approvals/test_canonical_hash.py
    - tests/approvals/test_snapshots.py
  modified: []

key-decisions:
  - "CanonicalHashProfile v1 lives in src/common/canonical_hash.py and is shared by approval, action, and replay consumers."
  - "The Phase 13-local action_safety_snapshot.v1 golden digest is frozen with exact canonical JSON and hash input bytes."
  - "ActionSafetySnapshot imports EvidenceRefV1 and canonical_evidence_projection instead of defining a reduced evidence schema."

patterns-established:
  - "Canonical hash callers pass complete allowed field sets so absent/null drift fails closed."
  - "Snapshot immutable_hash excludes immutable_hash/lifecycle fields and strips EvidenceRefV1.score while retaining rank."

requirements-completed:
  - SNAPSHOT-01

duration: 9 min
completed: 2026-06-15
---

# Phase 13 Plan 01: Canonical Hash and Action Safety Snapshot Summary

**CanonicalHashProfile v1 and ActionSafetySnapshot immutable hash contracts with fixed proposed_action and snapshot golden bytes**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-15T05:56:45Z
- **Completed:** 2026-06-15T06:06:37Z
- **Tasks:** 4
- **Files modified:** 7

## Accomplishments

- Added shared `src/common/canonical_hash.py` with deterministic `hash_profile.v1` bytes and `sha256:<hex>` output.
- Added `ActionSafetySnapshot` projection/builder that reuses canonical `EvidenceRefV1`, strips `score`, retains `rank`, and rejects raw payload-shaped keys.
- Added golden tests for both `proposed_action.v1` and `action_safety_snapshot.v1`, including exact canonical JSON, hash input bytes, and frozen digests.

## Task Commits

1. **Task 1: Add canonical hash golden tests before implementation** - `e3e054a` (test)
2. **Task 2: Implement CanonicalHashProfile v1 shared module** - `32f2870` (feat)
3. **Task 3: Add ActionSafetySnapshot golden tests** - `264056e` (test)
4. **Task 4: Implement ActionSafetySnapshot schema and builder** - `aea308a` (feat)

## Files Created/Modified

- `src/common/__init__.py` - Shared helper package marker.
- `src/common/canonical_hash.py` - Canonical JSON validation, hash input bytes, and digest helper.
- `src/approvals/__init__.py` - Approval domain package marker.
- `src/approvals/schemas.py` - Approval and proposed-action schema version literals.
- `src/approvals/snapshots.py` - ActionSafetySnapshot schema, hash projection, forbidden-key scanner, and builder.
- `tests/approvals/test_canonical_hash.py` - Golden and negative canonical hash tests.
- `tests/approvals/test_snapshots.py` - Golden and negative ActionSafetySnapshot tests.

## Verification

- `uv run pytest tests/approvals/test_canonical_hash.py tests/approvals/test_snapshots.py tests/knowledge/test_evidence_projection.py -q --tb=short` - **PASS**: 25 passed, 1 existing LangGraph deprecation warning.
- `uv run ruff check src/common src/approvals tests/approvals/test_canonical_hash.py tests/approvals/test_snapshots.py` - **PASS**.

## Decisions Made

- Used `src/common/canonical_hash.py` as the single shared owner for CanonicalHashProfile v1 rather than placing hash helpers under approvals.
- Froze the Phase 13 `action_safety_snapshot.v1` digest in tests with exact canonical JSON and input bytes, matching the plan constraint that the digest must not be hard-coded alone.
- Kept `EvidenceRefV1` as the snapshot evidence type and used `canonical_evidence_projection` for score stripping and rank-aware sorting.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Ruff flagged one unused import while implementing `src/approvals/snapshots.py`; it was removed before the Task 4 commit.
- `gsd-sdk query roadmap.update-plan-progress "13"` returned `updated: false` for this roadmap shape, so the equivalent Phase 13 checkbox/count/status update was applied manually.
- Some GSD state handlers accepted named arguments literally in STATE/REQUIREMENTS output; the affected metric, session, and requirement lines were corrected manually before the metadata commit.

## Known Stubs

None - stub scan found no placeholder data or unwired UI/data paths. The only match was the literal `"[]"` path marker used by recursive validation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-02 can consume `CanonicalHashProfile v1`, `ActionSafetySnapshot`, `snapshot_hash_projection`, and the golden tests while adding persistence/migration work. Approval service, API cutover, and runtime hash binding remain owned by later Phase 13 plans.

## Self-Check: PASSED

- Verified created files exist: `src/common/canonical_hash.py`, `src/approvals/snapshots.py`, `tests/approvals/test_canonical_hash.py`, `tests/approvals/test_snapshots.py`, and this summary.
- Verified task commits exist: `e3e054a`, `32f2870`, `264056e`, `aea308a`.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
