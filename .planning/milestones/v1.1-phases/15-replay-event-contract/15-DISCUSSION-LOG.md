# Phase 15: Replay Event Contract - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `15-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 15-replay-event-contract
**Areas discussed:** Delivery scope, V3 schema shape, Sequence allocator model, Lifecycle finalizer and SLA scanner, Operation pairing and backfill, Replay API read-switch and trace fallback, Phase 14 compatibility cleanup

---

## Delivery Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Complete V3 MVP | Implement V3 schema/service/API/finalizer/pairing/read-switch in Phase 15 while deferring Phase 17 external events. | yes |
| Split delivery | Build schema/service/API basics now and defer lifecycle or pairing depth to a later named phase. | no |
| Minimal API first | Return a safe V3 shape quickly while weakening pairing/finalizer depth. | no |

**User's choice:** Complete V3 MVP.
**Notes:** User chose this to avoid Phase 15 becoming a half-finished API stage.

---

## V3 Schema Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Physical column expansion | Add V3 columns/indexes/checks, keep old JSON fields compatible, and project through service. | yes |
| JSON projection | Avoid physical expansion and rely mostly on existing JSON fields. | no |
| Full rename | Rename/migrate current fields to contract names across the table. | no |

**User's choice:** Physical column expansion plus legacy JSON compatibility and service projection.
**Notes:** User prioritized indexes, constraints, pairing validation, and rollback explanation.

---

## Sequence Allocator Model

| Option | Description | Selected |
|--------|-------------|----------|
| Service current allocator | Keep advisory lock + `max(sequence)+1`, move ownership into replay/trace-event service, add cross-writer tests. | yes |
| AgentRun counter | Use `AgentRun.next_event_sequence` row lock/CAS. | no |
| Dedicated counter table | Add `run_event_sequences` table. | no |

**User's choice:** Service the current allocator.
**Notes:** User wants cross-writer concurrency tests to cover consistency and does not want a new counter schema in Phase 15.

---

## Lifecycle Finalizer and SLA Scanner

| Option | Description | Selected |
|--------|-------------|----------|
| Service + API/graph hooks | Add `RunLifecycleService` and call it from graph/API/approval terminal paths. | yes |
| Force graph `trace_close` node | Route all lifecycle closure through graph tail. | no |
| API finalizer first | Add finalization mainly in routers/API layer. | no |

**User's choice:** Service + API/graph hooks.
**Notes:** User wants a unified lifecycle owner without forcing all paths through `trace_close`.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep scanner disabled | Verify replay/allocator gate and disabled scanner behavior; defer active enablement. | yes |
| Conditionally enable | Enable only after replay lifecycle and allocator gates pass. | no |
| Directly enable | Make active scanner a Phase 15 must-have. | no |

**User's choice:** Keep active SLA scanner disabled.
**Notes:** User chose this to avoid expanding concurrent writer and lifecycle risk in Phase 15.

---

## Operation Pairing and Backfill

| Option | Description | Selected |
|--------|-------------|----------|
| Mark unresolved | Strict pairing for new events; mark unprovable historical/backfill rows as unresolved. | yes |
| Best-effort inference | Infer pairings from timestamp/type/node order. | no |
| Exclude old events | Return only V3 new writes. | no |

**User's choice:** Mark unresolved.
**Notes:** User explicitly rejected timestamp inference that could fabricate pairing.

---

## Replay API Read-Switch and Trace Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| `/replay` event-store-first, `/trace` legacy fallback | Add V3 `/replay`, keep `/trace` as existing rollback fallback. | yes |
| Both event-store-first | Switch both `/replay` and `/trace` to event-store-first. | no |
| `/replay` with legacy fallback | Let `/replay` fill gaps from legacy timeline. | no |

**User's choice:** `/replay` event-store-first, `/trace` legacy fallback.
**Notes:** User chose the rollback-safe Phase 15 path.

| Option | Description | Selected |
|--------|-------------|----------|
| V3 projection with provenance | Always return V3-shaped events; expose legacy/minimal rows through projection and provenance. | yes |
| Mixed schema | Return V3 for new events and minimal shape for old events. | no |
| Only V3 new writes | Omit legacy/minimal rows from replay. | no |

**User's choice:** V3 projection with provenance.
**Notes:** User wants a uniform API shape without hiding migration provenance.

---

## Phase 14 Compatibility Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Clean replay-facing expression only | Fix replay/timeline/API wording and deprecated markers that could imply external execution. | yes |
| Fully delete compatibility fields | Remove `execute_action` / `action_result` compatibility surfaces broadly. | no |
| Do not touch compatibility | Leave all compatibility cleanup to a later phase. | no |

**User's choice:** Clean replay-facing expression only.
**Notes:** User does not want Phase 15 to reopen intent taxonomy or broad compatibility deletion.

---

## the agent's Discretion

- Exact `src/replay/` module split.
- Exact focused test file split under `tests/replay/`.
- Whether `src/agent/events.py` becomes a wrapper or is partially moved behind the replay service.

## Deferred Ideas

- Active SLA scanner enablement after Phase 15 gates.
- Phase 17 external execution/reconciliation event families and external worker allocator concurrency.
- Broad compatibility-field deletion for `execute_action` / `action_result` outside replay-facing expression.
