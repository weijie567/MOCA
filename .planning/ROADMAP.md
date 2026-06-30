# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19. Full archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- [x] **v1.6 RAG Reranker + Query Rewrite** - Shipped on 2026-06-20. Full archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- [x] **v1.7 Short-term Memory Unification** - Shipped on 2026-06-20. Goal: complete the short-term memory chain for the current Agent Console `/api/v1/agent-runs + SSE` path.
- [x] **v1.8 Intent Routing Safety Hardening** - Shipped on 2026-06-21. Goal: harden ordinary-chat intent/routing traceability, risk tiering, workflow-state-first routing, and slot invalidation.
- [x] **v1.9 Agent Platform Foundation** - Shipped on 2026-06-30. Full archive: [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md). Audit: [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md).
- [ ] **v2.0 Merchant Scope Hardening** - Active. Goal: harden merchant-bound role semantics at database, migration, and authorization-readiness boundaries without widening run/trace/replay visibility.

## Phases

### Phase 36: Merchant-scope DB Hardening / Role Cleanup

**Status:** In progress — 3/6 plans complete
**Milestone:** v2.0 Merchant Scope Hardening
**Goal:** Convert v1.9 runtime merchant-bound role semantics into database, migration, and readiness facts without opening new run/status/evidence/trace/replay visibility.
**Requirements:** MSH-01, MSH-02, MSH-03, MSH-04, MSH-05, MSH-06, MSH-07, MSH-08
**Depends on:** v1.9 MER-01 runtime-scope closure, Phase 34 approval/action binding, Phase 35 owner/admin-only trace/replay hardening
**Plans:** 6 plans

**Success Criteria**:

1. Legacy `merchant` role is preserved only as deprecated compatibility and cannot become platform-wide or tenant-wide business-data authority.
2. Active merchant-bound business users have valid merchant binding or fail closed with explicit migration/preflight handling.
3. Username identity has tenant-scoped uniqueness or an explicit transitional tenant-resolution contract with tests preventing same-tenant duplicate principal ambiguity.
4. `AgentRun` has an unambiguous target merchant binding model and scope classification for business, policy-only / merchant-not-required, and unknown legacy runs.
5. Approval request, action draft, and safety snapshot target merchant bindings cannot contradict linked business-scoped run binding.
6. Migration/backfill gates reject unsafe null, duplicate, contradictory, or ambiguous data instead of guessing merchant scope.
7. Existing business-data runtime behavior remains unchanged: BusinessFactService authority, tenant public policy retrieval, memory contextual-only boundaries, RAG/claim boundaries, Phase 34 approval access, and owner/admin-only run/trace/replay access continue to pass.
8. Phase 36 emits one readiness conclusion for later Phase 37: `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`.

Plans:
- [x] 36-01-PLAN.md — Role registry and active business-user binding hardening
- [x] 36-02-PLAN.md — Tenant-aware username identity and auth resolution contract
- [x] 36-03-PLAN.md — AgentRun target merchant scope model and runtime persistence
- [ ] 36-04-PLAN.md — Approval/action/snapshot target merchant consistency
- [ ] 36-05-PLAN.md — Alembic migration, preflight, backfill, and downgrade gates
- [ ] 36-06-PLAN.md — Readiness artifact and final no-widening validation

## Requirement Coverage

| Requirement | Phase | Coverage |
|-------------|-------|----------|
| MSH-01 | Phase 36 | Legacy `merchant` role deprecation and role registry hardening |
| MSH-02 | Phase 36 | Active business-user merchant binding and invalid legacy fail-closed behavior |
| MSH-03 | Phase 36 | Tenant-scoped username identity or transitional tenant-resolution contract |
| MSH-04 | Phase 36 | `AgentRun` target merchant binding and scope classification |
| MSH-05 | Phase 36 | Cross-table target merchant consistency for authorization/audit roots |
| MSH-06 | Phase 36 | Migration/backfill preflight, idempotence, and no-guess classification |
| MSH-07 | Phase 36 | No regression for v1.9 runtime boundaries and owner/admin-only trace/replay access |
| MSH-08 | Phase 36 | Trace/replay authorization readiness conclusion for future Phase 37 |

## Future / Conditional Work

- **Phase 37 candidate: Same-merchant trace/replay authorization expansion** - only after Phase 36 proves trusted run-level merchant binding or explicitly reports an acceptable derived-ref readiness path. Scope should exclude live stream execution by default.
- **RLS hardening candidate** - PostgreSQL Row Level Security remains deferred until schema facts and local test harness are stable.

## Backlog

### Phase 999.1: Evaluate mem0 Memory Backend Spike (BACKLOG)

**Status:** Backlog
**Goal:** Spike whether mem0 can serve as an optional backend behind `MemoryContextService` for reviewed long-term/case memory only.
**Requirements:** TBD
**Plans:** 0 plans

**Success Criteria**:

1. Evaluation treats mem0 only as a backend candidate behind a MOCA adapter; agents must not call mem0 directly.
2. mem0 is not used for session context and must not become evidence, business fact, approval/action, material-claim, or replay authority.
3. Adapter design requires tenant, merchant, user, thread, and case filters derived from trusted MOCA context before any read/write.
4. Writes must pass through `MemoryWriteDecisionV2`; retrieved items must be projected as `ReviewedMemoryRef(authority_class="contextual_only")`.
