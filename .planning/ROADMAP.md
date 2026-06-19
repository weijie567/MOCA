# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19 as one roadmap phase: Phase 22.

## Overview

v1.5 is a one-phase milestone that inserts a bounded RAG reasoning kernel after v1.3/v1.4 retrieval and provenance work and before answer, recommendation, risk, approval, or action-draft reasoning. Phase 22 consumes already-retrieved `EvidenceRefV1` candidates and current business fact refs, builds prompt-safe context, verifies typed material claims against the correct authority sources, and routes unsupported or unsafe outcomes deterministically.

## Phases

- [x] **Phase 22: RAG Context Builder + Hallucination Control** - Build the retrieval-after/reasoning-before ContextBuilder, MaterialClaim verification, deterministic routing, and hallucination-control acceptance gate for all v1.5 requirements.

<details>
<summary>v1.0-v1.4 shipped baseline</summary>

- [x] Phase 1: Foundation
- [x] Phase 2: RAG Pipeline
- [x] Phase 3: LangGraph Core
- [x] Phase 4: Approval Workflow & Audit
- [x] Phase 5: Frontend & SSE
- [x] Phase 6: Evaluation & Polish
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
- [x] Phase 16: Long-term / Case Memory
- [x] Phase 20: RAG Hybrid Retrieval
- [x] Phase 21: RAG Production Ingestion + OCR

</details>

## Phase Details

### Phase 22: RAG Context Builder + Hallucination Control
**Goal**: Users and downstream agent nodes can rely on answers and action recommendations being grounded only in current, authorized, hash-valid, semantically supported policy evidence and current Tool System business facts, with unsupported or unsafe outcomes routed to regenerate-route, refusal/insufficient-evidence, or manual review before any action boundary can proceed.
**Depends on**: Phase 21
**Requirements**: CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06, CLM-01, CLM-02, CLM-03, CLM-04, CLM-05, VER-01, VER-02, VER-03, VER-04, VER-05, VER-06, RTE-01, RTE-02, RTE-03, RTE-04, RTE-05, BND-01, BND-02, BND-03, BND-04, BND-05, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05
**Success Criteria** (what must be TRUE):
  1. System can build a prompt-safe `RagContextBundle` or equivalent shared reasoning context from candidate evidence refs and current business refs, preserving citation maps, dedupe/merge traceability, risk labels, exclusion reasons, and budget traces while rejecting tenant/scope/hash/freshness/latest-version invalid evidence.
  2. System can represent policy, business fact, and action recommendation conclusions as typed `MaterialClaim` records and verify each claim against the correct authority source, keeping citation membership distinct from Level 2/3 semantic support.
  3. System can deterministically map unsupported, insufficient, conflicting, stale, unauthorized, scope-invalid, hash-mismatched, OCR-low-confidence, business-fact-missing, and manual-review-needed outcomes to allow, regenerate-route, refusal/insufficient-evidence, or manual review without model-chosen safety routing.
  4. System prevents non-allow verification outcomes from creating proposed actions, approval requests, action drafts, or `ActionSafetySnapshot` evidence, while still preserving existing approval/action boundaries when support passes.
  5. System passes blocking hallucination-control acceptance gates for claim support accuracy, citation support accuracy, refusal/manual-review routing, business-data hallucination, prompt/debug leakage, Level 3 trigger/timeout behavior, and fail-closed outcomes.
**Plans**: 6 plans

Plans:
- [x] 22-01-PLAN.md — Wave 0 unit scaffolding for ContextBuilder, MaterialClaim, verifier tiers, authority boundaries, and deterministic routes.
- [x] 22-02-PLAN.md — Wave 0 evidence validation, leakage, graph/action/final integration, boundary, and hallucination-eval scaffolding.
- [x] 22-03-PLAN.md — ContextBuilder, canonical evidence re-fetch, latest/current validation, citation maps, budgeting, and prompt-safe projections.
- [x] 22-04-PLAN.md — MaterialClaim contracts, Level 1/2 authority verification, and risk-triggered Level 3 semantic verifier.
- [x] 22-05-PLAN.md — Deterministic route map, recommendation/graph integration, action-boundary hardening, and safe final responses.
- [x] 22-06-PLAN.md — Hallucination-control metrics/eval gate, boundary guards, leakage closure, and final Phase 22 verification.

