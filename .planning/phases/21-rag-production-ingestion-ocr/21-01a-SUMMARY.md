---
phase: "21-rag-production-ingestion-ocr"
plan: "01a"
subsystem: database
tags: [rag, ingestion, provenance, sqlalchemy, alembic, postgres, boundaries]

requires:
  - phase: "21-rag-production-ingestion-ocr"
    provides: "21-01 parser contracts, source guards, and Markdown/plain-text adapters"
provides:
  - "Durable DocumentBlock and RagIngestionJob schema with tenant/document scope"
  - "PolicyDocument source metadata and dedicated policy_version_fingerprint field"
  - "PolicyChunk ordered source-block refs and OCR metadata JSONB columns"
  - "Tenant-scoped source-block and ingestion-job repositories"
  - "Evidence/scope boundary tests preserving v1.3 EvidenceRefV1 authority"
affects: [phase-21, rag-ingestion, policy-kb, evidence-boundaries, approvals, replay, memory]

tech-stack:
  added: []
  patterns:
    - "Additive Alembic schema migration with nullable/backfill/alter for existing JSONB chunk metadata"
    - "Tenant-scoped repositories using AsyncSession without independent commits"
    - "Static boundary guards for deferred RAG deliverables and public authority surfaces"

key-files:
  created:
    - "src/db/migrations/versions/015_rag_production_ingestion_ocr.py"
    - "src/repositories/document_block_repo.py"
    - "src/repositories/rag_ingestion_job_repo.py"
  modified:
    - "src/db/models.py"
    - "tests/rag/phase21_xfail_inventory.py"
    - "tests/rag/test_document_block_schema.py"
    - "tests/test_rag_production_migration.py"
    - "tests/knowledge/test_phase21_boundaries.py"

key-decisions:
  - "PolicyDocument.policy_version_fingerprint remains a dedicated nullable column, separate from parser_metadata_json."
  - "PolicyChunk provenance uses ordered JSONB source_block_refs_json plus separate chunk OCR metadata, preserving PolicyChunk.content/search_text and EvidenceRefV1."
  - "DocumentBlock and RagIngestionJob repositories validate unsafe parser/OCR trace text before flush and never commit independently."
  - "Scope guards allow existing v1.3 query_rewrite/rerank compatibility names only at known sites while forbidding new Phase 22/23/RAG-5 implementation surfaces."

patterns-established:
  - "Source-block provenance is subordinate to policy chunks and cannot become public evidence, approval, replay, memory, action, or business-tool authority."
  - "Migration downgrade removes dependent indexes, chunk provenance columns, job table, block table, then policy-document metadata columns."

requirements-completed: [PROV-01, PROV-04, OCR-01, INGEST-01, INGEST-04, BOUNDARY-01, BOUNDARY-03, BOUNDARY-04]

duration: "10 min"
completed: "2026-06-18"
---

# Phase 21 Plan 01a: Source Block Schema Repositories And Boundary Guards Summary

**Tenant-scoped source-block/job persistence with chunk provenance JSONB and strict evidence authority boundary guards**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-18T17:15:04Z
- **Completed:** 2026-06-18T17:24:42Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `DocumentBlock` and `RagIngestionJob` ORM models plus migration `015_rag_production_ingestion_ocr`.
- Added `PolicyDocument` source metadata and dedicated `policy_version_fingerprint`; added `PolicyChunk.source_block_refs_json` and `ocr_metadata_json` without changing evidence schemas.
- Added tenant-scoped repositories for block/job persistence with no independent commits and validation for unsafe raw parser/OCR trace material.
- Tightened Phase 21 boundary tests so deferred Phase 22/23/RAG-5 deliverables fail on implementation surfaces while docs/planning deferrals and v1.3 compatibility names remain allowed.

## Task Commits

1. **Task 21-01a-01: Add source-block, ingestion-job, and chunk provenance schema** - `e7dc1be` (`feat`)
2. **Task 21-01a-02: Lock evidence compatibility and strict scope guards** - `daac6bd` (`test`)

## Files Created/Modified

