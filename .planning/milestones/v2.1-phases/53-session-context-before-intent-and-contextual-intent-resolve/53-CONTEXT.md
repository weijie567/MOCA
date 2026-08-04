# Phase 53: Session Context Before Intent and Contextual Intent Resolve - Context

**Gathered:** 2026-07-06T10:21:54Z
**Status:** Ready for planning
**Mode:** Auto-selected conservative defaults via `$gsd-phase-autopilot 53`

<domain>
## Phase Boundary

Phase 53 delivers CAGM-04: move same-thread `session_context_load` before intent resolution, and cut over the active graph intent node from legacy `classify_intent` to canonical `contextual_intent_resolve`.

The phase must preserve Phase 52 `safety_pre_route` ownership, keep LLM output candidate-only, and make deterministic policy/router boundaries authoritative. It must not implement Phase 54 `slot_resolution_gate` provenance/freshness cutover, Phase 55 `memory_context_load`, later recommendation/risk node renames, or Phase 58 final no-debt cleanup.

</domain>

<decisions>
## Implementation Decisions

### Graph cutover shape

- **D-01:** Active entry order must become `receive_request -> safety_pre_route -> session_context_load -> contextual_intent_resolve`.
- **D-02:** `route_after_safety` safe / `safety_sensitive` continuation should route to `session_context_load`, not `classify_intent`.
- **D-03:** `session_context_load` should be registered under the canonical node key and should have a fixed edge to `contextual_intent_resolve`.
- **D-04:** `classify_intent` must no longer be an active registered graph node or route destination after Phase 53.
- **D-05:** `session_memory_load` may remain as an internal compatibility wrapper around `session_context_load` only if needed for tests/import compatibility, but it must not stay active in the graph. Any retained wrapper must be ledgered with a delete phase.

### Contextual intent node authority

- **D-06:** Implement active `contextual_intent_resolve` as the canonical runtime node. It may reuse deterministic helper/adaptor code currently colocated with `classify_intent`, but the active node name, trace step, graph vocabulary projection, and `llm_outputs` owner must be `contextual_intent_resolve`.
- **D-07:** `contextual_intent_resolve` may call the LLM for structured intent/operation/required-slot/candidate-slot suggestions, but it must not choose graph routes, mark slots complete, load long-term/case memory, verify evidence, lower action risk, draft actions, or call tools.
- **D-08:** The node must use an explicit AgentState adapter for structured output. It must write only validated intent fields, `required_slots`, `candidate_slots`, `routing_hints`, task-plan/deferred-step fields, trace, and eval metadata. It must not merge raw structured output wholesale into state.
- **D-09:** `classification_trace.pre_route_decision` duplicate ownership must be removed in Phase 53. Phase 52 already made `safety_pre_route` the runtime owner of pre-route decisions.
- **D-10:** Any remaining legacy `intent_classification` / `classify_intent` output mirrors are allowed only as explicitly ledgered compatibility artifacts with owner, reason, validation, trace projection, and delete phase. They must not be required by active graph routing.

### Same-thread session context before intent

- **D-11:** `session_context_load` should run before any intent LLM call and should load only same-thread session context through the existing `MemoryContextService` / `SessionMemoryBundleService` path.
- **D-12:** Pre-intent `session_context_load` must tolerate `current_intent=None`; it must not depend on an already-classified intent to load same-thread context.
- **D-13:** Same-thread pending-slot short replies, such as a bare order/refund/ticket identifier after a prior clarification, should be resolved using `session_context` / legacy-compatible `session_memory` without loading long-term memory, case memory, business facts, RAG, approval, or action services.
- **D-14:** Current-turn explicit identifiers override inherited session slots. Existing merchant-scope filtering and explicit-current-turn merge behavior in `session_context_load.py` should be preserved.

### Post-intent routing compatibility

- **D-15:** Phase 53 should introduce/rename the router boundary to `route_after_contextual_intent` for the active canonical node.
- **D-16:** Because Phase 54 owns `slot_resolution_gate`, Phase 53 may route slot-required paths to legacy `extract_slots` as a temporary compatibility destination, not to `session_memory_load`.
- **D-17:** Direct/final, clarification, and investigate routes must remain deterministic and fail closed. Any unregistered route, exception, approval-decision ordinary-chat value, or low-confidence/clarification state should land in `clarification_gate` or safe final response per existing policy.
- **D-18:** Active graph route maps, architecture baselines, and graph vocabulary tests must prove `classify_intent` and `session_memory_load` are no longer active graph nodes while `extract_slots` remains explicitly deferred to Phase 54.

### Validation and compatibility ledger

- **D-19:** Update architecture debt and current architecture docs to move Phase 52 compatibility rows forward: `classify_intent` active graph compatibility should be closed by Phase 53; any remaining helper/module/trace compatibility must have a named delete phase.
- **D-20:** Keep Phase 58 no-debt gates as guardrails only. Do not remove every legacy alias or all compatibility vocabulary in Phase 53.
- **D-21:** Tests must cover graph order, router maps, vocabulary projection, same-thread short-reply context behavior, no downstream memory/tool/action authority from intent, and no `classification_trace.pre_route_decision` duplication.

### Folded Todos

None. `gsd-sdk query todo.match-phase 53` returned no matching pending todos.

