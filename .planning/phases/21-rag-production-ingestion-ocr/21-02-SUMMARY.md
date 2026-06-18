---
phase: 21-rag-production-ingestion-ocr
plan: 02
subsystem: rag
tags: [rag, ingestion, chunking, provenance, versioning, search-text]

requires:
  - phase: 21-rag-production-ingestion-ocr
    provides: "Plan 21-01a schema columns and repositories for document blocks, chunk provenance, ingestion jobs, and policy version fingerprints."
provides:
  - "Block-aware chunking with ordered source-block refs and table row/header context."
  - "Parser-aware ingestion that preflights parse/chunk/embed before locked document replacement."
  - "Retrieval-only search_text enrichment and semantic policy version fingerprints."
affects: [rag, ingestion, policy-evidence, hybrid-retrieval, phase-21]

tech-stack:
  added: []
  patterns:
    - "PolicyChunk.content remains faithful visible citation text; source/table context is search_text-only."
    - "PolicyDocument.version is driven by policy_version_fingerprint with a legacy no-fingerprint content fallback."
    - "Repository helpers remain transaction-neutral; IngestionService owns commits and rollbacks."
    - "RagIngestionJob.doc_id is nullable only for pre-document failure trace rows; successful jobs and existing-document failures bind to PolicyDocument.id."

key-files:
  created:
    - src/rag/versioning.py
  modified:
    - src/rag/chunker.py
    - src/rag/search_text.py
    - src/rag/ingestion.py
    - src/db/models.py
    - src/db/migrations/versions/015_rag_production_ingestion_ocr.py
    - tests/rag/phase21_xfail_inventory.py
    - tests/rag/test_block_chunker.py
    - tests/rag/test_search_text.py
    - tests/test_ingestion.py
    - tests/rag/test_ingestion_jobs.py
    - tests/knowledge/test_text_hash.py

key-decisions:
  - "BlockChunkResult is additive beside ChunkResult so chunk_markdown stable behavior remains unchanged."
  - "Parser/OCR trace metadata is stored only in parser_metadata_json/job/block trace fields; version authority lives only in PolicyDocument.policy_version_fingerprint."
  - "search_text includes heading, table, and source-block context for retrieval, while EvidenceRefV1.text_hash continues to hash chunk.content only."
  - "First-import pre-document failures persist sanitized RagIngestionJob rows with doc_id unset and doc_key populated; DB-unavailable trace failures still return safe job_id=None reports."

patterns-established:
  - "A sanitized job trace row is created before parser preflight; parse, chunk, and embed run before get_by_doc_key_for_update; the locked transaction then replaces document blocks and chunks together."
  - "Early failures update sanitized job status before document lock, including first-import failures with doc_id unset; DB-unavailable trace failures return job_id=None."
  - "Table chunks repeat headers on row-group splits and preserve merged-cell metadata in source-block refs."

requirements-completed:
  - PROV-02
  - CHUNK-01
  - CHUNK-02
  - CHUNK-03
  - CHUNK-04
  - OCR-01
  - INGEST-02
  - INGEST-03
  - BOUNDARY-01
  - BOUNDARY-02
  - BOUNDARY-03

duration: "19 min"
completed: 2026-06-18
---

# Phase 21 Plan 02: Block Aware Chunking And Atomic Ingestion Summary

**Source-block-aware policy chunking with rollback-safe parser ingestion, retrieval-only enrichment, and semantic version fingerprints.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-06-18T17:29:44Z
- **Completed:** 2026-06-18T17:48:44Z
- **Tasks:** 3 completed
- **Files modified:** 10 implementation/test files plus this summary

## Accomplishments

- Added `BlockChunkResult` and `chunk_blocks(...)` while leaving `chunk_markdown(...)` stable.
- Preserved ordered source-block refs with text hashes, bbox/page/OCR/table metadata, table header repetition, and merged-cell metadata.
- Refactored ingestion to parse through `ParserRegistry`, build `DocumentBlock` and `PolicyChunk` rows from parser blocks, and perform document replacement after preflight parse/chunk/embed.
- Added sanitized `RagIngestionJob` status handling around early failures and document-write rollback failures without repository-level commits.
- Added canonical policy version fingerprints over citation text plus title/doc_type/risk/effective_date, excluding parser/OCR trace metadata.
- Extended `search_text` with optional heading/table/source context while preserving `PolicyChunk.content` and `EvidenceRefV1.text_hash` semantics.

## Task Commits

1. **Task 21-02-01: Add block-aware and table-aware chunking**
   - `9c4f5eb` test: add failing block-aware chunking coverage
   - `a7c3a83` feat: add block-aware chunking
2. **Task 21-02-02: Persist source blocks and chunks through an atomic ingestion flow**
   - `7c6e13c` test: add failing atomic ingestion coverage
   - `d5ae198` feat: persist parser-aware ingestion atomically
3. **Task 21-02-03: Implement content-based versioning and retrieval-only enrichment invariants**
   - `7176168` test: add failing versioning invariants
   - `8fd48ea` feat: implement policy version fingerprints

## Files Created/Modified

