# Phase 62: Business Query And Drilldown Foundation - Research

**Researched:** 2026-07-09
**Domain:** Scoped business query contracts, drilldown state, safe backend execution, projection, and console display [VERIFIED: .planning/ROADMAP.md + .planning/phases/62-business-query-and-drilldown-foundation/62-CONTEXT.md]
**Confidence:** HIGH for codebase anchors and project constraints; MEDIUM for exact implementation file names, which remain planner discretion [VERIFIED: codebase grep + 62-CONTEXT.md]

<user_constraints>
## User Constraints (from CONTEXT.md)

All claims in this section are copied from `.planning/phases/62-business-query-and-drilldown-foundation/62-CONTEXT.md`. [VERIFIED: 62-CONTEXT.md]

### Locked Decisions

#### Query Contract And Phase Depth

- **D-62-01:** Phase 62 should deliver the complete business-query foundation: contract, policy, runtime skeleton, answer context, projection/UI/eval, and at least one controlled runtime/eval example for `breakdown` and `compare`.
- **D-62-02:** Introduce `business_query` as the long-term primary read contract. Existing `business_metric_query` remains only as a compatibility/migration entry and must map into `BusinessQuerySpec`.
- **D-62-03:** Lock the read operation taxonomy now: `aggregate`, `list`, `detail`, `breakdown`, and `compare`. `draft` and `execute` remain action-path concepts and must not be mixed into business read query.
- **D-62-04:** Initial resource coverage is `order`, `refund_case`, `ticket`, `coupon_record`, and `merchant_metric`.

#### Runtime Scope And No-Existence-Leak

- **D-62-05:** Separate authorized business-query merchant scope from action target merchant. Business queries may operate over authorized scope-level aggregates/lists; action flows remain bound to one target merchant.
- **D-62-06:** `BusinessFactService` owns the business-query compiler/executor. Repositories expose controlled methods only. Agent nodes, tools, and final response code must not build ad hoc query conditions or call generic list helpers.
- **D-62-07:** Permission and scope checks must happen before existence disclosure. Out-of-scope merchant/resource/id inputs return the same safe scope-denied or empty-safe result without confirming whether the object exists.
- **D-62-08:** Metric/resource descriptors define compatibility rules such as `current_snapshot`. Graph/slot logic may clarify early, but the service boundary is the final gate and must reject incompatible specs.

#### Answer Context And Drilldown

- **D-62-09:** `last_query_spec`, `last_answer_context`, and `result_cursor` all belong in Phase 62.
- **D-62-10:** Answer context stores only replayable query spec and safe projection metadata: result ids/refs, allowed drilldowns, fields shown, cursor, and scope/time/filter summary. It must not store raw rows.
- **D-62-11:** Drilldown follow-ups derive a new operation from `last_query_spec` and re-execute through backend query with fresh scope, field, cursor, and no-existence-leak validation.
- **D-62-12:** Pending-slot and follow-up handling should generalize into an expected-slot-type flow for time, resource id, merchant filter, field/drilldown request, and similar answers. Avoid per-slot hardcoded branches.

#### Projection UI And Eval

- **D-62-13:** Phase 62 must add typed payload and basic Timeline/Details display that distinguishes `aggregate`, `list`, `detail`, `breakdown`, `compare`, RAG, clarification, and unsupported results.
- **D-62-14:** Safe projection uses field allowlists and per-resource projection. Each resource defines displayable fields, PII/redaction rules, prompt payload, and UI payload.
- **D-62-15:** Eval/golden coverage must include multi-turn drilldown, permission boundaries, and list/detail no-existence-leak. Required representative flow: `本周多少订单？` followed by `订单号是多少？`.
- **D-62-16:** `breakdown` and `compare` cannot be schema-only promises. Phase 62 needs contract plus at least one controlled runtime/eval example for each capability.

#### Deferrals And Phase Boundaries

- **D-62-17:** Defer risk/action taxonomy unification to Phase 63. Phase 62 only ensures business read query does not mix into `draft` or `execute` action paths.
- **D-62-18:** Defer RAG risk label unification to Phase 64. Phase 62 preserves the business facts vs RAG authority boundary but does not unify RAG labels.
- **D-62-19:** Phase 62 handles only the business-query payload pieces needed for its own result types. Defer global event, response-kind, graph-node, tool-label, and console-label registry work to Phase 65.
- **D-62-20:** Do not mutate ROADMAP during Phase 62 discuss to register Phase 67. Record the recommendation for a future `State Machine Registry And DB Constraint Hardening` phase and revisit formal registration after the Phase 62 plan is accepted.

### Claude's Discretion

- Exact class/module names for the query registry, descriptors, and specs are implementation discretion as long as the plan names one owner and every consumer derives from it.
- Exact frontend layout is implementation discretion, but typed payload support and result-kind distinction are required.
- Exact eval fixture format is planner discretion, but the required drilldown, permission, and no-existence-leak scenarios must be executable with MOCA-approved test entrypoints.

### Deferred Ideas (OUT OF SCOPE)

- Phase 63: risk severity vs risk disposition, action taxonomy, `canonical_action_type`, action keyword extraction, and evidence-required/action-bound intent routing registry.
- Phase 64: RAG risk label registry and `manual_review_sensitive` / conflict / stale-evidence label parity across builder, verifier, metrics, routing, and recommendation.
- Phase 65: global trace event, response-kind, node label, tool label, safe-reason label, DB CHECK, replay validator, and frontend/backend console label registry.
- Phase 66: demo seed constants, test magic dates, local config/port/DB defaults, investigate iteration settings, and demo authz role/scope cleanup.
- Suggested future Phase 67: `State Machine Registry And DB Constraint Hardening`, covering run/action/approval/memory/replay status registries, DB CHECK constraints, API schema, frontend types, and parity tests.
</user_constraints>

## Project Constraints (from CLAUDE.md and AGENTS.md)

- Local validation evidence in MOCA must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or repository `.venv/bin/...`; bare `pytest` and bare `python -m pytest` are invalid evidence. [VERIFIED: CLAUDE.md + AGENTS.md]
- Any local debug, startup, UI, API, RAG, agent, memory, or tool-call validation issue discovered during implementation must be appended in Chinese to `.planning/LOCAL-VALIDATION-ISSUES.md` after handling. [VERIFIED: CLAUDE.md + AGENTS.md]
- Changes to tool calling, RAG, memory, or intent recognition that discover or fix subsystem-level debt must append an entry to `.planning/ARCHITECTURE-DEBT.md` with evidence and residual risk. [VERIFIED: CLAUDE.md + AGENTS.md]
- Phase-level plans must be split before execution when a phase spans multiple service boundaries, ownership domains, waves, or verification gates; one oversized plan covering contract, runtime, compatibility, callers, security, and validation is a planning blocker. [VERIFIED: AGENTS.md]
- `docs/contract-spec.md` is the accepted contract semantics reference, but it is not proof of implementation; implementation/spec divergence requires a reviewed spec fix, MVP note, or owner-named deferral. [VERIFIED: CLAUDE.md + AGENTS.md]
- Project-local review workflow expects GSD plan checker first and Codex cross-review afterward for phase-level plans and larger changes. [VERIFIED: CLAUDE.md + AGENTS.md]

<phase_requirements>
## Phase Requirements

Phase 62 uses phase-local requirement IDs `BQ-62-01` through `BQ-62-08` for planning traceability. They are canonical for Phase 62 PLAN.md, VALIDATION.md, and research/test maps; `.planning/REQUIREMENTS.md` is not mutated by this planning revision because Phase 62 decisions are already locked in `62-CONTEXT.md` and the checker finding only requires concrete IDs inside Phase 62 artifacts. [VERIFIED: .planning/ROADMAP.md + .planning/REQUIREMENTS.md + 62-CONTEXT.md]

