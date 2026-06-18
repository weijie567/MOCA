# Requirements: MOCA v1.3 RAG Hybrid Retrieval

**Defined:** 2026-06-18
**Core Value:** Retrieve policy evidence with stronger small-scale production quality by combining semantic, sparse keyword, and fuzzy retrieval while preserving MOCA's existing KnowledgeService and EvidenceRefV1 contracts.
**Milestone Goal:** Upgrade the current pgvector-only policy retrieval path into a minimal production hybrid retrieval backend using PostgreSQL + pgvector + PostgreSQL full-text + pg_trgm, without introducing OCR, DocumentBlock, MaterialClaim, semantic verifier, Vespa, or Elasticsearch in this milestone.

## v1.3 Requirements

Committed scope for the active v1.3 milestone. All requirements map to Phase 20.

### Schema & Indexing

- [x] **RAGHYB-01**: `PolicyChunk` stores retrieval-ready `search_text` and a PostgreSQL full-text `search_vector` representation, with Alembic migration coverage and rollback-safe indexes for full-text and pg_trgm search.
- [x] **RAGHYB-02**: Existing pgvector HNSW search remains intact, and new sparse/fuzzy indexes do not change `EvidenceRefV1`, policy document versioning, or existing citation identity semantics.

### Tokenization

- [x] **RAGTOK-01**: Chinese policy content and query text are normalized through an application-level tokenizer with a domain dictionary for refund/support terms such as `仅退款`, `七天无理由`, `二次销售`, `商家举证`, `高价值订单`, `补偿券`, `退款时效`, and `跨境订单`.
- [x] **RAGTOK-02**: Ingestion derives `search_text` from persisted chunk content plus allowed document/section context without mutating the citation text used for `text_hash`.

### Hybrid Retrieval

- [x] **RAGRET-01**: Policy retrieval combines dense pgvector, PostgreSQL full-text sparse retrieval, and pg_trgm fuzzy retrieval into one ranked candidate set.
- [x] **RAGRET-02**: Reciprocal Rank Fusion merges dense/sparse/fuzzy candidates by rank instead of summing incompatible raw scores.
- [x] **RAGRET-03**: The current lightweight lexical rerank may remain as a fallback or tie-breaker, but it is not described as the completed hybrid retrieval implementation.

### Scope & Safety

- [x] **RAGSCOPE-01**: Tenant, effective date, doc type, risk level, and any existing knowledge-scope filters are applied before each retrieval channel contributes candidates.
- [x] **RAGSCOPE-02**: Retrieval preserves existing `PolicyKnowledgeService` behavior for strong/partial/no evidence, no-evidence fallback, and merchant-scope deny-all behavior.

### Trace & Evaluation

- [x] **RAGTRACE-01**: Retrieval produces a minimal internal trace for debugging/eval with `selected_by`, channel ranks, `rrf_score`, and `filter_status`; this trace does not enter prompts or replace `EvidenceRefV1`.
- [x] **RAGEVAL-01**: Tests and eval cover tokenizer output, sparse/fuzzy repository behavior, RRF ordering, effective-date filtering, tenant/scope pre-filtering, Hit@5, and fallback accuracy.

## Future Requirements

Tracked but not in the active v1.3 roadmap.

### Production Ingestion + OCR

- **RAG-OCR-01**: Introduce parser/OCR abstraction for PDF/DOCX/image inputs.
- **RAG-OCR-02**: Persist `DocumentBlock` or equivalent source-block metadata with page, bbox, block type, OCR confidence, table metadata, parser version, and source block references.

### Hallucination Control + Verifier

- **RAG-HALLU-01**: Introduce runtime `MaterialClaim` objects for claim-level answer validation.
- **RAG-HALLU-02**: Add a risk-triggered semantic support verifier and conflict/staleness manual-review routing.
- **RAG-HALLU-03**: Add faithfulness, citation accuracy, unsupported-claim refusal, and business-fact grounding eval.

### External Search Backend

- **RAG-BACKEND-01**: Define a full external `SearchBackend` contract only when shadow testing or replacing Postgres with Vespa/OpenSearch becomes necessary.

## Out of Scope

| Feature | Reason |
|---------|--------|
| OCR / PDF / DOCX / image parsing | Production ingestion is important but belongs to a later RAG ingestion milestone after hybrid retrieval is stable. |
| `DocumentBlock` persistence | Needed for OCR/page-bbox citation, but not required for Phase 20's Postgres hybrid retrieval. |
| `MaterialClaim` and semantic verifier | Belongs to hallucination control after evidence retrieval and context building are stable. |
| Complete external `SearchBackend` interface | Current code only has one Postgres backend; `PolicyKnowledgeService` already hides repository details from Agent nodes. |
| Vespa / Elasticsearch / OpenSearch | Current data scale favors PostgreSQL hybrid; external search stays a future optional backend. |
| Business Data QA inside RAG | Business facts remain Tool System outputs and must not be encoded as policy chunks or `EvidenceRefV1`. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RAGHYB-01 | Phase 20 | Complete |
| RAGHYB-02 | Phase 20 | Complete |
| RAGTOK-01 | Phase 20 | Complete |
| RAGTOK-02 | Phase 20 | Complete |
| RAGRET-01 | Phase 20 | Complete |
| RAGRET-02 | Phase 20 | Complete |
| RAGRET-03 | Phase 20 | Complete |
| RAGSCOPE-01 | Phase 20 | Complete |
| RAGSCOPE-02 | Phase 20 | Complete |
| RAGTRACE-01 | Phase 20 | Complete |
| RAGEVAL-01 | Phase 20 | Complete |

**Coverage:**
- v1.3 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-06-18*
*Last updated: 2026-06-18 after Phase 20 implementation*
