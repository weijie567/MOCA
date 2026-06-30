---
phase: 31-memory-platform-boundary
plan: 31-01
subsystem: testing
tags: [memory, red-tests, contextual-only, authority-boundary, tdd]

requires:
  - phase: 24.2
    provides: SessionMemoryBundle read path and legacy session_memory compatibility
  - phase: 24.4
    provides: memory non-authority eval precedent
  - phase: 30-03
    provides: business fact authority substitution guards
provides:
  - RED tests for contextual-only memory refs and status refs
  - RED tests for SessionContextMemory and session_context target aliases
  - RED tests for memory authority deny-list behavior
  - repaired known memory-supported action dependency expectation
affects: [Phase 31, APF-09, APF-10, Phase 33, Phase 34, Phase 35]

tech-stack:
  added: []
  patterns:
    - Wave 0 RED tests import planned DTOs without production implementation
    - Contextual memory refs use authority_class=contextual_only and cannot satisfy authority DTOs
    - Legacy session_memory assertions stay beside target session_context assertions during migration

key-files:
  created:
    - tests/memory/test_context_refs.py
    - .planning/phases/31-memory-platform-boundary/31-01-SUMMARY.md
  modified:
    - tests/agent/test_session_memory_load.py
    - tests/memory/test_session_memory_bundle.py
    - tests/agent/test_memory_evidence_boundary.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "31-01 remained RED-only: no production src/ files were changed."
  - "Memory-supported action dependencies are classified as insufficient authority, not semantic contradiction."
  - "Contextual-only memory refs/status refs are pinned as incompatible with evidence, business fact, approval, replay, and MaterialClaim authority paths."

patterns-established:
  - "RED contract-first memory DTO tests: planned imports fail until src.memory.context_refs exists."
  - "Compatibility migration tests: target session_context outputs are asserted while legacy session_memory fields remain unchanged."
  - "Authority deny-list tests: contextual-only dicts are rejected by strict downstream DTOs and verifier support paths."

requirements-completed: [APF-09, APF-10]

duration: 7min
completed: 2026-06-28
---

# Phase 31 Plan 01: Wave 0 Memory Boundary RED Tests Summary

**Contextual-only memory boundary RED tests now pin target session-context vocabulary and deny memory as authority.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-28T05:50:38Z
- **Completed:** 2026-06-28T05:57:42Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `tests/memory/test_context_refs.py` with RED contract tests for `SessionContextRef`, `ReviewedMemoryRef`, `SessionContextLoadStatusV1`, `ReviewedMemoryContextRetrieveStatusV1`, `ReviewedMemoryContextBundle`, and `MemoryWriteDecisionV2`.
- Extended session memory tests to require target `session_context`, `session_context_bundle`, and `session_context_load_status` outputs while preserving legacy `session_memory` / `session_memory_bundle` assertions.
- Repaired the known RED mismatch in `test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority`: memory-supported dependencies now expect `VerificationOutcome.INSUFFICIENT`.
- Added contextual-only authority deny-list RED coverage for `EvidenceRefV1`, `BusinessFactRefV1`, `ApprovalRequestCreateCommand.evidence_refs`, `ReplayEventV3`, and `MaterialClaim.business_fact_refs`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RED contextual ref and session-context target tests** - `06d7a6a` (test)
2. **Task 2: Repair known RED authority-boundary item and add contextual-only deny-list assertions** - `61bb95c` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/memory/test_context_refs.py` - New RED tests for planned contextual-only memory DTOs, status refs, strict extra-field rejection, and memory module import boundaries.
- `tests/agent/test_session_memory_load.py` - Adds RED assertions for target session-context fields beside existing legacy session memory assertions.
- `tests/memory/test_session_memory_bundle.py` - Adds RED projection test for `SessionContextMemory` / `SessionContextBundle` wrapping existing bundle surfaces.
- `tests/agent/test_memory_evidence_boundary.py` - Repairs known expected outcome and adds contextual-only authority deny-list tests.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records a zsh validation command pitfall required by project local-validation rules.

## Decisions Made

- Kept this plan as a true Wave 0 RED slice. No production `src/` files were edited.
- Treated `src.memory.context_refs` absence as the intended RED failure for Task 1.
- Used verifier-path assertions for `EvidenceRefV1` support instead of relying on bare `EvidenceRefV1` parse rejection, because that schema is not currently strict.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed zsh acceptance command variable collision**
- **Found during:** Task 1 acceptance checks
- **Issue:** The temporary shell command used `status=$?`; in zsh, `status` is a read-only special parameter, so the check failed before evaluating the files.
- **Fix:** Re-ran the acceptance check with `rg_status=$?` and recorded the issue in `.planning/LOCAL-VALIDATION-ISSUES.md` per project rules.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `rg_status` retry returned `NO_MATCHES` for `xfail|skip(`.
- **Committed in:** `06d7a6a`

---

**Total deviations:** 1 auto-fixed (1 blocking validation-command issue)
**Impact on plan:** No product behavior or production code changed. The extra planning file edit was required by MOCA local-validation recording rules.

## Issues Encountered

- Task 1 RED command failed as intended because `src.memory.context_refs` does not exist yet.
- Task 2 full-file RED command failed as intended because the verifier does not yet classify new `session_context_refs`, `reviewed_memory_refs`, and `memory_status_refs` as memory authority sources.
- Existing LangGraph deprecation/config warnings appeared during tests; they were pre-existing and non-blocking.

## Known Stubs

None. Stub scan found only intentional empty test literals such as `recent_messages=[]`, `tool_summaries=[]`, and existing historical notes in `.planning/LOCAL-VALIDATION-ISSUES.md`; no runtime placeholder data was introduced.

## Threat Flags

None. This plan added tests only and introduced no new network endpoints, auth paths, file access patterns, schema migrations, or runtime trust-boundary surfaces.

## Authentication Gates

None.

## Verification

- `bash -lc 'set +e; uv run pytest tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py -q; py_status=$?; test "$py_status" -ne 0'` - passed as RED wrapper; underlying failure is `ModuleNotFoundError: No module named 'src.memory.context_refs'`.
- `uv run ruff check tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py` - passed.
- `uv run pytest tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority -q` - passed (`1 passed`, 1 existing warning).
- `bash -lc 'set +e; uv run pytest tests/agent/test_memory_evidence_boundary.py -q; py_status=$?; test "$py_status" -ne 0'` - passed as RED wrapper; underlying failure is the new contextual-only verifier reason-code assertion.
- `uv run ruff check tests/agent/test_memory_evidence_boundary.py` - passed.
- `git diff --check` - passed.

## TDD Gate Compliance

This plan is intentionally RED-only. It produced test commits only and no GREEN `feat(...)` commit because production implementation is explicitly deferred to later Phase 31 plans.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 31-03 can implement `src.memory.context_refs` and the target session-context DTO aliases against the Task 1 RED tests. Plan 31-06 can extend verifier authority classification so contextual-only memory refs/status refs produce the expected deny-list reason codes.

---
*Phase: 31-memory-platform-boundary*
*Completed: 2026-06-28*

## Self-Check: PASSED

- Found summary file at `.planning/phases/31-memory-platform-boundary/31-01-SUMMARY.md`.
- Found key files `tests/memory/test_context_refs.py`, `tests/agent/test_session_memory_load.py`, `tests/memory/test_session_memory_bundle.py`, `tests/agent/test_memory_evidence_boundary.py`, and `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Found task commits `06d7a6a` and `61bb95c` in git history.
- No unexpected tracked file deletions were detected in task commits.
- Shared `.planning/STATE.md` and `.planning/ROADMAP.md` were not updated by this executor.
