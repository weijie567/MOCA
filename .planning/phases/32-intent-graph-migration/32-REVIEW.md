---
phase: 32-intent-graph-migration
reviewed: 2026-06-28T15:09:18Z
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
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 32: Code Review Report

**Reviewed:** 2026-06-28T15:09:18Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** clean

## Summary

Deep re-review covered the listed Phase 32 source and test files after fixes `76dfe83` and `895ea4d`. All reviewed files meet quality standards. No issues found.

WR-01 is fixed: `target_merchant_context.status = "resolved"` now accepts the real adapter `BusinessFactRefV1` source systems (`demo_orders_db`, `demo_refund_cases_db`, `demo_tickets_db`) while still requiring structured refs with tenant, resource type, resource id, and trusted source. Spoofed raw merchant/order/refund/ticket ids in state, slots, prompt/LLM text, or explicit `target_merchant_context` do not become authority, and trace/replay/run authorization remains owner/admin scoped without consulting target merchant context.

WR-02 is fixed: canonical runtime graph nodes now project as `runtime`, while `rag_context_build` and `claim_verify` remain `deferred_non_runnable`, `runnable=False`, and are not registered as runnable graph nodes.

Verification run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/agent/graph_vocabulary.py src/agent/intent_policy.py src/agent/merchant_context.py src/agent/nodes/classify_intent.py src/agent/nodes/extract_slots.py src/agent/nodes/receive_request.py src/agent/routing.py src/agent/state.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/repositories/trace_repo.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_trace.py tests/architecture/test_phase32_static_contract.py tests/replay/test_replay_api.py tests/test_agent_runs_api.py tests/test_trace_api.py
```

Result: `219 passed, 28 warnings in 172.30s`. Warnings were from LangGraph dependency deprecation/typing notices, not Phase 32 regressions.

Residual risk/test gaps: this review did not run the entire repository suite. The merchant-context projection still relies on internal `BusinessFactRefV1` producers and the trusted source-system allowlist rather than cryptographic provenance, so future business adapters should add source-system regression coverage before being treated as resolved merchant context.

---

_Reviewed: 2026-06-28T15:09:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
