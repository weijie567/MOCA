# Phase 62: Business Query And Drilldown Foundation - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 62 delivers the safe business-query foundation that upgrades the Phase 61 `business_metric_query` MVP into a long-term `business_query` contract. It must cover scoped read operations for `aggregate`, `list`, `detail`, `breakdown`, and `compare`; controlled backend execution; answer/query context for follow-up drilldown; safe projection; final response behavior; regression evals; and basic console support.

This phase is not a metric-only cleanup. It must make future business facts extensible without multiplying hardcoded metric, time, status, parser, tool, projection, and frontend branches.

</domain>

<decisions>
## Implementation Decisions

### Query Contract And Phase Depth

- **D-62-01:** Phase 62 should deliver the complete business-query foundation: contract, policy, runtime skeleton, answer context, projection/UI/eval, and at least one controlled runtime/eval example for `breakdown` and `compare`.
- **D-62-02:** Introduce `business_query` as the long-term primary read contract. Existing `business_metric_query` remains only as a compatibility/migration entry and must map into `BusinessQuerySpec`.
- **D-62-03:** Lock the read operation taxonomy now: `aggregate`, `list`, `detail`, `breakdown`, and `compare`. `draft` and `execute` remain action-path concepts and must not be mixed into business read query.
- **D-62-04:** Initial resource coverage is `order`, `refund_case`, `ticket`, `coupon_record`, and `merchant_metric`.

### Runtime Scope And No-Existence-Leak

- **D-62-05:** Separate authorized business-query merchant scope from action target merchant. Business queries may operate over authorized scope-level aggregates/lists; action flows remain bound to one target merchant.
- **D-62-06:** `BusinessFactService` owns the business-query compiler/executor. Repositories expose controlled methods only. Agent nodes, tools, and final response code must not build ad hoc query conditions or call generic list helpers.
- **D-62-07:** Permission and scope checks must happen before existence disclosure. Out-of-scope merchant/resource/id inputs return the same safe scope-denied or empty-safe result without confirming whether the object exists.
- **D-62-08:** Metric/resource descriptors define compatibility rules such as `current_snapshot`. Graph/slot logic may clarify early, but the service boundary is the final gate and must reject incompatible specs.

### Answer Context And Drilldown

- **D-62-09:** `last_query_spec`, `last_answer_context`, and `result_cursor` all belong in Phase 62.
- **D-62-10:** Answer context stores only replayable query spec and safe projection metadata: result ids/refs, allowed drilldowns, fields shown, cursor, and scope/time/filter summary. It must not store raw rows.
- **D-62-11:** Drilldown follow-ups derive a new operation from `last_query_spec` and re-execute through backend query with fresh scope, field, cursor, and no-existence-leak validation.
- **D-62-12:** Pending-slot and follow-up handling should generalize into an expected-slot-type flow for time, resource id, merchant filter, field/drilldown request, and similar answers. Avoid per-slot hardcoded branches.

### Projection UI And Eval

- **D-62-13:** Phase 62 must add typed payload and basic Timeline/Details display that distinguishes `aggregate`, `list`, `detail`, `breakdown`, `compare`, RAG, clarification, and unsupported results.
- **D-62-14:** Safe projection uses field allowlists and per-resource projection. Each resource defines displayable fields, PII/redaction rules, prompt payload, and UI payload.
- **D-62-15:** Eval/golden coverage must include multi-turn drilldown, permission boundaries, and list/detail no-existence-leak. Required representative flow: `本周多少订单？` followed by `订单号是多少？`.
- **D-62-16:** `breakdown` and `compare` cannot be schema-only promises. Phase 62 needs contract plus at least one controlled runtime/eval example for each capability.

### Deferrals And Phase Boundaries

- **D-62-17:** Defer risk/action taxonomy unification to Phase 63. Phase 62 only ensures business read query does not mix into `draft` or `execute` action paths.
- **D-62-18:** Defer RAG risk label unification to Phase 64. Phase 62 preserves the business facts vs RAG authority boundary but does not unify RAG labels.
- **D-62-19:** Phase 62 handles only the business-query payload pieces needed for its own result types. Defer global event, response-kind, graph-node, tool-label, and console-label registry work to Phase 65.
- **D-62-20:** Do not mutate ROADMAP during Phase 62 discuss to register Phase 67. Record the recommendation for a future `State Machine Registry And DB Constraint Hardening` phase and revisit formal registration after the Phase 62 plan is accepted.

### the agent's Discretion

- Exact class/module names for the query registry, descriptors, and specs are implementation discretion as long as the plan names one owner and every consumer derives from it.
- Exact frontend layout is implementation discretion, but typed payload support and result-kind distinction are required.
- Exact eval fixture format is planner discretion, but the required drilldown, permission, and no-existence-leak scenarios must be executable with MOCA-approved test entrypoints.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope And Current Planning State

