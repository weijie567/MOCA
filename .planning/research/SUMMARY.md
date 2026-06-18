# Project Research Summary

**Project:** MOCA - Merchant Operations Collaborative Agent
**Domain:** v1.4 Phase 21 RAG production ingestion, OCR, and source-block provenance
**Researched:** 2026-06-18
**Confidence:** MEDIUM-HIGH

## Executive Summary

MOCA is an enterprise-style merchant operations agent whose answers must stay evidence-backed, auditable, and safe around high-risk business actions. v1.4 is not a new agent-runtime milestone. It is a production ingestion foundation for real policy source files: PDF, DOCX, and image inputs must become durable, provenance-rich policy chunks that the existing v1.3 hybrid retrieval path can search and cite.

The recommended approach is to extend the offline/admin ingestion plane with a parser registry, typed parser outputs, durable `DocumentBlock` source blocks, table-aware chunking, parser/OCR trace, and atomic reindexing. `PolicyChunk.content` remains the canonical citation text, `PolicyChunk.search_text` remains retrieval-only enrichment, and `EvidenceRefV1` remains unchanged. Page, bbox, table/cell, OCR confidence, and parser metadata are resolved as subordinate provenance after retrieval, not as a new evidence identity.

The highest risks are contract drift and unsafe ingestion: parser/OCR text replacing citation text, `DocumentBlock` becoming a second evidence schema, low-confidence OCR entering policy evidence as if reliable, table semantics being flattened away, raw parser payloads leaking into prompts/API/logs, and Phase 21 absorbing later RAG phases. Mitigate these with strict surface separation, confidence thresholds, tenant-scoped provenance lookup, deterministic identity/version policy, all-or-nothing DB writes, file/security fixtures, and explicit negative checks that defer `MaterialClaim`/semantic verifier to Phase 22, reranker/query rewrite to Phase 23, and external search backend work to Phase RAG-5.

## Key Findings

### Recommended Stack

Keep Phase 21 inside the existing FastAPI, SQLAlchemy/Alembic, PostgreSQL, pgvector, pytest, and `uv` stack. Add deterministic local parser/OCR libraries only where they serve source-block provenance. Do not add a queue, document DB, object store, external search backend, cloud OCR, or LLM parser for this phase.

The stack recommendation is conservative: use project-owned DTOs and adapters so parser backends can change without changing MOCA's evidence contracts. Persist normalized source blocks and safe trace summaries in PostgreSQL; keep raw file bytes, raw parser dumps, and OCR debug payloads out of prompts and public evidence surfaces.

**Core technologies:**
- Existing FastAPI ingestion CLI/service boundary: offline/admin ingestion orchestration - keeps parser/OCR work out of the online retrieval path.
- Existing PostgreSQL + SQLAlchemy + Alembic: source-block, parser trace, OCR confidence, chunk provenance, and migration rollback - matches current policy document/chunk patterns.
- `pdfplumber==0.11.10`: digital PDF text, coordinates, pages, and tables - better provenance fit than basic PDF text extraction.
- `pypdfium2==5.10.1`: scanned-PDF page rendering for OCR fallback - use only to render pages/images for OCR, with PDFium thread-safety handled conservatively.
- `python-docx==1.2.0`: DOCX paragraphs and tables - store logical provenance for DOCX because page/bbox layout is not stable without a renderer.
- Tesseract OCR plus `tesseract-ocr-chi-sim`: local OCR engine for images and scanned PDF pages - fits the local demo and avoids cloud credentials.
- `pytesseract==0.3.13` and `Pillow==12.2.0`: OCR wrapper and image normalization - exposes word boxes, confidence, language, and timeouts.
- Existing Pydantic v2/dataclasses: parser DTOs such as `ParseResult`, `ParsedBlock`, `DocumentBlock`, `SourceBox`, `OCRTrace`, and `ParserTrace` - avoids binding contracts to a parser library.

