# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [ ] **v1.4 RAG Production Ingestion + OCR** - Active milestone. Scope: Phase 21.

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

<details>
<summary>v1.3 RAG Hybrid Retrieval (Phase 20) - SHIPPED 2026-06-18</summary>

- [x] Phase 20: RAG Hybrid Retrieval - 1/1 plan complete; UAT passed 7/7; security verified with `threats_open: 0`; archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

</details>

### Active Milestone: v1.4 RAG Production Ingestion + OCR

- [ ] **Phase 21: RAG Production Ingestion + OCR** - Parser/OCR ingestion and source-block provenance for PDF, DOCX, image, scanned-PDF, Markdown, and plain-text policy sources while preserving v1.3 evidence and retrieval contracts.

## Phase Details

### Phase 21: RAG Production Ingestion + OCR

**Goal**: Policy maintainers can ingest real policy source files with parser/OCR traceability and source-block provenance, while users continue receiving canonical `EvidenceRefV1` policy evidence through the existing v1.3 hybrid retrieval path.

**Depends on**: Phase 20

**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, PROV-01, PROV-02, PROV-03, PROV-04, CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, OCR-01, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-01, INGEST-02, INGEST-03, INGEST-04, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04

**Success Criteria** (what must be TRUE):
  1. Maintainer can ingest Markdown/plain text, PDF, DOCX, image, and scanned-PDF policy sources through project-owned parser DTOs and receive deterministic parser/OCR status, warnings, safe failure codes, counts, timings, and version metadata.
  2. Retrieved policy evidence still uses schema-compatible `EvidenceRefV1`, canonical citation text, stable content hashes, v1.3 dense/sparse/fuzzy filters, RRF ordering, and normalized evidence confidence.
  3. Maintainer can resolve a retrieved evidence ref to tenant-scoped source-block provenance after content/hash validation, including page, bbox, table row/cell, parser metadata, and OCR confidence when that metadata exists.
  4. Table and OCR-derived chunks preserve faithful visible citation text, row/header/cell context, retrieval-only `search_text` enrichment, and deterministic low-confidence OCR quarantine or review-needed behavior.
  5. Failed parsing, OCR timeout, embedding mismatch, DB insert failure, malformed or unsafe files, business-artifact inputs, and migration downgrade/reupgrade leave prior committed policy versions, chunks, blocks, retrieval behavior, and safety boundaries intact.

**Plans**: 9 plans

Plans:
- [x] 21-00-PLAN.md — Wave 0 validation and test scaffolding
- [x] 21-01-PLAN.md — Parser contracts, source guards, and Markdown/plain-text adapters
- [x] 21-01a-PLAN.md — Source-block schema, repositories, and boundary guards
- [x] 21-02-PLAN.md — Block-aware chunking and atomic ingestion
- [x] 21-03-PLAN.md — PDF, DOCX, image OCR adapters, and runtime preflight
- [x] 21-04-PLAN.md — Verified provenance lookup and safe trace reporting
- [ ] 21-04a-PLAN.md — Phase 21 boundary regression
- [ ] 21-05-PLAN.md — Migration rollback and security closure
- [ ] 21-05a-PLAN.md — Final Phase 21 acceptance gate

**Planning prerequisites**:
- Treat research work packages 21.1-21.5 as Phase 21 implementation slices, not separate roadmap phases.
- Use the research sequence as planning input: Slice 21.1 schema/parser contract/scope guards; Slice 21.2 block-aware chunking/atomic ingestion; Slice 21.3 PDF/DOCX/image/OCR adapters; Slice 21.4 provenance lookup/trace reporting/boundary regression; Slice 21.5 acceptance/downgrade/security gate.
- Read `docs/contract-spec.md`, `docs/rag-architecture-spec.md`, current v1.3 ingestion/retrieval code, and `.planning/research/SUMMARY.md` before implementation planning.
- Define concrete OCR confidence thresholds, file-size/page/image limits, parser timeouts, SourceBox coordinate semantics, and migration downgrade strategy during Phase 21 planning.
- Preserve the explicit v1.4 boundary: do not introduce `MaterialClaim`, semantic verifier, reranker/query rewrite, cross-encoder/external rerank API, Vespa/OpenSearch, or a full external `SearchBackend`.

## Coverage

- v1.4 requirements mapped: 26/26
- Active roadmap phases: 1
- Orphaned requirements: 0
- Duplicate phase mappings: 0

## Deferred Beyond v1.4

- **Phase 17: External Action Execution** - external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards. Phase 17 remains owner-named deferred work and is not renumbered by v1.4.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback.
- **Phase 22: RAG Context Builder + Hallucination Control** - evidence re-fetch/hash validation in ContextBuilder, citation map, `MaterialClaim`, semantic support verifier, conflict/freshness routing, refusal/manual-review policy, and faithfulness/citation eval.
- **Phase 23: RAG Reranker + Query Rewrite** - query rewrite, reranker interface, optional cross-encoder/external rerank API, full ranking explanation, retrieval ablation eval, and latency budget.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if scale, latency, or ranking-profile complexity outgrows PostgreSQL hybrid.
- **Policy Source Operations** - user/admin document upload, review, lifecycle, retention, and source-document viewer/highlight UI after backend provenance is stable.
- **Policy Source Scale Workers** - asynchronous large-batch ingestion workers only when source volume or OCR latency proves synchronous/admin ingestion insufficient.
- **Memory UX** - full user/admin memory management UI.
- **Memory retrieval quality expansion** - broader vector retrieval/reranking after lifecycle safety passes.

## Current Status

v1.4 RAG Production Ingestion + OCR is active and scoped to Phase 21 only. The milestone turns v1.3 hybrid retrieval into a production ingestion foundation for PDF, DOCX, image/scanned-PDF, Markdown, and plain-text policy sources with parser/OCR traceability, durable source-block provenance, table-aware chunking, and rollback-safe ingestion. Phase 21 must preserve `PolicyKnowledgeService`, `PolicyChunk.content`, `PolicyChunk.search_text`, `EvidenceRefV1`, Tool System facts, memory boundaries, approval snapshots, and replay contracts.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 21. RAG Production Ingestion + OCR | v1.4 | 6/9 | Executing; verified provenance lookup and safe trace reporting complete | - |

## Next Step

Run `$gsd-execute-phase 21` to continue with `21-04a-PLAN.md`.

---
*Updated: 2026-06-19 - Phase 21 Plan 04 verified provenance lookup and safe trace reporting complete.*
