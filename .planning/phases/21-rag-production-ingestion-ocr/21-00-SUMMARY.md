---
phase: 21-rag-production-ingestion-ocr
plan: "00"
subsystem: testing
tags: [rag, ingestion, ocr, provenance, pytest, validation]

requires:
  - phase: 20-rag-hybrid-retrieval
    provides: v1.3 EvidenceRefV1, hybrid retrieval, search_text, and ingestion baselines
provides:
  - Wave 0 pytest scaffold for parser, OCR, provenance, chunking, ingestion safety, migration, and boundary requirements
  - Owner-tasked strict xfail inventory for implementation-pending Phase 21 behavior
  - Explicit native OCR dependency skip path for missing pytesseract/Tesseract runtime
affects: [21-rag-production-ingestion-ocr, phase21-implementation-plans]

tech-stack:
  added: []
  patterns:
    - owner-tasked strict xfail scaffolds
    - skip-safe native dependency preflight for OCR tests
    - static scope guard for out-of-scope RAG deliverables

key-files:
  created:
    - tests/rag/phase21_xfail_inventory.py
    - tests/rag/test_parser_contract.py
    - tests/rag/test_document_block_schema.py
    - tests/rag/test_block_chunker.py
    - tests/rag/test_pdf_parser.py
    - tests/rag/test_docx_parser.py
    - tests/rag/test_ocr_parser.py
    - tests/rag/test_ingestion_safety.py
    - tests/rag/test_ingestion_jobs.py
    - tests/knowledge/test_provenance_lookup.py
    - tests/knowledge/test_phase21_boundaries.py
    - tests/test_rag_production_migration.py
  modified: []

key-decisions:
  - "Wave 0 records validation coverage for all Phase 21 requirements but does not mark the product requirements implemented."
  - "Implementation-pending behavior uses strict xfail markers with owner_task=21-* reasons and PHASE21_XFAIL_OWNERS entries."
  - "Native OCR behavior uses explicit pytest.importorskip/preflight instead of silent pass-through when pytesseract/Tesseract is unavailable."

patterns-established:
  - "Phase 21 scaffold tests use xfail_for(marker_id) from tests/rag/phase21_xfail_inventory.py."
  - "Boundary guard scans implementation Python surfaces while allowing deferred target-state strings in docs and planning files."

requirements-completed: []
requirements-scaffolded: [SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, PROV-01, PROV-02, PROV-03, PROV-04, CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, OCR-01, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-01, INGEST-02, INGEST-03, INGEST-04, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04]

duration: 8m 48s
completed: 2026-06-18
---

# Phase 21 Plan 00: Wave 0 Validation And Test Scaffolding Summary

**Phase 21 parser/OCR ingestion validation scaffold with owner-tasked strict xfails and v1.3 boundary guards**

## Performance

- **Duration:** 8m 48s
- **Started:** 2026-06-18T16:43:55Z
- **Completed:** 2026-06-18T16:52:43Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Created all twelve Wave 0 scaffold files named by the plan and `21-VALIDATION.md`.
- Added 26 owner-tasked strict xfails for implementation-pending parser, schema, chunking, OCR, provenance, safety, job trace, migration, and boundary behavior.
- Preserved existing v1.3 ingestion/retrieval tests without weakening or xfail changes.

## Task Commits

Each task was committed atomically:

1. **Task 21-00-01: Scaffold parser, schema, migration, and scope-guard tests** - `79da52c` (test)
2. **Task 21-00-02: Scaffold block chunking, ingestion safety, and job trace tests** - `c3ab644` (test)
3. **Task 21-00-03: Scaffold parser adapter and provenance lookup tests** - `9b21ad5` (test)

## Files Created/Modified