### Expected Features

Phase 21 should make real policy-source ingestion production-shaped without changing the policy evidence authority model. The product behavior is: ingest a policy source file, parse it into auditable blocks, chunk it without losing provenance, index it through the existing v1.3 retrieval path, and later resolve citations to source locations.

**Must have (table stakes):**
- Parser registry and adapter contract for Markdown/plain text, PDF, DOCX, image, and scanned-PDF OCR paths.
- Durable `DocumentBlock` or equivalent source-block schema with tenant/doc ownership, stable source-block IDs, block type, source order, page, bbox, table/cell metadata, parser version, OCR confidence, and text hash.
- Block-to-chunk provenance so every generated `PolicyChunk` can resolve ordered source blocks and page/bbox/cell metadata.
- Table-aware chunking that preserves row/header/cell context and uses retrieval-only enrichment in `search_text`.
- OCR confidence capture and gating with accepted, degraded/review-needed, and failed/rejected outcomes.
- Parser trace and ingest report with safe warnings, fallback paths, parser/OCR versions, failure modes, and block/chunk counts.
- v1.3 compatibility tests proving `PolicyChunk.content`, `PolicyChunk.search_text`, `EvidenceRefV1`, hybrid retrieval filters, and business-tool boundaries remain unchanged.
- Migration, downgrade, failed-ingestion rollback, raw-payload exclusion, cross-tenant provenance, and source-file security tests.

**Should have (competitive):**
- Evidence identity plus source-location sidecar - richer page/table/cell verification without widening `EvidenceRefV1`.
- Stable source-block hashes across re-ingestion - supports unchanged-region detection and explainable chunk churn.
- Confidence-aware OCR status - makes scanned-policy ingestion honest before Phase 22 adds verifier behavior.
- Partial-ingestion status model - distinguishes success, degraded, skipped, and failed blocks/pages.
- Internal provenance inspection CLI/report - useful for debugging if it stays outside prompt and public evidence contracts.

**Defer (v2+):**
- `MaterialClaim` and semantic support verifier - explicitly Phase 22.
- Reranker, query rewrite, cross-encoder rerank API, ranking explanations, and retrieval ablation work - explicitly Phase 23.
- Vespa/OpenSearch/full external `SearchBackend` abstraction - explicitly Phase RAG-5.
- User-facing source-document viewer/highlight UI - future policy source review UI, not Phase 21.
- Full document-management CMS, upload approval workflow, lifecycle/retention UI, and large async ingestion workers - future operations/scale milestones only after volume proves the need.
- Cloud OCR, LLM vision parsing, LlamaParse, Textract, Azure OCR, Google Document AI, or other external parsing services - not compatible with the local reproducible v1.4 scope.

### Architecture Approach

Extend the ingestion plane before chunks are written; leave the online retrieval and agent contract unchanged by default. The key architecture is `source file -> parser adapter -> ParsedBlock DTOs -> DocumentBlock rows -> block-aware chunks -> PolicyChunk rows with provenance sidecar -> existing hybrid retrieval -> EvidenceRefV1`. Provenance is durable and queryable, but subordinate to canonical policy evidence.

**Major components:**
1. `IngestionService` - orchestrates parse, clean, chunk, embed, and short atomic DB write.
2. `ParserRegistry` and parser adapters - select Markdown/PDF/DOCX/image/OCR implementations and return parser-neutral DTOs.
3. `ParsedBlock` / `DocumentBlock` contract - normalizes source text, page/bbox, table/cell, parser, OCR, confidence, and tenant/doc scope.
4. Deterministic cleaner - normalizes text, whitespace, headers/footers, OCR markers, and warnings without hiding low confidence.
5. `chunk_blocks(...)` - chunks structured blocks, preserves source-block indexes, handles tables, and keeps `chunk_markdown(...)` compatible.
6. `PolicyChunk` provenance sidecar - stores ordered source-block refs plus page/bbox/table summaries without changing `content` or `search_text` semantics.
7. `rag_ingestion_jobs` - records safe parser/OCR/indexing status, warnings, checksums, versions, timings, and failure codes.
8. Verified provenance lookup - resolves locators only after checking evidence content hash and tenant scope.
9. Existing `PolicyKnowledgeService`, `PolicyRetrievalEngine`, approval, memory, replay, and business tools - unchanged consumers of canonical `EvidenceRefV1` and Tool System outputs.

