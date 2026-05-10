---
phase: 02-rag-pipeline
plan: "06"
subsystem: rag-evaluation
tags: [rag, evaluation, hit-at-5, gap-closure, diagnostics]
status: gaps_found
requires:
  - phase: 02-rag-pipeline
    provides: live ingestion, retriever, search endpoint, and baseline RAG eval from Plans 03-05
provides:
  - deterministic eval scoring helpers
  - ranked failed-case live diagnostics
  - evidence that golden-set calibration alone cannot honestly close EVAL-02
affects: [phase-02-rag-pipeline, phase-06-evaluation, rag-search]
tech-stack:
  added: []
  patterns:
    - pure eval scoring helpers for DashScope-free tests
    - expected_doc_ids diagnostics separate from expected_chunk_ids scoring
key-files:
  created:
    - tests/test_rag_eval.py
    - .planning/phases/02-rag-pipeline/06-SUMMARY.md
  modified:
    - scripts/eval_rag_hit_at_5.py
key-decisions:
  - "Hit@5 scoring remains exact expected_chunk_ids in top-5; expected_doc_ids are diagnostics only."
  - "Golden labels were not changed because live top-5 answer-bearing candidates were insufficient to reach 80%."
requirements-completed: []
duration: 4min
completed: 2026-05-11
---

# Phase 2 Plan 06: RAG Hit@5 Gap Closure Summary

**Eval diagnostics now prove the remaining EVAL-02 gap is retrieval quality, not a safe golden-set calibration issue**

## Status

GAPS FOUND - Plan 06 stopped during Task 2 before modifying `eval/golden_rag_queries.jsonl`.

The live eval still reports `Hit@5: 58.3%` and `Fallback accuracy: 100.0%`. With 12 non-fallback cases, the eval needs at least 10 hits to satisfy the 80% threshold. Current live retrieval has 7 hits. The diagnostics found only one semantically justified calibration candidate under the plan's rules, so calibration could raise the score only to 8/12, not 10/12.

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-10T22:52:57Z
- **Completed:** 2026-05-10T22:55:46Z
- **Tasks:** 1 completed, stopped during Task 2
- **Files modified:** 3

## Accomplishments

- Added `_ranked_evidence()` and `_score_case()` to expose deterministic eval scoring without weakening the official pass criteria.
- Added DashScope-free tests proving doc-key-only matches are diagnostics and do not count as Hit@5.
- Re-ran live diagnostics and confirmed golden-set calibration cannot honestly close the gap.

## Task Commits

1. **Task 1 RED: eval scoring helper tests** - `59e6dd5` (test)
2. **Task 1 GREEN: eval scoring diagnostics** - `0b57c5e` (feat)

## Files Created/Modified

- `tests/test_rag_eval.py` - Pure scoring tests using `RetrievalResult` and `EvidenceItem`.
- `scripts/eval_rag_hit_at_5.py` - Scoring helpers and ranked failed-case diagnostics.
- `.planning/phases/02-rag-pipeline/06-SUMMARY.md` - Gap evidence and stop reason.

## Gap Evidence

Live command:

`set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`

Result: failed, `Hit@5: 58.3%`, `Fallback accuracy: 100.0%`.

Calibration candidate review:

| Failed query category | Plan-eligible answer-bearing top-5 expected-doc chunk | Outcome |
| --- | --- | --- |
| `refund_rule` 七天无理由拆封 | None sufficient | `refund_policy_002` is related to exceptions but does not directly provide the positive handling rule for "不影响二次销售". |
| `refund_rule` 超过15天 | None | Only `refund_time_limits_000` intro appears from the expected doc; it is not answer-bearing. |
| `sop` 补偿券审批信息 | None | Expected answer is `compensation_approval_sop_002` 提交材料; top-5 expected-doc chunks discuss approval levels or post-approval writeback. |
| `faq` 商家争议时效 | None | No `merchant_dispute_faq` chunk appears in top-5. |
| `boundary` 跨境质量问题运费 | `cross_border_refund_002` | Rank 1, score 0.7611, section `时效与税费`, snippet states quality issues or customs/material errors are merchant responsibility. |

Even accepting the one valid candidate would produce 8/12 non-fallback hits, below the required 10/12.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py -q` - PASS, 4 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --help` - PASS.
- Chunk-map validation command - PASS, 90 generated chunks; no existing golden expected chunks are missing or mapped to the wrong doc.
- Live eval command - FAIL as expected for this gap result: `Hit@5: 58.3%`, `Fallback accuracy: 100.0%`.

## Deviations from Plan

None - the plan explicitly required stopping before modifying the golden set if calibration could not honestly reach Hit@5 >= 80%.

## Issues Encountered

The calibration path is blocked by insufficient answer-bearing top-5 evidence in the current retrieval results. This is a retrieval improvement gap, not a scoring or JSONL validity issue.

## User Setup Required

None for the diagnostic work. The live eval used the local `.env` `DASHSCOPE_API_KEY` without printing the key.

## Next Phase Readiness

Do not mark EVAL-02 complete yet. Create a follow-up retrieval-improvement plan that can change ranking behavior or retrieval architecture within an explicit design decision, such as query rewriting, hybrid lexical/vector search, corpus phrasing improvements, reranking, or threshold/ranking calibration with fresh deterministic tests.

## Self-Check: PASSED

- Created files exist: `tests/test_rag_eval.py`, `.planning/phases/02-rag-pipeline/06-SUMMARY.md`.
- Modified file exists: `scripts/eval_rag_hit_at_5.py`.
- Task commits exist: `59e6dd5`, `0b57c5e`.
- Golden set was not modified.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-11*
