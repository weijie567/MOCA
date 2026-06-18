# Requirements: MOCA v1.4 RAG Production Ingestion + OCR

**Defined:** 2026-06-18
**Core Value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Milestone Goal:** Add production policy-source ingestion for PDF, DOCX, and image/OCR inputs with durable source-block provenance, while preserving MOCA's existing `PolicyKnowledgeService`, `EvidenceRefV1`, business-tool, memory, approval, and replay boundaries.

## v1.4 Requirements

Committed scope for the active v1.4 milestone. All requirements map to Phase 21.

### Source Parsing

- [x] **SRC-01**: Policy ingestion can route Markdown/plain text, PDF, DOCX, and image policy sources through a parser registry with project-owned parser DTOs rather than parser-library-native objects.
- [x] **SRC-02**: Parser outputs include deterministic block order, visible text, normalized text, block type, parser name/version, source type, warnings, and safe failure codes.
- [x] **SRC-03**: PDF ingestion extracts page-aware text blocks and table/cell metadata when available, and scanned PDF pages can fall back to local OCR without changing the retrieval runtime path.
- [x] **SRC-04**: DOCX ingestion extracts paragraphs, headings, and tables as logical source blocks without fabricating page or bbox metadata.
- [x] **SRC-05**: Image ingestion runs local OCR and emits text, bbox, language, engine/version, timeout/error status, and confidence metadata.

### Source Provenance

- [x] **PROV-01**: The database stores durable `DocumentBlock` or equivalent source-block rows scoped by tenant and policy document, with stable source block IDs, block index, block type, text hash, page number, bbox, table/cell metadata, parser metadata, and OCR metadata.
- [x] **PROV-02**: Every parser/OCR-derived `PolicyChunk` stores ordered source-block provenance so source page, bbox, table row/cell, and OCR confidence metadata can be resolved after retrieval.
- [ ] **PROV-03**: Source-location metadata is exposed only through a verified tenant-scoped provenance lookup that first validates the canonical evidence content/hash.
- [x] **PROV-04**: `DocumentBlock` and source-block IDs cannot act as standalone policy evidence, approval evidence, memory authority, action authority, replay truth, or business facts.

### Chunking & Search Text

- [x] **CHUNK-01**: Block-aware chunking derives `PolicyChunk.content` from faithful visible source text while preserving stable chunk IDs and source-block mappings.
- [x] **CHUNK-02**: Table-aware chunking preserves row/header/cell context for citation text and retrieval search text, including merged-cell or repeated-header cases covered by fixtures.
- [x] **CHUNK-03**: Retrieval-only `PolicyChunk.search_text` may include title, section, table header, and source-context enrichment, but this enrichment never changes `PolicyChunk.content` or `EvidenceRefV1.text_hash`.
- [x] **CHUNK-04**: Re-ingestion changes `PolicyDocument.version` only when canonical citation content or policy semantics metadata changes, not for parser trace or non-content metadata-only changes.

### OCR Quality & Safety

- [x] **OCR-01**: OCR confidence is stored at source-block level and propagated to chunk metadata without replacing `EvidenceRefV1.score` or `KnowledgeSearchResult.best_score`.
- [x] **OCR-02**: Low-confidence OCR blocks are rejected, quarantined, or marked review-needed according to deterministic thresholds covered by high-confidence, low-confidence, noisy, and mixed-language fixtures.
- [x] **SAFE-01**: Ingestion validates source type, extension/signature, file size, page count, image dimensions, decompression/zip-style hazards, parser timeouts, and malformed-file behavior with safe failed reports.
- [x] **SAFE-02**: Parser/OCR text is treated as untrusted external content; hidden prompt-injection text, comments, raw payloads, parser dumps, file bytes, and unsafe paths do not enter prompts, API evidence output, memory, action snapshots, or replay payloads.
- [x] **SAFE-03**: Policy source ingestion rejects business artifacts such as orders, refunds, tickets, screenshots, tool results, or business fact refs so Tool System facts cannot become policy chunks or `EvidenceRefV1`.

### Ingestion Trace & Rollback

- [x] **INGEST-01**: Ingestion records a safe parser/OCR job trace with source checksum, parser/OCR versions, stage/status, warnings, counts, timings, and sanitized failure reasons.
- [x] **INGEST-02**: Parsing, OCR, cleaning, chunking, and embedding complete before the short document write transaction deletes or inserts committed chunks/blocks.
- [x] **INGEST-03**: Failed parse, OCR timeout, embedding mismatch, or DB insert failure leaves the previous committed policy document version, chunks, blocks, and retrieval behavior intact.
- [x] **INGEST-04**: Alembic migration and downgrade coverage creates and removes source-block, ingestion-job, and provenance structures in dependency-safe order without regressing existing Markdown/hybrid retrieval.

### Contract Preservation

