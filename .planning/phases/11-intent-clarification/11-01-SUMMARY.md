---
phase: 11-intent-clarification
plan: 01
subsystem: agent
tags: [intent, schemas, classifier, state]
requires:
  - phase: 10-state-lifecycle-routing-migration
    provides: AgentState lifecycle and graph routing foundation
provides:
  - Strict IntentResultV3, RequiredSlotExpression, and ClarificationRequest schemas
  - Field-by-field classifier adapter with forbidden-write tests
  - Phase 11 turn-scoped state resets
affects: [phase-12-session-memory, phase-13-approval]
tech-stack:
  added: []
  patterns: [strict-pydantic-schema, field-by-field-adapter]
key-files:
  created:
    - src/agent/intent_policy.py
    - tests/agent/test_intent_adapter.py
  modified:
    - src/agent/schemas.py
    - src/agent/state.py
    - src/agent/prompts.py
    - src/agent/nodes/classify_intent.py
    - src/agent/nodes/receive_request.py
    - tests/agent/conftest.py
    - tests/agent/test_nodes/test_classify_intent.py
    - tests/agent/test_nodes/test_receive_request.py
key-decisions:
  - "Keep compatibility writes to current_intent/last_intent while canonical primary_intent/requested_operation are added."
  - "Runtime required slots come from REQUIRED_SLOT_POLICY, not raw LLM required_slots."
patterns-established:
  - "LLM structured output is stored as raw/eval metadata before deterministic state projection."
requirements-completed: [INTENT-01, INTENT-02, CLARIFY-01]
duration: 0h 0m
completed: 2026-06-14
---

# Phase 11 Plan 01: Intent Schema and Adapter Summary

**Strict ordinary-chat intent schema with deterministic state projection and stale-turn reset coverage**

## Performance

- **Duration:** Inline with Phase 11 execution batch
- **Started:** 2026-06-14
- **Completed:** 2026-06-14
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added `IntentResultV3`, `RequiredSlotExpression`, `ClarificationRequest`, and canonical Phase 11 state fields.
- Replaced the classifier mapping with `intent_result_to_state`, preserving raw LLM required-slot output only under eval metadata.
- Added reset coverage for `intent_confidence`, `secondary_intents`, `required_slots`, `candidate_slots`, `routing_hints`, and `clarification_request`.

## Task Commits

Inline execution was used in this runtime, so task-level changes are included in the final Phase 11 scoped commit rather than separate per-task commits.

## Deviations from Plan

Executor subagents and per-task commits were not used because this runtime executed the phase inline. Scope was preserved and the combined Phase 11 validation passed.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Plan 11-02 can consume `REQUIRED_SLOT_POLICY` and the classifier adapter without trusting raw LLM slot expressions.

---
*Phase: 11-intent-clarification*
*Completed: 2026-06-14*
