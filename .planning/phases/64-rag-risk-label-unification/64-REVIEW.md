---
phase: 64-rag-risk-label-unification
reviewed: 2026-07-10T00:18:48Z
depth: deep
files_reviewed: 10
files_reviewed_list:
  - src/agent/nodes/recommendation_generation.py
  - src/agent/rag_context/builder.py
  - src/agent/rag_context/metrics.py
  - src/agent/rag_context/risk_labels.py
  - src/agent/rag_context/routing.py
  - src/agent/rag_context/verifier.py
  - tests/agent/rag_context/test_context_builder.py
  - tests/agent/rag_context/test_metrics.py
  - tests/agent/rag_context/test_risk_labels.py
  - tests/architecture/test_rag_risk_label_boundaries.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 64: Code Review Report

**Reviewed:** 2026-07-10T00:18:48Z
**Depth:** deep
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the bounded Phase 64 RAG risk label unification scope against the current working tree, including the canonical registry, builder projections, verifier semantic triggers, backend route mappings, hallucination metrics, recommendation-generation label filtering, and architecture drift guards. The registry correctly keeps route reason codes out of prompt-safe evidence labels, preserves `manual_review_sensitive` for single-entry safe projections, and keeps semantic provider route reasons route-only.

The main issue is in the builder's aggregation of risk hints: duplicate entries for the same evidence id replace earlier safe labels instead of merging them. That can drop `manual_review_sensitive` before it reaches prompt/citation/verifier surfaces.

## Warnings

### WR-01: Duplicate Risk Hints Can Drop Manual Review Labels

**File:** `/Users/ming/projects/MOCA/src/agent/rag_context/builder.py:421`
**Issue:** `_risk_labels_by_evidence_id` assigns `labels[evidence_id] = ...` for each hint. If the input contains more than one hint for the same evidence id, the later entry overwrites earlier safe labels. A later entry with `["authority_checked"]` or only unknown labels would remove a prior `manual_review_sensitive`, so `citation_map.risk_labels` and verifier `_snippet_risk_labels()` no longer trigger semantic/manual-review handling for that evidence. The current tests cover unknown-label filtering within one hint, but not duplicate hint merging.
**Fix:**
```python
def _risk_labels_by_evidence_id(hints: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    for hint in hints:
        evidence_id = str(hint.get("evidence_id") or "")
        if not evidence_id:
            continue
        bucket = labels.setdefault(evidence_id, [])
        for label in filter_prompt_safe_risk_labels(hint.get("labels") or []):
            if label not in bucket:
                bucket.append(label)
    return labels
```
Add a regression test with two `risk_hints` entries for the same evidence id, where the first contains `manual_review_sensitive` and the second contains another safe label plus an unknown label.

## Info

### IN-01: Drift Guard Is Tied To Old Local Variable Names

**File:** `/Users/ming/projects/MOCA/tests/architecture/test_rag_risk_label_boundaries.py:19`
**Issue:** The architecture guard prevents reintroducing a few exact old names such as `_SAFE_RISK_LABELS` and `_ROUTE_MANUAL_REVIEW_REASONS`, but a duplicate source set under a new name in the same migrated files would pass. That weakens the taxonomy-drift guard this phase is trying to establish.
**Fix:** Extend the AST guard to detect collection literals or assignments outside `src/agent/rag_context/risk_labels.py` that contain multiple canonical risk-label strings, regardless of variable name. Keep the explicit import-origin check as a second guard.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_metrics.py tests/agent/rag_context/test_risk_labels.py tests/architecture/test_rag_risk_label_boundaries.py -q`
  - Result: `18 passed, 1 warning`

---

_Reviewed: 2026-07-10T00:18:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
