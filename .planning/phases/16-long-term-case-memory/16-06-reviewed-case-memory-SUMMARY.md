---
phase: 16-long-term-case-memory
plan: 06
subsystem: memory
tags: [case-memory, pgvector, tombstone, review-lifecycle, tdd]

requires:
  - phase: 16-01-memory-identity
    provides: canonical memory content/source/candidate hash helpers
  - phase: 16-02-schema-migration
    provides: case_memories, memory_tombstones, and memory_write_events tables
  - phase: 16-05-tombstone-supersede
    provides: exact tombstone matching and no-rewrite event semantics
provides:
  - Reviewed case memory service boundary for candidate, approve, reject, delete, and tombstone paths
  - Metadata-first reviewed case retrieval with pgvector ranking after hard filters
  - Prompt-safe case precedent views that cannot be treated as policy evidence
  - Case memory tombstone no-rewrite coverage by content hash and source identity
affects: [16-07-context-assembler-memory, 16-08-memory-retrieval-integration, 16-09-legacy-search-eval-closure]

tech-stack:
  added: []
  patterns:
    - Dedicated case-memory service/repository boundary under src/memory
    - Canonical candidate hashes reused for case memory write events
    - Metadata filter list is built before vector score expressions

key-files:
  created:
    - src/memory/case_memory.py
    - tests/memory/test_case_memory_retrieval.py
  modified:
    - src/memory/schemas.py
    - tests/memory/test_memory_tombstones.py

key-decisions:
  - "Case review approve/reject events use the existing memory_write_events enum: decision=write/reason_code=approved and decision=skip/reason_code=rejected."
  - "Reviewed case memory returns fixed prompt-safe precedent fields only and does not import or emit policy evidence contracts from src/memory."
  - "Case retrieval applies tenant/scope/status/deletion/expiry/PII/case-type/policy/tombstone filters before pgvector scoring."

patterns-established:
  - "CaseMemoryService owns candidate submission, review decisions, delete, tombstone, and retrieval orchestration."
  - "CaseMemorySearchItem is a fixed-shape prompt-safe view with case_memory_id, excerpt, applicability, outcome, caveats, score, policy_refs, and source_refs."
  - "Case tombstones match only canonical content_hash or allowed source_identity_hash."

requirements-completed:
  - CASEMEM-01
  - CASEMEM-02
  - CASEMEM-03
  - TOMBSTONE-01
  - TOMBSTONE-02
  - MEMREVIEW-01
  - MEMEVAL-01

duration: 12 min
completed: 2026-06-17
---

# Phase 16 Plan 06: Reviewed Case Memory Storage And Retrieval Summary

**Reviewed case precedent memory with auditable review lifecycle, metadata-first pgvector retrieval, and tombstone no-rewrite protection**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-17T16:35:57Z
- **Completed:** 2026-06-17T16:48:46Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Added reviewed case memory schemas and service/repository methods for submit, approve, reject, delete, tombstone, and retrieval paths.
- Implemented metadata-first retrieval filters for tenant, scope, status, deletion, expiry, PII, case type, policy compatibility, and active tombstones before vector ranking.
- Added prompt-safe search output that is not convertible to policy evidence and remains separate from legacy session-derived precedent search.
- Added case memory tombstone no-rewrite tests for both canonical content hash and allowed source identity fallback.

## Task Commits

1. **Task 16-06-01: Add reviewed case retrieval tests** - `3adbf48` (test)
2. **Task 16-06-02: Implement case memory service boundary** - `007576f` (feat)
3. **Task 16-06-03: Implement metadata-first vector retrieval** - `db8374e` (refactor)
4. **Task 16-06-04: Apply tombstone checks to case memory** - `c563dc0` (test)

## Files Created/Modified

- `src/memory/case_memory.py` - Reviewed case memory repository/service, event emission, metadata-first retrieval, prompt-safe projections, and tombstone checks.
- `src/memory/schemas.py` - Case memory write, review, search request/result, and prompt-safe search item contracts.
- `tests/memory/test_case_memory_retrieval.py` - TDD coverage for review lifecycle, write events, filters, pgvector retrieval boundary, session-memory separation, evidence-boundary negatives, and tombstone blocking.
- `tests/memory/test_memory_tombstones.py` - Additional case memory no-rewrite coverage in the tombstone suite.

## Decisions Made

- Case approve/reject paths follow the existing `memory_write_events.decision` enum. Approval emits `decision="write", reason_code="approved"`; rejection emits `decision="skip", reason_code="rejected"`.
- Case memory stays in `src/memory/case_memory.py` as a dedicated reviewed-memory boundary; legacy `src/memory/search.py` session-derived precedent search remains untouched for Plan 16-09.
- Retrieval returns only prompt-safe precedent fields and safe refs. No raw payloads, ORM rows, full policy text, or evidence contracts are exposed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mapped approve/reject events to existing write-event enum**
- **Found during:** Task 16-06-02 (Implement case memory service boundary)
- **Issue:** The plan text asked for literal approve/reject event decisions, but the existing `memory_write_events` check constraint only allows `write`, `skip`, `needs_review`, `delete`, `supersede`, `tombstone`, and `write_blocked`. Literal approve/reject values would fail database writes.
- **Fix:** Followed the prior Phase 16 decision: approve uses `decision="write", reason_code="approved"` and reject uses `decision="skip", reason_code="rejected"`.
- **Files modified:** `src/memory/case_memory.py`, `tests/memory/test_case_memory_retrieval.py`
- **Verification:** `uv run pytest tests/memory/test_case_memory_retrieval.py -q`
- **Committed in:** `007576f`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Preserves the observable review lifecycle without violating the existing database contract. No scope expansion.

## Issues Encountered

None. All planned verification commands passed. Pytest emitted only the existing LangGraph serializer deprecation warning.

## TDD Gate Compliance

- **RED:** `3adbf48` added failing case memory tests. Initial failure was `ModuleNotFoundError: No module named 'src.memory.case_memory'`.
- **GREEN:** `007576f` implemented the case memory service boundary and made `tests/memory/test_case_memory_retrieval.py` pass.
- **REFACTOR:** `db8374e` isolated hard retrieval filters from vector ranking while keeping tests green.

## Verification

- `uv run pytest tests/memory/test_case_memory_retrieval.py -q` — passed, 7 tests.
- `uv run pytest tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q` — passed, 14 tests.
- `uv run pytest tests/memory -q` — passed, 68 tests.
- `uv run ruff check src/memory tests/memory` — passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-07-context-assembler-memory-PLAN.md`. Reviewed case memories now have safe retrieval views and can be integrated into prompt assembly without becoming policy evidence, current business facts, approval authority, action authority, or replay/audit truth.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-17*

## Self-Check: PASSED

- Found key files: `src/memory/case_memory.py`, `tests/memory/test_case_memory_retrieval.py`, `src/memory/schemas.py`, `tests/memory/test_memory_tombstones.py`.
- Found task commits: `3adbf48`, `007576f`, `db8374e`, `c563dc0`.
