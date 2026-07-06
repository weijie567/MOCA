# Phase 53: Session Context Before Intent and Contextual Intent Resolve - Research

**Researched:** 2026-07-06 [VERIFIED: environment current_date]
**Domain:** Canonical Agent Graph migration, same-thread session context, contextual intent routing [VERIFIED: .planning/ROADMAP.md:392-403]
**Confidence:** HIGH for source-verified current implementation and Phase 53 boundaries; MEDIUM for exact plan split because planner may adjust task grouping. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-53]

<user_constraints>
## User Constraints (from CONTEXT.md)

All bullets in this section are copied from Phase 53 context and are binding planning constraints. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:16-63]

### Locked Decisions

#### Graph cutover shape

- **D-01:** Active entry order must become `receive_request -> safety_pre_route -> session_context_load -> contextual_intent_resolve`.
- **D-02:** `route_after_safety` safe / `safety_sensitive` continuation should route to `session_context_load`, not `classify_intent`.
- **D-03:** `session_context_load` should be registered under the canonical node key and should have a fixed edge to `contextual_intent_resolve`.
- **D-04:** `classify_intent` must no longer be an active registered graph node or route destination after Phase 53.
- **D-05:** `session_memory_load` may remain as an internal compatibility wrapper around `session_context_load` only if needed for tests/import compatibility, but it must not stay active in the graph. Any retained wrapper must be ledgered with a delete phase.

#### Contextual intent node authority

- **D-06:** Implement active `contextual_intent_resolve` as the canonical runtime node. It may reuse deterministic helper/adaptor code currently colocated with `classify_intent`, but the active node name, trace step, graph vocabulary projection, and `llm_outputs` owner must be `contextual_intent_resolve`.
- **D-07:** `contextual_intent_resolve` may call the LLM for structured intent/operation/required-slot/candidate-slot suggestions, but it must not choose graph routes, mark slots complete, load long-term/case memory, verify evidence, lower action risk, draft actions, or call tools.
- **D-08:** The node must use an explicit AgentState adapter for structured output. It must write only validated intent fields, `required_slots`, `candidate_slots`, `routing_hints`, task-plan/deferred-step fields, trace, and eval metadata. It must not merge raw structured output wholesale into state.
- **D-09:** `classification_trace.pre_route_decision` duplicate ownership must be removed in Phase 53. Phase 52 already made `safety_pre_route` the runtime owner of pre-route decisions.
- **D-10:** Any remaining legacy `intent_classification` / `classify_intent` output mirrors are allowed only as explicitly ledgered compatibility artifacts with owner, reason, validation, trace projection, and delete phase. They must not be required by active graph routing.

#### Same-thread session context before intent

- **D-11:** `session_context_load` should run before any intent LLM call and should load only same-thread session context through the existing `MemoryContextService` / `SessionMemoryBundleService` path.
- **D-12:** Pre-intent `session_context_load` must tolerate `current_intent=None`; it must not depend on an already-classified intent to load same-thread context.
- **D-13:** Same-thread pending-slot short replies, such as a bare order/refund/ticket identifier after a prior clarification, should be resolved using `session_context` / legacy-compatible `session_memory` without loading long-term memory, case memory, business facts, RAG, approval, or action services.
- **D-14:** Current-turn explicit identifiers override inherited session slots. Existing merchant-scope filtering and explicit-current-turn merge behavior in `session_context_load.py` should be preserved.

#### Post-intent routing compatibility

- **D-15:** Phase 53 should introduce/rename the router boundary to `route_after_contextual_intent` for the active canonical node.
- **D-16:** Because Phase 54 owns `slot_resolution_gate`, Phase 53 may route slot-required paths to legacy `extract_slots` as a temporary compatibility destination, not to `session_memory_load`.
- **D-17:** Direct/final, clarification, and investigate routes must remain deterministic and fail closed. Any unregistered route, exception, approval-decision ordinary-chat value, or low-confidence/clarification state should land in `clarification_gate` or safe final response per existing policy.
- **D-18:** Active graph route maps, architecture baselines, and graph vocabulary tests must prove `classify_intent` and `session_memory_load` are no longer active graph nodes while `extract_slots` remains explicitly deferred to Phase 54.

#### Validation and compatibility ledger

- **D-19:** Update architecture debt and current architecture docs to move Phase 52 compatibility rows forward: `classify_intent` active graph compatibility should be closed by Phase 53; any remaining helper/module/trace compatibility must have a named delete phase.
- **D-20:** Keep Phase 58 no-debt gates as guardrails only. Do not remove every legacy alias or all compatibility vocabulary in Phase 53.
- **D-21:** Tests must cover graph order, router maps, vocabulary projection, same-thread short-reply context behavior, no downstream memory/tool/action authority from intent, and no `classification_trace.pre_route_decision` duplication.

### Claude's Discretion

Planner may decide whether the new node is implemented as a new module that imports shared helper functions from `classify_intent.py`, or by extracting helpers into a shared intent module, as long as active graph registration, trace vocabulary, and state output ownership are canonical. Planner may choose the smallest safe compatibility ledger surface, but must not leave unrecorded legacy dependencies.

### Deferred Ideas (OUT OF SCOPE)

- Phase 54: `slot_resolution_gate` active graph cutover, slot provenance, freshness, stale/conflict/invalidation output, and final `extract_slots` active-node removal.
- Phase 55: `memory_context_load` naming and reviewed long-term/case/CWC context cutover after slot resolution.
- Phase 58: final no-debt cleanup of all active legacy node names, dual routes, aliases, and residual compatibility vocabulary.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAGM-04 | `session_context_load` runs before contextual intent resolution, and `contextual_intent_resolve` replaces active `classify_intent` graph routing while keeping LLM output as candidate-only and deterministic policy/route boundaries authoritative. [VERIFIED: .planning/REQUIREMENTS.md:56] | Current graph/router/node facts identify the cutover points; target state and validation map lock graph order, route values, node authority, same-thread context behavior, and legacy compatibility limits. [VERIFIED: src/agent/graph.py:282-319; src/agent/routing.py:37-85; src/agent/nodes/classify_intent.py:309-440] |
</phase_requirements>

## Summary

Phase 53 is a narrow but cross-cutting graph migration: change the active main-chain order from Phase 52's `safety_pre_route -> classify_intent -> session_memory_load` path to `safety_pre_route -> session_context_load -> contextual_intent_resolve`, while leaving the Phase 54 `extract_slots`/slot gate cutover out of scope. [VERIFIED: .planning/ROADMAP.md:392-403; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-47]

