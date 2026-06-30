---
phase: 25-intent-routing-safety-hardening
reviewed: 2026-06-21T04:15:35Z
depth: deep
files_reviewed: 10
files_reviewed_list:
  - src/agent/intent_policy.py
  - src/agent/schemas.py
  - src/agent/state.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/receive_request.py
  - src/agent/routing.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_required_slots.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: resolved
resolution:
  fixed_commit: aa10082
  resolved_at: 2026-06-21T04:25:00Z
---

# Phase 25: Code Review Report

**Reviewed:** 2026-06-21T04:15:35Z
**Depth:** deep
**Files Reviewed:** 10
**Status:** resolved

## Summary

Reviewed the intent taxonomy, pre-route policy, classifier state projection, receive-request reset, routing helpers, and related tests. The implementation generally fails closed for approval-chat state writes and stale slot reuse, and the scoped test suite passes under the project runner.

Two safety-routing gaps remain: pre-route escalation can keep a low-risk primary intent with no slot requirements, and `secondary_intents` are passed across the classifier boundary but ignored by precedence resolution.

Verification: `uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py` passed: 45 tests.

## Resolution

All review findings were accepted and fixed in commit `aa10082`:

- `WR-01` fixed by forcing safety-sensitive escalation pre-route decisions to effective `complaint_escalation`, preserving the escalation required-slot policy.
- `WR-02` fixed by including `secondary_intents` in precedence candidates and normalizing requested operation from the selected effective intent.
- `IN-01` fixed by deleting the unused legacy `IntentResult` schema that still carried obsolete ordinary-chat taxonomy values.

Post-fix verification:

- `uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py -q` passed: 47 tests.
- `uv run pytest tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools tests/agent/test_session_memory_integration.py -q` passed: 9 tests.
- `uv run ruff check src/agent/intent_policy.py src/agent/schemas.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/routing.py src/agent/nodes/extract_slots.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py` passed.

## Warnings

### WR-01: Escalation Pre-Route Does Not Force Escalation Slot Policy

**File:** `src/agent/nodes/classify_intent.py:157`
**Issue:** `detect_pre_route()` marks escalation phrases such as `主管` as `requested_operation="escalate"`, but `intent_result_to_state()` only forces the primary intent for `execute_action`. If the LLM returns `policy_qa` for `TKT-6001要不要转主管`, the effective state becomes `primary_intent="policy_qa"`, `requested_operation="escalate"`, empty `required_slots`, and `route_after_intent()` routes to `investigate` instead of `session_memory_load` / required-slot clarification. That bypasses the `complaint_escalation` required slot policy for a safety-sensitive route.
**Fix:**
```python
if pre_route and pre_route.disposition == "safety_sensitive":
    if pre_route.requested_operation == "execute_action":
        forced_intent = "action_request"
    elif pre_route.requested_operation == "escalate":
        forced_intent = "complaint_escalation"
    else:
        forced_intent = None

    if forced_intent and primary_intent != forced_intent:
        policy_overrides.append(
            {
                "source": "safety_sensitive_pre_route",
                "from": {"primary_intent": primary_intent},
                "to": {"primary_intent": forced_intent},
                "reason_codes": pre_route.reason_codes,
            }
        )
        primary_intent = forced_intent
        requested_operation = pre_route.requested_operation or requested_operation
```
Add a regression test where the LLM returns `policy_qa` for `TKT-6001要不要转主管`; the effective intent should be `complaint_escalation`, required slots should include one of ticket/order/merchant, and the initial route should not be direct `investigate`.

### WR-02: Secondary Intents Are Ignored During Precedence Resolution

**File:** `src/agent/intent_policy.py:198`
**Issue:** `classify_intent.intent_result_to_state()` passes `result.secondary_intents` into `resolve_intent_precedence()`, and the prompt/schema contract includes `secondary_intents`, but the policy function never reads that argument. Critical secondary intents can therefore be dropped unless the raw query also matches a hard-coded keyword. For example, an LLM result with `primary_intent="policy_qa"` and `secondary_intents=["complaint_escalation"]` remains `policy_qa` with empty required slots.
**Fix:**
```python
candidates = [primary_intent, *(secondary_intents or [])]

# Keep query-derived safety upgrades, then choose by PRECEDENCE_INTENTS.
for intent in PRECEDENCE_INTENTS:
    if intent in valid_candidates:
        operation = _operation_for_selected_intent(intent, requested_operation)
        reason_codes = [] if intent == primary_intent else ["intent_precedence_applied"]
        return intent, operation, reason_codes
```
Normalize `requested_operation` from the selected intent, not only from keyword side effects; e.g. `appeal_or_unban` and `complaint_escalation` should resolve to `escalate`.

## Info

### IN-01: Legacy IntentResult Schema Is Dead Code With Obsolete Taxonomy

**File:** `src/agent/schemas.py:8`
**Issue:** `IntentResult` is not referenced anywhere in `src` or `tests`, and it still permits old values such as `approval_request` and `unknown` that Phase 25 explicitly excludes from the ordinary-chat taxonomy.
**Fix:** Remove the unused model, or rename it as an explicit legacy compatibility type with tests proving it cannot be used by the active classifier path.

---

_Reviewed: 2026-06-21T04:15:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