- `.planning/ROADMAP.md` — Phase 62 goal, success criteria, and intended five-plan split.
- `.planning/STATE.md` — Current phase state and Phase 62/63/64/65/66 registration status.
- `.planning/ARCHITECTURE-DEBT.md` — Phase 61 metric compromises and the 2026-07-09 Phase 62-66 hardcoding coverage matrix.
- `.planning/phases/61-product-experience-fixes/61-CONTEXT.md` — Locked Phase 61 metric semantics, scope boundaries, response copy, console, and regression decisions.

### Accepted Architecture Contracts

- `docs/contract-spec.md` — TrustedContext, ToolPlatform, BusinessFactService, KnowledgeService, action/approval, replay, intent, and tool boundaries.
- `docs/architecture-overview.md` — Current architecture layering and non-negotiable code-controlled safety boundaries.
- `docs/current-langgraph-architecture.md` — Current canonical graph shape and node responsibilities.

### Source Anchors For Planning

- `src/agent/schemas.py` — Current intent, operation, metric, time, and slot schemas.
- `src/business/schemas.py` — Current `BusinessMetricQueryInput` and metric result contract.
- `src/business/service.py` — Current BusinessFactService metric execution, merchant-scope checks, time/status handling, and no-leak helpers.
- `src/tools/catalog.py` — Current tool descriptors and `query_business_metric` schema.
- `src/agent/nodes/contextual_intent_resolve.py` — Current metric parser and pending metric time follow-up logic.
- `src/agent/nodes/slot_resolution_gate.py` — Current duplicate metric parser and active-flow slot merge.
- `frontend/src/types/events.ts` and `frontend/src/components/timeline/TimelineStep.tsx` — Current result-kind and timeline display surfaces.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `BusinessFactService` already owns scoped business facts and metric execution; Phase 62 should extend this boundary rather than introducing tool-side or agent-node query compilation.
- `ToolCatalog` and `ToolPlatform` already provide descriptor-driven tool visibility, schema validation, runtime auth, projection, and event recording.
- `TrustedContext` and `project_to_tool_context` already carry tenant, user, role, permissions, merchant scope, session, thread, run, trace, and effective time into tools.
- Existing frontend timeline/details components can be extended with typed business-query result kinds, but current types are not sufficient for list/detail/breakdown/compare.

### Established Patterns

- LLM output may produce structured candidates, but authorization, scope, tool policy, execution, projection, approval, and replay truth stay backend-owned.
- Business facts and RAG have separate authority boundaries. RAG cannot prove current business facts; business query cannot replace policy evidence.
- Memory remains contextual-only. It may carry query/answer context for follow-up behavior, but it must not become business fact authority.
- MOCA test evidence must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or repository `.venv/bin/...`; bare `pytest` and bare `python -m pytest` are invalid.

### Integration Points

- Query parsing starts in `contextual_intent_resolve` / `slot_resolution_gate` but should move toward shared registry/resolver ownership.
- Backend query execution belongs behind `BusinessFactService`.
- Tool exposure should use a descriptor-backed business-query tool path, not a generic SQL/list executor.
- Final response and API/SSE payloads need typed result payloads and prompt-safe/UI-safe projections.
- Frontend Timeline/Details must support business-query result types without rendering raw payloads or scope internals.

</code_context>

<specifics>
## Specific Ideas

- Required drilldown example: user asks `本周多少订单？`; after an aggregate answer, user asks `订单号是多少？`; the system derives a list query from `last_query_spec`, revalidates scope/fields/cursor, and returns safe order identifiers.
- `current_snapshot` remains valid only where the metric/resource descriptor says a current-state snapshot is meaningful. For event-count metrics, current/now without a time range should clarify or fail validation.
- `business_metric_query` should not become another permanent branch. It is a migration shim into `business_query`.
- Phase 62 should avoid a generic database exploration feature. No raw SQL, arbitrary filters, or generic repository list-all exposure.

</specifics>

<deferred>
## Deferred Ideas

- Phase 63: risk severity vs risk disposition, action taxonomy, `canonical_action_type`, action keyword extraction, and evidence-required/action-bound intent routing registry.
- Phase 64: RAG risk label registry and `manual_review_sensitive` / conflict / stale-evidence label parity across builder, verifier, metrics, routing, and recommendation.
- Phase 65: global trace event, response-kind, node label, tool label, safe-reason label, DB CHECK, replay validator, and frontend/backend console label registry.
- Phase 66: demo seed constants, test magic dates, local config/port/DB defaults, investigate iteration settings, and demo authz role/scope cleanup.
- Suggested future Phase 67: `State Machine Registry And DB Constraint Hardening`, covering run/action/approval/memory/replay status registries, DB CHECK constraints, API schema, frontend types, and parity tests.

</deferred>

---

*Phase: 62-business-query-and-drilldown-foundation*
*Context gathered: 2026-07-09*