The implementation work touches four ownership areas: graph wiring, deterministic routers/policy route values, contextual intent node ownership, and validation/docs/debt artifacts. [VERIFIED: src/agent/graph.py:282-319; src/agent/routing.py:37-85; src/agent/nodes/classify_intent.py:309-440; src/agent/graph_vocabulary.py:49-99]

**Primary recommendation:** split Phase 53 into three plans: canonical contextual intent/router contract, graph/session-context cutover, and compatibility/docs/validation closeout. [VERIFIED: AGENTS.md:68-76; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-53]

## Project Constraints (from AGENTS.md / CLAUDE.md)

- MOCA validation commands must use the project environment entrypoint, for example `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; results from unscoped Pytest entrypoints are invalid for MOCA verification. [VERIFIED: AGENTS.md:24-29; CLAUDE.md:22-27]
- When plans modify tool/RAG/memory/intent core subsystems, they must update `.planning/ARCHITECTURE-DEBT.md` with verified facts and remaining risk. [VERIFIED: AGENTS.md:13-21; CLAUDE.md:13-20]
- Phase-level planning must split large service-boundary work into multiple numbered plans when the work spans ownership domains, waves, or verification gates. [VERIFIED: AGENTS.md:68-76]
- `docs/contract-spec.md` is a target contract and not proof of current implementation; plans must distinguish contract target from observed source facts. [VERIFIED: AGENTS.md:111-120; docs/contract-spec.md:1-5]
- Phase 53 must not implement Phase 54 `slot_resolution_gate`, Phase 55 `memory_context_load`, or Phase 58 final no-debt cleanup. [VERIFIED: .planning/ROADMAP.md:408-483; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:12]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Main graph node order | API / Backend | Validation tests | `build_graph` owns StateGraph node registration and edge maps, while architecture tests lock active node/route baselines. [VERIFIED: src/agent/graph.py:278-319; tests/architecture/test_canonical_graph_baseline.py:19-125] |
| Safety continuation route | API / Backend | Intent policy | `route_after_safety` is the deterministic backend router that currently returns `classify_intent`; Phase 53 changes this continuation to `session_context_load`. [VERIFIED: src/agent/routing.py:80-85; src/agent/routing.py:192-213; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-23] |
| Same-thread session context | API / Backend | Database / Storage | `session_context_load` calls `MemoryContextService.load_session_context_for_intent(...)`, which delegates to `SessionMemoryBundleService` for same-thread context. [VERIFIED: src/agent/nodes/session_context_load.py:76-120; src/memory/context_service.py:65-121] |
| Contextual intent resolution | API / Backend | LLM provider | The intent node may call an LLM for structured candidate output, but deterministic policy/routers own active route decisions and downstream authority boundaries. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33; src/agent/nodes/classify_intent.py:706-736] |
| Slot-required post-intent path | API / Backend | Phase 54 future work | Phase 53 may route slot-required paths to legacy `extract_slots`; `slot_resolution_gate` provenance/freshness/invalidation is deferred to Phase 54. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47; .planning/ROADMAP.md:408-419] |
| Trace/vocabulary projection | API / Backend | API stream/UI labels | `graph_vocabulary.py` currently projects legacy/canonical graph names, and API streaming has node message labels for runtime node names. [VERIFIED: src/agent/graph_vocabulary.py:49-99; src/api/routers/agent_runs.py:58-58] |

## Current Implementation Facts

### Active Graph And Routing

| Area | Current Fact | Planning Relevance |
|------|--------------|--------------------|
| Registered intent node | `build_graph` registers `classify_intent` as the active intent graph node with an LLM retry policy. [VERIFIED: src/agent/graph.py:282-286] | Remove active registration or replace with `contextual_intent_resolve`; helper reuse cannot leave `classify_intent` as a graph node. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:24-33] |
| Registered session node | `build_graph` registers `session_memory_load` and places it after `classify_intent`. [VERIFIED: src/agent/graph.py:284-319] | Register `session_context_load` before contextual intent; keep `session_memory_load` only as non-active compatibility if still imported by tests. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:23-25] |
| Safety route map | `route_after_safety` currently accepts `classify_intent`, `clarification_gate`, and `final_response`; `_route_after_safety` returns `classify_intent` for `none` and `safety_sensitive` dispositions. [VERIFIED: src/agent/routing.py:37-85; src/agent/routing.py:192-213] | Change safe/safety-sensitive continuation to `session_context_load` and change the allowlist so the wrapper does not fail closed on the new route. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-23] |
| Intent route map | `route_after_intent` currently validates against `INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "session_memory_load"}`. [VERIFIED: src/agent/routing.py:37-78] | Introduce active `route_after_contextual_intent` with no `session_memory_load` route value; slot-required paths should target `extract_slots` until Phase 54. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] |
| Policy route values | Slot-bearing intents in `INTENT_POLICY_REGISTRY` currently have `initial_route="session_memory_load"`, and `IntentRouteLiteral` includes `session_memory_load`. [VERIFIED: src/agent/intent_policy.py:15-15; src/agent/intent_policy.py:141-188] | Planner must include policy/route-value edits or a deterministic route translation; graph-only edits will leave active routes pointing at removed nodes. [VERIFIED: src/agent/routing.py:291-297; src/agent/graph.py:309-319] |
| Slot compatibility node | `extract_slots` remains an active graph node after `session_memory_load` and routes through `route_after_slots` to clarification, investigate, or long-term memory. [VERIFIED: src/agent/graph.py:319-328] | Keep `extract_slots` active as the Phase 54 compatibility destination; do not create active `slot_resolution_gate` in Phase 53. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] |

### Session Context Nodes

| Area | Current Fact | Planning Relevance |
|------|--------------|--------------------|
| Canonical function exists | `session_context_load(...)` defaults its `node_name` to `session_context_load`. [VERIFIED: src/agent/nodes/session_context_load.py:31-43] | Graph can register the canonical function directly without inventing a new memory loader. [VERIFIED: src/agent/nodes/session_context_load.py:31-43] |
| Pre-intent tolerant service API | `MemoryContextService.load_session_context_for_intent(...)` accepts `current_intent: str | None = None`. [VERIFIED: src/memory/context_service.py:65-74] | Phase 53 can call the existing service before intent is known. [VERIFIED: src/agent/nodes/session_context_load.py:88-94] |
| Same-thread source | The service delegates same-thread context loading to `SessionMemoryBundleService.load_session_memory_bundle(...)`. [VERIFIED: src/memory/context_service.py:90-98] | Phase 53 should not load long-term/case memory before intent. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:37-40] |
| State writes | `session_context_load` writes `session_context`, `session_context_bundle`, `session_context_load_status`, legacy `session_memory`, trace steps, and optionally `session_memory_bundle`. [VERIFIED: src/agent/nodes/session_context_load.py:302-328] | Preserve canonical state plus legacy projection for compatibility; update active node name in graph and trace expectations. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:23-25] |
| Compatibility wrapper | `session_memory_load` is already a wrapper that calls `session_context_load(..., node_name="session_memory_load")`. [VERIFIED: src/agent/nodes/session_memory_load.py:16-29] | Retain only if tests/imports need it and record delete phase; do not keep it in active graph. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:24-25] |
| Current-turn merge behavior | `session_context_load` merges current-turn `candidate_slots`/`extracted_slots` over inherited slots and filters cross-merchant or out-of-scope slots. [VERIFIED: src/agent/nodes/session_context_load.py:166-209; src/agent/nodes/session_context_load.py:271-283] | Preserve this behavior, but do not treat pre-intent `session_context_load` as the Phase 54 slot gate. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:40-47] |

### Intent Node And Vocabulary

| Area | Current Fact | Planning Relevance |
|------|--------------|--------------------|
| Current LLM node owner | `classify_intent` calls the structured-output LLM and appends trace steps with node `"classify_intent"`. [VERIFIED: src/agent/nodes/classify_intent.py:695-736] | Active trace node must become `contextual_intent_resolve`. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33] |
| Current output owner | Current intent outputs are stored under `llm_outputs["intent_classification"]`. [VERIFIED: src/agent/nodes/classify_intent.py:427-440; src/agent/nodes/classify_intent.py:563-574; src/agent/nodes/classify_intent.py:829-840] | Active `llm_outputs` owner must be canonical or any mirror must be ledgered compatibility, not routing authority. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33] |
| Explicit adapter exists | `intent_result_to_state(...)` maps `IntentResultV3` into validated state fields, policy-derived required slots, candidate slots, task-plan fields, routing hints, and trace. [VERIFIED: src/agent/nodes/classify_intent.py:309-440] | Reuse or extract this adapter pattern; do not wholesale merge raw structured output. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:30-31] |
| Duplicate pre-route trace | Current classifier writes `classification_trace["pre_route_decision"]` in LLM, deterministic, and fallback paths. [VERIFIED: src/agent/nodes/classify_intent.py:405-410; src/agent/nodes/classify_intent.py:541-546; src/agent/nodes/classify_intent.py:793-798] | Phase 53 must remove this duplicate ownership from canonical contextual intent traces; `safety_pre_route` owns pre-route decisions. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:32-33] |
| Short-reply handling | `_deterministic_context_update(...)` handles `active_flow_state.kind == "pending_required_slot"` and identifier-like short replies without the LLM. [VERIFIED: src/agent/nodes/classify_intent.py:584-620] | Preserve this behavior under canonical contextual intent, using already-loaded session context/flow state without long-term memory. [VERIFIED: .planning/ROADMAP.md:399-403] |
| Vocabulary status | `graph_vocabulary.py` currently marks `classify_intent` and `intent_classification` as aliases to `contextual_intent_resolve`, but also marks `contextual_intent_resolve` itself as `compatibility_alias`; `route_after_contextual_intent` is also currently `compatibility_alias`. [VERIFIED: src/agent/graph_vocabulary.py:49-51; src/agent/graph_vocabulary.py:98-99] | Make active canonical node/router vocabulary runtime while keeping only intentionally ledgered legacy aliases. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33] |

### Target Contract Versus Current Fact

- The accepted target contract says the initial canonical order is `receive_request -> safety_pre_route -> session_context_load -> contextual_intent_resolve`. [CITED: docs/contract-spec.md:474-481]
- The accepted target contract says `session_context_load` has a fixed route to `contextual_intent_resolve`. [CITED: docs/contract-spec.md:583-584]
- The accepted target contract says `contextual_intent_resolve` writes intent fields, required slots, routing hints, and candidate slots, with no side effects. [CITED: docs/contract-spec.md:630-633]
- The accepted target contract still allows legacy `extract_slots`/`route_after_slots` during migration before `slot_resolution_gate`. [CITED: docs/contract-spec.md:486-489]
- These contract statements are target-state guidance, not proof that source already implements them. [CITED: docs/contract-spec.md:1-5]

## Planning Implications

### Plan Granularity Recommendation

Do not write one large Phase 53 plan. The phase crosses graph wiring, routing/policy, node ownership, tests, documentation, and architecture debt, and MOCA planning rules require splitting this kind of service-boundary work. [VERIFIED: AGENTS.md:68-76; src/agent/graph.py:282-319; src/agent/routing.py:37-85; src/agent/nodes/classify_intent.py:309-440]

Recommended plan split:

| Plan | Ownership | Wave | Scope | Exit Criteria |
|------|-----------|------|-------|---------------|
| 53-01 | Contextual intent node and router contract | Wave 1 | Create/activate `contextual_intent_resolve`, canonical trace/`llm_outputs` ownership, explicit adapter, no `classification_trace.pre_route_decision`, and `route_after_contextual_intent` with no active `session_memory_load` route. [VERIFIED: src/agent/nodes/classify_intent.py:309-440; src/agent/routing.py:37-85] | Node/router unit tests prove candidate-only LLM output, fail-closed routing, short-reply deterministic path, and no duplicated pre-route trace. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:1-420] |
| 53-02 | Active graph cutover | Wave 2 | Register `session_context_load` and `contextual_intent_resolve`; wire `safety_pre_route -> session_context_load -> contextual_intent_resolve`; remove active `classify_intent` and `session_memory_load`; keep `extract_slots` active. [VERIFIED: src/agent/graph.py:282-319] | Architecture baseline and graph tests prove active order and route maps. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19-170; tests/agent/test_graph.py:1-1111] |
| 53-03 | Compatibility ledger, docs, and validation closeout | Wave 3 | Update graph vocabulary, current architecture docs, `.planning/ARCHITECTURE-DEBT.md`, API stream labels if needed, and artifact scans for active legacy node/route values. [VERIFIED: src/agent/graph_vocabulary.py:49-99; docs/current-langgraph-architecture.md:72-90; .planning/ARCHITECTURE-DEBT.md:42-56; src/api/routers/agent_runs.py:58-58] | Focused Phase 53 command set passes and compatibility rows name delete phases. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:51-53] |

### Sequencing Notes

- Router/policy route values should be changed before or with graph path-map changes so removed active nodes are not still returned by deterministic routers. [VERIFIED: src/agent/routing.py:37-85; src/agent/intent_policy.py:141-188]
- Graph baseline tests should be updated in the same plan as graph wiring because they assert exact active node and route maps. [VERIFIED: tests/architecture/graph_baseline.py:31-136; tests/architecture/test_canonical_graph_baseline.py:19-125]
- Documentation and architecture debt updates belong in their own closeout plan because Phase 53 explicitly changes core graph/intent/memory subsystem debt. [VERIFIED: AGENTS.md:13-21; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:51-53]

## Target State for Phase 53

### Active Graph Order

The active graph after Phase 53 should route:

```text
START
  -> receive_request
  -> safety_pre_route
  -> session_context_load
  -> contextual_intent_resolve
  -> route_after_contextual_intent
