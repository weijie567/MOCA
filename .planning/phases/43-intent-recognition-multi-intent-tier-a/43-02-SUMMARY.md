---
phase: 43-intent-recognition-multi-intent-tier-a
plan: 02
subsystem: agent-intent
tags: [classify-intent, agent-state, task-plan, deferred-steps]
requires:
  - phase: 43-intent-recognition-multi-intent-tier-a
    provides: TaskPlan contracts and s1-only prefix helper
provides:
  - AgentState task_plan and deferred_steps fields
  - Per-turn receive_request reset for TaskPlan/deferred state
  - classify_intent TaskPlan trace/state wiring with s1-only effective fields
affects: [intent-recognition, routing, final-response]
tech-stack:
  added: []
  patterns: [state-safe-task-plan-trace, pre-route-guard-neutralization]
key-files:
  created:
    - .planning/phases/43-intent-recognition-multi-intent-tier-a/43-02-SUMMARY.md
  modified:
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - src/agent/nodes/classify_intent.py
    - src/agent/intent_policy.py
    - tests/agent/test_nodes/test_receive_request.py
    - tests/agent/test_nodes/test_classify_intent.py
key-decisions:
  - "classification_trace records original pre_route_decision, while only multi_target_request clarification effects can be neutralized after a valid handled plan."
  - "Effective route fields, required slots, risk tier, and route_decision are derived from s1 only."
patterns-established:
  - "TaskPlan state writes use serialized dict/list payloads in both state and llm_outputs classification_trace."
  - "receive_request resets task_plan to None and deferred_steps to [] every turn."
requirements-completed: [IDR-02]
duration: 35min
completed: 2026-07-02
---

# Phase 43-02: Classify-State Task Plan Wiring Summary

**TaskPlan state/trace wiring that preserves existing s1 route semantics and defers all s2+ work**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-02T13:51:00Z
- **Completed:** 2026-07-02T14:26:26Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added additive `AgentState` fields for serialized `task_plan` and `deferred_steps`.
- Reset `task_plan` and `deferred_steps` in `receive_request` to prevent stale checkpointed plans from leaking across turns.
- Wired `classify_intent` to build a TaskPlan, write state-safe plan/deferred payloads, and keep `llm_outputs["intent_classification"]["classification_trace"]` synchronized.
- Preserved current-turn compatibility: `primary_intent`, `requested_operation`, `risk_tier`, required slots, and route decision come from s1 only.
- Added tests for valid multi-target neutralization, approval/safety guard preservation, high-risk secondary deferral, non-read s1 empty prefix, and two-read B1 deferral.

## Task Commits

1. **Task 1-2: State reset and classify TaskPlan wiring** - included in current 43-02 implementation commit.

## Files Created/Modified

- `src/agent/state.py` - Adds `task_plan` and `deferred_steps` annotations.
- `src/agent/nodes/receive_request.py` - Resets the new ephemeral fields each turn.
- `src/agent/nodes/classify_intent.py` - Builds and serializes TaskPlan state/trace while routing only s1.
- `src/agent/intent_policy.py` - Tightens secondary `action_request` TaskPlan operation handling.
- `tests/agent/test_nodes/test_receive_request.py` - Covers reset and annotations.
- `tests/agent/test_nodes/test_classify_intent.py` - Covers TaskPlan wiring and guard behavior.

## Decisions Made

The original `pre_route_decision` remains visible in trace. For `multi_target_request`, classify neutralizes only the clarification effect after a valid handled TaskPlan exists; approval-chat and safety-sensitive guards are left intact.

## Deviations from Plan

### Auto-fixed Issues

**1. Secondary action_request operation needed to stay high-risk**
- **Found during:** Task 2 (classify TaskPlan wiring)
- **Issue:** The 43-01 builder would inherit `read_status`/`advise` for secondary `action_request`, making an action step look read-only in deferred metadata.
- **Fix:** Added a TaskPlan-only operation helper so secondary `action_request` becomes `execute_action` when the raw operation is read/advise. This does not change existing single-intent operation selection.
- **Files modified:** `src/agent/intent_policy.py`
- **Verification:** `test_high_risk_secondary_step_is_deferred_not_executed` and `tests/agent/test_intent_task_plan.py` pass.

## Issues Encountered

None beyond the auto-fixed issue above.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/agent/test_nodes/test_receive_request.py -q`
- `uv run pytest tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py -q`
- `uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py -q`
- `uv run ruff check src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py`
- `git diff --exit-code -- src/agent/schemas.py src/agent/prompts.py docs/contract-spec.md`

## Next Phase Readiness

43-03 can consume `deferred_steps` and `classification_trace.plan_normalization` from state to add visible final-response decorations without touching routing or execution.

---
*Phase: 43-intent-recognition-multi-intent-tier-a*
*Completed: 2026-07-02*
