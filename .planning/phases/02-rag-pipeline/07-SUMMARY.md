---
phase: 02-rag-pipeline
plan: "07"
subsystem: rag-retrieval
tags: [rag, retrieval, hybrid-rerank, evaluation, gap-closure]
status: complete
requires:
  - phase: 02-rag-pipeline
    provides: Plan 06 retrieval gap evidence and live DB-backed eval baseline
provides:
  - title and section enriched policy embeddings
  - deterministic hybrid reranking over deeper tenant-filtered vector candidates
  - diagnostic failed-case audit output without changing official scoring
  - live EVAL-02 closure evidence
affects: [phase-02-rag-pipeline, rag-search, rag-evaluation]
tech-stack:
  added: []
  patterns:
    - deterministic lexical reranking over pgvector candidates
    - support-domain fallback guard for weak out-of-domain matches
key-files:
  created:
    - tests/test_ingestion.py
    - .planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md
    - .planning/phases/02-rag-pipeline/07-SUMMARY.md
  modified:
    - src/rag/ingestion.py
    - src/rag/retriever.py
    - scripts/eval_rag_hit_at_5.py
    - tests/test_retriever.py
    - tests/test_rag_eval.py
key-decisions:
  - "EVAL-02 is closed by live exact expected_chunk_ids Hit@5 >= 80%, not by doc-only scoring or label changes."
  - "Evidence scores remain vector similarity scores; hybrid ranking only changes final ordering."
  - "Out-of-domain fallback is protected by a deterministic support-domain guard while preserving MIN_SIMILARITY_THRESHOLD = 0.55."
requirements-completed: [EVAL-02]
duration: 13min
completed: 2026-05-10
---

# Phase 2 Plan 07: Retrieval Quality Gap Closure Summary

**Live RAG Hit@5 improved from 58.3% to 83.3% using contextual embeddings and deterministic hybrid reranking**

## Status

COMPLETE - EVAL-02 is closed for Phase 2.

Plan 07 changed retrieval behavior without weakening the golden set, tenant filters, fallback threshold, or citation semantics. Stored `PolicyChunk.content` and chunk IDs remain unchanged; only embedding input is enriched with document title and section context.

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-10T23:28:38Z
- **Completed:** 2026-05-10T23:41:45Z
- **Tasks:** 5 completed
- **Files modified:** 8

## Accomplishments

- Created `07-RETRIEVAL-AUDIT.md` with Plan 06 baseline and Plan 07 before/after evidence.
- Added diagnostic `--diagnostic-top-k` output while keeping official eval default scoring at `top_k=5` and `DEFAULT_THRESHOLD = 0.80`.
- Enriched document embedding input with title and section while preserving raw stored chunk content.
- Added deterministic hybrid reranking over a deeper tenant-filtered candidate set.
- Preserved metadata filtering through `PolicyChunkRepository.search_similar()` and returned only chunk-ID citations from final evidence.
- Fixed a fallback regression caused by the query prefix surfacing weak policy evidence for unrelated questions.

## Live Eval Result

Baseline from Plan 06:

- Hit@5: 58.3%
- Fallback accuracy: 100.0%
- Non-fallback hits: 7/12

After Plan 07:

- Hit@5: 83.3%
- Fallback accuracy: 100.0%
- Non-fallback hits: 10/12
- Fallback hits: 2/2

Residual exact-label misses remain for two non-fallback cases, but they do not block EVAL-02. Diagnostic top-20 output shows the expected chunks at ranks 6-7 for the quality-evidence query and rank 10 for the merchant-dispute timing query.

## Task Commits

1. **Task 1 RED: eval diagnostic depth test** - `93ce12a` (test)
2. **Task 1 GREEN: retrieval audit diagnostics** - `578a3b3` (feat)
3. **Task 2 RED: ingestion enrichment test** - `11d2537` (test)
4. **Task 2 GREEN: enriched embedding input** - `b4dc6f3` (feat)
5. **Task 3 RED: hybrid rerank tests** - `83934d9` (test)
6. **Task 3 GREEN: hybrid reranking** - `1cc1d73` (feat)
7. **Task 4: fallback preservation and audit evidence** - `e8ff034` (fix)

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py -q` - PASS, 5 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --help` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/test_retriever.py -q` - PASS, 20 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_retriever.py -q` - PASS, 13 passed.
- `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7` - PASS, 15 documents and 90 chunks.
- `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7` - PASS, Hit@5 83.3%, fallback accuracy 100.0%.
- `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7 --diagnostic-top-k 20` - PASS after rerun with network access.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py tests/test_retriever.py tests/test_search_integration.py -q` - PASS with local DB access, 23 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - PASS, 49 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src scripts tests` - PASS.
- `gsd-sdk query frontmatter.validate .planning/phases/02-rag-pipeline/07-PLAN.md --schema plan` - PASS.
- `gsd-sdk query verify.plan-structure .planning/phases/02-rag-pipeline/07-PLAN.md` - PASS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved fallback accuracy after query prefixing**
- **Found during:** Task 4 live eval.
- **Issue:** Initial post-rerank live eval reached Hit@5 83.3%, but fallback accuracy regressed to 0.0% because the prefixed query produced weak policy matches for unrelated questions.
- **Fix:** Added deterministic support-domain anchor filtering after tenant-scoped retrieval so out-of-domain queries return `no_evidence` while support-domain queries continue through hybrid reranking.
- **Files modified:** `src/rag/retriever.py`, `tests/test_retriever.py`, `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md`.
- **Commit:** `e8ff034`

**2. [Rule 3 - Blocking] Reran local DB and network-backed checks with required access**
- **Found during:** Task 5 focused integration tests and Task 4 diagnostic eval.
- **Issue:** Sandbox blocked localhost PostgreSQL access for `tests/test_search_integration.py`; one diagnostic eval attempt hit a transient embedding-provider connection error.
- **Fix:** Reran the focused integration suite with local DB access and reran the diagnostic eval with network access. Both passed.
- **Files modified:** None.
- **Commit:** N/A

## Known Stubs

None found.

## Threat Flags

None. The plan touched embedding input, retrieval ranking, CLI diagnostics, and docs; no new network endpoint, auth path, file access boundary, or schema change was introduced.

## Residual Risk

The two remaining exact-label misses are retained in `07-RETRIEVAL-AUDIT.md`. They are semantically close retrieval cases and do not prevent EVAL-02 closure, but they are useful future calibration/ranking evidence if the golden set is expanded in Phase 6.

## Self-Check: PASSED

- Created files exist: `tests/test_ingestion.py`, `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md`, `.planning/phases/02-rag-pipeline/07-SUMMARY.md`.
- Modified files exist: `src/rag/ingestion.py`, `src/rag/retriever.py`, `scripts/eval_rag_hit_at_5.py`, `tests/test_retriever.py`, `tests/test_rag_eval.py`.
- Task commits exist: `93ce12a`, `578a3b3`, `11d2537`, `b4dc6f3`, `83934d9`, `1cc1d73`, `e8ff034`.
- Live eval passed without changing `eval/golden_rag_queries.jsonl`.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-10*