```

This order is required by Phase 53 decisions and roadmap success criteria. [VERIFIED: .planning/ROADMAP.md:399-403; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-47]

### Active Node Names

| Node Name | Phase 53 Status | Notes |
|-----------|-----------------|-------|
| `receive_request` | Active | Already active entry node. [VERIFIED: src/agent/graph.py:282-299] |
| `safety_pre_route` | Active | Already active after Phase 52. [VERIFIED: src/agent/graph.py:282-304; .planning/phases/52-safety-pre-route-node/52-VERIFICATION.md:36-43] |
| `session_context_load` | Active canonical | Must replace active `session_memory_load` in graph and trace expectations. [VERIFIED: src/agent/nodes/session_context_load.py:31-43; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:23-25] |
| `contextual_intent_resolve` | Active canonical | Must replace active `classify_intent` graph node, trace step, vocabulary runtime entry, and primary `llm_outputs` owner. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33] |
| `extract_slots` | Active temporary compatibility | Keep as slot-required destination until Phase 54. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] |
| `long_term_memory_retrieve` | Active temporary compatibility | Phase 55 owns memory context naming and reviewed memory cutover. [VERIFIED: .planning/ROADMAP.md:424-435] |
| `generate_recommendation` / `assess_risk_and_approval` | Active temporary compatibility | Later graph migration phases own these renames. [VERIFIED: .planning/ROADMAP.md:440-467] |

### Allowed Compatibility Surfaces

- `session_memory_load` may remain as an import/test compatibility wrapper around `session_context_load`, but it must not be registered in the active graph or returned by active route maps. [VERIFIED: src/agent/nodes/session_memory_load.py:16-29; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:24-25]
- `classify_intent.py` helper code may be reused or extracted, but active graph registration, trace vocabulary, state output ownership, and `llm_outputs` ownership must be canonical. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:59-61]
- Legacy `intent_classification` or `classify_intent` output mirrors may remain only if documented with owner, reason, validation, trace projection, and delete phase. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:32-33]
- `extract_slots` remains an active temporary destination for slot-required paths until Phase 54. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47]

### Explicitly Out Of Scope

- Do not implement active `slot_resolution_gate`, slot provenance/freshness/stale/conflict/invalidation semantics, or final `extract_slots` removal. [VERIFIED: .planning/ROADMAP.md:408-419]
- Do not implement active `memory_context_load` or reviewed long-term/case memory naming cutover. [VERIFIED: .planning/ROADMAP.md:424-435]
- Do not remove every legacy alias or final no-debt compatibility vocabulary. [VERIFIED: .planning/ROADMAP.md:472-483; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:51-52]
- Do not give the intent LLM authority to choose graph routes, mark slots complete, load reviewed memory, verify evidence, lower risk, draft actions, or call tools. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-31]

## Standard Stack

This phase should use the existing MOCA backend stack; no new library is needed. [VERIFIED: pyproject.toml:1-55]

| Library / Tool | Version / Constraint | Purpose | Why Standard For This Phase |
|----------------|----------------------|---------|-----------------------------|
| Python | 3.12.13 in project `uv` environment; project requires `>=3.12`. [VERIFIED: local env probe 2026-07-06; pyproject.toml:3-7] | Runtime and tests | MOCA source uses Python 3.12 APIs and project commands already run through `uv`. [VERIFIED: AGENTS.md:24-29] |
| LangGraph | 1.1.10 in project environment; project dependency is `langgraph>=0.4`. [VERIFIED: local env probe 2026-07-06; pyproject.toml:9-15] | StateGraph node/edge runtime | Existing graph is built with `StateGraph(AgentState)`. [VERIFIED: src/agent/graph.py:278-280] |
| LangChain OpenAI | 1.2.1 in project environment; project dependency is `langchain-openai>=0.3`. [VERIFIED: local env probe 2026-07-06; pyproject.toml:9-15] | Structured intent LLM | Current classifier uses `.with_structured_output(IntentResultV3)`. [VERIFIED: src/agent/nodes/classify_intent.py:706-706] |
| Pytest / pytest-asyncio | pytest 9.0.3 and pytest-asyncio 1.3.0 in project environment. [VERIFIED: local env probe 2026-07-06] | Focused unit/graph validation | Existing tests cover architecture baselines, graph routing, graph integration, and async nodes. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19-170; tests/agent/test_graph.py:1-1111] |
| Ruff | 0.15.12 in project environment. [VERIFIED: local env probe 2026-07-06] | Static lint sanity check | Project dev dependencies include Ruff. [VERIFIED: pyproject.toml:43-48] |

## Architecture Patterns

### System Architecture Diagram

```text
User turn
  -> receive_request
     resets per-turn graph state and projects active flow
  -> safety_pre_route
     deterministic unsafe / unsupported / approval-chat screen
     | unsafe / unsupported / clarification -> clarification_gate or final_response
     | safe / safety_sensitive -> session_context_load
  -> session_context_load
     loads same-thread session_context only
     writes session_context + legacy session_memory projection
  -> contextual_intent_resolve
     deterministic short-reply guards and structured candidate LLM output
     writes intent fields + candidate_slots + routing_hints
  -> route_after_contextual_intent
     deterministic route decision
     | direct -> final_response
     | unclear / low confidence -> clarification_gate
     | no slots required -> investigate
     | slots required -> extract_slots (Phase 54 compatibility)
