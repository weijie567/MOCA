---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
plan: 03
subsystem: memory
tags: [case-memory, case-precedent, cwc, review-lifecycle, mem-04]

requires:
  - phase: 47-02
    provides: trusted closed-case CWC projection service and prompt-safe CaseMemoryWriteCandidate construction
provides:
  - governed closed-case candidate submission through CaseMemoryService
  - needs_review persistence with memory_write_events through existing case-memory lifecycle
  - duplicate/idempotency and PII skip coverage through existing service behavior
  - approval-gated reviewed retrieval coverage with mapped policy refs preserved
affects: [memory, case-memory, case-working-context, memory-review-api, phase-47]

tech-stack:
  added: []
  patterns:
    - service-owned case-memory write lifecycle for generated closed-case candidates
    - fixed-text PII-blocked candidate submission for service skip event observability
    - approval-gated reviewed retrieval tests for generated closed-case precedents

key-files:
  created:
    - .planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-03-SUMMARY.md
  modified:
    - src/memory/case_precedent.py
    - tests/memory/test_case_precedent_generation.py
    - tests/test_memory_review_api.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Closed-case CWC candidates persist only through CaseMemoryService.submit_case_memory_candidate(...)."
  - "PII-blocked CWC rows submit a fixed non-sensitive candidate so the existing service emits pii_blocked skip events without inserting a row."
  - "Pending generated candidates use the existing case-memory review API and remain invisible to retrieve_reviewed(...) until approval."

patterns-established:
  - "Source identity encodes close event and CWC row/version with allowed event_id and outcome_id keys."
  - "Generated policy refs preserve mapped case-memory keys: doc_key, chunk_id, policy_version."
  - "Task-level review/retrieval tests assert pending visibility before mutating the ORM row through approval."

requirements-completed: [MEM-04]

duration: 21 min
completed: 2026-07-03
---

# Phase 47 Plan 03: Governed Closed-Case Candidate Lifecycle Summary

**Closed-case CWC projections now enter the existing reviewed case-memory workflow as `needs_review` candidates with service-owned audit, duplicate, PII, and approval-gated retrieval behavior.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-03T14:10:30Z
- **Completed:** 2026-07-03T14:31:32Z
- **Tasks:** 3/3
- **Files modified:** 5

## Accomplishments

- Routed accepted terminal projections through `CaseMemoryService.submit_case_memory_candidate(...)`; `src/memory/case_precedent.py` no longer stops at projection for successful terminal candidates.
- Preserved source identity on existing allowed fields: `event_id=refund-case-close:{case_id}:{close_event_id}` and `outcome_id=cwc:{cwc_row.id}:v{cwc_row.version}`.
- Changed PII-blocked CWC handling to submit a fixed non-sensitive candidate with the CWC `pii_classification`, allowing the existing service to emit `pii_blocked` skip events without inserting rows.
- Added integration coverage for duplicate/idempotency, pending review visibility, reviewed retrieval exclusion until approval, retrieval after approval, policy-ref preservation, and existing memory review API handling of `closed_case_cwc_candidate`.
- Updated the Chinese local validation and architecture-debt ledgers for handled validation issues and the completed 47-03 memory lifecycle repair.

## Task Commits

Each task was committed atomically, with TDD red/green commits where applicable:

1. **Task 1 RED: Submit terminal projections through CaseMemoryService** - `b534821` (`test`)
2. **Task 1 GREEN: Submit terminal projections through CaseMemoryService** - `dde8fe9` (`feat`)
3. **Task 2 RED: Prove idempotency, duplicate handling, and PII skip behavior** - `14def65` (`test`)
4. **Task 2 GREEN: Prove idempotency, duplicate handling, and PII skip behavior** - `7cc0179` (`feat`)
5. **Task 3: Prove pending-review visibility and reviewed-retrieval invisibility until approval** - `1837f81` (`test`)
6. **Validation cleanup: Remove stale import after PII path change** - `9c6a319` (`fix`)

**Plan metadata:** committed separately after this summary and state updates.

## Files Created/Modified

