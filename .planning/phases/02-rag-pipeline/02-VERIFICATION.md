---
phase: 02-rag-pipeline
verified: 2026-05-10T14:35:47Z
status: gaps_found
score: 35/36 must-haves verified; live Hit@5 failed
overrides_applied: 0
deferred:
  - truth: "EVAL-01 full golden set size of 25-40 cases"
    addressed_in: "Phase 6"
    evidence: "Phase 6 success criteria: Golden set expanded to 25-40 cases; Phase 2 context D-11a/D-11h scopes this phase to 10-15 hand-written cases and defers expansion."
human_verification:
  - test: "Run real policy ingestion with DASHSCOPE_API_KEY against local PostgreSQL"
    expected: "scripts/ingest_policies.py reports 15 successful documents and the database contains non-null policy_chunks.embedding rows for Phase 2 doc_keys such as refund_policy."
    why_human: "Live DashScope embedding is an external service integration; current local DB check after seed shows 15 documents, 30 chunks, 0 embedded chunks, and 0 refund_policy Phase 2 documents."
  - test: "Run scripts/eval_rag_hit_at_5.py against the ingested database"
    expected: "Report prints measurable Hit@5 and fallback accuracy, both at or above the 80 percent threshold, and exits 0."
    why_human: "The eval script is wired and --help works, but the real run depends on live embeddings and ingested pgvector rows."
  - test: "Call /api/v1/search/ with an authenticated knowledge:read user after ingestion"
    expected: "Relevant refund/SOP/FAQ queries return top-5 evidence with doc_key, chunk_id, title, section, score, text, and metadata filters work; unrelated queries return no_evidence fallback."
    why_human: "Endpoint behavior is covered with deterministic test vectors, but live semantic relevance requires real embedding provider output."
---

# Phase 2: RAG Pipeline Verification Report

**Phase Goal:** Knowledge documents are chunked, embedded, and retrievable via pgvector; search endpoint returns relevant rule chunks with metadata filtering, confidence scoring, and citation validation.
**Verified:** 2026-05-10T14:35:47Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CLI ingestion processes 15-30 Chinese knowledge documents, chunks by heading, generates embeddings, and stores in pgvector with HNSW index | VERIFIED | `scripts/ingest_policies.py --dry-run` processed all 15 manifest docs successfully. Live DashScope ingestion also processed 15/15 manifest documents and the DB contained 15 Phase 2 documents, 90 chunks, and 90 non-null embeddings. Migration creates `vector(1024)` plus HNSW `vector_cosine_ops` index at `002_rag_pipeline.py:32-43`. |
| 2 | Chunk metadata and retrieval filters include tenant_id, doc_type, risk_level, citation IDs, title/section/text/effective_date | VERIFIED | `PolicyDocument` and `PolicyChunk` store doc_key/doc_id, chunk_id, title, doc_type, section, content, risk_level, effective_date, tenant_id, and embedding. `PolicyChunkRepository.search_similar` joins `PolicyDocument`, enforces both chunk and document tenant, eager-loads document metadata, and filters doc_type/risk_level at `policy_chunk_repo.py:41-66`. |
| 3 | Search endpoint returns top-5 relevant chunks; golden set of 10+ queries has measurable Hit@5 | VERIFIED (automated wiring) | `/api/v1/search/` is registered and protected; route delegates to `Retriever.search` at `search.py:19-43`. Golden set has 14 JSONL rows with distribution `refund_rule=5, sop=3, faq=2, boundary=2, fallback=2`; eval script computes Hit@5/fallback accuracy and exits non-zero below threshold at `eval_rag_hit_at_5.py:128-174`. |
| 4 | Citation validator verifies cited doc/chunk references exist in retrieval results | VERIFIED | `validate_citations` rejects empty citations and chunk IDs missing from retrieval evidence at `citation_validator.py:14-31`; `tests/test_retriever.py` covers valid, invalid, and empty citations. |
| 5 | No-evidence fallback is returned when confidence threshold is not met | VERIFIED | `Retriever` uses `MIN_SIMILARITY_THRESHOLD = 0.55`, `STRONG_EVIDENCE_THRESHOLD = 0.70`, and returns `no_evidence` with the required fallback message at `retriever.py:10-64`; endpoint integration tests cover no-evidence behavior. |