```

All active route decisions in the diagram are deterministic backend router decisions; LLM output is candidate input only. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-47]

### Recommended Project Structure

```text
src/agent/nodes/contextual_intent_resolve.py  # canonical active node or thin wrapper over extracted helpers
src/agent/nodes/classify_intent.py            # retained helper/compat surface only if ledgered
src/agent/routing.py                          # route_after_contextual_intent and route allowlists
src/agent/graph.py                            # active graph registration and path maps
src/agent/graph_vocabulary.py                 # runtime/compat projection updates
tests/agent/test_nodes/test_contextual_intent_resolve.py
tests/architecture/graph_baseline.py
tests/architecture/test_canonical_graph_baseline.py
```

This structure follows existing graph/node/router/test boundaries. [VERIFIED: src/agent/graph.py:278-319; src/agent/routing.py:37-85; src/agent/graph_vocabulary.py:41-103; tests/architecture/graph_baseline.py:31-136]

### Pattern: Canonical Wrapper With Explicit Adapter

Use a canonical active node name even if implementation logic is extracted from `classify_intent.py`; route, trace, vocabulary, and `llm_outputs` ownership must be canonical. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33]

### Pattern: Deterministic Router Wrapper

Existing router wrappers catch exceptions and fail closed to safe routes; the new contextual router should preserve that pattern. [VERIFIED: src/agent/routing.py:72-90]

### Pattern: Canonical State Plus Compatibility Projection

`session_context_load` already writes canonical `session_context` plus legacy `session_memory`; Phase 53 should use that established compatibility projection rather than duplicate session memory logic. [VERIFIED: src/agent/nodes/session_context_load.py:302-328]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Same-thread context load | A new pre-intent memory loader | Existing `session_context_load` plus `MemoryContextService.load_session_context_for_intent(...)`. [VERIFIED: src/agent/nodes/session_context_load.py:31-120; src/memory/context_service.py:65-121] | Existing service accepts `current_intent=None` and already writes canonical plus compatibility state. [VERIFIED: src/memory/context_service.py:65-74; src/agent/nodes/session_context_load.py:302-328] |
| Slot gate/provenance | A new Phase 53 slot-resolution system | Legacy `extract_slots` and existing `route_after_slots` until Phase 54. [VERIFIED: src/agent/graph.py:319-328; .planning/ROADMAP.md:408-419] | Phase 54 owns active `slot_resolution_gate` and slot provenance/freshness/invalidation. [VERIFIED: .planning/ROADMAP.md:408-419] |
| Pre-route safety ownership | A classifier-owned pre-route trace or duplicate detector path | Phase 52 `safety_pre_route` state owner plus router hints. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-VERIFICATION.md:36-43; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:32-33] | Duplicate `classification_trace.pre_route_decision` is an explicit Phase 53 deletion target. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:42-56] |
| LLM route authority | Letting structured LLM output decide graph route or active slots | Explicit AgentState adapter plus deterministic policy/router. [VERIFIED: src/agent/nodes/classify_intent.py:309-440; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-31] | CAGM-04 requires LLM output candidate-only and deterministic boundaries authoritative. [VERIFIED: .planning/REQUIREMENTS.md:56] |

## Risk / Threat Model Inputs

Each Phase 53 plan should include these risks in its threat model:

| Risk | STRIDE / Failure Class | Why It Matters | Required Mitigation |
|------|------------------------|----------------|---------------------|
| Active route points to removed node | Reliability / fail-open graph drift | `route_after_intent` and intent policy currently return `session_memory_load` for slot-bearing intents. [VERIFIED: src/agent/routing.py:37-78; src/agent/intent_policy.py:141-188] | Update route allowlists/policy route values and assert active route maps have no `classify_intent` or `session_memory_load`. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] |
| LLM gains routing or slot-completion authority | Tampering / elevation of privilege | Phase 53 allows structured candidate output but not route, slot satisfaction, memory, evidence, risk, action, or tool authority. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-31] | Keep deterministic router and required-slot policy as the only route/satisfaction authorities; test forbidden state writes. [VERIFIED: src/agent/nodes/classify_intent.py:76-89; src/agent/nodes/classify_intent.py:309-440] |
| Same-thread short reply calls reviewed memory | Information disclosure / authority confusion | Same-thread pending-slot replies must resolve from session context without long-term/case/business/RAG/approval/action services. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:37-40] | Add tests for bare identifiers after prior clarification proving no long-term/case memory path before intent. [VERIFIED: tests/agent/test_session_memory_integration.py:129-177] |
| Duplicate pre-route trace persists | Repudiation / audit ambiguity | Current classifier writes `classification_trace.pre_route_decision` in multiple paths. [VERIFIED: src/agent/nodes/classify_intent.py:405-410; src/agent/nodes/classify_intent.py:541-546; src/agent/nodes/classify_intent.py:793-798] | New contextual trace omits the duplicate and references safety trace/state only where needed. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:32-33] |
| Cross-merchant inherited slot leak | Information disclosure | `session_context_load` has merchant-scope and explicit-current-turn filtering that must be preserved. [VERIFIED: src/agent/nodes/session_context_load.py:166-209] | Keep existing filter path and retain tests for current-turn override and wrong tenant/thread/expired memory. [VERIFIED: tests/agent/test_session_memory_integration.py:153-251] |
| Phase 54 scope creep | Planning / migration drift | Slot provenance/freshness/stale/conflict/invalidation belongs to Phase 54. [VERIFIED: .planning/ROADMAP.md:408-419] | Route slot-required paths to legacy `extract_slots`; document `extract_slots` as remaining compatibility. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Pytest 9.0.3 with pytest-asyncio 1.3.0 in the project `uv` environment. [VERIFIED: local env probe 2026-07-06] |
| Config file | `pyproject.toml` contains Pytest async settings and dev dependencies. [VERIFIED: pyproject.toml:43-55] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` |
| Full focused command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` |
| Lint command | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture` |

