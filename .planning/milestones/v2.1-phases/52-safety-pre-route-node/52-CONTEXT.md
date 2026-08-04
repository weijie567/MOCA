# Phase 52: Safety Pre-route Node - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Source:** Lightweight `$gsd-discuss-phase 52 --auto` style context pass; no interactive questions.

<domain>
## Phase Boundary

Phase 52 is the first runtime rewiring phase after the Phase 51 canonical graph baseline guardrails. It must extract the current deterministic request-risk / pre-route behavior from the thick `classify_intent` entry into an explicit registered `safety_pre_route` node that runs immediately after `receive_request`.

The phase delivers the active entry path:

```text
START -> receive_request -> safety_pre_route
```

For safe requests, Phase 52 may temporarily continue to the current legacy `classify_intent` node until Phase 53 moves `session_context_load` before intent resolution and cuts over to `contextual_intent_resolve`. Phase 52 must not implement Phase 53, Phase 54, memory cutover, recommendation rename, risk-gate rename, or final no-debt cleanup.

</domain>

<decisions>
## Implementation Decisions

### Graph insertion boundary

- **D-52-01:** Register `safety_pre_route` as a real LangGraph node in `src/agent/graph.py`, immediately after `receive_request`.
- **D-52-02:** Add or expose a deterministic `route_after_safety` router for the new node. It must be side-effect-free and return only registered graph node keys.
- **D-52-03:** In Phase 52, the safe continuation may remain `safety_pre_route -> classify_intent` as temporary compatibility. Do not move `session_context_load` before intent and do not replace `classify_intent` with `contextual_intent_resolve`; those are Phase 53 / CAGM-04.
- **D-52-04:** Any preserved `classify_intent` compatibility must be recorded in the Phase 52 plan with the Phase 50 compatibility metadata: exact legacy surface, canonical owner, reason, trace projection, validation, and delete phase. The expected delete phase is Phase 53.

### Safety responsibility split

- **D-52-05:** Extract only deterministic request-risk pre-route behavior into `safety_pre_route`: current `detect_pre_route(...)` decisions, untrusted approval-chat detection, approval-bypass / approval-like short reply guards, and safety-sensitive request tagging.
- **D-52-06:** `safety_pre_route` must not run the LLM, load session / reviewed memory, query business facts, retrieve or verify policy evidence, evaluate proposed-action risk, create approval state, create action drafts, or execute tools.
- **D-52-07:** Untrusted approval chat and standalone approval/action short replies must fail closed before memory, investigate, approval, or action paths. The default route is `clarification_gate` when the system needs to explain the trusted approval channel; direct refusal through `final_response` is allowed only when the plan gives an explicit deterministic reason and tests it.
- **D-52-08:** Explicit approval-bypass attempts must not proceed to memory, investigate, `approval_gate`, or `action_draft`. They should be represented as a safety disposition and routed to `clarification_gate` or `final_response`.
- **D-52-09:** Ordinary safety-sensitive but supported requests, such as an action analysis request, may be tagged with `pre_route_disposition="safety_sensitive"` and continue to the legacy intent path only if they are not approval-bypass attempts. The pre-route node itself must never produce `proposed_action`, approval state, or action draft fields.
- **D-52-10:** Broad semantic `unsupported` classification remains owned by intent resolution until Phase 53 unless the unsupported case is deterministic and clearly part of request-risk pre-routing. If implementation needs broader unsupported detection in `safety_pre_route`, record it as an explicit MVP scope or spec delta rather than silently expanding the node.

### Trace and state projection

- **D-52-11:** `safety_pre_route` needs its own trace-visible decision record. Downstream planning should choose the smallest compatible state shape, but tests must prove the canonical node emits or projects `safety_pre_route` rather than hiding the decision only inside `intent_classification`.
- **D-52-12:** During compatibility, `classify_intent` may continue to include `pre_route_decision` in `classification_trace`, but this is a migration artifact. The Phase 52 plan must name its owner and Phase 53 cleanup path.
- **D-52-13:** Trace / vocabulary projection should treat the new node as canonical runtime `safety_pre_route`. Any remaining `classify_intent:pre_route` alias must be temporary and covered by tests.

### Validation and guardrails

