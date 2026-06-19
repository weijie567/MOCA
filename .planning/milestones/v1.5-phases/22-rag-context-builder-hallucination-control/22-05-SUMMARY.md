---
phase: 22-rag-context-builder-hallucination-control
plan: "05"
subsystem: rag-context
tags: [rag-context, deterministic-routing, graph-routing, action-boundary, final-response, pytest]

# Dependency graph
requires:
  - phase: 22-04
    provides: material claim verifier statuses, reason codes, and safe verification DTOs
provides:
  - Deterministic backend verifier route map with fail-closed defaults
  - Redacted AgentState verifier route/status/reason/metrics fields
  - Shared ContextBuilder and MaterialClaimVerifier recommendation integration
  - Conditional recommendation-to-action graph routing
  - Non-allow verifier guards before risk assessment, approval, action draft, and final response
  - Safe user-facing final-response wording for verifier stop states
affects: [phase-22, recommendation-generation, graph-routing, action-boundary, final-response]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Backend-owned verification routes; model output never chooses safety-critical route outcomes.
    - Non-allow verifier routes stop before action boundaries and render through safe final-response categories.
    - Recommendation prompts consume prompt-safe ContextBuilder projections while preserving retrieval/search behavior.

key-files:
  created:
    - src/agent/rag_context/routing.py
  modified:
    - src/agent/rag_context/__init__.py
    - src/agent/state.py
    - src/agent/nodes/generate_recommendation.py
    - src/agent/routing.py
    - src/agent/graph.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/action_draft.py
    - src/agent/nodes/final_response.py
    - .planning/phases/22-rag-context-builder-hallucination-control/deferred-items.md

key-decisions:
  - "Keep regenerate_route as a deterministic route/action contract only; no automatic retry loop or disabled feature flag was added."
  - "Only explicit backend verifier route allow may advance recommendation output to risk and action assessment."
  - "Block non-allow verifier state in graph routing, risk assessment, and direct action_draft resume calls."
  - "Render final responses from safe route categories and omit raw verifier, provenance, OCR, tool, debug, and private-reasoning payloads."

patterns-established:
  - "Verifier route decisions are total backend functions that fail closed to non-allow routes."
  - "Action boundary nodes defensively re-check verifier route state even when graph routing should have filtered it."
  - "Final responses use bounded verifier status categories instead of internal verifier traces."

requirements-completed: [RTE-01, RTE-02, RTE-03, RTE-04, RTE-05, CLM-04, VER-06, BND-05]

# Metrics
duration: 17min
completed: 2026-06-19
---

# Phase 22 Plan 05: Route, Action Boundary, and Safe Final Response Summary

**Backend-owned verifier routing now gates recommendation, action, and final-response paths without model-selected safety outcomes.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-06-19T09:53:00Z
- **Completed:** 2026-06-19T10:09:34Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added `src/agent/rag_context/routing.py` with deterministic route decisions for allow, regenerate, insufficient/refusal, and manual-review outcomes.
- Integrated `generate_recommendation` with the shared `ContextBuilder` and `MaterialClaimVerifier` without changing retrieval ranking or search behavior.
- Added backend graph routing after recommendation generation so non-allow verifier routes cannot reach risk/action assessment.
- Hardened risk assessment, action draft, and final response handling so non-allow verifier state does not create proposed actions, approval requests, action drafts, or safety snapshot evidence.
- Marked the Plan 22-04 deferred routing gap resolved with Plan 22-05 verification evidence.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement deterministic verifier route map and state fields** - `91ba050` (feat)
2. **Task 2: Integrate shared kernel into recommendation generation and graph routing** - `2025cdf` (feat)
3. **Task 3: Harden action boundary and final-response wording** - `41fd43e` (fix)

**Plan metadata:** committed separately after state updates.

_TDD note: RED checks were run against the existing Phase 22 test files before each implementation task. No test-file changes were required for Plan 22-05._

## Files Created/Modified

