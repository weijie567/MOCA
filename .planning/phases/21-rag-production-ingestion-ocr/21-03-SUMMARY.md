---
phase: "21-rag-production-ingestion-ocr"
plan: "03"
subsystem: "rag-ingestion"
tags: [rag, parsers, pdf, docx, ocr, tesseract, safety]
requires:
  - phase: "21-rag-production-ingestion-ocr"
    provides: "Plan 21-02 parser DTOs, block-aware chunking, source-block refs, and atomic ingestion job tracing"
provides:
  - "Pinned local parser/OCR dependency set and Docker native Tesseract runtime packages"
  - "Runtime OCR preflight for chi_sim+eng with deterministic safe failure states"
  - "Source-file validation for signatures, size, PDF pages, image dimensions, DOCX zip hazards, and business artifacts"
  - "Image OCR, PDF, and DOCX adapters returning project-owned ParseResult/ParsedBlock DTOs"
  - "OCR confidence metadata gated as accepted, review_needed, or rejected without changing retrieval scores"
affects: [phase-21, policy-rag-ingestion, parser-contract, source-block-provenance]
tech-stack:
  added: [pdfplumber==0.11.10, pypdfium2==5.10.1, python-docx==1.2.0, pytesseract==0.3.13, Pillow==12.2.0, filetype==1.2.0, tesseract-ocr-chi-sim, tesseract-ocr-eng]
  patterns:
    - "Native parser libraries are wrapped behind project-owned DTO adapters"
    - "OCR confidence remains source-block metadata and never replaces retrieval confidence"
    - "File validation fails closed before native parser execution"
key-files:
  created:
    - "src/rag/parsers/runtime.py"
    - "src/rag/parsers/ocr.py"
    - "src/rag/parsers/image.py"
    - "src/rag/parsers/pdf.py"
    - "src/rag/parsers/docx.py"
  modified:
    - "pyproject.toml"
    - "uv.lock"
    - "Dockerfile"
    - "src/rag/parsers/safety.py"
    - "tests/rag/phase21_xfail_inventory.py"
    - "tests/rag/test_ingestion_safety.py"
    - "tests/rag/test_ocr_parser.py"
    - "tests/rag/test_pdf_parser.py"
    - "tests/rag/test_docx_parser.py"
    - "tests/knowledge/test_hybrid_retrieval.py"
key-decisions:
  - "Use exact parser/OCR pins as a Phase 21 local ingestion reproducibility exception."
  - "Mock native OCR availability in tests while preflight returns deterministic chi_sim/eng/executable failure states."
  - "Store OCR confidence only in block/chunk metadata; retrieval score contracts remain unchanged."
  - "Do not edit ParserRegistry wiring in this plan because registry.py was outside the explicit 21-03 write scope."
patterns-established:
  - "Adapters sanitize visible parser text before building ParsedBlock text/normalized_text."
  - "Scanned PDF fallback reuses OcrEngine and converts OCR pixel boxes back to PDF page coordinates."
requirements-completed: [SRC-01, SRC-03, SRC-04, SRC-05, CHUNK-02, OCR-01, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-03]
duration: "16 min"
completed: "2026-06-19"
---

# Phase 21 Plan 03: PDF DOCX Image OCR Adapters And Runtime Preflight Summary

**Local PDF, DOCX, image, and OCR parser adapters with Tesseract chi_sim+eng preflight and fail-closed source validation**

## Performance

- **Duration:** 16 min
- **Started:** 2026-06-18T22:55:08Z
- **Completed:** 2026-06-18T23:11:23Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- Added exact local parser/OCR pins, refreshed `uv.lock`, and installed native Tesseract plus Simplified Chinese/English language packages in Docker.
- Implemented OCR preflight, deadline helpers, and file validation for source signatures, oversize files, PDF page count, image dimensions, DOCX zip hazards, malformed files, and business artifact rejection.
- Added `OcrEngine`, `ImageOcrParser`, `PdfParser`, and `DocxParser` adapters that emit project-owned `ParseResult`/`ParsedBlock` DTOs only.
- Preserved OCR confidence as metadata only and extended retrieval tests to prove `EvidenceRefV1.score` and best-score behavior remain retrieval-owned.

## Task Commits

