---
phase: 02-rag-pipeline
reviewed: 2026-05-11T02:59:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/rag/ingestion.py
  - src/rag/retriever.py
  - scripts/eval_rag_hit_at_5.py
  - tests/test_ingestion.py
  - tests/test_retriever.py
  - tests/test_rag_eval.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-11T02:59:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed Plan 07 changes for contextual ingestion, hybrid retrieval reranking, fallback behavior, tenant/filter preservation, eval scoring integrity, and focused tests. The eval script keeps official Hit@5 scoring at `top_k=5`, tenant/doc_type/risk_level filters are still passed through the repository boundary, and deterministic tests cover the main reranking and threshold invariants.

One retrieval correctness risk remains: the support-domain guard can suppress valid high-confidence evidence before evidence construction when the query lacks one of the hard-coded anchor words.

## Warnings

### WR-01: Domain-anchor guard can hide valid high-confidence retrieval results

**File:** `/Users/ming/projects/MOCA/src/rag/retriever.py:109`

**Issue:** `Retriever.search()` initializes `results = []` and only reranks/returns evidence when `_has_domain_anchor(query)` is true. That means a valid policy question with strong vector evidence can return `no_evidence` solely because the user omitted the current anchor vocabulary. For example, a support query like `已拆封但不影响二次销售怎么办？` can match refund policy content at a high score, but it contains none of the configured anchors such as `退款`, `退货`, `商品`, or `客服`, so lines 109-115 discard all candidates. This regresses retrieval correctness and makes fallback behavior depend on a brittle keyword list rather than the tenant-filtered retrieval evidence.

**Fix:** Do not use the anchor check as an absolute prerequisite for returning evidence. Rerank threshold-qualified candidates first, then use the domain guard only to suppress weak/noisy out-of-domain matches. Add regression tests for both a valid no-anchor support query and an anchored out-of-domain query.

```python
reranked_results = [
    (chunk, score)
    for chunk, score in _rerank_candidates(query, raw_results)
    if score >= MIN_SIMILARITY_THRESHOLD
]

if _has_domain_anchor(query):
    results = reranked_results[:top_k]
else:
    query_terms = _query_terms(query)
    results = [
        (chunk, score)
        for chunk, score in reranked_results
        if score >= STRONG_EVIDENCE_THRESHOLD
        and _overlap_ratio(query_terms, f"{chunk.document.title} {chunk.section} {chunk.content}") > 0
    ][:top_k]
```

Also add focused coverage similar to:

```python
@pytest.mark.asyncio
async def test_valid_no_anchor_policy_query_can_return_strong_evidence():
    chunk = _chunk(
        section="七天无理由",
        content="拆封后不影响二次销售时，可以支持七天无理由退货退款。",
    )
    retriever, _, _ = _retriever([(chunk, 0.82)])

    result = await retriever.search("已拆封但不影响二次销售怎么办？", tenant_id=uuid4())

    assert result.retrieval_status == "strong_evidence"
    assert result.evidence
```

---

_Reviewed: 2026-05-11T02:59:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
