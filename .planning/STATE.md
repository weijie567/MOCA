---
gsd_state_version: 1.0
milestone: v1.9
milestone_name: Agent Platform Foundation
status: executing
stopped_at: Completed 27-02-PLAN.md
last_updated: "2026-06-22T17:03:31.753Z"
last_activity: 2026-06-23 -- 27-02 platform contracts complete
progress:
  total_phases: 10
  completed_phases: 1
  total_plans: 10
  completed_plans: 3
  percent: 30
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-22)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** v1.9 Agent Platform Foundation — Phase 27 execution in progress

## Current Position

Phase: 27 - TrustedContextFactory and Projections — EXECUTING
Plan: 2 of 3 planned
Status: Ready for 27-03
Last activity: 2026-06-23 -- 27-02 platform contracts complete

Progress: [███░░░░░░░] 30%

Planning files:

- `.planning/PROJECT.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/REQUIREMENTS.md`
- `.planning/MILESTONES.md`
- `.planning/milestones/v1.6-ROADMAP.md`
- `.planning/milestones/v1.6-REQUIREMENTS.md`
- `.planning/milestones/v1.6-phases/23-rag-reranker-query-rewrite/`

## Active Milestone Context

- v1.9 targets the platform foundation for MOCA's agent architecture, not a new user-facing workflow and not full real external execution.
- The target is a microservice-ready modular monolith: service boundaries should be clear enough to split later, while deployment remains a single app for now.
- `docs/contract-spec.md` is the normative source. `docs/target-agent-platform-architecture-plan.md` records target architecture and Phase 26 spec-delta baseline decisions.
- The milestone should land foundations in dependency order: architecture contract baseline, TrustedContextFactory/projections, decision events, tool platform, business facts, memory platform, graph migration, RAG context build/claim verification, approval/action boundary hardening, replay/eval hardening.
- Memory remains contextual only; policy evidence, business facts, approval/action authority, and replay truth keep their own authoritative services and schemas.

## Performance Metrics

**v1.9 target:** 10 phases, 18 APF requirements, 10 phase plans.

| Phase | Plans | Status |
|-------|-------|--------|
| 26. Architecture Contract Baseline | 1/1 complete | Complete |
| 27. TrustedContextFactory and Projections | 2/3 | In Progress |
| 28. Decision Event Foundation | 0/1 | Pending |
| 29. Tool Platform Boundary | 0/1 | Pending |
| 30. BusinessFactService Boundary | 0/1 | Pending |
| 31. Memory Platform Boundary | 0/1 | Pending |
| 32. Intent Graph Migration | 0/1 | Pending |
| 33. RAG Context Build and Claim Verification | 0/1 | Pending |
| 34. Approval and ActionDraft Boundary Hardening | 0/1 | Pending |
| 35. Replay and Eval Hardening | 0/1 | Pending |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.
Latest execution metric: Phase 27 P27-02 — 6 min, 2 tasks, 5 files.

## Quick Tasks Completed

| Date | Quick ID | Task | Status |
|------|----------|------|--------|
| 2026-06-21 | 260621-lgq | MOCA memory long-term/case hardening | Complete |

## Accumulated Context

### Decisions

- v1.7 is scoped to Agent Console short-term memory unification, not a full memory product UI or long-term/case-memory redesign.
- Current `/agent-runs` is the user-facing Agent Console path and should be the implementation target.
- The legacy `/agent/chat` path is a compatibility/reference path; v1.7 should avoid introducing incompatible persistence semantics between the two paths.
- Memory context is contextual assistance only and must preserve established evidence, action, approval, and replay boundaries.
- v1.8 hardens the existing Phase 11 intent/clarification contract instead of replacing it with agent-selected routing.
- v1.9 starts a platform foundation milestone. Phase numbering continues from Phase 25 instead of restarting at Phase 1.
- v1.9 should implement a microservice-ready modular monolith, not physical microservice deployment.
- Full real external execution remains deferred; v1.9 only hardens action draft, approval, evidence, claim, and safety snapshot boundaries.
- 27-01 remains RED-only by design: planned production symbols are imported but no src/ files are edited.
- 27-01 seam integration tests use top-level src.platform imports so current failures are deterministic missing planned production modules, not local database setup.
- Preserved KnowledgeContext.merchant_scope as the existing list shape through project_merchant_scope_for_knowledge.
- Kept current search, agent route, graph node, and tool executor seam migration out of 27-02; 27-03 owns those call sites.
- Kept ToolCallContext safety_snapshot_ref and policy_snapshot_ref as compatibility fields only; target schema reconciliation remains Phase 29 scope.

### Roadmap Evolution

- Phase 24.2 inserted after Phase 24: Unified Session Memory Bundle Read Path.
- Phase 24.3 inserted after Phase 24: Memory Write Isolation Policy and Observability MVP.
- Phase 24.4 inserted after Phase 24: Memory Eval MVP.
- Phase 25 added and completed: Intent routing safety hardening.
- Phase 26-35 added for v1.9 Agent Platform Foundation.

### Pending Todos

- Execute Phase 27 plan 27-03 seam migrations.
- Archive completed old Phase 24/24.x/25 directories into milestone-specific phase archives after Phase 26 planning is stable.
- Optional follow-up from v1.8 remains: pin active slot `confidence` projection before confidence becomes a meaningful provenance field.

### Blockers / Concerns

- No active blockers.
- Resolved local GSD metadata drift: `init.new-milestone` now reads v1.9 as the current milestone and v1.8 as the latest completed milestone after ROADMAP/MILESTONES format repair. `validate.health` still reports non-blocking warnings for old STATE phase references, future Phase 27-35 directories, and older Phase 24/25 summary/archive state.

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-06-20:

| Category | Item | Status |
|----------|------|--------|
| deferred record | `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md` | future candidate only if Phase 17 is reintroduced |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |

## Last Archived Milestone Context

- v1.6 owned exactly one roadmap phase: Phase 23 RAG Reranker + Query Rewrite.
- All 26 v1.6 requirements are complete and archived in `.planning/milestones/v1.6-REQUIREMENTS.md`.
- Phase 23 follows v1.3 hybrid retrieval, v1.4 parser/OCR provenance, and v1.5 ContextBuilder/hallucination-control work.
- 17-prep AgentState cleanup is preserved as a deferred record for possible future Phase 17 work, not a pending todo or blocker.

## Session Continuity

Last session: 2026-06-22T17:03:31.278Z
Stopped at: Completed 27-02-PLAN.md
Resume file: None
Next: execute Phase 27 plan 27-03; old phase directory archive remains a separate cleanup todo.

**Completed Phase:** 23 (RAG Reranker + Query Rewrite) — 6/6 plans complete; UAT 7/7 passed — 2026-06-20T10:33:42+08:00

**Completed Phase:** 24 (Agent Runs Short-term Memory Parity) — 9/9 plans complete; verification passed — 2026-06-20T23:32:39+08:00

**Completed Phase:** 24.2 (Unified Session Memory Bundle Read Path) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 24.3 (Memory Write Isolation Policy and Observability MVP) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 24.4 (Memory Eval MVP) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 25 (Intent routing safety hardening) — 1/1 plans complete; review and verification passed — 2026-06-21T04:25:00Z

**Completed Phase:** 26 (Architecture Contract Baseline) — 1/1 plans complete; external review passed with warnings fixed — 2026-06-22T14:43:37Z
