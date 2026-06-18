---
phase: 20-rag-hybrid-retrieval
plan: 01
subsystem: rag
tags: [postgres, pgvector, full-text-search, pg-trgm, rrf, retrieval, eval]

requires:
  - phase: 16-long-term-case-memory
    provides: "Reviewed memory remains contextual only; Phase 20 preserves policy evidence and business-tool authority boundaries."
provides:
  - "Retrieval-only policy chunk search_text and generated PostgreSQL search_vector."
  - "Dense, sparse, and fuzzy policy retrieval channels fused with RRF."
  - "Internal hybrid retrieval trace for eval/debug without changing EvidenceRefV1."
affects: [knowledge, rag, ingestion, evaluation, policy-evidence]

tech-stack:
  added: [postgresql-full-text, pg_trgm]
  patterns:
    - "PolicyChunk.content remains citation text; search_text is retrieval-only."
    - "RRF controls ordering while normalized confidence controls evidence thresholds."

key-files:
  created:
    - src/rag/search_text.py
    - src/db/migrations/versions/014_rag_hybrid_retrieval.py
    - tests/rag/test_search_text.py
    - tests/knowledge/test_hybrid_schema.py
    - tests/knowledge/test_hybrid_retrieval.py
  modified:
    - src/db/models.py
    - src/rag/ingestion.py
    - src/repositories/policy_chunk_repo.py
    - src/knowledge/retrieval.py
    - src/api/schemas/search.py
    - scripts/eval_rag_hit_at_5.py
    - tests/test_ingestion.py
    - tests/test_rag_eval.py

key-decisions:
  - "Policy search_text is persisted separately from citation content and is generated during ingestion."
  - "PostgreSQL full-text and pg_trgm stay behind PolicyKnowledgeService rather than introducing a new backend abstraction."
  - "Hybrid trace fields are internal diagnostics only and are excluded from API serialization."

patterns-established:
  - "Hybrid retrieval channels share tenant, doc_type, risk_level, and effective_date filters before RRF fusion."
  - "Sparse scores are normalized before threshold evaluation; raw RRF score never becomes EvidenceRefV1.score."

requirements-completed:
  - RAGHYB-01
  - RAGHYB-02
  - RAGTOK-01
  - RAGTOK-02
  - RAGRET-01
  - RAGRET-02
  - RAGRET-03
  - RAGSCOPE-01
  - RAGSCOPE-02
  - RAGTRACE-01
  - RAGEVAL-01

duration: "1h 10m resumed execution"
completed: 2026-06-18
---

# Phase 20 Plan 01: PostgreSQL Hybrid Retrieval Summary

**PostgreSQL policy retrieval now combines pgvector dense search, full-text sparse search, and pg_trgm fuzzy search with RRF while preserving EvidenceRefV1 citation identity.**

## Performance

- **Duration:** 1h 10m resumed execution
- **Started:** 2026-06-18T08:50:00Z
- **Completed:** 2026-06-18T10:00:03Z
- **Tasks:** 6 completed
- **Files modified:** 13 implementation/test files plus planning artifacts

## Accomplishments

- Added deterministic Chinese/domain search text construction for policy chunks and queries.
- Added `PolicyChunk.search_text`, generated `search_vector`, pg_trgm/full-text indexes, and rollback-safe migration coverage.
- Persisted retrieval-only search text during ingestion while keeping `PolicyChunk.content` as the citation text.
- Added sparse and fuzzy repository channels with the same trusted tenant/effective/doc/risk filters as dense retrieval.
- Added RRF fusion across dense/sparse/fuzzy results while keeping evidence confidence normalized to 0-1.
- Added internal retrieval trace fields and eval diagnostics without extending `EvidenceRefV1`.

## Task Commits

1. **Task 20-01-01: Add deterministic policy search text tokenizer** - `e25a979` (feat)
2. **Task 20-01-02: Add hybrid retrieval schema and migration** - `e5f0aa1` (feat)
3. **Task 20-01-03: Persist retrieval-only search text during ingestion** - `98f511e` (feat)
4. **Task 20-01-04: Add sparse and fuzzy repository channels** - `daede74` (feat)
5. **Task 20-01-05: Fuse dense, sparse, and fuzzy candidates with RRF** - `daede74` (feat)
6. **Task 20-01-06: Update eval diagnostics and run retrieval regression suite** - `7b58217` (feat)

