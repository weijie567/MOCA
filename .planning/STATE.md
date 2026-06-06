---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Agentic Investigation
status: ready_to_plan
stopped_at: Completed 07-05-PLAN.md
last_updated: "2026-06-06"
last_activity: 2026-06-06 -- AAM-P1 contract baseline complete; AAM-P2/P3 ready to plan
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 5
  completed_plans: 5
  percent: 40
---

# Project State: MOCA

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution.
**Current focus:** Phase 08 — investigation-routing

## Current Position

Phase: 08
Plan: Not started
Status: Ready to plan
Last activity: 2026-06-04

Progress: [████░░░░░░] 40%

## Performance Metrics

**Velocity:**

- Total plans completed: 43
- Average duration: v1.1 active average 6min/plan
- Total execution time: v1.1 active 12min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v1.0 archive | 36 | historical | historical |
| v1.1 active | 2 | 12min | 6min |
| 07 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: v1.0 archived baseline, 07-01 contracts, 07-02 registry boundary
- Trend: v1.1 Phase 7 progressing on schedule

| Phase 07 P03 | 7min | 2 tasks | 4 files |
| Phase 07-tool-registry-contracts P05 | 5min | 5 tasks | 5 files |

## AAM Workstream (parallel)

The Agent Architecture Migration (AAM-P1..AAM-P11) is a separate workstream
tracked alongside the historical MOCA roadmap phases. It does not renumber or
replace MOCA Phase 07-11. Source: `docs/agent-architecture-phase-decomposition.md`.

| AAM Phase | Name | Status |
|-----------|------|--------|
| AAM-P1 | Contract baseline | COMPLETE (docs-only; verdict PARTIAL, MISSING=0; Claude review PASS) |
| AAM-P2 | Knowledge facade | Ready to plan (unblocked by AAM-P1) |
| AAM-P3 | Business tool facade | Ready to plan (unblocked by AAM-P1; parallel to AAM-P2) |

**AAM-P1 completion (2026-06-06):** Committed in `5e47e01`. Artifacts in
`.planning/phases/AAM-P1-contract-baseline/`. Status counts COVERED=7,
PARTIAL=26, DEFERRED_WITH_OWNER=34, MISSING=0. Because MISSING=0, AAM-P2 and
AAM-P3 may proceed to planning; each must preserve its named contract,
read-switch, test, and eval owner gates.

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v1.1 starts from Phase 7 and must not reintroduce archived v1.0 active phases.
- v1.1 keeps the deterministic LangGraph workflow and inserts only a bounded investigation layer.
- Investigator remains read-only/retrieval-only; approval and execution authority stay downstream.
- Keep default registry adapters inside `src/agent/tools/registry.py` for Plan 07-02 so existing graph nodes and direct tool functions remain untouched.
- Use `ToolExecutionResult(status="error")` with `not_found`, `unsafe_tool_request`, `validation_error`, and `tool_error` codes for structured registry rejection results.
- Keep direct tool function signatures unchanged and make adapters the compatibility layer for registry invocation.
- Sanitize registry success results to ToolExecutionResult.summary and evidence_refs only; raw payload data remains outside prompt-facing model dumps.
- Treat adapter output as untrusted runtime data and convert malformed wrappers to structured validation_error results.
- Keep dormant investigation fields internal but reset them to None every graph turn to avoid checkpoint leakage.

### Pending Todos

None yet.

### Blockers/Concerns

- Roadmap depends on preserving v1.0 API contract, approval semantics, trace replay, and fast-path latency expectations.
- Evaluation must prove bounded investigation improves ambiguous cases without drifting into full-chain ReAct behavior.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v1.0 archive | Historical audit artifacts listed at milestone close | carried forward | 2026-05-22 |

## Session Continuity

Last session: 2026-06-04T10:43:13.494Z
Stopped at: Completed 07-05-PLAN.md
Resume file: None

**Planned Phase:** 7 (Tool Registry & Investigation Contracts) — 4 plans — 2026-06-04T04:41:25.649Z
