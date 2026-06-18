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
- **For every implementation task that removes Wave 0 scaffolds:** Run the slice-specific command with `-rxX` and confirm no completed requirement still appears as an implementation-pending xfail.
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

Task IDs in this table are actual PLAN task owners plus a sub-behavior suffix. The `Plan Wave` column uses the real `wave:` value from each PLAN frontmatter.

| Owner Task / Behavior | Plan | Plan Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Scaffold Status | Status |
|-----------------------|------|-----------|-------------|------------|-----------------|-----------|-------------------|-----------------|--------|
| 21-01-01/parser-registry | 01 | 2 | SRC-01 | T21-01 | Parser registry routes only allowlisted source types into project DTOs. | unit | `uv run pytest tests/rag/test_parser_contract.py -q` | W0 scaffold | pending |
| 21-01-01/parser-dto | 01 | 2 | SRC-02 | T21-08 | Parser DTOs expose deterministic order, failure codes, warnings, and versions. | unit | `uv run pytest tests/rag/test_parser_contract.py -q` | W0 scaffold | pending |
| 21-01-01/source-guards | 01 | 2 | SAFE-01 | T21-01/T21-02/T21-03 | Source guards reject unsafe, spoofed, oversized, malformed, or unsupported inputs before parser execution. | security | `uv run pytest tests/rag/test_ingestion_safety.py -q` | W0 scaffold | pending |
| 21-01-01/business-artifact-guard | 01 | 2 | SAFE-03 | T21-06 | Business artifact source types are rejected before becoming policy parser inputs. | security | `uv run pytest tests/rag/test_ingestion_safety.py -q` | W0 scaffold | pending |
| 21-01a-01/source-block-schema | 01a | 3 | PROV-01 | T21-05 | `DocumentBlock` rows are tenant/document scoped and migration-backed. | schema | `uv run pytest tests/rag/test_document_block_schema.py -q` | W0 scaffold | pending |
| 21-01a-01/migration-rollback | 01a | 3 | INGEST-04 | T21-02 | Source-block, job, document fingerprint, and chunk-provenance structures downgrade in dependency-safe order. | migration | `uv run pytest tests/test_rag_production_migration.py -q` | W0 scaffold | pending |
| 21-01a-02/evidence-compat | 01a | 3 | BOUNDARY-01 | T21-07 | Evidence projection, snapshots, replay, and text hashing remain compatible. | regression | `uv run pytest tests/knowledge/test_evidence_projection.py tests/knowledge/test_text_hash.py tests/approvals/test_snapshots.py tests/replay/test_replay_migration_contract.py -q` | existing + W0 | pending |
| 21-01a-02/scope-guard | 01a | 3 | BOUNDARY-04 | T21-07 | Phase 22/23/RAG-5 deliverables are absent while current v1.3 compatibility names remain allowed. | static | `uv run pytest tests/knowledge/test_phase21_boundaries.py -q` | W0 scaffold | pending |
| 21-02-01/chunk-content | 02 | 4 | CHUNK-01 | T21-07 | `PolicyChunk.content` is faithful visible source text and chunk identity remains stable. | unit | `uv run pytest tests/rag/test_block_chunker.py tests/test_chunker.py -q` | partial + W0 | pending |
| 21-02-01/table-chunking | 02 | 4 | CHUNK-02 | T21-04 | Table chunks preserve headers, rows, cells, and visible citation text. | unit | `uv run pytest tests/rag/test_block_chunker.py -q` | W0 scaffold | pending |
| 21-02-01/chunk-provenance | 02 | 4 | PROV-02 | T21-05 | Chunks store ordered source-block refs without changing evidence identity. | unit | `uv run pytest tests/rag/test_block_chunker.py -q` | W0 scaffold | pending |
| 21-02-02/transaction-order | 02 | 4 | INGEST-02 | T21-03 | Parse/OCR/chunk/embed finish before the short document write transaction. | unit | `uv run pytest tests/test_ingestion.py -q` | partial | pending |
| 21-02-02/rollback | 02 | 4 | INGEST-03 | T21-03 | Parse/OCR/embed/DB failures leave prior committed chunks, blocks, and source refs intact. | unit | `uv run pytest tests/test_ingestion.py tests/rag/test_ingestion_jobs.py -q` | partial + W0 | pending |
| 21-02-03/search-text | 02 | 4 | CHUNK-03 | T21-04 | `search_text` enrichment never mutates content or text hash. | regression | `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_text_hash.py -q` | partial | pending |
| 21-02-03/versioning | 02 | 4 | CHUNK-04 | T21-08 | Version bumps ignore parser trace-only metadata and use dedicated fingerprint storage. | unit | `uv run pytest tests/test_ingestion.py -q` | partial | pending |
| 21-03-01/runtime-safety | 03 | 5 | SAFE-01 | T21-01/T21-02/T21-03 | Parser/OCR dependencies, runtime preflight, and file safety validation enforce Phase 21 limits. | security | `uv run pytest tests/rag/test_ingestion_safety.py tests/rag/test_ocr_parser.py -q` | W0 scaffold | pending |
| 21-03-02/image-ocr | 03 | 5 | SRC-05 | T21-03 | Image OCR emits text, bbox, language, engine, timeout/error, and confidence. | fixture | `uv run pytest tests/rag/test_ocr_parser.py -q` | W0 scaffold | pending |
| 21-03-02/ocr-confidence-metadata | 03 | 5 | OCR-01 | T21-07 | OCR confidence stays source-block/chunk metadata and never replaces retrieval confidence. | regression | `uv run pytest tests/rag/test_ocr_parser.py tests/knowledge/test_hybrid_retrieval.py -q` | partial + W0 | pending |
| 21-03-02/ocr-confidence-gates | 03 | 5 | OCR-02 | T21-03 | Low-confidence OCR is rejected, quarantined, or marked review-needed deterministically. | fixture | `uv run pytest tests/rag/test_ocr_parser.py -q` | W0 scaffold | pending |
| 21-03-03/pdf-adapter | 03 | 5 | SRC-03 | T21-01/T21-03 | PDF parser handles digital text, tables, coordinates, and scanned fallback through the OCR adapter. | fixture | `uv run pytest tests/rag/test_pdf_parser.py -q` | W0 scaffold | pending |
| 21-03-03/docx-adapter | 03 | 5 | SRC-04 | T21-01 | DOCX parser emits logical blocks and never fakes page/bbox. | fixture | `uv run pytest tests/rag/test_docx_parser.py -q` | W0 scaffold | pending |
| 21-04-01/provenance-lookup | 04 | 6 | PROV-03 | T21-05 | Provenance lookup validates tenant and evidence hash before returning locators. | unit | `uv run pytest tests/knowledge/test_provenance_lookup.py -q` | W0 scaffold | pending |
| 21-04-02/safe-job-report | 04 | 6 | INGEST-01 | T21-08 | Job traces persist safe checksum/version/status/warning/count/timing fields only, including early failures. | unit | `uv run pytest tests/rag/test_ingestion_jobs.py -q` | W0 scaffold | pending |
| 21-04-02/raw-payload-report-boundary | 04 | 6 | SAFE-02 | T21-04/T21-08 | Safe reports reject raw payloads, parser dumps, stack traces, hidden instructions, and local paths. | security | `uv run pytest tests/rag/test_ingestion_jobs.py tests/rag/test_ingestion_safety.py -q` | partial + W0 | pending |
| 21-04a-01/provenance-authority-boundary | 04a | 7 | PROV-04 | T21-07 | Block IDs cannot authorize evidence, approvals, memory, actions, replay, or business facts. | architecture | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_memory_evidence_boundary.py -q` | partial | pending |
| 21-04a-01/prompt-api-memory-boundary | 04a | 7 | BOUNDARY-03 | T21-04/T21-07 | Parser/OCR trace and provenance stay internal/debug/eval only. | architecture | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_graph.py -q` | partial | pending |
| 21-04a-01/hybrid-regression | 04a | 7 | BOUNDARY-02 | T21-07 | Hybrid filters, RRF ordering, and normalized confidence remain unchanged. | regression | `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_hybrid_schema.py -q` | existing | pending |

