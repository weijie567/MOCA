# Phase 32: Intent Graph Migration - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 33 likely new/modified files
**Analogs found:** 33 / 33

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/graph_vocabulary.py` | utility / registry | transform | `src/agent/intent_policy.py`; `src/platform/context_projections.py` | role-match |
| `src/agent/graph.py` | config / route | request-response | `src/agent/graph.py` | exact |
| `src/agent/intent_policy.py` | registry / model | transform | `src/agent/intent_policy.py` | exact |
| `src/agent/routing.py` | route / utility | request-response | `src/agent/routing.py` | exact |
| `src/agent/nodes/classify_intent.py` | graph node | request-response / transform | `src/agent/nodes/classify_intent.py` | exact |
| `src/agent/nodes/extract_slots.py` | graph node | request-response / transform | `src/agent/nodes/extract_slots.py`; `src/agent/routing.py` | exact |
| `src/agent/nodes/receive_request.py` | graph node | transform | `src/agent/nodes/receive_request.py` | exact |
| `src/agent/state.py` | model | transform | `src/agent/state.py` | exact |
| `src/agent/trace.py` | service / utility | file-I/O / transform | `src/agent/trace.py` | exact |
| `src/api/routers/agent_runs.py` | controller / route | streaming / request-response | `src/api/routers/agent_runs.py` | exact |
| `src/api/routers/traces.py` | controller / route | request-response | `src/api/routers/traces.py` | exact |
| `src/repositories/trace_repo.py` | repository / projection | CRUD / transform | `src/repositories/trace_repo.py` | exact |
| `src/replay/service.py` | service / projection | event-driven / transform | `src/replay/service.py` | exact |
| `src/api/schemas/agent_runs.py` | model / schema | request-response | `src/api/schemas/agent_runs.py` | exact |
| `src/api/schemas/approvals.py` | model / schema | request-response | `src/api/schemas/approvals.py` | role-match |
| `tests/agent/test_graph_vocabulary.py` | test | transform | `tests/agent/test_intent_policy_registry.py`; `tests/platform/test_context_projections.py` | role-match |
| `tests/agent/test_graph.py` | test | request-response | `tests/agent/test_graph.py` | exact |
| `tests/agent/test_trace.py` | test | file-I/O / transform | `tests/agent/test_trace.py` | exact |
| `tests/agent/test_intent_policy_registry.py` | test | transform | `tests/agent/test_intent_policy_registry.py` | exact |
| `tests/agent/test_intent_routing.py` | test | request-response | `tests/agent/test_intent_routing.py` | exact |
| `tests/agent/test_nodes/test_classify_intent.py` | test | request-response / transform | `tests/agent/test_nodes/test_classify_intent.py` | exact |
| `tests/agent/test_required_slots.py` | test | transform | `tests/agent/test_required_slots.py` | exact |
| `tests/agent/test_session_memory_integration.py` | test | CRUD / transform | `tests/agent/test_session_memory_integration.py` | exact |
| `tests/agent/test_nodes/test_receive_request.py` | test | transform | `tests/agent/test_nodes/test_receive_request.py` | exact |
| `tests/agent/test_session_memory_load.py` | test | request-response / transform | `tests/agent/test_session_memory_load.py` | exact |
| `tests/agent/test_reviewed_memory_context_retrieve.py` | test | request-response / transform | `tests/agent/test_graph.py` reviewed-memory section | role-match |
| `tests/agent/test_memory_evidence_boundary.py` | test | transform / authorization boundary | `tests/agent/test_memory_evidence_boundary.py` | exact |
| `tests/test_agent_runs_api.py` | test | streaming / request-response | `tests/test_agent_runs_api.py` | exact |
| `tests/test_trace_api.py` | test | request-response | `tests/test_trace_api.py` | exact |
| `tests/replay/test_replay_api.py` | test | event-driven / request-response | `tests/replay/test_replay_api.py` | exact |
| `tests/architecture/test_trusted_context_boundaries.py` | test | static transform | `tests/architecture/test_trusted_context_boundaries.py` | exact |
| `tests/platform/test_context_projections.py` | test | transform | `tests/platform/test_context_projections.py` | exact |
| `tests/platform/test_trusted_context_factory.py` | test | transform / authorization boundary | `tests/platform/test_trusted_context_factory.py` | exact |

## Pattern Assignments

### `src/agent/graph_vocabulary.py` (utility / registry, transform)

**Analogs:** `src/agent/intent_policy.py`, `src/platform/context_projections.py`

**Imports and typed registry pattern** (copy style from `src/agent/intent_policy.py` lines 1-18):

```python
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.agent.schemas import IntentLiteral, RequiredSlotExpression, RequestedOperationLiteral, RiskTierLiteral


IntentRouteLiteral = Literal["investigate", "session_memory_load", "final_response"]


