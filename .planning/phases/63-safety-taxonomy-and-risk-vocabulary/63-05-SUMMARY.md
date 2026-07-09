---
phase: 63-safety-taxonomy-and-risk-vocabulary
plan: 05
subsystem: safety-taxonomy-closeout
tags: [architecture-guard, safety-taxonomy, drift-guard, closeout]

requires:
  - phase: 63-safety-taxonomy-and-risk-vocabulary
    plan: 02
    provides: Risk gate migration
  - phase: 63-safety-taxonomy-and-risk-vocabulary
    plan: 03
    provides: Action draft migration
  - phase: 63-safety-taxonomy-and-risk-vocabulary
    plan: 04
    provides: Intent/routing migration
provides:
  - Static safety taxonomy drift guards
  - Verified Phase 63 architecture-debt closeout
  - Full focused Phase 63 pytest and ruff evidence
affects: [architecture-tests, architecture-debt, phase-63]

key-files:
  created:
    - tests/architecture/test_safety_taxonomy_boundaries.py
  modified:
    - src/agent/intent_policy.py
    - .planning/ARCHITECTURE-DEBT.md

requirements-completed:
  - SC-63-1
  - SC-63-2
  - SC-63-3
  - D-63-01
  - D-63-02
  - D-63-04
  - D-63-08
  - D-63-09
  - D-63-10
  - D-63-15
  - D-63-16

completed: 2026-07-10
---

# Phase 63 Plan 05: Drift Guards And Closeout Summary

## Accomplishments

- Added `tests/architecture/test_safety_taxonomy_boundaries.py` to guard canonical safety taxonomy ownership.
- Guard now blocks migrated callers from reintroducing local action taxonomy constants, local `_canonical_action_type`, local pre-route action keyword tuples, routing `_ACTION_BOUND_INTENTS`, and `manual_review` / `blocked` hardcoded as action types.
- The new guard caught a residual action/compensation tuple in `_is_next_step_advice_query`; it was migrated to `detect_pre_route_action_request(...)` / `matches_compensation_alias(...)`.
- Added verified Phase 63 closeout entry to `.planning/ARCHITECTURE-DEBT.md`, including the Phase 67 state-machine hardening deferral.

## Task Commits

1. **Task 1 RED: Add safety taxonomy drift guard** - `741382b` (test)
2. **Task 1 GREEN: Remove residual action alias tuple from intent policy** - `0159703` (fix)

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short` -> `5 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/architecture/test_safety_taxonomy_boundaries.py src/agent/intent_policy.py` -> `All checks passed!`
- Full focused phase gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short` -> `1388 passed, 1 warning`
- Full focused ruff gate: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/safety src/agent/nodes/risk_gate.py src/agent/nodes/action_draft.py src/agent/intent_policy.py src/agent/routing.py tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_safety_taxonomy_boundaries.py` -> `All checks passed!`

## Deviations From Plan

- The drift guard intentionally found one residual local action/compensation tuple in `src/agent/intent_policy.py`; the tuple was migrated to taxonomy helpers before closeout.

## Remaining Scope

- Phase 64 owns RAG risk label unification.
- Phase 65 owns trace event / console label consistency.
- Phase 66 owns dev/test/config hygiene.
- Suggested Phase 67 owns state-machine registry and DB/API/frontend CHECK hardening.
