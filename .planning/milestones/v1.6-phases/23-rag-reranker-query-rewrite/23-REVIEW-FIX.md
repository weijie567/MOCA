---
phase: 23-rag-reranker-query-rewrite
fixed_at: 2026-06-20T01:51:12Z
review_path: .planning/phases/23-rag-reranker-query-rewrite/23-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 23: Code Review Fix Report

**Fixed at:** 2026-06-20T01:51:12Z
**Source review:** `.planning/phases/23-rag-reranker-query-rewrite/23-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-05: Provider Rerank Scores Accept Boolean And NaN Values

**Files modified:** `src/knowledge/rerank.py`, `tests/knowledge/test_reranker.py`
**Commit:** 4c70bd6
**Applied fix:** Provider score normalization now rejects boolean values and non-finite floats before accepting provider rerank output.
**Tests:** `tests/knowledge/test_reranker.py::test_provider_score_bool_and_nan_are_malformed_output`

### WR-06: Malformed Effective Time Disables Evidence Freshness Checks

**Files modified:** `src/knowledge/service.py`, `tests/knowledge/test_phase22_evidence_validation.py`
**Commit:** 1dba424
**Applied fix:** Non-empty malformed `effective_at` values now fail closed with `freshness_invalid` and `effective_date_invalid` reason codes.
**Tests:** `tests/knowledge/test_phase22_evidence_validation.py::test_policy_knowledge_service_verified_details_rejects_malformed_effective_at`

## Skipped Issues

None - all in-scope findings were fixed.

## Verification

`PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider tests/knowledge/test_reranker.py -k 'provider_score_bool_and_nan_are_malformed_output or provider_adapter_disabled_timeout_error_malformed_and_budget_fallbacks'`

Result: 4 passed, 4 deselected, 1 warning.

`PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider tests/knowledge/test_phase22_evidence_validation.py -k 'malformed_effective_at or current_row_version_mismatch'`

Result: 2 passed, 4 deselected, 1 warning.

---

_Fixed: 2026-06-20T01:51:12Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
