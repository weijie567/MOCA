---
phase: 21
status: clean
review_depth: deep
files_reviewed: 12
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
reviewed_at: 2026-06-19
reviewer: codex
---

# Phase 21 Code Review

## Scope

- src/rag/parsers/base.py
- src/rag/chunker.py
- src/rag/ingestion.py
- src/rag/parsers/docx.py
- src/rag/parsers/ocr.py
- src/rag/parsers/pdf.py
- tests/rag/test_block_chunker.py
- tests/rag/test_docx_parser.py
- tests/rag/test_ocr_parser.py
- tests/rag/test_parser_contract.py
- tests/rag/test_pdf_parser.py
- tests/test_ingestion.py

## Findings

No issues found.

## Closed Re-Review Finding

- BLOCKER: unvalidated `doc_key` could be injected into `source_block_id`, chunk ids, embedding source context, search enrichment, and durable provenance JSON.
  - Resolution: added a shared `^[a-z0-9][a-z0-9_-]{0,63}$` doc key validator.
  - Resolution: ingestion now fails closed before parser/job/embed/write paths when `doc_key` is invalid.
  - Resolution: parser source block id builders and chunkers reject unvalidated doc keys as a second line of defense.
  - Regression coverage: malicious `doc_key` cannot enter ingestion report, job trace, embedding text, chunk ids, source refs, or parser source id builders.

## Review Notes

- Verified PDF canonical text is now derived from visible word geometry/style instead of raw `extract_text()` output.
- Verified PDF/DOCX table block text and table metadata are built from the same sanitized, bounded cell rows before chunking.
- Verified OCR `word_boxes` store sanitized word text and malformed OCR dict lengths do not raise `IndexError`.
- Verified durable ingestion paths persist sanitized table metadata and chunk content.
- Verified malicious `doc_key` values are rejected before parser, embedding, job trace, and durable writes.
- Verified parser source id builders and chunkers reject unvalidated `doc_key` values when called directly.
- Verified no Phase 21 pending xfail markers remain in the reviewed test scope.

## Verification

- `uv run pytest tests/test_ingestion.py tests/rag/test_block_chunker.py tests/rag/test_parser_contract.py tests/rag/test_pdf_parser.py tests/rag/test_docx_parser.py tests/rag/test_ocr_parser.py -q`
  - 65 passed, 1 third-party deprecation warning.
- `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q`
  - 203 passed, 1 third-party deprecation warning.
- `uv run ruff check src tests`
  - All checks passed.
- `uv run pytest -q`
  - 1131 passed, 1 skipped, 6 third-party/config deprecation warnings.

## Residual Risk

PDF visibility detection is intentionally conservative. Near-white or invisible text is rejected from canonical text; unusual valid PDFs that use white text on non-white backgrounds may need OCR/manual review rather than trusting the digital text layer.
