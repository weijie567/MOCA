---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: RAG Context Builder + Hallucination Control
status: between_milestones
stopped_at: Archived v1.5 milestone
last_updated: "2026-06-19T17:19:30.509Z"
last_activity: 2026-06-19
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-19)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Between milestones after v1.5 archive.

## Current Position

Phase: None active
Plan: None active
Status: v1.5 archived; ready to define the next milestone
Last activity: 2026-06-19

Progress: [----------] 0% for the next milestone

Planning files:

- `.planning/PROJECT.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/MILESTONES.md`
- `.planning/research/SUMMARY.md`

Archived v1.5 files:

- `.planning/milestones/v1.5-ROADMAP.md`
- `.planning/milestones/v1.5-REQUIREMENTS.md`
- `.planning/milestones/v1.5-MILESTONE-AUDIT.md`

## Last Milestone Context

- v1.5 owned exactly one roadmap phase: Phase 22.
- Phase 22 added the retrieval-after / reasoning-before RAG kernel: ContextBuilder, canonical evidence validation, typed `MaterialClaim` verification, deterministic route control, action-boundary blocking, final-response safety wording, and deterministic hallucination-control evals.
- v1.5 milestone audit status is `tech_debt`: no blockers, 32/32 active requirements satisfied, 6/6 integration areas wired, 8/8 required route/action/eval flows covered.
- Latest/current policy version validity, effective-date/freshness, and hash re-fetch were all verified acceptance points.
- `regenerate-route` was implemented as a backend route value only; automatic regeneration remains stretch scope unless separately accepted.

## Performance Metrics

**v1.5 velocity:** 1 phase complete, 6 of 6 plans complete.

| Phase | Plans | Status |
|-------|-------|--------|
| 22. RAG Context Builder + Hallucination Control | 6/6 | Archived |

Final v1.5 verification evidence:

- Phase 22 UAT: 6/6 checkpoints passed.
- Phase 22 security: 7/7 threats closed, `threats_open: 0`.
- Hallucination eval: 24 cases, 5 production-verifier cases, no failed cases, no threshold failures.
- Final gates: Phase 22 related suite `119 passed, 1 warning`; full non-integration pytest `1228 passed, 1 skipped, 6 warnings`; Ruff check and format check passed.

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

### Pending Todos

- [ ] 17-prep: AgentState Surface Contracts + Authority Isolation - `.planning/todos/pending/2026-06-17-constrain-agentstate-memory-expansion.md`

### Blockers / Concerns

- None for completed v1.5. The milestone audit recorded non-blocking tech debt only.

## Deferred Items

Items acknowledged and deferred at v1.5 close on 2026-06-19:

| Category | Item | Status |
|----------|------|--------|
| todo | 17-prep AgentState Surface Contracts + Authority Isolation | pending |
| tech debt | Defensive business fact ref status filtering hardening | deferred |
| tech debt | Deeper production-verifier eval coverage | deferred |
| tech debt | Eval script header wording drift | deferred |
| tech debt | 22-VALIDATION planning-time table wording drift | deferred |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase 23 RAG Reranker + Query Rewrite | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |

## Session Continuity

Last session: 2026-06-19T17:19:30.509Z
Stopped at: Archived v1.5 milestone
Resume file: None
Next: Run `$gsd-new-milestone` to define the next milestone.