- `src/agent/rag_context/routing.py` - Backend verifier route enum, route decision DTO, and total fail-closed route function.
- `src/agent/rag_context/__init__.py` - Exports deterministic routing primitives.
- `src/agent/state.py` - Adds redacted verifier route/status/reason/metrics/safe-reference state fields.
- `src/agent/nodes/generate_recommendation.py` - Builds prompt-safe shared RAG context bundles and verifies recommendation support before routing.
- `src/agent/routing.py` - Adds `route_after_recommendation` and fail-closed verifier route checks.
- `src/agent/graph.py` - Wires recommendation conditional routing before risk/action assessment.
- `src/agent/nodes/assess_risk_and_approval.py` - Blocks direct risk/approval execution when verifier route is non-allow.
- `src/agent/nodes/action_draft.py` - Blocks direct/resumed action draft generation when verifier route is non-allow.
- `src/agent/nodes/final_response.py` - Adds safe verifier stop-state final-response branches.
- `.planning/phases/22-rag-context-builder-hallucination-control/deferred-items.md` - Marks the 22-04 routing deferred item resolved by Plan 22-05.

## Decisions Made

- `regenerate_route` remains a route value only. Plan 22-05 does not start regeneration attempts, maintain retry counters beyond explicit zero metadata, or add a feature flag.
- Backend verifier route state is authoritative for graph/action permission; model output can provide recommendation content but cannot choose safety-critical route outcomes.
- Citation membership remains evidence metadata, but semantic support comes from the shared verifier route decision.
- Final-response copy is derived from bounded safe categories, not raw verifier prompts, traces, provenance, OCR details, hashes, raw tool payloads, private reasoning, or unbounded policy text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Guarded direct action_draft execution against non-allow verifier state**
- **Found during:** Task 3 (Harden action boundary and final-response wording)
- **Issue:** The plan behavior required non-allow outcomes to block action drafts, but Task 3's file list omitted `src/agent/nodes/action_draft.py`.
- **Fix:** Added a non-allow verifier guard that returns `VERIFIER_NOT_ALLOW` without creating a draft or draft outcome.
- **Files modified:** `src/agent/nodes/action_draft.py`
- **Verification:** Task 3 pytest and plan-level pytest passed.
- **Committed in:** `41fd43e` (part of task commit)

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Required for the stated action-boundary correctness requirement; no scope creep.

## Issues Encountered

- Task 2 initially broke existing recommendation node compatibility for missing-session tests and raw policy text persistence. The implementation was adjusted before commit so existing node tests and Phase 22 integration tests passed.
- Task 3 initially allowed direct risk/final/action paths to proceed on non-allow verifier state. Defensive guards were added before commit.

## Verification

- `uv run pytest tests/agent/rag_context/test_routing.py tests/test_graph_routing.py -q` - passed (`66 passed, 1 warning`)
- `uv run pytest tests/agent/test_phase22_recommendation_integration.py tests/test_graph_routing.py tests/agent/test_nodes/test_generate_recommendation.py -q` - passed (`59 passed, 1 warning`)
- `uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_final_response.py -q` - passed (`42 passed, 1 warning`)
- `uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/test_graph_routing.py -q` - passed (`89 passed, 1 warning`)
- `uv run pytest tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_final_response.py tests/test_graph_routing.py -q` - passed (`78 passed, 1 warning`)
- `uv run pytest tests/agent/rag_context tests/knowledge/test_citation_membership.py tests/agent/context/test_budget.py -q` - passed (`72 passed, 1 warning`)
- `uv run ruff check src/agent/rag_context/routing.py src/agent/state.py src/agent/graph.py src/agent/routing.py src/agent/nodes/generate_recommendation.py src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/final_response.py tests/agent/rag_context/test_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py` - passed

## Known Stubs

None - focused scans of touched runtime files found no placeholder/TODO stubs.

## Auth Gates

None.

## Threat Flags

None - the trust boundaries touched by this plan match the Plan 22-05 threat model; no new endpoint, schema, network, or file-access surface was introduced.

## Deferred Issues

None. The Plan 22-04 deferred routing item is resolved by Plan 22-05 and documented in `deferred-items.md`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 22-06 can build on deterministic verifier route state, safe final-response wording, and action-boundary gating for metrics/evaluation/leakage closure.

## Self-Check: PASSED

- Found `.planning/phases/22-rag-context-builder-hallucination-control/22-05-SUMMARY.md`
- Found `src/agent/rag_context/routing.py`
- Found task commits `91ba050`, `2025cdf`, and `41fd43e`
- Found `route_after_recommendation` in `src/agent/routing.py` and `src/agent/graph.py`

---
*Phase: 22-rag-context-builder-hallucination-control*
*Completed: 2026-06-19*
