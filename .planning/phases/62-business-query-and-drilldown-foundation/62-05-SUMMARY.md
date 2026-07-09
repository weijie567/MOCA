---
phase: 62-business-query-and-drilldown-foundation
plan: 05
subsystem: agent-business-query-drilldown
tags: [agent-state, business-query, tool-platform, slot-resolution, langgraph, tdd]

requires:
  - phase: 62-04
    provides: BusinessFactService and ToolPlatform runtime support for business_query
provides:
  - Safe same-thread business query answer context in AgentState
  - Expected-slot drilldown flow deriving validated BusinessQuerySpec payloads
  - ToolPlatform business_query re-execution for aggregate-to-list follow-ups
  - Graph coverage for 本周多少订单？ followed by 订单号是多少？
affects: [62-06, 62-07, final-response-projection, api-projection, frontend-drilldown]

tech-stack:
  added: []
  patterns:
    - context-bound safe answer state using business_query_context_binding
    - expected-slot-type routing for field_request and cursor_request drilldowns
    - metric-compatible aggregate answers seeding business_query drilldown context

key-files:
  created:
    - .planning/phases/62-business-query-and-drilldown-foundation/62-05-SUMMARY.md
  modified:
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - src/agent/nodes/contextual_intent_resolve.py
    - src/agent/nodes/slot_resolution_gate.py
    - src/agent/routing.py
    - src/agent/nodes/investigate.py
    - tests/agent/test_nodes/test_receive_request.py
    - tests/agent/test_nodes/test_contextual_intent_resolve.py
    - tests/agent/test_nodes/test_slot_resolution_gate.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/agent/test_graph.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Drilldown context stores only replayable BusinessQuerySpec, safe answer_context, cursor metadata, and binding fingerprints; raw rows and authority fields stay out of AgentState."
  - "Drilldown follow-ups reuse the existing business_metric_query path but carry a validated business_query_spec active slot instead of adding a new intent."
  - "Metric-compatible aggregate answers seed business_query drilldown context by normalizing preset-based metric args into a BusinessQuerySpec."

patterns-established:
  - "Safe follow-up context must pass business_query_context_binding before it can influence a new turn."
  - "Expected slot type strings live in routing and are consumed by contextual intent and slot resolution."
  - "Investigate deterministic fallbacks prefer validated business_query_spec before legacy metric fallback."

requirements-completed: [BQ-62-05, BQ-62-04]

duration: 21min
completed: 2026-07-09
---

# Phase 62 Plan 05: Business Query Drilldown Context Summary

**Same-thread business-query drilldowns with safe answer context, expected-slot routing, and ToolPlatform re-execution**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-09T14:23:21Z
- **Completed:** 2026-07-09T14:44:10Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments

- Added AgentState fields for `last_query_spec`, `last_answer_context`, `result_cursor`, `expected_slot_type`, and `expected_slot_context`.
- Persisted safe `business_query` answer context from stable `BusinessQueryResultV1` payloads and cleared stale context on denial or binding mismatch.
- Derived same-thread field/cursor drilldown specs from safe context only after authority binding validation.
- Routed validated `business_query_spec` through slot resolution and investigate, then invoked ToolPlatform `business_query` on the second turn.
- Preserved Phase 61 metric pending-time behavior while allowing metric-compatible aggregate answers to seed drilldown context.

## Task Commits

1. **Task 1 RED: Persist safe query and answer context tests** - `9255b49` (test)
2. **Task 1 GREEN: Safe business query context state** - `f6efab2` (feat)
3. **Task 2 RED: Drilldown query flow tests** - `f7093e4` (test)
4. **Task 2 GREEN: Drilldown business query flow** - `a71167d` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agent/state.py` - Adds durable drilldown context fields and `business_query_spec` active slot typing.
- `src/agent/nodes/receive_request.py` - Preserves or clears drilldown context based on tenant/user/role/thread/session/scope binding.
- `src/agent/nodes/investigate.py` - Records safe answer context, derives metric-compatible context, and dispatches validated `business_query_spec`.
- `src/agent/nodes/contextual_intent_resolve.py` - Classifies same-thread drilldown phrases against safe context without LLM.
- `src/agent/nodes/slot_resolution_gate.py` - Merges deterministic `business_query_spec` slots.
- `src/agent/routing.py` - Owns expected-slot type constants and routes validated business-query specs to investigate.
- `tests/agent/test_nodes/test_receive_request.py` - Covers context preservation and binding invalidation.
- `tests/agent/test_nodes/test_contextual_intent_resolve.py` - Covers field request derivation and no-context fail-closed behavior.
- `tests/agent/test_nodes/test_slot_resolution_gate.py` - Covers `business_query_spec` readiness without metric slots.
- `tests/agent/test_nodes/test_investigate.py` - Covers safe context persistence and ToolPlatform business_query fallback.
- `tests/agent/test_graph.py` - Covers `本周多少订单？` then `订单号是多少？` graph flow.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records the metric preset/window compatibility validation issue.
- `.planning/ARCHITECTURE-DEBT.md` - Records the verified drilldown expected-slot pipeline fix.
- `.planning/STATE.md` - Advances Phase 62 to plan 6/7 with 5/7 plans complete.
- `.planning/ROADMAP.md` - Marks 62-05 complete.

## Decisions Made

- Use a hashed context binding across tenant/user/role/thread/session/scope instead of storing raw authority values in drilldown state.
- Treat `business_query_spec` as the payload-bearing active slot on the existing `business_metric_query` path, keeping graph topology stable for this phase.
- Normalize metric-compatible aggregate context to keep `time_preset` and drop expanded `start_at/end_at`, because `BusinessQuerySpec` forbids combining preset and explicit ranges.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added metric-compatible drilldown context**
- **Found during:** Task 2
- **Issue:** The plan allowed the first turn to produce an aggregate business_query or metric-compatible answer, but Task 1 only persisted context for native `business_query` results.
- **Fix:** `investigate` now creates safe `last_query_spec` and `last_answer_context` from successful `query_business_metric` results when the metric can support a drilldown.
- **Files modified:** `src/agent/nodes/investigate.py`, `tests/agent/test_graph.py`
- **Verification:** `test_business_query_drilldown_followup_reuses_same_thread_answer_context` passes.
- **Committed in:** `a71167d`

**2. [Rule 1 - Bug] Normalized preset-based metric args before BusinessQuerySpec conversion**
- **Found during:** Task 2 focused GREEN verification
- **Issue:** Metric tool args contained both `time_preset` and expanded `start_at/end_at`; `BusinessQuerySpec` correctly rejects that combination, so compatibility context was discarded.
- **Fix:** Drop derived `start_at/end_at` when `time_preset` is present before converting metric args into a replayable BusinessQuerySpec.
- **Files modified:** `src/agent/nodes/investigate.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Focused suite passed: `5 passed, 2 warnings`; broader suite passed: `147 passed, 36 warnings`.
- **Committed in:** `a71167d`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)  
**Impact on plan:** Both fixes were necessary to satisfy the plan's required metric-compatible aggregate-to-list flow. No architectural scope change.

