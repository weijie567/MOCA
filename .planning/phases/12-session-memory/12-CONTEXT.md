# Phase 12: Session Memory - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 12` with Codex fallback defaults after interactive picker was unavailable

<domain>
## Phase Boundary

Phase 12 implements PostgreSQL-backed same-thread session memory for safe short-term continuity. It owns the `session_memories` persistence contract, version CAS, deterministic merge behavior, same-thread/user/tenant isolation, safe active slot inheritance, read-switch/fallback telemetry, and negative tests proving session memory is not policy evidence.

This phase is intentionally narrow. It must not implement long-term memory, case memory, `memory_identity.v1`, tombstones, embeddings, asynchronous memory extraction, review workflow, trusted approval lifecycle, action safety snapshots, action execution, or external side effects. Those remain owned by later phases.

</domain>

<decisions>
## Implementation Decisions

### Persistence Boundary and Schema
- **D-01:** PostgreSQL is the authoritative store for Phase 12 session memory. Redis must not be used as authoritative session memory; if introduced at all, Redis may only be a non-authoritative short-TTL helper with Postgres fallback and no correctness dependency.
- **D-02:** Add a `session_memories` table with unique active scope `(tenant_id, user_id, thread_id)` and `version int not null default 1`. The table must carry the spec-owned fields: `schema_version`, `active_slots_json`, `session_summary`, `unresolved_questions_json`, `last_intent`, `last_business_context_refs_json`, `last_run_id`, `expires_at`, timestamps, and `deleted_at`.
- **D-03:** `active_slots_json` must use the typed `session_slots.v1` envelope. Every inheritable slot must preserve value plus metadata such as source, source run, updated/expires timestamps, compatible intents, and enough identity metadata to prove tenant/user/thread scope.
- **D-04:** Session summary is lightweight continuity only. It may describe current troubleshooting context or missing information, but must not store policy conclusions, risk decisions, approval decisions, action authorization, durable preferences, or case precedent.

### Read and Write Timing
- **D-05:** `session_memory_load` remains a registered graph node before slot extraction. It should replace the Phase 10 empty adapter with a MemoryService read path that returns an empty, observable fallback view when disabled or unavailable.
- **D-06:** Slot completeness uses current explicit validated slots first, then compatible non-expired session slots. Current-turn explicit values always override inherited session values.
- **D-07:** Persisted session writes happen after the run has enough validated state to safely update continuity, not inside intent classification. Planning may choose the exact graph placement, but writes must be after slot extraction/resolution and must never block the user response on best-effort summary enrichment.
- **D-08:** Memory write candidates for Phase 12 are limited to session slots, unresolved questions, last intent, lightweight session summary, and last business context refs. Long-term/case memory candidates are out of scope.

### CAS and Conflict Semantics
- **D-09:** Every session-memory update must use version CAS or row locking with version validation. Silent last-write-wins is forbidden.
- **D-10:** On CAS miss, MemoryService must reload latest state and run a deterministic merge. If deterministic merge cannot preserve safety, it must return an explicit conflict/fallback result instead of overwriting.
- **D-11:** Deterministic merge precedence is current-turn explicit validated slots, then compatible non-expired existing session slots, then no inherited value. Conflicting current-turn explicit slots from different runs must not be merged silently.
- **D-12:** CAS conflict tests are blocking for Phase 12. Tests must prove concurrent same-thread updates do not lose `active_slots_json`, `session_summary`, `unresolved_questions_json`, `last_intent`, or `last_business_context_refs_json`.

### Safe Slot Inheritance
- **D-13:** Inherited slots may help pass `route_after_slots` only when tenant, user, and thread match; the slot is fresh; the slot is compatible with the current intent; and the current turn did not provide a conflicting explicit slot.
- **D-14:** Inherited slots must remain distinguishable from explicit current-turn input. They cannot be treated as direct user confirmation for policy evidence, risk, approval, or action safety requirements.
- **D-15:** High-risk action targets cannot execute from stale, incompatible, or unconfirmed inherited slots alone. The flow must reload current business context and policy evidence and may require clarification.
- **D-16:** Cross-thread, cross-user, and cross-tenant isolation tests are blocking. Same-thread continuity must pass without leaking memory across any other scope.

### Observability, Disable/Fallback, and Evidence Boundary
- **D-17:** Session memory must have a disable/read-switch path that falls back to the current empty adapter behavior: `continuity_claimed=False`, no inherited slots, and observable telemetry.
- **D-18:** Memory unavailable, disabled, stale, incompatible, or conflict fallback must not break ordinary routing. The graph should continue with current-turn slots and clarify when required slots remain missing.
- **D-19:** Session memory references/results must not be assignable to KnowledgeService `EvidenceRefV1`. KnowledgeService remains the only producer of policy evidence used for grounding, approval/action evidence, and later snapshot contracts.
- **D-20:** Phase 12 must add negative tests proving session memory cannot satisfy policy evidence, risk, approval, action authorization, or recommendation citation requirements.

