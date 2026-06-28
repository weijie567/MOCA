---
phase: 32
reviewed: 2026-06-28T14:54:03Z
depth: deep
files_reviewed: 25
files_reviewed_list:
  - src/agent/graph_vocabulary.py
  - src/agent/intent_policy.py
  - src/agent/merchant_context.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/receive_request.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/api/routers/agent_runs.py
  - src/api/routers/traces.py
  - src/repositories/trace_repo.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_policy_registry.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_trace.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/replay/test_replay_api.py
  - tests/test_agent_runs_api.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 32: Code Review Report

**Reviewed:** 2026-06-28T14:54:03Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Deep review covered the listed Phase 32 source and test files, using `f347f38..HEAD` as diff context and current files on disk as the review target. I found two warning-level correctness issues in the target contract projection layer. No critical security issues were found.

Review included cross-file tracing from trace/API projection code into graph vocabulary and merchant-context projection, plus direct projection checks using the project entrypoint style (`UV_CACHE_DIR=/tmp/uv-cache uv run ...`). I did not run the full pytest suite as part of this review.

## Warnings

### WR-01: Target Merchant Context Rejects Real Adapter Business Fact Refs

**File:** `src/agent/merchant_context.py:101`

**Issue:** `project_target_merchant_context()` only accepts `source_system` values from `_TRUSTED_REF_SOURCES`. The current allowlist contains service-style names, but the actual business adapters emit `BusinessFactRefV1` refs with concrete source systems such as `demo_orders_db`, `demo_refund_cases_db`, and `demo_tickets_db`. Those refs are stored unchanged by `investigate`, so a completed business-scoped run with valid same-tenant adapter refs is projected as `target_merchant_context.status = "unavailable"` instead of `resolved`. Existing tests miss this because they use synthetic `source_system: "business_fact_service"` refs or do not assert the projected merchant-context status on a realistic graph path.

**Fix:** Align the trusted-source check with the actual tool/business adapter registry, or centralize approval through the service that constructs `BusinessFactRefV1`. At minimum, include the currently approved adapter source systems and add a regression test with an adapter-shaped ref:

```python
_TRUSTED_REF_SOURCES = {
    "business_fact_service",
    "business_tool_service",
    "tool_platform",
    "tool_result_v2",
    "demo_orders_db",
    "demo_refund_cases_db",
    "demo_tickets_db",
}
```

### WR-02: Canonical Runtime Nodes Are Projected As Unknown Passthrough

**File:** `src/agent/graph_vocabulary.py:123`

**Issue:** `project_trace_step_for_contract()` returns `target_graph_status = "unknown_passthrough"` whenever a runtime node is absent from `_ENTRIES`. The vocabulary only lists Phase 32 aliases/deferred nodes, so common canonical runtime nodes such as `receive_request`, `investigate`, `clarification_gate`, `approval_gate`, `action_draft`, `final_response`, and `memory_write` are indistinguishable from unrecognized/debug nodes in trace/API contract output. Phase 32's target projection is supposed to make contract/eval/API surfaces speak the target graph vocabulary; treating ordinary runnable nodes as unknown weakens replay/eval consumers that need to separate valid runtime steps from unmapped implementation names.

**Fix:** Add explicit runtime identity entries for canonical runnable nodes that are already valid target vocabulary, and add tests that assert their `target_graph_status` is `runtime` rather than `unknown_passthrough`. Legacy names that intentionally project to a renamed target should be mapped explicitly instead of falling through.

```python
_entry("receive_request", "receive_request", "node", "runtime", True),
_entry("investigate", "investigate", "node", "runtime", True),
_entry("clarification_gate", "clarification_gate", "node", "runtime", True),
_entry("approval_gate", "approval_gate", "node", "runtime", True),
_entry("action_draft", "action_draft", "node", "runtime", True),
_entry("final_response", "final_response", "node", "runtime", True),
_entry("memory_write", "memory_write", "node", "runtime", True),
```

---

_Reviewed: 2026-06-28T14:54:03Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
