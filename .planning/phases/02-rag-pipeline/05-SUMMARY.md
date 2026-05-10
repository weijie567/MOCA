---
phase: 02-rag-pipeline
plan: "05"
subsystem: rag-evaluation
tags: [rag, evaluation, hit-at-5, pgvector, fastapi, pytest]
requires:
  - phase: 02-rag-pipeline
    provides: policy ingestion, retrieval, and search endpoint from Plans 03-04
provides:
  - Golden RAG query set with doc_key-based expected chunk IDs
  - Hit@5 evaluation script with real DB/session/retriever wiring
  - Search endpoint integration tests with deterministic seeded vectors
  - DashScope embedding environment variable documentation
affects: [phase-02-rag-pipeline, phase-06-evaluation, rag-search]
tech-stack:
  added: []
  patterns:
    - JSONL golden set for retrieval evaluation
    - Endpoint integration tests with seeded pgvector embeddings and mocked embedding API
key-files:
  created:
    - eval/golden_rag_queries.jsonl
    - scripts/eval_rag_hit_at_5.py
    - tests/test_search_integration.py
  modified:
    - .env.example
key-decisions:
  - "Golden expected_chunk_ids were calibrated against the current zero-based heading chunker output instead of leaving placeholder IDs."
  - "The eval script uses SessionLocal and the production Retriever/PolicyChunkRepository path so failures reflect real retrieval wiring."
patterns-established:
  - "RAG eval scripts should use project DB session factories and report expected-vs-got chunk IDs for calibration."
  - "Search integration tests seed explicit 1024-dimensional vectors and patch only the external embedding API call."
requirements-completed: [EVAL-01, EVAL-02]
duration: 7min
completed: 2026-05-10
---

# Phase 2 Plan 05: Golden Set + Eval Script + Integration Test Summary

**RAG evaluation baseline with calibrated golden queries, a real Hit@5 script, and deterministic search endpoint coverage**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-10T14:04:27Z
- **Completed:** 2026-05-10T14:11:37Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Added a 14-query JSONL golden set covering refund rules, SOP, FAQ, boundary, and no-evidence fallback cases.
- Added `scripts/eval_rag_hit_at_5.py` with real tenant resolution, DB session setup, Retriever wiring, score reporting, and threshold-based exit codes.
- Added authenticated `/api/v1/search/` integration tests that seed deterministic pgvector rows and mock DashScope embeddings.
- Documented DashScope embedding environment variables in `.env.example`.

## Task Commits

| Task | Name | Commit | Files |
| --- | --- | --- | --- |
| 05.1 | Create golden set JSONL file | `ea01712` | `eval/golden_rag_queries.jsonl` |
| 05.2 | Create Hit@5 evaluation script | `9ee0e35` | `scripts/eval_rag_hit_at_5.py` |
| 05.3 | Create search integration tests | `90009b3` | `tests/test_search_integration.py` |
| 05.4 | Update env example | `8bcf526` | `.env.example` |

## Files Created/Modified

- `eval/golden_rag_queries.jsonl` - Golden retrieval cases with doc IDs, expected chunk IDs, categories, difficulty, and fallback flags.
- `scripts/eval_rag_hit_at_5.py` - CLI evaluation script for Hit@5 and fallback accuracy against ingested policy chunks.
- `tests/test_search_integration.py` - FastAPI search route tests using deterministic vectors and mocked embedding calls.
- `.env.example` - DashScope API key and embedding model configuration documentation.

## Decisions Made

- Calibrated `expected_chunk_ids` against the actual `chunk_markdown` output. The current chunker includes a top-level `intro` chunk and then zero-based heading chunks, so several plan example IDs would have pointed at the wrong policy sections.
- Used `SessionLocal` from `src.db.session` in the eval script because this project exposes that async sessionmaker rather than an `async_session_factory` symbol.
- Patched `src.api.routers.search.EmbeddingService` in integration tests so the endpoint path, auth, repository filtering, and pgvector search run normally without external API calls.

## Deviations from Plan

### Plan Adjustments

**1. Calibrated placeholder expected chunk IDs**
- **Found during:** Task 05.1 (Create golden set JSONL file)
- **Issue:** The plan examples were marked as placeholder IDs; the actual chunker produces zero-based IDs and includes an `intro` chunk for each document.
- **Fix:** Generated the current chunk mapping from `src.rag.chunker.chunk_markdown` and used matching section IDs in the golden set.
- **Files modified:** `eval/golden_rag_queries.jsonl`
- **Verification:** JSONL parse passed; exactly 14 rows and 2 fallback cases; categories include refund_rule, sop, faq, boundary, fallback.
- **Committed in:** `ea01712`

**Total deviations:** 1 plan adjustment, expected by the plan note.
**Impact on plan:** Improves eval correctness without expanding scope.

## Issues Encountered

- The system `python` executable is broken on this machine due to a missing Homebrew Python framework. Verification used `UV_CACHE_DIR=/tmp/uv-cache uv run python ...`, which passed.
- The sandbox initially blocked localhost PostgreSQL access for pytest. Re-running the same pytest command with approved local DB access passed.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import json; [json.loads(l) for l in open('eval/golden_rag_queries.jsonl')]"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --help` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_search_integration.py -q` - passed, 4 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 35 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check scripts/eval_rag_hit_at_5.py tests/test_search_integration.py` - passed.
- `.env.example` contains `DASHSCOPE_API_KEY`.

## Known Stubs

None. The empty list and dict literals found during stub scan are runtime accumulators or assertions, not UI-facing placeholder data.

## Threat Flags

None. This plan added an offline eval CLI and tests; no new network endpoint, auth path, file access boundary, or schema trust boundary was introduced.

## User Setup Required

For live RAG evaluation beyond `--help`, run PostgreSQL with ingested policy documents and set `DASHSCOPE_API_KEY` in the environment.

## Next Phase Readiness

Phase 2 now has policy ingestion, retrieval, search endpoint coverage, and a baseline evaluation harness. Future eval expansion can add more reviewed golden queries and run `scripts/eval_rag_hit_at_5.py` after ingestion calibration.

## Self-Check: PASSED

- Verified created/modified files exist: `eval/golden_rag_queries.jsonl`, `scripts/eval_rag_hit_at_5.py`, `tests/test_search_integration.py`, `.env.example`, `.planning/phases/02-rag-pipeline/05-SUMMARY.md`.
- Verified task commits exist: `ea01712`, `9ee0e35`, `90009b3`, `8bcf526`.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-10*
