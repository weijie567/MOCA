---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: Intent Routing Safety Hardening
status: complete
stopped_at: Phase 25 complete
last_updated: "2026-06-21T04:25:00Z"
last_activity: 2026-06-21 -- Completed Phase 25 Intent Routing Safety Hardening
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 13
  completed_plans: 13
  percent: 100
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-21)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** v1.8 Intent Routing Safety Hardening — Phase 25 complete

## Current Position

Phase: 25 - Intent routing safety hardening
Plan: 1/1 complete
Status: Complete
Last activity: 2026-06-21 -- Completed Phase 25 Intent Routing Safety Hardening

Progress: [██████████] 100%

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

- v1.8 targets the ordinary-chat intent/routing safety layer, not a new user-facing workflow or external action execution.
- Raw LLM classification remains advisory; business routing must use deterministic effective classification, risk tier, and route decisions.
- Risk must be derived from intent, requested operation, role, channel, and hints instead of only intent-level high-risk booleans.
- Active workflow state should resolve pending clarification answers before ordinary classification when the pending flow is trusted and scoped.
- Slot memory remains contextual only; provenance and invalidation must prevent stale inherited identifiers from satisfying required slots after user negation or context switching.

## Performance Metrics

**v1.8 velocity:** Phase 25 complete; review and goal-backward verification passed.

| Phase | Plans | Status |
|-------|-------|--------|
| 24. Agent Runs Short-term Memory Parity | 9/9 | Complete |
| 24.2 Unified Session Memory Bundle Read Path | 1/1 | Complete |
| 24.3 Memory Write Isolation Policy and Observability MVP | 1/1 | Complete |
| 24.4 Memory Eval MVP | 1/1 | Complete |
| 25. Intent Routing Safety Hardening | 1/1 | Complete |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

## Accumulated Context

### Decisions

- v1.7 is scoped to Agent Console short-term memory unification, not a full memory product UI or long-term/case-memory redesign.
- Current `/agent-runs` is the user-facing Agent Console path and should be the implementation target.
- The legacy `/agent/chat` path is a compatibility/reference path; v1.7 should avoid introducing incompatible persistence semantics between the two paths.
- Memory context is contextual assistance only and must preserve established evidence, action, approval, and replay boundaries.
- v1.8 hardens the existing Phase 11 intent/clarification contract instead of replacing it with agent-selected routing.

### Roadmap Evolution

- Phase 24.2 inserted after Phase 24: Unified Session Memory Bundle Read Path.
- Phase 24.3 inserted after Phase 24: Memory Write Isolation Policy and Observability MVP.
- Phase 24.4 inserted after Phase 24: Memory Eval MVP.
- Phase 25 added and completed: Intent routing safety hardening.

### Pending Todos

- Optional follow-up: pin active slot `confidence` projection before confidence becomes a meaningful provenance field.

### Blockers / Concerns

- No active blockers. Phase verifier recorded one non-blocking warning: optional slot confidence projection is not pinned by focused tests because current writers do not populate confidence.

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

Last session: 2026-06-21T12:00:00+08:00
Stopped at: Phase 25 complete
Resume file: `.planning/phases/25-intent-routing-safety-hardening/25-CONTEXT.md`
Next: start the next milestone or archive v1.8 if desired.

**Completed Phase:** 23 (RAG Reranker + Query Rewrite) — 6/6 plans complete; UAT 7/7 passed — 2026-06-20T10:33:42+08:00

**Completed Phase:** 24 (Agent Runs Short-term Memory Parity) — 9/9 plans complete; verification passed — 2026-06-20T23:32:39+08:00

**Completed Phase:** 24.2 (Unified Session Memory Bundle Read Path) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 24.3 (Memory Write Isolation Policy and Observability MVP) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 24.4 (Memory Eval MVP) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 25 (Intent routing safety hardening) — 1/1 plans complete; review and verification passed — 2026-06-21T04:25:00Z
