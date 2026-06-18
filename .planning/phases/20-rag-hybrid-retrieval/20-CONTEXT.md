# Phase 20: RAG Hybrid Retrieval - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 20 upgrades MOCA's policy retrieval path from pgvector-only retrieval plus lightweight lexical rerank into a minimal production-style PostgreSQL hybrid retriever.

This phase owns retrieval-ready chunk search text, PostgreSQL full-text and pg_trgm indexes, application-level Chinese tokenization, dense + sparse + fuzzy retrieval, RRF fusion, minimal retrieval trace, and focused retrieval eval coverage.

This phase does not implement OCR, PDF/DOCX/image parsing, `DocumentBlock`, page/bbox citation, `MaterialClaim`, semantic verifier, reranker/query rewrite, Vespa/OpenSearch, or a full external `SearchBackend` contract. OCR/parser/`DocumentBlock` belongs to Phase 21: RAG Production Ingestion + OCR. `MaterialClaim` and semantic verification belong to Phase 22: RAG Context Builder + Hallucination Control. Reranker/query rewrite belongs to Phase 23: RAG Reranker + Query Rewrite. Vespa/OpenSearch and full external `SearchBackend` belong to Phase RAG-5: Optional External Search Backend.
</domain>

<decisions>
## Implementation Decisions

### Phase Numbering

- **D-01:** Use Phase 20 for this RAG milestone. Repository search found no tracked Phase 18/19 owner directories, but the user flagged that Phase 18/19 may already exist outside the current repo state. Phase 20 avoids a likely planning collision without renumbering Phase 17.

### Retrieval Backend Boundary

- **D-02:** Keep PostgreSQL as the only retrieval backend in this phase: pgvector for dense semantic search, PostgreSQL full-text search for sparse keyword search, and pg_trgm for fuzzy fallback.
- **D-03:** Do not introduce Vespa, Elasticsearch, OpenSearch, or a general external `SearchBackend` interface in Phase 20. The current `PolicyKnowledgeService` facade is the cross-layer boundary.
- **D-04:** `EvidenceRefV1` remains the canonical evidence identity. Runtime trace fields may help eval/debug, but they must not replace or weaken `EvidenceRefV1`, `text_hash`, `evidence_id`, or policy version semantics.

### Data And Tokenization

- **D-05:** Add retrieval-only `PolicyChunk.search_text` and generated/stored PostgreSQL `search_vector`; do not mutate `PolicyChunk.content`, because citation `text_hash` must continue to hash persisted chunk content only.
- **D-06:** Build `search_text` during ingestion from title, section, content, doc type, risk level, and application-level tokenizer terms. The allowed context helps retrieval but does not become citation text.
- **D-07:** Chinese search uses an application-level tokenizer with a domain dictionary for refund/support policy terms. PostgreSQL full-text uses the `simple` configuration over the already-tokenized, space-separated `search_text`.

### Ranking

- **D-08:** Dense, sparse, and fuzzy channels each return pre-filtered candidate lists. RRF fuses ranks, not raw scores.
- **D-09:** RRF determines ordering. `EvidenceRefV1.score` and `KnowledgeSearchResult.best_score` remain 0-1 normalized confidence values so existing strong/partial/no-evidence thresholds remain meaningful.
- **D-10:** The existing lightweight lexical rerank can remain only as a fallback or tie-breaker. It is not the completed hybrid retrieval implementation.

### Scope And Safety

- **D-11:** Tenant, effective date, doc type, risk level, and existing knowledge-scope checks must apply before each retrieval channel contributes candidates.
- **D-12:** Business facts remain Tool System outputs. They must not enter `policy_chunks`, search indexes, or `EvidenceRefV1`.
- **D-13:** Retrieval trace is internal only. It may include `selected_by`, channel ranks, RRF score, normalized confidence, and filter status; it must not enter LLM prompts by default.

### the agent's Discretion

- Exact PostgreSQL score normalization constants may be adjusted during implementation if tests pin behavior and existing facade thresholds remain stable.
- Exact helper class names may follow local conventions, but the plan should prefer small functions and dataclasses over a broad backend abstraction.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope And Requirements

- `.planning/ROADMAP.md` - Phase 20 goal, success criteria, planning prerequisites, and deferred boundaries.
- `.planning/REQUIREMENTS.md` - `RAGHYB-*`, `RAGTOK-*`, `RAGRET-*`, `RAGSCOPE-*`, `RAGTRACE-01`, and `RAGEVAL-01`.
- `.planning/PROJECT.md` - current milestone scope and safety boundaries.
- `.planning/STATE.md` - current planning state and deferred Phase 17 ownership.