_Note: resumed worktree state already contained batched Task 04/05 test changes, so those two tasks share one implementation commit._

## Files Created/Modified

- `src/rag/search_text.py` - domain dictionary, normalization, tokenizer, and policy search text builder.
- `src/db/models.py` - `PolicyChunk.search_text` and generated `search_vector`.
- `src/db/migrations/versions/014_rag_hybrid_retrieval.py` - pg_trgm extension, search columns, GIN indexes, and rollback.
- `src/rag/ingestion.py` - writes retrieval-only search text while preserving raw chunk content.
- `src/repositories/policy_chunk_repo.py` - sparse full-text and fuzzy pg_trgm retrieval methods.
- `src/knowledge/retrieval.py` - RRF fusion, normalized sparse confidence, internal trace fields, and scoped channel calls.
- `src/api/schemas/search.py` - excluded diagnostic fields for eval-only hybrid traces.
- `scripts/eval_rag_hit_at_5.py` - failed-case diagnostics include hybrid trace fields when present.
- `tests/rag/test_search_text.py` - tokenizer and search text coverage.
- `tests/knowledge/test_hybrid_schema.py` - schema and migration source coverage.
- `tests/knowledge/test_hybrid_retrieval.py` - RRF, trace, confidence, and scope-filter coverage.
- `tests/test_ingestion.py` - raw content plus search text assertions.
- `tests/test_rag_eval.py` - unchanged scoring and optional diagnostic trace coverage.

## Decisions Made

- Kept `EvidenceRefV1` unchanged; hybrid trace stays on `PolicyRetrievalHit` and eval-only `EvidenceItem` fields.
- Kept the existing `PolicyKnowledgeService` boundary; no external `SearchBackend` abstraction was added in Phase 20.
- Used `simple` PostgreSQL full-text over application-tokenized Chinese search text rather than relying on PostgreSQL to segment Chinese text.
- Preserved the existing lexical overlap rerank only inside dense-channel preparation; completed hybrid ordering is RRF-based.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added excluded diagnostic fields to `EvidenceItem`**
- **Found during:** Task 20-01-06 (eval diagnostics)
- **Issue:** The eval script reuses `RetrievalResult` / `EvidenceItem`; without explicit optional fields, hybrid trace attributes would be dropped before diagnostics could read them.
- **Fix:** Added `selected_by`, channel ranks, and `rrf_score` to `EvidenceItem` with `exclude=True`, so API serialization remains unchanged.
- **Files modified:** `src/api/schemas/search.py`
- **Verification:** `tests/test_rag_eval.py`, focused retrieval suite, and full pytest passed.
- **Committed in:** `7b58217`

**2. [Rule 3 - Blocking] Tightened tokenizer ordering to match first-seen semantics**
- **Found during:** Task 20-01-01 follow-up review
- **Issue:** The first recovered tokenizer grouped tokens by category before de-duplication, which was deterministic but not strict first-seen order across token types.
- **Fix:** Tokenizer now records token occurrences by text position before deterministic de-duplication.
- **Files modified:** `src/rag/search_text.py`, `tests/rag/test_search_text.py`
- **Verification:** `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/test_ingestion.py tests/test_rag_eval.py -q`
- **Committed in:** `e25a979`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both fixes preserve the original contract boundaries and avoid scope expansion.

## Issues Encountered

- The resumed session had already produced uncommitted implementation files, so exact RED/GREEN/REFACTOR commit boundaries could not be reconstructed without risky patch surgery. The final commits are grouped by task area, and all planned tests passed.

## Verification

- `uv run pytest tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_eval.py -q` -> 82 passed, 1 warning.
- `uv run ruff check src/rag/search_text.py src/knowledge/retrieval.py src/repositories/policy_chunk_repo.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py` -> passed.
- `uv run pytest -q` -> 1002 passed, 6 warnings in 535.05s.

DB-backed `uv run python scripts/eval_rag_hit_at_5.py --threshold 0.8` was not run separately after the full pytest gate; pure eval scoring and diagnostics are covered by `tests/test_rag_eval.py`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 20 retrieval implementation is ready for GSD verification. Future RAG phases can build OCR/parser, `DocumentBlock`, `MaterialClaim`, semantic verifier, or external backend work on top of this hybrid retrieval base.

---
*Phase: 20-rag-hybrid-retrieval*
*Completed: 2026-06-18*
