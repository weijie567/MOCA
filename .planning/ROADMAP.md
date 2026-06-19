# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)

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

<details>
<summary>v1.2 Long-term / Case Memory (Phase 16) - SHIPPED 2026-06-17</summary>

- [x] Phase 16: Long-term / Case Memory - 9/9 plans complete; verification passed.
- Delivered reviewed long-term profile memory and reviewed case memory retrieval on top of the v1.1 conversation/context foundation.
- Preserved the boundary that memory is contextual assistance only and cannot become policy evidence, approval/action authority, current business fact, or replay/audit truth.

</details>

<details>
<summary>v1.3 RAG Hybrid Retrieval (Phase 20) - SHIPPED 2026-06-18</summary>

- [x] Phase 20: RAG Hybrid Retrieval - 1/1 plan complete; UAT passed 7/7; security verified with `threats_open: 0`; archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

</details>

<details>
<summary>v1.4 RAG Production Ingestion + OCR (Phase 21) - SHIPPED 2026-06-19</summary>

- [x] Phase 21: RAG Production Ingestion + OCR - 9/9 plans complete; accepted; security verified; archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- Delivered parser/OCR ingestion and source-block provenance for PDF, DOCX, image, scanned-PDF, Markdown, and plain-text policy sources while preserving v1.3 evidence and retrieval contracts.
- Final gate: `1136 passed, 9 warnings`; live migration + OCR gate: `28 passed, 4 warnings`; milestone audit: 26/26 requirements satisfied.

</details>

## Coverage

- v1.4 requirements archived: 26/26
- Active roadmap phases: 0
- Orphaned requirements: 0
- Duplicate phase mappings: 0

## Deferred Work

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

v1.4 RAG Production Ingestion + OCR is shipped and archived. The project is between active milestones; start the next milestone with fresh requirements.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 21. RAG Production Ingestion + OCR | v1.4 | 9/9 | Shipped; archived | 2026-06-19 |

## Next Step

Run `$gsd-new-milestone` to select and scope the next milestone.

---
*Updated: 2026-06-19 - v1.4 shipped and archived.*
