# Phase 15: Replay Event Contract - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 15 --all`

<domain>
## Phase Boundary

Phase 15 implements the full ReplayEventV3 MVP on top of the Phase 10 minimal event foundation. It owns V3 event schema enrichment, replay/event service ownership, run lifecycle finalization, shared sequence allocator service ownership, operation pairing validation, redaction/retention, `/replay` read API, and rollback-safe read-switch behavior.

This phase does not implement Phase 16 long-term/case memory identity, tombstones, or review workflow. It does not implement Phase 17 external execution, outbox, reconciliation, compensation, external worker allocator tests, or `action_execution_*` event behavior. Replay records what happened; it does not become business truth or action authority.

</domain>

<decisions>
## Implementation Decisions

### Delivery Scope
- **D-01:** Phase 15 is locked to a complete ReplayEventV3 MVP, not a partial API-only stage. The phase must plan V3 schema/service/API/finalizer/pairing/read-switch together, while explicitly deferring Phase 17 external action/reconciliation event families.

### V3 Schema Shape
- **D-02:** `agent_trace_events` should use physical column expansion for V3 fields and indexes, while preserving current minimal JSON fields for compatibility. `ReplayService` / `TraceEventService` owns V3 projection from both old minimal rows and new V3 rows.
- **D-03:** Do not use a JSON-only V3 projection as the main implementation path. The plan must include explicit schema/index/check work for pairing, retention, access, and ordered replay.

### Sequence Allocator Model
- **D-04:** Phase 15 should service the current advisory-lock plus `max(sequence)+1` allocator behind the replay/trace-event service boundary and add cross-writer concurrency tests. Do not introduce `AgentRun.next_event_sequence` or a dedicated counter table in Phase 15.

### Lifecycle Finalizer and SLA Scanner
- **D-05:** Add `RunLifecycleService` as the unified lifecycle owner. Graph normal paths, API terminal persistence, approval resume paths, and error paths should call this service. Do not force all lifecycle closure through a graph `trace_close` node in this phase.
- **D-06:** Keep the active SLA scanner disabled in Phase 15. The phase must verify the disabled scanner gate and replay/allocator readiness, but enabling active scanner behavior is deferred to a named post-Phase 15 phase.

### Operation Pairing and Backfill
- **D-07:** New events must satisfy strict operation pairing: started/terminal pairs share `operation_id`, every operation has at most one terminal event, retry attempts use new `operation_id` plus valid `parent_operation_id` and incremented `attempt`.
- **D-08:** Historical/backfill rows that cannot be reliably paired must not be inferred from timestamp/order. Preserve them as independent operations and expose safe provenance such as `pairing_status="unresolved"` in V3 projection metadata.

### Replay API, Read-Switch, and Trace Fallback
- **D-09:** Add `/api/v1/agent-runs/{run_id}/replay` as an event-store-first V3 replay endpoint. Keep `/api/v1/agent-runs/{run_id}/trace` on the existing legacy composition path as rollback fallback.
- **D-10:** `/replay` must always return `replay_event.v3`-shaped timeline entries. Legacy/minimal rows are returned only through V3 projection with provenance such as `source_schema_version` and `pairing_status`; do not mix response schemas.

### Phase 14 Compatibility Cleanup
- **D-11:** Phase 15 should clean replay-facing wording, timeline/API expression, and deprecated markers that could make demo draft creation look like external execution. It should not reopen intent taxonomy or broadly delete `execute_action` / `action_result` compatibility fields unless a replay-facing expression blocks V3 clarity.

### the agent's Discretion
- Exact module names may follow local conventions, but the preferred ownership shape is a new `src/replay/` package for schemas, service, lifecycle, and validators.
- The planner may choose the exact test split under `tests/replay/`, as long as lifecycle matrix, allocator concurrency, operation pairing, redaction/retention, migration contract, and API access/read-switch are all automated.
- The planner may decide whether existing `src/agent/events.py` remains a compatibility wrapper or is moved behind the new service, but new code must not bypass the replay/trace-event service owner.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope and Requirements
- `.planning/ROADMAP.md` — Phase 15 goal, dependencies, mandatory architecture input, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — REPLAY-01, REPLAY-02, REPLAY-03 and phase planning requirements.
- `.planning/STATE.md` — Phase 13/14 handoff notes, SLA scanner disabled gate, and Phase 14 compatibility cleanup marker.

