---
phase: 43-intent-recognition-multi-intent-tier-a
plan: 01
subsystem: agent-intent
tags: [intent-policy, task-plan, multi-intent, risk-gate]
requires:
  - phase: 42-intent-recognition-three-layer-decoupling
    provides: semantic/risk/clarification policy layers
provides:
  - Frozen TaskStep and TaskPlan policy contracts
  - Deterministic Tier A task-plan builder with conservative normalization
  - s1-only executable-prefix helper and state-safe payload serializers
affects: [intent-recognition, classify-intent, final-response]
tech-stack:
  added: []
  patterns: [frozen-dataclass-policy-contract, state-safe-payload-helper]
key-files:
  created:
    - tests/agent/test_intent_task_plan.py
  modified:
    - src/agent/intent_policy.py
key-decisions:
  - "Tier A executable_prefix is observational and capped at s1; every s2+ step is deferred."
  - "Same-intent merge support is a controlled expansion of the brief: only already non-lossy list-valued identifier slots count as merged."
patterns-established:
  - "TaskPlan construction returns a single-intent fallback plus plan_invalid_fallback_single instead of throwing."
  - "TaskPlan/TaskStep payloads convert mappings and tuples to plain dict/list values before state writes."
requirements-completed: [IDR-02]
duration: 45min
completed: 2026-07-02
---

# Phase 43-01: Intent Policy Task Plan Contracts Summary

**Bounded TaskPlan contracts with conservative normalization and s1-only Tier A deferral semantics**

## Performance

- **Duration:** 45 min
- **Started:** 2026-07-02T13:35:00Z
- **Completed:** 2026-07-02T14:20:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added frozen `TaskStep` and `TaskPlan` contracts with final-plan validation for max step count, terminal step references, dependencies, and modifier rejection.
- Added deterministic `build_task_plan(...)` normalization for small-talk drops, complaint folding, independent secondary steps, same-intent merge records, and fail-closed fallback.
- Added `select_executable_prefix(...)` with Plan A semantics: only s1 can appear in the prefix; all `plan.steps[1:]` are deferred.
- Added policy-level tests for N=1 equivalence, read→draft deferral, two-read B1 regression, high-risk deferral, modifier handling, same-intent merge traces, and invalid-plan fallback.

## Task Commits

1. **Task 1-2: TaskPlan contracts, normalization, and prefix policy** - included in current 43-01 implementation commit.

## Files Created/Modified

- `src/agent/intent_policy.py` - Adds TaskPlan contracts, payload helpers, deterministic builder, and s1-only prefix selection.
- `tests/agent/test_intent_task_plan.py` - Adds focused IDR-02 policy tests.
- `.planning/phases/43-intent-recognition-multi-intent-tier-a/43-01-SUMMARY.md` - Records 43-01 completion.

## Decisions Made

Same-intent merge support was implemented as the controlled expansion called out by review: duplicate intents are not duplicated, and a merge is only recorded when existing candidate slots already contain non-lossy list-valued identifier fields. Scalar-only shapes record `same_intent_entity_merge_limited` and keep the single available step.

## Deviations from Plan

None - plan executed as written, with the reviewed same-intent merge expansion documented above.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/agent/test_intent_task_plan.py::test_task_plan_contract_serializes_to_plain_payload -q`
- `uv run pytest tests/agent/test_intent_task_plan.py -q`
- `uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py -q`
- `uv run ruff check src/agent/intent_policy.py tests/agent/test_intent_task_plan.py`
- `git diff --exit-code -- src/agent/schemas.py src/agent/prompts.py docs/contract-spec.md`

## Next Phase Readiness

43-02 can wire the policy contracts into `AgentState`, `receive_request`, and `classify_intent` without changing `IntentResultV3`, prompts, spec, or routing semantics.

---
*Phase: 43-intent-recognition-multi-intent-tier-a*
*Completed: 2026-07-02*
