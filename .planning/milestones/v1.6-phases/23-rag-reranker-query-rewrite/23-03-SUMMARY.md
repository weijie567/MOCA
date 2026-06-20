---
phase: 23-rag-reranker-query-rewrite
plan: "03"
subsystem: knowledge
tags: [rag, query-rewrite, hybrid-retrieval, evidence-boundary]
requires:
  - phase: 23-02
    provides: Query rewrite contracts and safe summaries
provides:
  - Backward-compatible PolicyRetrievalRun with retrieval-owned EvidenceRefV1 construction
  - Original-first query channel fan-out with optional bounded rewrite channels
  - Merge/dedupe of original and rewrite candidates before final hits and evidence refs
  - Safe rewrite summary propagation through PolicyKnowledgeService.search
affects: [phase-23, retrieval-quality, knowledge-service]
tech-stack:
  added: []
  patterns:
    - Original-query retrieval remains the baseline and fallback path
    - Safe selected_by labels are internal hit diagnostics and never enter EvidenceRefV1
key-files:
  created: []
  modified:
    - src/knowledge/config.py
    - src/knowledge/retrieval.py
    - src/knowledge/rewrite.py
    - src/knowledge/service.py
    - tests/knowledge/test_hybrid_retrieval.py
    - tests/knowledge/test_service.py
key-decisions:
  - "retrieve() and retrieve_hits() are now wrappers over retrieve_run(), preserving public tuple shapes."
  - "PolicyRetrievalEngine builds EvidenceRefV1 after final merge/rank so service does not construct evidence identity."
  - "Generic already-specific queries such as plain '仅退款', '补偿券审批', and '退款时效' skip rewrite to preserve baseline behavior."
patterns-established:
  - "Original and rewrite channels pass identical tenant, doc_type, risk_level, and effective_date filters."
  - "Duplicate candidates merge by (doc_key, chunk_id, policy_version) before final ranking."
  - "PolicyKnowledgeService.search uses retrieve_run() when present and falls back to legacy retrieve() for fake retrievers."
requirements-completed:
  - QRW-04
  - QRW-05
  - BND-01
  - BND-02
  - BND-03
  - EVAL-05
duration: 10min
completed: 2026-06-20
---

# Phase 23 Plan 03: Retrieval Rewrite Channel Wiring Summary

**Original-first hybrid retrieval now supports bounded query rewrite channels, safe merge/dedupe, baseline fallback, and service-level safe summary propagation.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-20T07:56:17+08:00
- **Completed:** 2026-06-20T08:06:18+08:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `PolicyRetrievalRun` and made `retrieve()` / `retrieve_hits()` wrappers over the richer retrieval run.
- Extracted one-query dense/sparse/fuzzy/RRF retrieval into `_retrieve_query_channel()` and wired original-first rewrite fan-out.
- Added candidate caps `ORIGINAL_QUERY_TOP_K`, `REWRITE_QUERY_TOP_K`, and `MERGED_CANDIDATE_CAP`.
- Added merge/dedupe before final hits and `EvidenceRefV1.build()`, preserving canonical evidence identity.
- Added safe internal selected-channel labels for rewrite-influenced hits, while keeping original-only hit diagnostics backward-compatible.
- Updated `PolicyKnowledgeService.search()` to consume `retrieve_run()` when available and set `KnowledgeSearchResult.query_rewrite` from the safe summary.

## Task Commits

1. **Tasks 1-3: Retrieval fan-out, merge/dedupe, and service propagation** - `840e499` (feat)

## Files Created/Modified

- `src/knowledge/config.py` - Original/rewrite/merged candidate cap constants.
- `src/knowledge/retrieval.py` - `PolicyRetrievalRun`, original-first fan-out, safe channel labels, merge/dedupe, fallback, and evidence ref construction.
- `src/knowledge/rewrite.py` - Added colloquial shipment alias and conservative already-specific skip handling.
- `src/knowledge/service.py` - Optional `retrieve_run()` path with safe query rewrite summary propagation.
- `tests/knowledge/test_hybrid_retrieval.py` - Filter preservation, original-first channel order, merge/dedupe, safe labels, and fallback coverage.
- `tests/knowledge/test_service.py` - rich-run and legacy retriever compatibility coverage.

## Verification

- `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_query_rewrite.py tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_retrieval.py tests/knowledge/test_service.py -q --tb=short` passed (`39 passed`, one existing LangChain deprecation warning).
- `uv run ruff check src/knowledge/retrieval.py src/knowledge/service.py src/knowledge/rewrite.py src/knowledge/config.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_query_rewrite.py tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_retrieval.py tests/knowledge/test_service.py` passed.
- `gsd-sdk query verify.key-links .planning/phases/23-rag-reranker-query-rewrite/23-03-PLAN.md` passed.

## Decisions Made

- Kept rewrite additive and fail-open to the original-query hybrid baseline.
- Kept `EvidenceRefV1` clean: no selected channel labels, rewrite diagnostics, fallback reasons, or raw rewrite text are added to evidence refs.
- Treated single clear alias questions as already-specific unless they include context that materially benefits from rewrite expansion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Behavior preservation] Conservative rewrite trigger for existing tests**
- **Found during:** Task 1/2 verification
- **Issue:** Plain `仅退款怎么处理？`, `补偿券审批需要哪些信息？`, and `退款时效超过48小时怎么办？` started using rewrite channels, breaking existing original-only expectations and selected_by diagnostics.
- **Fix:** Added conservative skip handling for generic already-specific alias questions while retaining rewrite for shipment/refund ambiguity such as `商家已发货还能仅退款吗？` and `商家发了货还能只退款吗？`.
- **Files modified:** `src/knowledge/rewrite.py`
- **Verification:** Existing retrieval tests, new hybrid rewrite tests, query rewrite tests, and plan-level verification passed.
- **Committed in:** `840e499`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** Preserves baseline retrieval compatibility while keeping the planned additive rewrite channel for ambiguous questions.

## Issues Encountered

- The earlier spawned Wave 3 executor did not produce a usable completion signal, so this plan was completed inline after verifying the prior partial work.

## User Setup Required

None.

## Next Phase Readiness

Ready for `23-04`: reranker contract and deterministic/default reranking can build on `PolicyRetrievalRun.hits`, safe `selected_by` diagnostics, and retrieval-owned `EvidenceRefV1` construction.

## Self-Check: PASSED

- Original query channel runs first.
- Rewrite channels pass the same trusted filters as original channels.
- Merge/dedupe happens before final hit and evidence construction.
- Rewrite, channel, and merge failures fall back to original-query candidates with safe fallback reasons.
- `KnowledgeSearchResult.query_rewrite` receives only a safe summary.

---
*Phase: 23-rag-reranker-query-rewrite*
*Completed: 2026-06-20*
