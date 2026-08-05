---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
plan: 02
subsystem: memory
tags: [case-memory, case-precedent, cwc, mem-04, projection]

requires:
  - phase: 47-01
    provides: reviewed closed-case precedent semantics and review-required closed_case_cwc_candidate source type
provides:
  - trusted internal closed-case precedent generation seam
  - tenant-bound RefundCase with Order merchant lookup for precedent scope resolution
  - deterministic allowlisted CWC-to-CaseMemoryWriteCandidate projection
affects: [memory, case-memory, case-working-context, refund-repository, phase-47]

tech-stack:
  added: []
  patterns:
    - trusted close seam with explicit terminal status allowlist
    - deterministic prompt-safe projection from CWC summaries and refs
    - merchant retrieval scope with exact case fallback, never tenant fallback

key-files:
  created:
    - src/memory/case_precedent.py
    - tests/memory/test_case_precedent_generation.py
    - .planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-02-SUMMARY.md
  modified:
    - src/repositories/refund_repo.py
    - tests/memory/test_phase47_case_precedent_alignment.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Terminal refund-case statuses are exactly closed, refunded, and rejected for Phase 47."
  - "Merchant scope is used only when RefundCase -> Order.merchant_id resolves; unresolved merchant falls back to exact case scope."
  - "47-02 builds a prompt-safe CaseMemoryWriteCandidate but does not submit it to CaseMemoryService; governed write lifecycle remains 47-03."
  - "CWC policy refs map to existing case-memory policy ref keys: doc_key, chunk_id, policy_version."

patterns-established:
  - "ClosedCasePrecedentService skips before CWC hydration for non-terminal or missing case inputs."
  - "Projection labels customer claims and verified facts separately and applies fixed contextual-only caveats."
  - "Case-precedent projection keeps embeddings optional by setting generated candidates to embedding=None."

requirements-completed: [MEM-04]

duration: 11 min
completed: 2026-07-03
---

# Phase 47 Plan 02: Closed-Case Candidate Projection Service Summary

**Trusted closed-case CWC projection now produces prompt-safe review-required case-memory candidates with terminal-status, tenant, scope, PII, and forbidden-payload guards.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-03T13:51:00Z
- **Completed:** 2026-07-03T14:01:58Z
- **Tasks:** 2/2
- **Files modified:** 9

## Accomplishments

- Added `ClosedCasePrecedentService` with explicit trusted close input, terminal refund status allowlist, case/CWC skip reasons, and lazy dependency injection for tests.
- Added tenant-bound `RefundRepository.get_by_id_with_order(...)` and scope resolution that uses merchant scope when safe, exact case scope otherwise, and never tenant-wide fallback.
- Added deterministic CWC projection into `CaseMemoryWriteCandidate` with claim/fact labels, ref-only policy refs, fixed caveat text, blocked sensitive/prohibited CWC PII, and no authority/replay DTO imports.
- Updated the memory architecture-debt ledger for the completed memory-subsystem fix and the remaining 47-03/47-04 boundaries.

## Task Commits

Each task was committed atomically with TDD gates:

1. **Task 1 RED: Trusted close seam tests** - `5d28154` (`test`)
2. **Task 1 GREEN: Trusted closed-case precedent seam** - `c9757b1` (`feat`)
3. **Task 2 RED: Closed-case projection tests** - `6a31dcb` (`test`)
4. **Task 2 GREEN: Closed-case CWC projection** - `f412b1d` (`feat`)

**Plan metadata:** committed separately after this summary and state updates.

## Files Created/Modified

- `src/memory/case_precedent.py` - Internal trusted close seam, result/request dataclasses, scope resolver, and deterministic projection helper.
- `src/repositories/refund_repo.py` - Tenant-bound `get_by_id_with_order(...)` helper with `selectinload(RefundCase.order)`.
- `tests/memory/test_case_precedent_generation.py` - DB-backed and unit-style tests for statuses, skip reasons, scope, projection, PII block, and payload marker exclusion.
- `tests/memory/test_phase47_case_precedent_alignment.py` - Static guard that prevents authority/replay DTO imports in the case-precedent projection module.
- `.planning/ARCHITECTURE-DEBT.md` - Chinese memory-subsystem ledger entry for Phase 47 Plan 02.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Logged the GSD state/roadmap handler mismatch encountered during metadata update.
- `.planning/STATE.md` - Advanced current position and metrics to Phase 47 plan 3 of 4.
- `.planning/ROADMAP.md` - Marked 47-02 complete and Phase 47 progress 2/4.

## Verification

- Task 1 RED: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` -> expected failure: missing `src.memory.case_precedent`
- Task 1 GREEN: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` -> `8 passed, 1 warning`
- Task 2 RED: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -x -q` -> expected failure: missing `PRECEDENT_CAVEAT_TEXT`
- Task 2 GREEN: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -x -q` -> `21 passed, 1 warning`
- Plan gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -q` -> `21 passed, 1 warning`
- Ruff: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py src/repositories/refund_repo.py tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py` -> pass

Warnings were the existing LangGraph/LangChain pending deprecation warning.

## Decisions Made

- Kept closure trust as an internal service seam only; no public refund-case close endpoint or agent-run completion inference was added.
- Kept source-ref identity on existing `MemorySourceRefV1` fields: `event_id` carries close-event identity, `outcome_id` carries CWC row/version identity, and business object fields carry source refund-case identity.
- Treated sensitive/prohibited CWC PII as a projection-time skip with `reason_code="pii_blocked"`, matching the later governed write path's PII boundary.
- Left actual `CaseMemoryService.submit_case_memory_candidate(...)` submission to 47-03 so write/review/audit/dedupe behavior lands as one governed lifecycle unit.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Expected TDD RED failures occurred before implementation and were committed as RED gates.
- During metadata update, the installed `gsd-sdk query state.record-metric` / `state.record-session` handlers interpreted named flags as positional text, and `roadmap.update-plan-progress` still could not match this ROADMAP format. The affected STATE/ROADMAP lines were repaired manually and the incident was logged in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. The absence of candidate submission is intentional 47-03 scope, not a stub in 47-02.

## Threat Flags

None beyond the plan threat model. This plan introduced the internal service seam and tenant-bound repository helper already listed in T-47-01 through T-47-06, and added no public endpoint, schema migration, ToolCallContext widening, or agent-run finalizer hook.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 47-03. The trusted projection service can now build a review-required candidate object, but MEM-04 is not phase-complete until 47-03 routes it through the existing case-memory write/review/audit/dedupe path and 47-04 validates metadata/text retrieval.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-02-SUMMARY.md`.
- Task commits found in git history: `5d28154`, `c9757b1`, `6a31dcb`, `f412b1d`.
- Key created/modified files exist: `src/memory/case_precedent.py`, `src/repositories/refund_repo.py`, `tests/memory/test_case_precedent_generation.py`, `tests/memory/test_phase47_case_precedent_alignment.py`, `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`.
- Remaining unrelated dirty files are the three pre-existing user-owned files from the executor prompt and were not staged or committed.

---
*Phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener*
*Completed: 2026-07-03*
