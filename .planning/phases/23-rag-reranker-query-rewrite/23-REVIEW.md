---
phase: 23-rag-reranker-query-rewrite
type: code-review
depth: standard
completed: 2026-06-20
---

# Phase 23 Code Review

## Scope

Reviewed Phase 23 retrieval-quality changes across:

- `src/knowledge/rewrite.py`
- `src/knowledge/retrieval.py`
- `src/knowledge/rerank.py`
- `src/knowledge/diagnostics.py`
- `src/knowledge/service.py`
- `scripts/eval_rag_ablation.py`
- Phase 23 knowledge, diagnostics, ablation, and boundary tests

## Findings

### FIXED: `no_evidence_precision` used the wrong denominator

- **Severity:** Medium
- **File:** `scripts/eval_rag_ablation.py`
- **Issue:** `no_evidence_precision` counted all cases in the denominator because every scored case carried `no_evidence_correct`. Precision should be measured over cases predicted as no-evidence.
- **Fix:** Added `predicted_no_evidence` to scored cases and compute precision only over those predictions.
- **Test:** Added `test_no_evidence_precision_counts_only_no_evidence_predictions`.
- **Commit:** `21c639e`

## Residual Risk

- The ablation script remains deterministic dry-run by default. It is suitable for Phase 23 gates, but a future live/database-backed eval should be added only under an explicit later scope.
- Existing LangChain deprecation warning from `langgraph/checkpoint/serde/encrypted.py` remains unrelated to Phase 23 behavior.

## Verdict

PASS after fix. No unresolved code-review findings remain for Phase 23 focused scope.