### Critical Pitfalls

1. **Parser/OCR text pollutes citation identity** - keep `PolicyChunk.content`, `PolicyChunk.search_text`, and parser/OCR provenance as separate surfaces; hash only citation content into `EvidenceRefV1`.
2. **`DocumentBlock` becomes a second evidence schema** - make it source-location metadata subordinate to chunks; never let block IDs authorize claims, actions, memory, replay, or snapshots.
3. **Block/chunk identity churn and partial reindex failures** - define deterministic source-block/chunk identity, version only when citation text changes, and parse/chunk/embed before an all-or-nothing DB write.
4. **Tables and OCR produce misleading evidence** - model tables as first-class blocks with row/header/cell metadata, and gate OCR by confidence instead of treating OCR quality as retrieval or policy confidence.
5. **Unsafe raw inputs and traces leak into prompts/API/logs** - validate file type/signature/size/page/image limits, use safe failure codes, store bounded sanitized metadata only, and add forbidden-key tests.
6. **Scope creep into later RAG phases** - Phase 21 must allow parser/OCR/`DocumentBlock` and forbid `MaterialClaim`, semantic verifier, reranker/query rewrite, Vespa/OpenSearch, and full external `SearchBackend`.

## Implications for Roadmap

Based on research, suggested Phase 21 work-package structure:

### Phase 21.1: Schema, Parser Contract, and Scope Guards

**Rationale:** Durable provenance and compatibility guards must exist before format-specific parsing. This also gives the roadmap a hard boundary around what Phase 21 is allowed to change.
**Delivers:** Alembic migration for `document_blocks`, `rag_ingestion_jobs`, `PolicyDocument` source metadata, nullable `PolicyChunk` provenance fields; parser DTOs/protocol; parser registry; Markdown/plain-text adapter; unchanged `EvidenceRefV1` contract tests; negative scope scans forbidding Phase 22/23/RAG-5 deliverables.
**Addresses:** Parser abstraction, durable source-block model, ingestion trace foundation, v1.3 retrieval/evidence compatibility.
**Avoids:** `DocumentBlock` as second evidence schema, migration drift, and accidental `MaterialClaim`/reranker/external backend scope.

### Phase 21.2: Block-Aware Chunking and Atomic Ingestion

**Rationale:** Source-block provenance must be created before chunks; otherwise page/bbox/table/OCR metadata is permanently lost. Atomic ingestion should be proven before expensive parser work lands.
**Delivers:** Deterministic cleaning, `chunk_blocks(...)`, table row/header chunk behavior, `search_text` enrichment rules, embedding text construction, source-block refs on chunks, content-based version bump policy, parse/chunk/embed-before-write flow, and rollback tests for failed parse/chunk/embed/insert.
**Addresses:** Block-to-chunk provenance, table-aware chunking, `PolicyChunk.content` versus `search_text` separation, stable identity, migration/rollback coverage.
**Avoids:** Parser output going straight to Markdown chunking, citation text pollution, partial document deletion, and version churn from parser metadata-only changes.

### Phase 21.3: PDF, DOCX, Image, and OCR Adapters