### Phase 15 Planning Inputs
- `.planning/phases/15-replay-event-contract/15-RESEARCH.md` — Current implementation inventory, contract targets, validation architecture, and risks.
- `.planning/phases/15-replay-event-contract/15-PATTERNS.md` — Code patterns for ORM/migrations, replay service, router access, trace fallback, and tests.
- `.planning/phases/15-replay-event-contract/15-VALIDATION.md` — Nyquist validation map and required test surfaces.

### Normative Architecture and Contract
- `docs/phase-13-17-architecture-plan.md` — Phase 15 target, required restructure, deletion/quarantine rules, and gate tests.
- `docs/contract-spec.md` §17.2 — Minimal Event Envelope, full ReplayEventV3, bounded-loop replay, operation pairing, allocator, and redaction requirements.
- `docs/contract-spec.md` §17.6 — `/replay` response, ordering/completeness, and access-control rules.
- `docs/contract-spec.md` §17.7 — Redaction and retention rules.
- `docs/contract-spec.md` §18.4 — `agent_trace_events` target schema, constraints, indexes, and transition strategy.

### Prior Phase Context
- `.planning/phases/10-state-lifecycle-routing-migration/10-CONTEXT.md` — Tool/RAG event classification, `redacted_payload.iteration`, bounded loop guardrails, and Phase 15 pairing handoff.
- `.planning/phases/12-session-memory/12-CONTEXT.md` — Session memory authority/fallback boundaries and memory event deferral to Phase 15 replay.
- `.planning/phases/13-approval-state-machine/13-CONTEXT.md` — Approval event additions, `approval_events.replay_event_id`, `respond`/`edit` refs, and SLA scanner gate.
- `.planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md` — Demo action draft event surface, `/trace` draft outcome projection, and Phase 15 compatibility cleanup handoff.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/events.py` — Current minimal event type registry, redaction guard, advisory-lock sequence allocator, and `emit_event()` helper.
- `src/db/models.py` — Current `AgentTraceEvent`, `ApprovalEvent.replay_event_id`, and action draft persistence models.
- `src/db/migrations/versions/006_agent_trace_events.py` — Base `agent_trace_events` table migration.
- `src/repositories/trace_repo.py` — Legacy `/trace` timeline composition that remains rollback fallback.
- `src/api/routers/traces.py` — Existing `/trace` access-control and `ApiResponse` route pattern.
- `src/approvals/events.py` — Approval event helper that links approval events to trace events.
- `src/actions/service.py` — `action_draft_created` minimal event emission with safe refs.
- `src/agent/nodes/investigate.py` and `src/agent/nodes/memory_write.py` — Current tool/RAG and memory event emitters.

### Established Patterns
- API routers should stay thin and call domain services.
- Persistence changes use SQLAlchemy models plus Alembic migrations.
- Existing migration strategy prefers nullable expand steps that preserve old rows.
- Tests use pytest/pytest-asyncio with DB-backed async fixtures and exact JSON assertions.
- Cross-tenant trace reads return 404; same-tenant non-owner non-supervisor reads return 403.

### Integration Points
- Add replay schemas/service/lifecycle validators under `src/replay/` or an equivalent clearly owned package.
- Route `/api/v1/agent-runs/{run_id}/replay` through `src/api/routers/traces.py` or a closely related router while preserving `/trace`.
- Service-owned append/projection must remain compatible with existing Phase 12/13/14 event emitters.
- Migration must extend `agent_trace_events` without rewriting old minimal rows into fabricated V3 facts.

</code_context>

<specifics>
## Specific Ideas

- `/replay` is the new V3 audit contract. `/trace` remains the rollback/debug fallback and should keep existing tests green.
- Every `/replay` event should be shaped as V3 even when sourced from old minimal rows; use provenance instead of mixed schemas.
- `pairing_status="unresolved"` is acceptable for historical/backfilled rows when pairing cannot be proven.
- Phase 15 should prevent demo draft replay from being mistaken for real external execution, but should avoid broad taxonomy churn.

</specifics>

<deferred>
## Deferred Ideas

- Active SLA scanner enablement is deferred to a named post-Phase 15 phase after replay/allocator gates are proven.
- Phase 17 owns external execution, outbox, reconciliation, compensation, `action_execution_*` event families, and external worker allocator concurrency tests.
- Broad deletion of `execute_action` / `action_result` compatibility fields is out of scope unless a replay-facing expression blocks V3 clarity.
- Phase 16 owns long-term/case memory identity, tombstones, review workflow, and memory retrieval predicates.

</deferred>

---

*Phase: 15-replay-event-contract*
*Context gathered: 2026-06-16*
