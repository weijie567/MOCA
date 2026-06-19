---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: RAG Reranker + Query Rewrite
status: defining_requirements
stopped_at: Started v1.6 milestone
last_updated: "2026-06-20T00:00:00+08:00"
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

Phase: 23 (RAG Reranker + Query Rewrite) — NOT STARTED
Plan: —
Status: Defining requirements and roadmap
Last activity: 2026-06-20 — Milestone v1.6 started

Progress: [----------] 0%

Planning files:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/MILESTONES.md`

## Current Milestone Context

- v1.6 owns exactly one roadmap phase: Phase 23.
- Phase 23 follows v1.3 hybrid retrieval, v1.4 parser/OCR provenance, and v1.5 ContextBuilder/hallucination-control work.
- Phase 23 may add bounded query rewrite, a reranker interface, optional provider adapters behind config, ranking explanations, ablation evals, and latency budgets.
- Phase 23 must preserve `EvidenceRefV1` identity, canonical citation text/text_hash, tenant/scope/effective-date filters, ContextBuilder validation, verifier routing, and action-boundary safety.
- 17-prep AgentState cleanup remains a pending todo before Phase 17 External Action Execution, not a blocker for Phase 23.

## Performance Metrics

**v1.6 velocity:** 0 phases complete, 0 plans complete.

| Phase | Plans | Status |
|-------|-------|--------|
| 23. RAG Reranker + Query Rewrite | 0/0 | Not started |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

## Accumulated Context

### Decisions

- Phase 22 is retrieval-after / reasoning-before kernel work, not retrieval backend or reranking work.
- Policy conclusions require `EvidenceRefV1`; business fact claims require Tool System refs; memory remains contextual only.
- Source-block/OCR/parser provenance remains internal/debug/maintainer lookup only unless explicitly projected as prompt-safe labels.
- Non-allow verification outcomes block proposed actions, approval requests, action drafts, and `ActionSafetySnapshot` evidence.
- Latest/current policy version validation is pinned separately from text hash and effective-date freshness validation.
- Phase 22 kept `EvidenceRefV1` unchanged; citation, trace, and budget metadata live in separate rag_context DTOs.
- Plan 22-03 implements latest/current policy validity as `EvidenceRefV1.policy_version == v{PolicyDocument.version}` for the current tenant/document row.
- Plan 22-03 projects provenance/OCR inputs only as prompt-safe risk labels on ordinary surfaces.
- Plan 22-04 kept `MaterialClaim` and verifier metadata outside `EvidenceRefV1` and `BusinessFactRefV1` identity DTOs.
- Plan 22-04 accepts successful or partial-success `ToolResultV2.business_fact_refs` as trusted business authority while failed tool results remain non-authority.
- Plan 22-04 keeps Level 3 semantic verification provider-injected with no live model, network, or credential requirement for default tests.
- Plan 22-05 keeps `regenerate_route` as a backend route value only; no automatic regeneration attempt was implemented.
- Plan 22-05 gates recommendation-to-action flow on explicit backend verification route `allow`; all other routes go to final response.
- Plan 22-05 blocks non-allow verifier state in graph routing, risk assessment, and action_draft direct/resume paths.
- Plan 22-05 renders final responses from safe route categories only and omits raw verifier/provenance/OCR/tool/debug payloads.
- Plan 22-06 uses deterministic local hallucination-control metrics as the blocking Phase 22 acceptance gate; no live semantic/model provider is required by default.
- Plan 22-06 eval reports remain redacted to metrics, threshold failures, and case IDs only; raw verifier prompts, private reasoning, raw policy/OCR/provenance/debug material stay out of reports.
- Plan 22-06 preserves `EvidenceRefV1` identity and deferred Phase 23, Phase 17, RAG5, Policy Source Operations, and automatic regeneration boundaries while allowing Phase 22-owned verifier and claim surfaces.
- v1.6 starts the owner-named Phase 23 retrieval-quality work. 17-prep AgentState cleanup remains deferred until Phase 17 preparation.

### Pending Todos

- [ ] 17-prep: AgentState Surface Contracts + Authority Isolation - `.planning/todos/pending/2026-06-17-constrain-agentstate-memory-expansion.md`

### Blockers / Concerns

- None for starting Phase 23. The active requirement and roadmap artifacts still need to be finalized in this milestone initialization.

## Deferred Items

| Category | Item | Status |
|----------|------|--------|
| todo | 17-prep AgentState Surface Contracts + Authority Isolation | pending before Phase 17 |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |

## Session Continuity

Last session: 2026-06-20T00:00:00+08:00
Stopped at: Started v1.6 milestone
Resume file: None
Next: Finish `$gsd-new-milestone` by creating `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md`.
