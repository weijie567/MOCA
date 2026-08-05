---
phase: 52-safety-pre-route-node
plan: "01"
subsystem: agent-graph
tags: [safety-pre-route, intent-policy, langgraph, tdd]

requires:
  - phase: 50-canonical-agent-graph-migration-spec-and-guardrails
    provides: canonical graph migration charter and safety pre-route contract
  - phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix
    provides: baseline graph guardrails before runtime rewiring
provides:
  - deterministic safety_pre_route node implementation
  - shared approval-like short-reply detector in intent policy
  - unit tests for pre-route safety decisions, trace visibility, forbidden writes, and forbidden dependencies
affects: [phase-52, phase-52-02, phase-52-03, phase-53]

tech-stack:
  added: []
  patterns:
    - side-effect-free deterministic graph node
    - TDD red/green commit sequence for node extraction

key-files:
  created:
    - src/agent/nodes/safety_pre_route.py
    - tests/agent/test_nodes/test_safety_pre_route.py
    - .planning/phases/52-safety-pre-route-node/52-01-SUMMARY.md
  modified:
    - src/agent/intent_policy.py
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - src/agent/nodes/classify_intent.py
    - tests/agent/test_nodes/test_receive_request.py

key-decisions:
  - "Approval-like standalone short replies are now detected by shared intent-policy helpers and folded into detect_pre_route."
  - "safety_pre_route writes only pre_route_decision, safety_flags, routing_hints, and trace_steps; graph wiring remains Plan 52-02 scope."

patterns-established:
  - "Safety pre-route node appends its own trace step without replacing receive_request trace history."
  - "Static unit guard checks the new node for forbidden dependency symbols instead of scanning generic authority field strings."

requirements-completed: [CAGM-03]

duration: 5min
completed: 2026-07-06
---

# Phase 52 Plan 01: Safety Pre-route Node Summary

**Deterministic `safety_pre_route` node with shared approval-like short-reply detection and unit-level no-side-effect guarantees.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-06T08:54:32Z
- **Completed:** 2026-07-06T08:59:04Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `src/agent/nodes/safety_pre_route.py`, which inspects only current state/query, calls `detect_pre_route`, appends a `safety_pre_route` trace step, and returns only deterministic metadata.
- Moved approval/action-like short-reply recognition into `intent_policy.py` and reused it from `classify_intent`, avoiding a second detector.
- Added focused tests for approval chat, short replies, multi-target requests, safety-sensitive action/escalation tagging, ordinary negative controls, trace preservation, forbidden output fields, and forbidden dependency symbols.

## Task Commits

1. **Task 1: Lock safety pre-route behavior before implementation** - `64fb74a` (test)
2. **Task 2: Implement deterministic safety_pre_route node and shared helpers** - `b9dd989` (feat)

## Files Created/Modified

- `src/agent/nodes/safety_pre_route.py` - New deterministic node that emits `pre_route_decision`, `safety_flags`, `routing_hints`, and appended trace metadata only.
- `src/agent/intent_policy.py` - Shared short-reply normalization/helpers plus `detect_pre_route` coverage for standalone approval/action-like replies.
- `src/agent/state.py` - Declares `pre_route_decision` and `safety_flags` as explicit ephemeral state fields.
- `src/agent/nodes/receive_request.py` - Resets the new safety fields at the start of each turn.
- `src/agent/nodes/classify_intent.py` - Reuses shared intent-policy short-reply helpers instead of owning a duplicate approval/action detector.
- `tests/agent/test_nodes/test_safety_pre_route.py` - New direct node tests and static no-dependency guard.
- `tests/agent/test_nodes/test_receive_request.py` - Reset/type coverage for safety pre-route fields.

## Decisions Made

- `detect_pre_route` now treats standalone approval/action-like replies such as `同意`, `approve`, and `doit` as `approval_chat_not_trusted`, so the new node and legacy classifier share one source of truth.
- Plan 52-01 intentionally did not edit `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/graph_vocabulary.py`, `.planning/STATE.md`, or `.planning/ROADMAP.md`; graph wiring and docs/ledger closeout remain owned by Plans 52-02 and 52-03.

## TDD Gate Compliance

- **RED:** `64fb74a` added failing tests. Verification failed as expected with missing node/helper/state fields.
- **GREEN:** `b9dd989` implemented the node and shared helpers. Focused pytest and ruff passed.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` - `46 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_safety_pre_route.py` - passed

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope expansion; graph routing remains deferred to Plan 52-02.

## Issues Encountered

None. The initial failing pytest run was the expected TDD RED gate.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 52-02 can wire `safety_pre_route` into the graph and add `route_after_safety`. The node contract is now available and covered, but CAGM-03 is not fully runtime-complete until Plans 52-02 and 52-03 finish graph wiring, architecture guardrails, trace vocabulary, and compatibility documentation.

## Self-Check: PASSED

- Found created files: `src/agent/nodes/safety_pre_route.py`, `tests/agent/test_nodes/test_safety_pre_route.py`, `.planning/phases/52-safety-pre-route-node/52-01-SUMMARY.md`
- Found task commits: `64fb74a`, `b9dd989`
- Confirmed `.planning/STATE.md` and `.planning/ROADMAP.md` have no diff

---
*Phase: 52-safety-pre-route-node*
*Completed: 2026-07-06*
