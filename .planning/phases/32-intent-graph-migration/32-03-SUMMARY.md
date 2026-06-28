---
phase: 32-intent-graph-migration
plan: 32-03
subsystem: agent-slot-policy
tags: [slot-policy, session-memory, routing, apf-12]
requires:
  - phase: 32-01
    provides: slot_resolution_gate and route_after_slot_resolution vocabulary aliases
  - phase: 32-02
    provides: module-level policy registry consumption pattern
provides:
  - SlotInheritanceContext and SlotInheritanceDecision policy API
  - Registry-owned inherited-slot acceptance with explicit rejection reason codes
  - Additive slot_resolution_gate / route_after_slot_resolution trace metadata
affects: [phase-32, session-memory, route-after-slots, trace-projection]
tech-stack:
  added: []
  patterns:
    - Deterministic slot inheritance context passed into SlotPolicyRegistry
key-files:
  created: []
  modified:
    - src/agent/intent_policy.py
    - src/agent/routing.py
    - src/agent/nodes/extract_slots.py
    - tests/agent/test_required_slots.py
    - tests/agent/test_session_memory_integration.py
    - tests/agent/test_graph.py
key-decisions:
  - "SlotPolicyRegistry owns inherited-slot acceptance and required-slot missing checks."
  - "slot_resolution_gate remains a semantic projection over extract_slots in Phase 32, not a new physical graph node."
patterns-established:
  - "Rejected inherited slots remain absent on repeated resolution; invalidated trusted slots are diagnostic metadata only."
requirements-completed: [APF-12]
duration: 10min
completed: 2026-06-28
---

# Phase 32 Plan 03: Slot Policy Gate and Target Router Projection Summary

**Registry-owned slot inheritance decisions with deterministic freshness checks and additive slot_resolution_gate projection**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-28T13:42:40Z
- **Completed:** 2026-06-28T13:52:32Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `SlotInheritanceContext` / `SlotInheritanceDecision` and explicit reason codes for missing, untrusted, mismatched, stale, invalidated, incompatible, and accepted slots.
- Moved required-slot missing checks and inherited-slot acceptance through `SLOT_POLICY_REGISTRY`.
- Added `extract_slots` trace metadata for `target_node="slot_resolution_gate"` and `target_router="route_after_slot_resolution"`.

## Task Commits

1. **Task 1 RED:** `cb73144` (test) add failing slot policy inheritance tests.
2. **Task 1 GREEN:** `3207015` (feat) move slot inheritance policy to registry.
3. **Task 2 RED:** `f2ac9af` (test) add failing slot resolution projection tests.
4. **Task 2 GREEN:** `9254eb6` (feat) project slot resolution target metadata.

## Files Created/Modified

- `src/agent/intent_policy.py` - Slot inheritance context/decision dataclasses and acceptance/missing-slot APIs.
- `src/agent/routing.py` - Registry-backed slot completeness and inherited-slot acceptance.
- `src/agent/nodes/extract_slots.py` - Additive target slot-resolution trace metadata.
- `tests/agent/test_required_slots.py` - Reason-code, deterministic time, and idempotence tests.
- `tests/agent/test_session_memory_integration.py` - Trace metadata assertion for `extract_slots`.
- `tests/agent/test_graph.py` - Legacy `route_after_slots` key and target router projection assertion.

## Decisions Made

- `run_started_at` is used as deterministic current time when available; otherwise slot freshness falls back to current UTC time to preserve existing behavior.
- Invalidated trusted session slots are retained only as rejected diagnostic metadata and do not satisfy required slots.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## Known Stubs

None. Empty literals found by the scan are existing prompt/test fixture values, not deferred implementation stubs.

## Auth Gates

None.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py -q --tb=short` - 15 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py -q --tb=short` - 48 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/routing.py tests/agent/test_required_slots.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/routing.py src/agent/nodes/extract_slots.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py` - passed.

## Next Phase Readiness

Plan 32-04 can project target graph vocabulary into trace/API surfaces and add safe target merchant-context status without changing legacy route keys.

## Self-Check: PASSED

- Found `.planning/phases/32-intent-graph-migration/32-03-SUMMARY.md`.
- Found `src/agent/nodes/extract_slots.py`.
- Found `tests/agent/test_required_slots.py`.
- Found commits `cb73144`, `3207015`, `f2ac9af`, and `9254eb6`.

---
*Phase: 32-intent-graph-migration*
*Completed: 2026-06-28*
