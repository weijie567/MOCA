# Phase 54: Slot Resolution Gate Cutover - Context

**Gathered:** 2026-07-06T23:29:53Z
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 54 delivers the CAGM-05 graph boundary cutover from the active legacy `extract_slots` node and `route_after_slots` router to canonical `slot_resolution_gate` and `route_after_slot_resolution`.

The phase owns slot satisfaction semantics after `contextual_intent_resolve`: current-turn candidate slots, same-thread inherited session slots, invalidation, stale/conflict/incompatible rejection, missing required slots, trace-visible provenance, and deterministic routing to clarification or the next investigation/memory path.

It does not implement Phase 55 `memory_context_load`, Phase 56 `recommendation_generation`, Phase 57 `risk_gate`, or Phase 58 final no-debt cleanup. `slot_extraction` must not become a registered graph node.

</domain>

<decisions>
## Implementation Decisions

### Graph Boundary
- **D-01:** The active registered graph node must be `slot_resolution_gate`, not `extract_slots`.
- **D-02:** `contextual_intent_resolve` routes slot-required intents to `slot_resolution_gate`.
- **D-03:** The active graph uses a canonical `route_after_slot_resolution` router.
- **D-04:** `route_after_slots` may remain only as a compatibility delegate to `route_after_slot_resolution`; it must not be the active graph router after cutover.
- **D-05:** Until Phase 55, the canonical slot router may still route memory-needed paths to the current `long_term_memory_retrieve` compatibility destination. Do not introduce active `memory_context_load` in Phase 54.

### Slot Extraction Versus Slot Resolution
- **D-06:** Slot candidate extraction is an internal capability of `contextual_intent_resolve` / `slot_resolution_gate`, not a registered graph node.
- **D-07:** The existing LLM-based `extract_slots` implementation can be reused internally or through a wrapper only if the registered node key and trace/eval/replay boundary are `slot_resolution_gate`.
- **D-08:** Deterministic slot resolution remains authoritative. LLM output can propose candidates but cannot mark required slots satisfied, inherit session slots, override invalidation, or choose graph routes.

### Provenance Contract
- **D-09:** `slot_resolution_gate` must output trace-visible provenance for at least: explicit current-turn slots, inherited session slots, invalidated slots, stale slots, incompatible slots, resolved slots, missing required slots, and reason codes.
- **D-10:** Preserve downstream compatibility fields required by current consumers: `extracted_slots`, `active_slots`, `active_slot_metadata`, `missing_required_slots` / routing hints where applicable.
- **D-11:** Keep the Phase 53 WR-01 fix invariant: pre-intent inherited slots are not pre-authorized for incompatible actual intents, while intentional cross-intent business-ID compatibility remains valid for `order_id`, `refund_case_id`, and `ticket_id`.

### Fail-Closed Routing
- **D-12:** Unknown intent, required-slot policy mismatch, stale inherited slots, incompatible inherited slots, invalidated slots, missing required slots, malformed state, or router exceptions must route to `clarification_gate`.
- **D-13:** The slot gate may route to `investigate` only when required slots are satisfied by current-turn slots or accepted trusted session slots.
- **D-14:** The slot gate may route to `long_term_memory_retrieve` only for the existing Phase 55-owned compatibility path when reviewed/long-term memory context is explicitly requested by routing hints.

### Compatibility Ledger
- **D-15:** Record active `extract_slots` node deletion as closed by Phase 54 once the graph no longer registers it.
- **D-16:** Retain `src/agent/nodes/extract_slots.py` and `route_after_slots` only if needed for internal/import/test compatibility, with explicit owner, reason, trace projection, validation coverage, and delete phase no later than Phase 58.
- **D-17:** Promote `slot_resolution_gate` and `route_after_slot_resolution` to runtime graph vocabulary entries. `extract_slots` and `route_after_slots` become compatibility aliases only.

### Planning Granularity
- **D-18:** Plan Phase 54 as multiple small plans, not one broad plan. Expected split: node/contract/unit work, graph/router/baseline cutover, and vocabulary/docs/validation closeout.
- **D-19:** The graph/router/policy path-map changes must be atomic in one plan so active route values and active graph destinations cannot drift.

