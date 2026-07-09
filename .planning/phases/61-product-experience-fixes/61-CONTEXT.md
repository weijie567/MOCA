# Phase 61: Product Experience Fixes - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 61 is one product-experience phase. It fixes concrete Agent Console and agent-response UX problems while preserving v2.1 subsystem boundaries: ToolPlatform remains the graph-facing tool boundary, BusinessFactService owns current business facts and scope checks, RAG/claim verification remains evidence authority, and memory remains contextual only.

This phase adds a generic `business_metric_query` capability for scoped operational metric questions. It does not create a BI dashboard, arbitrary SQL interface, cross-tenant analytics surface, or real external coupon ledger.

</domain>

<decisions>
## Implementation Decisions

### Metric Semantics And Defaults

- **D-01:** `business_metric_query` is a single generic intent, not one intent per metric.
- **D-02:** MVP metrics are locked to five supported metrics: order count, refund case count, pending ticket count, MOCA coupon draft/record count, and merchant refund rate.
- **D-03:** If a metric query lacks an explicit time range or an otherwise unambiguous snapshot meaning, the agent must ask for clarification rather than guessing a hidden statistic.
- **D-04:** Supported natural time expressions include today, this week, this month, this quarter, this year, and explicit start/end ranges.
- **D-05:** Natural time windows use local business/demo timezone semantics: today starts at local 00:00; this week starts Monday 00:00; this month starts on day 1 00:00; this quarter starts on the quarter's first day 00:00; this year starts January 1 00:00.
- **D-06:** `当前` means current status snapshot only for metrics that naturally have a current-state meaning, such as pending tickets. For event-count metrics such as order count, refund count, coupon records, and refund rate, `当前` without a time range should clarify the intended period.
- **D-07:** `本周补偿券发了多少` must use the MOCA demo-system record/draft口径, such as `issue_coupon` action drafts/records. The final answer must disclose that this is not a verified external coupon-delivery success count.
- **D-08:** Merchant refund rate uses a conservative default formula: orders with at least one refund case divided by total orders in the same authorized merchant scope and time range. This avoids overcounting one order that has multiple refund cases.

### Role And Merchant Scope Boundaries

- **D-09:** support users can only receive metric answers inside trusted `merchant_scope`; in the current demo this is normally their bound merchant.
- **D-10:** manager users can only receive metric answers inside trusted `merchant_scope`; Phase 61 does not invent a new organization or merchant-group hierarchy.
- **D-11:** admin users can only receive metric answers inside configured management scope. Admin sees all merchants only when trusted scope explicitly contains `["*"]`; if server context narrows admin scope, metric queries must respect the narrowed scope.
- **D-12:** User text, LLM output, memory, RAG, frontend payload, or tool args must never widen metric scope.
- **D-13:** Unauthorized merchant metric queries fail closed with no existence leak. User-visible wording should say that metrics for that merchant cannot be provided within the current permission scope, without confirming whether the merchant exists.

### Agent Routing And Response Copy

- **D-14:** Metric queries should route through the existing graph shape: `contextual_intent_resolve -> slot_resolution_gate -> investigate/tool -> final_response` when slots are complete. Missing metric/resource/time/scope slots go to clarification.
- **D-15:** Do not create a separate metric graph node in this phase unless planning proves the existing route cannot safely support the metric tool path. The expected default is to extend current intent/slot/tool/final-response surfaces.
- **D-16:** Metric tools must be read-only ToolPlatform declarations backed by BusinessFactService or its owned business metric boundary. The implementation must not let LLMs generate SQL or let final_response query the database directly.
- **D-17:** Clarification copy must explain what is missing and offer accepted options. Example: "要统计订单数，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。"
- **D-18:** Unsupported copy must explain the capability boundary and offer useful supported alternatives, rather than a bare "暂不支持" or speculative advice.
- **D-19:** Metric answers should be number-first. The first sentence gives the count/rate; the following sentence gives scope, time range, filters, and freshness.
- **D-20:** Existing `small_talk` behavior is considered a regression baseline, not a new capability. It must remain direct, deterministic for standalone short greetings, and must not claim policy/RAG evidence.

