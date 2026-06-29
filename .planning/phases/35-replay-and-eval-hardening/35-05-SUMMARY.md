---
phase: 35-replay-and-eval-hardening
plan: 35-05
subsystem: replay-eval-release-monitoring
tags: [replay, eval, release-gate, monitoring, pytest]

requires:
  - phase: 35-01
    provides: "Phase 35 coverage matrix and release/monitoring gate rows"
provides:
  - "Hash-owned release gate manifest with statistical_gate_not_demonstrated semantics"
  - "Limited release smoke case artifact for intent, RAG claim, and approval/action safety gaps"
  - "Monitoring gate manifest with pending/not_applicable/sample_only statuses"
  - "Evaluation docs section for Phase 35 replay/eval artifact discovery and approved commands"
affects: [phase35, replay, eval, APF-18]

tech-stack:
  added: []
  patterns:
    - "Release readiness artifacts record hashes and gaps without claiming release-scale evidence."
    - "Monitoring artifacts define schemas/statuses without requiring production telemetry."
    - "Phase 35 docs list only project-scoped uv pytest command entrypoints."

key-files:
  created:
    - eval/replay/release-smoke-cases.v1.json
    - eval/replay/release-gate.v1.json
    - eval/replay/monitoring-gate.v1.json
    - tests/eval/test_phase35_release_monitoring_manifests.py
  modified:
    - docs/evaluation.md
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Release statistical readiness remains non-blocking for Phase 35 and is represented as statistical_gate_not_demonstrated."
  - "Monitoring metrics are schema/status artifacts only until production telemetry exists."
  - "The release smoke dataset is limited to three smoke references and is not release-scale statistical evidence."

patterns-established:
  - "Release gate manifests should bind dataset_path/dataset_hash and coverage_manifest_path/coverage_manifest_hash."
  - "Monitoring manifest statuses are limited to pending, not_applicable, and sample_only for Phase 35."

requirements-completed: [APF-18]

duration: 8 min
completed: 2026-06-29
---

# Phase 35 Plan 35-05: Release and Monitoring Artifact Manifests Summary

**Hash-owned release/monitoring gate manifests with limited smoke coverage and non-blocking sample/telemetry semantics**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-29T15:43:11Z
- **Completed:** 2026-06-29T15:51:02Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `eval/replay/release-smoke-cases.v1.json` with exactly three limited smoke cases: `intent_hard_negatives`, `rag_claim_support`, and `approval_action_safety`.
- Added `eval/replay/release-gate.v1.json` with dataset hash, coverage matrix hash, command entrypoint, metrics, and `statistical_gate_not_demonstrated` sample-gap semantics.
- Added `eval/replay/monitoring-gate.v1.json` with replay completeness, drift, false-negative trend, tool deny reasons, RAG no-evidence trend, and memory write quality metrics.
- Added manifest tests and documented Phase 35 replay/eval artifact discovery plus approved command entrypoints in `docs/evaluation.md`.

## Task Commits

1. **Task 1 RED: Release/monitoring manifest tests** - `3a1d9b7` (`test`)
2. **Task 1 GREEN: Release and monitoring manifests** - `f7bf642` (`feat`)
3. **Task 2: Phase 35 replay/eval docs** - `ca8a49d` (`docs`)

## Files Created/Modified

- `eval/replay/release-smoke-cases.v1.json` - Limited smoke case dataset for the three Phase 35 release areas.
- `eval/replay/release-gate.v1.json` - Non-blocking release gate manifest with smoke dataset hash, coverage matrix hash, and gap reasons.
- `eval/replay/monitoring-gate.v1.json` - Monitoring metric/status manifest for replay/eval operational follow-up.
- `tests/eval/test_phase35_release_monitoring_manifests.py` - Pytest validation for schema, hashes, metric ids, and allowed statuses.
- `docs/evaluation.md` - Phase 35 replay/eval artifact paths, command entrypoints, and non-blocking release/monitoring semantics.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese local validation note for the `shasum` locale warning during hash calculation.

## Decisions Made

- Used `required_min_n=300` for each release metric to align with the release/M6 sample-size semantics in `docs/eval-test-plan.md` while recording only `smoke_n=1` and `statistical_n=0`.
- Kept release and monitoring artifacts as Phase 35 discovery/format outputs, not proof of production readiness.
- Listed `eval/replay/dev-contract-manifest.v1.json` in docs as the companion dev-contract artifact path even though 35-04 owns creating that manifest.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `shasum -a 256` emitted a local locale warning while computing manifest hashes. The command still returned valid SHA-256 values, the hashes were re-verified by the focused pytest test using Python `hashlib`, and the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- `gsd-sdk query roadmap.update-plan-progress 35` still did not match the current Phase 35 roadmap format. `ROADMAP.md` and `STATE.md` were manually corrected to show `4/6` Phase 35 plans complete, with `35-05-PLAN.md` checked and `35-04` still the next incomplete plan; the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_release_monitoring_manifests.py -q --tb=short` - passed (`4 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/eval/test_phase35_release_monitoring_manifests.py` - passed
- `git diff --check` - passed
- Acceptance `rg` probes for release gate, release smoke cases, monitoring metrics/statuses, docs discovery, and unscoped pytest absence - passed.

## Known Stubs

None. Stub-pattern scan found only the pre-existing `null` explanation for deterministic CI latency in `docs/evaluation.md`; no created manifest/test/doc stub prevents the plan goal.

## Threat Flags

None. The plan added static JSON artifacts, tests, and documentation only; no new network endpoint, auth path, file access boundary, or schema trust boundary outside the planned release/monitoring manifest surfaces was introduced.

## TDD Gate Compliance

- Task 1 RED: `3a1d9b7` added failing tests before the release/monitoring manifest files existed.
- Task 1 GREEN: `f7bf642` added the three manifest artifacts and made the focused test suite pass.
- Task 2 was documentation-only and committed separately as `ca8a49d`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for the dev-contract/final closure work. Release and monitoring artifacts are discoverable and explicitly avoid claiming production sample size or production telemetry readiness.

## Self-Check: PASSED

- Found created files: `eval/replay/release-smoke-cases.v1.json`, `eval/replay/release-gate.v1.json`, `eval/replay/monitoring-gate.v1.json`, `tests/eval/test_phase35_release_monitoring_manifests.py`, and this summary.
- Found task commits: `3a1d9b7`, `f7bf642`, and `ca8a49d`.
- Final plan-level pytest, ruff, and `git diff --check` verification passed.

---
*Phase: 35-replay-and-eval-hardening*
*Completed: 2026-06-29*
