---
status: complete
phase: 20-rag-hybrid-retrieval
source:
  - .planning/phases/20-rag-hybrid-retrieval/20-01-postgres-hybrid-retrieval-SUMMARY.md
started: 2026-06-18T10:20:05Z
updated: 2026-06-18T13:08:52Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Migration Smoke
expected: From a fresh local environment or disposable database, Phase 20's migration path includes `014_rag_hybrid_retrieval`, creates retrieval-only `search_text`, generated `search_vector`, full-text GIN and pg_trgm GIN indexes, and does not require OCR, DocumentBlock, MaterialClaim, Vespa/OpenSearch, or an external SearchBackend to boot or run the retrieval test suite.
result: pass

### 2. Tokenizer And Search Text
expected: Running `uv run pytest tests/rag/test_search_text.py -q` passes, and the tokenizer preserves refund/support domain terms such as `仅退款`, `七天无理由`, `二次销售`, `商家举证`, `补偿券`, and `退款时效` while producing deterministic search text without mutating citation content.
result: pass

### 3. Ingestion Citation Boundary
expected: Running `uv run pytest tests/test_ingestion.py tests/rag/test_search_text.py -q` passes; ingestion stores retrieval-only `search_text` while persisted `PolicyChunk.content` remains the raw citation text used for `EvidenceRefV1.text_hash`.
result: pass

### 4. Scoped Hybrid Channels
expected: Running `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_effective_time.py tests/knowledge/test_tenant_scope.py -q` passes; dense, sparse, and fuzzy channels all receive tenant, doc_type, risk_level, and effective_date filters before candidates are returned.
result: pass

### 5. RRF Ranking And EvidenceRef Compatibility
expected: Running `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_retrieval.py tests/knowledge/test_service.py -q` passes; RRF controls result ordering, but `EvidenceRefV1.score` and `KnowledgeSearchResult.best_score` remain normalized 0-1 confidence values, and hybrid trace fields do not appear in `EvidenceRefV1`.
result: pass

### 6. Eval Diagnostics Boundary
expected: Running `uv run pytest tests/test_rag_eval.py tests/knowledge/test_hybrid_retrieval.py -q` passes; failed-case diagnostics can include `selected_by`, channel ranks, and `rrf_score` when present, while official Hit@5/fallback scoring is unchanged and no business facts become policy evidence.
result: pass

### 7. Full Regression Gate
expected: Running `uv run pytest -q` completes successfully for the repository, showing Phase 20 did not regress existing memory, approval, action, replay, knowledge, or ingestion contracts.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
