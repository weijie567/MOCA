# Phase 53: Session Context Before Intent and Contextual Intent Resolve - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `53-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-07-06T10:21:54Z
**Phase:** 53-session-context-before-intent-and-contextual-intent-resolve
**Mode:** Auto-selected conservative defaults via `$gsd-phase-autopilot 53`
**Areas discussed:** Graph cutover shape, contextual intent authority, pre-intent session context, post-intent routing compatibility, validation and compatibility ledger

---

## Graph Cutover Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical active graph order now | Register `session_context_load` before `contextual_intent_resolve`, remove active `classify_intent` / `session_memory_load` graph registration, and keep later legacy nodes scoped to later phases. | yes |
| Thin alias only | Keep active graph node names as-is and only adjust vocabulary projection. |  |
| Full no-debt cutover | Remove all legacy graph names and route values in this phase. |  |

**Auto choice:** Canonical active graph order now.
**Notes:** This is the only option that satisfies CAGM-04 without overreaching into Phase 58.

---

## Contextual Intent Authority

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical node with helper reuse | Add active `contextual_intent_resolve` ownership, reuse existing deterministic/LLM adapter helpers where safe, and make trace/state owner canonical. | yes |
| Rewrite intent classifier from scratch | Replace the classifier implementation wholesale. |  |
| Keep legacy classifier node active | Keep `classify_intent` as the graph node and only document target naming. |  |

**Auto choice:** Canonical node with helper reuse.
**Notes:** This minimizes blast radius while making active graph ownership canonical. It still requires removing `classification_trace.pre_route_decision` duplication because Phase 52 owns pre-route decisions.

---

## Pre-Intent Session Context

| Option | Description | Selected |
|--------|-------------|----------|
| Same-thread contextual-only load before intent | Use existing `MemoryContextService`/`SessionMemoryBundleService`, tolerate `current_intent=None`, and expose contextual slots/history before intent resolution. | yes |
| Long-term/case memory before intent | Load reviewed long-term/case/CWC context before intent. |  |
| Keep session context after intent | Preserve current `classify_intent -> session_memory_load` order. |  |

**Auto choice:** Same-thread contextual-only load before intent.
**Notes:** This satisfies Phase 53 and keeps Phase 55 reviewed memory context out of scope.

---

## Post-Intent Routing Compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical router with Phase 54 slot compatibility | Rename active router to `route_after_contextual_intent`; route slot-required paths to legacy `extract_slots` until Phase 54; do not route to `session_memory_load`. | yes |
| Jump directly to `slot_resolution_gate` | Implement Phase 54 slot gate in this phase. |  |
| Keep `route_after_intent` and `session_memory_load` | Preserve old route vocabulary. |  |

**Auto choice:** Canonical router with Phase 54 slot compatibility.
**Notes:** This closes Phase 53's session-context-before-intent requirement while explicitly deferring slot gate semantics to Phase 54.

---

## Validation And Compatibility Ledger

| Option | Description | Selected |
|--------|-------------|----------|
| Update code, tests, docs, vocabulary, and architecture debt together | Require graph/route/vocabulary/static baseline tests plus ledger entries for any remaining helper compatibility. | yes |
| Code-only cutover | Change runtime graph first and leave docs/tests for later. |  |
| Final alias cleanup | Delete every legacy alias and no-debt marker now. |  |

**Auto choice:** Update code, tests, docs, vocabulary, and architecture debt together.
**Notes:** This matches Phase 50 migration policy and keeps Phase 58 final cleanup separate.

---

## the agent's Discretion

- Planner may choose the lowest-risk helper extraction strategy for intent code reuse.
- Planner may decide whether remaining `classify_intent.py` helper names are acceptable temporary compatibility, but must ledger any retained compatibility surface.

## Deferred Ideas

- Phase 54 slot resolution gate and provenance.
- Phase 55 reviewed memory context load cutover.
- Phase 58 final no-debt alias cleanup.