| Req ID | Requirement |
|--------|-------------|
| BQ-62-01 | Registry is the single source for operation/resource/metric/time/status/field/sort definitions. |
| BQ-62-02 | `business_query` is the primary read contract and `business_metric_query` maps into `BusinessQuerySpec` as compatibility only. |
| BQ-62-03 | `BusinessFactService` owns safe aggregate/list/detail/breakdown/compare execution. |
| BQ-62-04 | Out-of-scope list/detail/resource inputs do not reveal existence across service, graph, API, response, eval, or UI payloads. |
| BQ-62-05 | Drilldown flow uses `last_query_spec`, `last_answer_context`, and `result_cursor` to re-execute backend query safely. |
| BQ-62-06 | Projection, final response, and API/SSE emit bounded prompt-safe and UI-safe `business_query_answer` payloads. |
| BQ-62-07 | Frontend Timeline/Details render aggregate/list/detail/breakdown/compare from typed payloads without raw rows. |
| BQ-62-08 | Golden/eval coverage includes drilldown, permission boundary, list/detail no-existence-leak, breakdown, compare, projection bounds, clarification, and unsupported cases. |
</phase_requirements>

## Summary

Phase 62 is not a metric cleanup; it is the foundation that turns the Phase 61 metric MVP into a general read-only `business_query` system for `aggregate`, `list`, `detail`, `breakdown`, and `compare` while preserving ToolPlatform, TrustedContext, BusinessFactService, and no-existence-leak boundaries. [VERIFIED: 62-CONTEXT.md + .planning/ROADMAP.md + docs/contract-spec.md]

The current implementation has the exact debt Phase 62 is meant to remove: metric IDs, resource mapping, time presets, status allowlists, parser logic, tool schema, projection, final response, API payload, and frontend labels are duplicated across agent schemas, routing, node parsers, BusinessFactService, ToolCatalog, projection, final response, API response shaping, eval fixtures, and frontend timeline/types. [VERIFIED: codebase grep across src/agent, src/business, src/tools, src/api, frontend, evaluation + .planning/ARCHITECTURE-DEBT.md]

**Primary recommendation:** Keep the roadmap's five-plan split and make Plan 62-01 establish the registry/spec source of truth before touching runtime, drilldown, projection, or UI, because every later plan should consume the same descriptors instead of introducing another branch. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md + codebase grep]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Natural-language admission and missing-slot detection | API / Backend agent graph | Business query registry | `contextual_intent_resolve` and `slot_resolution_gate` currently own initial interpretation, but Phase 62 should make them consume shared registry/resolver metadata. [VERIFIED: src/agent/nodes/contextual_intent_resolve.py + src/agent/nodes/slot_resolution_gate.py + 62-CONTEXT.md] |
| Query operation/resource/time/status/field taxonomy | API / Backend domain registry | Agent parser and ToolCatalog | Current literals and allowlists are split across agent, business, and tool modules; Phase 62 success criteria require one source of truth. [VERIFIED: src/agent/schemas.py + src/agent/routing.py + src/business/schemas.py + src/tools/catalog.py + .planning/ROADMAP.md] |
| Tool visibility, schema validation, runtime auth, and event recording | API / Backend ToolPlatform | BusinessFactService | Contract spec assigns graph-facing dispatch and validation to ToolPlatform, while BusinessFactService owns domain facts and scope checks. [CITED: docs/contract-spec.md] |
| Business query compilation and execution | API / Backend BusinessFactService | Database / Storage | Locked decision D-62-06 makes BusinessFactService the compiler/executor owner; repositories must expose controlled methods only. [VERIFIED: 62-CONTEXT.md] |
| Trusted tenant, role, permission, and merchant scope | API / Backend TrustedContext and ToolCallContext | BusinessFactService | TrustedContext is canonical and must not be overwritten by user or LLM text; business reads require tenant, permission, scope, and domain ownership checks. [CITED: docs/contract-spec.md] |
| No-existence-leak enforcement | API / Backend BusinessFactService and ToolPolicy | Projection/final response | Scope checks must happen before existence disclosure, and denied resources must not confirm object existence. [VERIFIED: 62-CONTEXT.md + src/business/service.py] |
| Follow-up drilldown state | API / Backend agent session/checkpoint state | BusinessFactService revalidation | Phase 62 must add `last_query_spec`, `last_answer_context`, and `result_cursor`; drilldowns re-execute through backend with fresh scope/field/cursor validation. [VERIFIED: 62-CONTEXT.md + src/agent/state.py + src/agent/nodes/receive_request.py] |
| Prompt-safe and UI-safe projection | API / Backend projection/final response/API payload | Frontend rendering | Backend must project allowlisted fields and bounded payloads; frontend must not synthesize scope, freshness, or evidence claims. [VERIFIED: 62-CONTEXT.md + src/tools/projection.py + src/agent/nodes/final_response.py + src/api/routers/agent_runs.py + 62-UI-SPEC.md] |
| Timeline and Details presentation | Browser / Client | API payload | Phase 62 UI contract requires typed business-query payload rendering in existing Agent Console Timeline/Details without raw rows or scope internals. [VERIFIED: 62-UI-SPEC.md + frontend/src/types/events.ts + frontend/src/components/timeline/TimelineStep.tsx] |
| Validation and regression coverage | Test/eval layer | Backend and frontend | Existing Phase 61 coverage proves metric paths; Phase 62 needs new coverage for drilldown, list/detail no-leak, breakdown/compare examples, projection bounds, and UI typed payloads. [VERIFIED: tests/ + evaluation/golden/phase61_ux_cases.jsonl + 62-CONTEXT.md] |

## Standard Stack

### Core

Use the existing project stack; Phase 62 does not require a new framework or analytics engine. [VERIFIED: pyproject.toml + frontend/package.json + local environment probes]

| Library / Runtime | Project Version | Registry Latest Checked | Purpose | Why Standard |
|-------------------|-----------------|-------------------------|---------|--------------|
| Python | 3.12.13 | local runtime only | Backend runtime and tests | Project requires Python `>=3.12` and current venv runs 3.12.13. [VERIFIED: pyproject.toml + local `uv run python`] |
| FastAPI | installed 0.136.1 | PyPI latest 0.139.0, published 2026-07-01 | API routes and SSE surfaces | Existing API uses FastAPI; Phase 62 should extend existing routes/payloads, not add a service boundary. [VERIFIED: pyproject.toml + PyPI JSON + src/api] |
| Pydantic | installed/latest 2.13.4, published 2026-05-06 | PyPI 2.13.4 | Strict input/output contracts | Pydantic v2 supports `ConfigDict(extra="forbid")`, validators, and JSON schema patterns used by current metric models. [VERIFIED: PyPI JSON + Context7 `/pydantic/pydantic` + src/business/schemas.py] |
| SQLAlchemy | installed 2.0.49 | PyPI latest 2.0.51, published 2026-06-15 | Controlled ORM query construction | SQLAlchemy 2.0 `select()`/`Session.execute()`/`func.count()` cover bounded aggregate/list/detail queries without raw SQL exposure. [VERIFIED: PyPI JSON + Context7 `/websites/sqlalchemy_en_20` + src/business/service.py] |
| LangGraph | installed 1.1.10 | PyPI latest 1.2.8, published 2026-07-06 | Existing agent graph orchestration and checkpoint state | Current graph has 15 canonical nodes and uses state/checkpoint concepts; Phase 62 should not add a new graph node unless a plan proves the boundary. [VERIFIED: PyPI JSON + Context7 `/websites/langchain_oss_python_langgraph` + docs/current-langgraph-architecture.md] |
| langgraph-checkpoint-postgres | installed 3.0.5 | PyPI latest 3.1.0, published 2026-05-12 | Persistent thread/checkpoint state | Existing dependency implies checkpoint state can store follow-up query context, but state must not become business fact authority. [VERIFIED: PyPI JSON + pyproject.toml + docs/contract-spec.md] |
| PostgreSQL / pgvector image | running `pgvector/pgvector:pg16` container | local Docker only | Demo business data and agent persistence | Local `moca-postgres-1` is running on port 5432; `psql` is not installed on host, so plans should use app/SQLAlchemy or Docker fallback for DB checks. [VERIFIED: `docker ps` + environment probe] |
| React | installed 19.2.6 | npm latest 19.2.7, modified 2026-07-08 | Agent Console UI | Existing frontend is React; Phase 62 UI should extend current Timeline/Details components. [VERIFIED: frontend package tree + npm registry + 62-UI-SPEC.md] |
| Vite | installed 8.0.13 | npm latest 8.1.4, modified 2026-07-09 | Frontend dev/build/test harness | Existing frontend uses Vite; no new app shell is required. [VERIFIED: frontend package tree + npm registry + 62-UI-SPEC.md] |

