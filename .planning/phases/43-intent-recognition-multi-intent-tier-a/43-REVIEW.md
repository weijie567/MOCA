---
phase: 43-intent-recognition-multi-intent-tier-a
reviewed: 2026-07-02T14:57:14Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - src/agent/intent_policy.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/receive_request.py
  - src/agent/state.py
  - tests/agent/test_intent_task_plan.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_nodes/test_receive_request.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 43: Code Review Report

**Reviewed:** 2026-07-02T14:57:14Z
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the scoped Phase 43 Tier A multi-intent implementation across policy, classify, receive-request, final-response, state, and focused tests. The primary `s1` routing boundary is mostly preserved: `intent_result_to_state` derives effective route fields from the root task step, `select_executable_prefix` keeps `s2+` out of the executable prefix, and final responses render deferred work as labels only.

One warning remains: the `multi_target_request` clarification guard can be cleared by a single-step plan whose only normalization is a lossy same-intent merge. That lets a detected multi-target request continue with only `s1` represented.

## Warnings

### WR-01: Lossy same-intent merge clears multi-target clarification

**File:** `/Users/ming/projects/MOCA/src/agent/nodes/classify_intent.py:327`

**Issue:** `_pre_route_for_task_plan` treats any non-empty `plan_normalization` as evidence that a `multi_target_request` was handled. However `build_task_plan` can return a single-step plan with `same_intent_entity_merge_limited` when a same-intent secondary is collapsed without a multi-entity slot payload (`src/agent/intent_policy.py:867`). In that case, the second target is not represented in `task_plan` or `deferred_steps`, but `requires_clarification` is cleared and routing proceeds to `session_memory_load`.

Reproduced with `IntentResultV3(primary_intent="order_status_inquiry", secondary_intents=["order_status_inquiry"], candidate_slots={"order_id": "ORD-1"})` plus `PreRouteDecision(disposition="multi_target_request", requires_clarification=True)`: the trace records `plan_normalization=["same_intent_entity_merge_limited"]`, `clarification_decision.requires_clarification=False`, `route_decision="session_memory_load"`, and only `s1` in the task plan.

**Fix:** Only neutralize `multi_target_request` when the plan actually represents multiple work items or the normalization is known non-lossy. Keep clarification required for `same_intent_entity_merge_limited` and fallback records.

```python
def _pre_route_for_task_plan(
    pre_route: PreRouteDecision | None,
    *,
    step_count: int,
    normalization: tuple[str, ...],
) -> PreRouteDecision | None:
    if pre_route is None or pre_route.disposition != "multi_target_request":
        return pre_route
    if "plan_invalid_fallback_single" in normalization:
        return pre_route
    lossless_single_step_normalizations = {
        "same_intent_entities_merged",
        "modifier_dropped:small_talk",
        "modifier_folded:complaint_as_severity",
    }
    plan_handled_multiple_requests = step_count > 1 or all(
        item in lossless_single_step_normalizations for item in normalization
    )
    if not plan_handled_multiple_requests:
        return pre_route
    return PreRouteDecision(
        disposition=pre_route.disposition,
        requested_operation=pre_route.requested_operation,
        reason_codes=list(pre_route.reason_codes),
        requires_clarification=False,
    )
```

Add a regression test beside `test_multi_target_request_is_neutralized_only_after_valid_task_plan` that asserts `same_intent_entity_merge_limited` keeps `requires_clarification` in `routing_hints` and routes to `clarification_gate`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py` -> 66 passed, 1 LangGraph deprecation warning.
- Deep cross-file check traced `build_task_plan` -> `intent_result_to_state` -> `route_after_intent` -> graph conditional routing, plus `deferred_steps` rendering in `final_response`.
- Scoped grep found no hardcoded secrets, dangerous shell/eval calls, debug artifacts, or empty catch blocks in the reviewed files.

---

_Reviewed: 2026-07-02T14:57:14Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
