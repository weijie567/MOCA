---
phase: 23-rag-reranker-query-rewrite
plan: "01"
subsystem: testing
tags: [rag, retrieval, query-rewrite, reranker, diagnostics, eval, boundaries]
requires:
  - phase: 20
    provides: hybrid retrieval foundation and trusted filter propagation
  - phase: 21
    provides: parser/OCR/source-block provenance boundary guards
  - phase: 22
    provides: ContextBuilder, verifier, and action-boundary evidence contracts
provides:
  - Phase 23 RED tests for query rewrite, reranking, diagnostics, budgets, ablation, and boundaries
  - Static allowlist for Phase 23-owned rewrite/rerank surfaces only
  - Regression guard that keeps EvidenceRefV1 identity and deferred scopes unchanged
affects: [phase-23, retrieval-quality, evidence-boundaries]
tech-stack:
  added: []
  patterns:
    - Future imports inside test helpers so pytest collection succeeds before production modules exist
    - RED wrappers expect pytest exit 1 while ruff and existing boundary checks pass
key-files:
  created:
    - tests/knowledge/test_query_rewrite.py
    - tests/knowledge/test_reranker.py
    - tests/knowledge/test_retrieval_diagnostics.py
    - tests/knowledge/test_retrieval_budgets.py
    - tests/test_rag_ablation_eval.py
  modified:
    - tests/knowledge/test_hybrid_retrieval.py
    - tests/knowledge/test_phase21_boundaries.py
key-decisions:
  - "Wave 0 pins Phase 23 behavior as RED tests before production rewrite/rerank modules exist."
  - "Phase 23 static boundary allowances are path-scoped to owned rewrite, rerank, diagnostics, eval, and test files."
patterns-established:
  - "Phase 23 future API tests import inside helper functions rather than at module import time."
  - "Rerank/rewrite RED tests assert safe fallback, no filter widening, and no leakage of raw internals."
requirements-completed:
  - QRW-01
  - QRW-02
  - QRW-03
  - QRW-04
  - QRW-05
  - RRK-01
  - RRK-02
  - RRK-03
  - RRK-04
  - RRK-05
  - RRK-06
  - EXP-01
  - EXP-02
  - EXP-03
  - EXP-04
  - EVAL-01
  - EVAL-02
  - EVAL-03
  - EVAL-04
  - EVAL-05
  - BND-01
  - BND-02
  - BND-03
  - BND-04
  - BND-05
  - BND-06
duration: 13min
completed: 2026-06-20
---

# Phase 23 Plan 01: Validation Scaffold Summary

**RED pytest scaffold for Phase 23 query rewrite, reranker, diagnostics, ablation, latency budgets, and boundary preservation**

## Performance

- **Duration:** 13 min
- **Started:** 2026-06-19T23:29:39Z
- **Completed:** 2026-06-19T23:42:58Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added RED tests for bounded query rewrite and deterministic/local reranker contracts.
- Added RED tests for safe retrieval diagnostics, explicit rewrite/rerank budgets, and no-live-provider ablation reporting.
- Extended hybrid retrieval and static boundary tests so Phase 23 can add owned rewrite/rerank surfaces without opening deferred Phase 17, RAG-5, or Policy Source Operations scope.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create query rewrite and reranker RED tests** - `146887d` (test)
2. **Task 2: Create diagnostics, budgets, and ablation eval RED tests** - `3dd3969` (test)
3. **Task 3: Extend hybrid retrieval and static boundary RED expectations** - `f98ec31` (test)

## Files Created/Modified

- `tests/knowledge/test_query_rewrite.py` - Pins `QueryRewritePlan`, `RewriteExpansion`, and `build_query_rewrite_plan` behavior.
- `tests/knowledge/test_reranker.py` - Pins `DefaultLocalReranker`, provider fallback, identity preservation, and reranker input redaction.
- `tests/knowledge/test_retrieval_diagnostics.py` - Pins internal-only diagnostics DTOs and safe ranking explanations.
- `tests/knowledge/test_retrieval_budgets.py` - Pins versioned timeout, retry, disabled-provider, and fallback constants.
- `tests/test_rag_ablation_eval.py` - Pins required ablation variants, golden categories, and blocking metrics.
- `tests/knowledge/test_hybrid_retrieval.py` - Adds original-query plus rewrite-channel merge/dedupe/fallback RED expectations.
- `tests/knowledge/test_phase21_boundaries.py` - Adds a narrow Phase 23 allowlist while preserving deferred-scope bans and exact `EvidenceRefV1` identity.

## Verification

- `uv run pytest tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py -q --tb=short` returned exit 1 as expected because `src.knowledge.rewrite` and `src.knowledge.rerank` do not exist yet.
- `uv run pytest tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_retrieval_budgets.py tests/test_rag_ablation_eval.py -q --tb=short` returned exit 1 as expected because Phase 23 diagnostics, config constants, and ablation script do not exist yet.
- `uv run pytest tests/knowledge/test_hybrid_retrieval.py::test_original_and_rewrite_channels_merge_before_rerank -q --tb=short` returned exit 1 as expected because retrieval does not run rewrite channels yet.
- `uv run pytest tests/knowledge/test_phase21_boundaries.py::test_phase22_boundary_guard_still_blocks_rerank_query_rewrite_search_backend_and_execution_scope tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q --tb=short` passed.
- `uv run pytest tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q` passed.
- `uv run ruff check tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_retrieval_budgets.py tests/test_rag_ablation_eval.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_phase21_boundaries.py` passed.

## Decisions Made

- None beyond the planned Wave 0 decisions in `23-01-PLAN.md`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first spawned executor did not return a usable completion signal. Execution continued via the documented sequential inline fallback, and all existing task commits were verified before summary creation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `23-02`: the rewrite contract can now be implemented against the RED tests without changing production retrieval behavior first.

## Self-Check: PASSED

- All Wave 0 test files named in `23-VALIDATION.md` exist.
- RED tests collect and fail for missing Phase 23 production implementation rather than syntax or collection errors.
- Static boundary guard is narrowed for Phase 23-owned files only.
- No production Phase 23 behavior was implemented in this plan.

---
*Phase: 23-rag-reranker-query-rewrite*
*Completed: 2026-06-20*
