---
phase: 35-replay-and-eval-hardening
plan: 35-04
subsystem: replay-eval-dev-contract
tags: [replay, eval, dev-contract, pydantic, architecture-tests]

requires:
  - phase: 35-01
    provides: "Phase 35 coverage matrix and strict matrix validator"
  - phase: 35-02
    provides: "Owner/admin-only replay and trace permission regressions"
  - phase: 35-03
    provides: "Golden terminal timelines, operation identity, and redaction negatives"
  - phase: 35-05
    provides: "Non-blocking release and monitoring gate manifests"
provides:
  - "Blocking Phase 35 dev-contract replay/eval manifest"
  - "Strict manifest validator for matrix hash, forbidden behavior cases, commands, and non-blocking gate refs"
  - "Static replay/eval architecture guards for replay-by-rerun, parallel envelopes, real execution surfaces, and deployment creep"
affects: [phase35, replay, eval, APF-18]

tech-stack:
  added: []
  patterns:
    - "Hash-owned eval/replay manifest validated through strict Pydantic models"
    - "Dev-contract gates block phase exit while release/monitoring refs remain non-blocking"
    - "Replay-by-rerun static scans stay scoped to replay-owned code and trace/replay API code"

key-files:
  created:
    - eval/replay/dev-contract-manifest.v1.json
    - src/replay/phase35_eval_manifest.py
    - tests/eval/test_phase35_replay_eval_gates.py
    - tests/architecture/test_phase35_replay_eval_boundaries.py
  modified:
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Phase 35 dev-contract eval gates are blocking phase-exit checks; release sample volume and production telemetry remain non-blocking references."
  - "Forbidden behavior cases are manifest-owned and point to concrete existing focused tests rather than broad statistical datasets."
  - "Replay-by-rerun checks are intentionally scoped to replay-owned code and the trace/replay API router to avoid false positives in legitimate runtime graph paths."

patterns-established:
  - "Dev-contract manifest top-level fields are schema_version, phase, gate_level, blocking, failure_impact, coverage_matrix_path, coverage_matrix_hash, required_gate_categories, forbidden_behaviors, required_test_commands, and non_blocking_gate_refs."
  - "Non-blocking gate refs must exist and match their release/monitoring manifest schema, gate level, blocking value, and failure impact."
  - "Forbidden behavior cases must include concrete test paths under tests/replay, tests/eval, tests/architecture, tests/agent, or tests/actions."

requirements-completed: [APF-18]

duration: 12 min
completed: 2026-06-29
---

# Phase 35 Plan 35-04: Dev-Contract Eval Gate and Forbidden Behavior Datasets Summary

**Blocking replay/eval dev-contract manifest with deterministic forbidden-behavior coverage and static no-scope-creep guards**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-29T15:56:26Z
- **Completed:** 2026-06-29T16:08:16Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `eval/replay/dev-contract-manifest.v1.json` with Phase 35 phase-exit blocking semantics, matrix hash ownership, required dev-contract categories, all D-13/D-18 forbidden behavior cases, approved test commands, and non-blocking release/monitoring refs.
- Added `src/replay/phase35_eval_manifest.py` with strict Pydantic models plus deterministic validation for the coverage matrix hash, required categories, forbidden case ids, approved pytest entrypoints, concrete test paths, and referenced release/monitoring manifests.
- Added eval tests for manifest validity, matrix hash ownership, forbidden behavior coverage, approved MOCA test commands, and release/monitoring non-blocking semantics.
- Added static architecture guards against replay-by-rerun, parallel replay envelopes, real execution/outbox/reconciliation/compensation surfaces, physical microservice deployment creep, and missing concrete forbidden-behavior test paths.

## Task Commits

1. **Task 1 RED: Dev-contract eval gate tests** - `04aba5a` (`test`)
2. **Task 1 GREEN: Dev-contract manifest and validator** - `94841d8` (`feat`)
3. **Task 2 RED: Replay/eval boundary guard** - `803b030` (`test`)
4. **Task 2 GREEN: Static replay/eval boundary guards** - `c110b03` (`test`)

## Files Created/Modified

