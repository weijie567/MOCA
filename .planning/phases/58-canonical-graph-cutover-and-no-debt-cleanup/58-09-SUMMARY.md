---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 09
subsystem: agent-graph-approval-routing
tags: [langgraph, approvals, risk_gate, route-authority, canonical-agent-graph]

requires:
  - phase: 58-07
    provides: legacy risk wrapper deletion and canonical risk_gate ownership
provides:
  - approval retry historical metadata canonicalization to risk_gate
  - canonical-only approval graph resume route authority tests
  - route-authority debt ledger closeout for approval retry compatibility
affects: [phase-58, CAGM-09, approval-boundary, canonical-agent-graph]

tech-stack:
  added: []
  patterns:
    - bounded historical persisted-row mapping for retry metadata
    - current resume route authority accepts only canonical risk_gate
    - approval gate fixtures use canonical risk_gate node identity

key-files:
  created:
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-09-SUMMARY.md
  modified:
    - src/api/routers/approvals.py
    - tests/test_approval_api.py
    - tests/test_approval_gate.py
    - tests/test_graph_routing.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Kept historical persisted retry metadata readable through HISTORICAL_RETRY_ROUTE_TO_CANONICAL, but only after existing retry binding/version checks."
  - "Kept risk_gate as the only current resume route authority emitted by approval retry reconstruction, _should_resume_graph, API responses, and route_after_approval."
  - "Recorded the route-authority cleanup in the architecture debt ledger because this plan closed an approval/graph routing ambiguity."

patterns-established:
  - "Legacy route names may appear in approval retry code only as explicitly named historical persisted-row data-read mapping."
  - "Approval test fixtures use canonical current graph node names; legacy route behavior is covered only as fail-closed input."

requirements-completed: [CAGM-09]

duration: 17min
completed: 2026-07-08
---

# Phase 58 Plan 09: Approval Retry and Graph Route Authority Summary

**Approval retry compatibility now reads historical persisted legacy metadata only through a bounded mapping that emits canonical `risk_gate`, while graph resume authority rejects legacy route values.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-08T03:13:11Z
- **Completed:** 2026-07-08T03:29:56Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Replaced active-looking `LEGACY_RISK_ROUTE` with `HISTORICAL_RETRY_ROUTE_TO_CANONICAL` in approval retry reconstruction.
- Preserved approval/run/hash/snapshot/request/level/assignment version checks before constructing retry resume payloads.
- Added regression coverage proving fresh/current legacy `resume_route="assess_risk_and_approval"` fails closed.
- Migrated approval-gate/API resume fixtures to canonical `risk_gate` and added graph routing coverage for legacy route rejection.
- Updated `.planning/LOCAL-VALIDATION-ISSUES.md` and `.planning/ARCHITECTURE-DEBT.md` as required by project rules.

## Task Commits

1. **Task 1 RED: Add approval retry historical route guard** - `cbc9489` (test)
2. **Task 1 GREEN: Bound approval retry legacy route reads** - `3813135` (fix)
3. **Task 2 RED: Guard canonical approval graph routing** - `d6ddba3` (test)
4. **Task 2 GREEN: Prove canonical approval graph route authority** - `155d790` (fix)

## Files Created/Modified

- `src/api/routers/approvals.py` - Historical persisted retry route mapping now canonicalizes only to `risk_gate`; no `LEGACY_RISK_ROUTE` constant remains.
- `tests/test_approval_api.py` - Added source guard for historical retry mapping and migrated resume fake trace fixture to `risk_gate`.
- `tests/test_approval_gate.py` - Added guard against legacy risk node references in approval-gate fixtures and migrated fixture trace to `risk_gate`.
- `tests/test_graph_routing.py` - Added explicit fail-closed coverage for legacy edit `resume_route`.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Recorded the handled RED validation failures in Chinese.
- `.planning/ARCHITECTURE-DEBT.md` - Recorded closure of the approval retry / graph resume route-authority ambiguity.
- `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-09-SUMMARY.md` - This execution summary.

## Decisions Made

- Kept historical persisted-row compatibility instead of rejecting old rows, because the plan explicitly allowed readable persisted retry metadata if it can never authorize a legacy graph route.
- Did not change production `src/agent/graph.py`; source review and tests confirmed `route_after_approval(...)` already accepts only canonical `risk_gate` for edit reroute.
- Treated ledger updates as required project-rule work, not feature expansion.

## Deviations from Plan

None - plan executed as written. The ledger updates were required by project rules after handled RED validation failures and route-authority debt cleanup.

## Issues Encountered

- Task 1 RED failed as expected on `LEGACY_RISK_ROUTE` in `src/api/routers/approvals.py`; GREEN renamed it to historical persisted-row mapping and focused verification passed.
- Task 2 RED failed as expected on a stale `tests/test_approval_gate.py` trace fixture using `assess_risk_and_approval`; GREEN migrated current fixtures to `risk_gate`.
- No authentication gates or external setup blockers occurred.

## TDD Gate Compliance

- RED gate present for Task 1: `cbc9489` failed before GREEN `3813135`.
- RED gate present for Task 2: `d6ddba3` failed before GREEN `155d790`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only -q --tb=short` - RED failed as expected with `1 failed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` - Task 1 GREEN passed with `66 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py::test_approval_gate_tests_do_not_reference_legacy_risk_node_name tests/test_graph_routing.py::test_route_after_approval_rejects_legacy_risk_resume_route_authority -q --tb=short` - RED failed as expected with `1 failed, 1 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` - Task 2 and final verification passed with `160 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py src/agent/graph.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` - passed with `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`.
- `git diff --check` - passed.

## Known Stubs

None. Stub-pattern scan hits were normal test initializers, existing ledger history, or local variable defaults; no runtime or UI stub was introduced.

## Threat Flags

None. The changed trust surfaces were exactly those in the plan threat model: persisted approval metadata to API retry payload, API resume payload to graph route, and ordinary chat/test fixture route authority. No new endpoint, auth path, file access pattern, or schema boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Ledger Updates

- `.planning/LOCAL-VALIDATION-ISSUES.md` updated because project rules require handled validation failures to be recorded.
- `.planning/ARCHITECTURE-DEBT.md` updated because this plan closed a subsystem-level approval/graph route-authority ambiguity.

## Next Phase Readiness

Plan 58-10 can rely on approval retry compatibility being historical-data-read only and graph resume route authority being canonical-only.

## Self-Check: PASSED

- Found `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-09-SUMMARY.md`.
- Found task commits `cbc9489`, `3813135`, `d6ddba3`, and `155d790`.
- Confirmed no tracked file deletions in task commits.

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
