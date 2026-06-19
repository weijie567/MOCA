---
phase: 22-rag-context-builder-hallucination-control
plan: "01"
subsystem: testing
tags: [pytest, rag-context, hallucination-control, red-tests]

# Dependency graph
requires:
  - phase: 21-rag-production-ingestion-ocr
    provides: "Canonical EvidenceRefV1, parser/OCR provenance boundaries, and source-block safety constraints."
provides:
  - "Wave 0 RED pytest scaffold for ContextBuilder bundle and budgeting behavior."
  - "Wave 0 RED pytest scaffold for MaterialClaim authority classes and Level 1/2 verification."
  - "Wave 0 RED pytest scaffold for Level 3 semantic verifier budgets/fail-closed behavior and deterministic routing."
affects: [phase-22, context-builder, material-claim, verifier, deterministic-routing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Future Phase 22 API imports live inside test helpers so pytest collection remains clean in RED state."
    - "Tests use deterministic local fakes and existing EvidenceRefV1/BusinessFactRefV1 DTOs only."

key-files:
  created:
    - tests/agent/rag_context/test_context_builder.py
    - tests/agent/rag_context/test_budgeting.py
    - tests/agent/rag_context/test_material_claims.py
    - tests/agent/rag_context/test_verifier.py
    - tests/agent/rag_context/test_authority_boundaries.py
    - tests/agent/rag_context/test_semantic_verifier.py
    - tests/agent/rag_context/test_routing.py
  modified: []

key-decisions:
  - "Wave 0 remains RED-only by plan scope; no Phase 22 production APIs were implemented."
  - "Future imports are inside test helpers so failures are test failures, not collection failures."

patterns-established:
  - "RED scaffold tests pin public src.agent.rag_context builder/claims/verifier/routing APIs before implementation."
  - "Semantic verifier tests use deterministic fake providers and assert fail-closed redaction boundaries."

requirements-completed:
  - CTX-01
  - CTX-03
  - CTX-04
  - CTX-05
  - CLM-01
  - CLM-02
  - CLM-03
  - CLM-04
  - CLM-05
  - VER-01
  - VER-02
  - VER-03
  - VER-04
  - VER-05
  - RTE-01
  - RTE-02
  - BND-03
  - BND-04

# Metrics
duration: 9 min
completed: 2026-06-19
---

# Phase 22 Plan 01: Wave 0 Unit Scaffold Summary

**RED pytest scaffold for ContextBuilder, MaterialClaim, verifier tiers, authority boundaries, semantic fail-closed behavior, and deterministic routes**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-19T08:40:52Z
- **Completed:** 2026-06-19T08:49:44Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Created all seven planned `tests/agent/rag_context/` Wave 0 RED unit files.
- Pinned ContextBuilder bundle projections, citation maps, dedupe/merge traceability, invalid-evidence exclusion, and protected budgeting behavior.
- Pinned MaterialClaim authority classes, Level 1/2 verification outcomes, business/memory/provenance/model authority boundaries, Level 3 semantic budgets, provider fail-closed behavior, and backend-owned route decisions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ContextBuilder unit RED tests** - `c68e9ac` (test)
2. **Task 2: Create MaterialClaim and Level 1/2 verifier RED tests** - `e760629` (test)
3. **Task 3: Create Level 3 semantic and deterministic routing RED tests** - `1e0d1c6` (test)

**Plan metadata:** final docs commit.

## Files Created/Modified

- `tests/agent/rag_context/test_context_builder.py` - RED tests for CTX-01, CTX-03, CTX-04, invalid evidence exclusion, citation maps, prompt/verifier/debug/final projections.
- `tests/agent/rag_context/test_budgeting.py` - RED tests for CTX-05 protected citation metadata and included/truncated/excluded budget traces.
- `tests/agent/rag_context/test_material_claims.py` - RED tests for CLM-01 strict MaterialClaim authority classes and stable claim IDs.
- `tests/agent/rag_context/test_verifier.py` - RED tests for CLM-02 through CLM-04 and VER-01 through VER-03.
- `tests/agent/rag_context/test_authority_boundaries.py` - RED tests for CLM-05, BND-03, and BND-04 authority separation.
- `tests/agent/rag_context/test_semantic_verifier.py` - RED tests for VER-04 and VER-05 semantic trigger/budget/fail-closed behavior.
- `tests/agent/rag_context/test_routing.py` - RED tests for RTE-01 and RTE-02 deterministic route matrix and action-boundary blocking.

## Verification

- `bash -lc 'set +e; uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 6 tests and failed with missing `src.agent.rag_context`.
- `bash -lc 'set +e; uv run pytest tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 15 tests and failed with missing `src.agent.rag_context`.
- `bash -lc 'set +e; uv run pytest tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 38 tests and failed with missing `src.agent.rag_context`.
- `bash -lc 'set +e; uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 59 tests and failed with missing `src.agent.rag_context`.
- `uv run ruff check tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py` - passed.

## Decisions Made

- Kept the plan RED-only. The expected failing condition is `ModuleNotFoundError: No module named 'src.agent.rag_context'` because production APIs are reserved for later Phase 22 plans.
- Used existing `EvidenceRefV1` and `BusinessFactRefV1` factories in tests so authority-boundary fixtures are realistic without requiring database, Redis, network, or live model providers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired GSD metadata handler output**
- **Found during:** Metadata update after Task 3
- **Issue:** The installed `gsd-sdk` accepted flag-shaped arguments as literal values for `state.record-metric` and `state.add-decision`, `state.record-session` reset stale milestone labels, and `roadmap.update-plan-progress` did not match the current roadmap format.
- **Fix:** Re-ran the working positional commands where available, manually repaired malformed STATE/REQUIREMENTS formatting, and manually marked the roadmap Plan 22-01 progress.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Verification:** Metadata diff was reviewed and scoped to Plan 22-01 progress; unrelated dirty study-plan file remained untouched.
- **Committed in:** final docs commit.

---

**Total deviations:** 1 auto-fixed (1 blocking metadata issue).
**Impact on plan:** No scope change to test scaffold. Metadata now reflects Plan 22-01 completion and Wave 0 RED scaffold status.

## Issues Encountered

- A transient Git index lock appeared when two `git add` commands were attempted in parallel. The lock cleared immediately; staging was completed sequentially. No files outside the task scope were staged or committed.
- The local GSD SDK handler behavior differed from the newer workflow examples for some metadata updates. The affected metadata was repaired before final commit.

## Known Stubs

None. Stub scan found only deliberate empty-list/`None` negative-test fixtures; no UI-flowing hardcoded placeholder data or TODO/FIXME markers were introduced.

## Authentication Gates

None.

## Threat Flags

None. The plan created pytest files only; no network endpoints, auth paths, file access patterns, or schema/trust-boundary runtime surfaces were introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 22-02. Plan 22-03/22-04/22-05 can implement the `src.agent.rag_context` APIs against these RED tests.

## Self-Check: PASSED

- Summary file exists.
- All seven planned RED test files exist.
- Task commits found: `c68e9ac`, `e760629`, `1e0d1c6`.

---
*Phase: 22-rag-context-builder-hallucination-control*
*Completed: 2026-06-19*
