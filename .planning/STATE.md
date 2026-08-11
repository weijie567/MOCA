---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Product Experience Fixes
status: executing
last_updated: "2026-08-11T06:34:44Z"
last_activity: 2026-08-11 -- Phase 64.4 Plan 03 complete; truthful usage and immutable parity gates passed
progress:
  total_phases: 15
  completed_phases: 7
  total_plans: 54
  completed_plans: 46
  percent: 47
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-10)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 64.4 — token-aware-policy-chunking-and-reindex-validation

## Current Position

Phase: 64.4 (token-aware-policy-chunking-and-reindex-validation) — EXECUTING
Plan: 4 of 11 — Plan 64.4-04 production/dry-run/golden/A-B convergence
Status: Plans 01-03 complete; executing the approved strict 01→11 dependency chain.
Last activity: 2026-08-11 -- Phase 64.4 Plan 03 complete; truthful usage and immutable parity gates passed
Next: Execute `64.4-04-PLAN.md`, then continue dependency-ordered plans.
After: Phase 65 follows Phase 64.4.

Resume file: `.planning/autopilot/phase-64.4.md`

Progress: [█████░░░░░] 47%

## Last Completed Milestone

**v2.1 Core Subsystem Hardening** shipped Phases 37-60 plus inserted Phase 48.1.

- Plans: 87/87 complete
- Requirements: 24/24 complete
- Audit: `.planning/milestones/v2.1-MILESTONE-AUDIT.md` — `passed` / `archive_ready`
- Roadmap archive: `.planning/milestones/v2.1-ROADMAP.md`
- Requirements archive: `.planning/milestones/v2.1-REQUIREMENTS.md`

Phase directories remain under `.planning/phases/` for now. Use `$gsd-cleanup` later if you want to move completed phase directories into milestone archives.

## Next Milestone Setup

- v2.2 is active.
- Phase numbering continues after Phase 60.
- Preserve accepted contracts from `docs/contract-spec.md` unless a future phase records a reviewed spec delta, MVP scope note, or owner-named deferral.
- Keep memory contextual-only, ToolPlatform as the canonical tool boundary, and the canonical Agent Graph node vocabulary as the active runtime vocabulary unless the next milestone intentionally changes those contracts.

## Accumulated Context

### Roadmap Evolution

- Phase 61 added: Product Experience Fixes.
- Phase 61 context gathered: `.planning/phases/61-product-experience-fixes/61-CONTEXT.md`.
- Phase 61 planned as five execution plans: UX baseline, metric contract/scope, metric runtime, agent graph integration, and console/regression validation.
- Phase 62 added: Business Query And Drilldown Foundation.
- Phase 62 grain decision: Business Query mainline is one phase with seven plans, not five separate phases; independent safety/RAG/trace hardcoding debts remain future follow-up phase candidates.
- Phase 62 completed with 7/7 plans, clean code review, UAT 7/7 passed, `threats_open: 0`, and `nyquist_compliant: true`.
- Phase 63 added: Safety Taxonomy And Risk Vocabulary.
- Phase 63 planned as five execution plans and passed GSD plan-checker plus two-round Claude/Codex plan review.
- Phase 63 completed with canonical safety taxonomy, risk severity/disposition split, action-draft executable boundary, registry-derived routing, drift guards, post-review recommendation_generation registry fix, UAT, security, and validation closeout.
- Phase 64 added: RAG Risk Label Unification.
- Phase 64 context captured in auto mode: RAG-specific risk label registry, existing label compatibility, `manual_review_sensitive` builder propagation, and no Phase 65/66/67 scope creep.
- Phase 64 planned as four execution plans and passed GSD plan-checker after Claude/Codex plan review repairs: registry foundation, builder/recommendation migration, verifier/routing/metrics migration, and drift guard/validation closeout.
- Phase 64 completed with canonical RAG risk label registry, `manual_review_sensitive` builder propagation, registry-consuming builder/recommendation/verifier/routing/metrics paths, static drift guards, clean code review, UAT, security, and validation closeout.
- Phase 65 added: Trace Event And Console Label Consistency.
- Phase 66 added: Unified Operation Contract And Tool Gateway.
- Phase 67 added: Dev Test And Config Hygiene.
- Phase 68 added: State Machine Registry And DB Constraint Hardening.
- ROADMAP current-milestone structure normalized so GSD phase operations recognize Phases 62-71 inside v2.2 rather than treating only Phase 61 as current.
- Phase 64.1 inserted after Phase 64: Runtime Safety And Approval Contract Repair (URGENT).
- Phase 64.2 inserted after Phase 64.1: Evidence Identity Immutable Replay And Memory Provenance (URGENT).
- Phase 64.3 inserted after Phase 64.2: RAG Format Parity And Document Quality Evaluation (URGENT); it establishes the cross-format parser/retrieval baseline before Phase 65.
- Phase 64.4 inserted after Phase 64.3: Token-Aware Policy Chunking And Reindex Validation (URGENT); it consumes the Phase 64.3 baseline and Phase 64.2 identity contract before Phase 65.
- Phases 65-68 expanded with explicit audit finding ownership, scope boundaries, dependency order, and source-verifiable success criteria.
- Phase 69 added: LLM Runtime Gateway And Observability.
- Phase 70 added: Memory Retrieval Quality And Governance.
- Phase 71 added: Agent State And Service Boundary Decomposition.
- Phase 71 strengthened with a mandatory responsibility matrix for every audit-named high-complexity module and an explicit KEEP/SPLIT/MOVE/DELETE/DEFER closeout gate.

**Planned Phase:** 64.3 (RAG Format Parity And Document Quality Evaluation) — 5 plans — 2026-08-10T09:13:01.395Z
**Planned Phase:** 62 (Business Query And Drilldown Foundation) — 7 plans — 2026-07-09T12:11:17Z
**Completed Phase:** 63 (Safety Taxonomy And Risk Vocabulary) — 5/5 plans complete, review/UAT/security/validation clean
**Completed Phase:** 64 (RAG Risk Label Unification) — 4/4 plans complete, review/UAT/security/validation clean
**Completed Phase:** 64.1 (Runtime Safety And Approval Contract Repair) — 6/6 plans complete, review/UAT/security/validation clean
**Completed Phase:** 64.2 (Evidence Identity Immutable Replay And Memory Provenance) — 11/11 plans and 26/26 tasks complete; final review/UAT/security/validation clean
**Completed Phase:** 64.3 (RAG Format Parity And Document Quality Evaluation) — 5/5 plans and 12/12 tasks complete; final review/UAT/security/validation clean; canonical baseline truthfully quality-red
**Planned Phase:** 64.4 (Token-Aware Policy Chunking And Reindex Validation) — 11 plans / 22 executable tasks; GSD plan-checker passed after three iterations; pending Claude/Codex cross-review
**Registered Phase:** 65 (Trace Event And Console Label Consistency) — depends on 64.4, pending `$gsd-plan-phase 65`
**Registered Phase:** 66 (Unified Operation Contract And Tool Gateway) — pending `$gsd-plan-phase 66`
**Registered Phase:** 67 (Dev Test And Config Hygiene) — pending `$gsd-plan-phase 67`
**Registered Phase:** 68 (State Machine Registry And DB Constraint Hardening) — pending `$gsd-plan-phase 68`
**Registered Phase:** 69 (LLM Runtime Gateway And Observability) — pending `$gsd-plan-phase 69`
**Registered Phase:** 70 (Memory Retrieval Quality And Governance) — pending `$gsd-plan-phase 70`
**Registered Phase:** 71 (Agent State And Service Boundary Decomposition) — pending `$gsd-plan-phase 71`