If the planner keeps the legacy node test filename instead of creating `tests/agent/test_nodes/test_contextual_intent_resolve.py`, replace that path in the focused command with the updated canonical intent test file. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:1-420]

### Phase Requirements To Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAGM-04 | Active graph order is `safety_pre_route -> session_context_load -> contextual_intent_resolve`. [VERIFIED: .planning/ROADMAP.md:399-403] | Architecture/static + graph integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | Existing files need updates. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19-170; tests/agent/test_graph.py:1-1111] |
| CAGM-04 | `route_after_safety` safe/safety-sensitive paths route to `session_context_load`; contextual intent route maps omit active `session_memory_load`. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-47] | Router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py -q --tb=short` | Existing file needs updates. [VERIFIED: tests/test_graph_routing.py:260-310] |
| CAGM-04 | `contextual_intent_resolve` uses candidate-only LLM output and deterministic router/policy authority. [VERIFIED: .planning/REQUIREMENTS.md:56] | Node/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` | New or renamed file needed. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:1-420] |
| CAGM-04 | Same-thread pending-slot short replies resolve through session context/legacy session memory without reviewed memory. [VERIFIED: .planning/ROADMAP.md:399-403] | Integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_session_memory_integration.py tests/agent/test_session_memory_load.py -q --tb=short` | Existing files need updates. [VERIFIED: tests/agent/test_session_memory_integration.py:129-320; tests/agent/test_session_memory_load.py:223-278] |
| CAGM-04 | Graph vocabulary projects canonical active runtime names and retained aliases explicitly. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33] | Vocabulary/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py -q --tb=short` | Existing file needs updates. [VERIFIED: tests/agent/test_graph_vocabulary.py:13-27] |
| CAGM-04 | No active graph registration/route destination remains for `classify_intent` or `session_memory_load`; `extract_slots` remains deferred. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] | Artifact scan | Commands below | Scan-only coverage. [VERIFIED: tests/architecture/graph_baseline.py:31-136] |

