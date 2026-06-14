---
phase: 11-intent-clarification
reviewed: 2026-06-14T03:36:36Z
depth: deep
files_reviewed: 34
files_reviewed_list:
  - src/agent/schemas.py
  - src/agent/intent_policy.py
  - src/agent/intent_manifest.py
  - src/agent/state.py
  - src/agent/prompts.py
  - src/agent/routing.py
  - src/agent/graph.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/clarification_gate.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/long_term_memory_retrieve.py
  - src/agent/nodes/session_memory_load.py
  - src/agent/nodes/investigate.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/execute_action.py
  - tests/agent/conftest.py
  - tests/conftest.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_intent_adapter.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_clarification_gate.py
  - tests/agent/test_intent_manifest.py
  - tests/agent/test_intent_golden_contract.py
  - eval/intent/intent-golden.v1.json
  - eval/intent/coverage-manifest.v1.json
  - eval/intent/m6-statistical-gate.v1.json
  - eval/intent/intent-consistency.v1.json
findings:
  critical: 0
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-06-14T03:36:36Z
**Depth:** deep
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Reviewed the Phase 11 intent schema, deterministic policy helpers, graph routing, clarification path, tests, and eval manifests, with cross-file tracing into the existing investigate/action path because Phase 11 changed how those nodes are reached. The focused Phase 11 test gate passes (`131 passed, 3 skipped`), and `uv run ruff check src/agent tests/agent` passes.

The remaining issues are cross-file contract gaps: two runtime routing/safety cases can bypass the intended current-turn slot/action boundary, and two eval/manifest checks can claim coverage while missing or contradicting the actual runtime contract.

## Warnings

### WR-01: Policy QA Can Reuse Stale Active Slots After Direct Routing To Investigate

**File:** `src/agent/routing.py:99`

**Issue:** `route_after_intent` sends zero-slot intents such as `policy_qa` directly to `investigate` (`src/agent/routing.py:99-102`, wired by `src/agent/graph.py:77-86`). That bypasses `session_memory_load` and `extract_slots`, but `investigate.plan_next_step` still falls back to top-level persistent `active_slots` when `extracted_slots` is absent (`src/agent/nodes/investigate.py:44-49`). A same-thread policy question after a previous order/refund turn can therefore call `get_order`/`get_refund_case` using stale identifiers before policy search, leaking unrelated business facts into an ordinary policy answer.

**Fix:** Keep required-slot completeness and investigation planning on the same current-turn/trusted-slot source. For Phase 11, the lowest-risk fix is to stop `investigate` from reading top-level `active_slots` and only use `extracted_slots` or a resolver output populated through trusted session metadata.

```python
# src/agent/nodes/investigate.py
def _case_slots(state: AgentState) -> dict[str, Any]:
    extracted = state.get("extracted_slots") if isinstance(state.get("extracted_slots"), dict) else {}
    return {slot_name: extracted.get(slot_name) for slot_name in _CASE_SLOT_RESOURCES}
```

Add a graph test: first turn sets `active_slots` with `ORD-001`, second turn asks `退款超时规则是什么？`, and the tool calls must be only `search_policy`.

### WR-02: Safety-Sensitive Pre-Route Does Not Enforce The Action-Request Slot Policy

**File:** `src/agent/nodes/classify_intent.py:91`

**Issue:** `detect_pre_route` correctly marks write/action text as `safety_sensitive` with `requested_operation="execute_action"` (`src/agent/intent_policy.py:116-123`), but the classifier adapter only overwrites `requested_operation` (`src/agent/nodes/classify_intent.py:91-96`). It leaves `primary_intent` and runtime `required_slots` derived from the LLM-selected domain intent (`src/agent/nodes/classify_intent.py:97`, `src/agent/routing.py:105-117`). If the LLM returns a high-confidence `policy_qa` or `refund_troubleshooting` for text like "请对ORD-7001直接退款", Phase 11 can bypass the `action_request` policy that requires `action_type` plus a target identifier (`src/agent/intent_policy.py:43`). Downstream, `assess_risk_and_approval` can synthesize `proposed_action` from the recommendation text (`src/agent/nodes/assess_risk_and_approval.py:249-261`), so the missing current-turn `action_type` check is not purely cosmetic.

