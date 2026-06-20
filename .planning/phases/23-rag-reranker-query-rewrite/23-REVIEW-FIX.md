---
phase: 23-rag-reranker-query-rewrite
fixed_at: 2026-06-20T00:53:54Z
review_path: .planning/phases/23-rag-reranker-query-rewrite/23-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 23: Code Review Fix Report

**Fixed at:** 2026-06-20T00:53:54Z
**Source review:** `.planning/phases/23-rag-reranker-query-rewrite/23-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Rerank Runs After `max_results` Trimming

**Files modified:** `src/knowledge/retrieval.py`, `tests/knowledge/test_hybrid_retrieval.py`
**Commit:** 47de51d
**Applied fix:** Rerank now receives the eligible candidate set before final `max_results` trimming, with a regression test proving a later candidate can be promoted.
**Tests:** `tests/knowledge/test_hybrid_retrieval.py::test_reranker_sees_candidates_before_max_results_trim`

### WR-02: Golden Rewrite Alias Cases Skip Rewrite

**Files modified:** `src/knowledge/rewrite.py`, `tests/knowledge/test_query_rewrite.py`
**Commit:** fdfed00
**Applied fix:** Added synonym-aware alias rules with canonical trigger emission for the Phase 23 golden rewrite cases.
**Tests:** `tests/knowledge/test_query_rewrite.py::test_rewrite_plan_matches_phase23_golden_trigger_metadata`

### WR-03: Ablation Non-Dry-Run Still Uses Fake Results

**Files modified:** `scripts/eval_rag_ablation.py`, `tests/test_rag_ablation_eval.py`
**Commit:** c219b3f
**Applied fix:** Non-dry-run ablation now fails closed until real retrieval execution exists, and dry-run scoring consumes `expected_variant_wins` metadata.
**Tests:** `tests/test_rag_ablation_eval.py::test_run_rag_ablation_fails_closed_for_non_dry_run`, `tests/test_rag_ablation_eval.py::test_dry_run_consumes_expected_variant_wins_from_golden`

### WR-04: Ablation Hit Scoring Accepts Wrong Chunks From The Right Doc

**Files modified:** `scripts/eval_rag_ablation.py`, `tests/test_rag_ablation_eval.py`
**Commit:** 77d8040
**Applied fix:** Ablation scoring now requires an expected chunk match whenever `expected_chunk_ids` are provided.
**Tests:** `tests/test_rag_ablation_eval.py::test_expected_chunks_override_doc_level_hit_scoring`

## Verification

`PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider tests/knowledge/test_query_rewrite.py tests/test_rag_ablation_eval.py tests/knowledge/test_reranker.py tests/knowledge/test_hybrid_retrieval.py`

Result: 28 passed, 1 warning.

---

_Fixed: 2026-06-20T00:53:54Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
