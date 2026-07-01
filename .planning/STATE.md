---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Tool Platform Hardening
status: roadmap_ready
stopped_at: Roadmap created for v2.1; Phases 37-39 defined, awaiting phase planning
last_updated: "2026-07-01T00:00:00.000Z"
last_activity: 2026-07-01 -- v2.1 roadmap created (Phases 37-39)
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-01)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Milestone v2.1 Tool Platform Hardening — roadmap created (Phases 37-39), ready for phase planning

## Current Position

Phase: Not started (roadmap created; next is Phase 37 planning)
Plan: —
Status: Roadmap ready
Last activity: 2026-07-01 -- v2.1 roadmap created (Phases 37-39)

Progress: [          ] 0%

Planning files:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/MILESTONES.md`
- `.planning/milestones/v1.9-ROADMAP.md`
- `.planning/milestones/v1.9-REQUIREMENTS.md`
- `.planning/milestones/v1.9-MILESTONE-AUDIT.md`

## Current Milestone Context

- v2.1 is a bounded, pre-scoped cleanup of the tool-call platform's contract debt and implementation gaps, not a new user-facing feature.
- Sole normative contract source: `docs/contract-spec.md` §12.5/§12.6 and §8.0. All tool contract code lives under `src/tools/` (catalog.py, contracts.py, runtime.py, policy.py, platform.py, manager.py, projection.py, executors/).
- Blast-radius tiering drives sequencing: `ToolResultV2` and `ToolCallContext` are HIGH (7 external consumers); `ToolInvocationOutcome` / `ToolViewV1` / `ToolPolicyDecision` are effectively src/tools-internal (LOW). Defer HIGH-blast-radius envelope field changes; keep v2.1 to `output_schema` (data-shape) enforcement and internal refactors.
- `ToolCallContext` §8.0 identity fields (`tenant_id/user_id/role/permissions/merchant_scope/session_id/thread_id/run_id/trace_id`) are locked — MUST NOT redefine, widen, or rename. Off-limits.
- Domain-level ownership/scope enforcement already lives in BusinessFactService (`_merchant_scope_allows` + no-leak) — not a gap, do not rebuild.
- `docs/contract-spec.md` was just touched by prior memory-alignment work (commit `4dcb673`); Phase 39 planning must re-check whether §12.5/§12.6 were incidentally modified before editing.
- Code implementation is delegated to Codex per the dual-AI workflow; Claude is plan designer and adjudicator. These are planning/spec phases.
- TPH-02 (spec edit) must go through the dual-AI review workflow (`gsd-plan-checker` + Codex cross-review + Claude adjudication).

## Current Roadmap

| Phase | Plans | Status |
|-------|-------|--------|
| 37. Tool Declaration + Runtime/Policy Internal Consolidation (TPH-03, TPH-04) | 0/TBD | Not started |
| 38. output_schema Declaration + Runtime Output-Validation Enforcement (TPH-01) | 0/TBD | Not started |
| 39. contract-spec §12.5/§12.6 Reconciliation (TPH-02) | 0/TBD | Not started |

Sequencing rationale: Phase 37 consolidates the registry and converges runtime/policy internals with no external contract change (LOW blast radius). Phase 38 declares `output_schema` in that consolidated registry and enforces it through the shared failure path. Phase 39 reconciles the spec to the final implemented state via dual-AI review.

## Last Milestone Context

- v2.0 Merchant Scope Hardening delivered Phase 36 (merchant-scope DB hardening / role cleanup) on 2026-06-30. Its remaining same-merchant trace/replay authorization scope stays future work and is not part of v2.1.
- v1.9 Agent Platform Foundation (Phases 26-35.1) shipped and archived on 2026-06-30. It landed the descriptor-driven `ToolView`, runtime `ToolPolicyDecision`, safe tool result projection, and ToolPlatform boundary that v2.1 now hardens.
- `docs/contract-spec.md` is the normative source. Preserve v1.9 service-boundary contracts unless a phase explicitly records a spec delta.
- Memory remains contextual only; policy evidence, business facts, approval/action authority, and replay truth keep their own authoritative services and schemas.

## Performance Metrics

**v1.9 shipped scope:** 12 phases, 19 v1 requirements, 51/51 phase plans complete. Milestone audit status: archived.
**v2.0 shipped scope:** Phase 36 (6/6 plans complete).

Historical execution metrics are archived in milestone files and `.planning/MILESTONES.md`.

## Quick Tasks Completed

| Date | Quick ID | Task | Status |
|------|----------|------|--------|
| 2026-06-21 | 260621-lgq | MOCA memory long-term/case hardening | Complete |

## Accumulated Context

### Decisions

- v2.1 groups four requirements into three dependency-ordered phases: Phase 37 (TPH-03 registry + TPH-04 runtime/policy internal refactors, no contract change), Phase 38 (TPH-01 output_schema declaration + enforcement), Phase 39 (TPH-02 spec reconciliation via dual-AI review).
- Registry consolidation (TPH-03) lands before output_schema work (TPH-01) because `output_schema` is most naturally declared in the same single-source registry.
- TPH-01 is `output_schema` (data-shape) enforcement only and MUST NOT alter the `ToolResultV2` envelope shape (HIGH blast radius, 7 external consumers).
- TPH-02 is a spec-catches-up-to-code edit and MUST go through the dual-AI review workflow; planning must first re-check commit `4dcb673`'s effect on §12.5/§12.6.
- `ToolCallContext` §8.0 identity fields are off-limits across all phases; domain ownership/scope enforcement in BusinessFactService is not rebuilt.

### Roadmap Evolution

- Phase 25 added and completed: Intent routing safety hardening.
- Phase 26-35 added for v1.9 Agent Platform Foundation.
- Phase 35.1 added to close v1.9 milestone audit gates.
- Phase 36 added and completed for v2.0 Merchant Scope Hardening.
- Phase 37-39 added for v2.1 Tool Platform Hardening (2026-07-01).

### Pending Todos

- No active pending todos remain in `.planning/todos/pending/`.
- Optional follow-up from v1.8 remains deferred: pin active slot `confidence` projection before confidence becomes a meaningful provenance field.

### Blockers / Concerns

- No active blockers.

## Deferred Items

| Category | Item | Status |
|----------|------|--------|
| deferred record | `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md` | future candidate only if Phase 17 is reintroduced |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |
| future scope | Same-merchant manager run/trace/replay visibility expansion (post-Phase 36 readiness) | deferred, not part of v2.1 |

## Last Archived Milestone Context

- v1.9 owned Phase 26 through Phase 35.1; all 19 v1.9 requirements are complete and archived.
- v2.0 owned Phase 36; merchant-scope DB hardening and role cleanup complete, with same-merchant trace/replay authorization expansion named as future scope.

## Session Continuity

Last session: 2026-07-01T00:00:00.000Z
Stopped at: v2.1 roadmap created; Phases 37-39 defined
Resume file: `.planning/ROADMAP.md`
Next: Run `$gsd-plan-phase 37`.

**Completed Phase:** 35 (Replay and Eval Hardening) — 6/6 plans complete; UAT 8/8 passed; security `threats_open: 0` — 2026-06-29

**Completed Phase:** 35.1 (v1.9 Milestone Readiness Closure) — 1/1 plan complete; v1.9 archived — 2026-06-30

**Completed Phase:** 36 (Merchant-scope DB Hardening / Role Cleanup) — 6/6 plans complete — 2026-06-30

**Next Roadmap Item:** plan Phase 37
