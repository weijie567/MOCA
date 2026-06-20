---
phase: 23-rag-reranker-query-rewrite
reviewed: 2026-06-20T00:41:59Z
depth: deep
files_reviewed: 19
files_reviewed_list:
  - evaluation/golden/rag_cases.jsonl
  - scripts/eval_rag_ablation.py
  - src/knowledge/config.py
  - src/knowledge/diagnostics.py
  - src/knowledge/rerank.py
  - src/knowledge/retrieval.py
  - src/knowledge/rewrite.py
  - src/knowledge/service.py
  - tests/agent/rag_context/test_leakage.py
  - tests/agent/rag_context/test_verifier.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/knowledge/test_hybrid_retrieval.py
  - tests/knowledge/test_phase21_boundaries.py
  - tests/knowledge/test_query_rewrite.py
  - tests/knowledge/test_reranker.py
  - tests/knowledge/test_retrieval_budgets.py
  - tests/knowledge/test_retrieval_diagnostics.py
  - tests/knowledge/test_service.py
  - tests/test_rag_ablation_eval.py
findings:
  critical: 0
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-06-20T00:41:59Z
**Depth:** deep
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Deep review covered the Phase 23 query rewrite, hybrid retrieval, reranker, diagnostics, service facade, golden cases, and focused tests. No critical security issue was found, but four correctness/test-gate issues remain: rerank is applied after result trimming, two golden rewrite expectations are not implemented, the ablation harness can label fake local execution as non-dry-run, and ablation scoring can pass the wrong chunk as a hit.

Verification run: `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider tests/knowledge/test_query_rewrite.py tests/test_rag_ablation_eval.py tests/knowledge/test_reranker.py tests/knowledge/test_hybrid_retrieval.py` passed: 23 tests.

## Warnings

### WR-01: Rerank Runs After `max_results` Trimming

**File:** `src/knowledge/retrieval.py:538`
**Issue:** `_finalize_hits()` slices `fused_results` to `limit` before building `RerankCandidate`s. A candidate outside the RRF top `max_results` can never be promoted by the Phase 23 reranker, even when local/provider rerank would rank it first. This also means retrieval rarely exercises the configured rerank candidate budget.
**Fix:**
```python
eligible = fused_results if has_domain_anchor(query) else [
    candidate
    for candidate in fused_results
    if candidate.confidence >= STRONG_EVIDENCE_THRESHOLD and has_candidate_overlap(terms, candidate.chunk)
]
rerank_inputs = tuple(
    _to_rerank_candidate(candidate, baseline_rank=rank)
    for rank, candidate in enumerate(eligible[:MERGED_CANDIDATE_CAP], start=1)
)
rerank_output = await rerank_candidates_for_query(query=query, candidates=rerank_inputs, config=RerankConfig())
ordered_candidates = rerank_output.ranked_candidates[:limit]
```
Add a test where a candidate below the RRF top-`max_results` cutoff is promoted when the full eligible candidate set is reranked.

### WR-02: Golden Rewrite Alias Cases Skip Rewrite

**File:** `src/knowledge/rewrite.py:71`
**Issue:** `evaluation/golden/rag_cases.jsonl` expects rewrites for line 16 (`只退款不退货` / `发出去了`) and line 17 (`商家举证`), but `_ALIAS_RULES` only matches exact terms such as `仅退款`, `已发货`, and `发了货`. Those two golden cases currently return `skip_reason="already_specific"` with no expansions, so the implementation does not satisfy its own Phase 23 golden metadata.
**Fix:** Add synonym-aware alias rules or canonical trigger mapping, then assert the golden expectations in tests. For example:
```python
("只退款", "仅退款 商家举证 物流状态", "domain_synonym"),
("不退货", "仅退款 商家举证 物流状态", "domain_synonym"),
("发出去了", "商家已发货 物流核实", "intent_normalization"),
("商家举证", "商家举证 物流状态 履约证据", "merchant_support_alias"),
```
If `expected_rewrite_triggers` must stay canonical (`仅退款`, `已发货`), extend the rule shape so matched input aliases can emit canonical trigger terms.

### WR-03: Ablation Non-Dry-Run Still Uses Fake Results

**File:** `scripts/eval_rag_ablation.py:141`
**Issue:** `run_rag_ablation()` builds every variant from `_fake_variant_result()` regardless of `dry_run`. The CLI defaults `--dry-run` to false, so running the script normally reports `mode="deterministic_local"` while still scoring synthetic evidence copied from the golden expected IDs. This can mask retrieval/rewrite/rerank regressions and makes `expected_variant_wins` ineffective.
**Fix:** Either wire non-dry-run to real deterministic retrieval variants, or fail closed until that exists:
```python
if not dry_run:
    raise NotImplementedError("deterministic_local ablation requires real retrieval execution")
```
Also add tests that consume `expected_rewrite_triggers` and `expected_variant_wins` from the golden JSONL so those fields are not inert metadata.

### WR-04: Ablation Hit Scoring Accepts Wrong Chunks From The Right Doc

**File:** `scripts/eval_rag_ablation.py:240`
**Issue:** `_first_match_rank()` returns a hit when either `chunk_id` matches `expected_chunk_ids` or `doc_key` matches `expected_doc_ids`. For cases with explicit expected chunks, retrieving `refund_policy_001` passes even when the case expects `refund_policy_005`; `missing_expected_chunks` records the miss but does not fail the case.
**Fix:**
```python
for rank, item in enumerate(evidence, start=1):
    chunk_id = str(item.get("chunk_id", ""))
    doc_key = str(item.get("doc_key", ""))
    if expected_chunks:
        if chunk_id in expected_chunks:
            return int(item.get("rank") or rank)
    elif doc_key in expected_docs:
        return int(item.get("rank") or rank)
return None
```
Add a regression test where the correct document but wrong chunk is scored as a miss.

---

_Reviewed: 2026-06-20T00:41:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