### Supporting

| Library / Tool | Project Version | Purpose | When to Use |
|----------------|-----------------|---------|-------------|
| pytest | installed 9.0.3; PyPI latest 9.1.1 | Backend unit/integration tests | Use through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or `.venv/bin/...` only. [VERIFIED: local importlib + PyPI JSON + CLAUDE.md] |
| pytest-asyncio | installed 1.3.0; PyPI latest 1.4.0 | Async backend tests | Use for async service/API graph tests already in project. [VERIFIED: local importlib + PyPI JSON + pyproject.toml] |
| Vitest | installed 4.1.7; npm latest 4.1.10 | Frontend unit tests | Use for `useAgentRun`, Timeline, Details, and typed payload rendering. [VERIFIED: frontend package tree + npm registry + frontend tests] |
| Playwright | repo package 1.61.1; global host binary 1.60.0 | Frontend E2E | Use `npm --prefix frontend exec playwright -- ...` or npm scripts to avoid older global Python 3.9 Playwright. [VERIFIED: environment probe] |
| Ruff | installed 0.15.12; PyPI latest 0.15.20 | Lint/format | Use via `uv run ruff ...` if plans need lint verification. [VERIFIED: local importlib + PyPI JSON + AGENTS.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `BusinessFactService` business-query compiler/executor | New analytics microservice | Do not use; D-62-06 locks BusinessFactService ownership and current contracts already define BusinessFactService as business fact owner. [VERIFIED: 62-CONTEXT.md + docs/contract-spec.md] |
| Strict `BusinessQuerySpec` plus descriptor allowlists | Raw SQL or generic database exploration | Do not use; project requirements explicitly exclude arbitrary SQL/free-form DB exploration, and contract requires tool/policy/scope gates. [VERIFIED: .planning/REQUIREMENTS.md + docs/contract-spec.md] |
| Registry-driven parser/resolver metadata | One branch per metric/time/status/follow-up | Do not use; Phase 62 goal is to avoid multiplying hardcoded branches. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md] |
| Typed backend payloads | Frontend parsing localized final response text | Do not use; Phase 62 UI contract requires typed `business_query` payload data for long-term query answers. [VERIFIED: 62-UI-SPEC.md] |

**Installation:** No new packages are recommended for Phase 62. [VERIFIED: pyproject.toml + frontend/package.json + 62-CONTEXT.md]

## Architecture Patterns

### System Architecture Diagram

```text
User natural-language request
  -> receive_request
  -> contextual_intent_resolve
  -> slot_resolution_gate
       | missing slot
       v
     clarification_gate -> final_response/API/UI
       |
       | complete BusinessQuerySpec
       v
     investigate
       -> ToolPlatform.visible_tools/invoke
       -> ToolPolicy + TrustedContext -> ToolCallContext
       -> BusinessFactService business_query compiler/executor
       -> controlled repository/SQLAlchemy statements
       -> PostgreSQL
       -> BusinessQueryResult + BusinessFactRef + AnswerContext/Cursor
       -> ToolResult projection
       -> final_response safe business_query_answer
       -> agent-runs API/SSE safe payload
       -> Frontend Timeline/Details

Follow-up drilldown:
User follow-up -> receive_request loads same-thread state
  -> expected-slot-type resolver uses last_query_spec/last_answer_context/result_cursor
  -> derives new BusinessQuerySpec
  -> re-enters ToolPlatform + BusinessFactService path with fresh scope/field/cursor validation
```

This flow matches the current 15-node graph vocabulary and keeps runtime reads behind ToolPlatform and BusinessFactService. [VERIFIED: docs/current-langgraph-architecture.md + docs/contract-spec.md + 62-CONTEXT.md]

### Recommended Project Structure

Exact names are planner discretion, but the plan should name one registry/spec owner and route all consumers through it. [VERIFIED: 62-CONTEXT.md]

```text
src/business/
├── schemas.py              # Existing metric schemas; add/import BusinessQuerySpec/Result contracts here or from a sibling.
├── service.py              # Existing BusinessFactService; keep compiler/executor boundary here.
└── query/
    ├── registry.py         # Operation/resource/metric/time/status/field/sort/cursor descriptors.
    ├── schemas.py          # BusinessQuerySpec, BusinessQueryResult, AnswerContext, Cursor if split from business.schemas.
    ├── compiler.py         # Descriptor-to-controlled-query planning, no raw SQL strings.
    └── projection.py       # Prompt/UI projection descriptors if not owned by src/tools/projection.py.

src/agent/
├── schemas.py              # Intent/operation/slot state imports query literals from registry owner.
├── routing.py              # Slot policy consumes registry; no duplicate metric constants.
└── nodes/
    ├── contextual_intent_resolve.py  # Parser delegates to shared resolver metadata.
    ├── slot_resolution_gate.py       # Expected-slot-type flow, not metric-only branches.
    └── investigate.py                # Calls business_query through ToolPlatform.

src/tools/
├── catalog.py              # business_query descriptor and compatibility query_business_metric declaration.
├── projection.py           # Bounded prompt-safe summaries and UI-safe normalized output.
└── contracts.py            # BusinessFactRef/ToolResult contract updates.

frontend/src/
├── types/events.ts
├── components/timeline/TimelineStep.tsx
└── components/details/DetailsPanel.tsx
```

The proposed structure is a planning shape, not an existing file inventory. [ASSUMED]

### Pattern 1: Descriptor-Owned Query Taxonomy

**What:** Define operation, resource, metric, time preset, status, field, sort, limit, cursor, compatibility, and projection metadata in one registry consumed by agent parsers, Pydantic schemas, ToolCatalog JSON schema generation, BusinessFactService validation, projection, eval, and frontend-safe labels. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md]

**When to use:** Use for every Phase 62 business-query capability before adding list/detail/breakdown/compare branches. [VERIFIED: 62-CONTEXT.md]