- **D-52-14:** Update Phase 51 architecture guardrails to reflect the new migration state: `safety_pre_route` is now an active canonical node, while the remaining legacy nodes stay allowed only in migration mode.
- **D-52-15:** Add focused tests proving unsafe, approval-bypass, untrusted approval chat, and approval-like short replies cannot enter memory, investigate, approval, or action paths.
- **D-52-16:** Add focused graph/router tests proving `receive_request -> safety_pre_route` is the active entry path and `route_after_safety` has total route coverage over registered node keys.
- **D-52-17:** Tests must use MOCA-approved command entrypoints such as `uv run pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid verification in this repo.

### Plan granularity

- **D-52-18:** Do not plan Phase 52 as one broad runtime rewrite. A good split is likely: node/router extraction and unit tests; graph wiring plus architecture guardrail updates; compatibility/docs/validation closeout. The planner should adjust based on current source, but each plan must have one clear ownership boundary.

### the agent's Discretion

- The exact internal module name for the new node file is left to the planner, as long as registered graph key is exactly `safety_pre_route`.
- The exact state field name for the safety decision is left to the planner, as long as it is trace-visible, deterministic, and not treated as approval/action authority.
- The planner may decide whether direct refusal uses `final_response` or `clarification_gate` for each fail-closed disposition, provided the choice is deterministic and covered by tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Migration charter and phase scope

- `.planning/ROADMAP.md` - Phase 52 goal, dependency on Phase 51, and CAGM-03 success criteria.
- `.planning/REQUIREMENTS.md` - CAGM-03 requirement mapping.
- `.planning/STATE.md` - Current project state and next-step pointer.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - Binding migration charter, source hierarchy, target graph, compatibility policy, authority matrix, validation matrix, and Phase 52 order.
- `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md` - Baseline guardrail decisions that Phase 52 must update rather than bypass.
- `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-03-SUMMARY.md` - Confirms Phase 51 completed guardrails only and left runtime graph migration for Phase 52-58.

### Target architecture and contract

- `docs/contract-spec.md` - Primary accepted contract reference, especially Section 9 graph/node/router contract.
- `docs/target-agent-platform-architecture-plan.md` - Readable target architecture view, especially Section 6.1 Canonical Runtime Graph.
- `docs/current-langgraph-architecture.md` - Current implementation snapshot only; descriptive, not target authority.

### Current source facts

- `src/agent/graph.py` - Active LangGraph node registration and edge wiring. Current source routes `receive_request -> classify_intent`.
- `src/agent/nodes/receive_request.py` - Per-turn reset and `active_flow_state` projection before safety pre-route runs.
- `src/agent/nodes/classify_intent.py` - Current thick node containing `detect_pre_route(...)`, short reply guard, LLM structured intent, task planning, risk/clarification trace, and compatibility behavior.
- `src/agent/intent_policy.py` - `PreRouteDecision`, `detect_pre_route(...)`, intent route policy, risk policy, and task-plan helpers.
- `src/agent/routing.py` - Current deterministic routers and route allowlists.
- `src/agent/graph_vocabulary.py` - Legacy-to-target projection and current `classify_intent:pre_route -> safety_pre_route` compatibility alias.
- `src/agent/state.py` - `AgentState` contract and ephemeral fields reset by `receive_request`.

### Existing tests and guardrails

- `tests/architecture/graph_baseline.py` - Phase 51 target/current/migration constants and source parsers.
- `tests/architecture/test_canonical_graph_baseline.py` - Phase 51 architecture tests that Phase 52 must update.
- `tests/agent/test_nodes/test_classify_intent.py` - Current pre-route, safety-sensitive, untrusted approval, and short-reply behavior tests.
- `tests/test_graph_routing.py` - Existing graph routing coverage to consult before adding or changing route tests.
- `.planning/ARCHITECTURE-DEBT.md` - Core subsystem debt ledger; Phase 52 must append updates for graph migration / intent routing debt it fixes or preserves.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `PreRouteDecision` in `src/agent/intent_policy.py` already models `none`, `approval_chat_not_trusted`, `safety_sensitive`, and `multi_target_request` dispositions.
- `detect_pre_route(query)` in `src/agent/intent_policy.py` is the current deterministic pre-route detector and should be reused or moved, not reimplemented from scratch.
- `_deterministic_context_update(...)` and `_short_reply_clarification_update(...)` in `src/agent/nodes/classify_intent.py` contain current short-reply / approval-like fail-closed behavior that must be split carefully from true session-context resolution.
- `tests/architecture/graph_baseline.py` already parses `StateGraph.add_node(...)` and conditional edge maps without importing live graph dependencies.
- `graph_vocabulary.project_trace_step_for_contract(...)` already projects implementation node names to target graph names.

### Established Patterns

- Graph routers are deterministic functions with constrained route allowlists and safe fallbacks.
- Architecture guardrails prefer static source inspection over live provider, DB, or graph execution when the phase is about node vocabulary and route maps.
- Memory remains contextual-only and cannot satisfy evidence, business fact, approval/action, or replay authority.
- `investigate` is already a bounded read-only ReAct node from Phase 49; Phase 52 must preserve it and only prevent unsafe pre-route cases from reaching it.

### Integration Points

- `src/agent/graph.py` must add the new node and route map.
- `src/agent/routing.py` is the natural place for `route_after_safety` if the existing router module pattern is preserved.
- `src/agent/nodes/` is the natural home for the new node implementation.
- `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` must reflect the post-Phase 52 active graph baseline.
- `tests/agent/test_nodes/test_classify_intent.py` likely needs tests moved or duplicated so safety behavior is no longer proven only through `classify_intent`.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 52 as "make request-risk pre-route explicit" rather than "rewrite intent recognition".
- Preserve the current behavior that approval decisions are forbidden in ordinary chat and must use trusted approval routes.
- Keep safe-path compatibility intentionally boring: new node first, then legacy `classify_intent` until Phase 53.
- For fail-closed safety tests, assert absence of downstream fields such as `proposed_action`, `approval_result`, `action_draft`, and action execution state, and assert route does not enter memory/investigate/approval/action nodes.
- The plan should include a compatibility table for any remaining `classify_intent` pre-route or route alias, not just prose.

</specifics>

<deferred>
## Deferred Ideas

- Phase 53 owns `session_context_load -> contextual_intent_resolve` cutover and deletion of active `classify_intent` graph-node compatibility.
- Phase 54 owns `slot_resolution_gate` cutover and slot provenance exposure.
- Phase 55 owns `memory_context_load` cutover and memory authority labels.
- Phase 56 owns `recommendation_generation` canonicalization and RAG/claim status alignment.
- Phase 57 owns `risk_gate` / `approval_gate` canonicalization.
- Phase 58 owns final no-debt cleanup: no active legacy graph node names, compatibility aliases, dual route values, imports, or docs drift.
- External action execution after `action_draft` remains future scope and is not part of Phase 52.

</deferred>

---

*Phase: 52-safety-pre-route-node*
*Context gathered: 2026-07-06 via lightweight auto discuss*