### the agent's Discretion

Planner may decide whether the new node is implemented as a new module that imports shared helper functions from `classify_intent.py`, or by extracting helpers into a shared intent module, as long as active graph registration, trace vocabulary, and state output ownership are canonical. Planner may choose the smallest safe compatibility ledger surface, but must not leave unrecorded legacy dependencies.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract and sequencing

- `.planning/ROADMAP.md` — Phase 53 goal, CAGM-04 success criteria, dependency on Phase 52, and explicit Phase 54+ boundaries.
- `.planning/REQUIREMENTS.md` — CAGM-04 requirement traceability and pending status.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` — Canonical 15-node graph target, current-to-target matrix, authority matrix, temporary compatibility policy, and required downstream phase order.
- `.planning/phases/52-safety-pre-route-node/52-VERIFICATION.md` — Verified Phase 52 baseline and compatibility ledger that Phase 53 must close or carry forward explicitly.

### Accepted graph contract

- `docs/contract-spec.md` §9.0-9.5 — Canonical graph vocabulary, node list, target order, node contract table, and router contract table.
- `docs/contract-spec.md` §9 intent adapter rules around `contextual_intent_resolve` — Structured LLM output must go through explicit AgentState adapter; `candidate_slots` are not final slots.
- `docs/current-langgraph-architecture.md` — Current source graph snapshot and Phase 52 compatibility rows that must be updated by Phase 53.

### Architecture debt and guardrails

- `.planning/ARCHITECTURE-DEBT.md` — Agent Graph / intent recognition debt ledger and Phase 52 remaining risk naming Phase 53 cleanup.
- `tests/architecture/graph_baseline.py` — Current and target graph node/migration constants.
- `tests/architecture/test_canonical_graph_baseline.py` — Static graph baseline and route-map guardrails.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/agent/nodes/session_context_load.py` already implements canonical `session_context_load(...)`, using `MemoryContextService` and writing `session_context`, `session_context_bundle`, `session_context_load_status`, `session_memory`, trace, and legacy bundle projection.
- `src/agent/nodes/session_memory_load.py` is already only a compatibility wrapper around `session_context_load(...)` with `node_name="session_memory_load"`.
- `src/agent/nodes/classify_intent.py` contains the existing structured LLM call, intent adapter helpers, deterministic pre-route/short-reply guards, `IntentResultV3` conversion, task-plan normalization, and trace writing. These are likely reusable, but active graph ownership must move to `contextual_intent_resolve`.
- `src/agent/routing.py` already centralizes router wrappers and fail-closed behavior. It currently routes safety safe-path to `classify_intent` and intent slot-needed paths to `session_memory_load`; Phase 53 must change both active routes.
- `src/agent/graph_vocabulary.py` already has canonical runtime vocabulary entries for `session_context_load` and compatibility aliases for `classify_intent` / `intent_classification` / `session_memory_load`.

### Established Patterns

- Graph changes require both runtime wiring changes in `src/agent/graph.py` and static guard updates in `tests/architecture/graph_baseline.py` / `tests/architecture/test_canonical_graph_baseline.py`.
- MOCA node tests use deterministic fakes and focused async tests; graph tests use `FakeLLM`, `MemorySaver`, fake tool platform, and monkeypatches.
- Router wrappers catch exceptions and fail closed to known safe routes. New/renamed routers should preserve that pattern.
- Trace/vocabulary changes require docs and tests, not only code edits.
- MOCA validation commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, never bare `pytest` or bare `python -m pytest`.

### Integration Points

- `src/agent/graph.py` node registration and conditional path maps.
- `src/agent/routing.py` `SAFETY_ROUTES`, `INTENT_ROUTES`, `_route_after_safety`, and new/renamed contextual intent router.
- `src/agent/state.py` fields for `session_context`, `session_memory`, `primary_intent`, `requested_operation`, `intent_confidence`, `required_slots`, `candidate_slots`, `routing_hints`, `llm_outputs`, and trace.
- `src/memory/context_service.py::load_session_context_for_intent(...)` accepts `current_intent: str | None = None`, which supports pre-intent loading if tests lock that behavior.
- Existing session-memory and graph tests around inherited active slots, stale slots, and same-thread context should be migrated or expanded to the canonical node order.

</code_context>

<specifics>
## Specific Ideas

- Auto-selected default: use the smallest safe cutover that makes active graph vocabulary canonical now, while keeping Phase 54 slot-gate and Phase 58 no-debt cleanup out of scope.
- Treat Phase 52's `classification_trace.pre_route_decision` duplicate as a required deletion target for Phase 53.
- Treat `extract_slots` as the intentional post-intent legacy compatibility boundary until Phase 54.

</specifics>

<deferred>
## Deferred Ideas

- Phase 54: `slot_resolution_gate` active graph cutover, slot provenance, freshness, stale/conflict/invalidation output, and final `extract_slots` active-node removal.
- Phase 55: `memory_context_load` naming and reviewed long-term/case/CWC context cutover after slot resolution.
- Phase 58: final no-debt cleanup of all active legacy node names, dual routes, aliases, and residual compatibility vocabulary.

</deferred>

---

*Phase: 53-session-context-before-intent-and-contextual-intent-resolve*
*Context gathered: 2026-07-06T10:21:54Z*
