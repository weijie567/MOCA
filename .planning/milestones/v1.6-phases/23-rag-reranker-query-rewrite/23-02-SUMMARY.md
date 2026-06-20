---
phase: 23-rag-reranker-query-rewrite
plan: "02"
subsystem: knowledge
tags: [rag, query-rewrite, safe-summary, evidence-boundary]
requires:
  - phase: 23-01
    provides: RED query rewrite, diagnostics, and boundary tests
provides:
  - Strict frozen QueryRewritePlan and RewriteExpansion contracts
  - Deterministic local query rewrite aliases and skip rules
  - Safe query rewrite summary compatibility for KnowledgeSearchResult.query_rewrite
affects: [phase-23, retrieval-quality, knowledge-schemas]
tech-stack:
  added: []
  patterns:
    - Pydantic ConfigDict(extra="forbid", frozen=True) for internal DTOs
    - Safe summary strings cross from rewrite into diagnostics/search compatibility fields
key-files:
  created:
    - src/knowledge/rewrite.py
    - src/knowledge/diagnostics.py
  modified:
    - src/knowledge/config.py
    - tests/knowledge/test_query_rewrite.py
    - tests/knowledge/test_retrieval_diagnostics.py
key-decisions:
  - "Query rewrite accepts trusted context only as read-only input and never stores tenant/scope/filter fields in rewrite DTOs."
  - "Safe rewrite summaries carry counts/triggers or skip reasons, not raw query prompts or provider/private payloads."
patterns-established:
  - "build_query_rewrite_plan supports deterministic local aliases and explicit skip reasons."
  - "KnowledgeSearchResult.query_rewrite remains a str compatibility field populated from safe_rewrite_summary(plan)."
requirements-completed:
  - QRW-01
  - QRW-02
  - QRW-03
  - QRW-05
  - BND-01
  - BND-02
  - BND-06
duration: 12min
completed: 2026-06-20
---

# Phase 23 Plan 02: Query Rewrite Contract Summary

**Strict local query rewrite planner with bounded aliases, deterministic skip reasons, and safe summary compatibility**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-19T23:44:00Z
- **Completed:** 2026-06-19T23:56:17Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Implemented `RewriteExpansion`, `QueryRewritePlan`, `build_query_rewrite_plan`, and `safe_rewrite_summary`.
- Added versioned query rewrite config constants and local aliases for refund, shipment, compensation, return-window, and refund-timeout language.
- Added deterministic skip handling for specific, out-of-domain, unsafe, missing-context, and disabled rewrite cases.
- Preserved `EvidenceRefV1` exactly and kept `KnowledgeSearchResult.query_rewrite` as a safe-summary-only compatibility field.

## Task Commits

1. **Task 1 RED: Rewrite contract tests** - `948cd42` (test)
2. **Task 1 GREEN: Strict rewrite contracts** - `a5cc06d` (feat)
3. **Task 2 RED: Skip and safe summary tests** - `cd54120` (test)
4. **Task 2 GREEN: Deterministic skip summaries** - `f2e4776` (feat)
5. **Task 3: Safe query_rewrite compatibility** - `d4fe159` (test)

## Files Created/Modified

- `src/knowledge/rewrite.py` - Strict rewrite DTOs, alias expansion, skip rules, and safe summaries.
- `src/knowledge/config.py` - Query rewrite version and budget constants.
- `src/knowledge/diagnostics.py` - Minimal strict diagnostics DTOs needed for safe rewrite summary verification.
- `tests/knowledge/test_query_rewrite.py` - Contract, skip, no-widening, and compatibility coverage.
- `tests/knowledge/test_retrieval_diagnostics.py` - Safe rewrite summary redaction coverage.

## Verification

- `uv run pytest tests/knowledge/test_query_rewrite.py tests/knowledge/test_retrieval_diagnostics.py::test_query_rewrite_summary_excludes_raw_payloads tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q --tb=short` passed.
- `uv run ruff check src/knowledge/rewrite.py src/knowledge/config.py src/knowledge/schemas.py tests/knowledge/test_query_rewrite.py tests/knowledge/test_retrieval_diagnostics.py src/knowledge/diagnostics.py` passed.
- `gsd-sdk query verify.key-links .planning/phases/23-rag-reranker-query-rewrite/23-02-PLAN.md` passed.

## Decisions Made

- Kept rewrite local and deterministic for default tests; live/provider rewrite remains out of scope.
- Preserved `EvidenceRefV1` and did not add rewrite/rerank/diagnostic/provider fields to evidence identity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added minimal diagnostics DTOs during Plan 02**
- **Found during:** Task 2 safe summary verification
- **Issue:** The planned Task 2 verification imports `src.knowledge.diagnostics.build_retrieval_diagnostics`, but `src/knowledge/diagnostics.py` was not listed in Plan 02 `files_modified`.
- **Fix:** Added a minimal strict diagnostics module that only supports safe rewrite summary redaction and ranking DTO construction. Full diagnostics expansion remains owned by later Phase 23 plans.
- **Files modified:** `src/knowledge/diagnostics.py`
- **Verification:** Safe summary diagnostics test and ruff passed.
- **Committed in:** `f2e4776`

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** Necessary to satisfy the plan's own verification command. No EvidenceRefV1 or ordinary-surface authority expansion.

## Issues Encountered

- The spawned Wave 2 executor did not return a completion signal. Its partial commits were verified and the remaining implementation was completed inline.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `23-03`: retrieval can wire original-query plus rewritten-query channels using `build_query_rewrite_plan()` and `safe_rewrite_summary()`.

## Self-Check: PASSED

- `QueryRewritePlan` exists, is strict/frozen, and preserves `original_query`.
- Rewrite skip reasons are deterministic and tested.
- Rewrite output cannot widen trusted filters.
- Raw rewrite payloads/reasoning do not enter `KnowledgeSearchResult`, `EvidenceRefV1`, or ordinary surfaces.

---
*Phase: 23-rag-reranker-query-rewrite*
*Completed: 2026-06-20*
