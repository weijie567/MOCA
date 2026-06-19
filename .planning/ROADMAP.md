# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19. Full archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- [ ] **v1.6 RAG Reranker + Query Rewrite** - Active milestone. Scope: Phase 23 only.

## Overview

v1.6 is a one-phase retrieval-quality milestone. Phase 23 improves policy evidence recall and ranking after the v1.3 hybrid retrieval backend, v1.4 parser/OCR provenance, and v1.5 ContextBuilder/verifier kernel by adding bounded query rewrite, deterministic/default reranking, optional config-gated provider adapters, safe ranking diagnostics, retrieval ablation evals, and explicit latency budgets. The milestone must preserve all existing authority boundaries: `EvidenceRefV1` remains canonical policy evidence identity, trusted retrieval filters apply before candidates affect rank, provenance remains internal/maintainer-scoped, and reranker scores never substitute for ContextBuilder or verifier support.

Research is intentionally skipped for this milestone. Active planning uses `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, archived v1.5 owner notes, and current code/doc context during phase planning, not stale active research.

## Phases

- [ ] **Phase 23: RAG Reranker + Query Rewrite** - Improve policy retrieval recall/ranking with bounded rewrite, safe reranking, diagnostics, ablations, and latency fallback while preserving Phase 20-22 safety contracts.

## Phase Details

### Phase 23: RAG Reranker + Query Rewrite
**Goal**: Users get more relevant policy evidence for ambiguous, underspecified, and domain-synonym questions, while maintainers can evaluate and tune rewrite/rerank behavior safely; all retrieval filters, evidence identity, provenance boundaries, ContextBuilder validation, verifier authority, and action-boundary protections remain intact.
**Depends on**: Phase 22
**Requirements**: QRW-01, QRW-02, QRW-03, QRW-04, QRW-05, RRK-01, RRK-02, RRK-03, RRK-04, RRK-05, RRK-06, EXP-01, EXP-02, EXP-03, EXP-04, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, BND-01, BND-02, BND-03, BND-04, BND-05, BND-06
**Success Criteria** (what must be TRUE):
  1. Support or merchant questions with ambiguous wording, missing detail, or domain synonyms can retrieve better policy candidates through original-query plus bounded rewrite channels, while the original query and all trusted tenant/scope/effective-date filters are preserved.
  2. Specific, out-of-domain, unsafe, or insufficient-context queries skip rewrite deterministically and keep the existing safe hybrid retrieval or no-evidence behavior.
  3. Maintainers can run deterministic/default reranking without live provider credentials, and optional provider adapters are controlled by config, candidate/text budgets, timeouts, retry limits, fallback behavior, and provider/config version records.
  4. Maintainers and evals can inspect bounded ranking diagnostics showing selected channels, rewrite contribution, rerank contribution, rank changes, safe score components, and fallback reasons without leaking raw prompts, raw provider payloads, source-block internals, raw tool facts, private reasoning, or unbounded policy text.
  5. Final retrieval output still satisfies Phase 20-22 boundaries: reranking cannot mutate canonical chunk content, text hashes, policy version identity, `EvidenceRefV1` fields, ContextBuilder canonical validation, verifier support, approval snapshots, or action-draft safety.
  6. Retrieval evals compare dense-only, sparse-only, fuzzy-only, RRF baseline, rewrite-enabled, reranker-enabled, and rewrite-plus-reranker variants with blocking metrics for Hit@K, MRR or equivalent rank quality, citation-support compatibility, no-evidence precision, unsafe retrieval rate, fallback rate, and latency percentiles.
**Plans**: 6 plans

Plans:
- [x] 23-01-PLAN.md — Wave 0 RED test scaffold and static boundary updates for query rewrite, rerank, diagnostics, eval, budgets, and deferral expectations.
- [x] 23-02-PLAN.md — Query rewrite contracts, deterministic skip rules, safe summaries, and trusted-filter no-widening.
- [ ] 23-03-PLAN.md — Original-query plus rewritten-query candidate generation, channel limits, merge/dedupe, and baseline fallback.
- [ ] 23-04-PLAN.md — Project-owned reranker contract, deterministic/default local reranking, optional provider gates, and fallback diagnostics.
- [ ] 23-05-PLAN.md — Retrieval diagnostics, ablation golden cases, metrics reporting, latency budgets, and no-live-provider eval gates.
- [ ] 23-06-PLAN.md — Boundary regression closure across Phase 20 filters, Phase 21 provenance, Phase 22 verifier/action rules, deferrals, and final acceptance gates.

Suggested plan slices:

- [ ] 23-01 - Query rewrite contracts, deterministic skip rules, trusted-filter preservation, and safe rewrite trace fields.
- [ ] 23-02 - Original-query plus rewritten-query candidate generation, channel limits, merge/dedupe behavior, and baseline fallback.
- [ ] 23-03 - Project-owned reranker contract, deterministic/default local reranking, confidence/rank semantics, and safe adapter position before `EvidenceRefV1` construction.
- [ ] 23-04 - Optional provider adapter gates, timeouts/retries, redacted inputs, fallback records, score components, and maintainer/eval diagnostics.
- [ ] 23-05 - Retrieval ablation golden cases, metrics reporting, latency budget enforcement, and no-live-provider default test gates.
- [ ] 23-06 - Boundary regression closure across Phase 20 filters, Phase 21 provenance, Phase 22 ContextBuilder/verifier/action rules, Phase 17 deferrals, and RAG-5 backend deferrals.

Hard boundaries:

- No 17-prep AgentState Surface Contracts + Authority Isolation work; that todo stays deferred until before Phase 17 External Action Execution.
- No Phase 17 external action execution, outbox, reconciliation, compensation dispatch, external idempotency, or real side effects.
- No Phase RAG-5 external `SearchBackend`, Vespa/OpenSearch shadow testing, new vector database service, or backend replacement.
- No Policy Source Operations upload/review/lifecycle UI, source-document viewer, or admin source-management workflow.
- No `EvidenceRefV1` identity changes, canonical citation text mutation, `text_hash` mutation, policy version identity mutation, or source-block/OCR/provenance fields added to ordinary evidence refs.
- No reranker score or rewrite output may replace tenant/scope/effective-date/risk/doc-type filters, ContextBuilder canonical validation, verifier support, business fact authority, approval safety, or action-boundary checks.
- No raw rewrite prompts, raw provider payloads, private reasoning, parser/OCR/source-block internals, raw tool payloads, unbounded policy text, or ranking diagnostics in ordinary prompts, final responses, memory, replay payloads, approval snapshots, or action drafts.
- No Phase 24 or later phase is created in v1.6.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 23. RAG Reranker + Query Rewrite | v1.6 | 2/6 executed | In progress | - |

## Coverage

- v1.6 requirements mapped: 26/26
- Active roadmap phases: 1
- Orphaned requirements: 0
- Duplicate phase mappings: 0
- Traceability status: `.planning/REQUIREMENTS.md` already maps every active requirement to Phase 23 exactly once.

Requirement groups:

- Query Rewrite: QRW-01, QRW-02, QRW-03, QRW-04, QRW-05
- Reranker: RRK-01, RRK-02, RRK-03, RRK-04, RRK-05, RRK-06
- Explanations: EXP-01, EXP-02, EXP-03, EXP-04
- Evaluation and Latency: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05
- Boundary Preservation: BND-01, BND-02, BND-03, BND-04, BND-05, BND-06

## Deferred Work

- **17-prep: AgentState Surface Contracts + Authority Isolation** - pending cleanup todo before Phase 17 external action execution; intentionally not the next active phase.
- **Phase 17: External Action Execution** - external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards, and real side effects.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback and precedence merge.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if PostgreSQL hybrid no longer fits.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source document viewer, and admin review workflow.
- **Phase 23 Stretch Only** - live default-demo cross-encoder provider use, maintainer CLI trace reports, and eval-driven auto-tuning remain stretch unless explicitly accepted during Phase 23 planning.

## Current Status

v1.6 RAG Reranker + Query Rewrite is in execution. Phase 23 has completed 23-01 Wave 0 RED test scaffold and 23-02 query rewrite contracts/safe summaries; 4 implementation/verification plans remain.

## Next Step

Continue Phase 23 execution with 23-03 retrieval rewrite channel wiring.

---
*Updated: 2026-06-20 after v1.6 roadmap creation.*
