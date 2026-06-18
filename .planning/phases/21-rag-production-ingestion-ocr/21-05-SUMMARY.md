---
phase: 21-rag-production-ingestion-ocr
plan: "05"
subsystem: rag-ingestion
tags: [rag, ingestion, ocr, alembic, rollback, security, pytest]
requires:
  - phase: 21-04a
    provides: "Boundary regressions and replay redaction for Phase 21 provenance/parser/OCR metadata"
provides:
  - "Static and optional live-DB migration downgrade/reupgrade coverage for Phase 21 ingestion schema"
  - "Adversarial ingestion rollback tests proving prior policy evidence survives parser, OCR, embedding, DB, malformed, spoofed, oversize, decompression, hidden-prompt, and business-artifact failures"
  - "Empty Phase 21 implementation-pending xfail owner inventory"
  - "Safe failure-message redaction for hidden instructions, Tool System output, and business object payload markers"
affects: [phase-21-final-acceptance, rag-ingestion, provenance, ocr, migration]
tech-stack:
  added: []
  patterns:
    - "Optional live migration tests are gated by MOCA_TEST_DATABASE_URL and skip clearly when unset."
    - "Rollback tests compare pre/post policy evidence snapshots including doc version, content, chunks, source refs, blocks, and retrieval output."
key-files:
  created:
    - ".planning/phases/21-rag-production-ingestion-ocr/21-05-SUMMARY.md"
  modified:
    - "src/rag/ingestion.py"
    - "tests/test_rag_production_migration.py"
    - "tests/test_ingestion.py"
    - "tests/rag/phase21_xfail_inventory.py"
key-decisions:
  - "Use MOCA_TEST_DATABASE_URL as the only trigger for destructive live migration round-trip tests."
  - "Remove the obsolete strict xfail helper after PHASE21_XFAIL_OWNERS became empty."
  - "Treat hidden prompt, Tool System, and business object payload markers as unsafe failure-message content."
patterns-established:
  - "Migration rollback tests assert Phase 20 hybrid retrieval columns and indexes survive Phase 21 downgrade."
  - "Adversarial rollback tests preserve a prior-evidence snapshot through pre-transaction and in-transaction failure paths."
requirements-completed: [SRC-03, SRC-04, SRC-05, PROV-03, PROV-04, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-03, INGEST-04, BOUNDARY-01, BOUNDARY-03, BOUNDARY-04]
duration: "7m 42s"
completed: "2026-06-18T23:52:06Z"
---

# Phase 21 Plan 05: Migration Rollback And Security Closure Summary

**Migration downgrade/reupgrade and adversarial ingestion rollback gates with sanitized parser/OCR failure traces**

## Performance

- **Duration:** 7m 42s
- **Started:** 2026-06-18T23:44:23Z
- **Completed:** 2026-06-18T23:52:06Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added migration tests for Phase 21 document/block/job/provenance columns, dependency-safe downgrade ordering, Phase 20 hybrid retrieval preservation, and an optional Alembic downgrade/reupgrade round trip gated by `MOCA_TEST_DATABASE_URL`.
- Added adversarial rollback tests that preserve previous `PolicyDocument` version/content, chunks, source refs, blocks, and fake retrieval output across parser failure, OCR timeout, embedding mismatch, DB block insert failure, DB chunk insert failure, malformed/spoofed/oversize/decompression failures, hidden prompt text, and business artifact rejection.
- Removed the obsolete implementation-pending strict xfail helper while keeping `PHASE21_XFAIL_OWNERS` empty.
- Hardened persisted safe failure messages against hidden prompt instructions, Tool System output, and business object payload identifiers.

## Task Commits

1. **Task 21-05-01: Prove migration upgrade, downgrade, and re-upgrade safety** - `16fdfbe` (test)
2. **Task 21-05-02: Run adversarial ingestion rollback and security closure** - `e228137` (test)

## Files Created/Modified

- `src/rag/ingestion.py` - Adds unsafe failure-message patterns for hidden instructions, Tool System output, and business payload identifiers.
- `tests/test_rag_production_migration.py` - Adds static Phase 21 schema/downgrade checks and optional live DB Alembic round-trip coverage.
- `tests/test_ingestion.py` - Adds rollback evidence snapshot fakes and adversarial failure preservation tests.
- `tests/rag/phase21_xfail_inventory.py` - Leaves an empty implementation-pending owner mapping and removes the obsolete strict xfail helper.
- `.planning/phases/21-rag-production-ingestion-ocr/21-05-SUMMARY.md` - Records execution outcome.

