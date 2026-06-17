# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [ ] **v1.2 Long-term / Case Memory** - Active. Defined on 2026-06-17. Scope: Phase 16.

## Phases

<details>
<summary>v1.0 MVP (Phases 1-6) - SHIPPED 2026-05-22</summary>

- [x] Phase 1: Foundation
- [x] Phase 2: RAG Pipeline
- [x] Phase 3: LangGraph Core
- [x] Phase 4: Approval Workflow & Audit
- [x] Phase 5: Frontend & SSE
- [x] Phase 6: Evaluation & Polish

</details>

<details>
<summary>v1.1 Agent Architecture Migration (Phases 7-15.2) - SHIPPED 2026-06-17</summary>

- [x] Phase 7: Contract Baseline
- [x] Phase 8: Knowledge Facade
- [x] Phase 9: Business Tool Facade
- [x] Phase 10: State Lifecycle + Routing Migration
- [x] Phase 11: Intent / Clarification
- [x] Phase 12: Session Memory
- [x] Phase 13: Approval State Machine
- [x] Phase 14: Demo Action Executor Boundary
- [x] Phase 15: Replay Event Contract
- [x] Phase 15.1: Memory Foundation V2
- [x] Phase 15.2: v1.1 Readiness Closure

</details>

## Active Milestone: v1.2 Long-term / Case Memory

### Phase 16: Long-term / Case Memory

**Status:** In Progress — 4/9 plans complete

**Plans:** 4 summaries / 9 plan files in `.planning/phases/16-long-term-case-memory/` (`16-01` through `16-04` complete; `16-05` through `16-09` pending)

**Goal:** Implement reviewed long-term profile memory and reviewed case memory retrieval on top of the v1.1 conversation/context foundation, while preserving the boundaries that memory is contextual assistance only.

**Requirements:** `MEMID-01`, `MEMSCHEMA-01`, `LONGMEM-01`, `LONGMEM-02`, `LONGMEM-03`, `CASEMEM-01`, `CASEMEM-02`, `CASEMEM-03`, `TOMBSTONE-01`, `TOMBSTONE-02`, `MEMCTX-01`, `MEMCTX-02`, `MEMREVIEW-01`, `MEMEVAL-01`

**Success criteria:**

- `memory_identity.v1` has golden tests for canonical normalization and hash behavior.
- Long-term memory writes are reviewed/deterministic and retrieval excludes rejected, deleted, tombstoned, prohibited, superseded, stale, or out-of-scope records.
- Case memory stores reviewed precedents and retrieval is separate from session memory, long-term memory, policy evidence, and current business facts.
- Tombstones prevent immediate retrieval and block delayed/asynchronous rewrites in the same transaction.
- `ContextAssembler` can include bounded memory snippets without raw payload leakage or authority escalation.
- Tests prove memory cannot act as `EvidenceRefV1`, approval evidence, action authorization, current business truth, or replay/audit truth.
- Transitional `search_case_memory` behavior is renamed, quarantined, or backed by the new reviewed case memory store.

**Planning prerequisites:**

- Read `docs/contract-spec.md` Section 20 memory contracts.
- Read `docs/phase-13-17-architecture-plan.md` Phase 16 scope.
- Read `docs/current-implementation-map.md` memory-related current-state notes.
- Include migration rollback and downgrade preflight strategy for new schema.
- Include coverage for tombstone no-rewrite and separate-session concurrency risks where relevant.

## Deferred Beyond v1.2

- **Phase 17: External Action Execution** - external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback.
- **Memory UX** - full user/admin memory management UI.
- **Memory retrieval quality expansion** - broader vector retrieval/reranking after lifecycle safety passes.

## Current Status

v1.2 Phase 16 is in progress. Plans `16-01-memory-identity`, `16-02-schema-migration`, `16-03-long-term-memory-service`, and `16-04-semantic-episode` are complete; 5 Phase 16 plans remain.

## Next Step

Continue with `.planning/phases/16-long-term-case-memory/16-05-tombstone-supersede-PLAN.md`.

---
*Updated: 2026-06-17 - Phase 16 Plan 04 complete.*