Suggested plan slices for Phase 22 planning (internal work-package guidance, not roadmap phases):

- 22-01: Contracts, per-turn state, route enums, authority taxonomy, and static scope guards.
- 22-02: Verified evidence lookup through `PolicyKnowledgeService`, including tenant/scope/latest-version/effective-date/freshness/hash re-fetch validation.
- 22-03: `ContextBuilder`, citation map, dedupe/adjacent merge, protected metadata budgeting, prompt/verifier/debug/final projections, and risk labels.
- 22-04: Recommendation integration so shared context replaces node-local evidence re-fetch and citation-map logic without changing retrieval ranking.
- 22-05: `MaterialClaim` generation plus deterministic Level 1 and Level 2 verification for policy, business fact, and action recommendation claims.
- 22-06: Deterministic routing, final-response wording, and action/approval boundary hardening.
- 22-07: Risk-triggered Level 3 semantic support with explicit claim/evidence/token/timeout/retry/config budgets and fail-closed behavior.
- 22-08: Hallucination-control evals, leakage tests, metrics, and final acceptance gate.

Roadmap acceptance notes:

- Latest/current policy version validity is a visible acceptance point alongside effective-date/freshness and hash re-fetch. Phase 22 must not accept an implementation that checks only effective date while ignoring latest-version or hash validity.
- `regenerate-route` is in scope as a route enum/action. Actually performing an automatic regeneration attempt is stretch scope unless separately accepted.

Hard boundaries:

- No Phase 23 query rewrite, model relevance reranking, cross-encoder reranking, external rerank API, ranking explanation, retrieval ablation, or retrieval latency tuning.
- No Phase 17 external execution, outbox, reconciliation, compensation dispatch, external idempotency worker, or real side effects.
- No RAG-5 external `SearchBackend`, Vespa/OpenSearch, new vector database, or backend replacement.
- No Policy Source Operations UI, upload/review/lifecycle workflow, source-document viewer, or admin source-management surface.
- No `EvidenceRefV1` identity changes, and no MaterialClaim, source-block, OCR, provenance, business fact, or verifier fields added to `EvidenceRefV1` or ordinary business facts.
- No source-block/OCR/parser raw metadata or verifier/debug/private reasoning leakage into ordinary prompts, final responses, memory, replay, business facts, action snapshots, or user-facing answers.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 22. RAG Context Builder + Hallucination Control | v1.5 | 6/6 | Complete | 2026-06-19 |

## Coverage

- v1.5 requirements mapped: 32/32
- Active roadmap phases: 1
- Orphaned requirements: 0
- Duplicate phase mappings: 0

## Deferred Work

- **Phase 17: External Action Execution** - external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback and precedence merge.
- **Phase 23: RAG Reranker + Query Rewrite** - query rewrite, reranker interface, optional cross-encoder/external rerank API, ranking explanations, retrieval ablation eval, and latency budget.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if PostgreSQL hybrid no longer fits.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source document viewer, and admin review workflow.
- **Phase 22 Stretch Only** - bounded automatic regeneration attempt, persisted claim dependency map, maintainer verifier trace report, and granular policy claim subtypes.

## Current Status

v1.5 RAG Context Builder + Hallucination Control completed Phase 22. Plans 22-01 through 22-06 are complete and the final automated acceptance gate passes.

## Next Step

Run `$gsd-verify-work 22` or complete the v1.5 milestone.

---
*Updated: 2026-06-19 - Plan 22-06 hallucination eval and final acceptance gate complete.*
