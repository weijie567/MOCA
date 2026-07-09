---
phase: 62-business-query-and-drilldown-foundation
reviewed: 2026-07-09T23:23:35Z
depth: standard
files_reviewed: 54
files_reviewed_list:
  - docs/contract-spec.md
  - evaluation/golden/phase62_business_query_cases.jsonl
  - frontend/e2e/agent-console.spec.ts
  - frontend/package.json
  - frontend/src/components/details/BusinessQueryResultTab.tsx
  - frontend/src/components/details/DetailsPanel.tsx
  - frontend/src/components/timeline/TimelineStep.tsx
  - frontend/src/hooks/useAgentRun.test.ts
  - frontend/src/types/events.ts
  - scripts/eval_phase62_business_query.py
  - src/agent/nodes/contextual_intent_resolve.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/investigate.py
  - src/agent/nodes/investigate_planner.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/slot_resolution_gate.py
  - src/agent/prompts.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/api/routers/agent_runs.py
  - src/api/schemas/agent_runs.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/business/query/__init__.py
  - src/business/query/compiler.py
  - src/business/query/projection.py
  - src/business/query/registry.py
  - src/business/query/schemas.py
  - src/business/schemas.py
  - src/business/service.py
  - src/platform/trusted_context.py
  - src/tools/catalog.py
  - src/tools/contracts.py
  - src/tools/executors/business.py
  - src/tools/projection.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_contextual_intent_resolve.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_nodes/test_slot_resolution_gate.py
  - tests/agent/test_required_slots.py
  - tests/architecture/test_business_query_boundaries.py
  - tests/business/test_business_query_registry.py
  - tests/business/test_business_query_schemas.py
  - tests/business/test_business_query_service.py
  - tests/business/test_schemas.py
  - tests/business/test_service.py
  - tests/eval/test_phase62_business_query_golden.py
  - tests/platform/test_trusted_context_factory.py
  - tests/test_agent_runs_api.py
  - tests/tools/test_catalog.py
  - tests/tools/test_projection.py
  - tests/tools/test_tool_platform.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 62: Code Review Report

**Reviewed:** 2026-07-09T23:23:35Z
**Depth:** standard
**Files Reviewed:** 54
**Status:** issues_found

## Summary

Reviewed the Phase 62 business-query foundation source, tests, frontend event/rendering changes, contract/eval artifacts, and phase summaries at standard depth. The registry/schema/compiler/service/tool/frontend paths are generally aligned with the safe business-query contract: query specs are strict, backend execution remains scoped through trusted tool context, permission-denied payloads avoid fact refs, and public projections use safe allowlists.

One warning remains in the cross-turn drilldown foundation. The code stores and later trusts a drilldown context binding that is intended to include session and merchant scope, but the agent-runs graph path does not put those trusted values into the AgentState used by the binding helper. Tool execution still uses trusted config scope, so this is not a direct authorization bypass, but stale safe drilldown context can survive a scope/session change and influence the next business-query follow-up.

Tests were not rerun for this review artifact.

## Warnings

### WR-01: Drilldown context binding does not include trusted scope/session on the agent-runs state path

**File:** `src/api/routers/agent_runs.py:129`

**Issue:** `business_query_context_binding()` hashes `session_id` and `merchant_scope` from AgentState (`src/agent/state.py:197-205`), and both `receive_request` and `contextual_intent_resolve` accept a saved drilldown context when that hash matches (`src/agent/nodes/receive_request.py:68-76`, `src/agent/nodes/contextual_intent_resolve.py:883-894`). However, the agent-runs SSE path filters initial state to only `tenant_id`, `user_id`, `role`, `thread_id`, and `current_run_id` (`src/api/routers/agent_runs.py:129-132`, `src/api/routers/agent_runs.py:252-264`), while `merchant_scope` and `session_id` live only in config. The same state-derived helper is used when storing the expected context after a business-query result (`src/agent/nodes/investigate.py:1044-1048`, `src/agent/nodes/investigate.py:1077-1081`), so two turns with the same tenant/user/role/thread but different trusted merchant scope or session can still hash the absent state values as matching. The current tests cover user mismatch clearing but not scope/session mismatch (`tests/agent/test_nodes/test_receive_request.py:294-323`), and graph tests keep scope in config only (`tests/agent/test_graph.py:82-89`, `tests/agent/test_graph.py:116-128`).

**Fix:** Derive a non-raw business-query context binding from canonical `TrustedContext` for each run, including tenant/user/role/thread/session and merchant scope, and pass only that hash into AgentState. Store that trusted hash in `expected_slot_context` after business-query execution, and compare against the incoming trusted hash in `receive_request` and `contextual_intent_resolve` instead of recomputing from state fields that omit scope. Add regression tests that reuse the same checkpoint thread with a different `merchant_scope` and with a different non-null `session_id`, asserting `last_query_spec`, `last_answer_context`, `result_cursor`, and `expected_slot_context` are cleared.

---

_Reviewed: 2026-07-09T23:23:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
