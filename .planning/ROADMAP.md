# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19. Full archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)

## Current Roadmap Status

No active roadmap phases are defined. v1.5 has been archived; start the next milestone with `$gsd-new-milestone`.

## Progress

| Milestone | Scope | Status | Shipped |
|-----------|-------|--------|---------|
| v1.0 MVP | Phases 1-6 | Archived | 2026-05-22 |
| v1.1 Agent Architecture Migration | Phases 7-15.2 | Archived | 2026-06-17 |
| v1.2 Long-term / Case Memory | Phase 16 | Shipped | 2026-06-17 |
| v1.3 RAG Hybrid Retrieval | Phase 20 | Archived | 2026-06-18 |
| v1.4 RAG Production Ingestion + OCR | Phase 21 | Archived | 2026-06-19 |
| v1.5 RAG Context Builder + Hallucination Control | Phase 22 | Archived | 2026-06-19 |

## Deferred Work

These items are intentionally outside the active roadmap until a future milestone adopts them.

- **17-prep: AgentState Surface Contracts + Authority Isolation** - pending cleanup todo before Phase 17 external action execution.
- **Phase 17: External Action Execution** - external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback and precedence merge.
- **Phase 23: RAG Reranker + Query Rewrite** - query rewrite, reranker interface, optional cross-encoder/external rerank API, ranking explanations, retrieval ablation eval, and latency budget.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if PostgreSQL hybrid no longer fits.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source document viewer, and admin review workflow.
- **Phase 22 Stretch Only** - bounded automatic regeneration attempt, persisted claim dependency map, maintainer verifier trace report, and granular policy claim subtypes.

## Current Status

v1.5 RAG Context Builder + Hallucination Control is complete and archived. The milestone audit found no blockers and recorded only non-blocking tech debt.

## Next Step

Run `$gsd-new-milestone` to define the next milestone's requirements and roadmap.

---
*Updated: 2026-06-19 after v1.5 milestone archive.*
