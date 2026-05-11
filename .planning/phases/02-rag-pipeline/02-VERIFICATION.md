---
phase: 02-rag-pipeline
verified: 2026-05-11T03:06:54Z
status: passed
score: "9/9 must-haves verified"
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: "35/36 must-haves verified; live Hit@5 failed"
  gaps_closed:
    - "EVAL-02 live DB-backed RAG Hit@5 now passes: Plan 07 recorded Hit@5 83.3% and fallback accuracy 100.0% after re-ingestion."
    - "Code review WR-01 was fixed in commit f1752c2; no-anchor valid support queries can return strong evidence while weak out-of-domain matches still fall back."
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "EVAL-01 final golden set size of 25-40 cases"
    addressed_in: "Phase 6"
    evidence: "Phase 6 success criteria expands the golden set to 25-40 cases; Phase 2 establishes the 14-case RAG baseline and closes EVAL-02."
---

# Phase 2: RAG Pipeline Verification Report

**Phase Goal:** Knowledge documents are chunked, embedded, and retrievable via pgvector; search endpoint returns relevant rule chunks with metadata filtering, confidence scoring, and citation validation.
**Verified:** 2026-05-11T03:06:54Z
**Status:** passed
**Re-verification:** Yes - after Plan 07 gap closure and code-review fix

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | CLI ingestion processes 15-30 Chinese policy documents, structurally chunks them, embeds them, and stores pgvector rows with HNSW support. | VERIFIED | `scripts/ingest_policies.py --dry-run` processed all 15 manifest docs successfully; `src/rag/ingestion.py:50-99` embeds title/section-enriched texts before storing raw chunk content; `002_rag_pipeline.py:32-44` sets `vector(1024)` and HNSW cosine index. Plan 07 live audit records 15/15 re-ingested docs and 90 regenerated chunks. |
| 2 | Chunk metadata and retrieval filters include tenant_id, doc identity, chunk_id, title, section, text, doc_type, risk_level, and effective_date. | VERIFIED | `PolicyDocument` and `PolicyChunk` define the metadata in `src/db/models.py:148-178`; `PolicyChunkRepository.search_similar()` joins `PolicyDocument`, enforces tenant match on both sides, eager-loads the document, and applies doc_type/risk_level filters at `src/repositories/policy_chunk_repo.py:43-66`. |
| 3 | Search endpoint returns top-5 relevant chunks and the golden set has a measurable DB-backed Hit@5 score. | VERIFIED | `/api/v1/search/` is registered in `src/api/main.py:91`, protected by `knowledge:read` in `src/api/routers/search.py:19-42`, and delegates to `Retriever.search()`. `eval/golden_rag_queries.jsonl` has 14 cases, 12 non-fallback and 2 fallback. Plan 07 live audit records exact chunk-ID Hit@5 83.3% and fallback accuracy 100.0%. |
| 4 | Citation validator rejects cited chunk IDs not present in retrieval evidence. | VERIFIED | `validate_citations()` checks cited chunk IDs against `retrieval_result.evidence` in `src/rag/citation_validator.py:6-31`; `tests/test_retriever.py:125-148` covers valid, invalid, and empty citation sets. |
| 5 | No-evidence fallback is returned when confidence is insufficient or the query is out of support domain. | VERIFIED | `Retriever` keeps `MIN_SIMILARITY_THRESHOLD = 0.55` and `STRONG_EVIDENCE_THRESHOLD = 0.70`, reranks only threshold-qualified candidates, and returns the fallback message when evidence is absent at `src/rag/retriever.py:11-18` and `src/rag/retriever.py:114-154`. Regression tests cover low similarity and out-of-domain fallback. |
| 6 | EVAL-02 remains exact expected_chunk_ids Hit@5, not doc-only scoring. | VERIFIED | `_score_case()` only passes non-fallback cases when expected chunks intersect returned top-5 chunks at `scripts/eval_rag_hit_at_5.py:91-115`; `tests/test_rag_eval.py:39-67` proves doc-id-only hits are diagnostics. |
| 7 | Plan 07 retrieval fix changes final ranking behavior while preserving tenant/filter/fallback/citation invariants. | VERIFIED | `Retriever.search()` requests deeper tenant-filtered candidates, applies deterministic hybrid reranking, and returns only final top_k evidence at `src/rag/retriever.py:67-127`; `tests/test_retriever.py:177-252` covers query prefixing, rerank promotion, low-vector exclusion, out-of-domain fallback, and no-anchor strong evidence. |
| 8 | Code review WR-01 is fixed. | VERIFIED | Commit `f1752c2` modifies `src/rag/retriever.py` and `tests/test_retriever.py`; `02-REVIEW-FIX.md` records the fix and live eval pass. Current code applies the support-domain guard only as a stricter score/overlap gate for no-anchor queries. |
| 9 | Requirement IDs referenced by Phase 2 plans are accounted for. | VERIFIED | Plan frontmatter references `EVAL-01`, `EVAL-02`, `INFR-06`, `RAG-01`, `RAG-02`, `RAG-03`, `RAG-04`, `RAG-06`, and `RAG-07`; each appears in `.planning/REQUIREMENTS.md` with Phase 2 traceability. |

