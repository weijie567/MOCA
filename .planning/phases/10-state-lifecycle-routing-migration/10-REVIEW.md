---
phase: 10-state-lifecycle-routing-migration
reviewed: 2026-06-14T02:40:03Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - src/agent/events.py
  - src/agent/graph.py
  - src/agent/nodes/clarification_gate.py
  - src/agent/nodes/investigate.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/session_memory_load.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/agent/tools/unified.py
  - src/agent/trace.py
  - src/api/routers/agent.py
  - src/db/migrations/versions/006_agent_trace_events.py
  - src/db/models.py
  - tests/agent/test_empty_session_adapter.py
  - tests/agent/test_events.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/conftest.py
  - tests/test_embedder.py
  - tests/test_graph_routing.py
  - tests/test_state_lifecycle.py
findings:
  critical: 0
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-14T02:40:03Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Reviewed the Phase 10 state lifecycle, routing, unified investigation tool, trace event, API persistence, migration/model, and related tests. The main risks are in the new investigate-to-routing behavior: missing business facts are not surfaced, insufficient evidence can still produce a completed-looking final response, and the clarification fallback ignores the missing facts shape that the router expects. The event redaction guard also only checks top-level keys.

## Warnings

### WR-01: Action-Oriented Requests Can Advance Without Required Business Facts

**File:** `src/agent/nodes/investigate.py:134`
**Issue:** `business_context["missing_required_facts"]` is always returned as an empty list, even when no business facts were loaded. For a non-fact-only intent such as `refund_troubleshooting` with no `order_id`, `plan_next_step` can still retrieve policy evidence, and `route_after_investigate` will route to recommendation generation when `retrieval_status` is strong enough (`src/agent/routing.py:51-62`). That allows recommendations to be generated with policy evidence but no order/refund/ticket facts.
**Fix:**
```python
missing_required_facts = _missing_required_facts(state, context["facts"])
business_context = {
    "facts": context["facts"],
    "business_fact_refs": context["business_fact_refs"],
    "tool_results": context["tool_results"],
    "missing_required_facts": missing_required_facts,
    "errors": context["errors"],
    "status": _business_status(context),
}
```
Add `_missing_required_facts` rules for action-oriented intents/operations and cover the no-slot refund path in `tests/test_graph_routing.py` or `tests/agent/test_graph.py`.

### WR-02: Insufficient Evidence Falls Through To A Completed-Style Response

**File:** `src/agent/routing.py:57`
**Issue:** When investigation ends with `retrieval_status in {"error", "no_evidence", None}`, the router sends execution directly to `final_response`. The Phase 10 `investigate` return does not include a `recommendation_draft` for these terminal cases (`src/agent/nodes/investigate.py:154-171`). Existing `final_response` behavior treats an empty draft as a completed recommendation, so no-evidence or no-tool paths can return a misleading "completed" answer instead of the deterministic insufficient-evidence response.
**Fix:** Have `investigate` populate an insufficient/retrieval-error draft before routing to `final_response`, or route to a dedicated insufficient-evidence node.
```python
recommendation_draft = None
if context["retrieval_status"] in {"no_evidence", None}:
    recommendation_draft = {
        "recommended_action": "insufficient_evidence",
        "missing_info": ["No sufficient policy or business evidence found"],
        "evidence_refs": [],
    }
elif context["retrieval_status"] == "error":
    recommendation_draft = {
        "recommended_action": "retrieval_error",
        "missing_info": ["Policy retrieval failed"],
        "evidence_refs": [],
    }
```
Return that draft from `investigate` and add a graph-level test for `search_policy` returning `not_found`.

### WR-03: Clarification Gate Ignores Router Missing-Fact Shape

**File:** `src/agent/nodes/clarification_gate.py:18`
**Issue:** The router sends requests to `clarification_gate` when `business_context["missing_required_facts"]` is non-empty, but the gate only reads top-level `missing_info` or `required_slots`. Once `investigate` starts setting `missing_required_facts`, the user-facing clarification payload will still contain an empty `missing` list.
**Fix:**
```python
business_context = state.get("business_context") if isinstance(state.get("business_context"), dict) else {}
missing = (
    state.get("missing_info")
    or state.get("required_slots")
    or business_context.get("missing_required_facts")
    or []
)
```
Add a test that routes a state with `business_context.missing_required_facts` through `clarification_gate`.

### WR-04: Redaction Guard Only Blocks Forbidden Keys At The Top Level

**File:** `src/agent/events.py:117`
**Issue:** `_guard_redacted_payload` rejects top-level `data`, `raw`, `arguments`, and `prompt`, but nested forbidden keys are accepted and persisted. Any future caller that wraps tool or LLM payload details under a "safe" parent could store raw arguments or prompts in `agent_trace_events.redacted_payload`.
**Fix:**
```python
def _guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    def walk(value: Any, path: str = "redacted_payload") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_REDACTED_PAYLOAD_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(redacted_payload)
```
Add a nested-payload test such as `{"summary": {"prompt": "..."}}`.

---

_Reviewed: 2026-06-14T02:40:03Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