---

## Xfail Owner Discipline

Wave 0 may use strict xfail only for behavior whose target implementation does not exist yet. Every implementation-pending xfail must:

- include `owner_task=21-XX-YY` in the xfail reason;
- have a matching entry in `tests/rag/phase21_xfail_inventory.py` under `PHASE21_XFAIL_OWNERS`;
- be removed by the owning plan when that behavior is implemented;
- be checked with `pytest -rxX` in the owning plan's verification output.

Existing v1.3 regression tests for `EvidenceRefV1`, canonical evidence projection, text hashing, approval snapshots, replay, and hybrid retrieval must never be xfailed by Phase 21.

Final closure requires `PHASE21_XFAIL_OWNERS` to contain no implementation-pending owner entries and `rg -n "target code absent|owner_task=21-|xfail" tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_production_migration.py` to show no implementation-pending xfails. Dependency-only skips or xfails, such as missing native `chi_sim` data, must name the missing dependency explicitly.

---

## Cross-Surface Requirement Checklists

These cross-cutting requirements are not satisfied by frontmatter coverage alone. Final acceptance must record each surface as `scaffolded`, `implemented`, `regression-locked`, or `accepted`.

### SAFE-02 - Untrusted Parser/OCR Text Isolation

| Surface | Expected Gate |
|---------|---------------|
| parser adapters | Hidden PDF text, DOCX comments, raw parser dumps, debug OCR payloads, and control-character instructions do not enter `ParsedBlock.text` or `DocumentBlock.text`; they become safe warning codes. |
| `DocumentBlock` persistence | `text` is bounded faithful visible text only; `normalized_text` is bounded internal retrieval/chunking text, not prompt/public evidence authority. |
| job report | `build_safe_ingestion_report(...)` allows only safe status/checksum/version/warning/count/timing fields and rejects raw/stack/path/parser dump keys recursively. |
| API evidence | Public evidence schemas contain canonical `EvidenceRefV1` data only, not source-block IDs, parser/OCR metadata, locators, or normalized text. |
| prompt assembler | Hidden instruction fixtures and raw parser payloads do not appear in serialized prompt/context state. |
| memory/action/replay | Parser/OCR text and provenance metadata do not become memory authority, action authority, replay authority, or business facts. |