**Score:** 9/9 must-haves verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | EVAL-01 final 25-40 case golden set | Phase 6 | `ROADMAP.md` Phase 6 success criterion expands the golden set to 25-40 cases; `.planning/REQUIREMENTS.md` explicitly notes the Phase 2 14-case baseline is complete and final expansion is deferred. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/db/models.py` / `002_rag_pipeline.py` | RAG document/chunk schema, doc_key uniqueness, chunk_id index, vector(1024), HNSW | VERIFIED | `gsd-sdk verify.artifacts` passed for Plan 01; schema drift check returned valid with no issues. |
| `src/rag/chunker.py` / `src/rag/embedder.py` | Heading chunking and DashScope embedding wrapper | VERIFIED | Plan 02 artifacts pass; chunker uses stable doc_key chunk IDs and Chinese character limits; embedder lazily initializes and clamps batch size to 10. |
| `src/rag/ingestion.py` / `scripts/ingest_policies.py` / policy corpus | Manifest-backed ingestion CLI | VERIFIED | Plan 03 artifacts pass; dry-run processed 15/15 docs; live Plan 07 audit records 90 embedded chunks after re-ingestion. |
| `src/rag/retriever.py` / `src/rag/citation_validator.py` / `src/api/routers/search.py` | Retrieval, fallback, citation validation, protected endpoint | VERIFIED | Plan 04 artifacts pass; focused tests cover retriever/citation/endpoint behavior. |
| `eval/golden_rag_queries.jsonl` / `scripts/eval_rag_hit_at_5.py` | Golden set and DB-backed Hit@5 eval | VERIFIED | Plan 05 artifacts pass; 14 rows with distribution `refund_rule=5`, `sop=3`, `faq=2`, `boundary=2`, `fallback=2`; eval exits non-zero below threshold. |
| `.planning/phases/02-rag-pipeline/06-CALIBRATION-AUDIT.md` | Audit only if golden labels were changed in Plan 06 | NOT REQUIRED | Plan 06 concluded honest golden-set calibration could not close the gap and did not change labels; Plan 07 closed EVAL-02 through retrieval changes, so this superseded artifact is not a phase gap. |
| `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md` | Before/after retrieval audit with live eval result | VERIFIED | Plan 07 artifacts and key links pass; audit records baseline 58.3% and post-fix Hit@5 83.3%, fallback accuracy 100.0%. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/ingest_policies.py` | `src/rag/ingestion.py` | `IngestionService` | VERIFIED | CLI constructs `IngestionService` for real ingestion and uses chunk-only dry-run path. |
| `src/rag/ingestion.py` | `src/rag/chunker.py` / `src/rag/embedder.py` | `chunk_markdown`, `embed_documents` | VERIFIED | Ingestion chunks, builds title/section-enriched embedding text, embeds before DB mutation, and persists raw chunk content. |
| `src/api/routers/search.py` | `src/rag/retriever.py` | `Retriever.search` | VERIFIED | Endpoint passes query, tenant_id, top_k, doc_type, and risk_level to retriever. |
| `src/rag/retriever.py` | `src/repositories/policy_chunk_repo.py` | `search_similar` | VERIFIED | Retriever uses repository vector search with deeper internal top_k and tenant/filter arguments before reranking. |
| `scripts/eval_rag_hit_at_5.py` | `eval/golden_rag_queries.jsonl` | JSONL load and `_score_case()` | VERIFIED | Eval loads cases, scores exact expected chunk IDs for top-5, and separately tracks fallback accuracy. |
| `src/rag/citation_validator.py` | `src/rag/schemas.py` | `RetrievalResult.evidence` | VERIFIED | Validator checks requested citations against returned evidence chunk IDs. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/ingest_policies.py` | `DOCUMENT_MANIFEST` / reports | `data/policies/*.md` and `chunk_markdown()` | Yes | VERIFIED by dry-run: 15 successful docs, 90 total chunks. |
| `src/rag/ingestion.py` | `embeddings` | `EmbeddingService.embed_documents()` | Yes | VERIFIED by code path and Plan 07 live re-ingestion evidence. |
| `src/repositories/policy_chunk_repo.py` | `(PolicyChunk, score)` | PostgreSQL pgvector similarity query | Yes | VERIFIED by integration tests and live audit; tenant/doc filters are in SQL path. |
| `src/rag/retriever.py` | `evidence` | Repository search plus deterministic reranking | Yes | VERIFIED by focused retriever tests and live EVAL-02 result. |
| `src/api/routers/search.py` | `result.model_dump()` | `Retriever.search()` | Yes | VERIFIED by `tests/test_search_integration.py`. |
| `scripts/eval_rag_hit_at_5.py` | `hit_at_5`, `fallback_acc` | Production `SessionLocal` + `Retriever` path | Yes | VERIFIED by Plan 07 live audit: Hit@5 83.3%, fallback accuracy 100.0%. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Dry-run chunks all corpus docs without API key or DB | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --dry-run` | 15/15 docs succeeded; 90 chunks total | PASS |
| Golden set shape | `node -e ... eval/golden_rag_queries.jsonl` | 14 rows, 2 fallback, category distribution 5/3/2/2/2 | PASS |
| Eval CLI runnable | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --help` | Shows `--golden-set`, `--threshold`, `--tenant-id`, `--diagnostic-top-k` | PASS |
| Phase 2 focused tests | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_ingestion.py tests/test_retriever.py tests/test_rag_eval.py tests/test_search_integration.py -q` | 25 passed with localhost PostgreSQL access | PASS |
| Full regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | 50 passed | PASS |
| Schema drift | `gsd-sdk query verify.schema-drift "02"` | `valid: true`, no issues | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RAG-01 | 02, 03 | Import 15-30 Chinese policy docs | SATISFIED | 15 manifest-backed Markdown docs; dry-run processed all successfully. |
| RAG-02 | 01, 02, 03 | Chunking, embedding, pgvector storage/retrieval | SATISFIED | Schema, chunker, embedder, ingestion, repository, and live re-ingestion evidence all present. |
| RAG-03 | 01, 02, 03 | Chunk metadata | SATISFIED | Metadata exists across document/chunk models and is returned in evidence. |
| RAG-04 | 03, 04 | tenant_id/doc_type/risk_level filtering | SATISFIED | Repository filters tenant/doc/risk; integration test covers tenant mismatch exclusion. |
| RAG-06 | 04 | No-evidence fallback | SATISFIED | Retriever fallback logic plus endpoint/retriever tests; Plan 07 live fallback accuracy 100.0%. |
| RAG-07 | 04 | Citation validator | SATISFIED | Deterministic chunk-ID validation against retrieval evidence with tests. |
| INFR-06 | 02, 03 | CLI/background ingestion/eval without task queue | SATISFIED | Ingestion and eval are CLI scripts; no separate task queue introduced. |
| EVAL-01 | 05 | Golden set categories | SATISFIED FOR PHASE 2 / DEFERRED FINAL SIZE | Phase 2 has 14-case baseline with required RAG/fallback categories; 25-40 final expansion is Phase 6. |
| EVAL-02 | 04, 05, 06, 07 | RAG Hit@5 evaluation | SATISFIED | Eval script uses DB-backed production retriever; Plan 07 live audit records Hit@5 83.3% and fallback accuracy 100.0%. |

No orphaned Phase 2 requirement IDs found. The union of plan frontmatter IDs matches the roadmap Phase 2 set: `EVAL-01`, `EVAL-02`, `INFR-06`, `RAG-01`, `RAG-02`, `RAG-03`, `RAG-04`, `RAG-06`, `RAG-07`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tests/test_retriever.py` | 160 | `return []` in fake repository | Info | Intentional no-result branch for tenant isolation/fallback tests; not a runtime stub. |
| Several files | various | Empty list/dict initializers | Info | Runtime accumulators, test assertions, or Pydantic defaults; no hollow user-visible data flow found. |

### Human Verification Required

None. Live external verification was already performed and recorded in `07-RETRIEVAL-AUDIT.md` and `07-SUMMARY.md`: real ingestion passed, DB-backed Hit@5 passed at 83.3%, fallback accuracy passed at 100.0%, and the full local regression passes.

### Gaps Summary

No blocking gaps remain. The previous EVAL-02 gap is closed by Plan 07 live DB-backed evaluation. The only deferred item is EVAL-01's final 25-40 case golden-set expansion, which is explicitly assigned to Phase 6 and does not block Phase 2.

---

_Verified: 2026-05-11T03:06:54Z_
_Verifier: Claude (gsd-verifier)_
