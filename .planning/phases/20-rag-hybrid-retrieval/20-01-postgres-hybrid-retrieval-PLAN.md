---
phase: 20
plan: 01
type: tdd
wave: 1
depends_on: []
files_modified:
  - src/rag/search_text.py
  - src/db/models.py
  - src/db/migrations/versions/014_rag_hybrid_retrieval.py
  - src/rag/ingestion.py
  - src/repositories/policy_chunk_repo.py
  - src/knowledge/retrieval.py
  - scripts/eval_rag_hit_at_5.py
  - tests/rag/test_search_text.py
  - tests/knowledge/test_hybrid_schema.py
  - tests/knowledge/test_hybrid_retrieval.py
  - tests/knowledge/test_retrieval.py
  - tests/knowledge/test_effective_time.py
  - tests/knowledge/test_tenant_scope.py
  - tests/test_ingestion.py
  - tests/test_rag_eval.py
autonomous: true
requirements:
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
must_haves:
  - "`PolicyChunk.content` remains the citation text and `EvidenceRefV1.text_hash` continues to hash only that content."
  - "`PolicyChunk.search_text` and generated `search_vector` exist with full-text and pg_trgm indexes in migration `014_rag_hybrid_retrieval.py`."
  - "Dense, sparse, and fuzzy channels are pre-filtered by tenant/effective/doc/risk scope before RRF fusion."
  - "RRF ranks candidates by channel rank while `EvidenceRefV1.score` remains a normalized 0-1 confidence value."
  - "Focused tests cover tokenizer, schema, ingestion, repository channel filters, RRF ordering, fallback behavior, and eval diagnostics."
---

# Plan 20-01: PostgreSQL Hybrid Retrieval

<objective>
Implement minimal production hybrid retrieval for MOCA policy RAG on PostgreSQL: retrieval-only search text, full-text and pg_trgm indexes, dense + sparse + fuzzy candidate retrieval, RRF fusion, internal trace, and focused eval coverage.
</objective>

<threat_model>
- T-20-01-01 tenant_scope_leak: a sparse or fuzzy channel could return chunks outside the trusted tenant/effective/doc/risk scope. Severity: high. Mitigation: repository methods share the same filter inputs and tests assert all channels receive tenant/effective filters.
- T-20-01-02 citation_identity_regression: ingestion could mutate chunk content or hash retrieval-only `search_text`. Severity: high. Mitigation: tests assert persisted `content` remains raw and `EvidenceRefV1.text_hash` uses full content.
- T-20-01-03 threshold_regression: raw RRF scores could replace 0-1 similarity confidence and break strong/partial/no-evidence behavior. Severity: high. Mitigation: tests pin RRF ordering separately from normalized confidence and facade status thresholds.
- T-20-01-04 stale_search_index: search text/vector could be absent or stale after ingestion/reimport. Severity: medium. Mitigation: generated `search_vector`, ingestion tests, and migration backfill checks.
- T-20-01-05 business_fact_pollution: business/tool facts could be stored or reported as policy evidence diagnostics. Severity: high. Mitigation: eval diagnostics stay retrieval-only and tests assert no business fact refs become `EvidenceRefV1`.
</threat_model>

<tasks>
<task id="20-01-01" type="tdd">
<name>Add deterministic policy search text tokenizer</name>
<files>src/rag/search_text.py, tests/rag/test_search_text.py</files>
<read_first>
- src/rag/chunker.py
- src/rag/ingestion.py
- tests/test_ingestion.py
- .planning/phases/20-rag-hybrid-retrieval/20-CONTEXT.md
- .planning/phases/20-rag-hybrid-retrieval/20-RESEARCH.md
</read_first>
<action>
Create `tests/rag/test_search_text.py` first, then implement `src/rag/search_text.py`.

Required public API:
- `DOMAIN_TERMS`: tuple containing at least `仅退款`, `七天无理由`, `二次销售`, `商家举证`, `高价值订单`, `补偿券`, `退款时效`, and `跨境订单`.
- `normalize_search_text(text: str) -> str`
- `tokenize_search_text(text: str) -> list[str]`
- `build_policy_chunk_search_text(*, title: str, section: str, content: str, doc_type: str | None = None, risk_level: str | None = None) -> str`

