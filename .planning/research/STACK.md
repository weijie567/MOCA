# Stack Research

**Domain:** MOCA v1.4 production RAG ingestion, OCR, and citation provenance
**Researched:** 2026-06-18
**Confidence:** MEDIUM-HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Existing FastAPI ingestion CLI/service boundary | Current repo | Keep ingestion outside the hot online retrieval path | `src/rag/ingestion.py` is already offline/batch-oriented. Phase 21 should add parser/OCR before chunking, not add API background infrastructure or a new queue. |
| Existing PostgreSQL + Alembic + SQLAlchemy | PostgreSQL 16 via `pgvector/pgvector:pg16`; SQLAlchemy 2.x; Alembic current repo | Persist `DocumentBlock`, parser trace, OCR confidence, and block-to-chunk provenance | The repo already stores policy documents/chunks, JSONB metadata, generated full-text vectors, and pgvector in one database. Use relational rows plus JSONB for provenance instead of adding object storage or a document DB. |
| `pdfplumber` | 0.11.10 | Digital PDF parser for text, layout coordinates, page objects, and tables | It is MIT-licensed, current as of 2026-06-15, Python 3.12-compatible, and exposes page numbers, object coordinates, word bounding boxes, table cells, rows, columns, and debug signals. This fits source-block provenance better than plain `pypdf` and avoids PyMuPDF's AGPL/commercial decision. |
| `pypdfium2` | 5.10.1 | PDF page rendering for scanned-PDF OCR fallback | It is liberal-licensed, current as of 2026-06-15, ships prebuilt PDFium wheels on common platforms, and can render pages to bitmaps/Pillow images for Tesseract. Use it only for rendering scanned pages, not as the primary layout parser. |
| `python-docx` | 1.2.0 | DOCX paragraph and table extraction | It is stable, MIT-licensed, current as of 2025-06-16, and provides direct access to paragraphs, rows, cells, merged-cell metadata, and table structure. DOCX has no stable rendered page/bbox without a layout engine, so store logical provenance for DOCX. |
| Tesseract OCR engine | OS package: `tesseract-ocr` plus `tesseract-ocr-chi-sim` | Local OCR engine for images and scanned PDF pages | Tesseract is open source, runs locally, supports language traineddata packages, and matches demo/local constraints. Install the Simplified Chinese traineddata package in Docker for `chi_sim+eng`. |
| `pytesseract` | 0.3.13 | Python wrapper around the Tesseract executable | It supports Python 3.12 and exposes `image_to_data(...)`, which returns bounding boxes, confidence values, line/page fields, language selection, and timeout handling. This is the cleanest way to produce OCR confidence metadata. |
| `Pillow` | 12.2.0 | Image loading/normalization and OCR input | `pytesseract` requires Pillow/PIL-compatible images; `pypdfium2` can convert rendered pages to Pillow images. Pillow 12.2.0 supports Python 3.12 and is mature. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Existing Pydantic v2 | FastAPI-provided/current repo | Define `ParsedDocument`, `DocumentBlock`, `BlockBBox`, `OCRTrace`, and `ParserTrace` contracts | Use for parser outputs before DB persistence, mirroring existing `EvidenceRefV1`/knowledge schemas. No new schema library needed. |
| Existing stdlib `zipfile` | Python 3.12 | Preflight DOCX zip size/member count before `python-docx` opens it | Use to reject zip bombs and oversized embedded media in local fixtures and future uploads. Avoid `python-magic` unless content sniffing becomes a real requirement. |
| Existing stdlib `mimetypes` plus magic-byte checks | Python 3.12 | Route `.pdf`, `.docx`, and image files to parser adapters | Good enough for synthetic/local ingestion. Keep a strict extension and header allowlist rather than adding libmagic system dependencies. |
| Existing `hashlib` | Python 3.12 | Stable source-block and content hashes | Use for `source_block_id`, block content hash, parser input hash, and trace identity. Keep hashes deterministic and independent from retrieval time. |
| Existing PostgreSQL `JSONB` | Current repo | Store parser trace, bbox objects, table/cell metadata, OCR detail snippets | Use JSONB for low-cardinality provenance metadata, not for foreign-key identity. Keep durable IDs in columns. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Existing `uv` | Dependency install and lock updates | Add Python packages through `uv add` and commit lock updates during implementation. |
| Existing `ruff` | Linting | No new lint tooling needed. |
| Existing `pytest` + committed synthetic fixtures | Parser/OCR regression tests | Use small PDF/DOCX/PNG fixtures with known text, page numbers, bbox presence, table-cell coordinates, and OCR confidence ranges. Avoid network/model-dependent parser tests. |
| Tesseract CLI health check | Verify OCR runtime in Docker/local dev | Add a test or script that records `tesseract --version` and available languages in parser trace or test diagnostics. |

