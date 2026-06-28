---
phase: 32-intent-graph-migration
plan: 32-02
subsystem: agent-intent-policy
tags: [intent-policy, routing, classifier, apf-12]
requires:
  - phase: 32-01
    provides: target graph vocabulary and compatibility projection helper
provides:
  - IntentPolicyRegistry effective policy API
  - Registry-owned route/risk/precedence/required-slot consumption in intent routing
  - Candidate-only classifier trace fields with explicit policy_owner
affects: [phase-32, slot-policy-gate, route-after-intent, classifier-trace]
tech-stack:
  added: []
  patterns:
    - Module-level policy registries as deterministic effective-decision boundaries
key-files:
  created: []
  modified:
    - src/agent/intent_policy.py
    - src/agent/routing.py
    - src/agent/nodes/classify_intent.py
    - tests/agent/test_intent_policy_registry.py
    - tests/agent/test_intent_routing.py
    - tests/agent/test_nodes/test_classify_intent.py
key-decisions:
  - "IntentPolicyRegistry now owns effective route, risk, direct-response, evidence, critical-route, and precedence policy APIs."
  - "Classify intent keeps raw LLM output as candidate metadata and records policy_owner='IntentPolicyRegistry' for effective classification."
patterns-established:
  - "Routing consumers monkeypatch registry singletons in tests to prove behavioral consumption."
requirements-completed: [APF-12]
duration: 8min
completed: 2026-06-28
---

# Phase 32 Plan 02: Intent Policy Registry Consumption Summary

**Registry-owned contextual intent routing with candidate-only classifier traces and fail-closed route validation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-28T13:34:20Z
- **Completed:** 2026-06-28T13:42:36Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `INTENT_POLICY_REGISTRY` and `SLOT_POLICY_REGISTRY` module-level singletons plus effective policy methods.
- Migrated `route_after_intent` and classifier state projection off direct route/required-slot/direct-response constants.
- Added behavioral monkeypatch tests proving registry consumption and invalid/raising registry behavior fails closed.

## Task Commits

1. **Task 1 RED:** `92e239b` (test) add failing intent policy registry API tests.
2. **Task 1 GREEN:** `1a2be71` (feat) expose intent policy registry API.
3. **Task 2 RED:** `63f97a5` (test) add failing registry consumer tests.
4. **Task 2 GREEN:** `dbfe3ba` (feat) consume registries in intent routing.

## Files Created/Modified

- `src/agent/intent_policy.py` - Effective intent policy methods and registry singletons.
- `src/agent/routing.py` - Registry-backed `route_after_intent` and known-intent checks for slot routing.
- `src/agent/nodes/classify_intent.py` - Registry-backed precedence, risk, required slots, and candidate/effective trace fields.
- `tests/agent/test_intent_policy_registry.py` - Registry API coverage.
- `tests/agent/test_intent_routing.py` - Behavioral registry-consumption and static source guard coverage.
- `tests/agent/test_nodes/test_classify_intent.py` - Candidate-only and policy-owner classifier coverage.

## Decisions Made

- Unknown intents return no route from `IntentPolicyRegistry.route_for_intent(...)`, causing routers to clarify rather than infer.
- Unknown evidence requirement defaults to `True` in the registry API to avoid accidentally treating unknown intents as evidence-free.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## Known Stubs

None. Empty dict/list literals found by the scan are normal state/test values.

## Auth Gates

None.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py -q --tb=short` - 5 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` - 48 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py tests/agent/test_intent_policy_registry.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/routing.py src/agent/nodes/classify_intent.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py` - passed.
- `! rg -n "DIRECT_RESPONSE_INTENTS|INTENT_ROUTE_POLICY|REQUIRED_SLOT_POLICY" src/agent/routing.py src/agent/nodes/classify_intent.py` - passed.

## Next Phase Readiness

Plan 32-03 can extend `SlotPolicyRegistry` from required-slot lookup into inherited-slot acceptance while preserving the legacy `route_after_slots` edge keys.

## Self-Check: PASSED

- Found `.planning/phases/32-intent-graph-migration/32-02-SUMMARY.md`.
- Found `src/agent/intent_policy.py`.
- Found `src/agent/nodes/classify_intent.py`.
- Found commits `92e239b`, `1a2be71`, `63f97a5`, and `dbfe3ba`.

---
*Phase: 32-intent-graph-migration*
*Completed: 2026-06-28*
