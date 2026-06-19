---
phase: 21-rag-production-ingestion-ocr
verified: 2026-06-19T00:29:09Z
status: passed
score: 33/33 must-haves verified
overrides_applied: 0
post_dependency_gate_utc: 2026-06-19T04:07:57Z
dependency_only_statuses: []
---

# Phase 21: RAG Production Ingestion + OCR Verification Report

**Phase Goal:** Policy maintainers can ingest real policy source files with parser/OCR traceability and source-block provenance, while users continue receiving canonical `EvidenceRefV1` policy evidence through the existing v1.3 hybrid retrieval path.
**Verified:** 2026-06-19T00:29:09Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Maintainer can ingest Markdown/plain text, PDF, DOCX, image, and scanned-PDF policy sources through project-owned parser DTOs and receive deterministic parser/OCR status, warnings, safe failure codes, counts, timings, and version metadata. | VERIFIED | `src/rag/parsers/base.py` defines project DTOs; `src/rag/parsers/registry.py` registers Markdown/plain/PDF/DOCX/image adapters by default; native adapters in `pdf.py`, `docx.py`, `image.py`, `ocr.py` return `ParseResult`/`ParsedBlock`; ingestion job traces are persisted and reported safely. Tests: focused Phase 21 suite 191 passed; parser/PDF/DOCX/OCR/job tests present and passing; post-dependency OCR preflight reports `chi_sim+eng` available. |
| 2 | Retrieved policy evidence still uses schema-compatible `EvidenceRefV1`, canonical citation text, stable content hashes, v1.3 dense/sparse/fuzzy filters, RRF ordering, and normalized evidence confidence. | VERIFIED | `src/knowledge/schemas.py` keeps `EvidenceRefV1` shape; `src/knowledge/retrieval.py` still builds canonical refs from chunk content and uses dense/sparse/fuzzy, RRF, and normalized confidence. Tests cover text hash isolation, hybrid retrieval, evidence projection, and boundary serialization. |
| 3 | Maintainer can resolve a retrieved evidence ref to tenant-scoped source-block provenance after content/hash validation, including page, bbox, table row/cell, parser metadata, and OCR confidence when metadata exists. | VERIFIED | `PolicyKnowledgeService.get_verified_evidence_provenance(...)` validates tenant UUID, unique keys, ref tenant, content presence, and `evidence_text_hash` before fetching provenance; `PolicyChunkRepository.get_provenance_by_evidence_keys(...)` expands ordered source refs through tenant/doc-scoped `DocumentBlock` rows. Tests verify page/bbox/table/OCR locators and hash/tenant failure cases. |
| 4 | Table and OCR-derived chunks preserve faithful visible citation text, row/header/cell context, retrieval-only `search_text` enrichment, and deterministic low-confidence OCR quarantine or review-needed behavior. | VERIFIED | `chunk_blocks(...)` derives chunk content from visible block text and ordered source refs; table chunking repeats headers and preserves row/cell metadata; `build_policy_chunk_search_text(...)` enriches retrieval text without mutating content/hash; OCR thresholds classify accepted/review/rejected at 80/55 boundaries. Tests cover block chunking, table metadata, search text, OCR confidence, and retrieval score isolation. |
| 5 | Failed parsing, OCR timeout, embedding mismatch, DB insert failure, malformed or unsafe files, business-artifact inputs, and migration downgrade/reupgrade leave prior committed policy versions, chunks, blocks, retrieval behavior, and safety boundaries intact. | VERIFIED | `IngestionService.ingest_document(...)` parses/chunks/embeds before the locked write, rolls back DB failures, restores document snapshots, and records sanitized failed jobs; source guards reject unsafe/malformed/business inputs. Migration static tests assert dependency-safe downgrade and Phase 20 hybrid preservation. Post-dependency full pytest passed with no skipped tests. |

