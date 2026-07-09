---
phase: 61
slug: product-experience-fixes
status: complete
created: 2026-07-09
research_mode: local_codebase_review
---

# Phase 61 Research — Product Experience Fixes

## Research Complete

Phase 61 can be implemented as one roadmap phase with five execution plans. The existing graph already has the required route shape:

`contextual_intent_resolve -> slot_resolution_gate -> investigate -> final_response`

No new graph phase or dedicated metric node is required for MVP metric questions. The implementation should extend existing intent policy, slot resolution, ToolPlatform, BusinessFactService, final response, SSE, and frontend timeline surfaces.

## Current Implementation Findings

### Intent And Routing

- `src/agent/schemas.py` currently defines `IntentLiteral` without `business_metric_query`.
- `src/agent/intent_policy.py` owns `INTENT_DEFINITIONS`, `REQUIRED_SLOT_POLICY`, route policy, precedence, direct-response flags, and slot inheritance compatibility.
- `src/agent/nodes/contextual_intent_resolve.py` already has deterministic guards for standalone small talk and aggregate order queries:
  - `_is_standalone_small_talk(...)`
  - `_is_unsupported_aggregate_order_request(...)`
- The current aggregate-order guard returns `unsupported`, which was correct as a temporary fix but conflicts with the Phase 61 metric target. After the metric contract lands, prompts like `当前有多少订单` should become `business_metric_query` and clarify missing time range rather than asking for an order id or saying the whole category is unsupported.
- `src/agent/routing.py` already allows `slot_resolution_gate`, `investigate`, `clarification_gate`, and `final_response` after contextual intent. `_slot_resolution_route_decision(...)` sends complete slot sets to `investigate`.

### Slot Resolution And Clarification

- `SlotExtractionResult` only supports:
  - `order_id`, `refund_case_id`, `ticket_id`, `merchant_id`, `customer_id`, `issue_type`, `action_type`
- Metric support needs slots for at least:
  - `metric_id`, `metric_time_preset`, `time_range_start`, `time_range_end`, `status_filter`, `merchant_id`
- `slot_resolution_gate` is the correct owner for resolved `active_slots`; `contextual_intent_resolve` must not write `active_slots`.
- `clarification_gate` currently labels only ordinary business identifiers and action fields. It needs metric-specific safe questions:
  - missing time range: "今天、本周、本月、本季度、今年，或指定起止时间"
  - missing merchant filter when user asks for a merchant-specific rate without identifying a merchant
  - unsupported metric: describe supported metric options without exposing internals.

### ToolPlatform And BusinessFactService

- `src/tools/catalog.py` defines all graph-facing tool declarations and `investigate_tool_names(...)`.
- `src/agent/nodes/investigate_planner.py` has a separate static `INVESTIGATE_ALLOWED_TOOL_NAMES` set. Adding a metric tool requires updating this allowlist and tests that currently assert the historical eight-tool list.
- `src/business/service.py` owns current business fact and no-leak semantics. It already fails closed through `NO_LEAK_BUSINESS_RESOURCE_MESSAGE` and strips identifiers on permission denial.
- `src/tools/contracts.py` currently restricts `BusinessFactRefV1.resource_type` to `order`, `refund_case`, `ticket`, `logistics`, and `merchant_risk`. Metric facts need an accepted `business_metric` resource type or explicit metric resource types.
- `TrustedContextFactory` maps token scopes to tool permissions through `SCOPE_TO_TOOL_PERMISSION`. A new `tool:query_business_metric` permission must be derived from a trusted scope such as `metrics:read`; user text, LLM output, or frontend payload must not grant it.

### Data Available For Metrics

The existing demo database supports the locked MVP metrics:

- `Order`: `tenant_id`, `merchant_id`, `status`, `created_at`, `paid_at`.
- `RefundCase`: `tenant_id`, `order_id`, `status`, `created_at`; merchant scope requires joining to `Order`.
- `Ticket`: `tenant_id`, `order_id`, `status`, `created_at`; merchant scope requires joining to `Order`.
- `ActionDraft`: `tenant_id`, `run_id`, `target_merchant_id`, `action_type`, `status`, `created_at`; coupon count must be described as MOCA demo `issue_coupon` draft/record count, not external coupon delivery success.

Recommended metric semantics:

- `order_count`: count orders by `Order.created_at` in the requested time range.
- `refund_case_count`: count refund cases by `RefundCase.created_at` in the requested time range.
- `pending_ticket_count`: snapshot count where ticket status is `open` or `in_progress`; accepts `当前` without a time range.
- `coupon_record_count`: count `ActionDraft.action_type == "issue_coupon"` by `ActionDraft.created_at`; response must disclose demo-system record scope.
- `merchant_refund_rate`: distinct orders with at least one refund case divided by total orders in the same authorized merchant scope and time range.