## Decisions Made

- Optional live migration coverage is destructive by design and only runs when `MOCA_TEST_DATABASE_URL` is explicitly set.
- Phase 21 downgrade tests assert that chunk provenance columns drop before Phase 21 tables and document metadata columns, but do not invent a job-table-to-block-table dependency where no FK exists.
- The final xfail inventory keeps the `PHASE21_XFAIL_OWNERS` symbol for final acceptance/audit readability, but contains no implementation-pending owner entries or xfail helper.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Hardened failure-message sanitization for Phase 21 threat terms**
- **Found during:** Task 21-05-02
- **Issue:** Existing `_safe_message()` stripped paths, stack traces, raw bytes, and parser dumps, but did not explicitly reject hidden prompt-injection phrases, Tool System output markers, or business object payload identifiers.
- **Fix:** Added narrowly scoped unsafe message patterns in `src/rag/ingestion.py` and regression coverage in `tests/test_ingestion.py`.
- **Verification:** `uv run pytest tests/test_ingestion.py tests/rag/test_ingestion_safety.py tests/rag/test_ingestion_jobs.py tests/rag/test_ocr_parser.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_phase21_boundaries.py -q` passed.
- **Committed in:** `e228137`

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Required to satisfy SAFE-02/SAFE-03 trace hygiene. No out-of-scope Phase 22/23/RAG-5 surfaces were added.

## Issues Encountered

- Initial new rollback tests expected preflight job traces to bind to an existing doc, but the local test fake lacked the real repository's non-locking `get_by_doc_key` method. The fake was corrected and the suite passed.

## Verification

- `uv run pytest tests/test_rag_production_migration.py tests/knowledge/test_hybrid_schema.py -q` - passed: 12 passed, 1 skipped.
- `uv run pytest tests/test_ingestion.py tests/rag/test_ingestion_safety.py tests/rag/test_ingestion_jobs.py tests/rag/test_ocr_parser.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_phase21_boundaries.py -q` - passed: 74 passed.
- `uv run pytest tests/test_rag_production_migration.py tests/knowledge/test_hybrid_schema.py tests/test_ingestion.py tests/rag/test_ingestion_safety.py tests/rag/test_ingestion_jobs.py tests/rag/test_ocr_parser.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_phase21_boundaries.py -q` - passed: 86 passed, 1 skipped.
- `rg -n "target code absent|xfail" tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_production_migration.py` - passed: no matches.
- `uv run ruff check src/rag/ingestion.py tests/test_ingestion.py tests/test_rag_production_migration.py tests/rag/phase21_xfail_inventory.py` - passed.

## Dependency Skips

- `tests/test_rag_production_migration.py::test_phase21_migration_live_downgrade_round_trip_when_configured` skips unless `MOCA_TEST_DATABASE_URL` is set. This is dependency-only because the live round trip needs a disposable PostgreSQL database.

## Known Stubs

None - scan hits were test fakes, typed nullable fields, or safe empty collection defaults; no goal-blocking UI/data stubs were introduced.

## Threat Flags

None - no new network endpoint, auth path, file-access path, schema trust boundary, or public API surface was introduced beyond the plan's migration/test/sanitizer scope.

## User Setup Required

None. To exercise the optional live DB migration gate, set `MOCA_TEST_DATABASE_URL` to a disposable PostgreSQL database URL before running the migration test.

## Next Phase Readiness

21-05a can run the final Phase 21 acceptance gate with migration rollback, adversarial ingestion rollback, provenance, OCR, boundary, and xfail cleanup evidence in place. Remaining skip is dependency-only and explicit.

## Self-Check: PASSED

- Found `.planning/phases/21-rag-production-ingestion-ocr/21-05-SUMMARY.md`.
- Found `src/rag/ingestion.py`.
- Found `tests/test_rag_production_migration.py`.
- Found `tests/test_ingestion.py`.
- Found task commit `16fdfbe`.
- Found task commit `e228137`.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18*