@dataclass(frozen=True)
class IntentDefinition:
```

**Read-only registry methods** (copy immutability pattern from `src/agent/intent_policy.py` lines 134-183):

```python
class IntentPolicyRegistry:
    """Read-only view over current intent policy constants."""

    def definitions(self) -> Mapping[str, IntentDefinition]:
        return MappingProxyType(INTENT_DEFINITIONS)

    def get_definition(self, name: str) -> IntentDefinition | None:
        return INTENT_DEFINITIONS.get(name)

    def route_policy(self) -> Mapping[str, IntentRouteLiteral]:
        return MappingProxyType(INTENT_ROUTE_POLICY)


class SlotPolicyRegistry:
    """Read-only view over required slot policy constants."""

    def required_slot_policy(self) -> Mapping[str, RequiredSlotExpression]:
        return MappingProxyType(REQUIRED_SLOT_POLICY)
```

**Projection helper shape** (copy explicit Pydantic projection style from `src/platform/context_projections.py` lines 15-84 and 293-320):

```python
class IntentPolicyContext(ProjectionMetadata):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["intent_policy_context.v1"] = "intent_policy_context.v1"
    tenant_id: str
    user_id: str
    role: str
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None
    channel: str


def project_to_intent_policy_context(
    trusted: TrustedContext,
    *,
    channel: str,
    policy_version: str | None = None,
    model_version: str | None = None,
    tool_version: str | None = None,
    artifact_ref: str | None = None,
    artifact_refs: list[str] | None = None,
) -> IntentPolicyContext:
```

**Target vocabulary source:** `docs/contract-spec.md` lines 431-433 define target registered nodes, routers, and legacy alias rules. Phase 32 helper should encode at least:

- `intent_classification` / `classify_intent` -> `contextual_intent_resolve`
- `session_memory_load` -> `session_context_load`
- `long_term_memory_retrieve` -> `memory_context_load`
- `route_after_intent` -> `route_after_contextual_intent`
- `route_after_slots` -> `route_after_slot_resolution`
- `rag_context_build` and `claim_verify` as `deferred_non_runnable`, not successful runtime nodes.

### `src/agent/graph.py` (config / route, request-response)

**Analog:** `src/agent/graph.py`

**Graph assembly pattern** (lines 131-169): keep legacy runtime keys compiling; add projections outside the edge map unless a plan explicitly scopes physical renames.

```python
def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("session_memory_load", session_memory_load)
    builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
    builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)
    builder.add_node("investigate", investigate)
    ...
    builder.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
            "investigate": "investigate",
            "session_memory_load": "session_memory_load",
        },
    )
```

**Planner note:** target names should be asserted through `graph_vocabulary` and trace/API projection tests first. Do not register runnable `rag_context_build` or `claim_verify` in Phase 32 unless the plan explicitly makes them fail-closed/non-runnable placeholders.

### `src/agent/intent_policy.py` (registry / model, transform)

**Analog:** `src/agent/intent_policy.py`

**Policy definition pattern** (lines 17-27, 38-131): keep policy in typed definitions, derive constants and registry views from those definitions.

```python
@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
    direct_response: bool = False
    evidence_required: bool = True
    high_risk: bool = False
    critical_route_class: bool = False
```

**Consumed registry migration target:** extend `IntentPolicyRegistry` / `SlotPolicyRegistry` from read-only views into consumed APIs. Existing direct constants to retire from consumers are visible in `rg` output:

```text
src/agent/nodes/classify_intent.py:201: policy_required_slots = REQUIRED_SLOT_POLICY.get(...)
src/agent/routing.py:231: if intent in DIRECT_RESPONSE_INTENTS:
src/agent/routing.py:233: if intent not in INTENT_ROUTE_POLICY:
src/agent/routing.py:235: policy = REQUIRED_SLOT_POLICY.get(intent)
```

### `src/agent/routing.py` (route / utility, request-response)

**Analog:** `src/agent/routing.py`

**Fail-closed router wrapper pattern** (lines 56-69):

```python
def route_after_intent(state: AgentState) -> str:
    try:
        route = _route_after_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in INTENT_ROUTES else "clarification_gate"


def route_after_slots(state: AgentState) -> str:
    try:
        route = _route_after_slots(state)
    except Exception:
        return "clarification_gate"
    return route if route in SLOT_ROUTES else "clarification_gate"
```

**Slot resolution semantics to preserve** (lines 93-138): current-turn slots override inherited slots; inherited session slots require trusted metadata.

```python
def resolve_slots_with_metadata(state: AgentState) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    extracted = state.get("extracted_slots")
    current_slots = {key: value for key, value in (extracted or {}).items() if value not in (None, "")}
    invalidations = detect_slot_invalidations(str(state.get("user_query") or ""))
    session_memory = state.get("session_memory")
    ...
    for slot, value in active_slots.items():
        if slot in resolved or value in (None, ""):
            continue
        metadata = slot_metadata.get(slot)
        if _trusted_session_slot(metadata, state):
            if slot in invalidations:
                resolved_metadata[slot] = _invalidated_slot_metadata(metadata, invalidations[slot])
                continue
            resolved[slot] = value