### Artifact Scan Coverage

Run these scans after implementation and review any hits against the allowed compatibility ledger:

```bash
rg -n 'add_node\("classify_intent"|add_node\("session_memory_load"|\"classify_intent\": \"classify_intent\"|\"session_memory_load\": \"session_memory_load\"' src/agent/graph.py tests/architecture/graph_baseline.py
rg -n 'classification_trace.*pre_route_decision|pre_route_decision": pre_route|pre_route_decision": pre_route\.model_dump' src/agent/nodes tests/agent
rg -n '"session_memory_load"|route_after_intent|classify_intent' src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py tests/architecture/graph_baseline.py tests/agent
```

The third scan can have allowed compatibility/helper hits; the acceptance criterion is no active graph registration, active path-map destination, or active router value to `classify_intent` or `session_memory_load`. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:24-47]

### Sampling Rate

- Per task commit: run the narrow command for the touched area, using the `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` entrypoint. [VERIFIED: AGENTS.md:24-29]
- Per wave merge: run the quick command from this section. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19-170; tests/test_graph_routing.py:260-310]
- Phase gate: run the full focused command, Ruff, and artifact scans before `/gsd-verify-work`. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:51-53]

### Wave 0 Gaps

- [ ] `tests/agent/test_nodes/test_contextual_intent_resolve.py` - covers canonical active intent node name, trace owner, `llm_outputs` owner, candidate-only state writes, deterministic short-reply path, and no `classification_trace.pre_route_decision`. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:1-420]
- [ ] `tests/architecture/graph_baseline.py` - update active baseline node set and conditional edge maps from Phase 52 to Phase 53. [VERIFIED: tests/architecture/graph_baseline.py:31-136]
- [ ] `tests/test_graph_routing.py` - update safety and contextual intent router expectations. [VERIFIED: tests/test_graph_routing.py:260-310]
- [ ] `tests/agent/test_graph_vocabulary.py` - update runtime/compat status for `contextual_intent_resolve` and `route_after_contextual_intent`. [VERIFIED: tests/agent/test_graph_vocabulary.py:13-27]

## Implementation Landmines

1. `classification_trace.pre_route_decision` is written in three classifier paths and must not leak into canonical contextual intent traces. [VERIFIED: src/agent/nodes/classify_intent.py:405-410; src/agent/nodes/classify_intent.py:541-546; src/agent/nodes/classify_intent.py:793-798]
2. `route_after_intent` and `INTENT_POLICY_REGISTRY` still return or allow `session_memory_load`; changing only `graph.py` will produce route-map drift or fail-closed behavior. [VERIFIED: src/agent/routing.py:37-78; src/agent/intent_policy.py:141-188]
3. `session_context_load` runs before contextual intent after Phase 53, but its current-turn override reads `candidate_slots` and `extracted_slots`; `receive_request` clears these per-turn fields before intent. [VERIFIED: src/agent/nodes/session_context_load.py:271-283; src/agent/nodes/receive_request.py:45-80] Therefore the planner should preserve the override path for later slot stages instead of moving Phase 54 slot extraction into `session_context_load`. [VERIFIED: .planning/ROADMAP.md:408-419]
4. Same-thread short replies currently depend on `active_flow_state` projected by `receive_request` and classifier helper logic; the contextual intent plan must preserve this behavior under the canonical node name. [VERIFIED: src/agent/nodes/receive_request.py:15-42; src/agent/nodes/classify_intent.py:584-620]
5. The existing API stream label map contains a `classify_intent` message; runtime stream/UI labels may need a canonical `contextual_intent_resolve` label or an explicit ledger decision. [VERIFIED: src/api/routers/agent_runs.py:58-58]
6. `graph_vocabulary.py` currently marks `contextual_intent_resolve` and `route_after_contextual_intent` as `compatibility_alias`, so tests must prove they become active runtime surfaces in Phase 53. [VERIFIED: src/agent/graph_vocabulary.py:49-51; src/agent/graph_vocabulary.py:98-99]
7. `extract_slots` is still active by design in Phase 53; artifact scans must not treat `extract_slots` as a failure until Phase 54. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47]
8. Do not use `docs/contract-spec.md` as proof that the source is already canonical; it is target contract guidance. [CITED: docs/contract-spec.md:1-5]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `agent_steps.node_name` and `agent_trace_events.node_name` store historical node names; repositories/API project trace node names through vocabulary helpers. [VERIFIED: src/db/models.py:1178-1188; src/db/models.py:1529-1529; src/repositories/trace_repo.py:68-68; src/api/routers/traces.py:109-109] | No historical data migration recommended for Phase 53; update projection/vocabulary and keep historical rows readable. [VERIFIED: src/agent/graph_vocabulary.py:49-99] |
| Live service config | No local MOCA/LangGraph service process with graph node names was found during process scan; only transient research scan commands matched the searched names. [VERIFIED: local process scan 2026-07-06] | No live service patch identified; planner should still avoid assuming production services are changed by source edits. [VERIFIED: local process scan 2026-07-06] |
| OS-registered state | `launchctl list` had `com.moca.study.*` jobs, but the graph node-name scan found no `classify_intent`, `session_memory_load`, or `contextual_intent_resolve` registration. [VERIFIED: local launchctl scan 2026-07-06] | No OS re-registration action identified for Phase 53. [VERIFIED: local launchctl scan 2026-07-06] |
| Secrets/env vars | Scans of `.env`, `.env.example`, Docker, compose, and `pyproject.toml` found no graph node-name environment variables. [VERIFIED: local file scan 2026-07-06] | No secret/env var rename identified. [VERIFIED: local file scan 2026-07-06] |
| Build artifacts | Python `__pycache__` files exist for old node modules; no installed package artifact requiring migration was found in the scan. [VERIFIED: local find scan 2026-07-06] | No manual artifact migration; bytecode regenerates from source. [VERIFIED: local find scan 2026-07-06] |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | MOCA test/lint entrypoint | yes | 0.11.2 | None needed. [VERIFIED: local env probe 2026-07-06] |
| Python | Runtime/tests | yes | 3.12.13 via `uv run` | None needed. [VERIFIED: local env probe 2026-07-06] |
| LangGraph | Graph build/runtime tests | yes | 1.1.10 | None needed. [VERIFIED: local env probe 2026-07-06] |
| LangChain OpenAI | Structured intent node | yes | 1.2.1 | Existing tests use fakes/monkeypatches for focused coverage. [VERIFIED: local env probe 2026-07-06; tests/agent/test_graph.py:1-1111] |
| Pytest / pytest-asyncio | Validation | yes | 9.0.3 / 1.3.0 | None needed. [VERIFIED: local env probe 2026-07-06] |
| Ruff | Lint | yes | 0.15.12 | None needed. [VERIFIED: local env probe 2026-07-06] |

