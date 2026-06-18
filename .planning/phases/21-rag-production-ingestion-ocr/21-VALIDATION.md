---
phase: 21
slug: rag-production-ingestion-ocr
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-18
---

# Phase 21 - Validation Strategy

Per-phase validation contract for parser/OCR ingestion, source-block provenance,
and v1.3 evidence/retrieval compatibility.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_service.py -q` |
| Full suite command | `uv run pytest -q --tb=short && uv run ruff check src tests` |
| Estimated runtime | quick: under 90 seconds; full: under 15 minutes |

---

## Sampling Rate

- **After every task commit:** Run the quick command plus the slice-specific command listed below.
- **After every plan wave:** Run `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q`.
- **Before `$gsd-verify-work`:** Run `uv run pytest -q --tb=short && uv run ruff check src tests`.
- **Max feedback latency:** 90 seconds for slice tests; 15 minutes for the full gate.

---

## Threat References

| Ref | Threat | Required Secure Behavior |
|-----|--------|--------------------------|
| T21-01 | Spoofed extension or content type | Validate extension, signature, and declared type before parsing. |
| T21-02 | Oversized file, page, image, zip, or decompression hazard | Enforce deterministic limits and safe failure codes before DB mutation. |
| T21-03 | OCR timeout or parser hang | Apply parser/OCR deadlines and leave previous committed data intact. |
| T21-04 | Hidden prompt injection in parsed/OCR text | Keep raw payloads, parser dumps, and unsafe instructions out of prompts, memory, actions, replay, and API evidence. |
| T21-05 | Cross-tenant provenance leak | Resolve source locations only through tenant-scoped lookup after evidence content/hash validation. |
| T21-06 | Business artifact becomes policy evidence | Reject orders, refunds, tickets, screenshots, tool results, and business fact refs as policy sources. |
| T21-07 | `DocumentBlock` becomes a second authority surface | Prevent block IDs from acting as evidence, approval, memory, action, replay, or business fact authority. |
| T21-08 | Parser trace or stack trace leaks unsafe paths/secrets | Persist only sanitized failure codes, bounded warnings, timings, counts, checksums, and parser versions. |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 0 | SRC-01 | T21-01 | Parser registry routes only allowlisted source types into project DTOs. | unit | `uv run pytest tests/rag/test_parser_contract.py -q` | no, W0 | pending |
| 21-01-02 | 01 | 0 | SRC-02 | T21-08 | Parser DTOs expose deterministic order, failure codes, warnings, and versions. | unit | `uv run pytest tests/rag/test_parser_contract.py -q` | no, W0 | pending |
| 21-01-03 | 01 | 0 | PROV-01 | T21-05 | `DocumentBlock` rows are tenant/document scoped and migration-backed. | schema | `uv run pytest tests/rag/test_document_block_schema.py -q` | no, W0 | pending |
| 21-01-04 | 01 | 0 | INGEST-04 | T21-02 | Source-block, job, and chunk-provenance structures downgrade in dependency-safe order. | migration | `uv run pytest tests/test_rag_production_migration.py -q` | no, W0 | pending |
| 21-01-05 | 01 | 0 | BOUNDARY-04 | T21-07 | Phase 22/23/RAG-5 deliverables are absent. | static | `uv run pytest tests/knowledge/test_phase21_boundaries.py -q` | no, W0 | pending |
| 21-02-01 | 02 | 1 | CHUNK-01 | T21-07 | `PolicyChunk.content` is faithful source text and chunk identity remains stable. | unit | `uv run pytest tests/rag/test_block_chunker.py tests/test_chunker.py -q` | partial | pending |
| 21-02-02 | 02 | 1 | CHUNK-02 | T21-04 | Table chunks preserve headers, rows, cells, and visible citation text. | unit | `uv run pytest tests/rag/test_block_chunker.py -q` | no, W0 | pending |
| 21-02-03 | 02 | 1 | PROV-02 | T21-05 | Chunks store ordered source-block refs without changing evidence identity. | unit | `uv run pytest tests/rag/test_block_chunker.py -q` | no, W0 | pending |
| 21-02-04 | 02 | 1 | CHUNK-03 | T21-04 | `search_text` enrichment never mutates content or text hash. | regression | `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_text_hash.py -q` | partial | pending |
| 21-02-05 | 02 | 1 | CHUNK-04 | T21-08 | Version bumps ignore parser trace-only metadata. | unit | `uv run pytest tests/test_ingestion.py -q` | partial | pending |
| 21-02-06 | 02 | 1 | INGEST-02 | T21-03 | Parse/OCR/chunk/embed finish before the short write transaction. | unit | `uv run pytest tests/test_ingestion.py -q` | partial | pending |
| 21-02-07 | 02 | 1 | INGEST-03 | T21-03 | Parse/OCR/embed/DB failures leave prior committed chunks and blocks intact. | unit | `uv run pytest tests/test_ingestion.py tests/rag/test_ingestion_jobs.py -q` | partial | pending |
| 21-03-01 | 03 | 2 | SRC-03 | T21-01/T21-03 | PDF parser handles digital text/tables and scanned fallback safely. | fixture | `uv run pytest tests/rag/test_pdf_parser.py -q` | no, W0 | pending |
| 21-03-02 | 03 | 2 | SRC-04 | T21-01 | DOCX parser emits logical blocks and never fakes page/bbox. | fixture | `uv run pytest tests/rag/test_docx_parser.py -q` | no, W0 | pending |
| 21-03-03 | 03 | 2 | SRC-05 | T21-03 | Image OCR emits text, bbox, language, engine, timeout/error, and confidence. | fixture | `uv run pytest tests/rag/test_ocr_parser.py -q` | no, W0 | pending |
| 21-03-04 | 03 | 2 | OCR-01 | T21-07 | OCR confidence stays metadata and never replaces retrieval confidence. | regression | `uv run pytest tests/rag/test_ocr_parser.py tests/knowledge/test_hybrid_retrieval.py -q` | partial | pending |
| 21-03-05 | 03 | 2 | OCR-02 | T21-03 | Low-confidence OCR is rejected, quarantined, or marked review-needed deterministically. | fixture | `uv run pytest tests/rag/test_ocr_parser.py -q` | no, W0 | pending |
| 21-03-06 | 03 | 2 | SAFE-01 | T21-01/T21-02/T21-03 | Unsafe or malformed files fail with safe reports before DB mutation. | security | `uv run pytest tests/rag/test_ingestion_safety.py -q` | no, W0 | pending |
| 21-04-01 | 04 | 3 | PROV-03 | T21-05 | Provenance lookup validates tenant and evidence hash before returning locators. | unit | `uv run pytest tests/knowledge/test_provenance_lookup.py -q` | no, W0 | pending |
| 21-04-02 | 04 | 3 | PROV-04 | T21-07 | Block IDs cannot authorize evidence, approvals, memory, actions, replay, or business facts. | architecture | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_memory_evidence_boundary.py -q` | partial | pending |
| 21-04-03 | 04 | 3 | SAFE-02 | T21-04/T21-08 | Parser/OCR raw payloads and hidden instructions do not reach prompts or authority surfaces. | security | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/context/test_assembler.py -q` | partial | pending |
| 21-04-04 | 04 | 3 | SAFE-03 | T21-06 | Business artifacts and Tool System outputs cannot become policy chunks. | security | `uv run pytest tests/rag/test_ingestion_safety.py tests/agent/test_policy_retrieval_ownership.py -q` | partial | pending |
| 21-04-05 | 04 | 3 | INGEST-01 | T21-08 | Job traces persist safe checksum/version/status/warning/count/timing fields only. | unit | `uv run pytest tests/rag/test_ingestion_jobs.py -q` | no, W0 | pending |
| 21-04-06 | 04 | 3 | BOUNDARY-01 | T21-07 | Evidence projection, snapshots, replay, and text hashing remain compatible. | regression | `uv run pytest tests/knowledge/test_evidence_projection.py tests/knowledge/test_text_hash.py tests/approvals/test_snapshots.py tests/replay/test_replay_migration_contract.py -q` | yes | pending |
| 21-04-07 | 04 | 3 | BOUNDARY-02 | T21-07 | Hybrid filters, RRF ordering, and normalized confidence remain unchanged. | regression | `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_hybrid_schema.py -q` | yes | pending |
| 21-04-08 | 04 | 3 | BOUNDARY-03 | T21-04/T21-07 | Parser/OCR trace and provenance stay internal/debug/eval only. | architecture | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_graph.py -q` | partial | pending |