**Current anchors:** `src/agent/schemas.py`, `src/agent/routing.py`, `src/agent/nodes/contextual_intent_resolve.py`, `src/agent/nodes/slot_resolution_gate.py`, `src/business/schemas.py`, `src/business/service.py`, `src/tools/catalog.py`, `src/tools/projection.py`, `src/agent/nodes/final_response.py`, `src/api/routers/agent_runs.py`, `frontend/src/types/events.ts`, and `frontend/src/components/timeline/TimelineStep.tsx` currently contain metric-specific literals or branches. [VERIFIED: codebase grep]

### Pattern 2: Compatibility Shim, Not Parallel Product Surface

**What:** Keep `business_metric_query` and `query_business_metric` only as compatibility inputs that map into `BusinessQuerySpec`, then execute through the same `business_query` service path. [VERIFIED: 62-CONTEXT.md]

**When to use:** Use for Phase 61 metric golden tests and historical persisted run/tool records while moving new logic to `business_query`. [VERIFIED: evaluation/golden/phase61_ux_cases.jsonl + Runtime State Inventory]

**Example:**

```python
# Source: local pattern from BusinessMetricQueryInput and Phase 62 decision D-62-02.
def metric_input_to_business_query(metric: BusinessMetricQueryInput) -> BusinessQuerySpec:
    return BusinessQuerySpec(
        operation="aggregate",
        resource=metric.resource_type,
        metric_id=metric.metric_id,
        time=metric.time,
        filters=metric.safe_filters(),
    )
```

This example is a planning pattern; exact class and helper names are not locked. [ASSUMED]

### Pattern 3: Strict Schemas at the Boundary

**What:** Use Pydantic v2 strict models with forbidden extra fields for `BusinessQuerySpec`, `BusinessQueryResult`, query filters, cursors, answer context, and UI-safe payloads. [VERIFIED: Context7 `/pydantic/pydantic` + src/business/schemas.py]

**When to use:** Use at every LLM/tool/API boundary to prevent authority-bearing fields such as `tenant_id`, `merchant_scope`, raw SQL, raw cursor tokens, or unallowlisted display fields from entering through user/tool args. [CITED: docs/contract-spec.md]

**Example:**

```python
# Source: Context7 /pydantic/pydantic and local BusinessMetricQueryInput pattern.
class BusinessQuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["aggregate", "list", "detail", "breakdown", "compare"]
    resource: Literal["order", "refund_case", "ticket", "coupon_record", "merchant_metric"]
    limit: int = Field(default=20, ge=1, le=100)
```

### Pattern 4: Controlled SQLAlchemy Statements

**What:** Compile descriptors into fixed SQLAlchemy 2.0 `select()` statements, joins, filters, `func.count()`, ordering, and bounded `limit + 1` pagination. [VERIFIED: Context7 `/websites/sqlalchemy_en_20` + src/business/service.py]

**When to use:** Use for runtime aggregate/list/detail/breakdown/compare examples instead of generic repository list helpers or raw SQL strings. [VERIFIED: 62-CONTEXT.md]

**Example:**

```python
# Source: Context7 SQLAlchemy 2.0 select/order_by/limit docs and local BusinessFactService query style.
stmt = (
    select(Order.id, Order.order_no, Order.status, Order.created_at)
    .where(Order.tenant_id == ctx.tenant_id)
    .where(Order.merchant_id.in_(authorized_merchant_ids))
    .order_by(Order.created_at.desc(), Order.id.desc())
    .limit(spec.limit + 1)
)
```

### Pattern 5: Answer Context Stores Requery Metadata, Not Rows

**What:** Store replayable query spec, safe refs, shown fields, allowed drilldowns, safe scope/time/filter labels, and cursor metadata, but not raw database rows. [VERIFIED: 62-CONTEXT.md]

**When to use:** Use for multi-turn drilldown such as `本周多少订单？` followed by `订单号是多少？`; the second turn derives a list query and revalidates scope and fields through BusinessFactService. [VERIFIED: 62-CONTEXT.md + 62-UI-SPEC.md]

### Anti-Patterns to Avoid

- **Raw SQL or generic database explorer:** Excluded by requirements and unsafe across ToolPlatform/TrustedContext boundaries. [VERIFIED: .planning/REQUIREMENTS.md + docs/contract-spec.md]
- **New per-metric or per-follow-up branches:** This is the core hardcoding debt Phase 62 exists to stop. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md]
- **Frontend parsing final answer text:** UI contract requires typed backend-projected `business_query` payloads. [VERIFIED: 62-UI-SPEC.md]
- **Storing raw rows in checkpoint/session state:** D-62-10 explicitly forbids raw rows in answer context. [VERIFIED: 62-CONTEXT.md]
- **Final response querying the database:** Current architecture keeps investigation/tool execution before final response; final response should consume safe business context/projection only. [VERIFIED: docs/current-langgraph-architecture.md + src/agent/nodes/final_response.py]
- **Action taxonomy changes inside Phase 62:** D-62-17 defers risk/action taxonomy unification to Phase 63. [VERIFIED: 62-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query validation | Ad hoc dict checks in nodes/tools | Pydantic v2 strict models plus registry validators | Current metric schema already uses strict validation; Context7 confirms v2 forbidden-extra and validator patterns. [VERIFIED: src/business/schemas.py + Context7 `/pydantic/pydantic`] |
| Business query execution | Generic repository `list_all` or raw SQL string builder | BusinessFactService compiler/executor with SQLAlchemy expressions | Project contract and D-62-06 assign business reads to BusinessFactService and controlled repository methods. [VERIFIED: 62-CONTEXT.md + docs/contract-spec.md] |
| Authorization | User/LLM-supplied tenant, merchant scope, or permissions | TrustedContext -> ToolCallContext -> ToolPolicy/BusinessFactService checks | TrustedContext is canonical and cannot be overwritten by user or LLM text. [CITED: docs/contract-spec.md] |
| Cursoring | Raw offset/cursor tokens exposed to frontend or prompt | Backend-owned cursor plus safe `cursor_label` / capability flags | UI contract forbids raw cursor token display. [VERIFIED: 62-UI-SPEC.md] |
| Drilldown | Persist raw rows or infer from localized final text | `last_query_spec`, `last_answer_context`, and `result_cursor` | D-62-09 through D-62-11 lock structured context and backend re-execution. [VERIFIED: 62-CONTEXT.md] |
| Projection | Unbounded JSON dumps into prompt/UI | Field allowlists, PII/redaction rules, prompt-safe and UI-safe projections | D-62-14 and UI contract require backend-projected safe fields only. [VERIFIED: 62-CONTEXT.md + 62-UI-SPEC.md] |
| UI surface | New dashboard/chart/report builder | Existing Agent Console Timeline/Details | Phase 62 UI contract excludes new page shell, chart builder, export, dashboards, and decorative layouts. [VERIFIED: 62-UI-SPEC.md] |
| Test entrypoints | Bare `pytest` | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or `.venv/bin/...` | MOCA project rules mark bare pytest evidence invalid. [VERIFIED: CLAUDE.md + AGENTS.md] |

**Key insight:** The hard part is not calculating another count; it is preventing branch drift across parser, policy, service, projection, replay, eval, API, and UI while preserving no-existence-leak semantics. [VERIFIED: .planning/ARCHITECTURE-DEBT.md + codebase grep]

## Runtime State Inventory

Phase 62 includes migration/compatibility from `business_metric_query` / `query_business_metric` / `metric_answer` to long-term `business_query`, so runtime state must be planned explicitly. [VERIFIED: 62-CONTEXT.md + codebase grep]

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Local Docker shows running `moca-postgres-1`; source models and dependencies indicate persisted agent runs, conversation messages, session memory, tool call/result records, trace events, and LangGraph checkpoint tables can contain old intent/tool/response strings and active slot payloads. Host `psql` / `pg_isready` were unavailable, so row counts were not queried. [VERIFIED: docker ps + pyproject.toml + source model grep + environment probe] | Do not require destructive migration for history. Add compatibility readers/projections so old `business_metric_query`, `query_business_metric`, and `metric_answer` records remain displayable; planner may add an optional data migration only if it can be verified through Docker/app access. [VERIFIED: 62-CONTEXT.md] |
| Live service config | Running `moca-api-1` and `moca-frontend-1` containers exist; Docker/env config grep did not find business metric env var names, but running containers will keep old code until restarted/rebuilt. [VERIFIED: docker ps + rg over docker-compose/.env/.env.example] | Include implementation verification steps that restart/rebuild local API/frontend if doing manual console validation. [VERIFIED: environment probe] |
| OS-registered state | Launchd has MOCA study reminder/audit jobs, but no launchd entries containing `business_metric`, `query_business`, or `metric_answer`; `pm2` was not present or produced no relevant process list output. [VERIFIED: launchctl/pm2 probe] | No Phase 62 rename action required for OS registrations. [VERIFIED: launchctl/pm2 probe] |
| Secrets/env vars | Source auth maps `metrics:read` to metric capability; `.env` / `.env.example` / docker compose grep did not find metric-specific secret or env var names that must be renamed. [VERIFIED: src/auth/jwt.py + src/auth/permissions.py + rg over .env/.env.example/docker-compose.yml] | Keep `metrics:read` compatibility unless policy plan explicitly introduces a new scope; do not rename secrets blindly. [VERIFIED: docs/contract-spec.md + 62-CONTEXT.md] |
| Build artifacts | `frontend/dist`, `frontend/node_modules/.vite`, `.pytest_cache`, `.ruff_cache`, and `moca.egg-info` exist in the workspace and may retain old compiled/test metadata after code changes. [VERIFIED: filesystem scan] | Rebuild frontend and refresh editable package/test caches as needed during execution; do not treat artifact grep hits as source truth. [VERIFIED: filesystem scan] |

## Common Pitfalls

### Pitfall 1: Leaving More Than One Source Of Truth

**What goes wrong:** A new operation/resource/field is added to one layer but not parser, ToolCatalog schema, BusinessFactService validation, projection, API payload, frontend type, or eval. [VERIFIED: codebase grep + .planning/ARCHITECTURE-DEBT.md]

**Why it happens:** Phase 61 metric support currently duplicated literals and branches across many files. [VERIFIED: src/agent/schemas.py + src/agent/routing.py + src/business/schemas.py + src/business/service.py + src/tools/catalog.py + src/agent/nodes/final_response.py + frontend/src/types/events.ts]

**How to avoid:** Plan a registry/parity task in 62-01 and require import/derivation checks instead of manual constant copies. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md]

