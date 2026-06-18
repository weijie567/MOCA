---
phase: 21-rag-production-ingestion-ocr
plan: "04"
subsystem: rag
tags: [rag, provenance, ingestion, safety, pytest, ruff]

requires:
  - phase: 21-rag-production-ingestion-ocr
    provides: "21-02 block-aware ingestion persistence and 21-03 parser/OCR adapters"
provides:
  - "Verified tenant/hash-gated source provenance side path"
  - "Allowlisted safe ingestion report projection"
  - "Sanitized parser/OCR trace validation for persisted ingestion jobs"
affects: [phase-21, rag-ingestion, policy-evidence, maintainer-debug]

tech-stack:
  added: []
  patterns:
    - "Internal provenance DTOs stay separate from EvidenceRefV1 serialization"
    - "Safe report projection uses explicit allowlisted output fields"

key-files:
  created:
    - src/knowledge/provenance.py
  modified:
    - src/knowledge/service.py
    - src/knowledge/retrieval.py
    - src/repositories/policy_chunk_repo.py
    - src/repositories/rag_ingestion_job_repo.py
    - src/rag/ingestion.py
    - tests/knowledge/test_provenance_lookup.py
    - tests/rag/phase21_xfail_inventory.py
    - tests/rag/test_ingestion_jobs.py
    - tests/rag/test_ingestion_safety.py

key-decisions:
  - "Source provenance is internal maintainer/debug data and is returned only after tenant, unique-key, and canonical text-hash verification."
  - "Safe ingestion reports always project exactly the allowed fields and recursively drop raw payload, path, stack, parser dump, private reasoning, and authority-body keys."
  - "Wave 0 xfails were removed only for 21-04-owned provenance/report behavior; 21-04a-owned boundary xfail remains."

patterns-established:
  - "Verified side paths first reuse EvidenceRefV1 tenant/hash validation, then expand internal metadata."
  - "Durable parser/OCR traces are projected through allowlists before maintainer consumption."

requirements-completed: [PROV-03, SAFE-02, INGEST-01, BOUNDARY-03]

duration: 9m 29s
completed: 2026-06-18T23:28:57Z
---

# Phase 21 Plan 04: Verified Provenance Lookup And Safe Trace Reporting Summary

**Tenant/hash-verified source-block provenance lookup plus allowlisted parser/OCR ingestion report projection**

## Performance

- **Duration:** 9m 29s
- **Started:** 2026-06-18T23:19:28Z
- **Completed:** 2026-06-18T23:28:57Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added internal `SourceLocator`, `EvidenceProvenance`, and `EvidenceProvenanceLookupResult` DTOs without changing `EvidenceRefV1`.
- Added `PolicyKnowledgeService.get_verified_evidence_provenance(...)`, which verifies tenant UUID, unique keys, ref tenant, and `evidence_text_hash(content)` before expanding source-block locators.
- Added repository expansion from `PolicyChunk.source_block_refs_json` through tenant/doc-scoped `DocumentBlock` rows, failing closed for missing or ambiguous block rows.
- Added `build_safe_ingestion_report(...)` and `sanitize_failure_reason(...)` in `src/rag/ingestion.py` with exact allowed report fields and recursive forbidden-key redaction.
- Hardened `RagIngestionJobRepository` validation for forbidden raw/parser/authority trace keys.

## Task Commits

1. **Task 1 RED: Add failing provenance lookup tests** - `a909b01` (test)
2. **Task 1 GREEN: Implement verified evidence provenance lookup** - `5f3893c` (feat)
3. **Task 2 RED: Add failing safe ingestion report tests** - `f443be0` (test)
4. **Task 2 GREEN: Add safe ingestion report projection** - `a12b408` (feat)

## Files Created/Modified

