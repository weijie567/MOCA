# Phase 52: safety-pre-route-node - Research

**Researched:** 2026-07-06 [VERIFIED: environment current_date]
**Domain:** MOCA LangGraph canonical graph migration, request-risk pre-route extraction, deterministic safety routing [VERIFIED: .planning/ROADMAP.md; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
**Confidence:** HIGH for current source/test facts; MEDIUM for exact internal state-field naming because Phase 52 context leaves that to planning discretion. [VERIFIED: src/agent/graph.py; VERIFIED: src/agent/nodes/classify_intent.py; VERIFIED: tests/architecture/graph_baseline.py; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]

<user_constraints>
## User Constraints (from CONTEXT.md)

**Source for all copied constraints in this section:** `.planning/phases/52-safety-pre-route-node/52-CONTEXT.md`. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]

### Locked Decisions

#### Graph insertion boundary

- **D-52-01:** Register `safety_pre_route` as a real LangGraph node in `src/agent/graph.py`, immediately after `receive_request`.
- **D-52-02:** Add or expose a deterministic `route_after_safety` router for the new node. It must be side-effect-free and return only registered graph node keys.
- **D-52-03:** In Phase 52, the safe continuation may remain `safety_pre_route -> classify_intent` as temporary compatibility. Do not move `session_context_load` before intent and do not replace `classify_intent` with `contextual_intent_resolve`; those are Phase 53 / CAGM-04.
- **D-52-04:** Any preserved `classify_intent` compatibility must be recorded in the Phase 52 plan with the Phase 50 compatibility metadata: exact legacy surface, canonical owner, reason, trace projection, validation, and delete phase. The expected delete phase is Phase 53.

#### Safety responsibility split

- **D-52-05:** Extract only deterministic request-risk pre-route behavior into `safety_pre_route`: current `detect_pre_route(...)` decisions, untrusted approval-chat detection, approval-bypass / approval-like short reply guards, and safety-sensitive request tagging.
- **D-52-06:** `safety_pre_route` must not run the LLM, load session / reviewed memory, query business facts, retrieve or verify policy evidence, evaluate proposed-action risk, create approval state, create action drafts, or execute tools.
- **D-52-07:** Untrusted approval chat and standalone approval/action short replies must fail closed before memory, investigate, approval, or action paths. The default route is `clarification_gate` when the system needs to explain the trusted approval channel; direct refusal through `final_response` is allowed only when the plan gives an explicit deterministic reason and tests it.
- **D-52-08:** Explicit approval-bypass attempts must not proceed to memory, investigate, `approval_gate`, or `action_draft`. They should be represented as a safety disposition and routed to `clarification_gate` or `final_response`.
- **D-52-09:** Ordinary safety-sensitive but supported requests, such as an action analysis request, may be tagged with `pre_route_disposition="safety_sensitive"` and continue to the legacy intent path only if they are not approval-bypass attempts. The pre-route node itself must never produce `proposed_action`, approval state, or action draft fields.
- **D-52-10:** Broad semantic `unsupported` classification remains owned by intent resolution until Phase 53 unless the unsupported case is deterministic and clearly part of request-risk pre-routing. If implementation needs broader unsupported detection in `safety_pre_route`, record it as an explicit MVP scope or spec delta rather than silently expanding the node.

#### Trace and state projection

- **D-52-11:** `safety_pre_route` needs its own trace-visible decision record. Downstream planning should choose the smallest compatible state shape, but tests must prove the canonical node emits or projects `safety_pre_route` rather than hiding the decision only inside `intent_classification`.
- **D-52-12:** During compatibility, `classify_intent` may continue to include `pre_route_decision` in `classification_trace`, but this is a migration artifact. The Phase 52 plan must name its owner and Phase 53 cleanup path.
- **D-52-13:** Trace / vocabulary projection should treat the new node as canonical runtime `safety_pre_route`. Any remaining `classify_intent:pre_route` alias must be temporary and covered by tests.

#### Validation and guardrails

