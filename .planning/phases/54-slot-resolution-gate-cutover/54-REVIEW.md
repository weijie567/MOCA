---
phase: 54-slot-resolution-gate-cutover
reviewed: 2026-07-07T03:20:52Z
depth: deep
files_reviewed: 23
files_reviewed_list:
  - docs/current-langgraph-architecture.md
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/intent_policy.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/slot_resolution_gate.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/api/routers/agent_runs.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_nodes/test_contextual_intent_resolve.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_nodes/test_slot_resolution_gate.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_trace.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/test_agent_runs_api.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 54: Code Review Report

**Reviewed:** 2026-07-07T03:20:52Z
**Depth:** deep
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Reviewed the Phase 54 slot-resolution-gate cutover across active graph registration, routing/policy values, slot provenance, API/SSE trace projection, architecture baseline, and focused tests. The active graph cutover itself is consistent with Phase 54 boundaries: `slot_resolution_gate` is registered, `extract_slots` / `route_after_slots` are retained as compatibility-only surfaces, and `slot_extraction`, `memory_context_load`, `recommendation_generation`, and `risk_gate` are not activated as graph nodes.

One critical fail-open remains in the post-node router path: an LLM validation/error result from `slot_resolution_gate` can be overwritten by `route_after_slot_resolution` recomputing slot resolution from still-present session context. I also found one provenance gap for cross-intent current-turn slot replacement.

## Critical Issues

### CR-01: Slot Gate LLM Error Can Route To Investigation Through Recomputed Session Slots

**File:** `src/agent/routing.py:462`
**Issue:** `slot_resolution_gate` deliberately builds a fail-closed result on LLM validation/error by clearing resolved slots and adding `llm_slot_extraction_error` to `slot_resolution_trace` (`src/agent/nodes/slot_resolution_gate.py:172`). However, the active graph then calls `route_after_slot_resolution`, whose implementation ignores that prior node result and recomputes `resolve_slots_with_provenance(state)`. Because the merged LangGraph state still contains the original trusted `session_context` / `session_memory`, the router can accept inherited slots and return `investigate` after the node reported `route_decision="clarification_gate"`.

Verified reproduction:

```text
UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY'
from datetime import UTC, datetime, timedelta
from src.agent.routing import route_after_slot_resolution

state = {
    "tenant_id": "tenant-1",
    "user_id": "user-1",
    "thread_id": "thread-1",
    "primary_intent": "refund_troubleshooting",
    "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
    "run_started_at": datetime.now(UTC).isoformat(),
    "extracted_slots": {},
    "active_slots": {},
    "active_slot_metadata": {},
    "slot_resolution_trace": {
        "route_decision": "clarification_gate",
        "reason_codes": ["llm_slot_extraction_error", "missing_required_slots"],
        "resolved_slots": {},
    },
    "session_memory": {
        "continuity_claimed": True,
        "active_slots": {"order_id": "ORD-SESSION"},
        "slot_metadata": {"order_id": {
            "source": "trusted_session_memory",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "fresh": True,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "compatible_intents": ["refund_troubleshooting"],
        }},
    },
}
print(route_after_slot_resolution(state))
PY
```

This prints `investigate`, which violates the Phase 54 fail-closed requirement for LLM extraction errors.

**Fix:**
Honor the slot gate error decision before recomputing, and add a graph/router regression test that merges the node error update with the original state before routing.

```python
def _route_after_slot_resolution(state: AgentState) -> str:
    trace = state.get("slot_resolution_trace")
    if isinstance(trace, Mapping):
        reason_codes = trace.get("reason_codes")
        if isinstance(reason_codes, list) and "llm_slot_extraction_error" in reason_codes:
            return "clarification_gate"

    result = resolve_slots_with_provenance(state)
    route = result.get("route_decision")
    return route if isinstance(route, str) else "clarification_gate"
```

Suggested verification:

```text
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_required_slots.py tests/agent/test_graph.py -q --tb=short
```

## Warnings

### WR-01: Cross-Intent Current-Turn Replacement Drops Conflict Provenance

**File:** `src/agent/routing.py:165`
**Issue:** The conflict detection path calls `_trusted_session_slot(prior_metadata, state)` without passing the slot name, and the helper then calls `SLOT_POLICY_REGISTRY.accepts_inherited_slot("", ...)` (`src/agent/routing.py:756`). That drops the business-ID cross-intent compatibility rules for `order_id`, `refund_case_id`, and `ticket_id`. The route still succeeds because the current-turn slot is authoritative, but the trace omits `conflicting_slots` and `previous_trusted_session_value` when a compatible inherited business ID is replaced under a different intent. That weakens Phase 54 provenance and replay/audit visibility.

**Fix:** Pass the slot name through both call sites and helper signature.

```python
if (
    prior_value not in (None, "")
    and str(prior_value) != str(value)
    and _trusted_session_slot(slot, prior_metadata, state)
):
    ...

def _trusted_session_slot(slot: str, metadata: Any, state: AgentState) -> bool:
    decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(
        slot,
        metadata if isinstance(metadata, dict) else None,
        _slot_inheritance_context(state),
    )
    return decision.accepted
```

Add a regression test where `primary_intent="compensation_suggestion"`, current-turn `order_id` replaces an inherited `order_id` whose `compatible_intents` include `refund_troubleshooting`, and assert `slot_resolution_trace["conflicting_slots"]["order_id"]` is populated.

Suggested verification:

```text
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_slot_resolution_gate.py -q --tb=short
```

---

_Reviewed: 2026-07-07T03:20:52Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