Tokenizer behavior:
- Lowercase ASCII.
- Collapse whitespace.
- Preserve matched domain terms as whole tokens.
- Add alphanumeric terms from `[a-z0-9]+`.
- Add CJK 2, 3, and 4-grams for contiguous CJK spans.
- Return deterministic de-duplicated tokens in first-seen order.
- `build_policy_chunk_search_text(...)` returns a space-separated string that includes title, section, content-derived terms, `doc_type`, and `risk_level` when present.
- Do not alter or return citation text. This module only builds retrieval text.
</action>
<acceptance_criteria>
- `tests/rag/test_search_text.py` contains `def test_domain_terms_are_preserved_as_tokens`.
- `tests/rag/test_search_text.py` contains `def test_build_policy_chunk_search_text_includes_context_without_mutating_content`.
- `src/rag/search_text.py` contains `def tokenize_search_text`.
- `src/rag/search_text.py` contains `def build_policy_chunk_search_text`.
- `src/rag/search_text.py` contains `仅退款`, `七天无理由`, `二次销售`, and `补偿券`.
- `uv run pytest tests/rag/test_search_text.py -q` exits 0.
</acceptance_criteria>
<done>Tokenizer tests pass and search text construction is deterministic.</done>
<verify>
uv run pytest tests/rag/test_search_text.py -q
</verify>
</task>

<task id="20-01-02" type="tdd">
<name>Add hybrid retrieval schema and migration</name>
<files>src/db/models.py, src/db/migrations/versions/014_rag_hybrid_retrieval.py, tests/knowledge/test_hybrid_schema.py</files>
<read_first>
- src/db/models.py
- src/db/migrations/versions/013_long_term_case_memory.py
- src/db/migrations/versions/002_rag_pipeline.py
- tests/memory/test_memory_schema.py
- .planning/phases/20-rag-hybrid-retrieval/20-CONTEXT.md
</read_first>
<action>
Create `tests/knowledge/test_hybrid_schema.py` first, then update the ORM and migration.

In `src/db/models.py`:
- Import `Computed` from `sqlalchemy`.
- Import `TSVECTOR` from `sqlalchemy.dialects.postgresql`.
- Add `PolicyChunk.search_text` as non-null `Text`.
- Add `PolicyChunk.search_vector` as a generated/stored PostgreSQL `TSVECTOR` using `to_tsvector('simple', coalesce(search_text, ''))`.

Create `src/db/migrations/versions/014_rag_hybrid_retrieval.py`:
- `revision = "014_rag_hybrid_retrieval"`
- `down_revision = "013_long_term_case_memory"`
- `upgrade()` executes `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
- Add nullable `policy_chunks.search_text`.
- Backfill existing rows with `trim(concat_ws(' ', section, content))`.
- Alter `policy_chunks.search_text` to non-null.
- Add generated stored `policy_chunks.search_vector` with `to_tsvector('simple', coalesce(search_text, ''))`.
- Create `ix_policy_chunks_search_vector_gin` using `GIN (search_vector)`.
- Create `ix_policy_chunks_search_text_trgm` using `GIN (search_text gin_trgm_ops)`.
- Create `ix_policy_chunks_retrieval_scope` over `tenant_id`, `effective_date`, and `risk_level`.
- `downgrade()` drops indexes, drops `search_vector`, then drops `search_text`. Do not drop `pg_trgm`.

Do not create OCR, `DocumentBlock`, parser, `MaterialClaim`, or external search backend tables.
</action>
<acceptance_criteria>
- `src/db/models.py` contains `search_text`.
- `src/db/models.py` contains `search_vector`.
- `src/db/models.py` contains `TSVECTOR`.
- `src/db/migrations/versions/014_rag_hybrid_retrieval.py` contains `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
- `src/db/migrations/versions/014_rag_hybrid_retrieval.py` contains `ix_policy_chunks_search_vector_gin`.
- `src/db/migrations/versions/014_rag_hybrid_retrieval.py` contains `ix_policy_chunks_search_text_trgm`.
- `src/db/migrations/versions/014_rag_hybrid_retrieval.py` contains `down_revision: str | None = "013_long_term_case_memory"`.
- `tests/knowledge/test_hybrid_schema.py` asserts the migration source does not contain `DocumentBlock`, `ocr`, `material_claim`, `vespa`, or `opensearch`.
- `uv run pytest tests/knowledge/test_hybrid_schema.py -q` exits 0.
</acceptance_criteria>
<done>Schema/model/migration tests pass and new indexes are declared.</done>
<verify>
uv run pytest tests/knowledge/test_hybrid_schema.py -q
</verify>
</task>

