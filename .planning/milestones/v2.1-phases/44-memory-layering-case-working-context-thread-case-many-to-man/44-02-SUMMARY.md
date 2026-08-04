---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
plan: 02
subsystem: memory
tags: [postgres, sqlalchemy, pydantic, memory, concurrency]
requires:
  - phase: 44-memory-layering-case-working-context-thread-case-many-to-man
    provides: case_working_contexts and case_working_context_revisions DDL from 44-01
provides:
  - tenant-scoped refund_case_no/UUID to refund_cases.id case identity resolver
  - typed Case Working Context content schemas with claim/fact separation
  - active CWC read and advisory-lock/versioned write repository with append-only revisions
affects: [memory, case-working-context, phase-44-wave-3, phase-44-wave-4]
tech-stack:
  added: []
  patterns:
    - TDD red/green commits for memory service surfaces
    - explicit CWC content field to ORM JSON column mapping
    - transaction-scoped PostgreSQL advisory lock for tenant/case write serialization
key-files:
  created:
    - src/memory/case_identity.py
    - src/memory/case_working_context_schemas.py
    - src/memory/case_working_context.py
    - tests/memory/test_case_identity.py
    - tests/memory/test_case_working_context_repo.py
    - .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-02-SUMMARY.md
  modified:
    - .planning/ARCHITECTURE-DEBT.md
key-decisions:
  - "CWC scope never uses raw strings: resolver returns refund_cases.id UUID or typed invalid/not_found results."
  - "CWC schemas keep claims and verified facts as distinct typed fields and store policy refs only by doc/chunk/version."
  - "CWC writes serialize by tenant/case advisory lock, use expected_version conflict results, and snapshot prior active content before version bumps."
patterns-established:
  - "CWC repository reads/writes through dehydrate_content()/hydrate_content() instead of passing model_dump() directly to ORM rows."
  - "Phase 44 DB-backed memory tests use an explicit PostgreSQL availability probe before creating their own test engine."
requirements-completed: [MEM-01, MEM-02]
duration: 10min
completed: 2026-07-03
---

# Phase 44 Plan 02: Case Working Context Repository Summary

**Canonical case identity resolution plus typed, versioned Case Working Context repository backed by Wave 1 tables.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-02T17:46:08Z
- **Completed:** 2026-07-02T17:56:23Z
- **Tasks:** 3/3
- **Files modified:** 7

## Accomplishments

- Added `resolve_case_id(...)`, which maps blank input to `invalid`, tenant-scoped UUID/case-number matches to `refund_cases.id`, and unknown refs to `not_found`.
- Added CWC content schemas that keep `claims[]` and `verified_facts[]` distinct, require source refs on claim/fact/action/commitment entries, and keep policy storage to refs only.
- Added `CaseWorkingContextRepository` with active-row reads, explicit content-column hydration/dehydration, advisory-lock write serialization, expected-version conflicts, version bumps, and pre-write revision snapshots.
- Added DB-backed tests for first write, revision-on-update, conflict-no-clobber, content field mapping, active read miss, and concurrent first writes.

## Task Commits

1. **Task 1 RED: Case identity resolver tests** - `6d1954e` (`test`)
2. **Task 1 GREEN: Case identity resolver** - `bfa4a5b` (`feat`)
3. **Task 2 RED: CWC schema tests** - `94c05f0` (`test`)
4. **Task 2 GREEN: CWC schemas** - `31fccbc` (`feat`)
5. **Task 3 RED: CWC repository tests** - `9c7bab0` (`test`)
6. **Task 3 GREEN: CWC repository** - `52dd19e` (`feat`)

## Files Created/Modified

- `src/memory/case_identity.py` - Tenant-scoped case reference resolver returning typed pydantic results.
- `src/memory/case_working_context_schemas.py` - Typed CWC content, claim/fact/action/commitment/ref models, and write candidate.
- `src/memory/case_working_context.py` - CWC active read, mapped hydrate/dehydrate helpers, advisory-lock write, conflict, and revision logic.
- `tests/memory/test_case_identity.py` - Resolver behavior and tenant-scope coverage.
- `tests/memory/test_case_working_context_repo.py` - Schema shape plus DB-backed repository/versioning/concurrency coverage.
- `.planning/ARCHITECTURE-DEBT.md` - Project-rule memory ledger entry for the verified Wave 2 fix and remaining Wave 3/4 risks.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-02-SUMMARY.md` - This execution summary.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py -x -q`:
  - RED before implementation: failed with `ModuleNotFoundError: No module named 'src.memory.case_identity'`
  - GREEN after implementation: `6 passed, 1 warning`
