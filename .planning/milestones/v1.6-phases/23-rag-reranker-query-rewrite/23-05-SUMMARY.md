---
phase: 23-rag-reranker-query-rewrite
plan: "05"
subsystem: knowledge
tags: [rag, diagnostics, ablation, evaluation, latency]
requires:
  - phase: 23-04
    provides: Reranker score components, fallback reasons, and budget constants
provides:
  - Strict internal retrieval diagnostics and ranking explanations
  - Safe diagnostic exclusion handling for Phase 22 reason codes
  - Deterministic no-live-provider ablation script and Phase 23 golden categories
  - Blocking ablation metrics, fallback reporting, and latency percentiles
affects: [phase-23, evaluation, diagnostics]
tech-stack:
  added: []
  patterns:
    - Evaluation reports carry safe IDs, bounded snippets, config versions, metrics, and fallback reasons only
    - Diagnostics remain internal and do not extend EvidenceRefV1 or public evidence items
key-files:
  created:
    - scripts/eval_rag_ablation.py
  modified:
    - src/knowledge/diagnostics.py
    - src/knowledge/retrieval.py
    - src/knowledge/service.py
    - evaluation/golden/rag_cases.jsonl
    - tests/knowledge/test_retrieval_diagnostics.py
    - tests/test_rag_ablation_eval.py
key-decisions:
  - "PolicyRetrievalRun may carry internal RetrievalDiagnostics; KnowledgeSearchResult still exposes only safe query_rewrite summary."
  - "Ablation dry-run uses deterministic fake variant results and requires no live provider or network."
  - "Generated evaluation/reports/rag_ablation.json is not committed; it is produced by the script."
patterns-established:
  - "Diagnostics filter excluded evidence IDs using Phase 22 reason-code patterns before selected_candidate_ids/ranking_explanations are exposed."
  - "Ablation reports include required variants, metrics, thresholds, failed cases, fallback reasons, and config versions."
requirements-completed:
  - EXP-01
  - EXP-02
  - EXP-03
  - EXP-04
  - EVAL-01
  - EVAL-02
  - EVAL-03
  - EVAL-04
  - EVAL-05
  - QRW-05
  - RRK-05
  - BND-01
  - BND-02
  - BND-03
duration: 7min
completed: 2026-06-20
---

# Phase 23 Plan 05: Diagnostics and Ablation Eval Summary

**Safe retrieval diagnostics and deterministic ablation reporting now cover Phase 23 variants, golden categories, blocking metrics, fallback reasons, and latency budgets without live provider dependencies.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-20T08:13:16+08:00
- **Completed:** 2026-06-20T08:20:11+08:00
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Expanded diagnostics DTOs with `RankingExplanation`, `RewriteDiagnosticRecord`, `RerankDiagnosticRecord`, `DiagnosticEvidenceExclusion`, and `RetrievalDiagnostics`.
- Connected internal diagnostics to `PolicyRetrievalRun` while keeping ordinary `KnowledgeSearchResult` unchanged except safe `query_rewrite`.
- Added EXP-03 diagnostic exclusion coverage for `scope_invalid`, `freshness_invalid`, `effective_date_invalid`, `latest_version_invalid`, and `text_hash_mismatch`.
- Created `scripts/eval_rag_ablation.py` with required variants, report helpers, dry-run execution, safe evidence snippets, fallback counters, and config versions.
- Appended eight Phase 23 golden categories to `evaluation/golden/rag_cases.jsonl`.
- Added `hit_at_k`, `mrr`, citation support compatibility, no-evidence precision, unsafe retrieval rate, fallback rate, and latency p50/p95 metrics.

## Task Commits

1. **Tasks 1-3: Diagnostics, golden cases, ablation script, and metrics** - `d1986e7` (feat)

## Files Created/Modified

- `src/knowledge/diagnostics.py` - Strict internal diagnostics DTOs and safe diagnostic builder.
- `src/knowledge/retrieval.py` - `PolicyRetrievalRun.diagnostics` internal diagnostics construction.
- `src/knowledge/service.py` - Internal diagnostic type link while preserving public search output.
- `scripts/eval_rag_ablation.py` - Deterministic no-live-provider ablation runner and report helpers.
- `evaluation/golden/rag_cases.jsonl` - Phase 23 golden categories appended.
- `tests/knowledge/test_retrieval_diagnostics.py` - Safe diagnostics, redaction, and reason-code exclusion coverage.
- `tests/test_rag_ablation_eval.py` - Required variants, categories, metrics, fallback, and version report coverage.

## Verification

- `uv run pytest tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_retrieval_budgets.py tests/test_rag_ablation_eval.py -q --tb=short` passed (`9 passed`, one existing LangChain deprecation warning).
- `uv run python scripts/eval_rag_ablation.py --golden-set evaluation/golden/rag_cases.jsonl --output evaluation/reports/rag_ablation.json --dry-run` passed and generated a report; generated report was removed from git working tree.
- `uv run ruff check src/knowledge/diagnostics.py src/knowledge/service.py src/knowledge/retrieval.py src/knowledge/config.py scripts/eval_rag_ablation.py tests/knowledge/test_retrieval_diagnostics.py tests/knowledge/test_retrieval_budgets.py tests/test_rag_ablation_eval.py` passed.
- `gsd-sdk query verify.key-links .planning/phases/23-rag-reranker-query-rewrite/23-05-PLAN.md` passed.

## Decisions Made

- Kept ablation script default deterministic and local; real database/provider evaluation is not required for Phase 23 acceptance.
- Kept selected candidate IDs and ranking explanations derived only from filtered hits or explicitly supplied safe diagnostics.
- Kept report text to bounded snippets and did not commit generated report output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Test contract drift] Updated Phase 23 golden category test labels**
- **Found during:** Task 2 implementation
- **Issue:** Existing red test category labels used older names (`ambiguous_merchant_support`, `underspecified_policy_question`) while the 23-05 plan defined stable labels `ambiguous_support_wording` and `underspecified_question`, plus required `reranker_win`.
- **Fix:** Updated tests to match the plan interface and appended matching golden cases.
- **Files modified:** `tests/test_rag_ablation_eval.py`, `evaluation/golden/rag_cases.jsonl`
- **Verification:** Ablation tests and grep acceptance passed.
- **Committed in:** `d1986e7`

---

**Total deviations:** 1 auto-fixed
**Impact on plan:** Aligns tests and golden data with the normative 23-05 labels.

## Issues Encountered

- None blocking.

## User Setup Required

None. Dry-run ablation requires no provider credentials or external services.

## Next Phase Readiness

Ready for `23-06`: final boundary regression can verify Phase 20 filters, Phase 21 provenance/evidence identity, Phase 22 verifier/action boundaries, deferrals, and final acceptance gates.

## Self-Check: PASSED

- Diagnostics are internal/eval-only and safe.
- Phase 23 golden cases cover all required categories.
- Ablation variants and metrics match the plan labels.
- Latency/budget/fallback reporting is explicit and tested.
- Default eval path uses no live provider credentials.

---
*Phase: 23-rag-reranker-query-rewrite*
*Completed: 2026-06-20*