**Score:** 33/33 must-haves verified (5/5 ROADMAP success criteria plus 28/28 plan-level truth rollup).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/rag/parsers/base.py`, `registry.py`, `markdown.py`, `plain_text.py`, `safety.py` | Project-owned parser DTOs, registry, logical text adapters, guards | VERIFIED | Exist, substantive, imported by ingestion/tests; default registry routes supported policy sources and rejects business artifacts. |
| `src/rag/parsers/pdf.py`, `docx.py`, `image.py`, `ocr.py`, `runtime.py` | PDF/DOCX/image/OCR adapters and runtime preflight | VERIFIED | Exist, substantive, registered by default; PDF uses OCR fallback for scanned pages; OCR runtime preflight reports `chi_sim+eng` available after dependency gate execution. |
| `src/db/models.py`, `src/db/migrations/versions/015_rag_production_ingestion_ocr.py` | Source-block/job/provenance schema and rollback | VERIFIED | `DocumentBlock`, nullable pre-document `RagIngestionJob.doc_id`, chunk source refs/OCR JSONB, and dedicated fingerprint fields exist; static migration tests pass. |
| `src/repositories/document_block_repo.py`, `rag_ingestion_job_repo.py`, `policy_chunk_repo.py` | Tenant-scoped block/job/provenance repositories | VERIFIED | Queries include tenant scope; validation rejects unsafe parser/OCR trace fields; chunk provenance expands through block rows. |
| `src/rag/chunker.py`, `src/rag/search_text.py`, `src/rag/versioning.py`, `src/rag/ingestion.py` | Block-aware chunking, retrieval-only enrichment, fingerprinting, atomic ingestion | VERIFIED | Chunks preserve visible content and source refs; embeddings use enriched search text; parser trace-only metadata does not bump versions; rollback tests pass. |
| `src/knowledge/provenance.py`, `src/knowledge/service.py`, `src/knowledge/retrieval.py`, `src/knowledge/schemas.py`, `src/replay/validators.py` | Verified provenance lookup and boundary preservation | VERIFIED | Provenance is internal side path; `EvidenceRefV1` remains canonical; replay redacted payloads reject Phase 21 provenance/parser/OCR keys. |
| Phase 21 tests and acceptance docs | Automated coverage and final evidence | VERIFIED | `tests/rag/*`, `tests/knowledge/test_phase21_boundaries.py`, `tests/knowledge/test_provenance_lookup.py`, `tests/test_ingestion.py`, and `tests/test_rag_production_migration.py` all exist and pass in focused/full gates. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Parser registry | Native adapters | `ParserRegistry._register_native_adapters()` | WIRED | PDF, DOCX, and image adapters are registered by default, correcting the known 21-03 risk. |
| Parser adapters | `chunk_blocks(...)` | `IngestionService` parses then passes `ParsedBlock` tuples to `chunk_blocks` | WIRED | Parser DTOs feed block-aware chunking before embedding and DB writes. |
| PDF parser | OCR adapter | Scanned-page branch renders with `pypdfium2` then calls `OcrEngine.parse_image(...)` | WIRED | Scanned PDF fallback exists and tests verify PDF-point box conversion. |
| Ingestion | DB blocks/chunks/jobs | `DocumentBlockRepository`, `PolicyChunkRepository`, `RagIngestionJobRepository` | WIRED | Blocks and chunks are deleted/inserted in the write transaction; job success/failure is updated with sanitized fields. |
| Retrieval evidence | Provenance lookup | `get_verified_evidence_provenance(...)` then repository provenance expansion | WIRED | Tenant, duplicate-key, content, and hash checks happen before locator expansion. |
| Replay boundary | Phase 21 metadata keys | `FORBIDDEN_REDACTED_PAYLOAD_KEYS` | WIRED | Redacted payloads reject `source_block_id`, parser metadata, OCR metadata, and raw parser payload keys, correcting the known 21-04a risk. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/rag/ingestion.py` | `parse_result.blocks` -> `chunks` -> `db_blocks`/`db_chunks` | Parser registry, `chunk_blocks`, embedder, repositories | Yes | FLOWING |
| `src/repositories/policy_chunk_repo.py` | `source_block_refs_json` -> `EvidenceProvenance.source_locators` | Policy chunk rows plus tenant/doc-scoped `DocumentBlock` rows | Yes | FLOWING |
| `src/knowledge/service.py` | verified refs -> provenance map | Content lookup and hash validation before provenance lookup | Yes | FLOWING |
| `src/knowledge/retrieval.py` | `EvidenceRefV1` output | Hybrid retrieval hits using `PolicyChunk.content` | Yes | FLOWING |
| `src/rag/parsers/runtime.py` | OCR runtime status | Local `tesseract --list-langs` preflight | Yes, `chi_sim+eng` available after dependency gate execution | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 21 suite | `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q` | 191 passed, 1 warning in 4.35s | PASS |
| Full pytest gate | `MOCA_TEST_DATABASE_URL=... uv run pytest -q --tb=short -rs` against disposable `pgvector/pgvector:pg16` | 1136 passed, 9 warnings in 543.23s | PASS |
| Ruff gate | `uv run ruff check src tests` | All checks passed | PASS |
| Migration + OCR dependency gates | `MOCA_TEST_DATABASE_URL=... uv run pytest tests/test_rag_production_migration.py tests/rag/test_ocr_parser.py tests/rag/test_pdf_parser.py -q -rs` against disposable `pgvector/pgvector:pg16` | 28 passed, 4 warnings in 1.32s | PASS |
| OCR runtime preflight | `uv run python -c "from src.rag.parsers.runtime import check_ocr_runtime; ..."` | `available=True`, `failure_code=None`, `missing_languages=()`, version `tesseract 5.5.2` | PASS |
| Xfail inventory | `uv run python -c "from tests.rag.phase21_xfail_inventory import PHASE21_XFAIL_OWNERS; ..."` plus scoped `rg` | `PHASE21_XFAIL_OWNERS={}`, count 0; scoped xfail grep no matches | PASS |
| Final scope guard | `uv run pytest tests/knowledge/test_phase21_boundaries.py -q` | 13 passed, 1 warning | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| SRC-01 | 21-01, 21-03, 21-05a | Parser registry routes supported policy source formats through project DTOs | SATISFIED | Registry and default native adapters; `test_parser_registry_registers_native_adapters_by_default`. |
| SRC-02 | 21-01, 21-05a | Parser outputs deterministic block fields, warnings, failure codes | SATISFIED | Parser DTOs and parser contract tests. |
| SRC-03 | 21-03, 21-05 | PDF page/table extraction and scanned fallback | SATISFIED | `PdfParser`, OCR fallback, PDF parser tests. |
| SRC-04 | 21-03, 21-05 | DOCX paragraphs/headings/tables without fake page/bbox | SATISFIED | `DocxParser`, DOCX tests. |
| SRC-05 | 21-03, 21-05a | Image OCR status, bbox, language, version, timeout/error, confidence | SATISFIED | `ImageOcrParser`, `OcrEngine`, OCR tests; live `chi_sim+eng` preflight passed. |
| PROV-01 | 21-01a, 21-05a | Durable tenant/document scoped source blocks | SATISFIED | ORM/migration/repository tests. |
| PROV-02 | 21-02, 21-05a | Ordered source-block provenance on chunks | SATISFIED | `source_block_refs_json`, chunker and provenance tests. |
| PROV-03 | 21-04, 21-05 | Verified tenant/hash provenance lookup | SATISFIED | Service/repository implementation and provenance tests. |
| PROV-04 | 21-01a, 21-04a, 21-05 | Blocks cannot become authority surfaces | SATISFIED | Boundary tests across evidence/API/approval/action/replay/memory/business surfaces. |
| CHUNK-01 | 21-02, 21-05a | Faithful visible chunk content and stable IDs | SATISFIED | Block chunker tests. |
| CHUNK-02 | 21-02, 21-03, 21-05a | Table row/header/cell context | SATISFIED | Block/PDF/DOCX table tests. |
| CHUNK-03 | 21-02, 21-05a | Retrieval-only search text enrichment | SATISFIED | Search text and text-hash tests. |
| CHUNK-04 | 21-02, 21-05a | Version changes only on canonical content/semantics metadata | SATISFIED | Versioning and ingestion tests. |
| OCR-01 | 21-01a, 21-02, 21-03, 21-05a | OCR confidence stays metadata, not retrieval score | SATISFIED | OCR and hybrid retrieval tests. |
| OCR-02 | 21-03, 21-05, 21-05a | Deterministic OCR thresholds | SATISFIED | OCR confidence boundary tests; live `chi_sim+eng` preflight passed. |
| SAFE-01 | 21-01, 21-03, 21-05 | Source type/signature/size/page/image/zip/malformed/timeout safety | SATISFIED | Safety tests and parser runtime deadline tests. |
| SAFE-02 | 21-04, 21-04a, 21-05 | Untrusted parser/OCR text excluded from authority surfaces | SATISFIED | Safe report, prompt/API/memory/action/replay boundary tests. |
| SAFE-03 | 21-01, 21-04a, 21-05 | Business artifacts rejected as policy sources | SATISFIED | Source guard, ingestion rollback, and ownership tests. |
| INGEST-01 | 21-01a, 21-04, 21-05a | Safe parser/OCR job trace | SATISFIED | Job model/repo, job report, pre-document failure tests. |
| INGEST-02 | 21-02, 21-05a | Parse/OCR/chunk/embed before write transaction | SATISFIED | Event-order ingestion job tests. |
| INGEST-03 | 21-02, 21-03, 21-05 | Failures leave prior committed evidence intact | SATISFIED | Adversarial rollback tests. |
| INGEST-04 | 21-01a, 21-05, 21-05a | Migration upgrade/downgrade/reupgrade coverage | SATISFIED | Static migration tests pass; live DB downgrade/reupgrade passed against disposable `pgvector/pgvector:pg16`. |
| BOUNDARY-01 | 21-01a, 21-04a, 21-05 | EvidenceRef/projection/snapshot/replay/hash compatibility | SATISFIED | Boundary, evidence projection, text hash, replay, full-suite tests. |
| BOUNDARY-02 | 21-02, 21-04a, 21-05a | Hybrid retrieval filters/RRF/confidence intact | SATISFIED | Hybrid retrieval tests. |
| BOUNDARY-03 | 21-01a, 21-04, 21-04a, 21-05 | Parser/OCR/provenance internal by default | SATISFIED | API/prompt/memory/action/replay boundary tests. |
| BOUNDARY-04 | 21-01a, 21-04a, 21-05 | No Phase 22/23/RAG-5 deliverables | SATISFIED | Static scope guard; roadmap has no later active phase deferrals. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| Multiple implementation/test files | Various | Empty return/empty collection matches from guard paths, fakes, and accumulator initialization | INFO | Reviewed as non-stub patterns; no user-visible placeholder, orphaned implementation, or console-only behavior found. |

### Resolved Dependency Gates

| Item | Status | Evidence | Residual Risk |
|---|---|---|---|
| Native Simplified Chinese OCR data | Resolved locally | Preflight reports `available=True`, `failure_code=None`, `missing_languages=()`, version `tesseract 5.5.2`; `tests/rag/test_ocr_parser.py` and `tests/rag/test_pdf_parser.py` passed. | Runtime/CI must keep `chi_sim` traineddata installed. |
| Live DB migration round trip | Resolved locally | `tests/test_rag_production_migration.py` ran against disposable `pgvector/pgvector:pg16`; no skip remained in the full pytest gate. | Runtime/CI needs pgvector-capable PostgreSQL for this live gate. |

### Gaps Summary

No implementation gaps found. The known orchestrator corrections were verified in code and tests: `RagIngestionJob.doc_id` is nullable for pre-document failures, DB-available first-import parser/OCR failures persist sanitized traces, the default parser registry registers PDF/DOCX/image adapters, and replay redacted payloads reject Phase 21 provenance/parser/OCR keys.

---

_Verified: 2026-06-19T00:29:09Z_
_Verifier: Claude (gsd-verifier)_
