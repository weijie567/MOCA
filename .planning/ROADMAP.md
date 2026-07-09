# Roadmap: MOCA

## Milestones

- ✅ **v2.1 Core Subsystem Hardening** — Phases 37-60 plus inserted Phase 48.1 (shipped 2026-07-08). Archive: `.planning/milestones/v2.1-ROADMAP.md`
- ✅ **v2.0 Merchant Scope Hardening** — Phase 36 (shipped 2026-06-30). Archive: `.planning/milestones/v2.0-ROADMAP.md`
- ✅ **v1.9 Agent Platform Foundation** — Phases 26-35.1 (shipped 2026-06-30). Archive: `.planning/milestones/v1.9-ROADMAP.md`
- ✅ **v1.8 Intent Routing Safety Hardening** — Phase 25 (shipped 2026-06-21). Archive: `.planning/milestones/v1.8-phases/`
- ✅ Earlier milestones v1.0-v1.7 — archived under `.planning/milestones/`

## Current Planning State

**Active milestone:** v2.2 Product Experience Fixes
**Status:** Phase 61 complete
**Scope:** Fix concrete Agent Console and agent-response UX pain points without weakening the v2.1 safety, evidence, tool, memory, or approval contracts.

## Current Milestone: v2.2 Product Experience Fixes

**Goal:** Fix concrete user-facing experience problems in the Agent Console while preserving the v2.1 subsystem boundaries.

**Requirements:** `.planning/REQUIREMENTS.md` — 18 requirements, all mapped.

### Phase 61: Product Experience Fixes

**Goal:** Fix the concrete Agent Console UX pain points currently known: misleading direct responses, unsupported/clarification wording, scoped business metric questions, timeline presentation, and regression coverage.
**Requirements**: UX-01, UX-02, UX-03, UX-04, MET-01, MET-02, MET-03, MET-04, SCOPE-01, SCOPE-02, SCOPE-03, SCOPE-04, CONSOLE-01, CONSOLE-02, CONSOLE-03, EVAL-01, EVAL-02, EVAL-03
**Depends on:** Phase 60
**Plans:** 5 plans

**Success criteria:**
1. Existing small-talk fix remains covered by regression tests and still never claims policy/RAG evidence or enters business investigation.
2. Unsupported and clarification responses explain the capability boundary, required input, and accepted filters without misleading the user.
3. `business_metric_query` is modeled as one generic metric intent with metric/resource/filter slots, not one intent per metric.
4. Supported MVP metrics include order count, refund count, pending ticket count, coupon issuance count, and merchant refund rate.
5. Metric tools are read-only ToolPlatform declarations backed by trusted tenant and merchant-scope filters, never LLM-generated SQL.
6. Support, manager, and admin metric visibility is enforced from trusted role and merchant scope only.
7. Metric final responses include the number/rate plus scope, filters, and freshness.
8. Agent Console timeline and response surfaces distinguish direct-response, clarification, unsupported, metric, RAG, and tool-call outcomes.
9. Known bad prompts and role/scope metric cases are captured in repeatable UX regression coverage and local validation docs.

Plans:
- [x] 61-01 Agent Response UX Baseline — deterministic small talk, unsupported/clarification wording, and no-false-evidence response baseline.
- [x] 61-02 Metric Contract, Intent, Slots, And Clarification — one generic `business_metric_query` contract with time/metric/scope slots.
- [x] 61-03 Scoped Metric Runtime — read-only `query_business_metric` ToolPlatform integration backed by BusinessFactService and trusted scope.
- [x] 61-04 Agent Graph Metric Integration — route complete metric queries through investigate/tool/final_response and project safe SSE metadata.
- [x] 61-05 Console UX And Regression Validation — timeline polish, Phase 61 golden set, Playwright E2E, and local validation records.

## Last Completed Milestone: v2.1 Core Subsystem Hardening

**Status:** shipped 2026-07-08
**Scope:** Phases 37-60 plus inserted Phase 48.1
**Plans:** 87/87 complete
**Requirements:** 24/24 complete
**Audit:** `.planning/milestones/v2.1-MILESTONE-AUDIT.md` — `passed` / `archive_ready`

**Delivered:**

- Consolidated ToolPlatform declarations, runtime output-schema validation, failure handling, policy gates, and legacy manager cleanup.
- Decoupled intent recognition and preserved multi-intent utterances through bounded `TaskPlan` semantics without weakening the single-intent route contract.
- Rebuilt memory layering around Case Working Context, thread-case M:N linkage, session-context boundaries, reviewed case precedent generation, explicit preference-only long-term memory, and memory compatibility cleanup.
- Migrated `investigate` to a bounded read-only ReAct loop and completed the canonical 15-node Agent Graph cutover with legacy runtime route/name cleanup.
- Aligned recommendation/RAG claim fail-closed behavior, canonical `risk_gate`/`approval_gate` behavior, and approval-resume terminal memory finalization.
- Closed archive evidence gaps with formal verification, Nyquist validation, UAT, security signoff, and a passed v2.1 milestone audit.

**Accepted follow-ups:**

- Phase 49 bounded ReAct replay parent-operation identity remains an accepted limitation for a future replay/event hardening milestone if needed.
- Historical legacy graph-name references remain accepted only as historical/test/documentation refs after Phase 58 cleanup.
- Legacy `/api/v1/agent/chat` background `memory_write` compatibility remains outside the current `agent-runs` frontend lifecycle.
- GSD tooling/reporting debt: `gsd-sdk query init.milestone-op` can report missing legacy audit agents even when the main orchestrator can run `gsd-integration-checker`.