---

## Wave 0 Requirements

- [ ] `tests/rag/test_parser_contract.py` - stubs for SRC-01 and SRC-02.
- [ ] `tests/rag/test_document_block_schema.py` - stubs for PROV-01 and INGEST-04 static schema assertions.
- [ ] `tests/rag/test_block_chunker.py` - stubs for CHUNK-01, CHUNK-02, and PROV-02.
- [ ] `tests/rag/test_pdf_parser.py` - stubs for SRC-03 and table PDF fixtures.
- [ ] `tests/rag/test_docx_parser.py` - stubs for SRC-04 and DOCX table fixtures.
- [ ] `tests/rag/test_ocr_parser.py` - stubs for SRC-05, OCR-01, and OCR-02.
- [ ] `tests/rag/test_ingestion_safety.py` - stubs for SAFE-01, SAFE-02, and SAFE-03.
- [ ] `tests/rag/test_ingestion_jobs.py` - stubs for INGEST-01 and INGEST-03.
- [ ] `tests/knowledge/test_provenance_lookup.py` - stubs for PROV-03.
- [ ] `tests/knowledge/test_phase21_boundaries.py` - stubs for PROV-04, BOUNDARY-03, and BOUNDARY-04.
- [ ] `tests/test_rag_production_migration.py` - stubs for INGEST-04 migration upgrade/downgrade/reupgrade.

Existing pytest infrastructure covers this phase; Wave 0 adds missing target files and failing/skip-safe stubs before implementation.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Native Chinese OCR language data availability | SRC-05, OCR-02 | Local Tesseract is present, but `chi_sim` traineddata may be absent in developer/CI environments. | Run `tesseract --list-langs | grep -E '^(chi_sim|eng)$'`; install `chi_sim` or confirm OCR tests fail/skip with an explicit dependency message. |
| Optional disposable DB migration round trip | INGEST-04 | Requires a live disposable PostgreSQL test database. | Run Alembic upgrade to head, downgrade to `014_rag_hybrid_retrieval`, and re-upgrade; verify no source-block/job/provenance structures remain after downgrade. |

All other phase behaviors must have automated pytest or static validation.

---

## Validation Sign-Off

- [x] All requirements have automated verification commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing test-file references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 90 seconds for slice tests.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-18 for planning; Wave 0 remains implementation-owned.