**Score:** 35/36 combined roadmap and plan must-haves verified. Live verification later confirmed ingestion and endpoint behavior, but RAG Hit@5 failed the 80 percent threshold.

### Live Verification Update

| Check | Result | Evidence |
|---|---|---|
| Live policy ingestion | PASS | 15/15 manifest documents succeeded; DB contained 15 Phase 2 documents, 90 Phase 2 chunks, and 90 non-null embeddings. |
| Live RAG Hit@5 eval | FAIL | Hit@5 was 58.3 percent against an 80 percent threshold; fallback accuracy was 100 percent. |
| Live search endpoint | PASS | Authenticated search returned `strong_evidence` for refund and filtered SOP queries; unrelated query returned `no_evidence` fallback. |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | EVAL-01 literal 25-40 case golden set size | Phase 6 | `REQUIREMENTS.md` says 25-40, while Phase 2 roadmap success criterion requires 10+ and Phase 2 context D-11a scopes this phase to 10-15; Phase 6 success criterion explicitly expands to 25-40. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/db/models.py` | RAG document/chunk models | VERIFIED | `PolicyDocument.doc_key` tenant uniqueness, `PolicyChunk.chunk_id` index, `Vector(1024)` present. |
| `src/db/migrations/versions/002_rag_pipeline.py` | RAG migration and indexes | VERIFIED | Code review CR-01 fixed: nullable add, backfill, non-null alter, tenant unique constraint, HNSW index. |
| `src/rag/chunker.py` | Heading-based Markdown chunking | VERIFIED | Stable `doc_key` chunk IDs, sentence-boundary oversized splits, same-section overlap, Chinese character length tests. |
| `src/rag/embedder.py` | DashScope embedding wrapper | VERIFIED | Lazy client initialization, settings-backed defaults, batch clamp to 10, retry loop. |
| `src/repositories/policy_document_repo.py` | Tenant-scoped document persistence | VERIFIED | AsyncSession constructor injection and tenant/doc_key lookup. |
| `src/repositories/policy_chunk_repo.py` | pgvector similarity search | VERIFIED | Cosine similarity, top_k, tenant/doc_type/risk_level filters, document eager-load. |
| `src/rag/ingestion.py` | Ingestion orchestration | VERIFIED | Embeds before DB mutation, checks embedding count, per-document commit/rollback. |
| `scripts/ingest_policies.py` | Ingestion CLI | VERIFIED | 15-doc manifest, `--dry-run`, `--tenant-id`, DB-backed real path. |
| `data/policies/*.md` | Chinese policy corpus | VERIFIED | Exactly 15 Markdown files; dry-run produced chunks for all 15. |
| `src/rag/retriever.py` | Confidence scoring retrieval | VERIFIED | Strong/partial/no-evidence thresholds and evidence mapping. |
| `src/rag/citation_validator.py` | Citation validation | VERIFIED | Deterministic field matching, no LLM dependency. |
| `src/api/routers/search.py` | Authenticated search endpoint | VERIFIED | `Security(get_current_user, scopes=["knowledge:read"])`, tenant scoping, ApiResponse. |
| `eval/golden_rag_queries.jsonl` | Golden RAG cases | VERIFIED | 14 valid JSONL cases with planned Phase 2 category distribution. |
| `scripts/eval_rag_hit_at_5.py` | Hit@5 eval runner | VERIFIED | Loads JSONL, uses `SessionLocal`, production retriever/repository path, threshold exit. |
| `tests/test_search_integration.py` | Endpoint integration coverage | VERIFIED | Seeds deterministic vectors and patches only external embedding call. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/ingest_policies.py` | `src/rag/ingestion.py` | `IngestionService` | VERIFIED | CLI real path constructs `IngestionService`; dry-run avoids DB/API as required. |
| `src/rag/ingestion.py` | `src/rag/chunker.py` | `chunk_markdown` | VERIFIED | Ingestion chunks Markdown before embedding and persistence. |
| `src/rag/ingestion.py` | `src/rag/embedder.py` | `embed_documents` | VERIFIED | Embeddings generated before DB delete/insert. |
| `src/api/routers/search.py` | `src/rag/retriever.py` | `Retriever.search` | VERIFIED | Endpoint delegates query, tenant, top_k, doc_type, risk_level. |
| `src/rag/retriever.py` | `src/repositories/policy_chunk_repo.py` | `search_similar` | VERIFIED | Retriever passes query embedding, tenant_id, threshold, filters. |
| `src/rag/citation_validator.py` | `src/rag/schemas.py` | `RetrievalResult` evidence | VERIFIED | Validator checks cited chunk IDs against retrieval evidence. |
| `scripts/eval_rag_hit_at_5.py` | `eval/golden_rag_queries.jsonl` | JSONL load | VERIFIED | Eval loads cases and computes expected chunk intersections. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/ingest_policies.py` | `DOCUMENT_MANIFEST` / reports | `data/policies/*.md` via `chunk_markdown` | Yes for dry-run chunks | VERIFIED |
| `src/rag/ingestion.py` | `embeddings` | `EmbeddingService.embed_documents` | Yes, live DashScope ingestion generated embeddings | VERIFIED |
| `src/repositories/policy_chunk_repo.py` | `(PolicyChunk, score)` | DB rows with non-null pgvector embeddings | Yes, live DB has 90 embedded Phase 2 chunks | VERIFIED |
| `src/rag/retriever.py` | `evidence` | `PolicyChunkRepository.search_similar` | Yes with seeded vectors; live semantic retrieval needs real ingestion | VERIFIED + HUMAN |
| `src/api/routers/search.py` | `result.model_dump()` | `Retriever.search` | Yes in integration tests | VERIFIED |
| `scripts/eval_rag_hit_at_5.py` | `hit_at_5`, `fallback_acc` | Production retriever over DB | Live score computed: Hit@5 58.3%, fallback accuracy 100.0% | GAP FOUND |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Dry-run chunks all corpus docs without API key or DB | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --dry-run` | 15/15 success; chunk counts 5-9 per doc | PASS |
| Eval CLI is runnable and exposes expected options | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --help` | Shows `--golden-set`, `--threshold`, `--tenant-id` | PASS |
| Golden set shape | JSONL parse/count command | 14 rows; category distribution 5/3/2/2/2; 2 fallback cases | PASS |
| Embedder default config and lazy init | `EmbeddingService()` import check | `text-embedding-v4 1024 10`, client not initialized | PASS |
| Search route registration | FastAPI route inspection | `['/api/v1/search/']` | PASS |
| Live DB embedded data after ingestion | Read-only SQLAlchemy count | `{'phase2_documents': 15, 'phase2_chunks': 90, 'embedded_chunks': 90}` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RAG-01 | 02, 03 | Import Chinese policy docs | SATISFIED | 15 Markdown files and manifest; dry-run chunks all successfully. |
| RAG-02 | 01, 02, 03 | Chunking, embedding, pgvector storage/retrieval | SATISFIED | Code path exists, deterministic tests pass, live DashScope ingestion generated 90 embedded Phase 2 chunks, and live search returned DB-backed evidence. |
| RAG-03 | 01, 02, 03 | Chunk metadata | SATISFIED | Metadata stored across normalized `PolicyDocument` + `PolicyChunk`; evidence returns citation metadata. |
| RAG-04 | 03, 04 | Metadata filtering | SATISFIED | Repository filters tenant_id, doc_type, risk_level and tests tenant isolation/mismatched document tenant. |
| RAG-06 | 04 | No-evidence fallback | SATISFIED | Retriever threshold logic and endpoint tests cover fallback. |
| RAG-07 | 04 | Citation validator | SATISFIED | Deterministic validator checks cited chunk IDs against retrieval evidence. |
| INFR-06 | 02, 03 | CLI/background ingestion, no queue | SATISFIED | CLI scripts implement ingestion/eval; no task queue introduced. |
| EVAL-01 | 05 | Golden set categories | PARTIAL/DEFERRED | Phase 2 has 14 cases across required Phase 2 categories; literal 25-40 expansion is deferred to Phase 6 by roadmap. |
| EVAL-02 | 04, 05 | RAG Hit@5 evaluation | GAP FOUND | Eval script computes Hit@5 through production retriever and threshold exits; live DB-backed score was 58.3 percent, below the 80 percent threshold. |

No orphaned Phase 2 requirement IDs were found: the union of plan frontmatter IDs matches the requested set `EVAL-01, EVAL-02, INFR-06, RAG-01, RAG-02, RAG-03, RAG-04, RAG-06, RAG-07`.

### Code Review / Fix Assessment

Phase 2 code review found 1 critical and 4 warnings. `02-REVIEW-FIX.md` reports all five fixed, and verification confirms the material fixes:

| Review Finding | Verification |
|---|---|
| CR-01 migration duplicate empty doc_key | Fixed by nullable add, unique backfill, then non-null + unique constraint; covered by `tests/test_rag_migration.py`. |
| WR-01 seed path missing doc_key | Fixed in `scripts/seed_demo.py`; orchestrator reported `seed_demo.py --reset` passed. |
| WR-02 tenant mismatch leak | Fixed join condition includes `PolicyDocument.tenant_id == tenant_id`; integration test covers mismatched chunk/document tenant. |
| WR-03 env vars ignored | Fixed settings-backed `EmbeddingService`; `test_embedder.py` covers defaults and clamp. |
| WR-04 internal exception leak | Fixed generic 500 response; `test_error_handlers.py` covers no internal exception text. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tests/test_retriever.py` | 153 | `return []` in test fake | Info | Intentional no-result branch for tenant isolation; not a stub. |
| Several files | various | Empty list initializers/assertions | Info | Runtime accumulators, optional defaults, or test assertions; no hollow user-visible data flow found. |

### Human Verification Required

### 1. Live Embedding Ingestion

**Test:** Set `DASHSCOPE_API_KEY`, run `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id <demo tenant uuid>`.
**Expected:** All 15 manifest documents report `success`; DB has non-null embeddings for Phase 2 doc_keys such as `refund_policy`.
**Why human:** This calls an external embedding provider and writes to the local database.

### 2. Live RAG Hit@5

**Test:** After ingestion, run `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id <demo tenant uuid>`.
**Expected:** Hit@5 and fallback accuracy are both at least 80%; command exits 0.
**Why human:** Requires real embedded pgvector data and external embedding behavior.

### 3. Live Search Endpoint

**Test:** Authenticate as a user with `knowledge:read` and POST representative queries to `/api/v1/search/`, including doc_type and risk_level filters.
**Expected:** Relevant queries return top-5 evidence with citation metadata; unrelated queries return `no_evidence` fallback.
**Why human:** Automated tests use deterministic vectors; live semantic relevance depends on real embeddings.

### Gaps Summary

No implementation gaps were found in the Phase 2 code, wiring, review fixes, or deterministic tests. The phase is not marked `passed` because live external embedding ingestion and real DB-backed RAG scoring were not verified. Current local DB state after seed alone has 0 embedded chunks, so it does not demonstrate the final "chunked, embedded, and retrievable" outcome without the human/live ingestion step.

---

_Verified: 2026-05-10T14:35:47Z_
_Verifier: Claude (gsd-verifier)_