**Rationale:** Format adapters should implement the already-tested parser contract rather than define architecture through library-specific objects.
**Delivers:** `pdfplumber` PDF parser, `pypdfium2` scanned-PDF renderer, `python-docx` adapter, Pillow/Tesseract OCR adapter, `chi_sim+eng` OCR configuration, OCR confidence thresholds, source-file validation, safe parser timeouts, and fixtures for text PDF, scanned PDF, DOCX tables, standalone image OCR, low-confidence OCR, malformed files, and rotated/page-coordinate cases.
**Addresses:** PDF/DOCX/image intake, page/bbox metadata, table/cell provenance, OCR confidence capture/gating, parser warnings and fallback paths.
**Avoids:** Low-confidence OCR as normal evidence, fake DOCX page/bbox data, non-canonical coordinate systems, untrusted file assumptions, and raw parser object leakage.

### Phase 21.4: Provenance Lookup, Trace Reporting, and Boundary Regression

**Rationale:** Provenance should be exposed only after the persisted data path is stable, and only through a side path that verifies canonical evidence first.
**Delivers:** Tenant-scoped provenance lookup by evidence keys, evidence hash verification before locator expansion, safe ingestion report/trace projections, internal debug/CLI provenance output if needed, prompt/API serialization exclusions, business-fact ingestion rejection, and v1.3 hybrid retrieval regression coverage.
**Addresses:** Page/bbox/cell citation metadata, parser trace, source-block tenant scope, policy-vs-business boundary, and compatibility with `PolicyKnowledgeService`.
**Avoids:** Block ID cross-tenant leaks, parser trace becoming user-facing authority, source text influencing tools/memory/actions, and business facts entering policy evidence.

### Phase 21.5: Acceptance, Downgrade, and Security Gate

**Rationale:** Phase 21 creates foundational schema and parser boundaries; it should not close until rollback, downgrade, and adversarial input behavior are verified.
**Delivers:** Migration upgrade/downgrade/reupgrade tests; failed-ingestion rollback for document version, chunks, blocks, and chunk refs; oversized/spoofed/malformed/zip-style DOCX hazard tests; hidden prompt-injection fixtures; forbidden raw-payload key tests; cross-tenant provenance negative tests; final scope gate for Phase 22/23/RAG-5 deferrals.
**Addresses:** Migration/rollback/security tests, raw payload controls, indirect prompt injection, tenant isolation, and "looks done but is not" verification.
**Avoids:** Partial parser state, unsafe file ingestion, prompt-visible parser internals, and roadmap closure without downgrade confidence.

### Phase Ordering Rationale

- Start with contracts and schema because `DocumentBlock`, parser DTOs, and scope guards determine every downstream parser and test.
- Build block-aware chunking before format adapters so PDF/DOCX/OCR parsers have one project-owned target contract instead of shaping chunk logic ad hoc.
- Add parser/OCR libraries only after Markdown/plain-text proves no regression in existing evidence identity.
- Expose provenance through a separate verified side path after chunks and blocks are consistently linked.
- End with rollback/security gates because the highest risk is not parsing success; it is evidence, tenant, prompt, and migration safety.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 21.3:** Parser/OCR adapters need targeted official-doc checks during implementation, especially PDF table extraction, Tesseract `chi_sim+eng` runtime packaging, confidence interpretation, coordinate mapping, and `pypdfium2` rendering/thread-safety behavior.
- **Phase 21.5:** Security gate should validate exact file-size/page-count/image-dimension/DOCX-zip limits and parser isolation choices against OWASP guidance and the local Docker/runtime constraints.
- **Future Phase 22:** Needs separate research for `MaterialClaim`, semantic support verifier, and hallucination-control behavior. Do not pre-design this inside Phase 21.
- **Future Phase 23:** Needs separate research for reranker/query rewrite, cross-encoder/external rerank API, latency budgets, and ranking explanation.
- **Future Phase RAG-5:** Needs separate research before introducing Vespa/OpenSearch or a full external `SearchBackend`.