```

**Intent and slot route pattern** (lines 208-259): Phase 32 should move policy lookups behind registries but preserve deterministic finite keys.

```python
def _route_after_intent(state: AgentState) -> str:
    intent = _intent(state)
    requested_operation = state.get("requested_operation") or "advise"
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if requested_operation == "approval_decision":
        return "clarification_gate"
    ...
    if intent in DIRECT_RESPONSE_INTENTS:
        return "final_response"
    if intent not in INTENT_ROUTE_POLICY:
        return "clarification_gate"
    policy = REQUIRED_SLOT_POLICY.get(intent)
    if policy is not None and not policy.all_of and not policy.any_of:
        return "investigate"
    return "session_memory_load"
```

### `src/agent/nodes/classify_intent.py` (graph node, request-response / transform)

**Analog:** `src/agent/nodes/classify_intent.py`

**Candidate -> policy override -> effective classification pattern** (lines 125-238):

```python
def intent_result_to_state(
    result: IntentResultV3,
    prior_llm_outputs: dict[str, Any] | None = None,
    pre_route: PreRouteDecision | None = None,
    user_query: str = "",
    role: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    raw_primary_intent = result.primary_intent
    raw_requested_operation = result.requested_operation
    primary_intent, requested_operation, precedence_reasons = resolve_intent_precedence(...)
    policy_overrides: list[dict[str, Any]] = []
    ...
    classification_trace = {
        "raw_llm_classification": raw,
        "pre_route_decision": pre_route.model_dump() if pre_route else None,
        "policy_overrides": policy_overrides,
        "effective_classification": {
            "primary_intent": primary_intent,
            "requested_operation": requested_operation,
            "required_slots": policy_required_slots,
        },
        "risk_tier": risk_tier,
        "route_decision": route_decision,
        "reason_codes": reason_codes,
    }
```

**Forbidden state writes pattern** (lines 66-79): keep LLM output candidate-only and deny writes to approval/action/state authority.

```python
FORBIDDEN_STATE_WRITES = {
    "approval_result",
    "approval_revision_refs",
    "trusted_approval_result",
    "resume",
    "command",
    "extracted_slots",
    "active_slots",
    "risk_signals",
    "final_response",
    "tool_results",
    "action_result",
    "proposed_action",
}
```

### `src/agent/nodes/extract_slots.py` (graph node, request-response / transform)

**Analogs:** `src/agent/nodes/extract_slots.py`, `src/agent/routing.py`

**LLM candidate + deterministic merge pattern** (lines 62-97):

```python
async def extract_slots(state: AgentState, config: RunnableConfig | None = None) -> dict:
    started_at = _now_iso()
    prompt_assembly = await _assemble_slot_prompt(state, config)
    messages = prompt_assembly.to_messages()
    structured_llm = _get_llm().with_structured_output(SlotExtractionResult)
    ...
            extracted = result.model_dump()
            active_slots, active_slot_metadata = resolve_slots_with_metadata({**state, "extracted_slots": extracted})
            outputs = {**(state.get("llm_outputs") or {}), "extract_slots": extracted}
            return {
                "extracted_slots": extracted,
                "active_slots": active_slots,
                "active_slot_metadata": active_slot_metadata,
                "llm_outputs": outputs,
```

**Planner note:** expose `slot_resolution_gate` semantics by reusing or moving `resolve_slots_with_metadata`; avoid a second merge pass that can reintroduce stale slots.

### `src/agent/nodes/receive_request.py` and `src/agent/state.py` (node/model, transform)

**Analogs:** `src/agent/nodes/receive_request.py`, `src/agent/state.py`

**State declaration pattern** (`src/agent/state.py` lines 48-141): declare shared target fields only when more than one node/API surface consumes them.

```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""

    # Durable graph/checkpoint context: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    ...
    trace_steps: list[dict[str, Any]] | None
```

**Reset inventory pattern** (`src/agent/nodes/receive_request.py` lines 45-137): any new per-turn target projection or merchant-context evidence field must be explicitly reset here and tested.

```python
async def receive_request(state: AgentState) -> dict:
    """Reset per-turn state so checkpointed graph context cannot leak stale context."""
    started_at = _now_iso()
    active_flow_state = _project_active_flow_state(state)
    trace_steps = [
        {
            "node": "receive_request",
            "status": "completed",
            "started_at": started_at,
            "completed_at": _now_iso(),
            "provider_latency_ms": None,
            "retry_count": 0,
            "metrics_json": None,
        }
    ]

    return {
        "user_query": state.get("user_query"),
        "normalized_query": None,
        "current_intent": None,
        ...
        "current_run_id": state.get("current_run_id") or str(uuid4()),
        "run_started_at": started_at,
        "trace_steps": trace_steps,
    }
```

### `src/agent/trace.py` (service / utility, file-I/O / transform)

**Analog:** `src/agent/trace.py`

**Persist legacy node names unchanged** (lines 81-121 and 164-205):

```python
async def write_agent_steps(
    session: AsyncSession,
    *,
    run_id: str,
    trace_steps: list[dict[str, Any]],
) -> list[AgentStep]:
    """Insert one AgentStep row per trace step and return persisted instances."""
    steps: list[AgentStep] = []
    for idx, step in enumerate(trace_steps):
        ...
        agent_step = AgentStep(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            node_name=str(step.get("node") or "unknown"),
            step_index=idx,
            status=str(step.get("status") or "completed"),
            ...
            metrics_json=step.get("metrics_json"),
```

**Trace summary projection pattern** (lines 234-267): add target projection fields beside existing `nodes_executed`; do not replace it.

```python
def build_trace_summary(
    run_id: str,
    final_state: dict[str, Any],
    total_latency_ms: int,
) -> dict[str, Any]:
    """Build the safe trace summary returned by the API response."""
    trace_steps = final_state.get("trace_steps") or []
    nodes_executed = [str(step.get("node") or "unknown") for step in trace_steps]
    tools_called: list[str] = []
    ...
    return {
        "run_id": run_id,
        "intent": final_state.get("current_intent") or "unknown",
        "nodes_executed": nodes_executed,
```

### `src/api/routers/agent_runs.py` (controller / route, streaming / request-response)

**Analog:** `src/api/routers/agent_runs.py`

**Trusted graph config pattern** (lines 74-88): all auth/scope projection must come from `TrustedContextFactory`, not request body, memory, or LLM text.

```python
def _trusted_graph_config(trusted_context: TrustedContext) -> dict[str, Any]:
    # Compatibility keys stay derived from canonical trusted_context for existing callers.
    return {
        "trusted_context": trusted_context.model_dump(mode="json"),
        "permissions": list(trusted_context.permissions),
        "merchant_scope": trusted_context.merchant_scope.model_dump(mode="json"),
        "trace_id": trusted_context.trace_id or "",
        "session_id": trusted_context.session_id,
    }
```

**Streaming payload pattern** (lines 1011-1031 and 1053-1082): add canonical projection fields through payload/event data, preserving `node_name`.

```python
def _sse_event(
    *,
    event_type: str,
    run_id: str,
    step_index: int,
    status: str,
    message: str,
    payload: dict[str, Any],
    node_name: str | None = None,
) -> dict[str, str]:
    data = {
        "event_type": event_type,
        "run_id": run_id,
        "step_index": step_index,
        "node_name": node_name,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
```

**Visibility pattern** (lines 1135-1144): do not broaden manager/supervisor access in Phase 32.

```python
def _ensure_can_view_run(run: AgentRun | None, *, user: User) -> None:
    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```

### `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/replay/service.py` (API/repository/service projections)

**Analogs:** `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/replay/service.py`

**Trace API projection pattern** (`src/api/routers/traces.py` lines 22-78): add target fields in `steps` or `timeline` as additive fields only.

```python
steps=[
    {
        "node": step.node_name,
        "status": step.status,
        "latency_ms": step.latency_ms,
        "tool_name": step.tool_name,
    }
    for step in steps
],
```

**Timeline safe projection pattern** (`src/repositories/trace_repo.py` lines 56-79 and 128-143):

```python
for step in steps:
    timeline.append(
        {
            "type": "agent_step",
            "time": step.started_at.isoformat(),
            "title": f"Node: {step.node_name}",
            "status": step.status,
            "detail": {
                "node_name": step.node_name,
                "tool_name": step.tool_name,
                "latency_ms": step.latency_ms,
                "provider_latency_ms": step.provider_latency_ms,
            },
        }
    )
```

**Replay projection pattern** (`src/replay/service.py` lines 206-252): add `target_node_name` beside `node_name`; keep redaction guards.

```python
def project_event(
    self,
    event: AgentTraceEvent,
    *,
    pairing_status: OperationPairingStatus | None = None,
    include_retention_class: bool = True,
) -> dict[str, Any]:
    """Project stored minimal or V3 rows into the strict ReplayEventV3 shape."""
    retention_class = retention_for_event_type(event.event_type)
    payload = dict(event.redacted_payload or {})
    refs = dict(event.resource_refs or {})
    guard_redacted_payload(payload)
    guard_resource_refs(refs)
    ...
            "node_name": event.node_name,
```

### `src/api/schemas/agent_runs.py` and `src/api/schemas/approvals.py` (schemas, request-response)

**Analogs:** `src/api/schemas/agent_runs.py`, `src/api/schemas/approvals.py`

**Schema style** (`src/api/schemas/agent_runs.py` lines 11-32): use Pydantic `BaseModel`; additive fields should be optional unless replacing a field is intentionally scoped.

```python
class RunStatusResponse(BaseModel):
    run_id: str
    final_status: str
    started_at: datetime
    completed_at: datetime | None = None
    final_response: str | None = None


class SseEventPayload(BaseModel):
    evidence_count: int | None = None
    tool_name: str | None = None
    risk_level: str | None = None
    short_summary: str | None = None
```

**Trace response style** (`src/api/schemas/approvals.py` lines 83-93):

```python
class TraceResponse(BaseModel):
    run_id: str
    thread_id: str
    final_status: str
    started_at: datetime
    completed_at: datetime | None
    total_latency_ms: int | None
    steps: list[dict[str, Any]]
    approvals: list[ApprovalResponse]
    action_drafts: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
```

## Test Pattern Assignments

### `tests/agent/test_graph_vocabulary.py`

**Analogs:** `tests/agent/test_intent_policy_registry.py`, `tests/platform/test_context_projections.py`

Copy registry immutability and projection-local assertions:

```python
# tests/agent/test_intent_policy_registry.py lines 44-56
def test_registries_are_read_only() -> None:
    intent_registry = IntentPolicyRegistry()
    slot_registry = SlotPolicyRegistry()

    with pytest.raises(TypeError):
        intent_registry.definitions()["policy_qa"] = INTENT_DEFINITIONS["unsupported"]
```

```python
# tests/platform/test_context_projections.py lines 156-167
def test_intent_policy_context_channel_is_projection_local() -> None:
    trusted = _trusted_context()

    context = project_to_intent_policy_context(trusted, channel="agent_runs", policy_version="intent_policy.v1")

    assert context.channel == "agent_runs"
    assert "channel" not in trusted.model_dump()
```

Required RED assertions:

- legacy node names project to target names.
- target names pass through idempotently.
- unknown names pass through or return explicit unknown per helper contract.
- `rag_context_build` and `claim_verify` are cataloged as `deferred_non_runnable`.
- router aliases cover `route_after_contextual_intent` and `route_after_slot_resolution`.

### `tests/agent/test_graph.py`

**Analog:** `tests/agent/test_graph.py`

**Router edge key table pattern** (lines 38-44):

```python
ROUTER_EDGE_KEYS = {
    "route_after_intent": {"clarification_gate", "final_response", "investigate", "session_memory_load"},
    "route_after_slots": {"clarification_gate", "investigate", "long_term_memory_retrieve"},
    "route_after_risk": {"approval_gate", "final_response"},
    "route_after_approval": {"assess_risk_and_approval", "action_draft", "final_response"},
    "route_after_investigate": {"final_response", "clarification_gate", "recommendation_generation"},
}
```

**Trace summary shape test pattern** (lines 655-677): update exact key set intentionally if adding `target_nodes_executed`.

```python
summary = trace_module.build_trace_summary(final_state["current_run_id"], final_state, 1000)

assert set(summary) == {
    "run_id",
    "intent",
    "nodes_executed",
    "tools_called",
    "evidence_count",
    "risk_level",
    "total_latency_ms",
    "final_status",
}
```

**Graph compile and router totality pattern** (lines 680-748):

```python
def test_graph_compiles_with_investigate():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)

    assert {"investigate", "clarification_gate", "session_memory_load", "long_term_memory_retrieve"} <= nodes
    assert "action_draft" in nodes
    assert "execute_action" not in nodes
```

### `tests/agent/test_intent_policy_registry.py` and `tests/agent/test_intent_routing.py`

**Analogs:** same files

**Current registry tests** (`tests/agent/test_intent_policy_registry.py` lines 21-56) mirror constants. Phase 32 should add consumption tests with monkeypatch/fake registry methods so bypassing the registry fails.

```python
def test_intent_policy_registry_mirrors_existing_constants() -> None:
    registry = IntentPolicyRegistry()

    assert registry.definitions() == INTENT_DEFINITIONS
    assert registry.intent_names() == tuple(INTENT_DEFINITIONS)
    assert registry.precedence_order() == PRECEDENCE_INTENTS
    assert registry.route_policy() == INTENT_ROUTE_POLICY
```

**Safety and totality assertions** (`tests/agent/test_intent_routing.py` lines 172-200 and 261-288):

```python
update = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

assert update["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
assert update["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
assert update["requested_operation"] == "advise"
assert update["risk_tier"] == "forbidden_in_chat"
assert update["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
assert route_after_intent(update) == "clarification_gate"
```

```python
@pytest.mark.parametrize(
    "state",
    [
        {},
        {"primary_intent": "small_talk", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "unsupported", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "policy_qa", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9},
        {"routing_hints": {"pre_route_disposition": "approval_chat_not_trusted"}},
    ],
)
def test_route_after_intent_totality(state):
    assert route_after_intent(state) in INTENT_ROUTES
```

### `tests/agent/test_nodes/test_classify_intent.py`

**Analog:** `tests/agent/test_nodes/test_classify_intent.py`

**Effective classification test pattern** (lines 31-46):

```python
result = await classify_intent_module.classify_intent(base_state)

assert result["current_intent"] == "refund_troubleshooting"
assert result["primary_intent"] == "refund_troubleshooting"
assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "refund_troubleshooting"
assert result["classification_trace"]["effective_classification"]["primary_intent"] == "refund_troubleshooting"
assert result["classification_trace"]["route_decision"] == "session_memory_load"
```

**Approval chat fail-closed pattern** (lines 73-88):

```python
result = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

assert result["current_intent"] == "unsupported"
assert result["requested_operation"] == "advise"
assert result["risk_tier"] == "forbidden_in_chat"
assert result["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
assert "approval_result" not in result
assert "resume" not in result
```

### `tests/agent/test_required_slots.py` and `tests/agent/test_session_memory_integration.py`

**Analogs:** same files

**Slot candidate and stale active slot denial** (`tests/agent/test_required_slots.py` lines 26-37):

```python
state = {
    "primary_intent": "refund_troubleshooting",
    "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
    "candidate_slots": {"order_id": "ORD-1"},
    "active_slots": {"order_id": "ORD-STALE", "refund_case_id": "RF-STALE"},
    "extracted_slots": {},
    "session_memory": {"continuity_claimed": False, "active_slots": {"refund_case_id": "RF-SESSION-STALE"}},
}

assert route_after_slots(state) == "clarification_gate"
```

**Wrong scope / expired / incompatible fail-closed pattern** (`tests/agent/test_required_slots.py` lines 107-160):

```python
for metadata_update in cases:
    state = _trusted_state(metadata_update)
    assert resolve_slots_for_completeness(state) == {}
    assert route_after_slots(state) == "clarification_gate"
```

**DB-backed integration pattern** (`tests/agent/test_session_memory_integration.py` lines 129-177 and 179-252): use persisted session memory, then assert current-turn override and wrong-scope denial through `route_after_slots`.

### `tests/agent/test_nodes/test_receive_request.py`

**Analog:** `tests/agent/test_nodes/test_receive_request.py`

**Reset test pattern** (lines 9-50, 82-107, 148-175):

```python
result = await receive_request(state)

assert result["current_intent"] is None
assert result["intent_confidence"] is None
assert result["classification_trace"] is None
assert result["required_slots"] == {"all_of": [], "any_of": [], "optional": []}
assert result["candidate_slots"] == {}
assert [step["node"] for step in result["trace_steps"]] == ["receive_request"]
```

```python
def test_agent_state_declares_rag_verifier_fields():
    annotations = AgentState.__annotations__

    for field in (
        "rag_context_bundle",
        "rag_verification",
        "verifier_status",
        "verification_route",
        "verifier_reason_codes",
        "verifier_safe_citation_refs",
        "verifier_metrics",
    ):
        assert field in annotations
```

### `tests/agent/test_session_memory_load.py`

**Analog:** `tests/agent/test_session_memory_load.py`

**Target + legacy field compatibility pattern** (lines 117-172):

```python
result = await session_context_load(
    {**_state(), "current_run_id": run_id},
    {"configurable": {"session": FakeSession()}},
)

assert result["session_context"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
assert result["session_context_bundle"]["schema_version"] == "session_context_bundle.v1"
assert result["session_context_load_status"]["schema_version"] == "session_context_load_status.v1"
assert result["session_context_load_status"]["authority_class"] == "contextual_only"
assert result["session_memory"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
assert result["session_memory_bundle"]["schema_version"] == "session_memory_bundle.v1"
assert result["trace_steps"][-1]["node"] == "session_context_load"
```

### `tests/agent/test_trace.py`, `tests/test_trace_api.py`, and `tests/replay/test_replay_api.py`

**Analogs:** same files

**Trace persistence pattern** (`tests/agent/test_trace.py` lines 14-70): persist rows, then assert legacy `node_name` remains unchanged.

```python
await write_agent_steps(
    session,
    run_id=run_id,
    trace_steps=[
        {"node": "investigate", "status": "completed", "tools_called": ["get_order", "search_policy"]},
        {"node": "legacy_tool_step", "status": "completed", "tool_name": "get_ticket"},
    ],
)

assert [row.node_name for row in rows] == ["investigate", "legacy_tool_step"]
```

**Trace API visibility and safe payload pattern** (`tests/test_trace_api.py` lines 17-60, 101-120):

```python
assert payload["data"]["steps"][0] == {
    "node": "receive_request",
    "status": "completed",
    "latency_ms": 12,
    "tool_name": None,
}
assert "input_query" not in payload["data"]
assert "final_response" not in payload["data"]
assert "secret" not in str(payload["data"])
```

```python
for viewer in (supervisor, approval_manager):
    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=_auth_header(viewer, ["agent:chat"]),
    )
    assert response.status_code == 403
```

**Replay compatibility pattern** (`tests/replay/test_replay_api.py` lines 130-148): legacy trace fallback remains valid.

```python
response = await client.get(
    f"/api/v1/agent-runs/{run_id}/trace",
    headers=await _support_headers(client),
)
payload = response.json()

assert response.status_code == 200
assert payload["data"]["timeline"][0]["type"] == "agent_step"
assert payload["data"]["timeline"][0]["detail"]["node_name"] == "receive_request"
```

### `tests/test_agent_runs_api.py`

**Analog:** `tests/test_agent_runs_api.py`

**Trusted graph config pattern** (lines 880-918):

```python
trusted_context = TrustedContext.model_validate(configurable["trusted_context"])
legacy_identity = project_to_legacy_agent_state_identity(trusted_context)
assert trusted_context.schema_version == "trusted_context.v1"
assert trusted_context.run_id == str(run_id)
assert trusted_context.trace_id == configurable["trace_id"]
assert "current_run_id" not in trusted_context.model_dump()
assert input_state["current_run_id"] == legacy_identity["current_run_id"]
assert configurable["permissions"] == trusted_context.permissions
assert configurable["merchant_scope"] == trusted_context.merchant_scope.model_dump(mode="json")
```

**Visibility denial pattern** (lines 1055-1106):

```python
for viewer in (supervisor, approval_manager):
    status_response = await client.get(
        f"/api/v1/agent-runs/{run.id}",
        headers=_auth_header(viewer, ["agent:chat"]),
    )
    evidence_response = await client.get(
        f"/api/v1/agent-runs/{run.id}/evidence",
        headers=_auth_header(viewer, ["agent:chat"]),
    )

    assert status_response.status_code == 403
    assert evidence_response.status_code == 403
```

**SSE lifecycle fixture pattern** (lines 365-389): use fake graph lifecycle events to assert additive `target_node` / merchant-context payloads without hitting live graph dependencies.

### `tests/architecture/test_trusted_context_boundaries.py`

**Analog:** same file

**Static boundary pattern** (lines 58-91): if Phase 32 adds projection helpers, add a static architecture test that route seams use helpers and do not construct trusted context payloads directly.

```python
def test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors() -> None:
    seams = [
        ROOT / "src" / "api" / "routers" / "search.py",
        ROOT / "src" / "api" / "routers" / "agent.py",
        ROOT / "src" / "api" / "routers" / "agent_runs.py",
        ROOT / "src" / "agent" / "nodes" / "investigate.py",
        ROOT / "src" / "agent" / "nodes" / "action_draft.py",
        ROOT / "src" / "tools" / "executors" / "knowledge.py",
    ]
    ...
    assert violations == []
```

### `tests/platform/test_context_projections.py` and `tests/platform/test_trusted_context_factory.py`

**Analogs:** same files

**Projection does not widen identity/scope** (`tests/platform/test_context_projections.py` lines 124-167, 188-198):

```python
for projection in projections:
    payload = projection.model_dump()
    assert payload["tenant_id"] == trusted.tenant_id
    assert payload["user_id"] == trusted.user_id
    assert payload["role"] == trusted.role
    assert payload["thread_id"] == trusted.thread_id
    assert payload["run_id"] == trusted.run_id
    assert payload.get("permissions") in (None, trusted.permissions)
    assert payload.get("merchant_scope") in (None, trusted.merchant_scope.model_dump(), ["merchant-1"])
```

```python
identity = project_to_legacy_agent_state_identity(trusted)

assert identity["current_run_id"] == trusted.run_id
assert "permissions" not in identity
assert "merchant_scope" not in identity
```

**Trusted factory denial pattern** (`tests/platform/test_trusted_context_factory.py` lines 51-68 and 106-128):

```python
@pytest.mark.parametrize(
    "override_kwargs",
    [
        {"tenant_id": "tenant-from-request"},
        {"user_id": "user-from-request"},
        {"role": "admin"},
        {"permissions": ["tool:execute_refund"]},
        {"merchant_scope": {"merchant_ids": ["*"]}},
        {"request_payload": {"tenant_id": "tenant-from-body", "merchant_scope": {"merchant_ids": ["*"]}}},
        {"llm_output": {"permissions": ["tool:execute_refund"], "merchant_scope": {"merchant_ids": ["*"]}}},
    ],
)
def test_factory_rejects_user_payload_and_llm_override_kwargs(override_kwargs: dict) -> None:
```

### `tests/agent/test_memory_evidence_boundary.py`

**Analog:** same file

**Contextual memory is not authority pattern** (lines 239-283 and 286-359): apply this to target merchant context evidence. Evidence status must not become authorization or business fact proof.

```python
assert final_state["active_slots"]["order_id"] == "ORD-1001"
assert final_state["retrieved_evidence"]["evidence_refs"] == []
assert final_state["policy_evidence"] == []
assert final_state.get("approval_result") is None
assert final_state.get("action_result") is None
assert final_state.get("proposed_action") is None
assert "EvidenceRefV1" not in json.dumps(final_state["session_memory"], ensure_ascii=False)
```

## Shared Patterns

### Canonical Graph Vocabulary

**Source:** `docs/contract-spec.md` lines 431-433, `src/agent/intent_policy.py` lines 134-183

**Apply to:** `src/agent/graph_vocabulary.py`, `src/agent/trace.py`, `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/replay/service.py`, graph/eval/API tests.

Pattern:

- central typed helper with read-only maps.
- implementation names and target names both resolve to target canonical names.
- legacy fields remain unchanged for debugging/persistence.
- target projection is additive.

### Compatibility Wrappers

**Source:** `src/agent/nodes/session_memory_load.py` lines 16-29 and `src/agent/nodes/long_term_memory_retrieve.py` lines 15-31

**Apply to:** graph vocabulary aliases and any explicit Phase 32 wrapper.

```python
async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the target session_context_load node."""
    return await session_context_load(
        state,
        config,
        node_name="session_memory_load",
        ...
    )
```

### Router Totality And Fail-Closed Behavior

**Source:** `src/agent/routing.py` lines 56-69; `tests/agent/test_graph.py` lines 719-748

**Apply to:** `route_after_contextual_intent`, `route_after_slot_resolution`, tests for both legacy keys and target router projection.

All routers must be deterministic, side-effect-free, and return finite keys. Invalid state, exception, unknown policy, low confidence, approval chat, stale slots, or missing slots should route to `clarification_gate` or safe final response.

### Registry-Owned Effective Policy

**Source:** `src/agent/intent_policy.py` lines 134-183; direct-consumption gap from `rg` in `src/agent/routing.py` and `src/agent/nodes/classify_intent.py`

**Apply to:** `src/agent/intent_policy.py`, `src/agent/routing.py`, `src/agent/nodes/classify_intent.py`, `src/agent/nodes/extract_slots.py`, registry tests.

Tests should fail if effective route, risk tier, or required slots bypass `IntentPolicyRegistry` / `SlotPolicyRegistry`. LLM `IntentResultV3.required_slots` remains observable candidate metadata, not the authoritative policy.

### Trace/API Projection Without Storage Rename

**Source:** `src/agent/trace.py` lines 81-121 and 234-267; `src/api/routers/traces.py` lines 52-60; `src/repositories/trace_repo.py` lines 65-79; `src/replay/service.py` lines 220-249

**Apply to:** trace summary, SSE events, trace API, replay API, eval/golden projection surfaces.

Keep `trace_steps[].node`, `AgentStep.node_name`, and existing API `node`/`node_name` values legacy-compatible. Add `target_node`, `target_node_name`, `target_router`, or `target_nodes_executed` beside existing fields.

### Target Merchant Context Evidence Is Not Authorization

**Source:** `src/api/routers/agent_runs.py` lines 1135-1144; `tests/test_agent_runs_api.py` lines 1055-1106; `tests/platform/test_trusted_context_factory.py` lines 106-128; `tests/agent/test_memory_evidence_boundary.py` lines 239-359

**Apply to:** AgentRun status/detail/evidence, trace/replay projections, graph state fields.

Allowed target merchant context statuses: `resolved`, `deferred`, `unavailable`, `not_applicable`. This status is evidence only. It must not grant manager/supervisor-style run visibility in Phase 32. Until same-merchant proof is explicitly implemented, owner/admin-only access remains the pattern.

### No Fake Phase 33 Nodes

**Source:** `.planning/REQUIREMENTS.md` lines 44, 49-50; `docs/contract-spec.md` lines 641-643; local `rg` found no `rag_context_build` / `claim_verify` runtime registration in `src/agent`, `src/api`, or current focused tests.

**Apply to:** graph vocabulary helper, graph compile tests, static scans.

Phase 32 may catalog `rag_context_build` and `claim_verify` as target names, but it must not introduce successful runnable RAG/claim behavior. Any placeholder must be `deferred_non_runnable` or fail closed.

### MOCA Test Command Rule

**Source:** `AGENTS.md` local validation rule; `32-VALIDATION.md` lines 20-23 and 41-45

**Apply to:** every PLAN verify command and test instruction.

Use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or repo `.venv/bin/pytest ...`. Do not write bare `pytest` or bare `python -m pytest` as runnable validation commands. Bare commands are invalid in MOCA because they can hit the wrong Python.

Recommended focused commands copied from Phase 32 validation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_trace.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short
```

## No Analog Found

None. The new `src/agent/graph_vocabulary.py` and `tests/agent/test_graph_vocabulary.py` do not have exact predecessors, but the registry/projection patterns in `src/agent/intent_policy.py`, `src/platform/context_projections.py`, `tests/agent/test_intent_policy_registry.py`, and `tests/platform/test_context_projections.py` are close enough for implementation.

## Metadata

**Analog search scope:** `src/agent`, `src/api/routers`, `src/api/schemas`, `src/platform`, `src/repositories`, `src/replay`, `tests/agent`, `tests/replay`, `tests/architecture`, `tests/platform`, `tests/test_agent_runs_api.py`, `tests/test_trace_api.py`

**Files scanned:** 141 unique files

**Pattern extraction date:** 2026-06-28

**Important planning constraint:** Phase 32 should be split into multiple plans. Do not collapse graph vocabulary/projection, intent registry consumption, slot gate/router migration, trace/API/AgentRun merchant evidence, and final verification into one broad `32-01-PLAN.md`.