## Installation

```bash
# Python runtime additions
uv add "pdfplumber==0.11.10" "pypdfium2==5.10.1" "python-docx==1.2.0" "pytesseract==0.3.13" "pillow==12.2.0"

# Dockerfile system additions for OCR
apt-get update \
  && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
  && rm -rf /var/lib/apt/lists/*
```

Use exact pins for the phase implementation so parser traces can record deterministic `parser_name`, `parser_version`, `ocr_engine`, and `ocr_engine_version`. If exact patch pins are relaxed later, keep `uv.lock` authoritative and persist runtime versions in ingestion trace.

## Integration with Existing MOCA Boundaries

| Boundary | Recommendation | Rationale |
|----------|----------------|-----------|
| Parser abstraction | Add `PolicySourceParser` adapters: `PdfPlumberParser`, `DocxParser`, `ImageOCRParser` | Keeps file-type parsing out of `IngestionService` and makes parser/OCR trace testable. |
| Intermediate model | Add Pydantic `DocumentBlock` DTO before DB persistence | Current `chunk_markdown()` returns only citation text chunks. Phase 21 needs page/bbox/table/OCR metadata before chunking. |
| Persistence | Add `document_blocks` plus either `policy_chunk_blocks` join table or `PolicyChunk.source_block_refs_json` | Prefer a join table if chunks can span many source blocks. Use JSONB only for MVP metadata, not as the only durable link. |
| `PolicyDocument.content` | Store normalized extracted citation text, not raw binary | Preserves existing ingestion/version behavior while avoiding unsafe raw payload storage in prompts. |
| `PolicyChunk.content` | Keep as user-visible citation text | v1.3 explicitly separates citation text from retrieval-only enrichment. Do not inject OCR trace, bbox, or parser debug text into this field. |
| `PolicyChunk.search_text` | Enrich with table headers/cell labels when useful | Search text can include retrieval-only table context, but `EvidenceRefV1.text_hash` must continue hashing `PolicyChunk.content`. |
| `EvidenceRefV1` | Do not add page, bbox, cell, or OCR fields in v1.4 | Keep evidence identity stable: `doc_key/chunk_id@policy_version` plus text hash. Resolve provenance by looking up the chunk's source blocks after retrieval. |
| OCR confidence | Store per OCR block and aggregate per chunk | Tesseract confidence is word-level in TSV-style output. Aggregate deterministically, e.g. mean of valid word confidences and min confidence warning. |
| Parser trace | Store internal/eval metadata only | Trace belongs in DB/debug/eval views, not prompts, agent state, approval snapshots, or `EvidenceRefV1`. |

## Recommended Data Shape

Add these concepts with the existing SQLAlchemy/Alembic stack:

| Table/Field | Purpose | Notes |
|-------------|---------|-------|
| `document_blocks.id` | Internal UUID primary key | Standard repo pattern. |
| `document_blocks.tenant_id`, `document_blocks.doc_id` | Scope and parent document | Match existing policy document/chunk tenant discipline. |
| `document_blocks.source_block_id` | Stable parser-level ID | Derive from `doc_key`, `policy_version`, parser name/version, page/logical index, block index, and normalized text hash. |
| `document_blocks.block_type` | `heading`, `paragraph`, `table`, `table_cell`, `image_ocr`, `page_ocr` | Use strings plus check constraints; no enum dependency needed. |
| `document_blocks.text` | Normalized block citation text | Keep raw parser payload out. |
| `document_blocks.page_number` | 1-indexed PDF/image page when available | `NULL` for DOCX logical blocks unless a later layout engine creates rendered pages. |
| `document_blocks.bbox_json` | Coordinate box and unit | For PDFs/images, store `{x0, top, x1, bottom, unit, page_width, page_height, origin}`. For DOCX, `NULL`. |
| `document_blocks.table_json` | Table/cell provenance | Include table index, row index, column index, grid span, header text, and whether this block is a header/cell. |
| `document_blocks.ocr_json` | OCR metadata | Include engine, language, confidence 0-1, source image/page, timeout/error flags. |
| `document_blocks.parser_json` | Parser trace | Include parser name/version, parse mode, warnings, fallback path, input hash, and failure reason. |
| `policy_chunk_blocks` | Many-to-many provenance from chunks to blocks | Use if chunking can merge paragraph + table cell blocks. Store chunk UUID, block UUID, order, and text range if needed. |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `pdfplumber` + `pypdfium2` | `PyMuPDF` | Use PyMuPDF only after an explicit license decision. It is technically excellent and current, but PyPI lists AGPL/commercial licensing. |
| `pdfplumber` PDF tables | `camelot-py` / `tabula-py` | Use only if Phase 21 fixtures prove `pdfplumber` cannot handle required policy tables. They are table-specific and bring heavier system/Java/Ghostscript complexity. |
| Tesseract + `pytesseract` | PaddleOCR / EasyOCR | Use only if Chinese scanned-policy OCR accuracy becomes a blocker. They add model downloads, heavier CPU/GPU dependencies, and less predictable Docker demo behavior. |
| Local OCR | Cloud OCR / LLM vision parsers | Use only in a future production integration milestone. They need secrets/network, weaken local reproducibility, and complicate synthetic-data demos. |
| Pydantic DTOs + SQLAlchemy models | LlamaIndex document readers as the parser contract | Keep LlamaIndex as an offline ingestion baseline if useful, but do not make its reader/node metadata the normative source-block contract. MOCA needs stable page/bbox/cell/OCR provenance independent from LlamaIndex internals. |
| JSONB parser trace in PostgreSQL | External trace/event service | Existing DB is enough for Phase 21. Add observability only if ingestion volume or retention requirements become real. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `unstructured` with all extras | Large dependency surface, optional ML/OCR extras, and harder-to-pin parser behavior for a local demo | Explicit adapters around `pdfplumber`, `python-docx`, and Tesseract. |
| PyMuPDF as the default | Strong technical fit but AGPL/commercial licensing is a project-level decision; MOCA has no visible repo license file in this checkout | Default to MIT/liberal-licensed `pdfplumber` + `pypdfium2`; revisit PyMuPDF only with a recorded license decision. |
| `PyPDF2`, `PyPDF3`, `PyPDF4` | Old/forked PDF stack and weaker layout/table provenance | `pdfplumber` for layout/table metadata. |
| `pypdf` as the main parser | Good for basic PDF operations, but not enough for page/bbox/table-cell provenance | `pdfplumber`. |
| `ocrmypdf` | Excellent for making searchable PDFs, but it rewrites PDFs and adds system dependencies not needed for block-level provenance | Render pages/images and call `pytesseract.image_to_data(...)` directly. |
| PaddleOCR/EasyOCR by default | Heavy model/runtime footprint and less conservative for Docker Compose demo | Tesseract first, with `OCRProvider` abstraction for later replacement. |
| LlamaParse, Textract, Azure OCR, Google Document AI, Qwen-VL, GPT-4.1 vision | External services violate local/dev demo constraints and add credential/network failure modes | Local parser/OCR stack. |
| Celery/RQ/new queue | Phase 21 ingestion is still batch/offline and synthetic-data friendly | Existing CLI/service execution; revisit only when concurrent user uploads exist. |
| S3/MinIO/object storage | v1.4 needs provenance, not binary document management | Keep fixture inputs local and persist normalized text/provenance in Postgres. |
| Vespa/OpenSearch/external `SearchBackend` | Explicitly out of Phase 21 scope | Existing PostgreSQL hybrid retrieval through `PolicyKnowledgeService`. |
| `MaterialClaim`, semantic verifier, reranker/query rewrite | Owned by later phases | Preserve current retrieval/evidence contracts only. |

## Stack Patterns by Variant

**If the source is a text PDF:**
- Use `pdfplumber.open(...)`, `page.extract_words(...)`, `page.extract_text_lines(...)`, and `page.find_tables(...)`.
- Persist page numbers and PDF-coordinate bboxes for text blocks/table cells.
- Use `pdfplumber` table debug metadata in parser trace when table extraction is uncertain.

**If the source is a scanned PDF:**
- Use `pdfplumber` first to detect low/no text.
- Render the page with `pypdfium2` at a fixed DPI such as 200-300.
- OCR the rendered image with `pytesseract.image_to_data(..., lang="chi_sim+eng", timeout=...)`.
- Map OCR pixel boxes back to page-relative coordinates and mark `block_type = "page_ocr"` or `"image_ocr"`.

**If the source is a standalone image:**
- Load with Pillow, normalize orientation/mode, then run `pytesseract.image_to_data(...)`.
- Store image pixel bboxes with `origin = "top_left"` and confidence aggregates.
- Do not fabricate PDF page numbers; use `page_number = 1` only if the parser contract defines image pages that way.

**If the source is DOCX:**
- Use `python-docx` to walk paragraphs and tables in document order.
- Persist logical block order, heading style when available, table/row/cell metadata, and merged-cell info.
- Store `page_number = NULL` and `bbox_json = NULL`; DOCX pagination depends on a rendering engine and should not be faked.

