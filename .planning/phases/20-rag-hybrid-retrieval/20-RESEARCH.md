# Phase 20: RAG Hybrid Retrieval - Research

**Researched:** 2026-06-18
**Status:** Ready for planning
**Scope:** PostgreSQL hybrid retrieval for policy chunks: search text, tokenization, full-text, pg_trgm, RRF, trace, and focused eval.

## Planning Summary

Phase 20 should improve retrieval quality without widening the architecture into the later ingestion/verifier roadmap. The current system already has the right facade boundary: `PolicyKnowledgeService` produces canonical `EvidenceRefV1` and hides repository details from Agent nodes. The missing production slice is inside the retrieval backend: chunk search text, sparse/fuzzy indexes, channel-specific candidate retrieval, RRF fusion, and tests proving scope filters are applied before candidates are selected.

The safest implementation path is:

- add retrieval-only search text and generated `search_vector`;
- add deterministic application-level tokenizer/search-text builder;
- add repository methods for dense/sparse/fuzzy channels;
- update `PolicyRetrievalEngine` to fuse channel ranks with RRF;
- keep normalized 0-1 confidence for existing threshold semantics;
- add trace fields for eval/debug only.

OCR, `DocumentBlock`, semantic verification, and conflict detection are production RAG requirements, but they should start after the hybrid retrieval slice is stable.

## Live Code Findings

### Current Retrieval

- `src/knowledge/retrieval.py` has `PolicyRetrievalEngine.retrieve_hits(...)`.
- It embeds `QUERY_PREFIX + query`, calls `PolicyChunkRepository.search_similar(...)`, reranks by local query-term overlap, then maps hits to `EvidenceRefV1`.
- `PolicyRetrievalHit.score` currently behaves like vector similarity on a 0-1 scale.
- `strong_evidence`, `partial_evidence`, and `no_evidence` are derived from `MIN_SIMILARITY_THRESHOLD` and `STRONG_EVIDENCE_THRESHOLD`.

### Current Repository

- `src/repositories/policy_chunk_repo.py` has only `search_similar(...)`.
- The query joins `PolicyDocument`, filters by `tenant_id`, optional `doc_type`, optional `risk_level`, optional `effective_date`, and orders by pgvector cosine distance.
- There is no full-text query, pg_trgm fuzzy query, or retrieval explanation.

### Current Schema

- `src/db/models.py` defines `PolicyChunk` with `content`, `risk_level`, `effective_date`, and `embedding`.
- `src/db/migrations/versions/002_rag_pipeline.py` created the HNSW index.
- Current Alembic head is `013_long_term_case_memory.py`; Phase 20 should add a new `014_rag_hybrid_retrieval.py` migration.

### Current Ingestion

- `src/rag/ingestion.py` reads UTF-8 text, chunks Markdown, embeds `title / section: content`, and persists raw chunk `content`.
- This separation is correct. Phase 20 should add `search_text` for retrieval, not alter `content`.

### Current Tests And Eval

- `tests/knowledge/test_retrieval.py` covers strong/partial/no evidence, tenant behavior through fake repo, lexical rerank, and fallback behavior.
- `tests/knowledge/test_service.py` covers merchant-scope pre-deny and hash re-fetch behavior.
- `tests/knowledge/test_effective_time.py` covers effective date semantics.
- `scripts/eval_rag_hit_at_5.py` reports Hit@5 and fallback accuracy.

## Recommended Implementation Shape

### 1. Tokenizer And Search Text

Create `src/rag/search_text.py` with:

- `DOMAIN_TERMS`: refund/support dictionary including `仅退款`, `七天无理由`, `二次销售`, `商家举证`, `高价值订单`, `补偿券`, `退款时效`, `跨境订单`.
- `normalize_search_text(text: str) -> str`
- `tokenize_search_text(text: str) -> list[str]`
- `build_policy_chunk_search_text(*, title: str, section: str, content: str, doc_type: str | None = None, risk_level: str | None = None) -> str`

The helper should emit deterministic, space-separated terms for PostgreSQL `simple` full-text search. It should include matched domain terms, CJK 2-4 grams, alphanumeric terms, and allowed metadata/context terms. It must not mutate citation text.

### 2. Schema And Migration

Add to `PolicyChunk`:

- `search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")`
- `search_vector` mapped as PostgreSQL `TSVECTOR` with a generated/stored expression over `to_tsvector('simple', coalesce(search_text, ''))`.

Add migration `014_rag_hybrid_retrieval.py`:

- `down_revision = "013_long_term_case_memory"`
- `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- add nullable `search_text`, backfill existing rows from `section || ' ' || content`, then alter non-null;
- add generated stored `search_vector`;
- create `ix_policy_chunks_search_vector_gin` using GIN;
- create `ix_policy_chunks_search_text_trgm` using GIN and `gin_trgm_ops`;
- create a practical scope/filter index such as `ix_policy_chunks_retrieval_scope` over `tenant_id`, `effective_date`, and `risk_level`;
- downgrade drops indexes, `search_vector`, and `search_text` in reverse order. Do not drop `pg_trgm` because it may be shared.

### 3. Repository Methods

Keep the repository local and concrete:

- `search_similar(...)` stays dense pgvector.
- Add `search_sparse(query_text: str, tenant_id: UUID, top_k: int, doc_type: str | None, risk_level: str | None, effective_date: date | None) -> list[tuple[PolicyChunk, float]]`.
- Add `search_fuzzy(query_text: str, tenant_id: UUID, top_k: int, min_similarity: float, doc_type: str | None, risk_level: str | None, effective_date: date | None) -> list[tuple[PolicyChunk, float]]`.

Sparse scoring should use `plainto_tsquery('simple', query_text)`, `@@`, and `ts_rank_cd`. Fuzzy scoring should use pg_trgm `similarity(search_text, query_text)` with an explicit threshold. All methods must apply tenant/effective/doc_type/risk filters before returning candidates.

### 4. RRF Fusion

Add a small fusion layer in `src/knowledge/retrieval.py`:

- `RRF_K = 60`
- channel names: `dense`, `sparse`, `fuzzy`
- per-candidate identity: `(doc_key, chunk_id, policy_version)`
- `rrf_score = sum(1 / (RRF_K + rank_i))`
- candidate trace: selected channels, dense/sparse/fuzzy rank, per-channel raw score, normalized confidence, filter status.

RRF determines ordering. `PolicyRetrievalHit.score` should be a normalized confidence score on a 0-1 scale. Use dense similarity as-is, fuzzy similarity as-is, and normalize sparse rank with `SPARSE_SCORE_SCALE = 0.20` as `min(max(raw_sparse_score / SPARSE_SCORE_SCALE, 0.0), 1.0)`. Existing threshold semantics should not consume raw RRF score.

### 5. Trace And Eval

`PolicyRetrievalHit` may gain internal trace fields:

- `selected_by: tuple[str, ...]`
- `dense_rank`, `sparse_rank`, `fuzzy_rank`
- `rrf_score`
- `filter_status`

These fields are useful for tests and eval diagnostics. They should not be serialized into `EvidenceRefV1` or prompt context by default.

`scripts/eval_rag_hit_at_5.py` can include trace in failed-case diagnostics while preserving official Hit@5 and fallback accuracy scoring.

## Test And Verification Strategy

Required automated coverage:

- `tests/rag/test_search_text.py`: tokenizer/domain dictionary/search-text builder.
- `tests/knowledge/test_hybrid_schema.py`: model and migration source checks for `search_text`, `search_vector`, GIN full-text index, pg_trgm index, downgrade order, and no `DocumentBlock`/OCR table creation.
- `tests/test_ingestion.py`: ingestion persists raw chunk content unchanged and sets retrieval-only `search_text`.
- `tests/knowledge/test_hybrid_retrieval.py`: RRF ordering, dense/sparse/fuzzy candidate merge, duplicate dedupe, confidence normalization, and trace fields.
- `tests/knowledge/test_retrieval.py`: preserve strong/partial/no evidence, no-domain fallback, query prefix, and low-confidence filtering.
- `tests/knowledge/test_effective_time.py`: each channel receives the same effective date.
- `tests/knowledge/test_service.py` or `tests/knowledge/test_tenant_scope.py`: merchant-scope deny happens before repository calls.
- `tests/test_rag_eval.py` or `scripts/eval_rag_hit_at_5.py` tests: Hit@5/fallback path remains runnable and can report hybrid diagnostics.

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` / existing pytest configuration |
| Quick run command | `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/test_ingestion.py -q` |
| Full suite command | `uv run pytest -q` |
| Estimated runtime | repo-dependent; quick retrieval subset should remain the per-task loop |

Sampling guidance:

- After tokenizer task: `uv run pytest tests/rag/test_search_text.py -q`.
- After schema task: `uv run pytest tests/knowledge/test_hybrid_schema.py -q`.
- After ingestion task: `uv run pytest tests/test_ingestion.py tests/rag/test_search_text.py -q`.
- After repository/retrieval tasks: `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_retrieval.py tests/knowledge/test_effective_time.py tests/knowledge/test_tenant_scope.py -q`.
- Before phase verification: `uv run pytest tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_eval.py -q`, then `uv run pytest -q` if environment cost is acceptable.

## Risk Notes

- Tenant/scope leaks are the highest-impact failure mode. Each retrieval channel must receive the same trusted tenant/effective/doc filters.
- Changing `PolicyChunk.content` or hashing `search_text` instead of raw content would break citation identity.
- Raw RRF scores are not compatible with the existing similarity thresholds.
- Using PostgreSQL full-text directly on unsegmented Chinese content will underperform. The application tokenizer must produce spaced terms.
- Adding a broad backend abstraction now would increase implementation surface without current backend diversity.

## Open Questions

None blocking for planning. Exact sparse score normalization constants can be tuned during implementation if tests pin strong/partial/no-evidence behavior.