### PROV-04 - Provenance Is Subordinate To Canonical Evidence

| Surface | Expected Gate |
|---------|---------------|
| `EvidenceRefV1` | Field set remains unchanged and excludes source-block IDs, locators, parser metadata, OCR metadata, and ingestion job IDs. |
| approval snapshots | Hash projection stays based on canonical evidence content/ref fields only. |
| memory | Source-block/provenance metadata cannot authorize or replace canonical policy evidence. |
| action/replay | Approval/action/replay payloads cannot treat `DocumentBlock` IDs or parser metadata as authority. |
| tools/business facts | Tool System outputs and business fact refs cannot be inserted into policy RAG evidence. |

### BOUNDARY-03 - Parser/OCR Trace Is Internal Debug/Eval Only

| Surface | Expected Gate |
|---------|---------------|
| `PolicyDocument.parser_metadata_json` | Trace/debug only; never stores `policy_version_fingerprint` and never drives version bump. |
| `PolicyDocument.policy_version_fingerprint` | Dedicated internal field for canonical citation text plus semantic policy metadata fingerprint. |
| internal provenance lookup | Requires tenant and evidence text-hash validation before returning safe locators. |
| API response schemas | No public evidence response includes parser/OCR trace, block IDs, or arbitrary normalized/raw parser text. |
| context/prompt/memory | Parser/OCR trace does not enter prompt, memory, action, or replay authority surfaces. |
| final scope guard | Allows current v1.3 `query_rewrite`/rerank compatibility names but forbids new Phase 23-style services, interfaces, cross-encoders, Vespa/OpenSearch, or full `SearchBackend`. |

---

## Wave 0 Requirements

- [ ] `tests/rag/phase21_xfail_inventory.py` - owner-task inventory for implementation-pending strict xfails.
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
