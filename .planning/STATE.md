---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: RAG Context Builder + Hallucination Control
status: executing
stopped_at: Completed 22-03-PLAN.md
last_updated: "2026-06-19T09:30:57.124Z"
last_activity: 2026-06-19 -- Completed 22-03 ContextBuilder and canonical evidence validation
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 6
  completed_plans: 3
  percent: 50
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-19)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 22 — RAG Context Builder + Hallucination Control

## Current Position

Phase: 22 (RAG Context Builder + Hallucination Control) — EXECUTING
Plan: 4 of 6
Plans: 3/6 complete for v1.5
Status: Ready to execute
Last activity: 2026-06-19 -- Completed 22-03 ContextBuilder and canonical evidence validation

Progress: [█████░░░░░] 50%

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

**v1.5 velocity:** 0 phases complete, 3 of 6 plans complete.

| Phase | Plans | Status |
|-------|-------|--------|
| 22. RAG Context Builder + Hallucination Control | 3/6 | In Progress |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| 22-01 | 9 min | 3 | 7 |
| 22-02 | 13 min | 3 | 8 |
| 22-03 | 10 min | 3 | 6 |

## Accumulated Context

### Decisions

- Phase 22 is retrieval-after / reasoning-before kernel work, not retrieval backend or reranking work.
- Policy conclusions require `EvidenceRefV1`; business fact claims require Tool System refs; memory remains contextual only.
- Source-block/OCR/parser provenance remains internal/debug/maintainer lookup only unless explicitly projected as prompt-safe labels.
- Non-allow verification outcomes must block proposed actions, approval requests, action drafts, and `ActionSafetySnapshot` evidence.
- Wave 0 Phase 22 remains RED-only; production rag_context APIs are reserved for later implementation plans.
- Future Phase 22 API imports live inside pytest helpers so Wave 0 tests collect cleanly and fail only in RED execution.
- Plan 22-02 remains RED-only; production rag_context APIs and graph behavior are reserved for later implementation plans.
- Latest/current policy version validation is pinned separately from text hash and effective-date freshness validation.
- Phase 21 boundary guards now allow Phase 22-owned claim/verifier names only in owned files while preserving Phase 23/RAG-5/Phase 17 scope bans.
- Plan 22-03 kept EvidenceRefV1 unchanged; Phase 22 citation, trace, and budget metadata live in separate rag_context DTOs.
- Plan 22-03 implements latest/current policy validity as EvidenceRefV1.policy_version == v{PolicyDocument.version} for the current tenant/document row.
- Plan 22-03 projects provenance/OCR inputs only as prompt-safe risk labels on ordinary surfaces.

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

Last session: 2026-06-19T09:30:57.116Z
Stopped at: Completed 22-03-PLAN.md
Resume file: None
Next: Run `$gsd-execute-phase 22`

**Planned Phase:** 22 (RAG Context Builder + Hallucination Control) — 6 plans — 2026-06-19T08:10:51.999Z
