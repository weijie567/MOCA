---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: RAG Context Builder + Hallucination Control
current_phase: 22
current_phase_name: RAG Context Builder + Hallucination Control
status: planning_ready
stopped_at: v1.5 roadmap created; Phase 22 ready to discuss or plan
last_updated: "2026-06-19"
last_activity: "2026-06-19 -- v1.5 roadmap created"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-19)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** v1.5 RAG Context Builder + Hallucination Control — Phase 22 planning-ready

## Current Position

Phase: Phase 22 (RAG Context Builder + Hallucination Control)
Plan: TBD
Plans: 0/0 complete for v1.5
Status: Planning ready
Last activity: 2026-06-19 -- v1.5 roadmap created with one active roadmap phase

Progress: [░░░░░░░░░░] 0%

Planning files:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/research/SUMMARY.md`

## Current Milestone Context

- v1.5 owns exactly one roadmap phase: Phase 22.
- Research `22.1` through `22.8` items are internal Phase 22 plan slices, not roadmap phases.
- Phase 22 must preserve v1.3/v1.4 retrieval/evidence/provenance contracts while adding ContextBuilder, `MaterialClaim`, tiered verification, deterministic routing, and hallucination-control evals.
- Latest/current policy version validity, effective-date/freshness, and hash re-fetch are all required acceptance points.
- `regenerate-route` is in scope as a route enum/action; automatic regeneration attempt is stretch unless separately accepted.

## Performance Metrics

**v1.5 velocity:** 0 phases complete, 0 plans complete.

| Phase | Plans | Status |
|-------|-------|--------|
| 22. RAG Context Builder + Hallucination Control | TBD | Not started |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

## Accumulated Context

### Decisions

- Phase 22 is retrieval-after / reasoning-before kernel work, not retrieval backend or reranking work.
- Policy conclusions require `EvidenceRefV1`; business fact claims require Tool System refs; memory remains contextual only.
- Source-block/OCR/parser provenance remains internal/debug/maintainer lookup only unless explicitly projected as prompt-safe labels.
- Non-allow verification outcomes must block proposed actions, approval requests, action drafts, and `ActionSafetySnapshot` evidence.

### Pending Todos

- [ ] Constrain AgentState memory expansion - `.planning/todos/pending/2026-06-17-constrain-agentstate-memory-expansion.md`

### Blockers / Concerns

- Level 3 semantic verifier budgets and thresholds must be locked during Phase 22 planning.
- Business fact ref coverage must be checked before relying on business-fact claim verification.
- Scope guards must prevent Phase 23 query rewrite/reranking, Phase 17 execution, RAG-5 backend work, Policy Source Operations UI, and `EvidenceRefV1` identity changes.

## Deferred Items

| Category | Item | Status |
|----------|------|--------|
| todo | 2026-06-17-constrain-agentstate-memory-expansion.md | pending |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase 23 RAG Reranker + Query Rewrite | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |

## Session Continuity

Last session: 2026-06-19
Stopped at: v1.5 roadmap created; Phase 22 is ready to discuss or plan
Resume file: None
Next: Run `$gsd-discuss-phase 22` or `$gsd-plan-phase 22`
