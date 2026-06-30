---
phase: 34-approval-and-actiondraft-boundary-hardening
plan: 34-02
subsystem: risk-gate-routing
tags: [risk-gate, approval-gate, action-draft, langgraph, durable-bindings]

requires:
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-01
    provides: Phase 34 RiskDecisionV1, TargetMerchantBindingV1, AutoAllowedActionBindingV1, and typed approval/action refs
provides:
  - Target `risk_gate` semantics under the legacy `assess_risk_and_approval` runtime node
  - Structured `approval_plan`, `risk_decision`, target merchant, business fact, verified evidence, claim summary, and idempotency state
  - Fail-closed `route_after_risk` behavior for approval and auto-allowed action draft paths
affects: [risk_gate, route_after_risk, graph-vocabulary, approval-gate, action-draft]

tech-stack:
  added: []
  patterns: [TDD, strict Pydantic boundary validation, deterministic fail-closed routing]

key-files:
  created:
    - tests/architecture/test_phase34_approval_action_boundaries.py
  modified:
    - src/agent/state.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/graph.py
    - src/agent/graph_vocabulary.py
    - tests/agent/test_nodes/test_assess_risk_and_approval.py
    - tests/test_graph_routing.py

key-decisions:
  - "Runtime keeps the legacy `assess_risk_and_approval` node key while graph vocabulary projects it to target `risk_gate`."
  - "Approval routing requires an exact structured `approval_plan`; display-only proposed action and snapshot refs alone are insufficient."
  - "Auto-draft routing requires an exact `AutoAllowedActionBindingV1`; transient `auto_allowed=True` is not route authority."

patterns-established:
  - "Risk gate binding material is built only from service-approved business facts, claim verification bundles, and safe support refs."
  - "Route decisions validate structured durable binding state before crossing into approval or action-draft nodes."

requirements-completed: [APF-16]

duration: 18 min
completed: 2026-06-29
---

# Phase 34 Plan 02: Risk Gate Binding and Routing Summary

**Risk gate now writes structured approval/action bindings and graph routing fails closed without durable exact binding material**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added Phase 34 fields to `AgentState` for approval plans, risk decisions, target merchant bindings, business fact refs, verified evidence refs, claim verification summaries, idempotency keys, and auto-allowed bindings.
- Extended `assess_risk_and_approval` to emit target `risk_gate` binding outputs while failing closed when target merchant/business fact material is missing or ambiguous.
- Added graph vocabulary entries for `assess_risk_and_approval -> risk_gate` and runtime `route_after_risk`.
- Hardened `route_after_risk` so approval requires exact `approval_plan` bindings and auto-draft requires exact `AutoAllowedActionBindingV1`.
- Added static architecture coverage proving `approval_gate` does not own blocked/approval-required/auto-allowed routing policy.

## Task Commits

1. **Task 1 RED: Risk gate binding tests** - `3eaa818` (test)
2. **Task 1 GREEN: Risk gate binding state** - `0ab6734` (feat)
3. **Task 2 RED: Durable routing tests** - `b286f45` (test)
4. **Task 2 GREEN: Durable risk routing** - `1dc4bdb` (feat)

## Files Created/Modified

- `tests/architecture/test_phase34_approval_action_boundaries.py` - Phase 34 graph vocabulary and approval gate responsibility boundary tests.
- `src/agent/state.py` - Added optional Phase 34 risk/approval/action binding state fields.
- `src/agent/nodes/assess_risk_and_approval.py` - Builds structured risk decision, approval plan, target merchant, safe refs, idempotency, and auto-allowed binding outputs.
- `src/agent/graph.py` - Routes only from exact approval plan or auto-allowed binding material; adds action draft conditional edge from risk.
- `src/agent/graph_vocabulary.py` - Adds target `risk_gate` compatibility alias and runtime `route_after_risk`.
- `tests/agent/test_nodes/test_assess_risk_and_approval.py` - Node-level Phase 34 binding and fail-closed tests.
- `tests/test_graph_routing.py` - Durable approval/auto-allowed routing tests.

## Decisions Made

- Missing or ambiguous target merchant authority clears executable action state and returns the safe manual-review response.
- `verified_evidence_refs` come from claim bundle safe support refs, not candidate-only retrieved evidence.
- Auto-allowed binding uses a separate deterministic idempotency key from the approval idempotency key.

## Deviations from Plan

None - plan executed as written. Existing routing tests were updated to match the current Phase 33+ graph contract where recommendation routes to `claim_verify` and investigate routes to `rag_context_build` when policy evidence is required.

## Issues Encountered

- TDD RED and intermediate GREEN runs failed as expected until `approval_plan` and `auto_allowed_binding` route validation were implemented.
- The auto-allowed route test needed to simulate LangGraph state merge semantics by routing over `{**input_state, **result}` so prior `claim_verification_bundle` state remains available.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_phase34_approval_action_boundaries.py -q --tb=short` -> `69 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/state.py src/agent/nodes/assess_risk_and_approval.py src/agent/graph.py src/agent/graph_vocabulary.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_phase34_approval_action_boundaries.py` -> passed
- `git diff --check` -> passed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 34-03. Approval service/API work can consume `approval_plan`, `risk_decision`, target merchant bindings, business fact refs, verified evidence refs, and approval idempotency keys from graph state.

## Self-Check: PASSED

- Focused pytest and ruff checks pass through the MOCA-approved `uv run` entrypoint.
- `rg -n "approval_plan|risk_decision_ref|approval_idempotency_key|target_merchant_id|auto_allowed_binding" src/agent/state.py src/agent/nodes/assess_risk_and_approval.py` returns matches.
- `rg -n "AutoAllowedActionBindingV1|auto_allowed_binding|approval_plan" src/agent/graph.py` returns matches.
- `rg -n "auto_allowed|approval_required|blocked" src/agent/nodes/approval_gate.py` returns no policy-decision branch matches.

---
*Phase: 34-approval-and-actiondraft-boundary-hardening*
*Completed: 2026-06-29*
