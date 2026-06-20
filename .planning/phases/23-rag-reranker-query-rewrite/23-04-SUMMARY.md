---
phase: 23-rag-reranker-query-rewrite
plan: "04"
subsystem: knowledge
tags: [rag, reranker, diagnostics, evidence-boundary]
requires:
  - phase: 23-03
    provides: PolicyRetrievalRun and merged retrieval candidates before evidence refs
provides:
  - Project-owned reranker DTOs and deterministic local reranker
  - Retrieval integration before PolicyRetrievalHit and EvidenceRefV1 construction
  - Disabled-by-default provider adapter protocol with safe fallback reasons
  - Strict rerank diagnostic record shape
affects: [phase-23, retrieval-quality, reranking]
tech-stack:
  added: []
  patterns:
    - Rerank final_score is diagnostic-only and never replaces evidence confidence
    - Provider adapter output is optional, validated, bounded, and fallback-safe
key-files:
  created:
    - src/knowledge/rerank.py
  modified:
    - src/knowledge/config.py
    - src/knowledge/retrieval.py
    - src/knowledge/diagnostics.py
    - tests/knowledge/test_reranker.py
    - tests/knowledge/test_retrieval_budgets.py
key-decisions:
  - "RerankCandidate uses candidate_id/text_snippet/baseline_score/baseline_rank per the plan interface."
  - "Default local reranking is credential-free and deterministic."
  - "Provider integration remains a protocol only; no live provider dependency or credentials are introduced."
patterns-established:
  - "Reranked order changes hit/evidence rank while hit.score, evidence score, best_score, and status thresholds remain baseline confidence."
  - "Provider disabled, timeout, error, malformed output, and budget overflow all fall back to local ranking with safe fallback_reason."
requirements-completed:
  - RRK-01
  - RRK-02
  - RRK-03
  - RRK-04
  - RRK-05
  - RRK-06
  - EVAL-04
  - EVAL-05
  - BND-02
  - BND-03
duration: 7min
completed: 2026-06-20
---

# Phase 23 Plan 04: Reranker Contract Summary

**A strict project-owned reranker now runs before evidence construction, improves candidate order locally, and keeps all evidence confidence and authority boundaries unchanged.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-20T08:06:18+08:00
- **Completed:** 2026-06-20T08:13:16+08:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `RerankCandidate`, `RerankConfig`, `ProviderRerankScore`, `RerankScoreComponent`, `RerankedCandidate`, `RerankOutput`, `RerankerProviderAdapter`, and `DefaultLocalReranker`.
- Added deterministic local scoring from baseline confidence, lexical overlap, title/section overlap, channel coverage, and bounded RRF contribution.
- Integrated reranking in retrieval after candidate merge/filtering and before `PolicyRetrievalHit` / `EvidenceRefV1` construction.
- Preserved `PolicyRetrievalHit.score`, `EvidenceRefV1.score`, `best_score`, and status thresholds as baseline normalized confidence.
- Added provider gates with disabled default, timeout/error/malformed/budget fallbacks, and no live provider imports.
- Added strict `RerankDiagnosticRecord` for safe fallback and score-component diagnostics.

## Task Commits

1. **Tasks 1-3: Reranker DTOs, retrieval integration, and provider gates** - `1bf4d6f` (feat)

## Files Created/Modified

- `src/knowledge/rerank.py` - Reranker DTOs, deterministic local reranker, provider protocol, validation, fallback output, and safe provider payload handling.
- `src/knowledge/config.py` - Rerank/provider/text/latency/diagnostics budget constants.
- `src/knowledge/retrieval.py` - Rerank candidate conversion and reranked ordering before hit/evidence construction.
- `src/knowledge/diagnostics.py` - Strict rerank diagnostic record.
- `tests/knowledge/test_reranker.py` - Identity, determinism, score-component, provider fallback, input redaction, and retrieval integration coverage.
- `tests/knowledge/test_retrieval_budgets.py` - Versioned timeout/provider budget coverage.

## Verification

- `uv run pytest tests/knowledge/test_reranker.py tests/knowledge/test_retrieval_budgets.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q --tb=short` passed (`17 passed`, one existing LangChain deprecation warning).
- `uv run ruff check src/knowledge/rerank.py src/knowledge/retrieval.py src/knowledge/diagnostics.py src/knowledge/config.py tests/knowledge/test_reranker.py tests/knowledge/test_retrieval_budgets.py` passed.
- `gsd-sdk query verify.key-links .planning/phases/23-rag-reranker-query-rewrite/23-04-PLAN.md` passed.
- `rg -n "openai|anthropic|cohere|voyage|dashscope|requests|httpx" src/knowledge/rerank.py` found no live provider dependency imports.

## Decisions Made

- Reranker output is sequence-like for compatibility, but the normative return is `RerankOutput`.
- Provider budgets constrain the optional provider path; fallback local ranking keeps the candidate set rather than truncating evidence candidates.
- Provider payload text is sanitized and bounded separately from canonical chunk content, so text hashes and citations remain source-owned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Test contract drift] Updated RED tests from legacy rerank fields to final plan DTO fields**
- **Found during:** Task 1 implementation
- **Issue:** Existing red tests used `text`, `score`, and `rank` fields, while 23-04 plan required `candidate_id`, `text_snippet`, `baseline_score`, and `baseline_rank`.
- **Fix:** Updated tests to assert the final plan interface and added a retrieval-level test for rerank-before-evidence behavior.
- **Files modified:** `tests/knowledge/test_reranker.py`, `tests/knowledge/test_retrieval_budgets.py`
- **Verification:** Task-specific and plan-level tests passed.
- **Committed in:** `1bf4d6f`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** Aligns tests with the normative 23-04 interface; no evidence identity or authority expansion.

## Issues Encountered

- None blocking.

## User Setup Required

None. Provider use remains disabled by default and no credentials are required.

## Next Phase Readiness

Ready for `23-05`: diagnostics and ablation eval work can use safe rerank score components, selected candidate IDs, fallback reasons, and existing latency budget constants.

## Self-Check: PASSED

- Deterministic local reranker preserves candidate identity and requires no network or credentials.
- Rerank occurs before `EvidenceRefV1.build()`.
- Provider adapter path is disabled by default and safely falls back across disabled, timeout, error, malformed, and budget cases.
- Reranker diagnostics are separate from evidence identity and bounded to safe fields.

---
*Phase: 23-rag-reranker-query-rewrite*
*Completed: 2026-06-20*