- `eval/replay/dev-contract-manifest.v1.json` - Blocking Phase 35 dev-contract manifest with required categories, forbidden behavior cases, commands, and non-blocking gate refs.
- `src/replay/phase35_eval_manifest.py` - Strict manifest models, SHA-256 helper, loader, and deterministic validator.
- `tests/eval/test_phase35_replay_eval_gates.py` - Manifest validation and gate-separation tests.
- `tests/architecture/test_phase35_replay_eval_boundaries.py` - Static architecture guard tests for replay/eval scope boundaries.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese local-validation records for the validator bug and repeated `shasum` locale warning.

## Decisions Made

- Dev-contract gates block Phase 35 exit, but release sample volume and production telemetry are only referenced for format validation and remain non-blocking.
- The manifest uses existing focused tests as concrete evidence paths instead of introducing a new dataset runner or ad hoc replay event type.
- Static replay-by-rerun checks are scoped to `src/replay/*.py` and `src/api/routers/traces.py`; unrelated graph execution code remains outside the scan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed non-blocking gate ref validator type error**
- **Found during:** Task 1 GREEN (Dev-contract manifest and validator)
- **Issue:** `_validate_non_blocking_gate_refs()` attempted to subtract a `set` from `REQUIRED_NON_BLOCKING_GATE_PATHS`, which is a dict, causing a `TypeError`.
- **Fix:** Converted the required path mapping keys to a set before calculating missing/unknown ref path differences.
- **Files modified:** `src/replay/phase35_eval_manifest.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py -q --tb=short`; `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/phase35_eval_manifest.py tests/eval/test_phase35_replay_eval_gates.py`
- **Committed in:** `94841d8`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was limited to validator correctness and did not change manifest semantics or Phase 35 scope.

## Issues Encountered

- The local `shasum -a 256` command repeated the known Perl locale warning while calculating the coverage matrix hash. Hash calculation was switched to `UV_CACHE_DIR=/tmp/uv-cache uv run python ... hashlib`, and the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Task 2 used an explicit RED placeholder before replacing it with the passing static guard suite; this was intentional TDD flow.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py -q --tb=short` - passed (`7 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/phase35_eval_manifest.py tests/eval/test_phase35_replay_eval_gates.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase35_replay_eval_boundaries.py -q --tb=short` - passed (`5 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/architecture/test_phase35_replay_eval_boundaries.py` - passed
- Plan-level pytest passed: `12 passed, 1 warning`
- Plan-level ruff passed.
- Acceptance `rg` probes for manifest schema/blocking strings, forbidden case ids, static boundary keywords, and no production execution-surface matches passed.

## Known Stubs

None. Stub-pattern scan found only local empty accumulator lists in validator/test code and explicit `assert ... == []` expectations; no UI/data-source stubs or placeholder behavior were introduced.

## Threat Flags

None. The new manifest trust boundary and static guard tests are explicitly covered by the plan threat model; no unplanned endpoint, auth path, schema boundary, physical deployment surface, or real execution surface was introduced.

## TDD Gate Compliance

- Task 1 RED: `04aba5a` added failing manifest tests before `src/replay/phase35_eval_manifest.py` and the dev-contract manifest existed.
- Task 1 GREEN: `94841d8` added the manifest and validator and made the focused eval tests pass.
- Task 2 RED: `803b030` added a failing static boundary guard placeholder.
- Task 2 GREEN: `c110b03` replaced the placeholder with scoped static architecture guards and made the focused architecture tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `35-06-PLAN.md`. The blocking dev-contract layer now distinguishes deterministic Phase 35 failures from non-blocking release/monitoring insufficiency and statically protects against replay-by-rerun, parallel envelopes, real execution, and deployment creep.

## Self-Check: PASSED

- Found created files: `eval/replay/dev-contract-manifest.v1.json`, `src/replay/phase35_eval_manifest.py`, `tests/eval/test_phase35_replay_eval_gates.py`, `tests/architecture/test_phase35_replay_eval_boundaries.py`, and this summary.
- Found task commits: `04aba5a`, `94841d8`, `803b030`, and `c110b03`.
- Final plan-level pytest and ruff verification passed.

---
*Phase: 35-replay-and-eval-hardening*
*Completed: 2026-06-29*
