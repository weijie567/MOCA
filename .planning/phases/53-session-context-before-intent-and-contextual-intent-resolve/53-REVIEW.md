---
phase: 53-session-context-before-intent-and-contextual-intent-resolve
reviewed: 2026-07-06T22:56:35Z
depth: deep
files_reviewed: 21
files_reviewed_list:
  - docs/current-langgraph-architecture.md
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/intent_policy.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/contextual_intent_resolve.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - src/memory/service.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_contextual_intent_resolve.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_session_memory_load.py
  - tests/agent/test_trace.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/memory/test_session_memory_service.py
  - tests/test_graph_routing.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 53: Code Review Report

**Reviewed:** 2026-07-06T22:56:35Z
**Depth:** deep
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Deep review covered the Phase 53 active graph cutover, fail-closed router allowlists, canonical `contextual_intent_resolve` output ownership, candidate-only LLM authority, same-thread session context before intent, retained compatibility aliases, architecture baselines, and the listed tests.

The active graph cutover itself is coherent: `classify_intent` and `session_memory_load` are no longer active graph nodes or active route destinations, `route_after_contextual_intent` is the active intent router, and the focused suites pass. One behavioral regression remains in the new pre-intent session context path: session slots loaded before intent can be marked as intent-compatible before the actual intent is known, allowing later slot resolution to accept incompatible inherited slots instead of clarifying.

## Warnings

### WR-01: Pre-intent session slots can bypass later intent compatibility filtering

**File:** `/Users/ming/projects/MOCA/src/memory/service.py:89`, `/Users/ming/projects/MOCA/src/memory/service.py:101`, and `/Users/ming/projects/MOCA/src/agent/intent_policy.py:471`

**Issue:** Phase 53 changed `MemoryService.load_session_memory(..., current_intent=None)` to keep slots before intent is known, but each kept slot is still emitted with `slot_metadata["intent_compatible"] = True`. Later, after `contextual_intent_resolve` sets the actual intent, `SlotPolicyRegistry.accepts_inherited_slot()` trusts that boolean before checking the slot's `compatible_intents` (`src/agent/intent_policy.py:471`). That makes the new `session_context_load -> contextual_intent_resolve -> extract_slots` path fail open: a slot loaded only because the intent was unknown can satisfy required slots for an incompatible actual intent.

I reproduced the failure with an `action_request` state whose current turn provided `order_id`, while pre-intent session context contributed `action_type=issue_coupon` with `compatible_intents=["compensation_suggestion"]`. `resolve_slots_with_metadata()` accepted the inherited `action_type`, and `route_after_slots()` returned `investigate`; with `intent_compatible=False`, the same state correctly returned `clarification_gate`.

**Fix:**
Do not mark unknown-intent loads as already intent-compatible. Preserve the slot and its `compatible_intents`, but make final acceptance re-evaluate against the actual post-intent context.

```python
# src/memory/service.py
intent_filter_applied = current_intent is not None
intent_compatible = (
    _slot_intent_compatible(slot_name, slot.compatible_intents, current_intent)
    if intent_filter_applied
    else False
)
slot_metadata[slot_name] = {
    ...
    "compatible_intents": list(slot.compatible_intents),
    "intent_compatible": intent_compatible,
    "intent_filter_applied": intent_filter_applied,
}
```

Then update the inherited-slot policy so a non-null actual intent recomputes compatibility from `compatible_intents` rather than blindly accepting a pre-intent boolean. If cross-intent business ID compatibility is intentional here, move the shared compatibility helper into policy code and use it from both services.

Add a regression test that builds a `session_context.slot_continuity` loaded with `current_intent=None`, includes an incompatible non-business slot such as `action_type`, then asserts `resolve_slots_with_metadata()` excludes it and `route_after_slots()` returns `clarification_gate`.

## Verification

Commands run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py -q --tb=short
```

Result: `1231 passed, 8 warnings`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/graph_vocabulary.py src/agent/intent_policy.py src/agent/nodes/classify_intent.py src/agent/nodes/contextual_intent_resolve.py src/agent/routing.py src/api/routers/agent_runs.py src/memory/service.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_session_memory_integration.py tests/agent/test_session_memory_load.py tests/agent/test_trace.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/memory/test_session_memory_service.py tests/test_graph_routing.py
```

Result: `All checks passed!`

---

_Reviewed: 2026-07-06T22:56:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