**Warning signs:** The plan says "also update" more than once for the same literal set, or adds tests only at one layer. [ASSUMED]

### Pitfall 2: Making `business_metric_query` Permanent

**What goes wrong:** Metric compatibility becomes a second product surface that must be maintained beside `business_query`. [VERIFIED: 62-CONTEXT.md]

**Why it happens:** Phase 61 already has working metric tests, frontend labels, API payloads, and golden fixtures. [VERIFIED: tests/ + evaluation/golden/phase61_ux_cases.jsonl + frontend/src/components/timeline/TimelineStep.tsx]

**How to avoid:** Implement a metric-to-business-query shim and keep new logic behind `BusinessQuerySpec`. [VERIFIED: 62-CONTEXT.md]

**Warning signs:** New runtime, projection, or UI code branches on `business_metric_query` instead of `business_query` operation/resource descriptors. [ASSUMED]

### Pitfall 3: No-Existence-Leak Regression In List/Detail

**What goes wrong:** Detail/list queries reveal whether an out-of-scope merchant, order, refund, ticket, coupon, or metric exists. [VERIFIED: 62-CONTEXT.md + docs/contract-spec.md]

**Why it happens:** List/detail often tempts implementers to fetch by ID before checking trusted scope. [ASSUMED]

**How to avoid:** BusinessFactService must apply trusted tenant/permission/merchant scope before existence disclosure and return identical safe denied/empty semantics for out-of-scope inputs. [VERIFIED: 62-CONTEXT.md + src/business/service.py]

**Warning signs:** Tests assert "not found" for unauthorized IDs, or final response mentions the denied ID exists/does not exist. [VERIFIED: evaluation/golden/phase61_ux_cases.jsonl]

### Pitfall 4: Drilldown Uses Stale Rows Or Stale Scope

**What goes wrong:** Follow-up answers reuse previous rows or raw payload instead of revalidating scope, fields, cursor, and current query compatibility. [VERIFIED: 62-CONTEXT.md]

**Why it happens:** Current state has no `last_query_spec`, `last_answer_context`, or `result_cursor`, and pending follow-up logic is metric-time-specific. [VERIFIED: src/agent/state.py + src/agent/nodes/receive_request.py + src/agent/nodes/contextual_intent_resolve.py]

**How to avoid:** Store only safe query context and re-enter the backend query path for every drilldown. [VERIFIED: 62-CONTEXT.md]

**Warning signs:** Answer context contains raw rows, frontend row data drives follow-up, or drilldown bypasses ToolPlatform. [VERIFIED: 62-CONTEXT.md]

### Pitfall 5: Planner Allowlist Drift

**What goes wrong:** ToolCatalog advertises a tool, but `INVESTIGATE_ALLOWED_TOOL_NAMES` rejects it or tests lock the wrong visible set. [VERIFIED: .planning/ARCHITECTURE-DEBT.md + src/agent/nodes/investigate_planner.py + tests/tools/test_tool_platform.py]

**Why it happens:** Phase 61 added `query_business_metric` to both catalog and a separate static planner allowlist. [VERIFIED: .planning/ARCHITECTURE-DEBT.md]

**How to avoid:** Plan a parity test or derivation path when adding `business_query`. [VERIFIED: .planning/ARCHITECTURE-DEBT.md]

### Pitfall 6: API/Frontend Payload Mismatch

**What goes wrong:** Backend emits safe metadata but API filtering or frontend types drop it, producing blank timeline/details or unsafe fallbacks. [VERIFIED: src/api/routers/agent_runs.py + frontend/src/types/events.ts + frontend/src/components/timeline/TimelineStep.tsx]

**Why it happens:** Current API/frontend logic is metric-specific and does not type business-query list/detail/breakdown/compare. [VERIFIED: codebase grep + 62-UI-SPEC.md]

**How to avoid:** Plan backend payload, frontend type, Timeline label, Details tab, and E2E tests together in 62-05. [VERIFIED: .planning/ROADMAP.md + 62-UI-SPEC.md]

### Pitfall 7: Using RAG Or Memory As Business Fact Authority

**What goes wrong:** Final answers claim policy evidence for business facts or use memory/RAG to satisfy current metric/list/detail values. [VERIFIED: .planning/REQUIREMENTS.md + docs/contract-spec.md]

**Why it happens:** Business fact and policy evidence surfaces both enter final response. [VERIFIED: docs/current-langgraph-architecture.md + src/agent/nodes/final_response.py]

**How to avoid:** Preserve separate BusinessFactRef and EvidenceRef semantics; business-query final response should not claim RAG evidence unless RAG actually supplied verified policy evidence. [CITED: docs/contract-spec.md]

## Code Examples

Verified planning patterns from official docs and local code:

### Strict Boundary Model

```python
# Source: Context7 /pydantic/pydantic; local source: src/business/schemas.py.
class BusinessQueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    merchant_id: str | None = None
```