**Missing dependencies with no fallback:** None found for research and focused planning validation. [VERIFIED: local env probe 2026-07-06]

**Missing dependencies with fallback:** External LLM calls are not required for focused tests because existing graph/node tests use fakes or monkeypatches. [VERIFIED: tests/agent/test_graph.py:1-1111]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct change | Phase 53 does not alter user authentication boundaries. [VERIFIED: .planning/ROADMAP.md:392-403] |
| V3 Session Management | yes | Use existing same-thread session context service and preserve tenant/user/thread scoping. [VERIFIED: src/memory/context_service.py:65-121; tests/agent/test_session_memory_integration.py:179-320] |
| V4 Access Control | yes | Preserve merchant-scope filtering and trusted-context filtering in `session_context_load`. [VERIFIED: src/agent/nodes/session_context_load.py:166-209] |
| V5 Input Validation | yes | Structured LLM output must go through explicit adapter and policy-derived required slots. [VERIFIED: src/agent/nodes/classify_intent.py:309-440] |
| V6 Cryptography | no direct change | Phase 53 does not alter cryptographic primitives. [VERIFIED: .planning/ROADMAP.md:392-403] |

### Known Threat Patterns For This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM output treated as route authority | Elevation of privilege / tampering | Candidate-only LLM output plus deterministic `route_after_contextual_intent`. [VERIFIED: .planning/REQUIREMENTS.md:56; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-31] |
| Cross-thread or cross-merchant slot reuse | Information disclosure | Existing tenant/user/thread lookup and merchant-scope filtering. [VERIFIED: src/memory/context_service.py:90-98; src/agent/nodes/session_context_load.py:166-209] |
| Unsafe approval/action text routed as ordinary intent | Spoofing / elevation of privilege | Preserve Phase 52 safety pre-route and fail-closed safety router before session context or intent. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-VERIFICATION.md:36-43; src/agent/routing.py:192-213] |
| Ambiguous short replies over-trusted | Tampering | Deterministic short-reply guards and clarification fallback. [VERIFIED: src/agent/nodes/classify_intent.py:584-658] |

## Common Pitfalls

### Pitfall 1: Graph Cutover Without Router Cutover

**What goes wrong:** active graph removes `session_memory_load`, but deterministic routers still return it. [VERIFIED: src/agent/routing.py:37-78; src/agent/intent_policy.py:141-188]
**How to avoid:** update route allowlists, route function name, policy route values or translation, path maps, and tests in the same wave. [VERIFIED: src/agent/graph.py:300-319; tests/architecture/test_canonical_graph_baseline.py:105-125]

### Pitfall 2: Canonical Node Name But Legacy Trace Owner

**What goes wrong:** runtime graph uses `contextual_intent_resolve`, but traces and `llm_outputs` still say `classify_intent` or `intent_classification` without a compatibility ledger. [VERIFIED: src/agent/nodes/classify_intent.py:427-440; src/agent/nodes/classify_intent.py:726-735]
**How to avoid:** make canonical ownership part of node unit acceptance and ledger any mirror. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33]

### Pitfall 3: Accidentally Implementing Phase 54

**What goes wrong:** Phase 53 creates active `slot_resolution_gate` or implements final slot provenance/freshness/invalidation. [VERIFIED: .planning/ROADMAP.md:408-419]
**How to avoid:** use `extract_slots` as the temporary slot-required destination and document the remaining debt. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47]

### Pitfall 4: Treating Contract Spec As Current Source

**What goes wrong:** plan assumes canonical graph/order already exists because the contract names it. [CITED: docs/contract-spec.md:474-489]
**How to avoid:** use source and tests as current facts; use contract/spec only for target semantics. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:123-139; CITED: docs/contract-spec.md:1-5]

## Code Examples

No new external API pattern is needed for Phase 53; planner should reference existing local patterns instead of adding fresh abstractions. [VERIFIED: src/agent/nodes/session_context_load.py:31-120; src/agent/nodes/classify_intent.py:309-440; src/agent/routing.py:72-90]

Key local patterns:

- Register active graph nodes and conditional edge maps in `src/agent/graph.py`. [VERIFIED: src/agent/graph.py:278-319]
- Use router wrappers that catch exceptions and fail closed. [VERIFIED: src/agent/routing.py:72-90]
- Map structured intent output through an explicit state adapter. [VERIFIED: src/agent/nodes/classify_intent.py:309-440]
- Write canonical session context plus compatibility projection from `session_context_load`. [VERIFIED: src/agent/nodes/session_context_load.py:302-328]

