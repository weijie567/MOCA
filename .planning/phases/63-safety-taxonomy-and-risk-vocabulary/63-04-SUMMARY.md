---
phase: 63-safety-taxonomy-and-risk-vocabulary
plan: 04
subsystem: intent-policy-routing
tags: [intent-policy, routing, safety-taxonomy, action-taxonomy, tdd]

requires:
  - phase: 63-safety-taxonomy-and-risk-vocabulary
    plan: 01
    provides: Canonical safety taxonomy registry and pre-route action alias helper
provides:
  - Registry-owned action-bound intent metadata
  - Taxonomy-backed deterministic pre-route action detection
  - Registry-derived routing evidence/action-bound fallback
  - Safe fail-closed behavior when registry lookup fails
affects: [intent-policy, routing, contextual-intent-resolve, phase-63]

key-files:
  modified:
    - src/agent/intent_policy.py
    - src/agent/routing.py
    - tests/agent/test_intent_policy_registry.py
    - tests/agent/test_intent_routing.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

requirements-completed:
  - SC-63-1
  - SC-63-3
  - D-63-01
  - D-63-04
  - D-63-08
  - D-63-09
  - D-63-10
  - D-63-12
  - D-63-15

completed: 2026-07-10
---

# Phase 63 Plan 04: Intent Policy And Routing Taxonomy Migration Summary

## Accomplishments

- Added `IntentDefinition.action_bound` and registry APIs `action_bound_intents()` / `is_action_bound_intent(...)`.
- Marked `action_request`, `compensation_suggestion`, and `complaint_escalation` as registry-owned action-bound intents.
- Replaced `detect_pre_route(...)` local direct action term tuples with `detect_pre_route_action_request(...)` from `src.agent.safety.taxonomy`.
- Preserved approval-chat hard negatives, multi-target clarification, escalation pre-route behavior, and compensation/coupon policy-question hard negatives.
- Removed routing-local `_ACTION_BOUND_INTENTS`; `_policy_evidence_required(...)` and `_action_bound_or_high_risk(...)` now derive from `INTENT_POLICY_REGISTRY`.
- Added fail-closed registry exception fallback with `safe_routing_reasons` markers.

## Task Commits

1. **Task 1 RED: Pin registry derived intent safety routing** - `535a63d` (test)
2. **Task 2 GREEN: Derive intent safety routing from registries** - `379bcf8` (feat)

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py -q --tb=short` -> `1223 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short` -> `38 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py` -> `All checks passed!`

## Deviations From Plan

- Initial source exploration used two stale test filenames in an `rg` command. The invalid scan was discarded, the correct files were read, and the issue was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Remaining Scope

- Phase 63 Plan 05 must add drift guards / final closeout verification and ensure no local action/risk taxonomy duplicates remain in active safety surfaces.
- Phase 64 remains next chained phase after Phase 63 completes.