Use this pattern for every user/LLM/tool-supplied object, and reject authority-bearing extras rather than ignoring them. [VERIFIED: Context7 `/pydantic/pydantic` + docs/contract-spec.md]

### Controlled Aggregate

```python
# Source: Context7 SQLAlchemy 2.0 docs; local source: src/business/service.py.
stmt = (
    select(func.count())
    .select_from(Order)
    .where(Order.tenant_id == ctx.tenant_id)
    .where(Order.merchant_id.in_(authorized_merchant_ids))
)
```

Use fixed SQLAlchemy expressions generated from descriptors; do not compile user text or arbitrary filter JSON into SQL. [VERIFIED: Context7 `/websites/sqlalchemy_en_20` + .planning/REQUIREMENTS.md]

### Drilldown Re-Execution

```python
# Source: Phase 62 D-62-09 through D-62-11.
next_spec = derive_drilldown_spec(
    previous=state["last_query_spec"],
    answer_context=state["last_answer_context"],
    requested_fields=["order_no"],
    cursor=state.get("result_cursor"),
)
result = business_fact_service.query_business(ctx=tool_ctx, spec=next_spec)
```

This is a planning sketch; exact function and field names are implementation discretion. [ASSUMED]

### Frontend Typed Payload Consumption

```ts
// Source: 62-UI-SPEC.md typed payload contract.
if (payload.response_kind === 'business_query_answer') {
  const query = payload.business_query
  renderResultSummary(query.operation, query.result_label, query.scope_label)
}
```

Frontend should consume backend-projected safe payload fields only and must not parse localized final answer text. [VERIFIED: 62-UI-SPEC.md]

## State of the Art

| Old Approach | Current Approach For Phase 62 | When Changed / Why | Impact |
|--------------|--------------------------------|--------------------|--------|
| `business_metric_query` as a Phase 61 MVP intent/tool/final response path | `business_query` primary contract, metric path as compatibility shim | Locked in Phase 62 discuss decisions on 2026-07-09 | Prevents permanent parallel metric contract. [VERIFIED: 62-CONTEXT.md] |
| Metric/time/status parser constants duplicated across nodes and service | Registry/descriptor source of truth consumed by agent, tool, service, projection, eval, and UI | Required by Phase 62 success criterion 1 | Reduces branch drift. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md] |
| Metric operation represented as `read_status` MVP compromise | Business read operation taxonomy: `aggregate`, `list`, `detail`, `breakdown`, `compare` | Phase 61 debt recorded; Phase 62 locks read taxonomy | Keeps business reads separate from action `draft`/`execute`. [VERIFIED: .planning/ARCHITECTURE-DEBT.md + 62-CONTEXT.md] |
| Pending follow-up special-cased for metric time answers | Expected-slot-type flow for time, resource ID, merchant filter, field/drilldown requests | Locked by D-62-12 | Supports multi-turn drilldown without per-slot branches. [VERIFIED: 62-CONTEXT.md] |
| `metric_answer` frontend/API path | New `business_query_answer` typed payload with compatibility for `metric_answer` | Locked by Phase 62 UI contract | Enables aggregate/list/detail/breakdown/compare Timeline/Details rendering. [VERIFIED: 62-UI-SPEC.md] |
| Prompt/UI payload assembled from metric-specific branches | Field allowlists, redaction rules, prompt/UI payload split | Locked by D-62-14 and UI contract | Prevents raw rows, prompt bloat, and PII/scope leaks. [VERIFIED: 62-CONTEXT.md + 62-UI-SPEC.md] |

**Deprecated/outdated for new Phase 62 work:**

