---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: RAG Context Builder + Hallucination Control
status: milestone_complete
stopped_at: Completed 22-06-PLAN.md
last_updated: "2026-06-19T11:48:03.221Z"
last_activity: 2026-06-19
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 6
  completed_plans: 6
  percent: 100
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-19)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 22 — RAG Context Builder + Hallucination Control

## Current Position

Phase: 22 (RAG Context Builder + Hallucination Control) — COMPLETE
Plan: 6 of 6
Plans: 6/6 complete for v1.5
Status: Milestone complete
Last activity: 2026-06-19

Progress: [██████████] 100%

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

**v1.5 velocity:** 1 phase complete, 6 of 6 plans complete.

| Phase | Plans | Status |
|-------|-------|--------|
| 22. RAG Context Builder + Hallucination Control | 6/6 | Complete |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| 22-01 | 9 min | 3 | 7 |
| 22-02 | 13 min | 3 | 8 |
| 22-03 | 10 min | 3 | 6 |
| 22-04 | 10 min | 3 | 5 |
| 22-05 | 17 min | 3 | 10 |
| Phase 22 P06 | multi-session | 3 tasks | 11 files |

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
- Plan 22-04 kept MaterialClaim and verifier metadata outside EvidenceRefV1 and BusinessFactRefV1 identity DTOs.
- Plan 22-04 accepts successful or partial-success ToolResultV2 business_fact_refs as trusted business authority while failed tool results remain non-authority.
- Plan 22-04 keeps Level 3 semantic verification provider-injected with no live model, network, or credential requirement for default tests.
- Plan 22-05 keeps regenerate_route as a backend route value only; no automatic regeneration attempt was implemented.
- Plan 22-05 gates recommendation-to-action flow on explicit backend verification route allow; all other routes go to final response.
- Plan 22-05 blocks non-allow verifier state in graph routing, risk assessment, and action_draft direct/resume paths.
- Plan 22-05 renders final responses from safe route categories only and omits raw verifier/provenance/OCR/tool/debug payloads.
- Plan 22-06 uses deterministic local hallucination-control metrics as the blocking Phase 22 acceptance gate; no live semantic/model provider is required by default.
- Plan 22-06 eval reports remain redacted to metrics, threshold failures, and case IDs only; raw verifier prompts, private reasoning, raw policy/OCR/provenance/debug material stay out of reports.
- Plan 22-06 preserves EvidenceRefV1 identity and deferred Phase 23, Phase 17, RAG5, Policy Source Operations, and automatic regeneration boundaries while allowing Phase 22-owned verifier and claim surfaces.
- Plan 22-06 Task 3 stayed verification-only for its allowed files; out-of-scope final-gate failures were checkpointed and repaired in separate owning commits before rerunning the full gate.

### Pending Todos

- [ ] 17-prep: AgentState Surface Contracts + Authority Isolation - `.planning/todos/pending/2026-06-17-constrain-agentstate-memory-expansion.md`

### Blockers / Concerns

- None for completed Phase 22. Scope guards continue to prevent Phase 23 query rewrite/reranking, Phase 17 execution, RAG-5 backend work, Policy Source Operations UI, automatic regeneration implementation, and `EvidenceRefV1` identity changes.

## Deferred Items

| Category | Item | Status |
|----------|------|--------|
| todo | 17-prep AgentState Surface Contracts + Authority Isolation | pending |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase 23 RAG Reranker + Query Rewrite | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |

## Session Continuity

Last session: 2026-06-19T11:48:03.212Z
Stopped at: Completed 22-06-PLAN.md
Resume file: None
Next: Run `$gsd-verify-work 22` or complete the v1.5 milestone

**Planned Phase:** 22 (RAG Context Builder + Hallucination Control) — 6 plans — 2026-06-19T08:10:51.999Z