<task id="20-01-03" type="execute">
<name>Persist retrieval-only search text during ingestion</name>
<files>src/rag/ingestion.py, tests/test_ingestion.py, tests/rag/test_search_text.py</files>
<read_first>
- src/rag/ingestion.py
- src/rag/search_text.py
- tests/test_ingestion.py
- src/db/models.py
</read_first>
<action>
Update `IngestionService.ingest_document(...)` so each new `PolicyChunk` receives:

`search_text=build_policy_chunk_search_text(title=title, section=chunk.section, content=chunk.content, doc_type=doc_meta["doc_type"], risk_level=doc_meta["risk_level"])`

Keep the existing embedding text behavior:
- intro embedding text remains `f"{title}: {chunk.content}"`;
- section embedding text remains `f"{title} / {chunk.section}: {chunk.content}"`.

Keep persisted citation content exactly as `chunk.content`.

Update `tests/test_ingestion.py`:
- fake inserted chunks expose `search_text`;
- existing test `test_ingestion_embeds_title_and_section_but_persists_raw_content` continues asserting raw content;
- add assertion that inserted chunk `search_text` contains `退款规则`, `七天无理由`, and `二次销售` when present in title/section/content.
</action>
<acceptance_criteria>
- `src/rag/ingestion.py` imports `build_policy_chunk_search_text`.
- `src/rag/ingestion.py` assigns `search_text=` when constructing `PolicyChunk`.
- `tests/test_ingestion.py` asserts `[chunk.content for chunk in chunk_repo.inserted]` remains raw chunk content.
- `tests/test_ingestion.py` contains `search_text`.
- `uv run pytest tests/test_ingestion.py tests/rag/test_search_text.py -q` exits 0.
</acceptance_criteria>
<done>Ingestion stores search text without changing citation content.</done>
<verify>
uv run pytest tests/test_ingestion.py tests/rag/test_search_text.py -q
</verify>
</task>

<task id="20-01-04" type="tdd">
<name>Add sparse and fuzzy repository channels</name>
<files>src/repositories/policy_chunk_repo.py, tests/knowledge/test_hybrid_retrieval.py, tests/knowledge/test_effective_time.py, tests/knowledge/test_tenant_scope.py</files>
<read_first>
- src/repositories/policy_chunk_repo.py
- src/db/models.py
- tests/knowledge/test_effective_time.py
- tests/knowledge/test_tenant_scope.py
- .planning/phases/20-rag-hybrid-retrieval/20-RESEARCH.md
</read_first>
<action>
Create or extend `tests/knowledge/test_hybrid_retrieval.py` first with repository-facing expectations, then update `PolicyChunkRepository`.

Add methods:
- `search_sparse(query_text: str, tenant_id: UUID, top_k: int = 50, doc_type: str | None = None, risk_level: str | None = None, effective_date: date | None = None) -> list[tuple[PolicyChunk, float]]`
- `search_fuzzy(query_text: str, tenant_id: UUID, top_k: int = 20, min_similarity: float = 0.10, doc_type: str | None = None, risk_level: str | None = None, effective_date: date | None = None) -> list[tuple[PolicyChunk, float]]`

Sparse query:
- build `query_expr = func.plainto_tsquery("simple", query_text)`;
- rank with `func.ts_rank_cd(PolicyChunk.search_vector, query_expr)`;
- filter with `PolicyChunk.search_vector.op("@@")(query_expr)`;
- order by sparse rank descending;
- join `PolicyDocument` and use `selectinload(PolicyChunk.document)`.

Fuzzy query:
- score with `func.similarity(PolicyChunk.search_text, query_text)`;
- filter `similarity_expr >= min_similarity`;
- order by similarity descending;
- join `PolicyDocument` and use `selectinload(PolicyChunk.document)`.

Both methods must include the same trusted filters as `search_similar`: tenant, optional doc type, optional risk level, and optional effective date.
</action>
<acceptance_criteria>
- `src/repositories/policy_chunk_repo.py` contains `async def search_sparse`.
- `src/repositories/policy_chunk_repo.py` contains `async def search_fuzzy`.
- `src/repositories/policy_chunk_repo.py` contains `plainto_tsquery`.
- `src/repositories/policy_chunk_repo.py` contains `ts_rank_cd`.
- `src/repositories/policy_chunk_repo.py` contains `similarity`.
- `tests/knowledge/test_hybrid_retrieval.py` contains `def test_repository_sparse_and_fuzzy_methods_apply_scope_filters` or an equivalent async test name.
- `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_effective_time.py tests/knowledge/test_tenant_scope.py -q` exits 0.
</acceptance_criteria>
<done>Repository exposes sparse/fuzzy retrieval with pre-filters.</done>
<verify>
uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_effective_time.py tests/knowledge/test_tenant_scope.py -q
</verify>
</task>