- **D-52-14:** Update Phase 51 architecture guardrails to reflect the new migration state: `safety_pre_route` is now an active canonical node, while the remaining legacy nodes stay allowed only in migration mode.
- **D-52-15:** Add focused tests proving unsafe, approval-bypass, untrusted approval chat, and approval-like short replies cannot enter memory, investigate, approval, or action paths.
- **D-52-16:** Add focused graph/router tests proving `receive_request -> safety_pre_route` is the active entry path and `route_after_safety` has total route coverage over registered node keys.
- **D-52-17:** Tests must use MOCA-approved command entrypoints such as `uv run pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid verification in this repo.

#### Plan granularity

- **D-52-18:** Do not plan Phase 52 as one broad runtime rewrite. A good split is likely: node/router extraction and unit tests; graph wiring plus architecture guardrail updates; compatibility/docs/validation closeout. The planner should adjust based on current source, but each plan must have one clear ownership boundary.

### Claude's Discretion

- The exact internal module name for the new node file is left to the planner, as long as registered graph key is exactly `safety_pre_route`.
- The exact state field name for the safety decision is left to the planner, as long as it is trace-visible, deterministic, and not treated as approval/action authority.
- The planner may decide whether direct refusal uses `final_response` or `clarification_gate` for each fail-closed disposition, provided the choice is deterministic and covered by tests.

### Deferred Ideas (OUT OF SCOPE)

- Phase 53 owns `session_context_load -> contextual_intent_resolve` cutover and deletion of active `classify_intent` graph-node compatibility.
- Phase 54 owns `slot_resolution_gate` cutover and slot provenance exposure.
- Phase 55 owns `memory_context_load` cutover and memory authority labels.
- Phase 56 owns `recommendation_generation` canonicalization and RAG/claim status alignment.
- Phase 57 owns `risk_gate` / `approval_gate` canonicalization.
- Phase 58 owns final no-debt cleanup: no active legacy graph node names, compatibility aliases, dual route values, imports, or docs drift.
- External action execution after `action_draft` remains future scope and is not part of Phase 52.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAGM-03 | `safety_pre_route` exists as an explicit registered graph node immediately after `receive_request`, owning request-risk / unsafe / unsupported / untrusted approval pre-route decisions before memory, investigation, approval, or action paths. [VERIFIED: .planning/REQUIREMENTS.md] | Add a deterministic node after `receive_request`, add `route_after_safety`, keep safe compatibility to `classify_intent` only for Phase 52, and update guardrail tests plus focused safety tests. [VERIFIED: .planning/ROADMAP.md; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: src/agent/graph.py; VERIFIED: tests/architecture/graph_baseline.py] |
</phase_requirements>

## Summary

Phase 52 should be planned as an insertion and extraction phase, not as the Phase 53 intent cutover. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: .planning/ROADMAP.md] The current active graph path is `START -> receive_request -> classify_intent`, and `classify_intent` currently owns `detect_pre_route(...)`, short approval/action reply guards, LLM structured intent, policy/risk/clarification derivation, task-plan handling, and compatibility trace output. [VERIFIED: src/agent/graph.py:295-306; VERIFIED: src/agent/nodes/classify_intent.py:746-906]

The correct Phase 52 target is `START -> receive_request -> safety_pre_route`, with unsafe or approval-bypass dispositions routed to `clarification_gate` or `final_response` before memory, investigate, approval, or action paths. [VERIFIED: .planning/ROADMAP.md; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; CITED: docs/contract-spec.md:583-629] Safe requests may route to legacy `classify_intent` in Phase 52, but that compatibility must be documented with Phase 50 metadata and deleted in Phase 53. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md]

**Primary recommendation:** Split Phase 52 into three numbered plans: (1) extract deterministic safety node behavior and node tests, (2) wire graph/router plus Phase 51 architecture guardrails, and (3) record compatibility/trace/docs/validation closeout. [VERIFIED: AGENTS.md; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]

## Project Constraints (from CLAUDE.md and AGENTS.md)

- `CLAUDE.md` exists and requires architecture-debt entries to be based on real code, tests, or planning artifacts, with target docs separated from implemented facts. [VERIFIED: CLAUDE.md]
- `CLAUDE.md` requires implementation/spec divergence to be recorded rather than silently diverging from `docs/contract-spec.md`. [VERIFIED: CLAUDE.md]
- `AGENTS.md` requires MOCA test verification through `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or the current repo `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid. [VERIFIED: AGENTS.md]
- `AGENTS.md` requires phase-level plans with multiple ownership domains, waves, or verification gates to be split into multiple numbered plans. [VERIFIED: AGENTS.md]
- `AGENTS.md` requires core subsystem discoveries/fixes in tool calls, RAG, memory, or intent recognition to be appended to `.planning/ARCHITECTURE-DEBT.md` in Chinese by default. [VERIFIED: AGENTS.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Request-risk pre-route decision | API / Backend graph node | Test / Architecture guardrail | `safety_pre_route` is a registered LangGraph node in the backend runtime, and Phase 51 guardrails must prove it is active after `receive_request`. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; CITED: docs/contract-spec.md:628-629] |
| Safety route selection | API / Backend router | Test / Architecture guardrail | `route_after_safety` must be deterministic, side-effect-free, and return registered node keys. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; CITED: docs/contract-spec.md:657-661] |
| Legacy safe continuation | API / Backend graph wiring | Planning compatibility ledger | Phase 52 may route safe requests to `classify_intent`; Phase 53 owns `session_context_load -> contextual_intent_resolve` cutover and deletion of active `classify_intent` compatibility. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: .planning/ROADMAP.md] |
| Trace projection | API / Backend trace/vocabulary | Replay/API presentation | `AgentStep.node_name` and `AgentTraceEvent.node_name` store implementation names, and API/repository projections use `graph_vocabulary.project_trace_step_for_contract(...)`. [VERIFIED: src/db/models.py:1178-1188; VERIFIED: src/db/models.py:1496-1529; VERIFIED: src/api/routers/traces.py:108-117; VERIFIED: src/repositories/trace_repo.py:67-78] |
| Safety tests | Test / Unit and architecture | API / Backend behavior | Current tests already cover `classify_intent` pre-route and graph no-tool approval-chat behavior; Phase 52 needs new tests that prove the canonical `safety_pre_route` boundary owns the fail-closed behavior. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:304-420; VERIFIED: tests/agent/test_graph.py:1076-1085] |
| Documentation/debt closeout | Planning docs | API / Backend evidence | Graph migration debt is tracked in `.planning/ARCHITECTURE-DEBT.md`, and Phase 51 already records that runtime migration remains incomplete. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:22-40; VERIFIED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-03-SUMMARY.md] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | Project requires `>=3.12`; current `uv run` environment uses Python 3.12 packages. [VERIFIED: pyproject.toml:5; VERIFIED: UV test run output] | Runtime and tests | `datetime.UTC` usage and project test rules require the project virtual environment, not system Python. [VERIFIED: AGENTS.md; VERIFIED: src/agent/routing.py:4] |
| LangGraph | Installed `langgraph==1.1.10`; project declares `langgraph>=0.4`. [VERIFIED: uv run python importlib.metadata; VERIFIED: pyproject.toml:19] | `StateGraph` node/edge assembly | Current graph assembly uses `StateGraph.add_node`, `add_edge`, `add_conditional_edges`, and `compile`. [VERIFIED: src/agent/graph.py:276-377; CITED: /langchain-ai/langgraph Context7 docs] |
| Pydantic | Installed `pydantic==2.13.4`. [VERIFIED: uv run python importlib.metadata] | Typed state/decision schemas | `PreRouteDecision`, `IntentResultV3`, and approval/action schemas are Pydantic models. [VERIFIED: src/agent/intent_policy.py:566-572; VERIFIED: src/agent/schemas.py; VERIFIED: src/approvals/schemas.py] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | Installed `pytest==9.0.3`; project dev dependency is `pytest>=8.0`. [VERIFIED: uv run python importlib.metadata; VERIFIED: pyproject.toml:34-39] | Unit, graph, architecture tests | Use for all Phase 52 validation commands through `uv run pytest ...`. [VERIFIED: AGENTS.md; VERIFIED: pyproject.toml:54-55] |
| pytest-asyncio | Installed `pytest-asyncio==1.3.0`; project dev dependency is `pytest-asyncio>=0.23`. [VERIFIED: uv run python importlib.metadata; VERIFIED: pyproject.toml:34-39] | Async node/graph tests | Existing node and graph tests use `@pytest.mark.asyncio`. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:33; VERIFIED: tests/agent/test_graph.py:1076] |
| ruff | Installed `ruff==0.15.12`; project dev dependency is `ruff>=0.5`. [VERIFIED: uv run python importlib.metadata; VERIFIED: pyproject.toml:34-39] | Linting touched Python files | Use `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` for changed files. [VERIFIED: AGENTS.md; VERIFIED: pyproject.toml:50-52] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `PreRouteDecision` and `detect_pre_route(...)` | New safety DTO/detector | Do not hand-roll a second detector because current behavior is already modeled and tested in `intent_policy.py` and `test_classify_intent.py`. [VERIFIED: src/agent/intent_policy.py:566-622; VERIFIED: tests/agent/test_nodes/test_classify_intent.py:304-420] |
| Existing AST architecture helper | Live graph introspection only | Static AST parsing catches registration/route-map drift without requiring live LLM/provider/DB setup. [VERIFIED: tests/architecture/graph_baseline.py:149-188; VERIFIED: tests/architecture/test_canonical_graph_baseline.py:95-112] |
| Deterministic router in `src/agent/routing.py` | LLM or service-backed safety router | Router contract forbids LLM/tool/repository/service calls and requires valid node-key returns. [CITED: docs/contract-spec.md:657-661; VERIFIED: src/agent/routing.py:71-84] |

**Installation:** No new package installation is recommended for Phase 52. [VERIFIED: pyproject.toml; VERIFIED: src/agent/graph.py; VERIFIED: tests/architecture/graph_baseline.py]

```bash
# No new packages required. Use the existing project environment.
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q
```

**Version verification:** Versions above were checked with `uv run python -c 'import importlib.metadata ...'`, because this is a Python project and Phase 52 should not upgrade dependencies. [VERIFIED: uv run python importlib.metadata; VERIFIED: pyproject.toml]

## Architecture Patterns

### System Architecture Diagram

```text
User/API request
  -> receive_request
     - resets per-turn memory/risk/action fields
     - initializes trace_steps
     [VERIFIED: src/agent/nodes/receive_request.py:45-150]
  -> safety_pre_route
     - deterministic request-risk decision
     - writes trace-visible safety/pre-route projection
     - no LLM, memory, tools, evidence, risk_gate, approval, or action writes
     [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
  -> route_after_safety
     -> clarification_gate for untrusted approval chat / approval-like bypass
     -> final_response only for explicitly tested deterministic refusal
     -> classify_intent for Phase 52 safe compatibility
     [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
  -> classify_intent (temporary Phase 52 safe compatibility)
     -> existing route_after_intent / legacy migration path
     [VERIFIED: src/agent/graph.py:297-306]
```

### Recommended Project Structure

```text
src/agent/
├── nodes/
│   ├── receive_request.py        # existing per-turn reset before safety [VERIFIED: src/agent/nodes/receive_request.py]
│   ├── safety_pre_route.py       # new deterministic Phase 52 node [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
│   └── classify_intent.py        # temporary safe-path compatibility until Phase 53 [VERIFIED: src/agent/nodes/classify_intent.py]
├── routing.py                    # add route_after_safety beside deterministic routers [VERIFIED: src/agent/routing.py]
├── intent_policy.py              # reuse PreRouteDecision/detect_pre_route and move short approval helper if needed [VERIFIED: src/agent/intent_policy.py]
└── graph_vocabulary.py           # project safety_pre_route as runtime, keep aliases only with metadata [VERIFIED: src/agent/graph_vocabulary.py]

tests/
├── agent/test_nodes/test_safety_pre_route.py          # new focused node tests [VERIFIED: Wave 0 gap]
├── agent/test_nodes/test_classify_intent.py           # adjust compatibility tests [VERIFIED: tests/agent/test_nodes/test_classify_intent.py]
├── agent/test_graph.py                                # graph behavior and no-tool safety smoke tests [VERIFIED: tests/agent/test_graph.py]
└── architecture/test_canonical_graph_baseline.py      # update Phase 51 baseline [VERIFIED: tests/architecture/test_canonical_graph_baseline.py]
```

### Pattern 1: Deterministic Node + Deterministic Router

**What:** Put side-effect-free route choice in `route_after_safety`, and keep state mutation in `safety_pre_route`. [CITED: docs/contract-spec.md:657-661; VERIFIED: src/agent/routing.py:71-84]

**When to use:** Use this for Phase 52 because safety routing must fail closed before memory/investigation/approval/action and must return only registered graph node keys. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]

**Example:**

```python
# Source pattern: src/agent/routing.py route wrappers and allowlists.
SAFETY_ROUTES = {"classify_intent", "clarification_gate", "final_response"}

def route_after_safety(state: AgentState) -> str:
    try:
        route = _route_after_safety(state)
    except Exception:
        return "clarification_gate"
    return route if route in SAFETY_ROUTES else "clarification_gate"
```

### Pattern 2: Reuse `PreRouteDecision`, Do Not Clone It

**What:** `PreRouteDecision` already models `none`, `approval_chat_not_trusted`, `safety_sensitive`, and `multi_target_request`, and `detect_pre_route(...)` already detects approval-chat, multi-target, action, and escalation signals. [VERIFIED: src/agent/intent_policy.py:566-622]

**When to use:** `safety_pre_route` should call or share this detector and write a trace-visible decision, while `classify_intent` reads the existing state decision or falls back to detection only as temporary compatibility. [VERIFIED: src/agent/nodes/classify_intent.py:746-752; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]

**Example:**

```python
# Source pattern: src/agent/intent_policy.py PreRouteDecision/detect_pre_route.
decision = detect_pre_route(str(state.get("user_query") or ""))
update = {
    "pre_route_decision": decision.model_dump(),
    "routing_hints": {
        **dict(state.get("routing_hints") or {}),
        "pre_route_disposition": decision.disposition,
    },
}
```

### Pattern 3: Static Architecture Guardrails Track Migration State

**What:** Phase 51 uses AST/source inspection to enumerate `add_node(...)`, `add_conditional_edges(...)`, router returns, migration legacy maps, and forbidden node names. [VERIFIED: tests/architecture/graph_baseline.py:149-188; VERIFIED: tests/architecture/graph_baseline.py:377-390]

**When to use:** Update these constants/tests in the same plan that wires `safety_pre_route`, so `receive_request -> safety_pre_route` becomes the source-verified baseline and old legacy nodes remain migration-mode only. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: tests/architecture/test_canonical_graph_baseline.py:18-112]

**Example:**

```python
# Source pattern: tests/architecture/graph_baseline.py.
CURRENT_ACTIVE_GRAPH_NODES_BASELINE = CURRENT_ACTIVE_GRAPH_NODES_BASELINE | {"safety_pre_route"}
CURRENT_CONDITIONAL_EDGE_BASELINE[("safety_pre_route", "route_after_safety")] = {
    "classify_intent": "classify_intent",
    "clarification_gate": "clarification_gate",
    "final_response": "final_response",
}
```

### Anti-Patterns to Avoid

- **Moving `session_context_load` before intent in Phase 52:** Phase 53 owns that ordering and `contextual_intent_resolve` cutover. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: .planning/ROADMAP.md]
- **Letting `safety_pre_route` create action or approval state:** Phase 52 context forbids `proposed_action`, approval state, action drafts, tool execution, evidence verification, and proposed-action risk evaluation inside this node. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
- **Keeping safety only in `classification_trace`:** Phase 52 requires a trace-visible canonical `safety_pre_route` decision rather than hiding the decision only inside `intent_classification`. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
- **Broad unsupported semantics in pre-route:** Broad semantic unsupported remains intent-resolution-owned unless a case is deterministic and clearly part of request-risk pre-routing. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
- **Deleting all `classify_intent` compatibility in Phase 52:** Phase 53 owns active `classify_intent` graph-node deletion, so Phase 52 should record compatibility instead of over-scoping. [VERIFIED: .planning/ROADMAP.md; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Request-risk detection | A new regex/dict detector unrelated to existing intent policy | `PreRouteDecision` and `detect_pre_route(...)` | Existing behavior and tests cover approval-chat, multi-target, action, and escalation pre-route decisions. [VERIFIED: src/agent/intent_policy.py:566-622; VERIFIED: tests/agent/test_nodes/test_classify_intent.py:304-345] |
| Approval-like short reply recognition | A second private token list in the new node | Move/share the current short-reply helper from `classify_intent` or expose it in `intent_policy.py` | Current tokens are already defined and tested for standalone approval-like replies. [VERIFIED: src/agent/nodes/classify_intent.py:94-130; VERIFIED: tests/agent/test_nodes/test_classify_intent.py:407-420] |
| Graph source parsing | Custom grep-only parser for node/edge names | Existing `tests/architecture/graph_baseline.py` AST helpers | Existing helpers already parse `add_node`, `add_conditional_edges`, and router return values. [VERIFIED: tests/architecture/graph_baseline.py:149-188; VERIFIED: tests/architecture/graph_baseline.py:377-390] |
| Route safety enforcement | Service calls or LLM calls inside routers | Deterministic `route_after_safety` allowlist wrapper | Contract says routers are deterministic and side-effect-free. [CITED: docs/contract-spec.md:657-661; VERIFIED: src/agent/routing.py:71-84] |
| Historical trace migration | Updating old DB rows from `classify_intent` to `safety_pre_route` | Projection through `graph_vocabulary` plus new runtime node traces | Trace APIs already project implementation node names to target names. [VERIFIED: src/db/models.py:1178-1188; VERIFIED: src/api/routers/traces.py:108-117; VERIFIED: src/repositories/trace_repo.py:67-78] |

**Key insight:** Phase 52 is about making the pre-route boundary explicit and testable before memory/investigation/action, not replacing the entire intent subsystem. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: .planning/ROADMAP.md]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `agent_steps.node_name` stores implementation node names, and `agent_trace_events.node_name` stores nullable event node names. [VERIFIED: src/db/models.py:1178-1188; VERIFIED: src/db/models.py:1496-1529] Historical rows may contain `classify_intent`; API/repository timeline projections already call `project_trace_step_for_contract(...)`. [VERIFIED: src/api/routers/traces.py:108-117; VERIFIED: src/repositories/trace_repo.py:67-78] | No data migration recommended for Phase 52; update projection/vocabulary for future runs and keep old rows readable. [VERIFIED: src/agent/graph_vocabulary.py:129-139] |
| Live service config | No running MOCA/uvicorn/langgraph/celery/rq/dramatiq process was found in a local `ps` scan. [VERIFIED: ps -axo pid,command scan] `launchctl` contains `com.moca.study.*` jobs but no `safety_pre_route`/`classify_intent` graph service registration. [VERIFIED: launchctl list scan] | No live service config migration identified for local planning. [VERIFIED: ps/launchctl scans] |
| OS-registered state | No local `pm2` MOCA graph process was found, and the launchd hits are study jobs rather than graph runtime jobs. [VERIFIED: pm2 jlist scan; VERIFIED: launchctl list scan] | No OS re-registration required for Phase 52. [VERIFIED: pm2/launchctl scans] |
| Secrets/env vars | `.env`, `.env.example`, `docker-compose.yml`, and `Dockerfile` contain no `classify_intent`, `safety_pre_route`, `route_after_safety`, `pre_route`, `GRAPH`, `NODE`, or `ROUTE` matches. [VERIFIED: rg over .env .env.example docker-compose.yml Dockerfile] | No secret/env-var rename required. [VERIFIED: rg over env/compose/docker files] |
| Build artifacts | Local artifacts include `moca.egg-info`, many `__pycache__` directories, and `frontend/dist`; no graph-node-specific build artifact was identified. [VERIFIED: find build artifact scan] | No artifact migration required; normal test/lint commands will import source under `uv run`. [VERIFIED: pyproject.toml; VERIFIED: UV focused test run] |

**Nothing found requiring a database data migration:** Phase 52 should change source behavior and projection metadata; historical trace rows should remain historical implementation facts. [VERIFIED: src/db/models.py; VERIFIED: src/agent/graph_vocabulary.py; VERIFIED: src/api/routers/traces.py]

## Common Pitfalls

### Pitfall 1: Safe Route Accidentally Implements Phase 53

**What goes wrong:** `route_after_safety` routes safe requests to `session_context_load` or `contextual_intent_resolve` in Phase 52. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**Why it happens:** Target docs say safe target path is `safety_pre_route -> session_context_load`, but Phase 52 explicitly allows `safety_pre_route -> classify_intent` compatibility until Phase 53. [CITED: docs/contract-spec.md:583; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**How to avoid:** Use `classify_intent` as the Phase 52 safe route and record it in the compatibility table. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**Warning signs:** Plan edits mention moving `session_context_load` before intent, deleting `classify_intent`, or adding `contextual_intent_resolve` runtime wiring. [VERIFIED: .planning/ROADMAP.md]

### Pitfall 2: Unsafe Requests Still Reach `classify_intent`

**What goes wrong:** `safety_pre_route` tags `approval_chat_not_trusted` but safe-path routing still sends that state to `classify_intent`. [VERIFIED: src/agent/graph.py:297-306; VERIFIED: src/agent/routing.py:233-255]  
**Why it happens:** Current logic relies on `classify_intent` and `route_after_intent` to fail closed. [VERIFIED: src/agent/nodes/classify_intent.py:746-752; VERIFIED: src/agent/routing.py:237-243]  
**How to avoid:** Add node-level and graph-level tests that assert untrusted approval chat and approval-like short replies route to `clarification_gate` or `final_response` before `classify_intent`, memory, investigate, approval, or action. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**Warning signs:** `trace_steps` for an approval-bypass input include `classify_intent`, `session_memory_load`, `investigate`, `approval_gate`, or `action_draft`. [VERIFIED: src/agent/nodes/classify_intent.py:777-786; VERIFIED: src/agent/nodes/receive_request.py:49-150]

### Pitfall 3: Safety Node Writes Downstream Authority Fields

**What goes wrong:** The pre-route node writes `proposed_action`, `approval_result`, `action_draft`, `business_context`, `case_memory`, or evidence fields. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**Why it happens:** Current `classify_intent` is thick, and extracting logic can accidentally carry later-layer fields with it. [VERIFIED: src/agent/nodes/classify_intent.py:215-480; VERIFIED: src/agent/nodes/classify_intent.py:532-632]  
**How to avoid:** Define a small allowed-write contract for `safety_pre_route`, and test forbidden downstream fields are absent for every fail-closed disposition. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: tests/agent/test_nodes/test_classify_intent.py:257-258]  
**Warning signs:** New tests only check route labels and do not assert absence of action/approval/memory/evidence state. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:317-345]

### Pitfall 4: Short Replies Lose Their Boundary

**What goes wrong:** All ambiguous short replies are moved into `safety_pre_route`, including pending-slot continuity behavior that belongs to active-flow/session-context resolution. [VERIFIED: src/agent/nodes/classify_intent.py:635-709]  
**Why it happens:** Current `classify_intent` has both active-flow short-reply handling and standalone approval-like short-reply guarding in one helper block. [VERIFIED: src/agent/nodes/classify_intent.py:635-743]  
**How to avoid:** In Phase 52, extract only approval/action-like bypass short replies into safety; leave identifier replies and ordinary active-flow ambiguity in compatibility unless the plan explicitly records a scoped split. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**Warning signs:** Tests for `OD-12345` pending-slot replies change behavior in Phase 52. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py:348-377]

### Pitfall 5: Architecture Baseline Becomes Final No-Debt Too Early

**What goes wrong:** Updating Phase 51 tests makes Phase 52 fail because remaining legacy nodes are still active. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:45-84]  
**Why it happens:** Phase 58 owns exact final canonical node-set enforcement, while Phase 52 only activates `safety_pre_route`. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:156-158; VERIFIED: .planning/ROADMAP.md]  
**How to avoid:** Update current baseline to include `safety_pre_route`, keep the remaining legacy map in migration mode, and leave final exact no-debt skipped for Phase 58. [VERIFIED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-03-SUMMARY.md; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]  
**Warning signs:** `test_final_no_debt_gate_is_marked_phase58_scope` is unskipped in Phase 52. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:156-158]

## Code Examples

Verified patterns from current sources and target contracts:

### Safety Node Shape

```python
# Source: src/agent/nodes/receive_request.py trace-step style and
# src/agent/intent_policy.py PreRouteDecision/detect_pre_route.
async def safety_pre_route(state: AgentState) -> dict[str, Any]:
    started_at = _now_iso()
    decision = detect_pre_route(str(state.get("user_query") or ""))
    routing_hints = dict(state.get("routing_hints") or {})
    if decision.disposition != "none":
        routing_hints["pre_route_disposition"] = decision.disposition
        if decision.requires_clarification:
            routing_hints["requires_clarification"] = True
            routing_hints["clarification_reason"] = decision.disposition
    return {
        "pre_route_decision": decision.model_dump(),
        "routing_hints": routing_hints,
        "trace_steps": (state.get("trace_steps") or []) + [
            {
                "node": "safety_pre_route",
                "status": "completed",
                "started_at": started_at,
                "completed_at": _now_iso(),
                "provider_latency_ms": None,
                "retry_count": 0,
                "metrics_json": {"reason_codes": decision.reason_codes},
            }
        ],
    }
```

### Graph Wiring Shape

```python
# Source: src/agent/graph.py current StateGraph wiring pattern.
builder.add_node("receive_request", receive_request)
builder.add_node("safety_pre_route", safety_pre_route)
builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)

builder.add_edge(START, "receive_request")
builder.add_edge("receive_request", "safety_pre_route")
builder.add_conditional_edges(
    "safety_pre_route",
    route_after_safety,
    {
        "classify_intent": "classify_intent",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
)
```

### Compatibility Table Shape for PLAN.md

```markdown
| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
|----------------|-----------------|--------|------------------|------------|--------------|
| `classify_intent` still active for safe continuation | `contextual_intent_resolve` | Phase 53 owns session context before intent and active intent-node cutover | `classify_intent -> contextual_intent_resolve`; `safety_pre_route` emits its own trace step | graph baseline + focused safety tests | Phase 53 |
| `classification_trace.pre_route_decision` still emitted by `classify_intent` fallback | `safety_pre_route` | Unit compatibility for direct `classify_intent` calls until cutover | `safety_pre_route` trace is canonical for graph runs; classifier trace is migration artifact | classify compatibility tests | Phase 53 |
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Synthetic `classify_intent:pre_route -> safety_pre_route` vocabulary alias without active runtime node | Phase 52 should register real `safety_pre_route` and keep alias only as temporary compatibility | Phase 52 target after Phase 51 guardrails | Planner must create node/router/tests and update vocabulary status/projection. [VERIFIED: src/agent/graph_vocabulary.py:49-53; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] |
| `classify_intent` owns pre-route, LLM intent, deterministic context, risk, clarification, and task-plan projection | Safety pre-route becomes explicit before legacy safe continuation; Phase 53 later splits contextual intent | Phase 52 then Phase 53 | Planner must not over-split `classify_intent` beyond Phase 52 safety ownership. [VERIFIED: src/agent/nodes/classify_intent.py:215-480; VERIFIED: .planning/ROADMAP.md] |
| Phase 51 current graph baseline contains 14 active registered nodes | Post-Phase 52 baseline should contain `safety_pre_route` plus the remaining migration-mode legacy nodes | Phase 52 | Architecture tests must update current baseline and route maps. [VERIFIED: tests/architecture/graph_baseline.py:31-48; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] |
| Target docs route safe safety pre-route to `session_context_load` | Phase 52 compatibility may route safe safety pre-route to `classify_intent` | Phase 52 temporary compatibility | PLAN.md must explain this as an intentional Phase 52 MVP and deletion path. [CITED: docs/contract-spec.md:583; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] |

**Deprecated/outdated:** Treating `safety_pre_route` as only a trace alias is outdated for Phase 52, because CAGM-03 requires it as an explicit registered node immediately after `receive_request`. [VERIFIED: .planning/REQUIREMENTS.md; VERIFIED: .planning/ROADMAP.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

All claims in this research were verified against local source/planning artifacts, Context7/local LangGraph introspection, or official OWASP/ASVS pages; no `[ASSUMED]` claims are intentionally used. [VERIFIED: source inspection and commands listed in Sources]

## Open Questions

1. **Exact top-level state field names for the safety decision**
   - What we know: Phase 52 requires a trace-visible safety decision and allows the planner to choose the smallest compatible state shape. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
   - What's unclear: Whether to add `pre_route_decision`, `safety_pre_route_decision`, `safety_flags`, or only a structured trace plus `routing_hints`. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
   - Recommendation: Use `pre_route_decision` plus existing `routing_hints` for minimal compatibility, and update `AgentState` if the field is accessed outside trace-only tests. [VERIFIED: src/agent/state.py:70-175; VERIFIED: docs/contract-spec.md:628-629]

2. **Direct refusal versus clarification for bypass cases**
   - What we know: Phase 52 allows `clarification_gate` by default and permits `final_response` only when deterministic reason and tests are explicit. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
   - What's unclear: Which bypass strings, if any, deserve direct refusal instead of the existing trusted-approval-channel clarification. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
   - Recommendation: Use `clarification_gate` for Phase 52 unless a plan adds a deterministic direct-refusal case with dedicated tests. [VERIFIED: tests/agent/test_graph.py:1076-1085; VERIFIED: src/agent/nodes/clarification_gate.py:54-97]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Approved test/lint entrypoint | yes | `uv 0.11.2` [VERIFIED: command -v uv && uv --version] | `.venv/bin/pytest` only if current repo venv is confirmed. [VERIFIED: AGENTS.md] |
| Python project env | Runtime/tests | yes | Python packages under project `.venv`; project requires `>=3.12`. [VERIFIED: pyproject.toml; VERIFIED: UV focused test run] | None needed for focused tests. [VERIFIED: UV focused test run] |
| `pytest` | Validation | yes | `pytest==9.0.3` [VERIFIED: uv run python importlib.metadata] | None needed. [VERIFIED: UV focused test run] |
| `ruff` | Linting changed Python files | yes | `ruff==0.15.12` [VERIFIED: uv run python importlib.metadata] | Use focused pytest if no Python lint target changes; otherwise no fallback. [VERIFIED: pyproject.toml] |
| Context7 CLI via `npx ctx7` | Library documentation lookup | yes | Resolved `/langchain-ai/langgraph`. [VERIFIED: npx ctx7 library command] | Local introspection of installed `StateGraph` signatures. [VERIFIED: uv run python inspect.signature] |
| PostgreSQL/Redis/live services | Not required by recommended focused tests | not required | No live service process found locally. [VERIFIED: ps scan] | Use `MemorySaver`/static tests and fake services for Phase 52 focused validation. [VERIFIED: tests/agent/test_graph.py:11-17; VERIFIED: tests/architecture/graph_baseline.py] |
| Graphify knowledge graph | Optional GSD context | disabled | `graphify is not enabled`. [VERIFIED: gsd-tools graphify status] | Source grep/read inspection was used. [VERIFIED: rg/nl inspections] |

**Missing dependencies with no fallback:** None for the recommended Phase 52 focused validation. [VERIFIED: environment commands; VERIFIED: current focused pytest run]

**Missing dependencies with fallback:** Graphify is disabled, and direct source inspection is the fallback. [VERIFIED: gsd-tools graphify status; VERIFIED: rg/nl inspections]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `9.0.3` with pytest-asyncio `1.3.0`. [VERIFIED: uv run python importlib.metadata] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"`. [VERIFIED: pyproject.toml:54-55] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` [VERIFIED: AGENTS.md; VERIFIED: tests/agent/test_nodes/test_classify_intent.py; VERIFIED: tests/architecture/test_canonical_graph_baseline.py] |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` [VERIFIED: AGENTS.md; VERIFIED: existing test files] |

Current focused baseline before Phase 52 changes passed with `107 passed, 1 skipped, 1 warning` using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q`. [VERIFIED: command run on 2026-07-06]

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAGM-03 | `receive_request -> safety_pre_route` is the active entry path. [VERIFIED: .planning/ROADMAP.md] | architecture + graph compile | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | Existing files need updates. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py; VERIFIED: tests/agent/test_graph.py] |
| CAGM-03 | `route_after_safety` only returns registered graph node keys. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] | unit + architecture | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py -q --tb=short` | Existing files need updates. [VERIFIED: tests/architecture/graph_baseline.py; VERIFIED: tests/test_graph_routing.py] |
| CAGM-03 | Untrusted approval chat and approval-bypass attempts do not enter memory/investigate/approval/action. [VERIFIED: .planning/ROADMAP.md] | unit + graph smoke | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_graph.py -q --tb=short` | `test_safety_pre_route.py` is new; `test_graph.py` exists. [VERIFIED: tests/agent/test_graph.py] |
| CAGM-03 | Approval-like short replies fail closed before memory/investigate/approval/action. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | New file plus existing compatibility file. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py] |
| CAGM-03 | `safety_pre_route` does not load memory, query business facts, verify evidence, evaluate action risk, or execute tools. [VERIFIED: .planning/ROADMAP.md] | unit + graph no-tool smoke | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools -q --tb=short` | New file plus existing graph test. [VERIFIED: tests/agent/test_graph.py:1076-1085] |
| CAGM-03 | Compatibility left in `classify_intent` has owner/delete phase/trace projection/validation coverage. [VERIFIED: .planning/ROADMAP.md; VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md] | docs/static review | `rg -n "classify_intent|Phase 53|safety_pre_route|compatibility" .planning/phases/52-safety-pre-route-node/*.md .planning/ARCHITECTURE-DEBT.md` | Plan/Summary/ledger updates are future files. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] |

### Sampling Rate

- **Per task commit:** Run the focused command for files touched by that task, always through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: AGENTS.md]
- **Per wave merge:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short`. [VERIFIED: existing test layout]
- **Phase gate:** Full suite above plus `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/test_graph_routing.py`. [VERIFIED: AGENTS.md; VERIFIED: pyproject.toml]

### Wave 0 Gaps

- [ ] `tests/agent/test_nodes/test_safety_pre_route.py` - covers `CAGM-03` safety node dispositions, forbidden writes, trace projection, and no LLM/tool/memory calls. [VERIFIED: no file exists currently]
- [ ] Update `tests/architecture/graph_baseline.py` - add active `safety_pre_route`, new `route_after_safety`, updated route maps, and remaining legacy migration mode. [VERIFIED: tests/architecture/graph_baseline.py]
- [ ] Update `tests/architecture/test_canonical_graph_baseline.py` - assert Phase 52 current baseline while keeping Phase 58 final no-debt skipped. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py]
- [ ] Update `tests/agent/test_graph.py` / `tests/test_graph_routing.py` - cover active entry path and router return coverage. [VERIFIED: tests/agent/test_graph.py; VERIFIED: tests/test_graph_routing.py]

## Security Domain

OWASP ASVS is a security verification standard for web applications and services; the OWASP project page lists 5.0.0 as the latest stable version. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct auth change | Preserve trusted context as API-auth injected state; do not let user text or LLM output create approval authority. [VERIFIED: docs/contract-spec.md:442; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] |
| V3 Session Management | indirect | Do not load session context in `safety_pre_route`; Phase 53 owns session context before intent. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: .planning/ROADMAP.md] |
| V4 Access Control | yes | Fail closed on untrusted approval chat and approval-bypass before memory, investigate, approval, or action paths. [VERIFIED: .planning/ROADMAP.md; VERIFIED: tests/agent/test_graph.py:1076-1085] |
| V5 Input Validation | yes | Treat raw user text as untrusted input; deterministic detector/router produces bounded dispositions and registered node-key routes. [VERIFIED: src/agent/intent_policy.py:578-622; CITED: docs/contract-spec.md:657-661] |
| V6 Cryptography | no direct cryptography change | Do not evaluate action payload hashes or safety snapshots in `safety_pre_route`; those belong to downstream risk/action boundaries. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: src/agent/graph.py:67-86] |

### Known Threat Patterns for MOCA Safety Pre-route

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| User sends "approve APR-1" or similar ordinary-chat approval command | Elevation of Privilege / Spoofing | `detect_pre_route(...)`/short approval guard sets an untrusted approval disposition, and `route_after_safety` sends it to safe clarification or refusal before `classify_intent`, memory, approval, or action. [VERIFIED: src/agent/intent_policy.py:581-592; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md] |
| User sends standalone "同意"/"approve"/"do it" without trusted approval channel | Elevation of Privilege | Reuse the current approval/action short-reply token set and route fail-closed before downstream graph paths. [VERIFIED: src/agent/nodes/classify_intent.py:94-130; VERIFIED: tests/agent/test_nodes/test_classify_intent.py:407-420] |
| Router returns an unregistered or legacy-wrong route | Tampering / Denial of Service | Allowlist `route_after_safety` returns and architecture-test the route map against registered node names. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:99-112; CITED: docs/contract-spec.md:657-661] |
| Safety decision is hidden only in classifier trace | Repudiation | Emit a `safety_pre_route` trace step and update graph vocabulary/projection so the canonical node is visible in traces. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: src/agent/graph_vocabulary.py:129-139] |
| Unsafe input reaches memory or investigation before fail-closed decision | Information Disclosure / Elevation of Privilege | Register `safety_pre_route` immediately after `receive_request` and test no memory/tool calls for unsafe inputs. [VERIFIED: src/agent/graph.py:295-317; VERIFIED: .planning/ROADMAP.md] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/52-safety-pre-route-node/52-CONTEXT.md` - locked decisions, discretion, deferred scope. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` - CAGM-03 requirement text. [VERIFIED: file read]
- `.planning/ROADMAP.md` - Phase 52 goal, success criteria, and Phase 53/58 boundaries. [VERIFIED: file read]
- `.planning/STATE.md` - current phase pointer and graph migration sequence. [VERIFIED: file read]
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - migration charter, compatibility policy, authority matrix, validation matrix. [VERIFIED: file read]
- `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md` and `51-03-SUMMARY.md` - Phase 51 guardrail decisions and closeout. [VERIFIED: file read]
- `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/nodes/classify_intent.py`, `src/agent/intent_policy.py`, `src/agent/nodes/receive_request.py`, `src/agent/graph_vocabulary.py`, `src/agent/state.py` - current implementation facts. [VERIFIED: file reads and rg/nl inspections]
- `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `tests/agent/test_nodes/test_classify_intent.py`, `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/agent/test_graph_vocabulary.py` - current validation facts. [VERIFIED: file reads and focused pytest]
- Context7 `/langchain-ai/langgraph` docs plus installed `StateGraph` introspection - LangGraph graph assembly mechanics. [CITED: Context7 `/langchain-ai/langgraph`; VERIFIED: uv run python inspect.signature]
- OWASP ASVS project/GitHub pages - ASVS source and current stable version. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

### Secondary (MEDIUM confidence)

- No secondary unverified web findings are needed for this codebase-specific phase. [VERIFIED: source hierarchy followed]

### Tertiary (LOW confidence)

- None. [VERIFIED: no `[ASSUMED]` claims intentionally used]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Versions were verified locally and Phase 52 should not change dependencies. [VERIFIED: uv run python importlib.metadata; VERIFIED: pyproject.toml]
- Architecture: HIGH - Current graph/router/source facts and target constraints are directly verified from source and planning artifacts. [VERIFIED: src/agent/graph.py; VERIFIED: tests/architecture/graph_baseline.py; VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md]
- Pitfalls: HIGH - Pitfalls map to existing source behavior, tests, and locked Phase 52/53 boundaries. [VERIFIED: src/agent/nodes/classify_intent.py; VERIFIED: tests/agent/test_nodes/test_classify_intent.py; VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md]
- Exact internal state field names: MEDIUM - Phase context leaves the exact field name to planner discretion, but target contract and current `AgentState` define likely surfaces. [VERIFIED: .planning/phases/52-safety-pre-route-node/52-CONTEXT.md; VERIFIED: src/agent/state.py; CITED: docs/contract-spec.md:628-629]

**Research date:** 2026-07-06 [VERIFIED: environment current_date]
**Valid until:** 2026-07-13 for graph-migration planning, because Phase 52-58 are active and source facts may change quickly. [VERIFIED: .planning/STATE.md; VERIFIED: .planning/ROADMAP.md]

