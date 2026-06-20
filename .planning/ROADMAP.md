# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19. Full archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- [x] **v1.6 RAG Reranker + Query Rewrite** - Shipped on 2026-06-20. Full archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- [ ] **v1.7 Short-term Memory Unification** - Current milestone. Goal: complete the short-term memory chain for the current Agent Console `/api/v1/agent-runs + SSE` path.

## Phases

<details>
<summary>Shipped phases through v1.6</summary>

- v1.0 MVP: Phases 1-6
- v1.1 Agent Architecture Migration: Phases 7-15.2
- v1.2 Long-term / Case Memory: Phase 16
- v1.3 RAG Hybrid Retrieval: Phase 20
- v1.4 RAG Production Ingestion + OCR: Phase 21
- v1.5 RAG Context Builder + Hallucination Control: Phase 22
- v1.6 RAG Reranker + Query Rewrite: Phase 23

</details>

### Phase 24: Agent Runs Short-term Memory Parity

**Status:** Planned  
**Milestone:** v1.7 Short-term Memory Unification  
**Requirements:** STM-01, STM-02, STM-03, STM-04, STM-05, STM-06, STM-07, STM-08, STM-09, STM-10, STM-11, STM-12, STM-13, STM-14
**Plans:** 9 plans

**Goal:** Make the current `/api/v1/agent-runs + SSE` path persist and consume the same short-term memory surfaces expected by Agent Console follow-up turns: conversation messages, prompt-safe tool summaries, rolling thread summaries, and PostgreSQL-backed session slots.

**Success criteria:**

1. `/api/v1/agent-runs` creates or resolves a conversation thread, persists exactly one user message per submitted query, and passes trusted conversation identifiers into graph execution.
2. Completed runs persist exactly one assistant message and update the rolling thread summary from committed messages and eligible prompt-safe tool summaries.
3. Follow-up runs can load recent messages, latest prior rolling summary, prompt-safe tool summaries, and session slot memory into prompt context.
4. Explicit current-turn slots override inherited trusted session slots, and stale or scope-mismatched inherited memory fails closed.
5. Error, cancelled, approval-interrupted, retried, and re-opened stream states are idempotent and do not produce false completed summaries or duplicated records.
6. Memory surfaces remain contextual only and cannot satisfy policy evidence, current business fact, approval/action authority, or replay/audit truth.
7. Regression tests and an integration or live smoke flow prove a three-turn Agent Console conversation can use both slot continuity and rolling-summary context.

Plans:
- [ ] 24-01-PLAN.md — Wave 0 API/SSE RED scaffolding for create, config, finalizer, retry, and smoke behavior
- [ ] 24-02-PLAN.md — Wave 0 prompt context, session slot, prompt-safety, and authority-boundary RED scaffolding
- [ ] 24-03-PLAN.md — DB-backed idempotency indexes and blocking Alembic verification
- [ ] 24-04-PLAN.md — Shared conversation and rolling-summary idempotency helpers
- [ ] 24-05-PLAN.md — `/agent-runs` user-message creation and trusted SSE graph config
- [ ] 24-06-PLAN.md — Completed-run assistant, summary, and bounded session-memory finalizer
- [ ] 24-07-PLAN.md — Error/cancel/interruption and retry/reopen completed-only safeguards
- [ ] 24-08-PLAN.md — Prompt-context parity and memory authority-boundary protections
- [ ] 24-09-PLAN.md — Legacy compatibility, focused regression, and three-turn smoke

## Current Status

v1.7 is active and ready for Phase 24 discussion/planning. `.planning/REQUIREMENTS.md` defines the short-term memory parity requirements.

## Requirement Coverage

| Requirement | Phase | Coverage |
|-------------|-------|----------|
| STM-01 | Phase 24 | Agent runs user-message persistence |
| STM-02 | Phase 24 | Conversation identifiers in graph config |
| STM-03 | Phase 24 | Assistant-message persistence |
| STM-04 | Phase 24 | Rolling-summary update |
| STM-05 | Phase 24 | Prompt-context loading |
| STM-06 | Phase 24 | Session slot continuity and override |
| STM-07 | Phase 24 | Prompt-safe tool summary constraints |
| STM-08 | Phase 24 | Legacy chat compatibility |
| STM-09 | Phase 24 | Error/cancel/interruption semantics |
| STM-10 | Phase 24 | SSE retry idempotency |
| STM-11 | Phase 24 | Ordered memory persistence stages |
| STM-12 | Phase 24 | Authority boundary preservation |
| STM-13 | Phase 24 | Regression coverage |
| STM-14 | Phase 24 | Three-turn smoke verification |

## Last Closeout

v1.6 final closeout is recorded in `.planning/FINAL-CLOSEOUT.md` and archived milestone files.

## Deferred Work

- **17-prep: AgentState Surface Contracts + Authority Isolation** - preserved as `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md`; future candidate only if Phase 17 is reintroduced.
- **Phase 17: External Action Execution** - not active. Possible future scope: external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards, and real side effects.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback and precedence merge.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if PostgreSQL hybrid no longer fits.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source document viewer, and admin review workflow.

## Next Step

Run `$gsd-discuss-phase 24` to lock gray-area decisions, then `$gsd-plan-phase 24` to produce the implementation plan.

---
*Updated: 2026-06-20 when v1.7 roadmap was created.*