<task id="20-01-05" type="tdd">
<name>Fuse dense, sparse, and fuzzy candidates with RRF</name>
<files>src/knowledge/retrieval.py, tests/knowledge/test_hybrid_retrieval.py, tests/knowledge/test_retrieval.py, tests/knowledge/test_service.py, tests/knowledge/test_effective_time.py</files>
<read_first>
- src/knowledge/retrieval.py
- src/knowledge/config.py
- src/knowledge/schemas.py
- src/repositories/policy_chunk_repo.py
- tests/knowledge/test_retrieval.py
- tests/knowledge/test_facade_status.py
- tests/knowledge/test_effective_time.py
- .planning/phases/20-rag-hybrid-retrieval/20-CONTEXT.md
</read_first>
<action>
Update tests first to cover hybrid fusion, then update `src/knowledge/retrieval.py`.

Required constants/helpers:
- `RRF_K = 60`
- `SPARSE_CANDIDATE_TOP_K = 50`
- `FUZZY_CANDIDATE_TOP_K = 20`
- `FUZZY_MIN_SIMILARITY = 0.10`
- `SPARSE_SCORE_SCALE = 0.20`
- a small helper that fuses channel result lists by `(doc_key, chunk_id, policy_version)`.
- `normalize_sparse_score(raw_score: float) -> float`, implemented as `min(max(raw_score / SPARSE_SCORE_SCALE, 0.0), 1.0)`.

Update `PolicyRetrievalHit` to include optional internal trace fields:
- `selected_by: tuple[str, ...] = ()`
- `dense_rank: int | None = None`
- `sparse_rank: int | None = None`
- `fuzzy_rank: int | None = None`
- `rrf_score: float | None = None`
- `filter_status: str = "passed"`

Retrieval flow:
- Parse `effective_at` once.
- Build query embedding as today with `QUERY_PREFIX`.
- Build `query_search_text` with `build_policy_chunk_search_text(title="", section="", content=query)`.
- Call dense `search_similar`, sparse `search_sparse`, and fuzzy `search_fuzzy` using the same tenant, doc type, risk level, and effective date.
- Fuse by RRF rank with `RRF_K`.
- Keep at most `max_results`.
- Use RRF for ordering.
- Compute `PolicyRetrievalHit.score` as normalized confidence on a 0-1 scale, not raw RRF. Use max available channel confidence where dense similarity and fuzzy similarity are already 0-1, and sparse score is `normalize_sparse_score(raw_sparse_score)`.
- Preserve existing fallback behavior for out-of-domain/no-anchor queries and low-confidence candidates.
- Preserve `EvidenceRefV1.build(...)` inputs and rank assignment.

Do not add RRF trace fields to `EvidenceRefV1` or `KnowledgeSearchResult` in this phase.
</action>
<acceptance_criteria>
- `src/knowledge/retrieval.py` contains `RRF_K = 60`.
- `src/knowledge/retrieval.py` contains `SPARSE_SCORE_SCALE = 0.20`.
- `src/knowledge/retrieval.py` contains `def normalize_sparse_score`.
- `src/knowledge/retrieval.py` contains `search_sparse`.
- `src/knowledge/retrieval.py` contains `search_fuzzy`.
- `src/knowledge/retrieval.py` contains `rrf_score`.
- `src/knowledge/retrieval.py` contains `selected_by`.
- `tests/knowledge/test_hybrid_retrieval.py` contains `test_rrf_promotes_candidate_seen_by_multiple_channels`.
- `tests/knowledge/test_hybrid_retrieval.py` contains `test_rrf_score_does_not_replace_normalized_confidence_score`.
- `tests/knowledge/test_hybrid_retrieval.py` contains `test_retrieval_trace_stays_internal_to_hits`.
- `tests/knowledge/test_retrieval.py` still passes existing strong/partial/no-evidence and fallback tests.
- `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_retrieval.py tests/knowledge/test_service.py tests/knowledge/test_effective_time.py -q` exits 0.
</acceptance_criteria>
<done>Hybrid RRF retrieval preserves existing facade semantics and exposes internal trace on hits.</done>
<verify>
uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_retrieval.py tests/knowledge/test_service.py tests/knowledge/test_effective_time.py -q
</verify>
</task>