Phases with standard patterns (skip research-phase unless implementation uncovers surprises):
- **Phase 21.1:** Schema/model/parser-contract work follows established local SQLAlchemy/Alembic/Pydantic and evidence-contract patterns.
- **Phase 21.2:** Transaction, versioning, chunk persistence, and search-text separation are already documented by v1.3 code and tests.
- **Phase 21.4:** Verified provenance lookup can follow existing `PolicyKnowledgeService` content verification and Phase 20 trace-exclusion patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Library recommendations are backed by current package docs and project constraints. Main uncertainty is OCR quality on Chinese scans, PDF table edge cases, and exact runtime limits. |
| Features | HIGH | Feature scope is anchored in `.planning/PROJECT.md`, v1.3 deferrals, and current MOCA evidence/business boundaries. |
| Architecture | HIGH | Architecture maps directly to existing ingestion, chunking, repository, retrieval, and `EvidenceRefV1` contracts. |
| Pitfalls | HIGH | Contract/security pitfalls are well supported by current code patterns and OWASP guidance; parser-engine-specific failure modes remain medium until fixtures are implemented. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- OCR confidence thresholds: define concrete accepted/degraded/rejected cutoffs in Phase 21 planning and prove them with noisy and high-confidence fixtures.
- DOCX page/bbox expectations: keep DOCX logical-only for Phase 21; do not fake pagination or bbox without a real renderer.
- Complex PDF tables: start with `pdfplumber`; escalate to heavier table tooling only if Phase 21 fixtures prove a blocker, and record the dependency/license decision.
- SourceBox coordinate contract: specify origin, units, page dimensions, rotation, and fallback behavior before exposing bbox metadata.
- Parser sandbox and file limits: choose concrete size/page/dimension/timeout limits in implementation based on Docker demo constraints.
- Provenance storage shape: JSONB ordered block refs are acceptable for v1.4 if chunk-centric lookup is enough; use a join table only if block-centric visual review becomes a real requirement.

## Sources

### Primary (HIGH confidence)

- `.planning/PROJECT.md` - v1.4 scope, Phase 21 active requirements, current milestone goals, and explicit Phase 22/23/RAG-5 deferrals.
- `.planning/research/STACK.md` - parser/OCR technology recommendations, version pins, alternatives, and stack fit.
- `.planning/research/FEATURES.md` - table stakes, differentiators, anti-features, MVP definition, and feature dependencies.
- `.planning/research/ARCHITECTURE.md` - ingestion-plane architecture, component boundaries, data flow, build order, and test strategy.
- `.planning/research/PITFALLS.md` - critical pitfalls, security traps, integration gotchas, recovery strategies, and verification gates.
- Current MOCA code references cited by research: `src/rag/ingestion.py`, `src/rag/chunker.py`, `src/db/models.py`, `src/knowledge/schemas.py`, `src/knowledge/service.py`, `src/knowledge/retrieval.py`, and existing ingestion/knowledge tests.
- Official/library docs cited by stack research: `pdfplumber`, `pypdfium2`, `python-docx`, `pytesseract`, Pillow, Tesseract installation/traineddata docs, and PyMuPDF docs for comparison/license caution.
- OWASP File Upload Cheat Sheet, OWASP Unrestricted File Upload, OWASP LLM Prompt Injection Prevention Cheat Sheet, OWASP AI Agent Security Cheat Sheet, and OWASP Top 10 for LLM Applications - source-file, parser, and indirect prompt-injection risk controls.

### Secondary (MEDIUM confidence)

- `docs/rag-architecture-spec.md` - target-state RAG architecture and DocumentBlock/OCR rationale; useful for direction but not all target-state design is implemented.
- `.planning/milestones/v1.3-ROADMAP.md` and Phase 20 artifacts - shipped v1.3 retrieval constraints and deferral ownership; high confidence for MOCA history, medium where they describe future target architecture.

### Tertiary (LOW confidence)

- None used for roadmap-critical recommendations.

---
*Research completed: 2026-06-18*
*Ready for roadmap: yes*
