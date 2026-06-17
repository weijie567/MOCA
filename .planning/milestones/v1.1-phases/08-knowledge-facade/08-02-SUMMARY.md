---
phase: 08-knowledge-facade
plan: 08-02
subsystem: knowledge
tags: [facade, adapter, retrieval, tenant-scope, effective-time]

# Dependency graph
requires:
  - phase: 08-knowledge-facade
    provides: Canonical EvidenceRefV1 and knowledge request/result schemas from 08-01
provides:
  - PolicyKnowledgeService evidence-only facade
  - Legacy RAG adapter producing full-text canonical EvidenceRefV1 values
  - Deterministic tenant-scoped and effective-time retrieval contract tests
affects: [08-04, 08-05, 13-approval-state-machine, 15-replay-event-contract]

# Tech tracking
tech-stack:
  added: []
  patterns: [trusted-context retrieval scope, adapter-owned legacy compatibility, deterministic effective-time cutoff]

key-files:
  created:
    - src/knowledge/config.py
    - src/knowledge/adapters.py
    - src/knowledge/service.py
    - tests/knowledge/test_facade_status.py
    - tests/knowledge/test_effective_time.py
    - tests/knowledge/test_tenant_scope.py
  modified: []

key-decisions:
  - "Use context.effective_at as both the effective cutoff and single deterministic retrieved_at boundary timestamp."
  - "Treat merchant_id as an authorization-only input until policy tables gain merchant scope."
  - "Keep tenant-over-global precedence deferred to a later policy-scope schema and query migration."

patterns-established:
  - "Knowledge facade returns only KnowledgeSearchResult; repository and chunk objects remain adapter-internal."
  - "Effective-date filtering runs before rerank and final top-k truncation."

requirements-completed: [KNOW-01, KNOW-02]

# Metrics
duration: 5 min
completed: 2026-06-07
---

# Phase 8 Plan 2: Policy Knowledge Facade Summary

**Evidence-only PolicyKnowledgeService with a legacy-compatible adapter that preserves retrieval semantics while producing deterministic full-text EvidenceRefV1 records**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-07T02:22:16Z
- **Completed:** 2026-06-07T02:27:01Z
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments

- Added stable retrieval/rerank config versions and facade status thresholds.
- Wrapped the existing repository/embedder pipeline without modifying legacy RAG, preserving rerank, overlap, domain-anchor, threshold, and timeout behavior.
- Enforced trusted tenant scope, merchant authorization-only handling, full-content evidence hashing, and effective filtering before final truncation.
- Added DB-free contract coverage for statuses, timeout errors, deterministic effective time, tenant isolation, and merchant scope.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add knowledge config version literals** - `5c80874` (feat)
2. **Task 2: Implement LegacyRagKnowledgeAdapter** - `a9a6581` (feat)
3. **Task 3: Implement PolicyKnowledgeService facade** - `a3468ba` (feat)
4. **Task 4: Facade contract tests** - `fc6aae6` (test)

## Files Created/Modified

- `src/knowledge/config.py` - Defines config versions and legacy-compatible status thresholds.
- `src/knowledge/adapters.py` - Runs tenant-scoped legacy retrieval and maps full chunks into EvidenceRefV1.
- `src/knowledge/service.py` - Exposes the evidence-only facade and public error contract.
- `tests/knowledge/test_facade_status.py` - Covers statuses, full-text hashes, canonical fields, and timeout errors.
- `tests/knowledge/test_effective_time.py` - Covers cutoff ordering and cross-call determinism.
- `tests/knowledge/test_tenant_scope.py` - Covers trusted tenant and merchant authorization boundaries.

## Decisions Made

- Used `context.effective_at` as the explicit `retrieved_at` value so identical retrieval inputs produce identical canonical evidence refs.
- Authorized merchant filters remain no-ops for policy queries because policy tables have no merchant column.
- Re-exported the legacy `search_policy` path from the adapter module for rollback compatibility.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Concurrent 08-03 commits landed between 08-02 task commits. They were left untouched; every 08-02 commit contains only plan-owned files.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge -q` - 26 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check` on all 08-02-owned source and test files - passed.
- Owned commit file scan confirms only the six files listed by 08-02 were changed before this summary.
- No files under `src/rag/`, `src/agent/`, or `src/db/` were modified by 08-02.

## Known Stubs

None.

## Threat Flags

None - the new facade and adapter surfaces are covered by the plan threat model and contract tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The knowledge facade is ready for node cutover in 08-04.
- Tenant-over-global and merchant-scoped policy queries remain explicitly deferred to the later policy-scope owner phase.

## Self-Check: PASSED

- All six owned implementation/test files exist.
- All four task commits exist.
- Full knowledge tests, lint, and ownership-boundary checks pass.

---
*Phase: 08-knowledge-facade*
*Completed: 2026-06-07*