### the agent's Discretion
- Exact module/file names under `src/memory/`, repository method names, event helper names, and test fixture organization may follow existing codebase conventions.
- Planning may decide whether session writes are implemented as a dedicated `memory_write` graph node or as a post-response/finalizer service hook, as long as the write timing, CAS, fallback, and replay/event ownership rules above are preserved.
- Exact slot TTL defaults and summary length limits may be set during planning/evaluation, but stale slot exclusion and explicit override semantics are not optional.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Normative Memory and State Contracts
- `docs/contract-spec.md` Section 13.1-13.2 - Working memory vs session memory boundary, `session_slots.v1`, deterministic inheritance rules, CAS miss behavior, and session-summary restrictions.
- `docs/contract-spec.md` Section 18.1 - `session_memories` table shape, active unique scope, version CAS, deterministic merge precedence, and memory schema/index constraints.
- `docs/contract-spec.md` Sections 9.3-9.5 - Graph node/router order including `session_memory_load`, `slot_extraction`, `route_after_slots`, and the memory-is-not-evidence boundary.
- `docs/contract-spec.md` Section 10.1 - AgentState lifecycle fields for `active_slots`, `session_memory`, `last_business_context_refs`, memory write candidates/results, and reset/merge rules.
- `docs/contract-spec.md` Section 12.8 - Redis boundary: Redis cannot be authoritative memory and Postgres CAS remains the correctness boundary.

### Phase and Migration Inputs
- `docs/agent-architecture-phase-decomposition.md` - Phase 12 boundary, dependencies on Phases 10/11, schema ownership, acceptance gates, Redis exclusion, and Phase 16 deferrals.
- `docs/migration-plan.md` - Phase 12 migration row and rollback statement: disable session memory and fall back to empty memory behavior.
- `docs/eval-test-plan.md` - Session-memory path expectations in golden flows and required memory-related eval coverage.
- `.planning/REQUIREMENTS.md` - SESSION-01, SESSION-02, SESSION-03 and planning requirements for coverage matrix, migration ownership, rollback, and eval gates.

### Prior Phase Context
- `.planning/phases/10-state-lifecycle-routing-migration/10-CONTEXT.md` - Phase 10 empty session-memory adapter, slot/router foundation, and state lifecycle constraints.
- `.planning/phases/10-state-lifecycle-routing-migration/10-05-SUMMARY.md` - Live graph wiring summary: `session_memory_load` exists as empty adapter with `continuity_claimed=False`.
- `.planning/phases/11-intent-clarification/11-CONTEXT.md` - Phase 11 slot, clarification, and ordinary-chat boundaries; candidate slots are hints only and real session continuity is Phase 12.
- `.planning/phases/11-intent-clarification/11-03-SUMMARY.md` - Route/slot behavior requiring trusted session continuity metadata before inherited slots can satisfy completeness.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/nodes/session_memory_load.py` - Existing empty adapter to replace or extend; currently returns `{"active_slots": {}, "source": "empty_adapter", "continuity_claimed": False}`.
- `src/agent/routing.py` - `resolve_slots_for_completeness` already requires trusted session metadata before inheriting slots and routes missing required slots to clarification.
- `src/agent/state.py` - AgentState already has persistent `active_slots`, `last_intent`, `last_business_context_refs`, and per-turn `session_memory`.
- `src/agent/graph.py` - `session_memory_load` is already registered between intent classification and slot extraction.
- `src/db/models.py` - Existing SQLAlchemy model patterns for tenant/user/thread scoped tables, `AgentRun`, `AgentTraceEvent`, and versioned entities.

### Established Patterns
- Database access should go through repository/service boundaries, not raw SQL inside graph nodes.
- Router tests should remain pure state-only tests with no DB, LLM, network, or service calls.
- Nodes append trace steps and should preserve enough observable fallback information for run inspection.
- Existing tests use pytest/pytest-asyncio, fake LLM seams, direct state fixtures, and API/integration tests for graph behavior.

### Integration Points
- Add `src/memory/` service/schemas/repository modules or an equivalent package following the KnowledgeService and BusinessToolService facade pattern.
- Add an Alembic migration and ORM model for `session_memories`.
- Wire MemoryService read into `session_memory_load` while preserving empty fallback behavior.
- Add a write path after safe slot resolution/final response handling so same-thread future turns can inherit allowed slots.
- Extend routing/node/API/integration tests to cover same-thread continuity, isolation, CAS conflict, stale slot exclusion, explicit override, disable fallback, and memory-is-not-policy-evidence.

</code_context>

<specifics>
## Specific Ideas

- Keep Phase 12 demonstrable: a user can refer to "that order/refund" in the same tenant/user/thread only when Phase 12 has a fresh compatible slot from prior explicit input.
- Treat `session_memory_load` as a safety filter, not a convenience cache. If metadata is missing or questionable, the planner should prefer clarification over inheritance.
- Preserve the current Phase 10 empty adapter as the rollback/fallback behavior.

</specifics>

<deferred>
## Deferred Ideas

- Long-term memory, case memory, `memory_identity.v1`, tombstones, embeddings, async extraction, and review workflow remain Phase 16.
- Trusted approval `needs_info` resume, approval version CAS, approval revision invalidation, and ActionSafetySnapshot remain Phase 13.
- Demo action draft/executor behavior remains Phase 14.
- ReplayEventV3 full read API, redaction/retention, and lifecycle finalizer remain Phase 15, though Phase 12 should register/emit memory-related events on the Phase 10 base envelope if planning confirms that is required.

</deferred>

---

*Phase: 12-session-memory*
*Context gathered: 2026-06-14*