- Adding a new branch for every metric/time/status parser location is outdated because Phase 62 requires a shared registry. [VERIFIED: .planning/ROADMAP.md + .planning/ARCHITECTURE-DEBT.md]
- Treating `business_metric_query` as the long-term contract is outdated because D-62-02 makes `business_query` primary. [VERIFIED: 62-CONTEXT.md]
- Rendering new query results by reading localized final response text is outdated because UI contract requires typed payloads. [VERIFIED: 62-UI-SPEC.md]
- Using `read_status` as the semantic operation for metrics is a recorded Phase 61 MVP compromise, not the desired Phase 62 end state. [VERIFIED: .planning/ARCHITECTURE-DEBT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Proposed module names such as `src/business/query/registry.py` are planning suggestions, not existing locked paths. | Recommended Project Structure | Low; planner can rename while preserving ownership. |
| A2 | Warning-sign heuristics for future plan review are engineering judgment rather than direct code facts. | Common Pitfalls | Low; they guide review but do not define implementation. |
| A3 | Compatibility helper names such as `metric_input_to_business_query` and `derive_drilldown_spec` are sketches. | Architecture Patterns / Code Examples | Low; exact names are explicitly user-delegated discretion. |

## Open Questions (RESOLVED)

1. **(RESOLVED) What Phase 62 requirement IDs should PLAN.md use?** [VERIFIED: .planning/ROADMAP.md + 62-CONTEXT.md]
   - Decision: Use phase-local canonical IDs `BQ-62-01` through `BQ-62-08` inside Phase 62 planning artifacts. Do not mutate `.planning/REQUIREMENTS.md` in this checker-fix revision because the locked decisions and phase-local validation map already provide the needed traceability.
   - Mapping: `BQ-62-01` registry source of truth; `BQ-62-02` primary `business_query` contract and metric compatibility; `BQ-62-03` BusinessFactService runtime; `BQ-62-04` no-existence-leak; `BQ-62-05` answer context/drilldown; `BQ-62-06` projection/final/API payload; `BQ-62-07` frontend Timeline/Details; `BQ-62-08` golden/eval coverage.

2. **(RESOLVED) Should `docs/contract-spec.md` be updated in Phase 62 or treated as already sufficient?** [VERIFIED: docs/contract-spec.md + 62-CONTEXT.md]
   - Decision: Plan 62-02 updates `docs/contract-spec.md` with the accepted Phase 62 contract delta before ToolPlatform/runtime/UI work depends on it.
   - Required delta: define `business_query` as the primary read contract; record aggregate/list/detail/breakdown/compare taxonomy; record `business_metric_query` as compatibility into `BusinessQuerySpec`; record BusinessFactService ownership, descriptor compatibility gates, no-existence-leak, and the business-facts-versus-RAG boundary.
   - Boundary: the spec update must not implement or register Phase 63 risk/action taxonomy, Phase 64 RAG label unification, Phase 65 global label registry, Phase 66 config/test hygiene, or the suggested Phase 67 state-machine registry.

3. **(RESOLVED) How much live data migration is required?** [VERIFIED: Runtime State Inventory]
   - Decision: Phase 62 plans backwards-compatible readers, payload compatibility, and renderer compatibility; no live DB rewrite is planned.
   - Caution: Runtime records may contain old intent/tool/response strings, and host `psql` was unavailable during research, so execution must not assume direct host DB migration tooling. If implementers discover a necessary migration, it must be optional, app/SQLAlchemy or Docker-verified, no destructive rewrite by default, and documented in `.planning/LOCAL-VALIDATION-ISSUES.md` if local verification exposes a DB/env issue.
   - Rationale: `business_metric_query` remains a compatibility entry and maps into `BusinessQuerySpec`, so historical records can be read/rendered safely without rewriting old runs.

4. **(RESOLVED) Which controlled `breakdown` and `compare` examples should Phase 62 implement first?** [VERIFIED: 62-CONTEXT.md]
   - Decision: Implement `breakdown` as order count by status and `compare` as order count for the current requested period versus the previous equivalent period.
   - Coverage: Plan 62-01 registers these descriptors; Plan 62-04 implements runtime execution; Plan 62-06 adds golden/eval cases `breakdown_order_by_status` and `compare_order_count_previous_period`; Plan 62-07 renders both typed payloads in Timeline/Details.
   - Rationale: These examples use existing order/time/status paths while satisfying D-62-16 that breakdown and compare are not schema-only promises.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python via uv | Backend tests, scripts, app execution | yes | Python 3.12.13; uv 0.11.2 | Use repository `.venv/bin/...` only if confirming it belongs to this repo. [VERIFIED: environment probe + AGENTS.md] |
| Node/npm | Frontend type/unit/e2e tests | yes | Node v25.9.0; npm 11.12.1 | None needed. [VERIFIED: environment probe] |
| Docker | Local API/frontend/Postgres services | yes | Docker 29.4.2; Compose v5.1.3 | If Docker unavailable later, use unit tests that mock DB/service boundaries. [VERIFIED: environment probe] |
| PostgreSQL server | Runtime service/integration checks | yes, via container | `moca-postgres-1` image `pgvector/pgvector:pg16` | Use SQLAlchemy/app tests or `docker exec` fallback because host `psql` is missing. [VERIFIED: docker ps + environment probe] |
| Host `psql` / `pg_isready` | Direct DB inventory | no | not found | Use Docker container tools or app-level SQLAlchemy scripts if row counts are required. [VERIFIED: environment probe] |
| Repo Playwright | Frontend E2E | yes | `@playwright/test` 1.61.1 | Use repo npm command; avoid global Playwright 1.60.0 under Python 3.9 path. [VERIFIED: frontend package tree + environment probe] |
| LLM provider credentials | Live end-to-end agent behavior | not probed | unknown | Deterministic unit/integration tests should avoid requiring live LLM; manual/live tests may need existing project env. [ASSUMED] |

**Missing dependencies with no fallback:**
- None identified for planning or deterministic tests. [VERIFIED: environment probe]

**Missing dependencies with fallback:**
- Host `psql` / `pg_isready` are missing; use Docker/app-level access if direct DB inventory is needed. [VERIFIED: environment probe]

## Validation Architecture

`.planning/config.json` has `workflow.nyquist_validation: true`, so validation architecture is required. [VERIFIED: .planning/config.json]

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 9.0.3 with pytest-asyncio 1.3.0; project config sets async mode in `pyproject.toml`. [VERIFIED: local importlib + pyproject.toml] |
| Frontend framework | Vitest 4.1.7 and Playwright 1.61.1 through frontend npm package tree. [VERIFIED: frontend package tree] |
| Config file | `pyproject.toml` for backend pytest; frontend package scripts/configs under `frontend/`. [VERIFIED: pyproject.toml + frontend package tree] |
| Quick backend command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business tests/tools tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py -q --tb=short` [VERIFIED: test tree + AGENTS.md] |
| Focused graph/API command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` [VERIFIED: test tree + AGENTS.md] |
| Frontend unit command | `npm --prefix frontend test` [VERIFIED: frontend/package.json] |
| Frontend E2E command | `npm --prefix frontend run e2e` or `npm --prefix frontend exec playwright -- test` depending on existing package scripts. [VERIFIED: frontend/package.json + environment probe] |
| Full backend suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -q --tb=short` [VERIFIED: test tree + AGENTS.md] |

### Phase Requirements -> Test Map

This map uses the canonical Phase 62 requirement IDs `BQ-62-01` through `BQ-62-08`. [VERIFIED: .planning/ROADMAP.md + 62-CONTEXT.md]

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| BQ-62-01 | Registry is single source for operation/resource/metric/time/status/field/sort definitions. | unit/parity | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/tools/test_catalog.py -q --tb=short` | no for new registry file; existing adjacent tests yes. [VERIFIED: test tree] |
| BQ-62-02 | `business_metric_query` maps into `BusinessQuerySpec` and remains compatibility-only. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_schemas.py tests/agent/test_graph.py -q --tb=short` | no for new schema file; graph tests exist. [VERIFIED: test tree] |
| BQ-62-03 | BusinessFactService executes aggregate/list/detail/breakdown/compare through controlled scope-safe queries. | service/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py -q --tb=short` | no. [VERIFIED: test tree] |
| BQ-62-04 | Out-of-scope list/detail/resource inputs do not reveal existence. | service/graph/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` | partially existing metric no-leak tests only. [VERIFIED: test tree + evaluation/golden/phase61_ux_cases.jsonl] |
| BQ-62-05 | Drilldown flow `本周多少订单？` -> `订单号是多少？` re-executes backend query using last query context. | graph/eval | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short` plus eval script update | graph tests exist; new case missing. [VERIFIED: test tree + 62-CONTEXT.md] |
| BQ-62-06 | Projection/final response emits bounded prompt-safe and UI-safe `business_query_answer` payload. | unit/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/test_agent_runs_api.py -q --tb=short` | existing metric tests yes; business-query tests missing. [VERIFIED: test tree] |
| BQ-62-07 | Frontend Timeline/Details render aggregate/list/detail/breakdown/compare without raw rows or overlap. | frontend unit/build/e2e | `npm --prefix frontend test && npm --prefix frontend run build`; phase gate also runs `npm --prefix frontend run e2e` | existing metric frontend tests yes; business-query tests missing. [VERIFIED: frontend test tree + 62-UI-SPEC.md] |
| BQ-62-08 | Golden/eval coverage includes drilldown, permission boundary, list/detail no-existence-leak, breakdown, and compare. | eval | Existing Phase 61 eval script must be extended or a Phase 62 eval script added. | missing. [VERIFIED: evaluation/golden/phase61_ux_cases.jsonl + scripts/eval_phase61_ux.py + 62-CONTEXT.md] |

### Sampling Rate

- **Per task commit:** Run the smallest targeted backend/frontend command for the touched boundary, always through MOCA-approved entrypoints. [VERIFIED: AGENTS.md]
- **Per wave merge:** Run focused graph/API/backend service tests plus relevant frontend tests when payload/UI changes. [VERIFIED: test tree + 62-UI-SPEC.md]
- **Phase gate:** Full backend suite plus frontend unit/E2E and Phase 62 eval/golden run before `/gsd-verify-work`. [VERIFIED: .planning/config.json + 62-CONTEXT.md]

### Wave 0 Gaps

- [ ] `tests/business/test_business_query_registry.py` or equivalent parity tests for descriptor source of truth. [VERIFIED: test tree]
- [ ] `tests/business/test_business_query_schemas.py` for strict `BusinessQuerySpec`, filters, limits, cursors, and compatibility shim. [VERIFIED: test tree]
- [ ] `tests/business/test_business_query_service.py` for aggregate/list/detail/breakdown/compare and no-existence-leak. [VERIFIED: test tree]
- [ ] Agent graph tests for `本周多少订单？` then `订单号是多少？`. [VERIFIED: 62-CONTEXT.md + tests/agent/test_graph.py]
- [ ] API payload tests for `business_query_answer` and safe payload filtering. [VERIFIED: src/api/routers/agent_runs.py + tests/test_agent_runs_api.py]
- [ ] Frontend Timeline/Details tests for result kinds and no raw payload rendering. [VERIFIED: frontend tests + 62-UI-SPEC.md]
- [ ] Phase 62 golden/eval cases and runner updates or a new script. [VERIFIED: evaluation/golden/phase61_ux_cases.jsonl + scripts/eval_phase61_ux.py]

## Security Domain

`.planning/config.json` does not disable `security_enforcement`, so security domain coverage is required. [VERIFIED: .planning/config.json]

### Applicable ASVS Categories

OWASP ASVS 5.0.0 is the current stable ASVS version as of the official OWASP downloads/GitHub sources checked in this session. [CITED: https://owasp.org/www-project-application-security-verification-standard/ + https://github.com/OWASP/ASVS]

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Preserve existing authenticated Agent Runs/JWT flow; do not grant query authority from user text or LLM output. [VERIFIED: src/auth/jwt.py + docs/contract-spec.md] |
| V3 Session Management | yes | Same-thread `last_query_spec` / answer context must remain scoped to trusted session/thread/user/tenant and must not bleed across runs. [VERIFIED: docs/contract-spec.md + 62-CONTEXT.md] |
| V4 Access Control | yes | Use TrustedContext, ToolPolicy, merchant scope, and BusinessFactService scope checks before existence disclosure. [CITED: docs/contract-spec.md] |
| V5 Input Validation | yes | Use Pydantic strict schemas, descriptor allowlists, bounded limits, cursor validation, and field allowlists. [VERIFIED: Context7 `/pydantic/pydantic` + 62-CONTEXT.md] |
| V6 Cryptography | no new crypto | Do not introduce custom cryptography; existing token/secret handling remains outside Phase 62 except permission mapping compatibility. [ASSUMED] |
| V7 Error Handling and Logging | yes | Error/denied/empty payloads must use safe reason codes and avoid stack traces/raw IDs in UI or prompt payloads. [VERIFIED: 62-UI-SPEC.md + src/api/routers/agent_runs.py] |
| V10 Malicious Code / Injection | yes | No raw SQL, no arbitrary filters, no raw cursor tokens, and no frontend JSON viewer for business rows. [VERIFIED: .planning/REQUIREMENTS.md + 62-UI-SPEC.md] |

### Known Threat Patterns for Business Query

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection or filter injection through natural language | Tampering | Descriptor-to-SQLAlchemy compiler with Pydantic strict filters and no raw SQL strings. [VERIFIED: .planning/REQUIREMENTS.md + Context7 SQLAlchemy docs] |
| IDOR / merchant-scope bypass | Elevation of Privilege / Information Disclosure | TrustedContext-derived ToolCallContext, permission mapping, and BusinessFactService scope gates before fetching/revealing existence. [CITED: docs/contract-spec.md] |
| No-existence-leak failure in detail/list | Information Disclosure | Return the same safe denied/empty response for unauthorized merchant/resource/id inputs. [VERIFIED: 62-CONTEXT.md + docs/contract-spec.md] |
| Prompt payload leakage | Information Disclosure | Prompt-safe projection with field allowlists, max payloads, redaction, and no raw rows. [VERIFIED: 62-CONTEXT.md + 62-UI-SPEC.md] |
| Frontend raw payload rendering | Information Disclosure | Render only backend-projected UI-safe `business_query` fields; no raw JSON/details viewer. [VERIFIED: 62-UI-SPEC.md] |
| Cross-thread drilldown bleed | Information Disclosure / Spoofing | Same-thread state loading plus trusted session/thread/run checks; revalidate every derived query. [VERIFIED: docs/contract-spec.md + 62-CONTEXT.md] |
| Tool planner allowlist mismatch | Tampering / Denial of Service | Add parity/derivation tests between ToolCatalog visibility and investigate allowed tools. [VERIFIED: .planning/ARCHITECTURE-DEBT.md] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/62-business-query-and-drilldown-foundation/62-CONTEXT.md` - locked user decisions, deferrals, source anchors, required drilldown flow. [VERIFIED: file read]
- `.planning/ROADMAP.md` - Phase 62 goal, five-plan split, success criteria, dependency on Phase 61. [VERIFIED: file read]
- `.planning/STATE.md` - current focus and registration status for Phases 62-66. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` - completed v2.2 requirements, future analytics items, and explicit out-of-scope boundaries. [VERIFIED: file read]
- `.planning/ARCHITECTURE-DEBT.md` - Phase 61 metric compromises and Phase 62-66 hardcoding coverage matrix. [VERIFIED: codebase grep/file read]
- `docs/contract-spec.md` - TrustedContext, ToolPlatform, BusinessFactService, KnowledgeService, replay, action/approval, and metric tool contract boundaries. [CITED: docs/contract-spec.md]
- `docs/architecture-overview.md` - subsystem ownership, ToolPlatform/BusinessFactService boundaries, and code-controlled safety constraints. [CITED: docs/architecture-overview.md]
- `docs/current-langgraph-architecture.md` - canonical 15-node graph and routing responsibilities. [CITED: docs/current-langgraph-architecture.md]
- Source anchors: `src/agent/schemas.py`, `src/agent/routing.py`, `src/agent/intent_policy.py`, `src/agent/nodes/contextual_intent_resolve.py`, `src/agent/nodes/slot_resolution_gate.py`, `src/agent/nodes/investigate.py`, `src/agent/nodes/final_response.py`, `src/business/schemas.py`, `src/business/service.py`, `src/tools/catalog.py`, `src/tools/contracts.py`, `src/tools/projection.py`, `src/api/routers/agent_runs.py`, `frontend/src/types/events.ts`, `frontend/src/components/timeline/TimelineStep.tsx`, `frontend/src/components/details/DetailsPanel.tsx`. [VERIFIED: codebase grep/file reads]
- `.planning/phases/62-business-query-and-drilldown-foundation/62-UI-SPEC.md` - typed `business_query_answer` UI contract and console constraints. [VERIFIED: file read]
- Context7 library docs: `/pydantic/pydantic`, `/websites/sqlalchemy_en_20`, `/websites/langchain_oss_python_langgraph`. [VERIFIED: Context7 CLI]
- Local environment probes: Python/uv/package versions, npm package tree, Docker containers, launchctl/pm2 scan, host `psql` absence. [VERIFIED: terminal probes]

### Secondary (MEDIUM confidence)

- OWASP ASVS official project page and GitHub repository for current ASVS 5.0.0 reference and category framing. [CITED: https://owasp.org/www-project-application-security-verification-standard/ + https://github.com/OWASP/ASVS]

### Tertiary (LOW confidence)

- None used as authoritative implementation guidance. [VERIFIED: research process]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - versions were verified from local environment, PyPI/npm registries, and project manifests; recommendation is to stay on existing stack. [VERIFIED: local probes + PyPI/npm + pyproject.toml + frontend/package.json]
- Architecture: HIGH - ownership boundaries are locked by user decisions and accepted contract docs, and current source anchors were inspected. [VERIFIED: 62-CONTEXT.md + docs/contract-spec.md + codebase grep]
- Pitfalls: HIGH for branch-drift/no-leak/tool-allowlist/UI payload risks, because they are visible in current code and architecture debt; MEDIUM for exact future warning signs. [VERIFIED: .planning/ARCHITECTURE-DEBT.md + codebase grep]
- Runtime state: MEDIUM - source and running containers prove likely persisted old strings, but direct DB row counts were not available because host `psql`/`pg_isready` were missing. [VERIFIED: docker ps + source model grep + environment probe]
- UI: HIGH for typed payload requirements from Phase 62 UI spec; MEDIUM for final component structure because exact frontend implementation remains planner discretion. [VERIFIED: 62-UI-SPEC.md + frontend source]

**Research date:** 2026-07-09
**Valid until:** 2026-07-16 for fast-moving framework versions; architecture/codebase findings remain valid until Phase 62 implementation changes these files. [ASSUMED]