### Normative Contracts

- `docs/contract-spec.md` section 8.3 - `PolicyKnowledgeService`, `KnowledgeContext`, `KnowledgeSearchRequest`, `KnowledgeSearchResult`, canonical `EvidenceRefV1`, citation membership, and hash projection rules.
- `docs/contract-spec.md` section 12/17 references to RAG events - RAG calls are service/tool events, not business truth.
- `docs/eval-test-plan.md` - RAG groundedness and eval direction.
- `docs/rag-architecture-spec.md` - production-oriented RAG target spec, especially current-state baseline, RAG-1, hallucination-control deferrals, and Postgres-first backend decision.

### Current Code

- `src/rag/ingestion.py` - current Markdown ingestion, embedding text construction, and chunk insert path.
- `src/rag/chunker.py` - current heading-aware Markdown chunking.
- `src/rag/embedder.py` - DashScope/OpenAI-compatible embedding service and 1024 dimension assumption.
- `src/knowledge/retrieval.py` - current retrieval engine, threshold semantics, lexical rerank, and hit projection.
- `src/knowledge/service.py` - facade behavior, merchant-scope deny-before-adapter behavior, and error/no-evidence handling.
- `src/knowledge/schemas.py` - canonical `EvidenceRefV1` and search result schemas.
- `src/repositories/policy_chunk_repo.py` - current pgvector repository query and metadata filters.
- `src/db/models.py` - `PolicyDocument` and `PolicyChunk` ORM models.
- `src/db/migrations/versions/013_long_term_case_memory.py` - current Alembic head before Phase 20.
- `tests/knowledge/test_retrieval.py`, `tests/knowledge/test_service.py`, `tests/knowledge/test_effective_time.py`, `tests/knowledge/test_tenant_scope.py`, `tests/test_ingestion.py` - existing retrieval, facade, effective-time, tenant, and ingestion regression tests.
</canonical_refs>

<code_context>
## Existing Code Insights

- Current `PolicyRetrievalEngine` embeds the query, calls `PolicyChunkRepository.search_similar`, applies effective-date filtering again, then applies lightweight overlap rerank.
- Current `PolicyChunkRepository.search_similar` is pgvector-only and joins `PolicyDocument` for `doc_type`.
- Current `PolicyChunk` has `content`, `risk_level`, `effective_date`, and `embedding`, but no `search_text`, `search_vector`, full-text index, or pg_trgm index.
- Current ingestion embeds `title / section: content` but persists only raw chunk content. Phase 20 should preserve that citation separation and add separate retrieval-only search text.
- Existing tests use fake repositories with `search_similar`; Phase 20 tests should update fakes to expose dense/sparse/fuzzy methods without broadening production interfaces.
</code_context>

<specifics>
## Specific Ideas

- Add `src/rag/search_text.py` with deterministic normalization/tokenization helpers and a small domain dictionary.
- Add `PolicyChunkRepository.search_sparse(...)` and `PolicyChunkRepository.search_fuzzy(...)` next to `search_similar(...)`.
- Add a small RRF fusion helper in `src/knowledge/retrieval.py`, not a full backend abstraction.
- Extend `PolicyRetrievalHit` with optional internal trace fields.
- Keep official eval scoring at top 5 and add optional per-channel diagnostic output for failed cases.
</specifics>

<deferred>
## Deferred Ideas

- OCR and parser abstraction for PDF/DOCX/image inputs - Phase 21: RAG Production Ingestion + OCR.
- `DocumentBlock`, page/bbox/cell citation, table-aware chunking - Phase 21: RAG Production Ingestion + OCR.
- `MaterialClaim`, semantic support verifier, conflict detector, risk-only hallucination verifier - Phase 22: RAG Context Builder + Hallucination Control.
- Query rewrite, reranker interface, optional cross-encoder/external rerank API, full ranking explanation, ablation eval, and latency budget - Phase 23: RAG Reranker + Query Rewrite.
- Vespa/OpenSearch shadow testing and external `SearchBackend` contract - Phase RAG-5: Optional External Search Backend.
</deferred>

---

*Phase: 20-rag-hybrid-retrieval*
*Context gathered: 2026-06-18*
