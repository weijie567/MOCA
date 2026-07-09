---
phase: 61
slug: product-experience-fixes
status: complete
created: 2026-07-09
---

# Phase 61 Patterns — Closest Existing Analogs

## Pattern Summary

Phase 61 should extend existing runtime boundaries rather than create parallel systems.

| New Work | Closest Existing Pattern | Notes |
|----------|--------------------------|-------|
| `business_metric_query` intent | `src/agent/intent_policy.py`, `src/agent/schemas.py` | Add to central registry, route policy, evidence/direct flags, and consistency tests. |
| Metric slot extraction | `src/agent/nodes/slot_resolution_gate.py`, `src/agent/routing.py` | Slot owner remains slot resolution; candidate slots from contextual intent are hints only unless explicitly validated by metric slot policy. |
| Metric clarification | `src/agent/nodes/clarification_gate.py` | Extend safe slot labels/questions instead of formatting metric prompts in final response. |
| Read-only metric tool | `src/tools/catalog.py`, `src/tools/executors/business.py`, `src/business/service.py` | ToolPlatform declaration plus BusinessToolExecutor backed by BusinessFactService. |
| Metric no-leak scope | `BusinessFactService._permission_denied_result`, `tests/business/test_service.py` | Reuse fail-closed result and generic safe message style. |
| Tool visibility/auth | `src/platform/trusted_context.py`, `src/auth/jwt.py`, `src/auth/permissions.py` | New `metrics:read` trusted token scope maps to `tool:query_business_metric`. |
| Planner tool allowlist | `src/agent/nodes/investigate_planner.py`, `tests/tools/test_tool_platform.py` | Update static allowlist and exact-count tests intentionally. |
| Metric final answer | `_business_fact_response(...)` in `src/agent/nodes/final_response.py` | Add a sibling deterministic metric branch before generic completed response. |
| SSE result typing | `_extract_step_payload(...)` in `src/api/routers/agent_runs.py` | Project safe response kind, reason, metric id, and scope summary for frontend. |
| Timeline rendering | `frontend/src/components/timeline/TimelineStep.tsx` | Add payload-aware labels/subtitles with existing layout density. |
| UX regression set | `evaluation/golden/agent_cases.jsonl`, `scripts/eval_agent.py` | Use separate Phase 61 UX set rather than Phase 11 intent admission files. |
| Frontend tests | `frontend/src/hooks/useAgentRun.test.ts` | Add jsdom tests for timeline labels and stale-state reset. |

## Existing Contracts To Preserve

- `contextual_intent_resolve` cannot write downstream authority fields such as `active_slots`, `tool_results`, `business_context`, or `final_response`.
- `slot_resolution_gate` owns `extracted_slots`, `active_slots`, missing slot trace, and route-to-clarification decisions.
- `investigate` calls tools only through `ToolPlatform.visible_tools(...)` and `ToolPlatform.invoke(...)`.
- Business data authority remains `BusinessFactService`; final response must not query DB.
- `ToolResultV2` and `BusinessFactRefV1` must remain strict pydantic contracts.
- Memory remains contextual only and cannot supply metric authority.
- RAG/claim verification remains policy/evidence authority and should not be invoked for pure metrics unless a future phase defines mixed metric+policy workflows.

## Tests To Reuse Or Extend

| Area | Existing Tests |
|------|----------------|
| Intent policy/registry | `tests/agent/test_intent_policy_registry.py`, `tests/agent/test_intent_manifest.py`, `tests/agent/test_intent_golden_contract.py` |
| Contextual intent node | `tests/agent/test_nodes/test_contextual_intent_resolve.py` |
| Slot resolution | `tests/agent/test_nodes/test_slot_resolution_gate.py`, `tests/agent/test_required_slots.py` |
| Clarification | `tests/agent/test_clarification_gate.py`, `tests/agent/test_nodes/test_final_response.py` |
| Business service scope | `tests/business/test_service.py`, `tests/platform/test_trusted_context_factory.py`, `tests/platform/test_merchant_scope.py` |
| Tool contracts | `tests/tools/test_catalog.py`, `tests/tools/test_tool_platform.py`, `tests/tools/test_tool_result_storage.py` |
| Graph routing | `tests/agent/test_graph.py`, `tests/agent/test_intent_routing.py` |
| API/SSE | `tests/test_agent_runs_api.py` |
| Frontend hook | `frontend/src/hooks/useAgentRun.test.ts` |

## Design Notes

- Prefer one tool, `query_business_metric`, with a strict enum `metric_id`; this avoids one tool per metric while keeping runtime validation explicit.
- Metric calculations should use SQLAlchemy expression APIs, not dynamic SQL strings.
- Metric output should be a business fact result with stable fields:
  - `metric_id`
  - `value`
  - `unit`
  - `time_range`
  - `filters`
  - `scope`
  - `freshness`
  - `formula`
  - `caveats`
  - `no_leak_status`
- For `merchant_refund_rate`, use numerator/denominator fields and display a percentage.
- For `coupon_record_count`, include caveat text that these are MOCA demo action drafts/records, not verified external issuance success.

## Pattern Risks

- If `BusinessFactRefV1.resource_type` is not extended, metric tool success will fail strict validation.
- If `INVESTIGATE_ALLOWED_TOOL_NAMES` is not updated, the LLM planner can see a catalog tool but runtime validation can reject it.
- If token scopes do not map to `tool:query_business_metric`, the tool will be hidden in normal agent-runs execution.
- If metric slots are only candidate slots, existing route code will not treat them as resolved; slot-resolution tests must prove active slots are owned by `slot_resolution_gate`.
- If final response lacks a stable response kind, frontend timeline will be forced to infer result type from localized text.

## PATTERNS COMPLETE
