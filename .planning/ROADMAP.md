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

## Phases

<details>
<summary>v1.9 Agent Platform Foundation (Phases 26-35.1) - SHIPPED 2026-06-30</summary>

- [x] Phase 26: Architecture Contract Baseline (1/1 plan)
- [x] Phase 27: TrustedContextFactory and Projections (3/3 plans)
- [x] Phase 28: Decision Event Foundation (1/1 plan)
- [x] Phase 29: Tool Platform Boundary (4/4 plans)
- [x] Phase 29.5: Merchant Scope / Role Model Alignment (6/6 plans)
- [x] Phase 30: BusinessFactService Boundary (3/3 plans)
- [x] Phase 31: Memory Platform Boundary (6/6 plans)
- [x] Phase 32: Intent Graph Migration (5/5 plans)
- [x] Phase 33: RAG Context Build and Claim Verification (9/9 plans)
- [x] Phase 34: Approval and ActionDraft Boundary Hardening (6/6 plans)
- [x] Phase 35: Replay and Eval Hardening (6/6 plans)
- [x] Phase 35.1: v1.9 Milestone Readiness Closure (1/1 plan)

Full details are archived in [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md).

</details>

<details>
<summary>Shipped phases through v1.8</summary>

- v1.0 MVP: Phases 1-6
- v1.1 Agent Architecture Migration: Phases 7-15.2
- v1.2 Long-term / Case Memory: Phase 16
- v1.3 RAG Hybrid Retrieval: Phase 20
- v1.4 RAG Production Ingestion + OCR: Phase 21
- v1.5 RAG Context Builder + Hallucination Control: Phase 22
- v1.6 RAG Reranker + Query Rewrite: Phase 23
- v1.7 Short-term Memory Unification: Phase 24 and inserted memory follow-ups
- v1.8 Intent Routing Safety Hardening: Phase 25

Archived milestone details live in `.planning/milestones/`.

</details>

## Current Status

v1.9 is shipped and archived. The project is between milestones.

Next step:

```text
$gsd-new-milestone
```

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