### the agent's Discretion
- Exact schema name for the new provenance payload is left to the planner, as long as it is explicit, trace-visible, and covered by tests.
- Whether to factor deterministic slot resolution helpers from `src/agent/routing.py` into a dedicated module is left to the planner, provided public compatibility and route behavior stay stable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Migration Charter
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` — Source hierarchy, exact 15-node canonical graph, temporary compatibility policy, authority matrix, validation matrix, and Phase 54 ownership of `slot_resolution_gate`.
- `.planning/ROADMAP.md` — Phase 54 goal, CAGM-05 requirement, dependency on Phase 53, and success criteria.
- `.planning/REQUIREMENTS.md` — CAGM-05 requirement status and mapping.

### Target Contract
- `docs/contract-spec.md` §9.0-9.3 — Target graph vocabulary, registered node/router semantics, slot-resolution gate transition, and fail-closed routing contract.
- `docs/target-agent-platform-architecture-plan.md` §6.1 and slot gate discussion — Human-readable target architecture and provenance expectations for `slot_resolution_gate`.

### Current Source Facts
- `docs/current-langgraph-architecture.md` — Current Phase 53 graph snapshot and compatibility ledger showing `extract_slots` as Phase 54-owned.
- `src/agent/graph.py` — Active registered nodes and conditional edge path maps.
- `src/agent/routing.py` — Current `route_after_contextual_intent`, `route_after_slots`, slot invalidation, and slot resolution helper behavior.
- `src/agent/intent_policy.py` — `SlotPolicyRegistry`, `SlotInheritanceContext`, and shared `slot_intent_compatible()` compatibility logic.
- `src/agent/nodes/extract_slots.py` — Current legacy node combining LLM slot extraction, deterministic resolution, and trace projection.
- `src/agent/graph_vocabulary.py` — Current runtime/compat trace projection entries for `extract_slots`, `slot_resolution_gate`, `route_after_slots`, and `route_after_slot_resolution`.

### Upstream Phase Evidence
- `.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-VERIFICATION.md` — Confirms `extract_slots` is the explicit Phase 54 deferred compatibility node.
- `.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-UAT.md` — Confirms Phase 53 plus WR-01 review-fix closeout before Phase 54.
- `.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-REVIEW-FIX.md` — Documents the pre-intent inherited slot compatibility fix that Phase 54 must preserve.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/nodes/extract_slots.py`: Existing LLM structured-output prompt path, prompt assembly, trace helper, and `resolve_slots_with_metadata()` call can be reused internally if the active registered node becomes `slot_resolution_gate`.
- `src/agent/routing.py`: Existing deterministic `resolve_slots_with_metadata()`, `missing_required_slots()`, invalidation detection, and `_route_after_slots()` behavior are the starting point for canonical slot gate semantics.
- `src/agent/intent_policy.py`: `SlotPolicyRegistry.accepts_inherited_slot()` and `slot_intent_compatible()` already encode tenant/user/thread/freshness/intent compatibility rules, including Phase 53 WR-01 protection.
- `tests/agent/test_required_slots.py`: Existing unit coverage for missing slots, trusted session inheritance, invalidation, stale/incompatible slots, current-turn overrides, and WR-01 regression.
- `tests/architecture/graph_baseline.py`: Existing migration baseline explicitly maps `extract_slots -> slot_resolution_gate` with delete phase Phase 54.

### Established Patterns
- Active graph cutovers are validated by architecture static tests plus graph smoke tests.
- New canonical names are represented in `src/agent/graph_vocabulary.py` as `runtime`; retained legacy names are `compatibility_alias` with reason codes and deletion phase.
- Current routers fail closed through wrapper functions that constrain return values to allowlists.
- Planning artifacts use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` and `UV_CACHE_DIR=/tmp/uv-cache uv run ruff ...`; bare `pytest` is invalid in MOCA.

### Integration Points
- `src/agent/graph.py`: replace `add_node("extract_slots", ...)` with `add_node("slot_resolution_gate", ...)` and update conditional path maps.
- `src/agent/routing.py`: make `route_after_slot_resolution` the active slot router; keep `route_after_slots` as compatibility delegate only if retained.
- `src/agent/nodes/clarification_gate.py`: consumes missing required slot state/routing hints and should remain compatible.
- `src/agent/nodes/session_context_load.py`: produces same-thread slot continuity consumed by the slot gate.
- `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/agent/test_intent_routing.py`, `tests/agent/test_session_memory_integration.py`, and architecture tests must move from active `extract_slots` assertions to active `slot_resolution_gate` assertions.

</code_context>

<specifics>
## Specific Ideas

- Treat `slot_resolution_gate` as the audit/replay boundary, not a cosmetic rename.
- Keep `extract_slots` visible only as implementation detail or historical compatibility while Phase 54 is active.
- Preserve Phase 53's slot inheritance fix exactly: unknown-intent session slots require post-intent revalidation.

</specifics>

<deferred>
## Deferred Ideas

- `memory_context_load` graph cutover remains Phase 55.
- `recommendation_generation` graph naming and RAG/claim status alignment remain Phase 56.
- `risk_gate` and approval canonicalization remain Phase 57.
- Final deletion of all retained compatibility aliases and exact 15-node no-debt gate remains Phase 58.

</deferred>

---

*Phase: 54-slot-resolution-gate-cutover*
*Context gathered: 2026-07-06T23:29:53Z*