- `src/db/models.py` - Adds source-block/job ORM models and additive policy/chunk provenance fields.
- `src/db/migrations/versions/015_rag_production_ingestion_ocr.py` - Adds/drops Phase 21 provenance schema in dependency-safe order.
- `src/repositories/document_block_repo.py` - Adds tenant-scoped block delete/insert/query methods and safe text/metadata validation.
- `src/repositories/rag_ingestion_job_repo.py` - Adds tenant-scoped job create/delete/query methods and safe trace validation.
- `tests/rag/test_document_block_schema.py` - Converts 21-01a schema xfails into passing schema/repository safety coverage.
- `tests/test_rag_production_migration.py` - Covers migration revision chain, JSONB backfill style, indexes, fingerprint field, and downgrade order.
- `tests/knowledge/test_phase21_boundaries.py` - Adds evidence/snapshot/replay/memory/business/tool authority boundary checks and precise scope guards.
- `tests/rag/phase21_xfail_inventory.py` - Removes only strict xfail entries whose behavior now passes under 21-01a.

## Decisions Made

- `policy_version_fingerprint` is a first-class `policy_documents` column, not a key inside `parser_metadata_json`.
- `source_block_refs_json` and `ocr_metadata_json` are non-null chunk JSONB fields with ORM defaults; migration uses nullable add, backfill, then alter instead of persistent fake server defaults.
- Repository validation rejects overlong/control-character `DocumentBlock.text`, raw parser/OCR metadata keys, stack traces, local paths, and raw dumps before flush.
- Scope guard tests ignore only guard files that intentionally contain forbidden strings; docs and `.planning/` remain outside implementation scans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed stale strict xfail for now-passing provenance authority boundary**
- **Found during:** Task 21-01a-02 verification
- **Issue:** `test_document_block_ids_are_not_evidence_memory_action_replay_or_business_authority` was still strict-xfailed under a later-plan marker, but the 21-01a implementation made it pass and the xfail became an XPASS failure.
- **Fix:** Removed that one strict xfail marker and its inventory entry while leaving the remaining later-plan prompt/API/memory boundary xfail intact.
- **Files modified:** `tests/knowledge/test_phase21_boundaries.py`, `tests/rag/phase21_xfail_inventory.py`
- **Verification:** `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_evidence_projection.py tests/knowledge/test_hybrid_retrieval.py tests/approvals/test_snapshots.py -q`
- **Committed in:** `daac6bd`

---

**Total deviations:** 1 auto-fixed blocking issue.
**Impact on plan:** The cleanup was required for the 21-01a boundary behavior that now passes. No deferred implementation scope was added.

## Verification

- `uv run pytest tests/rag/test_document_block_schema.py tests/test_rag_production_migration.py -q` - 15 passed
- `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_evidence_projection.py tests/knowledge/test_hybrid_retrieval.py tests/approvals/test_snapshots.py -q` - 35 passed
- `uv run pytest tests/rag/test_document_block_schema.py tests/test_rag_production_migration.py tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_evidence_projection.py tests/knowledge/test_hybrid_retrieval.py tests/approvals/test_snapshots.py -q` - 50 passed
- `uv run ruff check src/db/models.py src/db/migrations/versions/015_rag_production_ingestion_ocr.py src/repositories/document_block_repo.py src/repositories/rag_ingestion_job_repo.py tests/rag/test_document_block_schema.py tests/test_rag_production_migration.py tests/knowledge/test_phase21_boundaries.py tests/rag/phase21_xfail_inventory.py` - passed

Note: pytest emitted the existing LangGraph `allowed_objects` pending-deprecation warning.

## Known Stubs

None. Stub scan found only intentional test empty literals and the pre-existing `PolicyChunk.search_text` default.

## Issues Encountered

- The first migration test pass treated timestamp `server_default=now()` as a semantic fake default. The assertion was narrowed to the new JSONB provenance columns, and the focused migration/schema suite then passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `21-02-PLAN.md`. The schema/repository foundation and evidence boundary guards are now in place; block-aware chunking and atomic ingestion can persist source-block refs without changing v1.3 public evidence contracts.

## Self-Check: PASSED

- Found summary file and created source files.
- Found task commits `e7dc1be` and `daac6bd`.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18*
