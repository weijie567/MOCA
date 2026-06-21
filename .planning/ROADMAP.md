# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19. Full archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- [x] **v1.6 RAG Reranker + Query Rewrite** - Shipped on 2026-06-20. Full archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- [x] **v1.7 Short-term Memory Unification** - Completed on 2026-06-20. Goal: complete the short-term memory chain for the current Agent Console `/api/v1/agent-runs + SSE` path.

## Phases

<details>
<summary>Shipped phases through v1.7</summary>

- v1.0 MVP: Phases 1-6
- v1.1 Agent Architecture Migration: Phases 7-15.2
- v1.2 Long-term / Case Memory: Phase 16
- v1.3 RAG Hybrid Retrieval: Phase 20
- v1.4 RAG Production Ingestion + OCR: Phase 21
- v1.5 RAG Context Builder + Hallucination Control: Phase 22
- v1.6 RAG Reranker + Query Rewrite: Phase 23
- v1.7 Short-term Memory Unification: Phase 24

</details>

### Phase 24: Agent Runs Short-term Memory Parity

**Status:** Complete
**Milestone:** v1.7 Short-term Memory Unification
**Requirements:** STM-01, STM-02, STM-03, STM-04, STM-05, STM-06, STM-07, STM-08, STM-09, STM-10, STM-11, STM-12, STM-13, STM-14
**Plans:** 9/9 plans complete

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
- [x] 24-01-PLAN.md — Wave 0 API/SSE RED scaffolding for create, config, finalizer, retry, and smoke behavior
- [x] 24-02-PLAN.md — Wave 0 prompt context, session slot, prompt-safety, and authority-boundary RED scaffolding
- [x] 24-03-PLAN.md — DB-backed idempotency indexes and blocking Alembic verification
- [x] 24-04-PLAN.md — Shared conversation and rolling-summary idempotency helpers
- [x] 24-05-PLAN.md — `/agent-runs` user-message creation and trusted SSE graph config
- [x] 24-06-PLAN.md — Completed-run assistant, summary, and bounded session-memory finalizer
- [x] 24-07-PLAN.md — Error/cancel/interruption and retry/reopen completed-only safeguards
- [x] 24-08-PLAN.md — Prompt-context parity and memory authority-boundary protections
- [x] 24-09-PLAN.md — Legacy compatibility, focused regression, and three-turn smoke

## Current Status

v1.7 is complete. Phase 24 delivered Agent Console `/agent-runs + SSE` short-term memory parity, including conversation persistence, rolling summaries, prompt-safe tool summaries, session slot continuity, failure/idempotency safeguards, authority-boundary regressions, and a three-turn smoke verification. Phase 24.2-24.4 follow-ups then consolidated the session memory bundle read path, memory write isolation/observability, and deterministic memory eval MVP.

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

Phase 24 final review and verification are recorded in `.planning/phases/24-agent-runs-short-term-memory-parity/24-REVIEW.md` and `.planning/phases/24-agent-runs-short-term-memory-parity/24-VERIFICATION.md`.

## Deferred Work

- **17-prep: AgentState Surface Contracts + Authority Isolation** - preserved as `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md`; future candidate only if Phase 17 is reintroduced.
- **Phase 17: External Action Execution** - not active. Possible future scope: external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards, and real side effects.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback and precedence merge.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if PostgreSQL hybrid no longer fits.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source document viewer, and admin review workflow.

### Phase 24.2: Unified Session Memory Bundle Read Path (INSERTED)

**Status:** Complete
**Goal:** Make `SessionMemoryBundle` the graph-facing session read model for rolling summary, recent messages, tool summaries, and slot continuity while preserving the existing `session_memory` slot-continuity contract.
**Requirements**: Memory consolidation follow-up
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 24.2-01-PLAN.md — Unified session memory bundle read path

### Phase 24.3: Memory Write Isolation Policy and Observability MVP (INSERTED)

**Status:** Complete
**Goal:** Extract and enforce the rule that memory side effects must not rollback or otherwise contaminate the main business transaction, and add minimal safe trace metrics for finalizer memory writes.
**Requirements**: Memory consolidation follow-up
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 24.3-01-PLAN.md — Memory write isolation policy and observability MVP

### Phase 24.4: Memory Eval MVP (INSERTED)

**Status:** Complete
**Goal:** Create a focused deterministic pytest suite that acts as MOCA's first memory quality gate for short-term recall, slot expiry, tombstone forgetting, and authority contamination.
**Requirements**: Memory consolidation follow-up
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 24.4-01-PLAN.md — Memory eval MVP

## Next Step

Start the next milestone with `$gsd-new-milestone`.

---
*Updated: 2026-06-21 after completing Phase 24.2-24.4 memory consolidation follow-ups.*