- `tests/rag/phase21_xfail_inventory.py` - Owner-task inventory and xfail marker helper.
- `tests/rag/test_parser_contract.py` - Parser registry, DTO, failure-code, and evidence-boundary scaffolds.
- `tests/rag/test_document_block_schema.py` - DocumentBlock, RagIngestionJob, and chunk provenance schema scaffolds.
- `tests/rag/test_block_chunker.py` - Block-aware chunking, table context, content, and search_text scaffolds.
- `tests/rag/test_pdf_parser.py` - PDF digital text, table, scanned fallback, and SourceBox scaffolds.
- `tests/rag/test_docx_parser.py` - DOCX logical block and no-fabricated-page/bbox scaffolds.
- `tests/rag/test_ocr_parser.py` - OCR confidence thresholds and native dependency preflight scaffolds.
- `tests/rag/test_ingestion_safety.py` - Source guard, limit, timeout, business artifact, and unsafe payload scaffolds.
- `tests/rag/test_ingestion_jobs.py` - Versioning, transaction order, rollback, safe job report, and sanitized failure scaffolds.
- `tests/knowledge/test_provenance_lookup.py` - Verified evidence content mirrors plus future provenance locator scaffold.
- `tests/knowledge/test_phase21_boundaries.py` - Scope guard and provenance authority boundary scaffolds.
- `tests/test_rag_production_migration.py` - Migration revision and downgrade-order scaffolds.

## Verification

- `uv run pytest tests/rag/test_parser_contract.py tests/rag/test_document_block_schema.py tests/rag/test_block_chunker.py tests/rag/test_pdf_parser.py tests/rag/test_docx_parser.py tests/rag/test_ocr_parser.py tests/rag/test_ingestion_safety.py tests/rag/test_ingestion_jobs.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_phase21_boundaries.py tests/test_rag_production_migration.py -q -rxXs`
  - Result: 14 passed, 3 skipped, 26 xfailed, 1 warning.
- `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_service.py -q`
  - Result: 35 passed, 1 warning.

## Decisions Made

- Wave 0 coverage is tracked as scaffolded, not implemented. Later Phase 21 plans own removing xfails and marking requirements complete.
- The OCR threshold scaffold was created before the full OCR adapter file because Task 2 acceptance explicitly grepped `tests/rag/test_ocr_parser.py`.
- Scope guard tests intentionally ignore docs and `.planning/` target-state strings while scanning implementation Python surfaces.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created OCR threshold scaffold during Task 2**
- **Found during:** Task 21-00-02 (Scaffold block chunking, ingestion safety, and job trace tests)
- **Issue:** Task 2 acceptance grepped `tests/rag/test_ocr_parser.py`, but the plan otherwise scheduled that file for Task 3. Without an early file, the acceptance command would fail on a missing path.
- **Fix:** Added only the OCR threshold scaffold values in Task 2, then completed adapter/OCR behavior scaffolds in Task 3.
- **Files modified:** `tests/rag/test_ocr_parser.py`
- **Verification:** Task 2 and Task 3 slice pytest commands passed; final Wave 0 command passed.
- **Committed in:** `c3ab644` and completed in `9b21ad5`

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** No production scope added; the deviation only made the plan's own acceptance checks executable in task order.

## Issues Encountered

- Local Python environment does not provide `pytesseract`; OCR behavior tests skip explicitly with `pytesseract is required for native OCR tests`. This is expected for Wave 0 and remains implementation-owned by later Phase 21 plans.

## Known Stubs

None - the intentional strict xfails are the Wave 0 deliverable and are tracked in `PHASE21_XFAIL_OWNERS`.

## User Setup Required

None - no external service configuration required for this validation scaffold.

## Next Phase Readiness

Ready for Phase 21 implementation plans. Plans 21-01 through 21-04a can remove their owned strict xfails as production parser, schema, chunking, OCR, provenance, safety, and boundary code lands.

## Self-Check: PASSED

- Verified all created files exist on disk.
- Verified task commits exist: `79da52c`, `c3ab644`, `9b21ad5`.
- Verified final Wave 0 scaffold command and existing v1.3 ingestion/retrieval regression slice pass.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18*