## State Of The Art

| Old Approach | Current Phase 53 Approach | When Changed / Target | Impact |
|--------------|---------------------------|-----------------------|--------|
| `safety_pre_route -> classify_intent` | `safety_pre_route -> session_context_load -> contextual_intent_resolve` | Phase 53 target. [VERIFIED: .planning/ROADMAP.md:392-403] | Same-thread context is available before intent and active graph uses canonical intent node naming. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-47] |
| `classify_intent` owns pre-route copy in `classification_trace` | `safety_pre_route` owns pre-route decision; contextual intent trace omits duplicate. | Phase 52 introduced safety pre-route; Phase 53 removes duplicate. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-VERIFICATION.md:36-43; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:32-33] | Avoids audit ambiguity over which node made safety pre-route decisions. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:42-56] |
| Slot-required intents route to `session_memory_load` | Slot-required intents route to legacy `extract_slots` until Phase 54 | Phase 53 compatibility target. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:44-47] | Removes active session-memory graph node while deferring full slot gate migration. [VERIFIED: .planning/ROADMAP.md:408-419] |

## Assumptions Log

All implementation-relevant current-state claims in this research were verified against local repository files, project planning artifacts, or local environment probes. No `[ASSUMED]` claims are required for planning. [VERIFIED: local repository scan 2026-07-06]

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| None | None | None | None |

## Open Questions (RESOLVED)

1. **Should `llm_outputs["intent_classification"]` remain as a compatibility mirror?**
   - What we know: active owner must become `contextual_intent_resolve`; mirrors are allowed only with explicit owner/reason/validation/delete phase. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33]
   - Decision: `llm_outputs["contextual_intent_resolve"]` is the Phase 53 canonical owner. `llm_outputs["intent_classification"]` is not an active routing or eval authority after Phase 53. Plan 53-01 must update `tests/agent/test_nodes/test_classify_intent.py` so legacy classifier tests no longer require `session_memory_load` routes or classifier-owned `pre_route_decision`. Plan 53-03 must scan for `intent_classification` readers; retain a mirror only if a non-test or historical-reader compatibility need remains, and ledger it with owner, reason, validation, trace projection, and delete phase no later than Phase 58. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:32-33]

2. **Should helper extraction happen in Phase 53 or stay as imports from `classify_intent.py`?**
   - What we know: Phase context allows either new module imports or helper extraction if active graph ownership is canonical. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:59-61]
   - Decision: use the smallest safe implementation that makes the active owner unambiguous. Plan 53-01 should put the canonical active behavior in `src/agent/nodes/contextual_intent_resolve.py`; `src/agent/nodes/classify_intent.py` may remain only as import/test compatibility or a delegating wrapper and must not be required by active graph registration, canonical trace ownership, or primary `llm_outputs` ownership. Broad helper extraction beyond what is needed for canonical ownership is out of scope for Phase 53. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:29-33; .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-PATTERNS.md]

## Sources

### Primary (HIGH confidence)

- `.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md` - locked Phase 53 decisions, discretion, and deferred scope. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:1-141]
- `.planning/ROADMAP.md` - Phase 53 goal, success criteria, and Phase 54/55/58 boundaries. [VERIFIED: .planning/ROADMAP.md:392-486]
- `.planning/REQUIREMENTS.md` - CAGM-04 requirement. [VERIFIED: .planning/REQUIREMENTS.md:56-56]
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - canonical target graph, authority matrix, compatibility policy, and source hierarchy. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:17-250]
- `src/agent/graph.py` - current active graph node and edge wiring. [VERIFIED: src/agent/graph.py:278-319]
- `src/agent/routing.py` - current route allowlists and deterministic routers. [VERIFIED: src/agent/routing.py:37-85; src/agent/routing.py:192-317]
- `src/agent/nodes/session_context_load.py` and `src/memory/context_service.py` - existing session context implementation. [VERIFIED: src/agent/nodes/session_context_load.py:31-439; src/memory/context_service.py:53-281]
- `src/agent/nodes/classify_intent.py` - current intent adapter, LLM call, trace, and short-reply handling. [VERIFIED: src/agent/nodes/classify_intent.py:309-855]
- `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` - graph guardrails and migration baselines. [VERIFIED: tests/architecture/graph_baseline.py:31-136; tests/architecture/test_canonical_graph_baseline.py:19-170]

### Secondary (MEDIUM confidence)

- `docs/contract-spec.md` - accepted target contract, used only for target semantics, not current implementation facts. [CITED: docs/contract-spec.md:1-5; docs/contract-spec.md:474-489; docs/contract-spec.md:630-663]
- `docs/current-langgraph-architecture.md` - current architecture snapshot and Phase 52 compatibility ledger, subject to update in Phase 53. [VERIFIED: docs/current-langgraph-architecture.md:1-90]
- `.planning/ARCHITECTURE-DEBT.md` - graph/intent/memory debt ledger and Phase 52 remaining risk. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:6-56]

### Tertiary (LOW confidence)

- None used. [VERIFIED: local repository scan 2026-07-06]

## Metadata

**Confidence breakdown:**

- Current implementation facts: HIGH - verified against local source and tests. [VERIFIED: src/agent/graph.py:278-319; src/agent/routing.py:37-85; src/agent/nodes/classify_intent.py:309-855]
- Target state: HIGH - locked by Phase 53 context, roadmap, requirements, and Phase 50 SPEC. [VERIFIED: .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-CONTEXT.md:21-53; .planning/ROADMAP.md:392-403; .planning/REQUIREMENTS.md:56-56]
- Plan split: MEDIUM - source-verified ownership boundaries support the split, but planner may choose exact file/task grouping. [VERIFIED: AGENTS.md:68-76]
- Validation architecture: HIGH - verified existing test files and MOCA command rules; one canonical node test file is expected to be added or renamed. [VERIFIED: AGENTS.md:24-29; tests/agent/test_nodes/test_classify_intent.py:1-420]

**Research date:** 2026-07-06 [VERIFIED: environment current_date]
**Valid until:** 2026-08-05 unless Phase 53 or adjacent graph migration phases change first. [VERIFIED: .planning/ROADMAP.md:392-486]