**Fix:** Treat `pre_route.disposition == "safety_sensitive"` as an action policy boundary. Either force `primary_intent="action_request"` before computing `policy_required_slots`, or route to clarification until current-turn extraction supplies both `action_type` and the required target slot.

```python
# src/agent/nodes/classify_intent.py
if pre_route and pre_route.disposition == "safety_sensitive":
    primary_intent = "action_request"
    requested_operation = pre_route.requested_operation or "execute_action"
```

Add tests where the fake LLM returns `policy_qa` and `refund_troubleshooting` for safety-sensitive user text; both should require `action_type` and route to `clarification_gate` when it is missing.

### WR-03: Golden Dataset Contains Contradictory Hard Negatives And The Contract Test Does Not Exercise Runtime Classification Semantics

**File:** `eval/intent/intent-golden.v1.json:136`

**Issue:** Some hard-negative labels contradict the implemented contract. For example, `"通过订单号 ORD-1 查询退款状态"` is labeled as a hard negative for `order_status_inquiry` (`eval/intent/intent-golden.v1.json:136-143`), even though it is semantically an order/refund status query and the pre-router test explicitly expects that phrase to remain a normal domain/read-only candidate (`tests/agent/test_intent_routing.py:31`). Another example: `approve APR-1` is labeled as `not_primary_intent: unsupported` for the `unsupported` hard-negative bucket (`eval/intent/intent-golden.v1.json:703-709`), while runtime intentionally forces approval-looking ordinary chat to `primary_intent="unsupported"` plus clarification metadata (`src/agent/nodes/classify_intent.py:93-95`). The executable golden test does not catch this because it seeds every hard negative through `resolve_intent_precedence("policy_qa", "advise", ...)` instead of exercising the classifier adapter or the expected primary intent (`tests/agent/test_intent_golden_contract.py:59-64`).

**Fix:** Replace contradictory hard negatives with semantically close but truly negative examples for each intent, and strengthen the golden contract test to validate expected runtime fields for cases that declare `primary_intent`, `not_primary_intent`, `pre_route_disposition`, or `route`. Approval-boundary cases should assert the combined runtime contract: `primary_intent="unsupported"`, `routing_hints.pre_route_disposition="approval_chat_not_trusted"`, and no trusted approval fields.

### WR-04: M6 `coverage_manifest_hash` Is Not Validated For Staleness

**File:** `src/agent/intent_manifest.py:204`

**Issue:** `m6-statistical-gate.v1.json` stores `coverage_manifest_hash` (`eval/intent/m6-statistical-gate.v1.json:9`), and the current value matches the coverage manifest today. However, `validate_intent_manifest` only checks the golden dataset hash on the coverage and consistency manifests (`src/agent/intent_manifest.py:146-150`) and never verifies `m6.coverage_manifest_hash` against the canonical hash of `coverage-manifest.v1.json` (`src/agent/intent_manifest.py:204-211`). A future edit to coverage semantics could leave the M6 gate pointing at stale contract coverage while `test_intent_manifest_files_are_hash_owned_and_complete` still passes.

**Fix:** Compute and compare the coverage manifest hash when `m6_gate_path` is provided, and add a stale-hash test analogous to `test_stale_dataset_hash_fails`.

```python
if m6_gate_path is not None:
    m6 = load_json_model(m6_gate_path, M6StatisticalGate)
    expected_coverage_hash = compute_dataset_hash(coverage_path)
    if m6.coverage_manifest_hash != expected_coverage_hash:
        errors.append("stale coverage_manifest_hash in M6 gate")
```

---

_Reviewed: 2026-06-14T03:36:36Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
