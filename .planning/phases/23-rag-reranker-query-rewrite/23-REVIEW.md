---
phase: 23-rag-reranker-query-rewrite
reviewed: 2026-06-20T01:43:37Z
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
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-06-20T01:43:37Z
**Depth:** deep
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Deep re-review covered the Phase 23 query rewrite, hybrid retrieval, reranker, diagnostics, service facade, golden cases, and boundary/leakage tests against current HEAD.

The requested post-fix checks are verified: ablation CLI no-arg execution defaults to dry-run; explicit `--deterministic-local` exits fail-closed with `NotImplementedError`; Phase 21/22 static guards still block non-owned Phase 23/search/execution surfaces while allowing the Phase 23-owned files; `retrieve_run().diagnostics` carries rerank metadata through `RetrievalDiagnostics` without extending `EvidenceRefV1`; and prior WR-01 through WR-04 remain fixed.

Verification run:
`PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider tests/agent/rag_context/test_leakage.py tests/agent/rag_context/test_verifier.py tests/agent/test_phase22_action_boundary.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py tests/knowledge/test_retrieval_budgets.py tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_service.py tests/test_rag_ablation_eval.py`

Result: 93 passed, 1 third-party deprecation warning.

## Warnings

### WR-05: Provider Rerank Scores Accept Boolean And NaN Values

**File:** `src/knowledge/rerank.py:423`
**Issue:** `_normalize_provider_scores()` checks `isinstance(raw_score, int | float)` and then only rejects values `< 0` or `> 1`. In Python, `bool` is an `int`, so a provider JSON value of `true` is accepted as `1.0`. `float("nan")` also passes the range check because comparisons with NaN are false. Either case can turn malformed provider output into a successful provider rank instead of the intended `provider_malformed_output` fallback.
**Fix:**
```python
import math

if isinstance(raw_score, bool) or not isinstance(raw_score, int | float):
    return None
score = float(raw_score)
if not math.isfinite(score) or score < 0 or score > 1:
    return None
```
Add a regression test in `tests/knowledge/test_reranker.py` or `tests/knowledge/test_retrieval_budgets.py` that provider scores of `True`, `False`, and `float("nan")` all produce `provider_malformed_output`.

### WR-06: Malformed Effective Time Disables Evidence Freshness Checks

**File:** `src/knowledge/service.py:309`
**Issue:** `get_verified_evidence_details()` converts malformed `effective_at` values to `None` via `_effective_date()` and then skips both future-effective and expired-row checks. A canonical row with `effective_date="2099-01-01"` is included when the caller passes `effective_at="not-a-date"`, so malformed trusted-context time can fail open and admit evidence that should be excluded from prompt/verifier authority surfaces.
**Fix:**
```python
effective_date = _effective_date(effective_at)
effective_at_malformed = bool(effective_at) and effective_date is None

# inside the per-ref validation, before inclusion:
if effective_at_malformed:
    reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
elif effective_date is not None and row_effective_date is not None and row_effective_date > effective_date:
    reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
elif effective_date is not None and row_expires_at is not None and row_expires_at < effective_date:
    reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
```
Add a regression test in `tests/knowledge/test_phase22_evidence_validation.py` with malformed `effective_at` and a future-effective row, asserting the evidence is excluded with freshness/effective-date reason codes.

---

_Reviewed: 2026-06-20T01:43:37Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