## Issues Encountered

- RED tests failed as expected before implementation.
- The first Task 2 GREEN graph run showed missing `last_query_spec` after a metric-compatible aggregate answer; fixed and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- The first SUMMARY self-check shell snippet used zsh's special `path` variable as a loop name, causing a false `git`/`grep` command-not-found failure; fixed by rerunning with `file_path` and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- GSD state/roadmap handlers again miscomputed MOCA compact metadata; corrected `.planning/STATE.md` and `.planning/ROADMAP.md` manually and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py::test_agent_state_declares_business_query_drilldown_fields tests/agent/test_nodes/test_receive_request.py::test_receive_request_preserves_safe_business_query_drilldown_context tests/agent/test_nodes/test_receive_request.py::test_receive_request_clears_business_query_drilldown_context_on_binding_mismatch tests/agent/test_nodes/test_investigate.py::test_successful_business_query_stores_safe_answer_context_for_drilldown tests/agent/test_nodes/test_investigate.py::test_denied_business_query_clears_stale_drilldown_context -q --tb=short` -> RED failed before Task 1 implementation, then `5 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` -> `106 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py::test_contextual_intent_resolve_business_query_drilldown_field_request_uses_last_answer_context tests/agent/test_nodes/test_contextual_intent_resolve.py::test_contextual_intent_resolve_business_query_field_request_without_context_fails_closed tests/agent/test_nodes/test_slot_resolution_gate.py::test_slot_resolution_gate_routes_business_query_drilldown_spec_without_metric_slots tests/agent/test_nodes/test_investigate.py::test_deterministic_fallback_calls_business_query_from_resolved_drilldown_spec tests/agent/test_graph.py::test_business_query_drilldown_followup_reuses_same_thread_answer_context -q --tb=short` -> RED failed before Task 2 implementation, then `5 passed, 2 warnings`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py -q --tb=short` -> `147 passed, 36 warnings`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/state.py src/agent/routing.py src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/agent/nodes/investigate.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py` -> passed.
- `rg -n "last_query_spec|last_answer_context|result_cursor|expected_slot_type" src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/investigate.py` -> required links found.
- `rg -n "answered_business_query_drilldown|field_request|cursor_request|business_query_spec" src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/agent/routing.py src/agent/nodes/investigate.py` -> required links found.

## TDD Gate Compliance

- RED gate commits exist for both TDD tasks: `9255b49`, `f7093e4`.
- GREEN gate commits exist after their matching RED commits: `f6efab2`, `a71167d`.
- No refactor-only commits were needed.

## Known Stubs

None. Stub scan found only intentional empty defaults/test fixtures and no placeholders that block the plan goal.

## Threat Flags

None. New state, intent, routing, and ToolPlatform surfaces are covered by T-62-16 through T-62-19 in the plan threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 62-06 can project `business_context.facts["business_query"]` knowing drilldown specs are re-executed through ToolPlatform and not parsed from final response text.
- Phase 62-07 can build UI drilldown affordances from `answer_context`, `fields_shown`, and cursor capability.
- Remaining deferred work stays as planned: final/API/frontend projection, broader field-language coverage, Phase 63 risk/action taxonomy, Phase 64 RAG label unification, Phase 65 global label registry, Phase 66 config hygiene, and suggested Phase 67 state-machine registry.

---
*Phase: 62-business-query-and-drilldown-foundation*
*Completed: 2026-07-09*

## Self-Check: PASSED

- Verified summary and all key source/test files exist.
- Verified task commits exist: `9255b49`, `f6efab2`, `f7093e4`, `a71167d`.