- `src/memory/case_precedent.py` - Added service submission, service-result mapping, source identity event format, and fixed-text PII-blocked candidate submission.
- `tests/memory/test_case_precedent_generation.py` - Added closed-case write, source-ref, duplicate, PII skip, pending/retrieval/approval, and policy-ref preservation coverage.
- `tests/test_memory_review_api.py` - Exercised existing review API with a `closed_case_cwc_candidate` case-memory row.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Logged handled Task 3 test-ordering and Ruff validation incidents.
- `.planning/ARCHITECTURE-DEBT.md` - Added Phase 47-03 memory lifecycle repair ledger entry.
- `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-03-SUMMARY.md` - This execution summary.

## Verification

- RED Task 1: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` -> expected failure: `projection_ready` instead of service-owned `requires_review`.
- GREEN Task 1: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` -> `12 passed, 1 warning`.
- RED Task 2: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` -> expected failure: PII-blocked result lacked service event id.
- GREEN Task 2: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` -> `18 passed, 1 warning`.
- Task 3 initial run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -x -q` -> failed due test assertion ordering; fixed and reran.
- Task 3 final run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -x -q` -> `33 passed, 1 warning`.
- Plan gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -q` -> `33 passed, 1 warning`.
- Ruff first run: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py tests/memory/test_case_precedent_generation.py tests/test_memory_review_api.py` -> failed on stale unused import.
- Ruff final: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py tests/memory/test_case_precedent_generation.py tests/test_memory_review_api.py` -> `All checks passed!`
- Final plan gate rerun after Ruff cleanup: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -q` -> `33 passed, 1 warning`.

Warnings were the existing LangGraph/LangChain pending deprecation warning.

## Decisions Made

- Reused the existing case-memory write/review/audit/dedupe service instead of adding a second store, second review queue, or custom event path.
- Kept `policy_version` in `source_ref_json` because it is allowed in `ALLOWED_SOURCE_REF_KEYS`; no source-ref key was removed for the prior external warning.
- Treated Task 3 as test-only after Tasks 1 and 2 made the review/retrieval lifecycle behavior available through existing services.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Fixed pending-row assertion ordering**
- **Found during:** Task 3 (pending-review and reviewed-retrieval lifecycle)
- **Issue:** The new test asserted a pending ORM row's `review_status` after `approve_case_memory(...)` mutated the same SQLAlchemy object to `approved`.
- **Fix:** Moved pending-review and hidden-retrieval assertions before the approval call.
- **Files modified:** `tests/memory/test_case_precedent_generation.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Task 3 command reran with `33 passed, 1 warning`.
- **Committed in:** `1837f81`

**2. [Rule 1 - Lint Bug] Removed stale import after PII path changed**
- **Found during:** Final touched-file Ruff check
- **Issue:** `ClosedCasePrecedentGenerationResult` import became unused after PII-blocked projection started returning a fixed-text `CaseMemoryWriteCandidate`.
- **Fix:** Removed the stale import and logged the validation incident.
- **Files modified:** `tests/memory/test_case_precedent_generation.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Ruff passed and the plan-level pytest rerun passed.
- **Committed in:** `9c6a319`

---

**Total deviations:** 2 auto-fixed test/validation issues.
**Impact on plan:** Both fixes were local to validation/test correctness. No production scope expansion, no schema change, and no new API endpoint were introduced.

## Issues Encountered

- Task 3's first focused command failed due ORM row mutation after approval; fixed test order and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Ruff caught a stale unused import after the PII projection behavior changed; removed it, reran Ruff and pytest, and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No authentication gates occurred.

## Known Stubs

None. Stub-pattern scan hits were intentional optional `None` values (`session=None` test fakes, `outcome=None`, `embedding=None`) and historical ledger text; none are unresolved implementation stubs.

## Threat Flags

None beyond the plan threat model. This plan introduced no public refund-case close endpoint, no ToolCallContext widening, no schema migration, and no new auth or network surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 47-04. The governed write lifecycle is complete; 47-04 still owns broader metadata/text retrieval, tool/reviewed-context stability, docs, DEFER-3 carry-forward, and final Phase 47 validation.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-03-SUMMARY.md`.
- Task commits found in git history: `b534821`, `dde8fe9`, `14def65`, `7cc0179`, `1837f81`, `9c6a319`.
- Key created/modified files exist: `src/memory/case_precedent.py`, `tests/memory/test_case_precedent_generation.py`, `tests/test_memory_review_api.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`, `.planning/ARCHITECTURE-DEBT.md`.
- Remaining unrelated dirty files are the three pre-existing user-owned files from the executor prompt and were not staged or committed.

---
*Phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener*
*Completed: 2026-07-03*
