---
phase: 21
slug: rag-production-ingestion-ocr
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-19T03:29:40Z
verified: 2026-06-19T03:29:40Z
post_dependency_gate_utc: 2026-06-19T04:07:57Z
---

# Phase 21 - Security

Per-phase security contract for RAG production ingestion and OCR.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Source file -> parser registry | Maintainer-supplied files and metadata enter allowlisted parser routing. | Untrusted bytes, filename, declared source type, declared MIME, document metadata. |
| Parser/OCR output -> database | Parser and OCR libraries emit text, warnings, geometry, confidence, and failure data that may become durable rows. | Untrusted parser text, OCR text, source locators, parser names/versions, safe failure codes. |
| Document blocks -> policy chunks | Source blocks become canonical chunk text plus retrieval-only enrichment and ordered provenance refs. | Visible citation text, table metadata, OCR metadata, source block ids. |
| Evidence refs -> provenance lookup | Retrieved evidence may request internal locators after tenant/content/hash validation. | `EvidenceRefV1`, chunk content, `DocumentBlock` locator metadata. |
| Job trace -> maintainer report | Durable ingestion jobs are projected into safe diagnostics. | Source checksums, parser/OCR versions, stage/status, warnings, counts, timings, sanitized messages. |
| RAG internals -> prompt/API/memory/action/replay | Phase 21 internal provenance/parser/OCR data must not become authority surfaces. | Evidence refs, public evidence items, prompt snippets, memory, approval/action snapshots, replay payloads. |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T21-01 | Tampering | Parser registry, source safety guards, adapters | mitigate | Allowlist source types, validate extension/signature/MIME before parser execution, and reject unsafe routes with safe failure codes. Evidence: `tests/rag/test_parser_contract.py`, `tests/rag/test_ingestion_safety.py`, parser/PDF/DOCX tests. | closed |
| T21-02 | Denial of Service | File safety, migration | mitigate | Enforce 20MB files, 50 PDF pages, 8000x8000 images, DOCX zip ratio/decompression checks, and dependency-safe migration downgrade/reupgrade. Evidence: `tests/rag/test_ingestion_safety.py`, `tests/test_rag_production_migration.py`. | closed |
| T21-03 | Denial of Service | Parser/OCR runtime, ingestion ordering | mitigate | Lock parser/OCR timeout constants, fail closed on OCR timeout/runtime absence, and finish parse/OCR/chunk/embed before DB mutation. Evidence: `tests/rag/test_ocr_parser.py`, `tests/rag/test_ingestion_jobs.py`, `tests/test_ingestion.py`. | closed |
| T21-04 | Spoofing / Elevation of Privilege | Parser text, OCR text, prompt/API/memory/action/replay boundaries | mitigate | Persist only bounded visible citation text; hidden text, DOCX comments, local paths, raw parser dumps, traceback text, raw OCR payloads, and hidden prompt injection text are stripped, redacted, or projected as warning codes. Evidence: parser sanitizer tests, boundary tests, and W1/W2/W3 Phase 21 fixes. | closed |
| T21-05 | Information Disclosure | Provenance lookup, block repositories | mitigate | Require tenant scope, unique evidence keys, content presence, and `evidence_text_hash(content)` match before returning source locators. Evidence: `tests/knowledge/test_provenance_lookup.py`, `tests/knowledge/test_service.py`. | closed |
| T21-06 | Tampering / Elevation of Privilege | Source guards, business artifact separation | mitigate | Reject business artifacts, Tool System outputs, screenshots, orders, refunds, tickets, and business fact refs as policy source material. Evidence: `tests/rag/test_ingestion_safety.py`, `tests/agent/test_policy_retrieval_ownership.py`. | closed |
| T21-07 | Elevation of Privilege | `DocumentBlock`, chunk refs, public authority surfaces | mitigate | Keep `DocumentBlock` ids subordinate to chunks and prove they cannot authorize evidence, approvals, memory, actions, replay, tools, or business facts. Evidence: `tests/knowledge/test_phase21_boundaries.py`, memory/replay/action tests. | closed |
| T21-08 | Information Disclosure | `RagIngestionJob`, failure handling, safe reports | mitigate | Persist bounded safe job trace data only; sanitize job source types, doc keys, parser identities, failure codes/messages, and revalidate job rows before create/failure/success commits. Evidence: `tests/rag/test_document_block_schema.py`, `tests/rag/test_ingestion_jobs.py`, commits `6ee235b` and `01716e2`. | closed |

## Verification Evidence

| Check | Result |
|-------|--------|
| Focused job trace regression | `uv run pytest tests/rag/test_ingestion_jobs.py tests/rag/test_document_block_schema.py -q` -> `22 passed, 1 warning`. |
| Ruff | `uv run ruff check src tests` -> `All checks passed`. |
| Post-dependency full regression | `MOCA_TEST_DATABASE_URL=... uv run pytest -q --tb=short -rs` against disposable `pgvector/pgvector:pg16` -> `1136 passed, 9 warnings`. |
| Live migration + OCR dependency gates | `MOCA_TEST_DATABASE_URL=... uv run pytest tests/test_rag_production_migration.py tests/rag/test_ocr_parser.py tests/rag/test_pdf_parser.py -q -rs` -> `28 passed, 4 warnings`. |
| OCR runtime preflight | `check_ocr_runtime()` -> `available=True`, `failure_code=None`, `missing_languages=()`, version `tesseract 5.5.2`. |
| Xfail/pending inventory | Scoped Phase 21 xfail/pending search has no implementation-pending matches; `PHASE21_XFAIL_OWNERS={}` in acceptance evidence. |

## Accepted Risks Log

No accepted risks.

Previously dependency-only gates were rerun and resolved locally:

| Dependency | Status | Follow-up |
|------------|--------|-----------|
| Native `chi_sim` OCR traineddata | Installed locally; OCR preflight passes with `chi_sim+eng` available. | Keep `chi_sim` installed in runtime/CI. |
| Optional live DB migration round trip | Passed against disposable `pgvector/pgvector:pg16` PostgreSQL using `MOCA_TEST_DATABASE_URL`. | Keep a pgvector-capable disposable DB available for live migration gates. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By | Evidence |
|------------|---------------|--------|------|--------|----------|
| 2026-06-19 | 8 | 8 | 0 | Codex / gsd-secure-phase | Phase 21 artifacts, focused/broader tests, Ruff, commits `5034232`, `7a6a9d7`, `6ee235b`, `01716e2`. |
| 2026-06-19 | 8 | 8 | 0 | Codex / post-dependency gates | Full pytest with disposable pgvector DB, live migration round trip, OCR parser/PDF parser tests, and `chi_sim+eng` preflight. |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-19
