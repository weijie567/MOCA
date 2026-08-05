---
phase: 54-slot-resolution-gate-cutover
plan: "01"
subsystem: agent-routing
tags: [langgraph, slot-resolution, intent-routing, provenance, tdd]

requires:
  - phase: 53-session-context-before-intent-and-contextual-intent-resolve
    provides: Phase 53 contextual intent routing and WR-01 inherited-slot compatibility fix.
provides:
  - Deterministic slot-resolution provenance helper and route_after_slot_resolution contract.
  - Non-active canonical slot_resolution_gate node contract with fail-closed LLM error handling.
  - Focused unit coverage for current-turn, inherited, rejected, conflicting, missing, candidate-only, and WR-01 slot behavior.
affects: [phase-54, phase-55-memory-context-load, phase-58-no-debt-cleanup]

tech-stack:
  added: []
  patterns:
    - Deterministic slot resolver owns active slot satisfaction; LLM output remains candidate/extracted input only.
    - Canonical node trace names can be introduced before active graph registration.

key-files:
  created:
    - src/agent/nodes/slot_resolution_gate.py
    - tests/agent/test_nodes/test_slot_resolution_gate.py
  modified:
    - src/agent/routing.py
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - tests/agent/test_required_slots.py
    - tests/agent/test_nodes/test_receive_request.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Active graph/router cutover remains deferred to 54-02; 54-01 only adds the non-active node contract and deterministic route helper."
  - "route_after_slots is retained only as a compatibility delegate to route_after_slot_resolution."
  - "LLM slot extraction errors strictly fail closed and do not continue with inherited session slots."

patterns-established:
  - "slot_resolution_trace.phase54 carries explicit, inherited, invalidated, stale, incompatible, conflicting, resolved, missing, route, and reason-code provenance."
  - "slot_resolution_gate writes canonical trace node metrics while preserving compatibility fields for downstream consumers."

requirements-completed: [CAGM-05]

duration: 9min
completed: 2026-07-07
---

# Phase 54 Plan 01: Slot Resolution Gate Contract Summary

**Canonical slot-resolution contract with deterministic provenance, fail-closed routing, and a non-active `slot_resolution_gate` node ready for Phase 54-02 graph cutover.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-07T02:33:59Z
- **Completed:** 2026-07-07T02:43:17Z
- **Tasks:** 2
- **Files modified:** 8 plus this summary

## Accomplishments

- Added `resolve_slots_with_provenance(...)` and `route_after_slot_resolution(...)` in `src/agent/routing.py`, with `route_after_slots(...)` reduced to a compatibility delegate.
- Added `slot_resolution_trace` and `missing_required_slots` state/reset support while preserving pending-required-slot `active_flow_state`.
- Created non-active `src/agent/nodes/slot_resolution_gate.py` with canonical trace node name, canonical router metrics, compatibility fields, missing-slot hints, and strict LLM-error fail-closed behavior.
- Added focused TDD coverage for explicit current-turn slots, accepted inherited slots, invalidated/stale/incompatible/conflicting inherited slots, missing required slots, candidate-only non-authority, WR-01 behavior, and node error output.

## Task Commits

1. **Task 1 RED: deterministic provenance tests** - `3195a16` (test)
2. **Task 1 GREEN: deterministic provenance implementation** - `2659145` (feat)
3. **Task 2 RED: canonical node tests** - `99752c3` (test)
4. **Task 2 GREEN: canonical node implementation** - `a36c323` (feat)

**Plan metadata:** pending in final docs commit.

## Files Created/Modified

- `src/agent/nodes/slot_resolution_gate.py` - New canonical slot gate node contract; not registered in the active graph yet.
- `src/agent/routing.py` - Deterministic provenance resolver, canonical slot router, compatibility delegate, and fail-closed route decision helper.
- `src/agent/state.py` - AgentState additions for `slot_resolution_trace` and `missing_required_slots`.
- `src/agent/nodes/receive_request.py` - Per-turn reset for the new slot-resolution fields while preserving pending required-slot flow projection.
- `tests/agent/test_required_slots.py` - Resolver/router provenance, delegate, candidate-only, conflict, and WR-01 coverage.
- `tests/agent/test_nodes/test_receive_request.py` - Reset and state-field coverage.
- `tests/agent/test_nodes/test_slot_resolution_gate.py` - Canonical node unit coverage.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Required local validation entry for the intermediate Task 1 GREEN test expectation failure.

Retained compatibility surface: `src/agent/nodes/extract_slots.py` was intentionally left unchanged. Active graph still registers `extract_slots`; the active graph/router cutover is explicitly deferred to `54-02`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py -q --tb=short` -> `52 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/routing.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/slot_resolution_gate.py src/agent/nodes/extract_slots.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py` -> pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... static graph checks ..."` -> `54-01 final static checks passed`

## Decisions Made

- Kept `resolve_slots_with_metadata(...)` and `resolve_slots_for_completeness(...)` as compatibility APIs backed by the new deterministic resolver.
- Did not add a compatibility mirror under `llm_outputs["extract_slots"]` for the new node; `llm_outputs["slot_resolution_gate"]` is the canonical owner for new node tests.
- On LLM validation/timeout/error, the node explicitly clears active slots and inherited-slot resolution, adds `llm_slot_extraction_error`, and routes to clarification semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected an invalid WR-01 test expectation**
- **Found during:** Task 1 GREEN verification
- **Issue:** The new test expected `ticket_id` to inherit from `ticket_reply_draft` into `action_request`, but the existing policy's `ticket_id` compatibility group does not include `action_request`.
- **Fix:** Changed the business-ID acceptance scenario to `compensation_suggestion`, which is in the existing `ticket_id` cross-intent group, and logged the validation failure in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Files modified:** `tests/agent/test_required_slots.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Focused Task 1 pytest passed after the correction.
- **Committed in:** `2659145`

---

**Total deviations:** 1 auto-fixed blocking test issue.
**Impact on plan:** No scope change; the fix aligned tests with the existing WR-01 policy.

## Issues Encountered

- One intermediate Task 1 GREEN run failed because of the incorrect WR-01 test expectation above. This required appending `.planning/LOCAL-VALIDATION-ISSUES.md`; no environment or tooling issue remained.

## Known Stubs

None. Stub scan hits were normal empty dict/list initializers or test assertions, not UI/data-source stubs.

## User Setup Required

None - no external service configuration required.

## TDD Gate Compliance

- RED gate commits present: `3195a16`, `99752c3`
- GREEN gate commits present after RED: `2659145`, `a36c323`
- REFACTOR gate: not needed

## Next Phase Readiness

Plan 54-02 can wire the active graph to `slot_resolution_gate` and `route_after_slot_resolution`. The legacy `extract_slots` active registration remains intentionally present until that cutover.

## Self-Check: PASSED

- Created files found: `src/agent/nodes/slot_resolution_gate.py`, `tests/agent/test_nodes/test_slot_resolution_gate.py`, this summary.
- Task commits found: `3195a16`, `2659145`, `99752c3`, `a36c323`.

---
*Phase: 54-slot-resolution-gate-cutover*
*Completed: 2026-07-07*