### Scope Boundaries

- `TrustedContextFactory` already produces:
  - support/manager/merchant: merchant-bound `merchant_scope`
  - admin: wildcard `["*"]` unless narrowed by server-supplied scope
- Managers are not tenant-wide supervisors in the current implementation. Phase 61 should consume trusted merchant scope only and not invent merchant groups.
- Unauthorized merchant metric queries should use a no-existence-leak response such as "当前权限范围内无法提供该商户指标" and must not reveal whether the merchant exists.

### Final Response

- `src/agent/nodes/final_response.py` currently has deterministic branches for:
  - direct small talk and unsupported
  - clarification
  - business fact responses for `order_status_inquiry`
  - RAG/manual review/insufficient evidence branches
- It needs a metric branch before the generic completed-response branch. Metric final responses should be number-first:
  - first sentence: value/rate
  - second sentence: scope, time range, filters, freshness, and caveat if coupon metric.
- `llm_outputs["final_response"]` should include a stable response kind/result type so SSE/frontend can label metric answers without parsing Chinese text.

### SSE And Frontend Console

- Backend node messages are in `src/api/routers/agent_runs.py::NODE_MESSAGES`.
- `_extract_step_payload(...)` currently emits evidence count, risk level, recommendation summary, tool name, and RAG claim summary. It does not emit `response_kind`, `safe_reason`, or metric summary.
- Frontend timeline label logic is in:
  - `frontend/src/types/events.ts`
  - `frontend/src/hooks/useAgentRun.ts`
  - `frontend/src/components/timeline/TimelineStep.tsx`
  - `frontend/src/components/timeline/AgentTimeline.tsx`
- `TimelineStep` currently displays a fixed node message and raw `node · status`. It should display safe business labels for:
  - direct response
  - clarification
  - unsupported
  - business metric query
  - RAG/evidence answer
  - tool call

### Existing Tests And Risky Test Locks

- `tests/agent/test_nodes/test_contextual_intent_resolve.py` covers deterministic small talk and current aggregate-order unsupported behavior.
- `tests/agent/test_nodes/test_final_response.py` covers small talk and unsupported aggregate order direct response.
- `tests/tools/test_tool_platform.py` has `test_investigate_visible_tools_exactly_match_phase49_eight_tool_allowlist`; this must be intentionally updated when adding the metric read tool.
- `tests/business/test_service.py` already has strong BusinessFactService no-leak tests and seeded support/admin scope cases.
- Frontend has Vitest/jsdom but no Playwright config or dependency in `frontend/package.json`.
- Intent golden files under `eval/intent/` are Phase 11 admission/coverage manifests. Phase 61 should add a separate UX/metric golden set instead of overloading that dataset.

## Implementation Boundaries

Must do:

- Add one generic `business_metric_query` intent.
- Add metric slot/result schemas and metric-specific clarification.
- Add one read-only ToolPlatform metric tool backed by BusinessFactService.
- Enforce tenant and merchant scope through trusted context only.
- Add metric final response formatting.
- Add backend SSE safe payload fields and frontend timeline labels.
- Add Phase 61 UX/metric golden regression plus role/scope cases.
- Add Playwright E2E infrastructure because the user explicitly selected it.

Must not do:

- Do not add one intent per metric.
- Do not add free-form SQL or LLM-generated SQL.
- Do not query the database from `final_response`.
- Do not use RAG or memory as metric authority.
- Do not invent manager merchant groups or organization hierarchy.
- Do not confirm whether an unauthorized merchant exists.
- Do not claim external coupon delivery success.
- Do not create a separate metric graph node unless implementation proves the existing route cannot safely support the contract.

## Validation Architecture

Phase 61 needs validation at five layers:

1. **Response UX baseline:** node-level tests for small talk, unsupported, clarification, and no false evidence wording.
2. **Metric contract and intent:** schema/registry/golden tests for one generic metric intent, conditional time-range clarification, and no per-metric intent additions.
3. **Metric runtime and scope:** BusinessFactService/ToolPlatform tests for support, manager, admin, wildcard/narrowed scope, unauthorized merchant no-leak, and read-only tool behavior.
4. **Agent graph integration:** focused graph tests proving metric prompts route through slot resolution, call the metric tool, and produce number-first final responses.
5. **Console and E2E:** frontend Vitest for timeline rendering and Playwright E2E for live demo prompts, including role switching and stale-state regression.

Primary validation commands should use project-approved entrypoints:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`
- `cd frontend && npm run test -- --run`
- `cd frontend && npm run build`
- `cd frontend && npm run e2e`

Manual/local validation results must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` when execution performs live UI/API checks.

## Research Complete Marker

## RESEARCH COMPLETE
