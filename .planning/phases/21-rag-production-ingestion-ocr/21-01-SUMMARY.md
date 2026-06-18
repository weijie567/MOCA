---
phase: 21-rag-production-ingestion-ocr
plan: "01"
subsystem: rag-ingestion
tags: [rag, parser-dto, source-guards, markdown, plain-text, safety]

requires:
  - phase: 20-rag-hybrid-retrieval
    provides: v1.3 EvidenceRefV1, PolicyChunk content/search_text, and hybrid retrieval behavior
  - phase: 21-00
    provides: Phase 21 validation scaffold and owner-tasked strict xfail inventory
provides:
  - Project-owned parser DTOs for source blocks, parser warnings, source boxes, and parse results
  - Parser registry with allowlisted policy source routing and fail-closed unsupported adapter behavior
  - Markdown and plain-text adapters that emit deterministic synthetic source blocks
  - Source safety constants, OCR confidence thresholds, and business-artifact rejection guards
affects: [21-01a-source-block-schema, 21-02-block-aware-chunking, 21-03-native-parser-adapters]

tech-stack:
  added: []
  patterns:
    - frozen dataclass parser DTOs
    - parser registry adapter protocol
    - safe warning codes for hidden/raw/control parser text
    - synthetic source-block IDs for logical text sources

key-files:
  created:
    - src/rag/parsers/__init__.py
    - src/rag/parsers/base.py
    - src/rag/parsers/registry.py
    - src/rag/parsers/markdown.py
    - src/rag/parsers/plain_text.py
    - src/rag/parsers/safety.py
  modified:
    - tests/rag/phase21_xfail_inventory.py
    - tests/rag/test_parser_contract.py
    - tests/rag/test_ingestion_safety.py

key-decisions:
  - "Markdown and plain-text adapters emit synthetic block IDs as doc_key:source_type:synthetic:0000-style identifiers."
  - "Hidden Markdown comments, control characters, local paths, raw parser dumps, and debug payload markers are excluded from ParsedBlock text and represented by safe warning codes."
  - "PDF, DOCX, and image source types are allowlisted for registry resolution, but parsing remains fail-closed until later native adapter plans register implementations."

patterns-established:
  - "Parser adapters return ParseResult and ParsedBlock DTOs only; native parser objects do not cross the parser boundary."
  - "Source guards return stable safe failure codes without leaking parser exceptions, local paths, or raw file content."

requirements-completed: [SRC-01, SRC-02, SAFE-01, SAFE-03, OCR-01]

duration: 12m
completed: 2026-06-18
---

# Phase 21 Plan 01: Parser Contracts Source Guards And Markdown Plain Text Adapters Summary

**Parser DTOs, source safety guards, and deterministic Markdown/plain-text synthetic source blocks for Phase 21 ingestion**

## Performance

- **Duration:** 12m
- **Started:** 2026-06-18T16:57:58Z
- **Completed:** 2026-06-18T17:09:45Z
- **Tasks:** 1
- **Files modified:** 10

## Accomplishments

- Added `SourceBox`, `ParserWarning`, `ParsedBlock`, `ParseResult`, and finite safe parser failure/warning codes under `src/rag/parsers/base.py`.
- Added `ParserRegistry` and `ParserAdapter` protocol with allowlisted source routing and fail-closed unsupported native adapter behavior.
- Added Markdown and plain-text adapters that emit stable synthetic `source_block_id` values and bounded visible/normalized text.
- Added source safety constants, OCR thresholds, signature/size/page/image guards, and business-artifact rejection for policy-source scope.
- Removed only the 21-01-owned Wave 0 strict xfail markers and left later-plan xfails owner-tasked.

## Task Commits

1. **Task 21-01-01: Implement parser DTOs, registry, Markdown/plain-text adapters, and source guards** - `997b018` (`feat`)

## Files Created/Modified

