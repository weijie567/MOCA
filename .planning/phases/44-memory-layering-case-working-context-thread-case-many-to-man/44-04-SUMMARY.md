---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
plan: 04
subsystem: memory
tags: [contract-spec, memory, cwc, thread-case, verification]
requires:
  - phase: 44-memory-layering-case-working-context-thread-case-many-to-man
    provides: Waves 1-3 CWC schema, resolver/repository, thread-case links, and CWC write service
provides:
  - normative Case Working Context contract in docs/contract-spec.md §13
  - additive thread_case_links contract note preserving conversation_threads.case_id
  - Phase 44 contract-alignment test for CWC authority and red-line table names
  - DEFER trace for CWC/thread-case delivery and Phase 45 auto-update hook wiring
affects: [memory, contract-spec, phase-44, phase-45-memory-lifecycle-wiring]
tech-stack:
  added: []
  patterns:
    - docs/spec alignment test reads the normative contract as a text boundary
    - spec deltas remain explicit and checkpoint-reviewed before final approval
key-files:
  created:
    - tests/memory/test_phase44_contract_alignment.py
    - .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-04-SUMMARY.md
  modified:
    - docs/contract-spec.md
    - .planning/MEMORY-REDESIGN-DECISIONS.md
key-decisions:
  - "Case Working Context is normative in §13 as contextual_only, not EvidenceRefV1, and distinct from case_memory precedent."
  - "thread_case_links is documented as additive M:N and does not drop, rename, retype, or replace conversation_threads.case_id."
  - "Spec checkpoint evidence is prepared, but final human/dual-AI approval is intentionally not claimed by this delegated run."
requirements-completed: [MEM-01, MEM-02]
duration: 5min
completed: 2026-07-03
---

# Phase 44 Plan 04: Contract Alignment Summary

**Case Working Context is now normatively described in §13 with contextual-only authority, additive thread-case M:N semantics, and a regression test locking the red lines.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-02T18:17:50Z
- **Completed:** 2026-07-02T18:22:45Z
- **Tasks:** 3/3 automated tasks complete
- **Files modified:** 4

## Accomplishments

- Added a §13 Case Working Context layer-table row and subsection defining scope, `authority_class = contextual_only`, claim/fact separation, refs-only tool facts, versioned revisions, human correction, and the explicit NOT-`EvidenceRefV1` authority boundary.
- Clarified `case_memories` / `case_memory` as reviewed precedent, NOT active case state.
- Documented `thread_case_links` as additive many-to-many while preserving the legacy `conversation_threads.case_id` column.
- Added `tests/memory/test_phase44_contract_alignment.py` to lock CWC contract text, memory-write type presence, red-line table names, additive M:N wording, and DEFER markers.
- Added the Phase 44 delivery trace to `.planning/MEMORY-REDESIGN-DECISIONS.md`: CWC + thread-case M:N delivered; auto-update hook wiring deferred to Phase 45.

## Task Commits

1. **Task 1: Add normative CWC + thread-case note** - `f80d838` (`docs`)
2. **Task 2: Contract-alignment test + DEFER trace** - `8a708c9` (`test`)
3. **Task 3: Phase-level verification sweep** - no code commit; verification-only task produced no file changes

## Files Created/Modified

- `docs/contract-spec.md` - Adds the normative CWC subsection, additive `thread_case_links` note, and `case_working_context` write-event type.
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - Records Phase 44 delivery and Phase 45 auto-update hook wiring defer trace.
- `tests/memory/test_phase44_contract_alignment.py` - Contract alignment tests for §13, red-line table names, CWC audit type, and DEFER markers.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-04-SUMMARY.md` - Execution summary.

## Verification

- `grep -n "Case Working Context" docs/contract-spec.md && grep -n "case_working_context" docs/contract-spec.md && grep -n "thread_case_links" docs/contract-spec.md` -> matched §13 layer row/subsection, write type, storage rows, and M:N note.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase44_contract_alignment.py -x -q` -> `5 passed, 1 warning`.
- `grep -n "DEFER-1\|DEFER-2\|DEFER-3" .planning/MEMORY-REDESIGN-DECISIONS.md` -> all three DEFER markers matched.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py -q` -> `37 passed, 5 warnings`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase44_contract_alignment.py -q` -> `5 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` -> `022_case_working_context (head)`.
- `git grep -n "case_memories\|long_term_memories" -- docs/contract-spec.md` -> retained names at §13 and storage/schema sections; no rename.
- `git grep -n "case_memories\|long_term_memories" -- src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py` -> no matches.
- `git grep -n "conversation_threads.case_id" -- src tests docs .planning` -> matched docs/planning references plus migration/model index references; no code/schema change in this plan. `git grep -n "case_id" -- src/conversation/repository.py src/db/models.py` confirms the legacy ORM string column and new UUID link/CWC columns coexist.

## Checkpoint Evidence

The blocking `checkpoint:human-verify` has NOT been finally approved in this delegated run.

Evidence prepared for orchestrator review:

- §13 diff defines CWC scope as tenant + `refund_cases.id`, `authority_class = contextual_only`, NOT `EvidenceRefV1`, and not policy/risk/approval/action authority.
- §13.4 now locks `case_memories` / `case_memory` as reviewed precedent, NOT active case state.
- M:N note explicitly says `thread_case_links` is additive and does not drop, rename, retype, or replace `conversation_threads.case_id`.
- Contract-alignment test and full Phase 44 verification pass.

## Decisions Made

- Did not update `.planning/STATE.md` or `.planning/ROADMAP.md`; the orchestrator owns phase state for Wave 4.
- Did not modify schema/code. Wave 4 stayed to spec, tests, DEFER trace, and verification.
- Did not append `.planning/LOCAL-VALIDATION-ISSUES.md`; DB-backed Phase 44 verification ran and passed, so no local validation issue was discovered.

## Deviations from Plan

None - plan Tasks 1-3 executed as written. The planned checkpoint remains pending external review by design.

## Issues Encountered

None. PostgreSQL-backed Phase 44 verification passed locally through the project entrypoint.

## Known Stubs

None. Stub scan of introduced changes found no UI/data stubs. The only pattern hit was an existing decision-record observation that `memory_write_candidates` is cleared to `[]`, not a stub introduced by this plan.

## Threat Flags

None beyond the plan threat model. This plan introduced no new runtime endpoint, auth path, file access pattern, or schema boundary; it added docs/tests only.

## User Setup Required

None.

## Next Phase Readiness

Ready for orchestrator spec review/adjudication. After approval, Phase 44 can be closed by the orchestrator; Phase 45 remains the named follow-up for real lifecycle wiring of CWC/thread-case auto-update hooks.

## Self-Check: PASSED

- Created/modified files found: `docs/contract-spec.md`, `.planning/MEMORY-REDESIGN-DECISIONS.md`, `tests/memory/test_phase44_contract_alignment.py`, and this summary.
- Task commits found in git history: `f80d838`, `8a708c9`.
- Red lines verified: no `case_memories` / `long_term_memories` matches in Phase 44 migrations 021/022, and `conversation_threads.case_id` remains as the legacy ORM/model path alongside additive UUID link/CWC columns.