**If OCR confidence is low:**
- Persist the block with `ocr_confidence`, `ocr_low_confidence = true`, and parser warnings.
- Keep it eligible for retrieval only if Phase 21 requirements explicitly allow low-confidence text; otherwise mark it as review-needed and exclude from chunk insertion.
- Do not change `EvidenceRefV1` to express OCR confidence.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| MOCA Python | Python 3.12 | Current `pyproject.toml` requires `>=3.12`; all recommended Python packages support 3.12. |
| `pdfplumber==0.11.10` | Python 3.10-3.14 | PyPI lists 0.11.10 as latest on 2026-06-15 and tested on Python 3.10-3.14. |
| `pypdfium2==5.10.1` | Python 3.x; PDFium bundled on common wheels | Docs warn PDFium is not thread-safe; serialize PDFium calls in-process or use processes for parallel rendering. |
| `python-docx==1.2.0` | Python >=3.9 | Works with MOCA's Python 3.12; use stdlib zip preflight before opening untrusted DOCX files. |
| `pytesseract==0.3.13` | Python >=3.8; Tesseract executable; Pillow | `image_to_data` returns boxes/confidence and supports `timeout`. Requires system Tesseract installed separately. |
| `Pillow==12.2.0` | Python >=3.10 | Works with Python 3.12 and supports image I/O needed by Tesseract and PDF rendering. |
| Tesseract OCR | `tesseract-ocr-chi-sim` traineddata | Tesseract docs distinguish engine install from language traineddata. Docker must install both engine and Simplified Chinese language data. |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| PDF digital parsing | HIGH | `pdfplumber` directly supports coordinates, words, page objects, and tables; current version verified. |
| PDF scanned-page rendering | MEDIUM-HIGH | `pypdfium2` is current and capable, but its docs warn PDFium is not thread-safe. Keep ingestion serial/process-based. |
| DOCX logical extraction | HIGH | `python-docx` table/paragraph APIs are stable. Page/bbox absence is a real DOCX limitation, not a library miss. |
| OCR integration | MEDIUM | Tesseract is conservative and local, but Simplified Chinese accuracy varies by scan quality. Parser abstraction should allow future OCR provider replacement. |
| MOCA boundary fit | HIGH | Recommendations preserve `PolicyChunk.content`, retrieval-only `search_text`, and `EvidenceRefV1` identity. |

## Sources

- Context7: `/pymupdf/pymupdf` - verified PyMuPDF OCR/page API shape for comparison, including Tesseract-backed OCR caveats. HIGH confidence.
- Context7: `/websites/python-docx_readthedocs_io_en` - verified table/cell iteration, grid-span, and row-column caveats. HIGH confidence.
- Context7: `/websites/pypi_project_pytesseract` - verified `image_to_data`, confidence/box output, language config, and timeout support. HIGH confidence.
- https://pypi.org/project/pdfplumber/ - verified `pdfplumber` 0.11.10, release date, MIT license, Python 3.10-3.14 support, PDF object coordinates, table extraction, and explicit lack of OCR. HIGH confidence.
- https://pypi.org/project/pypdfium2/ - verified `pypdfium2` 5.10.1, release date, liberal licensing, prebuilt package guidance, optional Pillow adapters, and Python compatibility. HIGH confidence.
- https://pypdfium2.readthedocs.io/en/stable/python_api.html - verified `PdfPage.render()`, bitmap/Pillow conversion surface, text page APIs, and PDFium thread-safety warning. HIGH confidence.
- https://python-docx.readthedocs.io/en/latest/ and https://python-docx.readthedocs.io/en/latest/api/table.html - verified python-docx 1.2.0 docs and table/cell APIs. HIGH confidence.
- https://pypi.org/project/python-docx/ - verified python-docx 1.2.0 release date, Python requirement, and MIT license. HIGH confidence.
- https://pypi.org/project/pytesseract/ - verified pytesseract 0.3.13, Python 3.12 classifier, Tesseract wrapper role, Pillow prerequisite, `image_to_data`, and timeout support. HIGH confidence.
- https://tesseract-ocr.github.io/tessdoc/Installation.html - verified Tesseract engine/traineddata split and package naming including `tesseract-ocr-chi-sim`. HIGH confidence.
- https://pypi.org/project/pillow/ - verified Pillow 12.2.0, release date, Python >=3.10, and imaging role. HIGH confidence.
- https://pypi.org/project/PyMuPDF/ and https://pymupdf.readthedocs.io/en/latest/recipes-text.html - verified PyMuPDF current version, page text/bbox/table/OCR capabilities, and AGPL/commercial license caveat. HIGH confidence.

---
*Stack research for: MOCA v1.4 RAG Production Ingestion + OCR*
*Researched: 2026-06-18*
