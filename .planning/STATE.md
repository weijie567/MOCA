---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: RAG Reranker + Query Rewrite
status: not_started
stopped_at: Roadmap created; ready to discuss or plan Phase 23
last_updated: "2026-06-20T01:37:14+08:00"
last_activity: 2026-06-20
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-20)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 23 — RAG Reranker + Query Rewrite

## Current Position

Phase: 23 (1 of 1 active phase: RAG Reranker + Query Rewrite) — NOT STARTED
Plan: —
Status: Not started; ready to discuss or plan Phase 23
Last activity: 2026-06-20 — Created v1.6 roadmap with Phase 23 as the only active phase

Progress: [----------] 0%

Planning files:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/MILESTONES.md`

## Current Milestone Context

- v1.6 owns exactly one roadmap phase: Phase 23 RAG Reranker + Query Rewrite.
- Active requirements total 26 and already map to Phase 23 exactly once in `.planning/REQUIREMENTS.md`.
- Phase 23 follows v1.3 hybrid retrieval, v1.4 parser/OCR provenance, and v1.5 ContextBuilder/hallucination-control work.
- Phase 23 may add bounded query rewrite, deterministic/default reranking, optional config-gated provider adapters, ranking diagnostics, ablation evals, and latency budgets.
- Phase 23 must preserve `EvidenceRefV1` identity, canonical citation text/text_hash, tenant/scope/effective-date filters, source-block/OCR provenance boundaries, ContextBuilder validation, verifier routing, and action-boundary safety.
- Research was intentionally skipped for v1.6; do not use stale active `.planning/research` content.
- 17-prep AgentState cleanup remains a pending todo before Phase 17 External Action Execution, not a blocker or next active phase for v1.6.

## Performance Metrics

**v1.6 velocity:** 0 phases complete, 0 plans complete.

| Phase | Plans | Status |
|-------|-------|--------|
| 23. RAG Reranker + Query Rewrite | 0/TBD | Not started |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

## Accumulated Context

### Decisions

- v1.6 starts owner-named Phase 23 retrieval-quality work and does not reset phase numbering.
- Phase 23 is the only active roadmap phase; no Phase 24+ is created for this milestone.
- 17-prep AgentState cleanup remains deferred until Phase 17 preparation.
- `EvidenceRefV1` remains canonical policy evidence identity; rewrite/rerank may reorder or expand retrieval candidates but cannot mutate evidence identity or bypass ContextBuilder/verifier authority.
- Optional live reranker providers must be config-gated, timeout-bounded, retry-bounded, and able to fall back to deterministic/default retrieval.

### Pending Todos

- [ ] 17-prep: AgentState Surface Contracts + Authority Isolation - `.planning/todos/pending/2026-06-17-constrain-agentstate-memory-expansion.md`

### Blockers / Concerns

- None for discussing or planning Phase 23.

## Deferred Items

| Category | Item | Status |
|----------|------|--------|
| todo | 17-prep AgentState Surface Contracts + Authority Isolation | pending before Phase 17 |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |

## Session Continuity

Last session: 2026-06-20T01:37:14+08:00
Stopped at: Created v1.6 roadmap and aligned state
Resume file: None
Next: Discuss or plan Phase 23.