### Console Timeline Presentation

- **D-21:** Agent Console timeline must distinguish direct response, clarification, unsupported request, metric answer, RAG/evidence-backed answer, and tool-call outcomes with user-readable labels.
- **D-22:** Metric runs should display as business metric queries, for example "正在查询业务指标", with a compact subtitle such as `metric: refund_count · scope: 当前权限范围`.
- **D-23:** clarification and unsupported timeline entries should show safe reasons, such as missing time range or unsupported aggregate capability. Do not expose raw `routing_hints`, debug internals, or sensitive scope details.
- **D-24:** Scope and freshness belong primarily in the final answer. Timeline should carry compact labels only so it remains scannable.

### Regression And Demo Validation

- **D-25:** Regression coverage should include backend node tests, graph/routing tests, final-response tests, frontend timeline rendering checks, and full Playwright E2E demo flows.
- **D-26:** Build a large golden set for UX regression rather than only three minimal prompts. It should include known bad examples and role/scope metric cases.
- **D-27:** Required golden prompts include at least: `你好`, `当前有多少订单`, missing-ID single order/refund/ticket queries, today refund count, weekly coupon records, week/month/quarter/year time expressions, merchant refund rate, and unauthorized merchant metric queries.
- **D-28:** Local UI/API validation must be recorded in Phase 61 validation artifacts and, when a concrete local issue is found, in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **D-29:** Phase 61 remains one roadmap phase, but planning must split implementation into multiple small plans by ownership boundary. Expected split: response UX baseline, metric contract/scope, metric runtime, agent routing/final-response integration, and console/regression validation.

### the agent's Discretion

- Exact schema names for metric slots and metric result payloads may be chosen during planning, as long as the contract captures metric id, resource, time range, status filter, merchant filter, computed value, scope, freshness, and no-leak status.
- Exact current-status enum mappings, such as what counts as pending ticket, should be derived from existing demo data/status values and locked in tests.
- Exact UI styling for result-type labels is implementation discretion, as long as labels are concise and do not overlap or clutter the current console.
- Exact Playwright fixture shape and golden-set file format are planner discretion, but tests must use MOCA-approved commands and include frontend verification.

</decisions>

<canonical_refs>
## Canonical References

Downstream agents must read these before planning or implementing.

### Phase Scope

- `.planning/ROADMAP.md` - Phase 61 goal, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` - v2.2 UX, metric, scope, console, and regression requirements.
- `.planning/PROJECT.md` - current milestone focus and v2.1 guardrails carried forward.

### Architecture Contracts

- `docs/contract-spec.md` - normative ToolPlatform, TrustedContext, BusinessFactService, RAG/claim, and graph-boundary contracts.
- `.planning/phases/42-intent-recognition-three-layer-decoupling/42-CONTEXT.md` - intent candidate, policy arbitration, and LLM authority boundaries.
- `.planning/phases/49-investigate-bounded-react-loop-migration/49-CONTEXT.md` - bounded read-only investigate loop and planner authority.
- `.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md` - contextual intent runtime owner and state-write constraints.
- `.planning/phases/54-slot-resolution-gate-cutover/54-CONTEXT.md` - slot gate ownership, provenance, and fail-closed routing.
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md` - final wording must not imply verified evidence when gates did not run.

### Local Issue Evidence