<task id="20-01-06" type="execute">
<name>Update eval diagnostics and run retrieval regression suite</name>
<files>scripts/eval_rag_hit_at_5.py, tests/test_rag_eval.py, tests/knowledge/test_hybrid_retrieval.py</files>
<read_first>
- scripts/eval_rag_hit_at_5.py
- tests/test_rag_eval.py
- src/knowledge/retrieval.py
- .planning/phases/20-rag-hybrid-retrieval/20-VALIDATION.md
</read_first>
<action>
Update `scripts/eval_rag_hit_at_5.py` so failed-case diagnostics can include internal hybrid trace fields when present on `PolicyRetrievalHit`, while official scoring remains unchanged:
- Hit@5 still checks expected chunk IDs in top 5.
- Fallback accuracy still checks `retrieval_status == "no_evidence"`.
- Diagnostic evidence may include `selected_by`, `dense_rank`, `sparse_rank`, `fuzzy_rank`, and `rrf_score` if those attributes exist.

Update or add tests in `tests/test_rag_eval.py` to prove:
- `_score_case(...)` behavior is unchanged for hit and fallback cases.
- diagnostic evidence can carry hybrid trace fields without requiring them.
- no diagnostic path creates `EvidenceRefV1` from business facts or adds `business_fact_refs`.

Run the focused retrieval regression suite. If DB-backed eval cannot run because local PostgreSQL is unavailable, record that blocker in the eventual summary and still run pure pytest coverage.
</action>
<acceptance_criteria>
- `scripts/eval_rag_hit_at_5.py` contains `selected_by`.
- `scripts/eval_rag_hit_at_5.py` contains `rrf_score`.
- `tests/test_rag_eval.py` contains a test for unchanged fallback scoring.
- `tests/test_rag_eval.py` contains `selected_by` or `rrf_score`.
- `tests/test_rag_eval.py` does not expect business facts to become `EvidenceRefV1`.
- `uv run pytest tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_eval.py -q` exits 0.
</acceptance_criteria>
<done>Eval diagnostics support hybrid traces and focused regression suite passes.</done>
<verify>
uv run pytest tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_eval.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_hybrid_schema.py tests/knowledge/test_hybrid_retrieval.py tests/test_ingestion.py -q`.
- Run `uv run pytest tests/knowledge/test_retrieval.py tests/knowledge/test_service.py tests/knowledge/test_effective_time.py tests/knowledge/test_tenant_scope.py tests/test_rag_eval.py -q`.
- Run `uv run ruff check src/rag/search_text.py src/knowledge/retrieval.py src/repositories/policy_chunk_repo.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py`.
- If local DB is available and seeded, run `uv run python scripts/eval_rag_hit_at_5.py --threshold 0.8`.
- Before phase verification, run `uv run pytest -q` unless environment constraints make the full suite impractical; record any blocker explicitly.
</verification>

<success_criteria>
- Policy chunks have retrieval-only `search_text` and generated `search_vector`.
- PostgreSQL full-text and pg_trgm indexes are declared in Phase 20 migration.
- Ingestion preserves raw citation content and persists deterministic search text.
- Dense, sparse, and fuzzy retrieval channels return scoped candidates.
- RRF fusion improves ranking without breaking normalized threshold semantics.
- Minimal trace exists on retrieval hits and remains out of `EvidenceRefV1`.
- Focused tests and eval diagnostics cover tokenizer, schema, ingestion, RRF, scope filters, fallback, and Hit@5 path.
</success_criteria>

<must_haves>
- `EvidenceRefV1` remains canonical and unchanged.
- Business data remains outside policy chunk storage and policy evidence refs.
- OCR/parser/`DocumentBlock` stays deferred to Phase 21: RAG Production Ingestion + OCR. `MaterialClaim` and semantic verifier stay deferred to Phase 22: RAG Context Builder + Hallucination Control. Query rewrite, reranker, and full ranking explanation stay deferred to Phase 23: RAG Reranker + Query Rewrite. Vespa/OpenSearch and full external `SearchBackend` stay deferred to Phase RAG-5: Optional External Search Backend.
- Every Phase 20 requirement ID appears in this plan's frontmatter.
</must_haves>