1. **Task 21-03-01: Runtime preflight and safety validation** - `7f11314` (feat)
2. **Task 21-03-02 RED: OCR adapter coverage** - `f1db991` (test)
3. **Task 21-03-02 GREEN: Image OCR adapter** - `df58d5d` (feat)
4. **Task 21-03-03 RED: PDF/DOCX adapter coverage** - `cc2bca8` (test)
5. **Task 21-03-03 GREEN: PDF/DOCX adapters** - `d3378ac` (feat)

## Files Created/Modified

- `src/rag/parsers/runtime.py` - Tesseract preflight and parser/OCR deadline helpers.
- `src/rag/parsers/safety.py` - File-level source validation for parser/OCR ingestion boundaries.
- `src/rag/parsers/ocr.py` - Tesseract OCR wrapper, word boxes, and confidence gates.
- `src/rag/parsers/image.py` - Image validation plus OCR adapter.
- `src/rag/parsers/pdf.py` - PDF text/table parser and scanned-page OCR fallback.
- `src/rag/parsers/docx.py` - DOCX logical heading, paragraph, and table parser.
- Parser/safety/retrieval tests - Fixture and mocked-runtime coverage for the adapter contract.

## Decisions Made

- Exact parser/OCR dependency pins are intentional for Phase 21 reproducibility, even though the repository usually uses lower-bound dependency style.
- Native OCR availability is preflighted in `runtime.py`; adapter tests mock Tesseract so local machines without `chi_sim` can still run deterministically.
- Low-confidence OCR status is stored in `ocr_metadata` only and does not alter retrieval confidence fields.

## Deviations from Plan

### Scope-Constrained Adjustment

**1. Registry factory wiring not changed**
- **Found during:** Task 21-03-03
- **Issue:** The task text asked to register PDF/DOCX adapters in the registry factory, but both the plan `files_modified` list and the user’s explicit write scope excluded `src/rag/parsers/registry.py` and `src/rag/parsers/__init__.py`.
- **Action:** Implemented and verified the concrete adapters directly without editing the registry factory.
- **Impact:** Adapter behavior is complete and tested, but default `ParserRegistry()` construction still needs an explicitly scoped registry-wiring follow-up before ingestion service routes PDF/DOCX/image sources automatically.
- **Verification:** `tests/rag/test_parser_contract.py` still passes for existing registry routing; direct adapter tests pass.

**Total deviations:** 1 scope-constrained adjustment.

## Issues Encountered

None beyond the registry write-scope conflict documented above.

## Verification

- `uv run pytest tests/rag/test_pdf_parser.py tests/rag/test_docx_parser.py tests/rag/test_ocr_parser.py tests/rag/test_ingestion_safety.py tests/rag/test_parser_contract.py tests/knowledge/test_hybrid_retrieval.py -q` - **PASS** (41 passed, 1 xfailed; xfail is later 21-04 safe-report boundary)
- `uv lock --check` - **PASS**
- `uv run ruff check src/rag/parsers/runtime.py src/rag/parsers/safety.py src/rag/parsers/ocr.py src/rag/parsers/image.py src/rag/parsers/pdf.py src/rag/parsers/docx.py tests/rag/test_ingestion_safety.py tests/rag/test_ocr_parser.py tests/rag/test_pdf_parser.py tests/rag/test_docx_parser.py tests/knowledge/test_hybrid_retrieval.py tests/rag/test_parser_contract.py` - **PASS**
- `uv run pytest tests/rag/test_block_chunker.py -q` - **PASS** (5 passed)
- Acceptance greps for exact pins, OCR confidence states, `chi_sim+eng`, `pixel`, `pdfplumber`, `pypdfium2`, `python-docx`, `DocxParser`, `PdfParser`, and `pdf_point` - **PASS**

## Known Stubs

None. Empty collections and `None` values found by the stub scan are DTO defaults, safe-failure fields, or test fixtures, not UI/data-source stubs.

## Threat Flags

None. New native parser/OCR/file-access surfaces are the planned surfaces covered by the 21-03 threat model mitigations.

## User Setup Required

None for tests. Runtime OCR deployments must include the Docker/native Tesseract packages added in this plan.

## Next Phase Readiness

Ready for 21-04 provenance lookup and trace reporting. Before production ingestion routes PDF/DOCX/image sources through `IngestionService`, add an explicitly scoped registry-wiring change for the native adapters.

## Self-Check: PASSED

- Key created files found: `runtime.py`, `ocr.py`, `image.py`, `pdf.py`, `docx.py`, and this summary.
- Task commits found: `7f11314`, `f1db991`, `df58d5d`, `cc2bca8`, `d3378ac`.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-19*
