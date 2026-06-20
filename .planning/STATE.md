---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Short-term Memory Unification
status: ready_to_plan
stopped_at: Phase 24 context gathered
last_updated: "2026-06-20T19:38:19+08:00"
last_activity: 2026-06-20 -- Gathered Phase 24 context
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
**Current focus:** v1.7 Short-term Memory Unification

## Current Position

Phase: 24 - Agent Runs Short-term Memory Parity
Plan: Not started
Status: Context gathered; ready to plan
Last activity: 2026-06-20 -- Gathered Phase 24 context

Progress: [----------] 0%

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

- v1.7 targets the current Agent Console main path: `/api/v1/agent-runs + SSE`.
- The milestone goal is to complete the short-term memory chain for follow-up turns: structured session slots, conversation messages, tool prompt summaries, and rolling thread summaries.
- Legacy `/api/v1/agent/chat` already has conversation-message and rolling-summary persistence behavior; v1.7 should bring the current run-based path to parity without breaking the frontend API contract.
- Session slot memory must stay PostgreSQL-authoritative, prompt-safe, tenant/thread/session scoped, and contextual only.
- Memory must not become policy evidence, current business fact authority, approval/action authority, or replay/audit truth.

## Performance Metrics

**v1.7 velocity:** Not started.

| Phase | Plans | Status |
|-------|-------|--------|
| 24. Agent Runs Short-term Memory Parity | 0/0 | Ready to plan |

Historical execution metrics are archived in prior milestone files and `.planning/MILESTONES.md`.

## Accumulated Context

### Decisions

- v1.7 is scoped to Agent Console short-term memory unification, not a full memory product UI or long-term/case-memory redesign.
- Current `/agent-runs` is the user-facing Agent Console path and should be the implementation target.
- The legacy `/agent/chat` path is a compatibility/reference path; v1.7 should avoid introducing incompatible persistence semantics between the two paths.
- Memory context is contextual assistance only and must preserve established evidence, action, approval, and replay boundaries.

### Pending Todos

- Plan Phase 24 implementation.

### Blockers / Concerns

- No active blockers.

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

Last session: 2026-06-20T19:38:19+08:00
Stopped at: Phase 24 context gathered
Resume file: `.planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md`
Next: Run `$gsd-plan-phase 24`.

**Completed Phase:** 23 (RAG Reranker + Query Rewrite) — 6/6 plans complete; UAT 7/7 passed — 2026-06-20T10:33:42+08:00