- `grep -n "get_by_case_no" src/memory/case_identity.py` -> matched resolver reuse at line 45.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_repo.py -x -q -k schema`:
  - RED before implementation: failed with `ModuleNotFoundError: No module named 'src.memory.case_working_context_schemas'`
  - GREEN after implementation: `4 passed, 1 warning`
- `grep -n "class CaseWorkingContextVerifiedFactV1" src/memory/case_working_context_schemas.py` -> matched line 20.
- `grep -n "class CaseWorkingContextClaimV1" src/memory/case_working_context_schemas.py` -> matched line 12.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_repo.py -x -q`:
  - RED before implementation: failed with `ModuleNotFoundError: No module named 'src.memory.case_working_context'`
  - GREEN after implementation: `10 passed, 1 warning`
- `grep -n "CaseWorkingContextRevision" src/memory/case_working_context.py` -> matched import and revision insert.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_identity.py src/memory/case_working_context_schemas.py src/memory/case_working_context.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py` -> `All checks passed!`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py -q` -> `16 passed, 1 warning`
- `git grep -n "contextual_only" src/memory/case_working_context.py` -> create and update paths both pin `authority_class`.
- `git grep -n "CaseWorkingContextPolicyRefV1\|policy_refs\|source_ref" src/memory/case_working_context_schemas.py src/memory/case_working_context.py` -> confirms policy storage is ref-shaped and source refs are required on provenance-bearing models.

## Decisions Made

- Followed 44-01's DDL contract directly; no migrations, table renames, or changes to `conversation_threads.case_id`.
- Used the existing `RefundRepository.get_by_case_no(...)` resolution surface instead of duplicating case-number lookup logic.
- Stored revision `snapshot_json` as the prior active content shape from `dehydrate_content(hydrate_content(row))`, keeping the snapshot aligned with the mapped ORM columns.

## Deviations from Plan

### Project-Rule Documentation

**1. [CLAUDE.md / AGENTS.md - Memory Architecture Debt Ledger] Added verified Wave 2 memory entry**
- **Found during:** Summary preparation after memory subsystem changes
- **Issue:** Project rules require updates to `.planning/ARCHITECTURE-DEBT.md` when memory subsystem fixes are completed.
- **Fix:** Added a Chinese Phase 44 Wave 2 entry with problem/root cause, fix, evidence, verification, and remaining Wave 3/4 risks.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Diff reviewed; entry is source/test/commit-backed and does not claim Wave 3/4 completion.

**Total deviations:** 1 project-rule documentation update.
**Impact on plan:** No code scope expansion; only required memory subsystem ledger documentation.

## Issues Encountered

None beyond expected TDD RED failures. DB-backed CWC repository tests ran against the local Phase 44 PostgreSQL test database and passed.

## Known Stubs

None. Stub scan only found intentional pydantic defaults (`None` / empty lists) and test assertions for those defaults; no UI/data-source stubs were introduced.

## Threat Flags

None beyond the plan threat model. The new resolver and CWC write trust boundaries were explicitly covered by tenant-scoped lookup, distinct claim/fact schemas, expected-version conflict handling, advisory locking, and revision snapshots.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 44-03. Wave 3 can call the resolver, construct `CaseWorkingContextWriteCandidate`, and write through `CaseWorkingContextRepository`; thread-case link lifecycle, CWC write service/audit event, and isolated-session orchestration remain intentionally unimplemented until Wave 3. Contract-spec §13 alignment and final sweep remain Wave 4.

## Self-Check: PASSED

- Created files found: `case_identity.py`, `case_working_context_schemas.py`, `case_working_context.py`, both focused test files, and this summary.
- Task commits found in git history: `6d1954e`, `bfa4a5b`, `94c05f0`, `31fccbc`, `9c7bab0`, `52dd19e`.
- Wave 2 code diff is limited to `src/memory/` and `tests/memory/`; no migrations, table renames, or `conversation_threads.case_id` changes were introduced.

---
*Phase: 44-memory-layering-case-working-context-thread-case-many-to-man*
*Completed: 2026-07-03*
