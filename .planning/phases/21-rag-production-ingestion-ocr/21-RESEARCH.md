# Phase 21: RAG Production Ingestion + OCR - Research

**Researched:** 2026-06-18 [VERIFIED: system date]
**Domain:** Production RAG ingestion, parser/OCR provenance, PostgreSQL hybrid retrieval compatibility [VERIFIED: .planning/ROADMAP.md]
**Confidence:** MEDIUM-HIGH [VERIFIED: codebase inspection + official docs + package registry]

## User Constraints

No Phase 21 `CONTEXT.md` exists, so there are no additional locked discussion decisions to copy verbatim. [VERIFIED: `gsd-sdk query init.phase-op 21` returned `has_context: false`]

Planner must treat work packages 21.1-21.5 as implementation slices inside Phase 21, not separate roadmap phases. [VERIFIED: .planning/ROADMAP.md]

Planner must use this sequence: 21.1 schema/parser contract/scope guards; 21.2 block-aware chunking/atomic ingestion; 21.3 PDF/DOCX/image/OCR adapters; 21.4 provenance lookup/trace reporting/boundary regression; 21.5 acceptance/downgrade/security gate. [VERIFIED: .planning/ROADMAP.md]

Planner must define concrete OCR confidence thresholds, file-size/page/image limits, parser timeouts, `SourceBox` coordinate semantics, and migration downgrade strategy during Phase 21 planning. [VERIFIED: .planning/ROADMAP.md]

Planner must preserve the explicit boundary: do not introduce `MaterialClaim`, semantic verifier, reranker/query rewrite, cross-encoder/external rerank API, Vespa/OpenSearch, or a full external `SearchBackend`. [VERIFIED: .planning/ROADMAP.md]

Planner must address all 26 Phase 21 requirement IDs: SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, PROV-01, PROV-02, PROV-03, PROV-04, CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, OCR-01, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-01, INGEST-02, INGEST-03, INGEST-04, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04. [VERIFIED: .planning/REQUIREMENTS.md]

## Summary

Phase 21 should extend the existing maintainer ingestion plane, not the online retrieval contract: parse real source files into project-owned DTOs, persist durable source blocks and job traces, derive block-aware chunks, then feed the existing v1.3 `PolicyKnowledgeService` and hybrid retrieval path. [VERIFIED: src/rag/ingestion.py + src/knowledge/service.py + .planning/ROADMAP.md]

The central rule is surface separation: `PolicyChunk.content` remains faithful visible citation text, `PolicyChunk.search_text` remains retrieval-only enrichment, `EvidenceRefV1` remains unchanged, and source-block/page/bbox/table/OCR metadata is exposed only through a verified tenant-scoped provenance lookup after content/hash validation. [VERIFIED: src/knowledge/schemas.py + tests/knowledge/test_text_hash.py + tests/knowledge/test_service.py + .planning/REQUIREMENTS.md]

The highest planning risks are partial reindexing, parser/OCR trace leakage, low-confidence OCR being treated as policy confidence, table context loss, unsafe file handling, and scope creep into Phase 22/23/RAG-5. [VERIFIED: .planning/research/SUMMARY.md + OWASP File Upload Cheat Sheet + OWASP LLM Prompt Injection Prevention Cheat Sheet]