- `src/rag/parsers/__init__.py` - Public exports for parser DTOs, registry, adapters, and safety guards.
- `src/rag/parsers/base.py` - Frozen parser DTO dataclasses, safe parser failure/warning codes, and visible-text sanitization helpers.
- `src/rag/parsers/registry.py` - Parser adapter protocol, allowlisted route resolution, default Markdown/plain adapters, and safe failed parse results.
- `src/rag/parsers/markdown.py` - Markdown adapter with heading/paragraph/list logical block extraction and hidden/raw unsafe-text warnings.
- `src/rag/parsers/plain_text.py` - Plain-text adapter with paragraph block extraction and synthetic source-block provenance.
- `src/rag/parsers/safety.py` - Source limits, OCR thresholds, source validation result DTO, file guard checks, and business-artifact rejection.
- `tests/rag/phase21_xfail_inventory.py` - Removed only the implemented 21-01 owner entries.
- `tests/rag/test_parser_contract.py` - Replaced strict xfails with concrete DTO, registry, adapter, synthetic-block, warning, and safe-failure assertions.
- `tests/rag/test_ingestion_safety.py` - Replaced source-guard/business-artifact strict xfails with passing safety tests using `safety.py`.

## Decisions Made

- Synthetic source-block IDs use `doc_key:source_type:synthetic:{block_index:04d}` to give downstream schema and chunking plans deterministic provenance handles before durable source-block rows exist.
- Markdown/plain text page and bbox fields are intentionally `None`; table and OCR metadata are intentionally empty dicts because these logical formats have no page geometry or OCR output in Plan 21-01.
- Native parser source types are route-allowlisted now, but their adapters are not implemented in this plan and parse fail closed until Plan 21-03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved warning codes for document-level unsafe Markdown preamble**
- **Found during:** Task 21-01-01 verification
- **Issue:** The initial Markdown adapter could drop control-character warnings when unsafe text appeared before the first visible Markdown block.
- **Fix:** Sanitized the Markdown document after hidden-comment stripping and aggregated document-level safety warnings into `ParseResult.warnings`.
- **Files modified:** `src/rag/parsers/markdown.py`, `tests/rag/test_parser_contract.py`
- **Verification:** `uv run pytest tests/rag/test_parser_contract.py tests/rag/test_ingestion_safety.py -q`
- **Committed in:** `997b018`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** No scope expansion; the fix is required for the plan's safe warning-code contract.

## Issues Encountered

- The first focused pytest run failed because `control_characters_removed` was not preserved for a Markdown preamble. The adapter now records the warning at document level and the required suite passes.

## Authentication Gates

None.

## Known Stubs

None. Stub-pattern scan only found intentional optional DTO fields (`None` page/box values for logical text sources and empty table/OCR metadata dicts for non-table, non-OCR blocks).

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/rag/test_parser_contract.py tests/rag/test_ingestion_safety.py -q` - PASS (`10 passed, 2 xfailed`)
- `uv run pytest tests/knowledge/test_evidence_projection.py tests/knowledge/test_hybrid_retrieval.py tests/rag/test_search_text.py -q` - PASS (`17 passed`)
- `uv run ruff check src/rag/parsers tests/rag/test_parser_contract.py tests/rag/test_ingestion_safety.py` - PASS
- `rg -n "class SourceBox|class ParsedBlock|class ParseResult|class ParserRegistry|MAX_SOURCE_FILE_BYTES|OCR_CONFIDENCE_ACCEPTED_MIN|reject_business_artifact_source" src/rag/parsers tests/rag/test_parser_contract.py tests/rag/test_ingestion_safety.py` - PASS

## Next Phase Readiness

Plan 21-01a can build durable source-block schema/repositories against the DTOs and stable synthetic block IDs. Later PDF/DOCX/image/OCR, runtime deadline, ingestion report, provenance lookup, and boundary tests remain owner-tasked xfails for their respective plans.

## Self-Check: PASSED

- Created-file checks passed for all parser modules, touched tests, and this summary.
- Commit visibility check passed for task commit `997b018`.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18*