## Next

Phase 62 is complete. Next step is Phase 63 planning.

### Phase 62: Business Query And Drilldown Foundation

**Goal:** Build a safe, maintainable business-query foundation so scoped aggregate, list, detail, and follow-up drilldown questions can be added without multiplying hardcoded metric/time/status/tool/projection branches.
**Requirements**: TBD during Phase 62 planning.
**Depends on:** Phase 61
**Plans:** 7/7 plans complete

**Success criteria:**
1. Business query time, scope, operation, metric/resource, status, and parser definitions have a single source of truth for the agent/business-query path.
2. A safe `business_query` contract covers aggregate/list/detail/breakdown/compare operations with scoped filters, field allowlists, limits, cursors, sort, and no raw SQL exposure.
3. Runtime read queries are implemented behind `BusinessFactService` and trusted scope/policy gates, not by exposing generic repository list helpers.
4. Multi-turn drilldown uses structured answer context/query context instead of per-slot hardcoded follow-up branches.
5. Projection, final response, regression evals, and console UI safely handle metric/list/detail answers with bounded prompt payloads and no-existence-leak semantics.

Plans:
- [x] 62-01 Query Foundation And Single Source Cleanup — shared time/scope resolvers, operation taxonomy, metric/resource/status/time-preset definitions, and parser consolidation.
- [x] 62-02 Safe Business Query Contract And Schema — accepted `business_query` contract, strict `BusinessQuerySpec`, result/context/cursor models, and metric compatibility mapping.
- [x] 62-03 ToolPlatform Policy And Trusted Scope Boundary — trusted permission mapping, read-only ToolCatalog descriptor, ToolPolicy denial checks, and safe executor boundary.
- [x] 62-04 Business Query Runtime Implementation — controlled aggregate/list/detail/breakdown/compare execution in `BusinessFactService` with scoped repositories and bounded pagination.
- [x] 62-05 Answer Context And Drilldown Flow — `last_query_spec`, `last_answer_context`, result cursor, expected-slot-type parser flow, and aggregate-to-list follow-up revalidation.
- [x] 62-06 Projection, Final Response, API, And Eval — safe backend projection, `business_query_answer` payload, golden/eval coverage, and raw payload stripping.
- [x] 62-07 Agent Console Business Query UI — typed Timeline/Details rendering, operation-specific result display, frontend unit/build checks, and E2E phase gate.

### Phase 63: Safety Taxonomy And Risk Vocabulary

**Goal:** Unify action classification and risk vocabulary across `risk_gate`, `action_draft`, and `intent_policy` so safety routing and execution-side action handling cannot drift.
**Requirements**: TBD during Phase 63 planning.
**Depends on:** Phase 62
**Plans:** 0 plans

**Success criteria:**
1. `canonical_action_type` and action keyword taxonomy have one owner shared by risk, action draft, and intent policy code.
2. Risk severity and risk disposition are modeled separately instead of overloading one string field.
3. Safety-critical route checks and action execution checks use the same taxonomy and are covered by parity tests.

Plans:
- [ ] TBD (run /gsd-plan-phase 63 to break down)

### Phase 64: RAG Risk Label Unification

**Goal:** Unify RAG risk labels across context builder, metrics, verifier, semantic routing, and tests so labels such as `manual_review_sensitive`, `conflict`, and `stale_evidence` keep the same meaning across the RAG pipeline.
**Requirements**: TBD during Phase 64 planning.
**Depends on:** Phase 63
**Plans:** 0 plans

**Success criteria:**
1. RAG risk labels have a single source of truth consumed by builder, metrics, verifier, and routing.
2. Existing labels keep compatible semantics or receive an explicit migration note.
3. Parity tests prevent future label-set drift.

Plans:
- [ ] TBD (run /gsd-plan-phase 64 to break down)

### Phase 65: Trace Event And Console Label Consistency

**Goal:** Add consistency checks and registry boundaries for trace event types, node labels, tool labels, safe reasons, and console display labels so new runtime concepts do not silently degrade in replay/API/frontend surfaces.
**Requirements**: TBD during Phase 65 planning.
**Depends on:** Phase 64
**Plans:** 0 plans

**Success criteria:**
1. Trace event type registration, replay validators, and DB CHECK constraints have explicit consistency tests or a documented migration workflow.
2. Node/tool/safe-reason labels have a clear backend/frontend ownership model with fallback behavior covered by tests.
3. Console Timeline/Details behavior remains stable when new tool names, node names, response kinds, or safe reasons are added.

Plans:
- [ ] TBD (run /gsd-plan-phase 65 to break down)

### Phase 66: Dev Test And Config Hygiene

**Goal:** Reduce long-term validation and environment maintenance cost by consolidating test fixtures, demo constants, local configuration defaults, and developer-environment hardcoded values that are not covered by the business-query, safety, RAG, or trace-label phases.
**Requirements**: TBD during Phase 66 planning.
**Depends on:** Phase 65
**Plans:** 0 plans

**Success criteria:**
1. Test magic dates and demo business identifiers use shared fixtures/constants where that reduces brittleness without obscuring test intent.
2. E2E and frontend tests avoid unnecessary exact backend-copy assertions while still locking user-visible behavior.
3. Local config defaults such as dev DB credentials, ports, API URLs, and investigate iteration limits have clear ownership and documented override paths.
4. Demo-only defaults such as action draft retention policy are either renamed/isolated as demo scope or documented as intentional non-production defaults.

Plans:
- [ ] TBD (run /gsd-plan-phase 66 to break down)
