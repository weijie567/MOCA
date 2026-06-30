---
phase: 35-replay-and-eval-hardening
plan: 35-01
subsystem: replay-eval-contracts
tags: [replay, eval, pydantic, pytest, coverage-matrix]

requires:
  - phase: 34-approval-and-actiondraft-boundary-hardening
    provides: "approval/action/risk bindings that Phase 35 maps into replay and eval coverage"
provides:
  - "Phase 35 replay/eval coverage matrix with all required platform boundary rows"
  - "Strict Pydantic loader and deterministic validator for matrix drift"
  - "Blocking pytest guard for registered replay events, gate levels, six-plan roadmap shape, and approved pytest entrypoints"
affects: [phase35, replay, eval, APF-17, APF-18]

tech-stack:
  added: []
  patterns:
    - "Machine-checkable eval/replay contract artifact under eval/replay/"
    - "Strict Pydantic artifact validator returning deterministic error strings"
    - "Matrix rows use existing replay events plus payload/projection contract tests"

key-files:
  created:
    - eval/replay/phase35-coverage-matrix.v1.json
    - src/replay/phase35_matrix.py
    - tests/replay/test_phase35_coverage_matrix.py
  modified:
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Phase 35 matrix coverage uses existing registered replay events plus payload/projection assertions; no replay event type was added."
  - "The six-plan Phase 35 shape is enforced by tests against ROADMAP.md."
  - "MOCA pytest command discipline is enforced for Phase 35 plan and matrix artifacts through an approved-entrypoint scan."

patterns-established:
  - "Coverage rows must map boundary, owner, replay_events, trace_projection, eval_gate_level, forbidden_behaviors, acceptance_tests, decision_assertions, event_strategy, and notes."
  - "Left-half generic-event boundaries require focused assertion ids outside the matrix self-test."

requirements-completed: [APF-17, APF-18]

duration: 12 min
completed: 2026-06-29
---

# Phase 35 Plan 35-01: Coverage Matrix and Replay Contract Inventory Summary

**Machine-checkable Phase 35 replay/eval coverage matrix backed by a strict validator and drift-guard pytest suite**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-29T14:32:59Z
- **Completed:** 2026-06-29T14:44:56Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `eval/replay/phase35-coverage-matrix.v1.json` with all 13 required platform boundaries and `event_strategy="existing_event_plus_payload_contract"` throughout.
- Added `src/replay/phase35_matrix.py` with strict Pydantic models, `REQUIRED_BOUNDARIES`, `load_phase35_matrix()`, and `validate_phase35_matrix()`.
- Added blocking matrix tests for boundary coverage, registered replay event usage, decision assertions, gate-level coverage, six-plan roadmap shape, and MOCA-approved pytest entrypoints.

## Task Commits

1. **Task 1 RED: Matrix contract tests** - `dcc3670` (`test`)
2. **Task 1 GREEN: Matrix artifact and validator** - `3a4f743` (`feat`)
3. **Task 2: Matrix drift and six-plan guards** - `55a7896` (`test`)

## Files Created/Modified

- `eval/replay/phase35-coverage-matrix.v1.json` - Phase 35 dev-contract/release/monitoring matrix for replay/eval boundary coverage.
- `src/replay/phase35_matrix.py` - Strict matrix models, loader, and drift validator.
- `tests/replay/test_phase35_coverage_matrix.py` - Blocking pytest contract for matrix shape, event registry usage, assertion focus, roadmap shape, and approved pytest entrypoints.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese local-validation record for the Task 2 scan false positive and fix.

## Decisions Made

- Used only existing replay event names from `src/replay/validators.py`; no event registry, ORM constraint, or migration change was needed.
- Kept release and monitoring rows in the matrix while requiring deterministic safety boundaries to remain `dev-contract`.
- Treated Phase 35 plan/matrix command discipline as a static contract in the same matrix test file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pytest entrypoint scan false positive**
- **Found during:** Task 2 (Guard matrix drift and six-plan Phase 35 shape)
- **Issue:** The initial inline-code scanner treated explanatory text in `35-01-PLAN.md` mentioning "unscoped pytest entrypoints" as an actual unapproved pytest command.
- **Fix:** Narrowed `_pytest_command_snippets()` to collect only command-shaped snippets from line starts, inline code, or `<automated>` tags.
- **Files modified:** `tests/replay/test_phase35_coverage_matrix.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_coverage_matrix.py -q --tb=short`; `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/replay/test_phase35_coverage_matrix.py`
- **Committed in:** `55a7896`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix kept Task 2 scoped to static test coverage and command-discipline enforcement. No production behavior or replay event registry changed.

## Issues Encountered

- Task 2 initially failed because the new command scanner flagged prose rather than an executable command. The scanner was tightened and the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_coverage_matrix.py -q --tb=short` - passed (`18 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/phase35_matrix.py tests/replay/test_phase35_coverage_matrix.py` - passed
- Acceptance `rg` probes for required boundaries, event strategy, validator symbols, `PLAN_PROGRESS_RE`, and `35-06-PLAN.md` - passed

## Known Stubs

None. Stub-pattern scan only found internal empty accumulator lists in validator/test code, not UI or data-source stubs.

## TDD Gate Compliance

- RED gate: `dcc3670` added failing tests before `src/replay/phase35_matrix.py` existed.
- GREEN gate: `3a4f743` added the validator and matrix; focused pytest then passed.
- Task 2 was intentionally test-only and committed as `55a7896` after the drift guards passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `35-02-PLAN.md`. The matrix now names the proof/permission, timeline, redaction, eval, release, monitoring, and architecture tests that later Phase 35 plans must create or extend.

## Self-Check: PASSED

- Found created files: `eval/replay/phase35-coverage-matrix.v1.json`, `src/replay/phase35_matrix.py`, `tests/replay/test_phase35_coverage_matrix.py`, and this summary.
- Found task commits: `dcc3670`, `3a4f743`, and `55a7896`.
- Verification commands passed after implementation.

---
*Phase: 35-replay-and-eval-hardening*
*Completed: 2026-06-29*
