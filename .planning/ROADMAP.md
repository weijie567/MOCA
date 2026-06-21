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
- [ ] **v1.8 Intent Routing Safety Hardening** - Active. Goal: harden ordinary-chat intent/routing traceability, risk tiering, workflow-state-first routing, and slot invalidation.

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

v1.8 is active. Phase 25 owns production hardening for MOCA's ordinary-chat intent/routing layer: traceable raw-to-effective classification decisions, risk tiers derived from intent/operation/role/channel, workflow-state-first handling for pending clarifications, slot provenance/invalidation, and end-to-end regression coverage for route and safety outcomes.

## Requirement Coverage

| Requirement | Phase | Coverage |
|-------------|-------|----------|
| IRS-01 | Phase 25 | Classification trace exposes raw/pre-route/override/effective/risk/route |
| IRS-02 | Phase 25 | Business code consumes effective classification and route |
| IRS-03 | Phase 25 | RiskTier derives from intent, operation, role, channel, and hints |
| IRS-04 | Phase 25 | Chat approval/direct execution attempts fail closed or gate safely |
| IRS-05 | Phase 25 | Existing high-risk behavior remains backward-compatible |
| IRS-06 | Phase 25 | Active workflow state is checked before ordinary classification |
| IRS-07 | Phase 25 | Ambiguous short replies cannot approve or execute without trusted pending flow |
| IRS-08 | Phase 25 | Slot metadata records trusted provenance and scope |
| IRS-09 | Phase 25 | Slot negation/context switching invalidates inherited identifiers |
| IRS-10 | Phase 25 | Current-turn slots override memory and invalidated slots do not satisfy required slots |
| IRS-11 | Phase 25 | Golden/regression coverage verifies route, risk, clarification, and slot outcomes |
| IRS-12 | Phase 25 | Existing evidence/business fact/memory/approval/action/replay boundaries remain intact |

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

### Phase 25: Intent routing safety hardening

**Status:** Planned
**Milestone:** v1.8 Intent Routing Safety Hardening
**Goal:** Harden the ordinary-chat intent/routing contract so raw LLM classification remains advisory, deterministic policy produces effective classification/risk/route decisions, active workflow state can answer pending clarification turns before reclassification, and inherited slots can be traced and invalidated safely.
**Requirements:** IRS-01, IRS-02, IRS-03, IRS-04, IRS-05, IRS-06, IRS-07, IRS-08, IRS-09, IRS-10, IRS-11, IRS-12
**Depends on:** Phase 24
**Plans:** 1 plan

**Success criteria:**

1. Trace output clearly distinguishes raw LLM classification, deterministic pre-route, policy overrides, effective classification, risk tier, and final route.
2. Risk policy can classify read-only, draft, suggestion, approval-required, and ordinary-chat-forbidden requests from intent/operation/role/channel inputs.
3. Pending clarification state can consume short identifier replies before ordinary intent classification, while unsafe short approvals or "continue" replies fail closed.
4. Slot metadata includes trusted provenance and deterministic invalidation prevents stale order/refund/ticket identifiers from satisfying required slots.
5. Golden/focused regression tests cover effective classification, route, risk tier, clarification reason, and memory inheritance/invalidation outcomes without weakening existing authority boundaries.

Plans:
- [ ] 25-01-PLAN.md — Intent routing safety hardening

---
*Updated: 2026-06-21 after starting v1.8 Intent Routing Safety Hardening and adding Phase 25.*