- [x] **BOUNDARY-01**: `EvidenceRefV1`, canonical evidence projection, approval snapshots, replay events, and policy citation text hashing remain schema-compatible with v1.3.
- [x] **BOUNDARY-02**: Existing hybrid retrieval behavior remains intact: dense/sparse/fuzzy filters apply before candidate contribution, RRF controls ordering, and normalized confidence controls evidence thresholds.
- [x] **BOUNDARY-03**: Parser/OCR trace and provenance metadata are internal/debug/eval data by default and are excluded from `EvidenceRefV1`, prompts, public API evidence serialization, memory, and action authority.
- [x] **BOUNDARY-04**: Phase 21 implementation does not introduce `MaterialClaim`, semantic verifier, reranker/query rewrite, cross-encoder rerank API, Vespa/OpenSearch, or a full external `SearchBackend`.

## Future Requirements

Tracked but not in the active v1.4 roadmap.

### Phase 22: RAG Context Builder + Hallucination Control

- **HALLU-01**: Introduce runtime `MaterialClaim` objects for claim-level answer validation.
- **HALLU-02**: Add risk-triggered semantic support verification, conflict/freshness routing, refusal/manual-review policy, and faithfulness/citation eval.

### Phase 23: RAG Reranker + Query Rewrite

- **RERANK-01**: Add bounded query rewrite for short, vague, or domain-anchor queries without bypassing tenant/effective-date/scope filters.
- **RERANK-02**: Add a reranker interface, optional cross-encoder/external rerank API, full ranking explanation, retrieval ablation eval, and latency budget coverage.

### Phase RAG-5: Optional External Search Backend

- **BACKEND-01**: Define and validate a full external `SearchBackend` contract only when scale, latency, or ranking-profile complexity outgrows PostgreSQL hybrid retrieval.

### Policy Source Operations

- **SRCOPS-01**: Add user/admin document upload, review, lifecycle, retention, and source-document viewer/highlight UI after backend provenance is stable.
- **SRCOPS-02**: Add asynchronous large-batch ingestion workers only when source volume or OCR latency proves synchronous/admin ingestion insufficient.

## Out of Scope

| Feature | Reason |
|---------|--------|
| `MaterialClaim` and semantic verifier | Deferred to Phase 22; v1.4 owns ingestion/provenance only. |
| Query rewrite, reranker, cross-encoder rerank API, and ranking explanations | Deferred to Phase 23; v1.4 must not change ranking semantics beyond existing v1.3 behavior. |
| Vespa, OpenSearch, or full external `SearchBackend` | Deferred to Phase RAG-5; PostgreSQL hybrid remains the retrieval backend. |
| Cloud OCR, LLM vision parsing, LlamaParse, Textract, Azure OCR, Google Document AI | Adds credentials/network/model dependency and weakens local reproducibility; local parser/OCR stack is sufficient for v1.4. |
| User-facing document CMS or source viewer UI | Backend provenance must be established first; UI belongs to a later source operations milestone. |
| Real external action execution or business data ingestion into RAG | Existing Tool System and approval/action boundaries remain authoritative; policy KB must not absorb business facts. |
| Memory use of parsed/OCR text | Memory remains contextual assistance only and cannot become policy evidence or source-ingestion authority. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 21 | Complete |
| SRC-02 | Phase 21 | Complete |
| SRC-03 | Phase 21 | Complete |
| SRC-04 | Phase 21 | Complete |
| SRC-05 | Phase 21 | Complete |
| PROV-01 | Phase 21 | Complete |
| PROV-02 | Phase 21 | Pending |
| PROV-03 | Phase 21 | Pending |
| PROV-04 | Phase 21 | Complete |
| CHUNK-01 | Phase 21 | Pending |
| CHUNK-02 | Phase 21 | Complete |
| CHUNK-03 | Phase 21 | Pending |
| CHUNK-04 | Phase 21 | Pending |
| OCR-01 | Phase 21 | Complete |
| OCR-02 | Phase 21 | Complete |
| SAFE-01 | Phase 21 | Complete |
| SAFE-02 | Phase 21 | Complete |
| SAFE-03 | Phase 21 | Complete |
| INGEST-01 | Phase 21 | Complete |
| INGEST-02 | Phase 21 | Pending |
| INGEST-03 | Phase 21 | Complete |
| INGEST-04 | Phase 21 | Complete |
| BOUNDARY-01 | Phase 21 | Complete |
| BOUNDARY-02 | Phase 21 | Pending |
| BOUNDARY-03 | Phase 21 | Complete |
| BOUNDARY-04 | Phase 21 | Complete |

**Coverage:**

- v1.4 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

**Wave 0 scaffold status:**

- 21-00 created automated scaffold tests for all 26 requirement IDs.
- Requirement statuses remain Pending until implementation plans remove their owned strict xfails and pass the corresponding acceptance gates.

---
*Requirements defined: 2026-06-18*
*Last updated: 2026-06-18 after 21-00 validation scaffold*