- `src/knowledge/provenance.py` - Internal provenance DTOs and safe locator projection from document blocks.
- `src/knowledge/service.py` - Tenant/hash-verified provenance side path.
- `src/knowledge/retrieval.py` - Retrieval-engine bridge to provenance repository lookup.
- `src/repositories/policy_chunk_repo.py` - Chunk source-ref expansion through `DocumentBlockRepository`.
- `src/repositories/rag_ingestion_job_repo.py` - Stronger durable trace forbidden-key validation.
- `src/rag/ingestion.py` - Safe ingestion report and failure-reason projection helpers.
- `tests/knowledge/test_provenance_lookup.py` - Provenance validation, repository expansion, and EvidenceRef boundary tests.
- `tests/rag/phase21_xfail_inventory.py` - Removed only 21-04-owned Wave 0 xfail entries.
- `tests/rag/test_ingestion_jobs.py` - Safe report allowed-field and forbidden-key tests.
- `tests/rag/test_ingestion_safety.py` - Hidden/raw parser payload report boundary test.

## Verification

- `uv run pytest tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/rag/test_ingestion_jobs.py tests/rag/test_ingestion_safety.py -q` -> 37 passed, 1 warning
- `uv run ruff check src/knowledge/provenance.py src/knowledge/service.py src/knowledge/retrieval.py src/repositories/policy_chunk_repo.py src/repositories/rag_ingestion_job_repo.py src/rag/ingestion.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/rag/test_ingestion_jobs.py tests/rag/test_ingestion_safety.py tests/rag/phase21_xfail_inventory.py` -> passed
- `rg -n "build_safe_ingestion_report|file_bytes|parser_dump|stack_trace|local_path" src/rag tests/rag/test_ingestion_jobs.py` -> projection/tests found, forbidden-key handling remains explicit
- `rg -n "21-04|safe-job-report|raw-payload-report-boundary|provenance-lookup" tests/rag/phase21_xfail_inventory.py tests -S` -> only 21-04a-owned xfail remains

## Decisions Made

- Provenance identity is checked against the caller's `EvidenceRefV1.evidence_id`, including `v{PolicyDocument.version}`, before returning locators.
- Safe reports include all allowed fields with empty defaults where needed, rather than exposing source text or parser-native structures.
- `src.rag.ingestion.py` owns the report helpers because creating a new helper file was outside the user-specified 21-04 write scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed provenance repository row identity after adding document version**
- **Found during:** Task 1 (verified source provenance lookup)
- **Issue:** Adding `PolicyDocument.version` to the provenance query shifted tuple indexes; row uniqueness would have been checked against `(doc_key, version)` instead of `(doc_key, chunk_id)`.
- **Fix:** Corrected row counting to use `(doc_key, chunk_id)` and added repository regression coverage for document-version evidence identity.
- **Files modified:** `src/repositories/policy_chunk_repo.py`, `tests/knowledge/test_provenance_lookup.py`
- **Verification:** `uv run pytest tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py -q`
- **Committed in:** `5f3893c`

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Correctness-only fix inside the planned repository path. No scope expansion.

## Issues Encountered

None beyond the auto-fixed repository projection issue documented above.

## Known Stubs

None. Stub scan found only normal Python defaults and test empty-result assertions.

## Authentication Gates

None.

## TDD Gate Compliance

- RED commits present: `a909b01`, `f443be0`
- GREEN commits present after RED: `5f3893c`, `a12b408`
- Refactor commit: not needed

## Next Phase Readiness

Plan 21-04a can continue with prompt/API/memory/action/replay boundary work. The 21-04a xfail inventory entry remains intact, and no public document viewer, semantic verifier, reranker/query rewrite, external backend, or business fact RAG ingestion surface was added.

## Self-Check: PASSED

- Created files verified: `.planning/phases/21-rag-production-ingestion-ocr/21-04-SUMMARY.md`, `src/knowledge/provenance.py`
- Task commits verified in git log: `a909b01`, `5f3893c`, `f443be0`, `a12b408`
- No accidental deletions found in task commits.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18T23:28:57Z*