**Primary recommendation:** Plan five slices exactly as the roadmap says, starting with schema/DTO/scope guards, then block-aware chunking and atomic ingestion, then adapters, then provenance lookup, then migration/security acceptance gates. [VERIFIED: .planning/ROADMAP.md + .planning/research/SUMMARY.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Source-file validation and parser/OCR execution | API / Backend | OS runtime | Maintainer ingestion is orchestrated by backend service/CLI code, while native OCR depends on system `tesseract`. [VERIFIED: scripts/ingest_policies.py + local `tesseract --version`] |
| Parser DTOs and parser registry | API / Backend | - | Parser-library-native objects must not become MOCA contracts; project-owned DTOs belong in `src/rag`. [VERIFIED: .planning/REQUIREMENTS.md] |
| Durable source blocks and ingestion jobs | Database / Storage | API / Backend | `DocumentBlock` and job traces are persistent provenance and audit state scoped by tenant/document. [VERIFIED: .planning/REQUIREMENTS.md + docs/rag-architecture-spec.md] |
| Block-aware chunking and embeddings | API / Backend | Database / Storage | Current ingestion computes chunks/embeddings before DB writes, then persists `PolicyChunk` rows. [VERIFIED: src/rag/ingestion.py] |
| Hybrid retrieval | API / Backend | Database / Storage | `PolicyRetrievalEngine` calls repository dense/sparse/fuzzy SQL and returns canonical evidence refs. [VERIFIED: src/knowledge/retrieval.py + src/repositories/policy_chunk_repo.py] |
| Provenance lookup | API / Backend | Database / Storage | Existing verified evidence content lookup already rechecks tenant and hash before returning text; provenance lookup should extend that side path. [VERIFIED: src/knowledge/service.py + tests/knowledge/test_service.py] |
| Public evidence contract | API / Backend | Agent runtime | `EvidenceRefV1` is canonical and consumed by knowledge, approval, replay, and agent code. [VERIFIED: docs/contract-spec.md + src/knowledge/schemas.py + rg] |
| Prompt/action/memory boundaries | Agent runtime | API / Backend | Parser/OCR metadata must remain internal by default and cannot become prompts, memory, action authority, or replay truth. [VERIFIED: .planning/REQUIREMENTS.md + tests/agent/test_memory_evidence_boundary.py + docs/contract-spec.md] |

## Project Constraints (from CLAUDE.md / AGENTS.md)

- `docs/contract-spec.md` is the only normative MOCA contract source; `docs/rag-architecture-spec.md` is target-state guidance and loses on conflicts. [VERIFIED: CLAUDE.md + AGENTS.md + docs/rag-architecture-spec.md]
- Phase implementation may diverge from the target spec only with an explicit recorded decision: spec wrong means update spec through review; MVP compromise means annotate spec and `.planning/`. [VERIFIED: CLAUDE.md + AGENTS.md]
- Phase-level planning and larger changes use GSD native review first, then independent Codex cross-review; small single-file fixes do not need the full workflow. [VERIFIED: CLAUDE.md + AGENTS.md]
- Plan repair that adds/deletes/reorders tasks, spans at least three files, changes waves/dependencies, or needs source reread is classified as large and must be handed to Codex execution per the project workflow. [VERIFIED: CLAUDE.md + AGENTS.md]
- `study_plan/` documentation defaults to Chinese, but Phase 21 research under `.planning/` is not constrained to Chinese by that rule. [VERIFIED: CLAUDE.md + AGENTS.md]

<phase_requirements>

## Phase Requirements

| ID | Description | Recommended Slice | Research Support |
|----|-------------|-------------------|------------------|
| SRC-01 | Route Markdown/plain text, PDF, DOCX, and image sources through a parser registry with project-owned DTOs. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.3 | Define `ParserRegistry`, `ParseResult`, `ParsedBlock`, `SourceBox`, `ParserWarning`, and adapters under `src/rag/parsers/`. [VERIFIED: docs/rag-architecture-spec.md + codebase inspection] |
| SRC-02 | Parser outputs include deterministic order, visible/normalized text, block type, parser name/version, source type, warnings, and safe failure codes. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1 | DTO tests should freeze field names and deterministic sort order before adapters land. [VERIFIED: tests/test_chunker.py pattern + .planning/REQUIREMENTS.md] |
| SRC-03 | PDF ingestion extracts page-aware text/table metadata and scanned pages fall back to local OCR without retrieval-runtime changes. [VERIFIED: .planning/REQUIREMENTS.md] | 21.3 | Use `pdfplumber` for machine-generated PDF text/tables and `pypdfium2` to render scanned pages for OCR. [CITED: https://github.com/jsvine/pdfplumber] [CITED: https://pypdfium2.readthedocs.io/en/v4/python_api.html] |
| SRC-04 | DOCX ingestion extracts paragraphs, headings, and tables as logical blocks without fake page/bbox metadata. [VERIFIED: .planning/REQUIREMENTS.md] | 21.3 | `python-docx` exposes document-order paragraphs/tables via `iter_inner_content`; it does not provide stable rendered page/bbox layout. [CITED: https://python-docx.readthedocs.io/en/latest/api/document.html] |
| SRC-05 | Image ingestion runs local OCR and emits text, bbox, language, engine/version, timeout/error status, and confidence metadata. [VERIFIED: .planning/REQUIREMENTS.md] | 21.3 | `pytesseract.image_to_data` exposes bounding boxes/confidence and supports timeout handling; local `tesseract` is installed but `chi_sim` is missing. [CITED: https://pypi.org/project/pytesseract/] [VERIFIED: local `tesseract --list-langs`] |
| PROV-01 | Store durable source-block rows scoped by tenant/document with stable IDs and parser/OCR/table metadata. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1 | Add `DocumentBlock` SQLAlchemy model and migration after current `PolicyDocument`/`PolicyChunk` tables. [VERIFIED: src/db/models.py + src/db/migrations/versions] |
| PROV-02 | Every parser/OCR-derived `PolicyChunk` stores ordered source-block provenance. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2 | Add ordered JSONB refs on `PolicyChunk` for v1.4 chunk-centric provenance lookup. [RESOLVED: planner revision 2026-06-18] |
| PROV-03 | Source-location metadata is exposed only through verified tenant-scoped provenance lookup. [VERIFIED: .planning/REQUIREMENTS.md] | 21.4 | Mirror `get_verified_evidence_contents`: validate tenant, unique key, and `evidence_text_hash(content)` before returning locators. [VERIFIED: src/knowledge/service.py + tests/knowledge/test_service.py] |
| PROV-04 | `DocumentBlock` IDs cannot act as policy evidence, approval evidence, memory authority, action authority, replay truth, or business facts. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.4, 21.5 | Add boundary tests scanning memory/action/approval/replay/tool paths for block IDs or parser metadata as authority. [VERIFIED: tests/agent/test_memory_evidence_boundary.py + tests/approvals/test_snapshots.py] |
| CHUNK-01 | Block-aware chunking derives `PolicyChunk.content` from faithful visible text while preserving stable chunk IDs and source-block mappings. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2 | Extend `src/rag/chunker.py` with `chunk_blocks` while keeping `chunk_markdown` compatibility. [VERIFIED: src/rag/chunker.py + tests/test_chunker.py] |
| CHUNK-02 | Table-aware chunking preserves row/header/cell context including merged-cell/repeated-header fixtures. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2, 21.3 | Keep table blocks atomic by default; split large tables by row groups and repeat headers in visible citation text. [VERIFIED: docs/rag-architecture-spec.md] |
| CHUNK-03 | `PolicyChunk.search_text` may include retrieval-only enrichment but never changes `PolicyChunk.content` or `EvidenceRefV1.text_hash`. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2 | Existing search-text tests prove context enrichment does not mutate content; extend those tests for table/header/source context. [VERIFIED: tests/rag/test_search_text.py] |
| CHUNK-04 | Re-ingestion bumps `PolicyDocument.version` only when canonical citation content or policy semantics metadata changes. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2 | Existing ingestion tests bump version on changed content and keep same-content version stable; extend comparison to ignore parser trace-only changes. [VERIFIED: tests/test_ingestion.py] |
| OCR-01 | OCR confidence is stored at source-block level and propagated to chunk metadata without replacing retrieval score fields. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.2, 21.3 | Keep OCR confidence in block/chunk metadata and keep `EvidenceRefV1.score`/`KnowledgeSearchResult.best_score` normalized retrieval confidence. [VERIFIED: src/knowledge/retrieval.py + tests/knowledge/test_hybrid_retrieval.py] |
| OCR-02 | Low-confidence OCR blocks are rejected, quarantined, or marked review-needed by deterministic thresholds. [VERIFIED: .planning/REQUIREMENTS.md] | 21.3, 21.5 | Recommended thresholds are listed in Assumptions Log and must be locked in planning with fixtures. [ASSUMED] |
| SAFE-01 | Validate source type, extension/signature, file size, page count, image dimensions, decompression hazards, timeouts, and malformed files with safe failed reports. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.3, 21.5 | OWASP recommends allowlisted extensions plus content-type/signature checks, and Pillow exposes decompression-bomb warnings/errors. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html] [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] |
| SAFE-02 | Parser/OCR text is untrusted; hidden prompt injection, raw payloads, parser dumps, bytes, and unsafe paths do not enter prompts/API/memory/actions/replay. [VERIFIED: .planning/REQUIREMENTS.md] | 21.4, 21.5 | OWASP identifies retrieved/fetched RAG documents as untrusted content needing screening and least privilege controls. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html] |
| SAFE-03 | Reject business artifacts so Tool System facts cannot become policy chunks or `EvidenceRefV1`. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.5 | Contract spec separates BusinessToolService `ToolResultV2` from policy `EvidenceRefV1`; tests already guard memory/evidence boundaries. [VERIFIED: docs/contract-spec.md + tests/agent/test_memory_evidence_boundary.py] |
| INGEST-01 | Record safe parser/OCR job trace with checksum, versions, stage/status, warnings, counts, timings, and sanitized failure reasons. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.4 | Add `rag_ingestion_jobs` or equivalent job log with bounded safe fields; target spec recommends job log before a full ingestion event model. [VERIFIED: docs/rag-architecture-spec.md] |
| INGEST-02 | Parse, OCR, clean, chunk, and embed before short document write transaction deletes/inserts committed chunks/blocks. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2 | Current `IngestionService` already generates embeddings before DB delete/insert and commit. [VERIFIED: src/rag/ingestion.py] |
| INGEST-03 | Failed parse, OCR timeout, embedding mismatch, or DB insert failure leaves prior committed document version, chunks, blocks, and retrieval intact. [VERIFIED: .planning/REQUIREMENTS.md] | 21.2, 21.5 | Existing tests verify rollback on insert failure and embedding count mismatch failure; extend to blocks/jobs/OCR timeout. [VERIFIED: tests/test_ingestion.py] |
| INGEST-04 | Alembic migration/downgrade creates/removes source-block, job, and provenance structures safely without Markdown/hybrid regression. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.5 | Existing migration tests assert column/index order and forbidden scope; extend with upgrade/downgrade/reupgrade and reverse dependency order. [VERIFIED: tests/test_rag_migration.py + tests/knowledge/test_hybrid_schema.py] |
| BOUNDARY-01 | `EvidenceRefV1`, canonical projection, approval snapshots, replay events, and text hashing remain v1.3-compatible. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.4, 21.5 | Keep `src/knowledge/schemas.py` unchanged except additive internal DTOs elsewhere; run evidence projection/hash/snapshot tests. [VERIFIED: src/knowledge/schemas.py + tests/knowledge/test_evidence_projection.py] |
| BOUNDARY-02 | Existing hybrid retrieval behavior remains intact: filters before contribution, RRF ordering, normalized confidence thresholds. [VERIFIED: .planning/REQUIREMENTS.md] | 21.4, 21.5 | Current `PolicyRetrievalEngine` implements dense/sparse/fuzzy channels, RRF, and confidence separate from RRF score. [VERIFIED: src/knowledge/retrieval.py + tests/knowledge/test_hybrid_retrieval.py] |
| BOUNDARY-03 | Parser/OCR trace and provenance are internal/debug/eval data by default and excluded from evidence serialization, prompts, memory, and action authority. [VERIFIED: .planning/REQUIREMENTS.md] | 21.4, 21.5 | Current hybrid trace fields stay internal to hits and are excluded from `EvidenceRefV1`; extend same pattern to provenance. [VERIFIED: tests/knowledge/test_hybrid_retrieval.py] |
| BOUNDARY-04 | Phase 21 does not introduce Phase 22/23/RAG-5 deliverables. [VERIFIED: .planning/REQUIREMENTS.md] | 21.1, 21.5 | Add scope-guard tests that fail on `MaterialClaim`, semantic verifier, query rewrite, reranker API, Vespa/OpenSearch, or full `SearchBackend`. [VERIFIED: tests/knowledge/test_hybrid_schema.py pattern + .planning/REQUIREMENTS.md] |

</phase_requirements>

## Implementation Approach And Sequencing

### Slice 21.1 - Schema, Parser Contract, Scope Guards

Create parser-neutral DTOs in `src/rag/parsers/base.py`, a registry in `src/rag/parsers/registry.py`, Markdown/plain-text adapters, `DocumentBlock` and `RagIngestionJob` SQLAlchemy models, repositories, and Alembic migration `015_rag_production_ingestion_ocr.py`. [VERIFIED: docs/rag-architecture-spec.md + current migration numbering]

Add compatibility tests before parser adapters: `EvidenceRefV1` golden projection unchanged, `PolicyChunk.content/search_text` semantics unchanged, and scope-guard tests forbidding Phase 22/23/RAG-5 names. [VERIFIED: tests/knowledge/test_evidence_projection.py + tests/rag/test_search_text.py + tests/knowledge/test_hybrid_schema.py]

### Slice 21.2 - Block-Aware Chunking And Atomic Ingestion

Add `chunk_blocks(...)` alongside `chunk_markdown(...)`; do not remove the Markdown path because scripts and tests depend on it. [VERIFIED: scripts/ingest_policies.py + tests/test_chunker.py]

Refactor `IngestionService.ingest_document` into parse/clean/chunk/embed preflight and a short locked write transaction that updates the document, blocks, chunks, chunk provenance, and job status atomically. [VERIFIED: src/rag/ingestion.py + tests/test_ingestion.py]

Use content-derived comparison for version bumps: changes to canonical citation content or policy semantics metadata bump `PolicyDocument.version`; parser version, timings, warnings, and OCR trace-only changes do not. [VERIFIED: .planning/REQUIREMENTS.md] [ASSUMED: exact semantics-metadata allowlist]

### Slice 21.3 - PDF, DOCX, Image, OCR Adapters

Implement `PdfParser`, `DocxParser`, `ImageOcrParser`, and scanned-PDF fallback as adapters that return the same DTO contract rather than leaking `pdfplumber`, `python-docx`, `pypdfium2`, or `pytesseract` objects. [VERIFIED: .planning/REQUIREMENTS.md + docs/rag-architecture-spec.md]

Use `pdfplumber` only for machine-generated PDF text, object geometry, and table extraction; use OCR fallback when text extraction is absent or below a deterministic text-density threshold. [CITED: https://github.com/jsvine/pdfplumber] [ASSUMED: text-density threshold]

Render scanned PDF pages with `pypdfium2` in a conservative process or mutex-isolated path, because its docs warn that expensive PDFium work should be parallelized with processes rather than unsafe threads. [CITED: https://pypdfium2.readthedocs.io/en/v4/python_api.html]

Use `python-docx` for DOCX paragraph/table logical order and explicitly set page/bbox fields to null for DOCX blocks. [CITED: https://python-docx.readthedocs.io/en/latest/api/document.html] [VERIFIED: .planning/REQUIREMENTS.md]

Use local `tesseract` via `pytesseract` for OCR; require `chi_sim+eng` language availability preflight for Chinese policy OCR acceptance. [CITED: https://pypi.org/project/pytesseract/] [VERIFIED: local `tesseract --list-langs`] [RESOLVED: planner revision 2026-06-18]

### Slice 21.4 - Provenance Lookup, Trace Reporting, Boundary Regression

Add `PolicyKnowledgeService.get_verified_evidence_provenance(...)` or equivalent side-path API that first reuses content/hash validation, then returns block/page/bbox/table/OCR metadata for valid refs only. [VERIFIED: src/knowledge/service.py + tests/knowledge/test_service.py]

Expose ingestion reports and provenance as maintainer/debug outputs only; do not add fields to `EvidenceRefV1`, approval snapshot evidence projections, replay evidence payloads, or prompt evidence refs. [VERIFIED: docs/contract-spec.md + src/knowledge/schemas.py + tests/approvals/test_snapshots.py]

### Slice 21.5 - Acceptance, Downgrade, Security Gate

Run migration static tests, disposable DB upgrade/downgrade/reupgrade tests when DB is available, parser fixture tests, rollback tests, and scope/security scans before phase closure. [VERIFIED: tests/conversation/test_models.py + tests/knowledge/test_hybrid_schema.py + .planning/config.json]

Add adversarial fixtures for spoofed extension/signature, oversize files, DOCX zip hazards, malformed PDFs/images, OCR timeout, hidden prompt injection text, business-artifact screenshots, cross-tenant provenance, and low-confidence OCR quarantine. [VERIFIED: .planning/REQUIREMENTS.md + OWASP File Upload Cheat Sheet + OWASP LLM Prompt Injection Prevention Cheat Sheet]

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python | 3.12.13 under `uv run`; project requires `>=3.12`. [VERIFIED: local `uv run python --version` + pyproject.toml] | Runtime | Matches repo `.python-version` and project metadata. [VERIFIED: .python-version + pyproject.toml] |
| uv | 0.11.2 [VERIFIED: local `uv --version`] | Dependency/test runner | Existing repo commands use `uv run`. [VERIFIED: scripts/ingest_policies.py docstring + test commands in state] |
| FastAPI | 0.136.1 installed; `>=0.115` declared. [VERIFIED: importlib.metadata + pyproject.toml] | API runtime | Existing app stack. [VERIFIED: pyproject.toml + src/api/main.py] |
| SQLAlchemy | 2.0.49 installed; `>=2.0` declared. [VERIFIED: importlib.metadata + pyproject.toml] | ORM | Existing models/repositories use SQLAlchemy async. [VERIFIED: src/db/models.py + src/repositories/policy_chunk_repo.py] |
| Alembic | 1.18.4 installed; `>=1.13` declared. [VERIFIED: local `uv run alembic --version` + pyproject.toml] | Migrations | Existing migration chain lives under `src/db/migrations/versions`. [VERIFIED: src/db/migrations/versions] |
| Pydantic | 2.13.4 installed. [VERIFIED: importlib.metadata] | DTO/schema validation | Existing knowledge contracts are Pydantic models. [VERIFIED: src/knowledge/schemas.py] |
| PostgreSQL + pgvector + pg_trgm | pgvector 0.4.2 installed; DB service not probed. [VERIFIED: importlib.metadata + local command audit] | Storage and hybrid retrieval | Existing policy chunks use `Vector(1024)`, generated tsvector, and trigram index migration. [VERIFIED: src/db/models.py + src/db/migrations/versions/014_rag_hybrid_retrieval.py] |
| pytest / pytest-asyncio | pytest 9.0.3, pytest-asyncio 1.3.0 installed. [VERIFIED: local `uv run pytest --version` + importlib.metadata] | Validation | Existing tests are pytest/asyncio. [VERIFIED: tests/test_ingestion.py + tests/knowledge/test_hybrid_retrieval.py] |

### Parser/OCR Additions

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| pdfplumber | 0.11.10, uploaded 2026-06-15. [VERIFIED: `pip index versions` + PyPI JSON] | Machine-generated PDF text/object/table extraction | Use for digital PDFs with extractable text and table/object geometry. [CITED: https://github.com/jsvine/pdfplumber] |
| pypdfium2 | 5.10.1, uploaded 2026-06-15. [VERIFIED: `pip index versions` + PyPI JSON] | PDF page rendering for scanned-page OCR fallback | Use to rasterize PDF pages for OCR; guard concurrency with process/mutex strategy. [CITED: https://pypdfium2.readthedocs.io/en/v4/python_api.html] |
| python-docx | 1.2.0, uploaded 2025-06-16. [VERIFIED: `pip index versions` + PyPI JSON] | DOCX paragraph/table logical extraction | Use for DOCX logical blocks; do not claim page/bbox. [CITED: https://python-docx.readthedocs.io/en/latest/api/document.html] |
| pytesseract | 0.3.13, uploaded 2024-08-16. [VERIFIED: `pip index versions` + PyPI JSON] | Python wrapper for local Tesseract OCR | Use `image_to_data` for text boxes/confidence and `timeout` for safe termination. [CITED: https://pypi.org/project/pytesseract/] |
| Pillow | 12.2.0, uploaded 2026-04-01. [VERIFIED: `pip index versions` + PyPI JSON] | Image open/normalize/dimension checks | Use for image validation and decompression-bomb protections. [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] |
| filetype | 1.2.0, uploaded 2022-11-02. [VERIFIED: `pip index versions` + PyPI JSON] | Lightweight magic-number type detection | Use as one layer with extension/content-type validation; not as sole security check. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html] |
| Tesseract OCR | 5.5.0 installed locally; `chi_sim` not installed. [VERIFIED: local `tesseract --version` + `tesseract --list-langs`] | Native OCR engine | Install or preflight `chi_sim` before Chinese OCR acceptance. [CITED: https://tesseract-ocr.github.io/tessdoc/Data-Files.html] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pdfplumber` + `pypdfium2` | PyMuPDF | Strong PDF extraction/rendering alternative, but Phase 21 already needs separable PDF extraction and scanned-page rendering with project-owned DTOs; avoid swapping unless fixtures prove pdfplumber/pypdfium2 insufficient. [ASSUMED] |
| Local Tesseract OCR | Cloud OCR or LLM vision parsing | Requirements explicitly exclude cloud OCR and LLM parsing services for v1.4. [VERIFIED: .planning/REQUIREMENTS.md] |
| JSONB chunk source refs | `policy_chunk_source_blocks` join table | JSONB is simpler for chunk-centric provenance; use join table if planner requires block-centric review queries or strong relational constraints. [VERIFIED: .planning/research/SUMMARY.md] |
| Existing PostgreSQL hybrid | Vespa/OpenSearch/SearchBackend | Phase RAG-5 owns external backend work; Phase 21 must preserve existing PostgreSQL hybrid retrieval. [VERIFIED: .planning/ROADMAP.md + docs/rag-architecture-spec.md] |

**Installation:**

```bash
uv add pdfplumber==0.11.10 pypdfium2==5.10.1 python-docx==1.2.0 pytesseract==0.3.13 Pillow==12.2.0 filetype==1.2.0
```

**Native dependency preflight:**

```bash
tesseract --version
tesseract --list-langs | grep -E '^(chi_sim|eng)$'
```

The local machine has `tesseract 5.5.0` with `eng`, `osd`, and `snum`, but not `chi_sim`. [VERIFIED: local `tesseract --list-langs`]

## Architecture Patterns

### System Architecture Diagram

```text
Maintainer CLI / backend call
  -> Source guard
       -> extension + signature + size + page/image limits
       -> reject business artifacts and unsafe paths
  -> ParserRegistry
       -> markdown/plain adapter
       -> pdf adapter -> digital blocks OR scanned-page render -> OCR adapter
       -> docx adapter
       -> image OCR adapter
  -> Project DTOs
       -> ParseResult -> ParsedBlock[] -> warnings/failure codes/timings
  -> Cleaner and OCR gate
       -> visible text stays visible text
       -> normalized text and metadata stay internal
       -> low confidence -> reject/quarantine/review-needed
  -> Block-aware chunker
       -> ChunkResult + ordered source_block refs
       -> content = citation text
       -> search_text = retrieval enrichment
  -> Embedding preflight
       -> embed all chunk texts
       -> fail before DB mutation on mismatch/timeout
  -> Short DB transaction
       -> lock PolicyDocument by tenant/doc_key
       -> update doc version only for canonical content/semantic metadata changes
       -> replace DocumentBlock rows
       -> replace PolicyChunk rows + provenance metadata
       -> write safe RagIngestionJob result
  -> Existing retrieval
       -> dense/sparse/fuzzy SQL filters
       -> RRF ordering
       -> normalized confidence
       -> EvidenceRefV1 only
  -> Optional maintainer provenance lookup
       -> tenant + hash verification
       -> return source blocks/page/bbox/table/OCR metadata
```

The diagram preserves the current code's parse/embed-before-write pattern and keeps retrieval output as `EvidenceRefV1`. [VERIFIED: src/rag/ingestion.py + src/knowledge/retrieval.py + src/knowledge/schemas.py]

### Recommended Project Structure

```text
src/rag/
├── ingestion.py              # orchestrates parse/chunk/embed/write [VERIFIED: existing file]
├── chunker.py                # keep chunk_markdown; add chunk_blocks [VERIFIED: existing file]
├── cleaning.py               # text/control-char/header/footer/OCR cleanup [VERIFIED: docs/rag-architecture-spec.md]
├── limits.py                 # file/page/image/OCR timeout constants [VERIFIED: .planning/ROADMAP.md]
├── parsers/
│   ├── base.py               # DTOs/protocols/failure codes [VERIFIED: .planning/REQUIREMENTS.md]
│   ├── registry.py           # extension/source_type routing [VERIFIED: .planning/REQUIREMENTS.md]
│   ├── markdown.py           # Markdown/plain text adapter [VERIFIED: current src/rag/ingestion.py]
│   ├── pdf.py                # pdfplumber + scanned fallback [CITED: https://github.com/jsvine/pdfplumber]
│   ├── docx.py               # python-docx logical blocks [CITED: https://python-docx.readthedocs.io/en/latest/api/document.html]
│   ├── image.py              # Pillow validation + OCR adapter [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html]
│   └── ocr.py                # pytesseract wrapper and confidence gating [CITED: https://pypi.org/project/pytesseract/]
src/repositories/
├── document_block_repo.py    # block persistence and lookup [VERIFIED: repository pattern in src/repositories/policy_chunk_repo.py]
├── rag_ingestion_job_repo.py # job trace persistence [VERIFIED: docs/rag-architecture-spec.md]
└── policy_chunk_repo.py      # extend with provenance lookup joins [VERIFIED: existing file]
tests/rag/
├── test_parser_contract.py
├── test_block_chunker.py
├── test_pdf_parser.py
├── test_docx_parser.py
├── test_ocr_parser.py
└── test_ingestion_safety.py
tests/knowledge/
├── test_provenance_lookup.py
└── test_phase21_boundaries.py
```

### Pattern 1: Project-Owned Parser DTOs

**What:** Parser adapters must emit MOCA DTOs, not parser-library-native rows. [VERIFIED: .planning/REQUIREMENTS.md]

**When to use:** Use for every source type before chunking or persistence. [VERIFIED: .planning/REQUIREMENTS.md]

**Example:**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class SourceBox:
    page_number: int | None
    x0: float
    top: float
    x1: float
    bottom: float
    unit: Literal["pdf_point", "pixel"]
    origin: Literal["top_left"] = "top_left"
    page_width: float | None = None
    page_height: float | None = None
    rotation_degrees: int | None = None


@dataclass(frozen=True)
class ParsedBlock:
    block_index: int
    block_type: Literal["heading", "paragraph", "table", "image", "list", "header", "footer"]
    visible_text: str
    normalized_text: str
    source_type: str
    parser_name: str
    parser_version: str
    source_box: SourceBox | None = None
    table_metadata: dict = field(default_factory=dict)
    ocr_metadata: dict = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
```

The `SourceBox` recommendation uses top-left coordinates because pdfplumber exposes `top`/`bottom` distances from page top and Tesseract data uses image left/top boxes. [CITED: https://github.com/jsvine/pdfplumber] [CITED: https://pypi.org/project/pytesseract/] [ASSUMED: one normalized SourceBox DTO]

### Pattern 2: Parse/Embed Before Write, Then Atomic Replacement

**What:** Parser/OCR/chunking/embedding must finish before deleting or inserting committed policy rows. [VERIFIED: .planning/REQUIREMENTS.md]

**When to use:** Use for all source types, including Markdown. [VERIFIED: .planning/REQUIREMENTS.md]

**Example:**

```python
parse_result = parser_registry.parse(source)
blocks = clean_blocks(parse_result.blocks)
chunks = chunk_blocks(blocks, doc_key=doc_key)
embeddings = await embedder.embed_documents([chunk.embedding_text for chunk in chunks])
if len(embeddings) != len(chunks):
    return failed_report("EMBEDDING_COUNT_MISMATCH")

async with short_write_transaction(session):
    doc = await doc_repo.get_by_doc_key_for_update(doc_key, tenant_id)
    await block_repo.replace_for_document(doc.id, blocks)
    await chunk_repo.replace_for_document(doc.id, chunks, embeddings)
    await job_repo.mark_success(job_id, safe_counts_and_timings)
```

This mirrors existing ingestion, which embeds before DB delete/insert and rolls back on failures. [VERIFIED: src/rag/ingestion.py + tests/test_ingestion.py]

### Pattern 3: Provenance Lookup Is A Side Path

**What:** Resolve page/bbox/table/OCR metadata only after `EvidenceRefV1` content/hash verification. [VERIFIED: .planning/REQUIREMENTS.md]

**When to use:** Use for maintainer trace/debug or source review, not for ordinary policy evidence serialization. [VERIFIED: .planning/REQUIREMENTS.md]

**Example:**

```python
async def get_verified_evidence_provenance(tenant_id: str, evidence_refs: list[EvidenceRefV1]) -> dict[str, list[dict]]:
    verified_text = await self.get_verified_evidence_contents(tenant_id=tenant_id, evidence_refs=evidence_refs)
    if not verified_text:
        return {}
    return await self.retriever.get_provenance_by_evidence_ids(
        tenant_id=UUID(tenant_id),
        evidence_ids=list(verified_text),
    )
```

The hash-checking step should reuse the existing `get_verified_evidence_contents` behavior. [VERIFIED: src/knowledge/service.py + tests/knowledge/test_service.py]

### Anti-Patterns to Avoid

- **Expanding `EvidenceRefV1` for provenance:** This would break the canonical cross-layer evidence contract. [VERIFIED: docs/contract-spec.md + tests/knowledge/test_evidence_projection.py]
- **Persisting parser-library objects:** This would bind MOCA contracts to replaceable parser implementations. [VERIFIED: .planning/REQUIREMENTS.md]
- **Running OCR during retrieval:** Scanned-page OCR belongs to ingestion; retrieval must keep v1.3 dense/sparse/fuzzy behavior. [VERIFIED: .planning/ROADMAP.md + src/knowledge/retrieval.py]
- **Treating OCR confidence as evidence confidence:** OCR confidence is source quality metadata, while `EvidenceRefV1.score` is retrieval confidence. [VERIFIED: .planning/REQUIREMENTS.md + tests/knowledge/test_hybrid_retrieval.py]
- **Fake DOCX page/bbox:** DOCX adapter should produce logical blocks only unless a renderer is introduced. [VERIFIED: .planning/REQUIREMENTS.md + python-docx docs]
- **Letting parser/OCR text enter memory/action/replay authority:** Parsed text is untrusted external content and must stay out of authority-bearing surfaces by default. [VERIFIED: .planning/REQUIREMENTS.md + OWASP LLM Prompt Injection Prevention Cheat Sheet]

## Current Codebase Patterns And Closest Files

| Area | Existing Pattern | Closest Files To Edit/Create |
|------|------------------|------------------------------|
| Maintainer ingestion | CLI loads manifest, supports dry run, resolves tenant, then calls `IngestionService`. [VERIFIED: scripts/ingest_policies.py] | Edit `scripts/ingest_policies.py`; add manifest fields for `source_type`, limits, parser report output. [VERIFIED: codebase inspection] |
| Ingestion atomicity | Reads UTF-8 file, chunks Markdown, embeds texts, locks document row, deletes/reinserts chunks, commits or rolls back. [VERIFIED: src/rag/ingestion.py] | Refactor `src/rag/ingestion.py`; add parser preflight and block persistence. [VERIFIED: codebase inspection] |
| Chunking | `chunk_markdown` returns frozen `ChunkResult` with stable IDs and section/part indexes. [VERIFIED: src/rag/chunker.py] | Add `ParsedBlock`-aware chunking to `src/rag/chunker.py` or `src/rag/chunking.py`. [VERIFIED: docs/rag-architecture-spec.md] |
| Search text | Search text includes title/section/doc_type/risk/content tokens without mutating content. [VERIFIED: src/rag/search_text.py + tests/rag/test_search_text.py] | Extend `build_policy_chunk_search_text(...)` to accept heading path/table context as keyword-only optional inputs. [VERIFIED: current function pattern] |
| Policy schema | `PolicyDocument` and `PolicyChunk` are SQLAlchemy models with tenant/doc/version/content/chunk/search fields. [VERIFIED: src/db/models.py] | Add `DocumentBlock`, `RagIngestionJob`, and additive nullable metadata columns on `PolicyChunk`. [VERIFIED: .planning/REQUIREMENTS.md] |
| Migrations | Migrations are numbered in `src/db/migrations/versions`; Phase 20 head is `014_rag_hybrid_retrieval`. [VERIFIED: src/db/migrations/versions] | Create `015_rag_production_ingestion_ocr.py` with `down_revision="014_rag_hybrid_retrieval"`. [VERIFIED: migration chain] |
| Repositories | `PolicyChunkRepository` owns SQL search methods and content lookup. [VERIFIED: src/repositories/policy_chunk_repo.py] | Add `DocumentBlockRepository`; extend `PolicyChunkRepository` with verified provenance lookup. [VERIFIED: repository pattern] |
| Knowledge service | `PolicyKnowledgeService` validates merchant scope and has verified content lookup by evidence refs. [VERIFIED: src/knowledge/service.py] | Add provenance side path without changing `search(...)` result schema. [VERIFIED: .planning/REQUIREMENTS.md] |
| Retrieval | `PolicyRetrievalEngine` fuses dense/sparse/fuzzy channels with RRF and returns `EvidenceRefV1`. [VERIFIED: src/knowledge/retrieval.py] | Avoid changes except metadata-safe lookup support. [VERIFIED: BOUNDARY-02] |
| Boundary tests | Existing tests guard EvidenceRef projection, memory/evidence boundary, hybrid trace exclusion, and migration scope. [VERIFIED: tests/knowledge/test_evidence_projection.py + tests/agent/test_memory_evidence_boundary.py + tests/knowledge/test_hybrid_retrieval.py + tests/knowledge/test_hybrid_schema.py] | Extend these with Phase 21 negative assertions. [VERIFIED: test patterns] |

## Migration, Downgrade, And Rollback Strategy

Use additive migration first: create `rag_ingestion_jobs`, create `document_blocks`, add nullable `source_block_refs_json`, `page_start`, `page_end`, `bbox_json`, `ocr_metadata_json`, `parser_metadata_json`, `chunk_hash`, and `content_hash` or equivalent fields to `policy_chunks`. [VERIFIED: .planning/REQUIREMENTS.md] [ASSUMED: exact column list]

Keep `policy_documents` and `policy_chunks` as the retrieval source of truth; do not replace existing policy tables in Phase 21. [VERIFIED: .planning/ROADMAP.md + src/db/models.py]

Backfill existing Markdown chunks with empty source-block refs or synthetic Markdown source blocks only if provenance lookup needs to work for legacy chunks; otherwise return no provenance for legacy chunks while preserving retrieval. [ASSUMED]

Downgrade should drop indexes/FKs first, then provenance columns, then `document_blocks`, then `rag_ingestion_jobs`, leaving `policy_documents`, `policy_chunks`, `search_text`, `search_vector`, and v1.3 hybrid indexes intact. [VERIFIED: tests/knowledge/test_hybrid_schema.py pattern + migration dependency reasoning]

Runtime rollback should never delete committed chunks before parse/OCR/chunk/embed success; DB insert failure must roll back document version, blocks, chunks, and job status in the same transaction. [VERIFIED: src/rag/ingestion.py + tests/test_ingestion.py + .planning/REQUIREMENTS.md]

Add static migration tests and, when a disposable PostgreSQL URL is available, round-trip `uv run alembic upgrade head`, `uv run alembic downgrade 014_rag_hybrid_retrieval`, and `uv run alembic upgrade head`. [VERIFIED: tests/conversation/test_models.py pattern + local alembic availability]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Existing runtime DB may contain `policy_documents` and `policy_chunks`; this session verified schema/code but did not inspect a live DB because `psql`/`pg_isready` are not available locally. [VERIFIED: src/db/models.py + local command audit] | Planner should include preflight SQL counts for policy docs/chunks and a disposable DB migration round trip. [VERIFIED: migration test patterns] |
| Live service config | No external parser/OCR service config was found in repo; Phase 21 recommendation uses local parser/OCR libraries. [VERIFIED: rg + pyproject.toml] | Add `tesseract` language-data preflight; no cloud credentials should be introduced. [VERIFIED: .planning/REQUIREMENTS.md + local `tesseract --list-langs`] |
| OS-registered state | Local `tesseract 5.5.0` exists, but `chi_sim` language data is missing. [VERIFIED: local `tesseract --version` + `tesseract --list-langs`] | Install `chi_sim.traineddata` or make Chinese OCR tests skip/fail with explicit missing dependency. [CITED: https://tesseract-ocr.github.io/tessdoc/Data-Files.html] |
| Secrets/env vars | Phase 21 local OCR/parser stack requires no new API keys; existing embedding/OpenAI-compatible config remains outside this research. [VERIFIED: pyproject.toml + .planning/REQUIREMENTS.md] | Do not add cloud OCR/LLM parser secrets; keep embedding config unchanged. [VERIFIED: .planning/REQUIREMENTS.md] |
| Build artifacts | New Python dependencies require `pyproject.toml` and `uv.lock` update during implementation; no package install was performed during research. [VERIFIED: pyproject.toml + git status] | Planner should assign dependency lock update in Slice 21.3 or 21.1 depending on parser-contract tests. [ASSUMED] |

## Common Pitfalls

### Pitfall 1: Parser/OCR Metadata Changes Evidence Identity

**What goes wrong:** Parser version, OCR timings, bbox, or warnings cause `EvidenceRefV1.text_hash` or `PolicyDocument.version` churn. [VERIFIED: .planning/REQUIREMENTS.md]

**Why it happens:** Parser metadata and visible citation content are stored in the same surface. [VERIFIED: .planning/research/SUMMARY.md]

**How to avoid:** Hash only canonical visible citation text; store parser/OCR metadata in blocks/jobs/provenance metadata. [VERIFIED: docs/contract-spec.md + tests/knowledge/test_text_hash.py]

**Warning signs:** Snapshot/hash golden tests change, same visible content bumps policy version, or OCR confidence appears in `EvidenceRefV1`. [VERIFIED: tests/knowledge/test_evidence_projection.py + .planning/REQUIREMENTS.md]

### Pitfall 2: Partial Reindex Deletes Good Chunks

**What goes wrong:** A parse/OCR/embed failure deletes previous chunks or increments document version without usable replacement chunks. [VERIFIED: .planning/REQUIREMENTS.md]

**Why it happens:** DB mutation starts before parser/OCR/embed preflight completes. [VERIFIED: src/rag/ingestion.py comment documents current safe pattern]

**How to avoid:** Complete parse, OCR, cleaning, chunking, and embedding before the locked write transaction. [VERIFIED: src/rag/ingestion.py + .planning/REQUIREMENTS.md]

**Warning signs:** Tests cannot assert previous version/content after simulated insert failure. [VERIFIED: tests/test_ingestion.py]

### Pitfall 3: Low-Confidence OCR Becomes High-Confidence Evidence

**What goes wrong:** Bad OCR text is indexed and later retrieved with high retrieval confidence. [VERIFIED: .planning/REQUIREMENTS.md]

**Why it happens:** OCR quality confidence is confused with retrieval score and no quarantine/review path exists. [VERIFIED: .planning/research/SUMMARY.md]

**How to avoid:** Gate OCR blocks before chunking and store OCR confidence only as source quality metadata. [VERIFIED: .planning/REQUIREMENTS.md]

**Warning signs:** Low-confidence OCR fixtures create normal `PolicyChunk` rows or `EvidenceRefV1.score` contains OCR confidence. [VERIFIED: .planning/REQUIREMENTS.md]

### Pitfall 4: Table Context Is Flattened Away

**What goes wrong:** Retrieved citation text loses header/row/cell meaning, so a table cell becomes misleading evidence. [VERIFIED: .planning/REQUIREMENTS.md]

**Why it happens:** Tables are treated like raw paragraph text. [VERIFIED: docs/rag-architecture-spec.md]

**How to avoid:** Model table blocks with header rows, row index, cell text, cell bbox when available, and repeat headers in row-group chunks. [VERIFIED: docs/rag-architecture-spec.md]

**Warning signs:** A table fixture can retrieve a value without its governing row/header labels. [VERIFIED: .planning/REQUIREMENTS.md]

### Pitfall 5: Hidden Prompt Injection Leaks Into Agent Authority

**What goes wrong:** A policy PDF/image contains instructions that affect prompts, memory, actions, or replay payloads. [VERIFIED: OWASP LLM Prompt Injection Prevention Cheat Sheet + .planning/REQUIREMENTS.md]

**Why it happens:** Retrieved documents and file contents are treated as trusted instructions rather than untrusted content. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html]

**How to avoid:** Keep parser/OCR traces internal, expose only canonical evidence refs, use least-privilege tool paths, and add forbidden-key prompt/API/replay tests. [VERIFIED: docs/contract-spec.md + OWASP LLM Prompt Injection Prevention Cheat Sheet]

**Warning signs:** Raw parser payloads, hidden text, local file paths, or source bytes appear in prompt snapshots, memory rows, action snapshots, or replay payloads. [VERIFIED: .planning/REQUIREMENTS.md]

### Pitfall 6: Phase 21 Absorbs Later RAG Phases

**What goes wrong:** Planning adds claim verifier, query rewrite, reranker, external backend, or source UI. [VERIFIED: .planning/ROADMAP.md]

**Why it happens:** `docs/rag-architecture-spec.md` contains target-state RAG-3/RAG-4/RAG-5 guidance that is not Phase 21 scope. [VERIFIED: docs/rag-architecture-spec.md]

**How to avoid:** Add negative tests and explicit out-of-scope checklist in Slice 21.1 and Slice 21.5. [VERIFIED: tests/knowledge/test_hybrid_schema.py pattern]

**Warning signs:** New classes or modules named `MaterialClaim`, `SemanticVerifier`, `SearchBackend`, `Reranker`, `QueryRewrite`, `Vespa`, or `OpenSearch`. [VERIFIED: .planning/REQUIREMENTS.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Machine-generated PDF geometry/tables | A custom PDF parser | `pdfplumber` adapter | It exposes chars, object geometry, pages, and table extraction for digital PDFs. [CITED: https://github.com/jsvine/pdfplumber] |
| Scanned PDF rendering | Manual PDF rasterization | `pypdfium2` adapter | It provides page rasterization to bitmaps with DPI/rotation controls. [CITED: https://pypdfium2.readthedocs.io/en/v4/python_api.html] |
| OCR subprocess wrapper | Raw `subprocess.run(["tesseract", ...])` | `pytesseract` wrapper | It supports OCR functions, box/confidence output, version/language checks, and timeout termination. [CITED: https://pypi.org/project/pytesseract/] |
| DOCX parsing | Manual ZIP/XML traversal | `python-docx` adapter | It provides document-order paragraph/table iteration. [CITED: https://python-docx.readthedocs.io/en/latest/api/document.html] |
| Image decompression safeguards | Manual image byte decoding | Pillow with `MAX_IMAGE_PIXELS` and decompression-bomb handling | Pillow has documented warning/error behavior for decompression bombs. [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] |
| File upload security | Extension-only checks | Allowlist extension + content-type + signature + size/decompression limits | OWASP warns content type and signature are insufficient alone and recommends layered controls. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html] |
| Evidence hashing | New hash format | Existing `evidence_text_hash` | Contract freezes NFC/newline/strip/no-case-fold behavior. [VERIFIED: docs/contract-spec.md + tests/knowledge/test_text_hash.py] |
| Hybrid ranking | New reranker/query rewrite | Existing dense/sparse/fuzzy + RRF | Phase 21 must preserve v1.3 retrieval semantics and defer reranker/query rewrite. [VERIFIED: .planning/ROADMAP.md + tests/knowledge/test_hybrid_retrieval.py] |

**Key insight:** Custom parsing is less risky when hidden behind project-owned DTOs, but custom file/OCR/PDF security and custom evidence contracts are high risk because they affect trust, tenant isolation, and rollback behavior. [VERIFIED: .planning/REQUIREMENTS.md + OWASP File Upload Cheat Sheet + docs/contract-spec.md]

## Concrete Planning Decisions To Lock

| Decision | Recommended Default | Confidence |
|----------|---------------------|------------|
| OCR accepted threshold | Accept block when average valid word confidence is `>= 80`; mark review-needed for `55-79`; reject below `55` or empty text. [RESOLVED: planner revision 2026-06-18] | HIGH for v1.4 acceptance criteria. |
| OCR timeout | `15s/page` for OCR pages/images and `30s` parser timeout in synchronous maintainer ingestion. [RESOLVED: planner revision 2026-06-18] | MEDIUM until local fixture timing is measured. |
| PDF page limit | 50 pages per source in Phase 21 default. [ASSUMED] | LOW until product fixtures confirm size. |
| PDF/DOCX/image file limit | 20 MB per source file. [RESOLVED: planner revision 2026-06-18] | MEDIUM until maintainer corpus size is known. |
| Image limit | Maximum image dimension `8000x8000`; treat Pillow decompression-bomb warning as hard failure. [RESOLVED: planner revision 2026-06-18] [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] | MEDIUM for bomb handling. |
| SourceBox coordinates | Persist `(page_number, x0, top, x1, bottom, unit, origin="top_left", page_width, page_height, rotation_degrees)`; use `pdf_point` for PDF extraction and `pixel` for OCR images. [ASSUMED] [CITED: https://github.com/jsvine/pdfplumber] [CITED: https://pypi.org/project/pytesseract/] | MEDIUM. |
| DOCX bbox/page | Store `null` page/bbox and logical block order only. [VERIFIED: .planning/REQUIREMENTS.md + python-docx docs] | HIGH. |
| Chunk provenance storage | Use ordered JSONB refs in `PolicyChunk.source_block_refs_json` for v1.4. [RESOLVED: planner revision 2026-06-18] | HIGH for v1.4 chunk-centric provenance lookup. |
| Migration downgrade | Downgrade to `014_rag_hybrid_retrieval` removes Phase 21 provenance/job structures but preserves v1.3 retrieval tables/columns. [VERIFIED: migration chain + .planning/ROADMAP.md] | HIGH for strategy, MEDIUM until tested. |

## Code Examples

### Verified Content Before Provenance

```python
# Pattern source: src/knowledge/service.py get_verified_evidence_contents [VERIFIED: codebase]
contents = await retriever.get_contents_by_evidence_keys(tenant_id=tenant_uuid, keys=keys)
if evidence_text_hash(content) == ref.text_hash and ref.tenant_id == tenant_id:
    verified[ref.evidence_id] = content
```

Use the same validation gate before returning source-block provenance. [VERIFIED: src/knowledge/service.py + tests/knowledge/test_service.py]

### Search Text Enrichment Without Content Mutation

```python
# Pattern source: src/rag/search_text.py and tests/rag/test_search_text.py [VERIFIED: codebase]
search_text = build_policy_chunk_search_text(
    title=title,
    section=section,
    content=chunk.content,
    doc_type=doc_type,
    risk_level=risk_level,
)
```

Extend the function with optional `heading_path`, `table_headers`, and `source_context` but keep `chunk.content` unchanged. [VERIFIED: tests/rag/test_search_text.py] [ASSUMED: exact optional parameter names]

### Migration Static Contract Test

```python
# Pattern source: tests/knowledge/test_hybrid_schema.py [VERIFIED: codebase]
source = Path("src/db/migrations/versions/015_rag_production_ingestion_ocr.py").read_text(encoding="utf-8")
assert 'down_revision: str | None = "014_rag_hybrid_retrieval"' in source
assert "document_blocks" in source
assert "rag_ingestion_jobs" in source
assert source.index("drop_constraint") < source.index("drop_table")
```

Use static migration assertions plus disposable DB round-trip when possible. [VERIFIED: tests/conversation/test_models.py + tests/knowledge/test_hybrid_schema.py]

## State Of The Art

| Old Approach | Current Approach For Phase 21 | When Changed | Impact |
|--------------|--------------------------------|--------------|--------|
| Markdown-only ingestion with `chunk_markdown`. [VERIFIED: src/rag/ingestion.py] | Parser registry and `ParsedBlock` DTOs for Markdown/plain/PDF/DOCX/image/OCR. [VERIFIED: .planning/REQUIREMENTS.md] | Phase 21. [VERIFIED: .planning/ROADMAP.md] | Real source files become auditable without changing retrieval output. [VERIFIED: .planning/ROADMAP.md] |
| `PolicyChunk.content` plus embedding only. [VERIFIED: src/db/models.py] | `PolicyChunk.content` remains citation text, while source-block refs and parser/OCR metadata become sidecar provenance. [VERIFIED: .planning/REQUIREMENTS.md] | Phase 21. [VERIFIED: .planning/ROADMAP.md] | Page/bbox/table/OCR trace can be resolved after evidence hash validation. [VERIFIED: .planning/REQUIREMENTS.md] |
| Dense-only initial RAG. [VERIFIED: src/db/migrations/versions/002_rag_pipeline.py] | v1.3 hybrid dense/sparse/fuzzy with RRF and normalized confidence stays intact. [VERIFIED: src/knowledge/retrieval.py + tests/knowledge/test_hybrid_retrieval.py] | Phase 20 shipped 2026-06-18. [VERIFIED: .planning/STATE.md] | Phase 21 should not replan retrieval ranking. [VERIFIED: .planning/ROADMAP.md] |
| Parser trace not persisted. [VERIFIED: src/rag/ingestion.py] | Safe `rag_ingestion_jobs` trace with checksums, stage/status, warnings, counts, timings, and sanitized errors. [VERIFIED: .planning/REQUIREMENTS.md] | Phase 21. [VERIFIED: .planning/ROADMAP.md] | Maintainers can diagnose ingestion without raw payload leakage. [VERIFIED: .planning/REQUIREMENTS.md] |

**Deprecated/outdated:**

- Treating `pdfplumber` as sufficient for scanned PDFs is outdated for Phase 21 because its own README says it works best on machine-generated PDFs. [CITED: https://github.com/jsvine/pdfplumber]
- Treating extension checks as sufficient file safety is unsafe because OWASP recommends layered validation and says signature checks should not stand alone. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html]
- Treating citation membership as semantic claim support is incorrect because `docs/contract-spec.md` explicitly defers semantic/support validation. [VERIFIED: docs/contract-spec.md]

## Out-Of-Scope Guardrails

| Deferred Area | Guardrail |
|---------------|-----------|
| Phase 22 hallucination control | Do not add `MaterialClaim`, semantic support verifier, claim-to-evidence support scoring, conflict/freshness answer policy, or faithfulness verifier. [VERIFIED: .planning/REQUIREMENTS.md + docs/rag-architecture-spec.md] |
| Phase 23 reranker/query rewrite | Do not add query rewrite, reranker interface, cross-encoder, external rerank API, ranking explanation surface, or ablation eval beyond v1.3 trace regression. [VERIFIED: .planning/REQUIREMENTS.md + docs/rag-architecture-spec.md] |
| Phase RAG-5 backend | Do not add Vespa/OpenSearch, full `SearchBackend`, shadow index, or backend abstraction beyond current repository/retriever interfaces. [VERIFIED: .planning/REQUIREMENTS.md + docs/rag-architecture-spec.md] |
| Source operations/UI | Do not add user/admin document upload UI, CMS lifecycle, retention UI, or source-document viewer/highlight UI. [VERIFIED: .planning/REQUIREMENTS.md] |
| Async scale workers | Do not add queues/large-batch OCR workers unless explicitly replanned after Phase 21. [VERIFIED: .planning/REQUIREMENTS.md] |
| Cloud/LLM parsing | Do not add Textract, Azure OCR, Google Document AI, LlamaParse, or LLM vision parser. [VERIFIED: .planning/REQUIREMENTS.md] |
| Business data ingestion | Do not ingest orders/refunds/tickets/tool results/screenshots as policy chunks. [VERIFIED: .planning/REQUIREMENTS.md + docs/contract-spec.md] |

## Open Questions (RESOLVED)

1. **What exact OCR thresholds should become locked acceptance criteria?** [RESOLVED]
   - What we know: Requirements demand deterministic thresholds and fixtures. [VERIFIED: .planning/REQUIREMENTS.md]
   - Decision: v1.4 locks `accepted` at average confidence `>= 80`, `review_needed` at `55-79`, and `rejected` at `< 55` or empty text. Fixtures must cover 80, 79, 55, 54, and empty text boundaries. [RESOLVED: planner revision 2026-06-18]

2. **Should legacy Markdown chunks get synthetic `DocumentBlock` rows?** [RESOLVED]
   - What we know: Existing Markdown ingestion has no source-block layer. [VERIFIED: src/rag/ingestion.py]
   - Decision: Markdown and plain-text ingestion executed through the Phase 21 parser registry must emit synthetic source blocks. Existing pre-Phase-21 rows may remain retrieval-compatible; newly ingested legacy formats get `DocumentBlock` provenance. [RESOLVED: planner revision 2026-06-18]

3. **Is the planner allowed to require installing `chi_sim` on developer/CI machines?** [RESOLVED]
   - What we know: Local Tesseract lacks `chi_sim`, and Chinese policy OCR needs Simplified Chinese traineddata. [VERIFIED: local `tesseract --list-langs`] [CITED: https://tesseract-ocr.github.io/tessdoc/Data-Files.html]
   - Decision: `chi_sim+eng` runtime preflight is required. When either language is absent, OCR-dependent tests must skip or fail with an explicit missing-language message rather than silently passing. [RESOLVED: planner revision 2026-06-18]

4. **Should chunk provenance be JSONB or relational join table?** [RESOLVED]
   - What we know: Requirement only says ordered provenance must be stored. [VERIFIED: .planning/REQUIREMENTS.md]
   - Decision: Use JSONB ordered source-block refs on `PolicyChunk` for v1.4. A relational join table remains out of scope unless a later block-centric review/query phase is explicitly planned. [RESOLVED: planner revision 2026-06-18]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| uv | Running tests and dependency management | yes [VERIFIED: local command] | 0.11.2 | none needed |
| Python via uv | App/tests | yes [VERIFIED: local command] | 3.12.13 | none needed |
| pytest | Validation | yes [VERIFIED: local command] | 9.0.3 | none needed |
| Alembic | Migration tests | yes [VERIFIED: local command] | 1.18.4 | static migration tests if DB unavailable |
| Docker | Disposable DB option | yes [VERIFIED: local command] | 29.4.2 | static tests if Docker daemon unavailable |
| psql / pg_isready | DB probing | no [VERIFIED: local command audit] | - | use SQLAlchemy/Alembic tests through configured DB or Docker |
| Tesseract | OCR | yes [VERIFIED: local command] | 5.5.0 | skip/fail OCR tests if absent |
| Tesseract `chi_sim` data | Chinese OCR | no [VERIFIED: local `tesseract --list-langs`] | - | install traineddata or mark Chinese OCR unavailable |
| pdfplumber/pypdfium2/python-docx/pytesseract/Pillow/filetype | Parser adapters | not installed in project deps [VERIFIED: pyproject.toml] | see Standard Stack | add dependencies in implementation |

**Missing dependencies with no fallback:**

- Chinese OCR acceptance requires `chi_sim` traineddata or equivalent installed language data. [VERIFIED: local `tesseract --list-langs`] [CITED: https://tesseract-ocr.github.io/tessdoc/Data-Files.html]

**Missing dependencies with fallback:**

- `psql`/`pg_isready` are missing; planner can use Alembic/SQLAlchemy with configured DB or Docker for round-trip migration tests. [VERIFIED: local command audit + Docker availability]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 [VERIFIED: local command + importlib.metadata] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_service.py -q` [VERIFIED: existing test files] |
| Full suite command | `uv run pytest -q --tb=short` and `uv run ruff check src tests` [VERIFIED: .planning/STATE.md uses these gates] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SRC-01 | Parser registry and source routing | unit | `uv run pytest tests/rag/test_parser_contract.py -q` | no, Wave 0 [VERIFIED: file audit] |
| SRC-02 | Deterministic parser DTO fields/failure codes | unit | `uv run pytest tests/rag/test_parser_contract.py -q` | no, Wave 0 [VERIFIED: file audit] |
| SRC-03 | PDF digital/scanned parsing | unit/integration fixture | `uv run pytest tests/rag/test_pdf_parser.py -q` | no, Wave 0 [VERIFIED: file audit] |
| SRC-04 | DOCX paragraphs/headings/tables logical blocks | unit fixture | `uv run pytest tests/rag/test_docx_parser.py -q` | no, Wave 0 [VERIFIED: file audit] |
| SRC-05 | Image OCR status/bbox/confidence | unit fixture | `uv run pytest tests/rag/test_ocr_parser.py -q` | no, Wave 0 [VERIFIED: file audit] |
| PROV-01 | `DocumentBlock` ORM/migration fields | unit/static migration | `uv run pytest tests/rag/test_document_block_schema.py -q` | no, Wave 0 [VERIFIED: file audit] |
| PROV-02 | Chunk ordered source-block refs | unit | `uv run pytest tests/rag/test_block_chunker.py -q` | no, Wave 0 [VERIFIED: file audit] |
| PROV-03 | Verified provenance lookup | unit | `uv run pytest tests/knowledge/test_provenance_lookup.py -q` | no, Wave 0 [VERIFIED: file audit] |
| PROV-04 | Blocks cannot be evidence/authority | architecture/unit | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_memory_evidence_boundary.py -q` | partial existing [VERIFIED: tests/agent/test_memory_evidence_boundary.py] |
| CHUNK-01 | Block-aware citation content and stable chunk IDs | unit | `uv run pytest tests/rag/test_block_chunker.py tests/test_chunker.py -q` | partial existing [VERIFIED: tests/test_chunker.py] |
| CHUNK-02 | Table row/header/cell context | unit fixture | `uv run pytest tests/rag/test_block_chunker.py tests/rag/test_pdf_parser.py tests/rag/test_docx_parser.py -q` | no, Wave 0 [VERIFIED: file audit] |
| CHUNK-03 | Search text enrichment does not mutate content/hash | unit | `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_text_hash.py -q` | partial existing [VERIFIED: existing files] |
| CHUNK-04 | Version bumps only on canonical content/semantics | unit | `uv run pytest tests/test_ingestion.py -q` | partial existing [VERIFIED: tests/test_ingestion.py] |
| OCR-01 | OCR confidence stored separately from retrieval score | unit | `uv run pytest tests/rag/test_ocr_parser.py tests/knowledge/test_hybrid_retrieval.py -q` | partial existing [VERIFIED: tests/knowledge/test_hybrid_retrieval.py] |
| OCR-02 | Low-confidence quarantine/review-needed | unit fixture | `uv run pytest tests/rag/test_ocr_parser.py -q` | no, Wave 0 [VERIFIED: file audit] |
| SAFE-01 | File safety limits and malformed behavior | unit/security | `uv run pytest tests/rag/test_ingestion_safety.py -q` | no, Wave 0 [VERIFIED: file audit] |
| SAFE-02 | Prompt-injection/raw-payload exclusion | architecture/security | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/context/test_assembler.py -q` | partial existing [VERIFIED: tests/agent/context/test_assembler.py] |
| SAFE-03 | Business artifact rejection | unit/security | `uv run pytest tests/rag/test_ingestion_safety.py tests/agent/test_policy_retrieval_ownership.py -q` | partial existing [VERIFIED: tests/agent/test_policy_retrieval_ownership.py] |
| INGEST-01 | Safe job trace reports | unit | `uv run pytest tests/rag/test_ingestion_jobs.py -q` | no, Wave 0 [VERIFIED: file audit] |
| INGEST-02 | Parse/OCR/chunk/embed before transaction | unit | `uv run pytest tests/test_ingestion.py -q` | partial existing [VERIFIED: tests/test_ingestion.py] |
| INGEST-03 | Failed parse/OCR/embed/DB leaves previous state | unit/integration | `uv run pytest tests/test_ingestion.py tests/rag/test_ingestion_jobs.py -q` | partial existing [VERIFIED: tests/test_ingestion.py] |
| INGEST-04 | Migration upgrade/downgrade/reupgrade | static/integration | `uv run pytest tests/test_rag_production_migration.py -q` | no, Wave 0 [VERIFIED: file audit] |
| BOUNDARY-01 | EvidenceRef/snapshot/replay/hash compatibility | regression | `uv run pytest tests/knowledge/test_evidence_projection.py tests/knowledge/test_text_hash.py tests/approvals/test_snapshots.py tests/replay/test_replay_migration_contract.py -q` | existing [VERIFIED: file audit] |
| BOUNDARY-02 | Hybrid retrieval filters/RRF/confidence intact | regression | `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_hybrid_schema.py -q` | existing [VERIFIED: file audit] |
| BOUNDARY-03 | Parser/OCR metadata excluded from public surfaces | architecture/regression | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_graph.py -q` | partial existing [VERIFIED: tests/agent/test_graph.py] |
| BOUNDARY-04 | No Phase 22/23/RAG-5 deliverables | architecture/static | `uv run pytest tests/knowledge/test_phase21_boundaries.py -q` | no, Wave 0 [VERIFIED: file audit] |

### Sampling Rate

- **Per task commit:** Run the quick command plus the new test file for the touched slice. [VERIFIED: GSD validation pattern + existing test organization]
- **Per wave merge:** Run `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q`. [ASSUMED]
- **Phase gate:** Run full suite and Ruff before `/gsd-verify-work`. [VERIFIED: .planning/STATE.md]

### Wave 0 Gaps

- [ ] `tests/rag/test_parser_contract.py` - covers SRC-01/SRC-02. [VERIFIED: file audit]
- [ ] `tests/rag/test_document_block_schema.py` - covers PROV-01/INGEST-04 static schema. [VERIFIED: file audit]
- [ ] `tests/rag/test_block_chunker.py` - covers CHUNK-01/CHUNK-02/PROV-02. [VERIFIED: file audit]
- [ ] `tests/rag/test_pdf_parser.py` - covers SRC-03/table PDF fixtures. [VERIFIED: file audit]
- [ ] `tests/rag/test_docx_parser.py` - covers SRC-04/DOCX tables. [VERIFIED: file audit]
- [ ] `tests/rag/test_ocr_parser.py` - covers SRC-05/OCR-01/OCR-02. [VERIFIED: file audit]
- [ ] `tests/rag/test_ingestion_safety.py` - covers SAFE-01/SAFE-02/SAFE-03. [VERIFIED: file audit]
- [ ] `tests/rag/test_ingestion_jobs.py` - covers INGEST-01/INGEST-03. [VERIFIED: file audit]
- [ ] `tests/knowledge/test_provenance_lookup.py` - covers PROV-03. [VERIFIED: file audit]
- [ ] `tests/knowledge/test_phase21_boundaries.py` - covers PROV-04/BOUNDARY-03/BOUNDARY-04. [VERIFIED: file audit]
- [ ] `tests/test_rag_production_migration.py` - covers INGEST-04 migration static and optional DB round trip. [VERIFIED: file audit]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement: false`. [VERIFIED: .planning/config.json]

OWASP ASVS 5.0.0 is the current stable ASVS version according to OWASP project docs. [CITED: https://owasp.org/www-project-application-security-verification-standard/]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct new auth surface | Phase 21 uses existing maintainer/backend context and should not add public upload auth. [VERIFIED: .planning/REQUIREMENTS.md] |
| V3 Session Management | no direct new session surface | No session changes are needed for parser/OCR ingestion. [VERIFIED: .planning/REQUIREMENTS.md] |
| V4 Access Control | yes | Tenant-scoped document/block/chunk/job rows; provenance lookup validates tenant and evidence hash before returning locators. [VERIFIED: src/knowledge/service.py + .planning/REQUIREMENTS.md] |
| V5 Input Validation | yes | Parser DTO validation, file extension/signature/size/page/image limits, and safe failure codes. [VERIFIED: .planning/REQUIREMENTS.md + OWASP File Upload Cheat Sheet] |
| V6 Cryptography | yes, existing hashing only | Use existing SHA-256 `evidence_text_hash` and source checksum; do not invent custom crypto. [VERIFIED: tests/knowledge/test_text_hash.py] |
| V8 Error Handling and Logging | yes | Store sanitized failure codes/messages and timings, not raw parser dumps or secrets. [VERIFIED: .planning/REQUIREMENTS.md + docs/contract-spec.md] |
| V12 File and Resource Handling | yes | Treat uploaded/imported files as untrusted, enforce limits, store safe names/paths, and prevent unsafe file execution. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html] |

### Known Threat Patterns For Phase 21

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed file extension/content type | Tampering | Allowlist extension, content type, and file signature; do not trust any one signal alone. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html] |
| Decompression bomb / oversized image | Denial of Service | Enforce file/image/page limits and convert Pillow decompression warnings into failures. [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html] |
| DOCX zip-style hazard | Denial of Service | Check compressed/uncompressed size ratios before parsing and fail safely. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html] |
| OCR timeout / parser hang | Denial of Service | Use `pytesseract` timeouts and parser-level deadlines before DB mutation. [CITED: https://pypi.org/project/pytesseract/] |
| Hidden prompt injection in source file | Spoofing / Elevation of Privilege | Treat source text as untrusted content; keep raw parser/OCR text out of prompts/actions/memory/replay except canonical evidence refs and verified citation text. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html] |
| Cross-tenant provenance leak | Information Disclosure | Query blocks/jobs/chunks by tenant and validate evidence hash before returning source location. [VERIFIED: src/knowledge/service.py + tests/knowledge/test_tenant_scope.py] |
| Business artifact becomes policy evidence | Tampering / Elevation of Privilege | Reject business-object source types and forbid Tool System outputs from chunk store. [VERIFIED: docs/contract-spec.md + .planning/REQUIREMENTS.md] |
| Parser stack trace leaks secrets/paths | Information Disclosure | Store stable failure code and sanitized message only; keep debug stack out of job trace/API. [VERIFIED: docs/contract-spec.md redaction rules + .planning/REQUIREMENTS.md] |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OCR acceptance threshold locked: accept `>=80`, review `55-79`, reject `<55` or empty text. | Phase Requirements / Concrete Planning Decisions | Boundary fixtures may still need expansion after real corpus import. |
| A2 | OCR timeout locked: `15s/page`; parser timeout remains `30s`. | Concrete Planning Decisions | Slow valid scans may fail or bad files may consume too much time. |
| A3 | PDF page limit recommendation: 50 pages. | Concrete Planning Decisions | Real maintainer sources may exceed the cap. |
| A4 | PDF/DOCX/image file limit locked at 20 MB. | Concrete Planning Decisions | Real maintainer sources may exceed the cap. |
| A5 | Image dimension limit locked at `8000x8000`. | Concrete Planning Decisions | Real image sources may exceed the cap or DoS risk may remain too high. |
| A6 | OCR language preflight requires `chi_sim+eng`. | Slice 21.3 / Standard Stack | OCR may fail on local/CI if language data is missing. |
| A7 | JSONB ordered source-block refs are selected for v1.4. | Resolved Decisions / Migration Strategy | Block-centric review queries may become awkward or slow. |
| A8 | Phase 21 Markdown/plain-text ingestion emits synthetic source blocks; pre-Phase-21 rows remain retrieval-compatible. | Resolved Decisions | Maintainers may expect provenance for already committed legacy rows. |
| A9 | Exact policy semantics metadata allowlist for version bumping is not yet defined. | Slice 21.2 | Parser metadata-only changes may accidentally churn policy versions. |
| A10 | Dependency lock update should be assigned during implementation rather than research. | Runtime State Inventory | Planner might sequence dependency changes later than parser-contract tests need. |

## Sources

### Primary (HIGH confidence)

- `.planning/ROADMAP.md` - Phase 21 goal, sequence, constraints, out-of-scope guardrails. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` - all 26 Phase 21 requirements. [VERIFIED: file read]
- `.planning/STATE.md` - shipped v1.3 decisions and current status. [VERIFIED: file read]
- `.planning/research/SUMMARY.md` - v1.4 research summary and recommended slices. [VERIFIED: file read]
- `docs/contract-spec.md` - normative EvidenceRef, trusted context, replay/redaction, and business/policy boundaries. [VERIFIED: file read]
- `docs/rag-architecture-spec.md` - target-state RAG ingestion, DocumentBlock, and RAG phase roadmap guidance. [VERIFIED: file read]
- `src/rag/ingestion.py`, `src/rag/chunker.py`, `src/rag/search_text.py`, `src/db/models.py`, `src/knowledge/schemas.py`, `src/knowledge/service.py`, `src/knowledge/retrieval.py`, `src/repositories/policy_chunk_repo.py`. [VERIFIED: file read]
- `tests/test_ingestion.py`, `tests/rag/test_search_text.py`, `tests/knowledge/test_hybrid_retrieval.py`, plus related boundary/migration tests found by `rg`. [VERIFIED: file read]
- PyPI package index and JSON metadata for `pdfplumber`, `pypdfium2`, `python-docx`, `pytesseract`, `Pillow`, and `filetype`. [VERIFIED: pip index + PyPI JSON]
- Official pdfplumber README. [CITED: https://github.com/jsvine/pdfplumber]
- Official pypdfium2 docs. [CITED: https://pypdfium2.readthedocs.io/en/v4/python_api.html]
- Official python-docx docs. [CITED: https://python-docx.readthedocs.io/en/latest/api/document.html]
- pytesseract PyPI docs. [CITED: https://pypi.org/project/pytesseract/]
- Pillow docs. [CITED: https://pillow.readthedocs.io/en/stable/reference/Image.html]
- Tesseract traineddata docs. [CITED: https://tesseract-ocr.github.io/tessdoc/Data-Files.html]
- OWASP File Upload Cheat Sheet. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html]
- OWASP LLM Prompt Injection Prevention Cheat Sheet. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html]
- OWASP ASVS project page. [CITED: https://owasp.org/www-project-application-security-verification-standard/]

### Secondary (MEDIUM confidence)

- Current local environment probes for `uv`, Python, pytest, Alembic, Docker, Tesseract, and missing `psql`/`chi_sim`. [VERIFIED: local commands]

### Tertiary (LOW confidence)

- Numeric OCR thresholds, file/page/image limits, and JSONB-vs-join-table preference are planning recommendations pending fixture calibration and user confirmation. [ASSUMED]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH for existing project stack and package versions; MEDIUM for parser/OCR fit until fixtures run. [VERIFIED: pyproject.toml + package registry + official docs]
- Architecture: HIGH for preserving `EvidenceRefV1` and v1.3 retrieval; MEDIUM for exact provenance storage shape. [VERIFIED: codebase + requirements]
- Pitfalls: HIGH for contract/security pitfalls; MEDIUM for OCR/table parser edge cases until fixture corpus exists. [VERIFIED: requirements + OWASP + official docs]
- Migration strategy: MEDIUM-HIGH because existing migration patterns are clear, but live DB contents were not inspected. [VERIFIED: migration files + local command audit]

**Research date:** 2026-06-18 [VERIFIED: system date]
**Valid until:** 2026-07-02 for parser/OCR package versions; 2026-07-18 for internal codebase architecture if no major RAG changes land. [ASSUMED]