- `.planning/LOCAL-VALIDATION-ISSUES.md` - Issue 21 documents the `你好` and `当前有多少订单` demo failures and the current direct-response fix.
- `.planning/ARCHITECTURE-DEBT.md` - direct-response intent template fix and subsystem debt ledger.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/agent/intent_policy.py` owns current intent definitions, route policy, direct-response intent flags, required slot policy, and risk decisions. It does not yet define `business_metric_query`.
- `src/agent/nodes/contextual_intent_resolve.py` owns the active contextual intent node and already has deterministic guards for standalone small talk and unsupported aggregate order count.
- `src/agent/nodes/clarification_gate.py` builds ordinary clarification output and can be extended to produce metric-specific missing-slot prompts.
- `src/agent/nodes/investigate.py` is the bounded read-only ReAct loop that discovers visible tools through `ToolPlatform.visible_tools(...)` and invokes tools through `ToolPlatform.invoke(...)`.
- `src/tools/catalog.py` is the single source for graph-facing tool declarations, input schemas, output schemas, caller allowlists, risk level, and executor assignment.
- `src/tools/platform.py` and `src/tools/runtime.py` already enforce descriptor lookup, schema validation, runtime auth, side-effect gates, executor dispatch, output validation, and projection.
- `src/business/service.py` contains `BusinessFactService`, the current business fact and scope-check boundary. Metric reads should be added here or behind an owned metric boundary with equivalent scope/no-leak behavior.
- `src/db/models.py` has `Order`, `RefundCase`, `Ticket`, and `ActionDraft` models with tenant, merchant/status/time fields usable for read-only metric queries.
- `frontend/src/hooks/useAgentRun.ts`, `frontend/src/types/events.ts`, and `frontend/src/components/timeline/TimelineStep.tsx` are the current SSE/timeline integration points.

### Established Patterns

- Graph nodes should not query repositories directly when a platform/domain service boundary exists.
- Tool declarations require strict schemas and output validation; unsupported future payloads should not be invented.
- Business reads must use trusted `ToolCallContext` projected from `TrustedContext`; user text and LLM outputs cannot widen scope.
- Final responses must truthfully reflect executed gates. No RAG/policy evidence wording may appear if RAG/claim verification did not provide that authority.
- Tests and validation commands must use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or `.venv/bin/pytest ...`; bare `pytest` is invalid in MOCA.

### Integration Points

- Add `business_metric_query` to intent/schema/prompt/policy surfaces without creating per-metric intents.
- Add metric slot schema and clarification behavior for metric id, resource, time range, status filter, and merchant filter.
- Add read-only metric tool declaration(s) in `src/tools/catalog.py`, executed by the business executor and backed by BusinessFactService-owned code.
- Extend investigate planning/fallback so metric queries call metric tools only when slots are complete.
- Extend final_response to format metric answers number-first with scope, filters, and freshness.
- Extend SSE/timeline payload projection and frontend rendering with safe result-type labels and safe reasons.

</code_context>

<specifics>
## Specific Ideas

- The user explicitly wants one generic `business_metric_query / operations_query / analytics_query` style intent, not one intent per metric.
- Metric examples to support in the MVP: "今天有多少退款单", "待处理工单有多少", "本周补偿券发了多少", "某商家的退款率是多少".
- Accepted clarification options should visibly include today, this week, this month, this quarter, this year, and explicit start/end dates.
- Timeline should show compact labels such as `metric: refund_count · scope: 当前权限范围`, while final answers carry the full scope/freshness explanation.
- The user chose heavier validation than the recommended minimum: full Playwright E2E and a large golden regression set are in scope for Phase 61 planning.

</specifics>

<deferred>
## Deferred Ideas

- Full BI dashboard, charting, grouping, exports, scheduled reports, and period-over-period analytics remain future analytics expansion.
- Real external coupon delivery success metrics require a real external coupon ledger or integration; Phase 61 may only count MOCA demo records and must say so.
- A new manager organization hierarchy or merchant-group administration model is out of scope. Phase 61 consumes trusted scope only.
- Arbitrary SQL, natural-language database exploration, and cross-tenant analytics are out of scope.

</deferred>

---

*Phase: 61-product-experience-fixes*
*Context gathered: 2026-07-09*
