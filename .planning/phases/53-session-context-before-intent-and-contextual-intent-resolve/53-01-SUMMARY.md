---
phase: 53-session-context-before-intent-and-contextual-intent-resolve
plan: "01"
subsystem: agent-graph-intent
tags: [langgraph, intent-routing, contextual-intent, canonical-graph]

requires:
  - phase: 52-safety-pre-route-node
    provides: explicit safety_pre_route node and legacy safe continuation boundary
provides:
  - Canonical contextual_intent_resolve node contract with candidate-only state adapter
  - Non-active route_after_contextual_intent helper routing slot-required paths to extract_slots
  - Compatibility wrapper for classify_intent imports until active graph cutover
affects: [phase-53-02-graph-cutover, phase-53-03-validation-closeout, phase-54-slot-resolution-gate]

tech-stack:
  added: []
  patterns:
    - canonical LangGraph node module with explicit AgentState adapter
    - fail-closed non-active router helper

key-files:
  created:
    - src/agent/nodes/contextual_intent_resolve.py
    - tests/agent/test_nodes/test_contextual_intent_resolve.py
  modified:
    - src/agent/nodes/classify_intent.py
    - src/agent/routing.py
    - tests/agent/test_nodes/test_classify_intent.py
    - tests/test_graph_routing.py
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Kept route_after_contextual_intent non-active until the 53-02 atomic router/policy/graph cutover."
  - "Preserved active route_after_safety, route_after_intent, SAFETY_ROUTES, INTENT_ROUTES, IntentRouteLiteral, and IntentDefinition.initial_route values."
  - "Retained classify_intent.py as a compatibility wrapper while contextual_intent_resolve owns canonical trace and llm_outputs data."

patterns-established:
  - "Canonical intent ownership: contextual_intent_resolve writes classification_trace and llm_outputs['contextual_intent_resolve'] without pre_route_decision."
  - "Route boundary staging: new route_after_contextual_intent is tested but not wired into the active graph before 53-02."

requirements-completed: [CAGM-04]

duration: 7 min
completed: 2026-07-06
---

# Phase 53 Plan 01: Contextual Intent Contract Summary

**Canonical contextual intent resolution now has a tested node contract and staged non-active router helper, while active graph route values remain pre-53-02 compatible.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-06T11:28:44Z
- **Completed:** 2026-07-06T11:36:08Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `contextual_intent_resolve` with canonical trace owner, canonical `llm_outputs["contextual_intent_resolve"]`, explicit state adapter, candidate-only LLM output handling, deterministic pending-slot short reply handling, and allowlisted invalid-output fallback.
- Added tested `route_after_contextual_intent` helper that returns only `clarification_gate`, `final_response`, `investigate`, or `extract_slots`.
- Updated legacy classifier tests away from active `session_memory_load` route and classifier-owned `pre_route_decision` assertions.
- Preserved the 53-01 atomicity boundary: after this plan, the active graph still uses legacy route values compatible with the pre-53-02 graph, and `route_after_contextual_intent` remains non-active until 53-02.

## Task Commits

1. **Task 1: Lock canonical contextual intent and router behavior** - `7e796c5` (test)
2. **Task 2: Implement canonical node adapter and deterministic route contract** - `c9deaef` (feat)

## Files Created/Modified

- `src/agent/nodes/contextual_intent_resolve.py` - Canonical intent node and adapter implementation.
- `src/agent/nodes/classify_intent.py` - Compatibility wrapper for existing imports and pre-53-02 graph registration.
- `src/agent/routing.py` - Non-active `route_after_contextual_intent` helper and allowlist.
- `tests/agent/test_nodes/test_contextual_intent_resolve.py` - Canonical node success, candidate-only, pending-slot, and failure coverage.
- `tests/agent/test_nodes/test_classify_intent.py` - Legacy classifier assertions updated away from active legacy route/pre-route ownership.
- `tests/test_graph_routing.py` - Contextual router totality/fail-closed coverage while active safety routing remains unchanged.
- `.planning/ARCHITECTURE-DEBT.md` - Project-required intent/graph compatibility ledger entry.

## Decisions Made

The active graph cutover was intentionally not performed in 53-01. `route_after_safety`, `route_after_intent`, `SAFETY_ROUTES`, `INTENT_ROUTES`, `IntentRouteLiteral`, and `IntentDefinition.initial_route` still preserve the current graph-compatible values. The new `route_after_contextual_intent` helper is available and tested, but it is not the active graph router until 53-02.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added project-required architecture-debt ledger entry**
- **Found during:** Task 2 (Implement canonical node adapter and deterministic route contract)
- **Issue:** Project instructions require updates to `.planning/ARCHITECTURE-DEBT.md` when modifying the intent-recognition / graph subsystem.
- **Fix:** Added a Chinese ledger entry recording what 53-01 landed and what remains intentionally deferred to 53-02/53-03/54.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Focused pytest, Ruff, and active-route guard scans passed.
- **Committed in:** `c9deaef`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Required project bookkeeping only; runtime scope remains within 53-01 boundaries.

## Issues Encountered

None. The Task 1 RED failure was expected TDD behavior: the focused suite failed because `contextual_intent_resolve` and `route_after_contextual_intent` did not exist yet.

## Verification

- RED gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/test_graph_routing.py -q --tb=short` failed on missing canonical module/helper before implementation.
- GREEN gate: same focused pytest command passed: `90 passed, 1 warning`.
- Ruff: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/classify_intent.py src/agent/routing.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/test_graph_routing.py` passed.
- Artifact scans passed:
  - no `pre_route_decision` in `src/agent/nodes/contextual_intent_resolve.py`
  - no `route_decision.*session_memory_load` or `pre_route_decision` in `tests/agent/test_nodes/test_classify_intent.py`
  - no premature active `session_context_load` safety route or `extract_slots` policy-route cutover in `src/agent/routing.py` / `src/agent/intent_policy.py`

## Known Stubs

None. Stub scan hits were intentional empty defaults/fixtures or historical ledger text, not user-facing placeholder behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 53-02. The canonical node and non-active router helper are tested; 53-02 can now atomically cut over active router/policy/graph path maps without relying on untested surfaces.

## Self-Check: PASSED

- Found `src/agent/nodes/contextual_intent_resolve.py`
- Found `tests/agent/test_nodes/test_contextual_intent_resolve.py`
- Found `.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-01-SUMMARY.md`
- Found task commits `7e796c5` and `c9deaef`
- Confirmed no `.planning/STATE.md` or `.planning/ROADMAP.md` diffs

---
*Phase: 53-session-context-before-intent-and-contextual-intent-resolve*
*Completed: 2026-07-06*
