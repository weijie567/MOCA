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

Phase 61 is complete. Next step is milestone closeout or the next v2.2 follow-up phase if new scope is added.