- `src/rag/chunker.py` - adds block-aware chunk results, ordered source refs, and table-aware row-group splitting.
- `src/rag/ingestion.py` - parser-aware preflight, pre-document job trace creation, document/block/chunk replacement, sanitized job trace handling, and fingerprint-driven versioning.
- `src/db/models.py` - permits `RagIngestionJob.doc_id` to remain unset for pre-document failure rows while keeping `DocumentBlock.doc_id` non-null.
- `src/db/migrations/versions/015_rag_production_ingestion_ocr.py` - aligns the job trace schema with nullable pre-document `doc_id`.
- `src/rag/search_text.py` - optional retrieval-only heading/table/source context.
- `src/rag/versioning.py` - canonical policy version fingerprint helper.
- `tests/rag/test_block_chunker.py` - source ref, visible text, stable ID, and table chunking coverage.
- `tests/test_ingestion.py` - parser-aware ingestion, fingerprint, rollback, and content/search_text invariant coverage.
- `tests/rag/test_ingestion_jobs.py` - preflight ordering, sanitized failure, DB-unavailable trace, and job rollback coverage.
- `tests/rag/test_search_text.py` - retrieval-only enrichment context coverage.
- `tests/knowledge/test_text_hash.py` - EvidenceRef text hash remains chunk-content based.
- `tests/rag/phase21_xfail_inventory.py` - removed only 21-02-owned strict xfail entries.

## Decisions Made

- Kept `chunk_markdown(...)` untouched and added `chunk_blocks(...)` as an additive parser-block path.
- Used `PolicyDocument.policy_version_fingerprint` as the only version authority surface; `parser_metadata_json` remains trace/debug-only.
- Preserved legacy rows without fingerprints by falling back to content comparison on their first 21-02 reimport, then storing the fingerprint.
- Kept search enrichment out of citation content and evidence identity; enrichment is persisted only to `PolicyChunk.search_text`.

## Deviations from Plan

### Resolved Corrective Action

**1. [Rule 4 - Architecture Avoided] First-import early failure job rows initially could not be persisted before a document row existed**
- **Found during:** Task 21-02-02
- **Issue:** Plan 21-02 asks for durable job rows before document replacement, but Plan 21-01a made `RagIngestionJob.doc_id` non-null and FK-scoped to `PolicyDocument`. Persisting a first-import job before a document exists would require a schema change or an invalid FK.
- **Resolution:** Orchestrator review corrected the schema and ingestion flow: `RagIngestionJob.doc_id` is nullable for pre-document trace rows, every ingest attempts a sanitized job trace before parser preflight, and successful new-document imports bind the job row to the created `PolicyDocument.id`.
- **Files modified:** `src/db/models.py`, `src/db/migrations/versions/015_rag_production_ingestion_ocr.py`, `src/rag/ingestion.py`, `tests/rag/test_document_block_schema.py`, `tests/test_rag_production_migration.py`, `tests/rag/test_ingestion_jobs.py`
- **Verification:** Required plan pytest command now passes with first-import early failure persistence coverage; DB-unavailable trace failure still asserts `job_id is None`.
- **Committed in:** `3c1c405`

---

**Total deviations:** 1 resolved corrective action.
**Impact on plan:** Durable sanitized job trace now covers first-import pre-document parser/OCR failures when the DB is available, while DB-unavailable trace failures still return safe in-memory reports.

## Issues Encountered

- Existing ingestion tests assumed only document/chunk repositories; they were updated to inject fake block and job repositories and to assert parser-block citation text.
- Reimport without explicit `effective_date` initially used `date.today()` as semantic metadata; fixed to preserve an existing document effective date unless the manifest supplies a new one.

## Verification

- `uv run pytest tests/rag/test_block_chunker.py tests/test_chunker.py -q` -> 15 passed.
- `uv run pytest tests/test_ingestion.py tests/rag/test_ingestion_jobs.py tests/rag/test_block_chunker.py -q` -> 15 passed, 3 xfailed.
- `uv run pytest tests/test_ingestion.py tests/rag/test_search_text.py tests/knowledge/test_text_hash.py tests/knowledge/test_hybrid_retrieval.py -q` -> 29 passed.
- Required after corrective commit `3c1c405`: `uv run pytest tests/rag/test_block_chunker.py tests/test_chunker.py tests/test_ingestion.py tests/rag/test_search_text.py tests/rag/test_ingestion_jobs.py tests/knowledge/test_text_hash.py tests/knowledge/test_hybrid_retrieval.py -q` -> 51 passed, 2 xfailed.
- Schema/migration guard after corrective commit `3c1c405`: `uv run pytest tests/rag/test_document_block_schema.py tests/test_rag_production_migration.py -q` -> 15 passed.
- `uv run ruff check src/rag/chunker.py src/rag/ingestion.py src/rag/search_text.py src/rag/versioning.py tests/rag/test_block_chunker.py tests/test_ingestion.py tests/rag/test_search_text.py tests/rag/test_ingestion_jobs.py tests/knowledge/test_text_hash.py` -> passed.
- `rg -n "21-02-0[123]" tests/rag/phase21_xfail_inventory.py` -> no matches; later-plan xfails remain.

## Known Stubs

None - stub scan found only typed empty initializers and test fixtures, not unfinished implementation placeholders.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 21-03 can build native PDF/DOCX/image/OCR parser internals on top of the parser-block ingestion path. Plan 21-04 can rely on sanitized job traces for DB-available first-import parser/OCR failures, with `doc_id` populated only after a document row exists.

## Self-Check: PASSED

- Verified key created/modified files exist.
- Verified task commits exist: `9c4f5eb`, `a7c3a83`, `7c6e13c`, `d5ae198`, `7176168`, `8fd48ea`.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18*
