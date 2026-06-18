# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [ ] **v1.3 RAG Hybrid Retrieval** - Active. Scope: Phase 20.

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

## Completed Milestone: v1.2 Long-term / Case Memory

### Phase 16: Long-term / Case Memory

**Status:** Complete — 9/9 plans executed; verification passed

**Plans:** 9/9 plans complete

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

## Current Milestone: v1.3 RAG Hybrid Retrieval

### Phase 20: RAG Hybrid Retrieval

**Status:** Complete — 1/1 plan executed; verification pending

**Goal:** Upgrade MOCA's current pgvector-only policy retrieval path into a minimal production hybrid retrieval backend using PostgreSQL + pgvector + PostgreSQL full-text + pg_trgm, while preserving `PolicyKnowledgeService`, `EvidenceRefV1`, existing citation identity, and the Tool System boundary for business facts.

**Requirements:** `RAGHYB-01`, `RAGHYB-02`, `RAGTOK-01`, `RAGTOK-02`, `RAGRET-01`, `RAGRET-02`, `RAGRET-03`, `RAGSCOPE-01`, `RAGSCOPE-02`, `RAGTRACE-01`, `RAGEVAL-01`

**Success criteria:**

- `PolicyChunk` has retrieval-ready `search_text` / `search_vector` support and indexes for full-text and pg_trgm search.
- Chinese tokenizer and domain dictionary produce stable query/content search terms without mutating citation text.
- Retrieval combines dense, sparse, and fuzzy candidates through RRF.
- Tenant/effective-date/scope filters apply before each retrieval channel contributes candidates.
- `PolicyKnowledgeService` and canonical `EvidenceRefV1` behavior remain compatible with existing Agent, approval, snapshot, and replay consumers.
- Minimal retrieval trace is available for eval/debug and does not enter prompts.
- Focused tests and eval cover tokenizer, sparse/fuzzy search, RRF ordering, scope filtering, effective-date filtering, Hit@5, and fallback accuracy.

**Planning prerequisites:**

- Read `docs/rag-architecture-spec.md` sections 2, 8, 9, 14, 15, and 16.
- Read `docs/contract-spec.md` §8.3, especially canonical `EvidenceRefV1` and citation membership semantics.
- Read `src/knowledge/retrieval.py`, `src/knowledge/service.py`, `src/repositories/policy_chunk_repo.py`, `src/rag/ingestion.py`, `src/rag/chunker.py`, `src/db/models.py`, and `src/db/migrations/versions/002_rag_pipeline.py`.
- Do not implement OCR, `DocumentBlock`, `MaterialClaim`, semantic verifier, Vespa/OpenSearch, or full external `SearchBackend` in Phase 20.

## Deferred Beyond v1.3

- **Phase 17: External Action Execution** - external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards. Phase 17 remains owner-named deferred work and is not renumbered by v1.3.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback.
- **Memory UX** - full user/admin memory management UI.
- **Memory retrieval quality expansion** - broader vector retrieval/reranking after lifecycle safety passes.

## Current Status

v1.3 Phase 20 implementation is complete and ready for GSD verification. The retrieval slice adds policy chunk `search_text` / generated `search_vector`, PostgreSQL full-text and pg_trgm retrieval channels, RRF fusion, internal hybrid trace, and focused eval diagnostics while preserving `EvidenceRefV1` and Tool System boundaries.

## Next Step

Run `$gsd-verify-work 20` for Phase 20 RAG Hybrid Retrieval, then complete the v1.3 milestone if verification passes.

---
*Updated: 2026-06-18 - Phase 20 implementation complete; verification pending.*
