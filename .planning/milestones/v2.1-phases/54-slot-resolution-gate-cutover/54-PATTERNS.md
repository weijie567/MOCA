# Phase 54: slot-resolution-gate-cutover - Pattern Map

**Mapped:** 2026-07-07  
**Files analyzed:** 25  
**Analogs found:** 25 / 25  
**Context:** 已读取 `54-CONTEXT.md`、`54-RESEARCH.md`、`54-VALIDATION.md`、`AGENTS.md`、`CLAUDE.md`。本仓库没有 `.claude/skills/` 或 `.agents/skills/` project skills。

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agent/nodes/slot_resolution_gate.py` | node | request-response / transform | `src/agent/nodes/extract_slots.py`; `src/agent/nodes/contextual_intent_resolve.py` | role+flow-match |
| `src/agent/nodes/extract_slots.py` | compatibility node / utility | request-response / transform | self; `src/agent/nodes/classify_intent.py` compatibility wrapper pattern | role-match |
| `src/agent/routing.py` | router / utility | request-response | existing `route_after_contextual_intent`, `route_after_slots`, slot helpers | exact |
| `src/agent/intent_policy.py` | policy model / registry | transform | `SlotPolicyRegistry`, `slot_intent_compatible` | exact |
| `src/agent/state.py` | model / state contract | transform | existing `AgentState` ephemeral fields | exact |
| `src/agent/schemas.py` | model / validation | transform | `RequiredSlotExpression`, `SlotExtractionResult`, `IntentResultV3` | role-match |
| `tests/agent/test_nodes/test_slot_resolution_gate.py` | test | request-response / transform | `tests/agent/test_nodes/test_extract_slots.py`; `tests/agent/test_required_slots.py` | role+flow-match |
| `tests/agent/test_nodes/test_extract_slots.py` | test | request-response / transform | self | exact |
| `tests/agent/test_required_slots.py` | test | request-response / transform | self | exact |
| `tests/agent/test_nodes/test_contextual_intent_resolve.py` | test | request-response / transform | self | exact |
| `src/agent/graph.py` | graph config / route | request-response | existing `build_graph()` cutover wiring | exact |
| `tests/architecture/graph_baseline.py` | architecture test utility | transform / static analysis | self | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | architecture test | transform / static analysis | self | exact |
| `tests/agent/test_graph.py` | graph integration test | request-response | existing graph compile/router/memory-hint tests | exact |
| `tests/test_graph_routing.py` | router test | request-response | contextual intent router tests | exact |
| `tests/agent/test_intent_routing.py` | router/policy test | request-response / transform | slot and contextual intent route tests | exact |
| `src/agent/graph_vocabulary.py` | utility / projection | transform | existing vocabulary entry and trace projection helpers | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform | self | exact |
| `tests/agent/test_trace.py` | test | transform | target graph projection summary tests | exact |
| `tests/test_trace_api.py` | API test | request-response / transform | timeline target projection tests | role+flow-match |
| `src/api/routers/agent_runs.py` | API router | streaming / request-response | SSE node message and target projection helpers | role+flow-match |
| `tests/test_agent_runs_api.py` | API test | streaming / request-response | SSE target projection and fake graph stream tests | role+flow-match |
| `docs/current-langgraph-architecture.md` | documentation | transform | Phase 53 current-source snapshot | exact |
| `.planning/ARCHITECTURE-DEBT.md` | ledger documentation | transform | Phase 53 closeout and WR-01 entries | exact |
| `.planning/phases/54-slot-resolution-gate-cutover/54-VALIDATION.md` | validation artifact | batch / verification | existing validation command map | exact |

## Pattern Assignments

### `src/agent/nodes/slot_resolution_gate.py` (node, request-response / transform)

**Analog:** `src/agent/nodes/extract_slots.py` + `src/agent/nodes/contextual_intent_resolve.py`

**Imports / dependency pattern** (`src/agent/nodes/extract_slots.py` lines 1-19):

```python
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.context import ContextAssembler, PromptAssembly, project_candidate_slot_hints_for_prompt
from src.agent.context.session_memory_bundle import load_session_prompt_context
from src.agent.graph_vocabulary import target_graph_name
from src.agent.prompts import EXTRACT_SLOTS_SYSTEM
from src.agent.routing import resolve_slots_with_metadata
from src.agent.schemas import SlotExtractionResult
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
from src.config import settings
```

**LLM / trace helper pattern** (`src/agent/nodes/extract_slots.py` lines 26-64):

```python
def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )

def _trace_step(...):
    metrics_json = {
        "model": settings.llm_model,
        "provider": "dashscope",
        "context_chars": context_chars,
        "target_node": target_graph_name(node, kind="node"),
    }
```

Phase 54 copy rule: new node trace must call `_trace_step("slot_resolution_gate", ...)`; do not emit new runtime trace step with `"extract_slots"` except from retained compatibility wrapper.

**Core node pattern** (`src/agent/nodes/extract_slots.py` lines 67-102):

```python
async def extract_slots(state: AgentState, config: RunnableConfig | None = None) -> dict:
    started_at = _now_iso()
    prompt_assembly = await _assemble_slot_prompt(state, config)
    messages = prompt_assembly.to_messages()
    structured_llm = _get_llm().with_structured_output(SlotExtractionResult)
    ...
    result = await structured_llm.ainvoke(messages)
    extracted = result.model_dump()
    active_slots, active_slot_metadata = resolve_slots_with_metadata({**state, "extracted_slots": extracted})
    outputs = {**(state.get("llm_outputs") or {}), "extract_slots": extracted}
    return {
        "extracted_slots": extracted,
        "active_slots": active_slots,
        "active_slot_metadata": active_slot_metadata,
        "llm_outputs": outputs,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("extract_slots", ...)],
    }
```

Phase 54 copy rule: keep this flow, but add explicit `slot_resolution_trace` / provenance payload before returning. Keep compatibility fields: `extracted_slots`, `active_slots`, `active_slot_metadata`, and missing-slot routing hints.

**Error handling pattern** (`src/agent/nodes/extract_slots.py` lines 103-129):

```python
except (ValidationError, ValueError, TimeoutError, Exception) as exc:
    provider_latency_ms = round((time.perf_counter() - t0) * 1000)
    last_error = str(exc)
    if attempt == 0:
        messages.append({"role": "user", "content": f"Validation failed: {last_error}. Respond with valid JSON."})

return {
    "extracted_slots": {},
    "node_errors": (state.get("node_errors") or []) + [{"node": "extract_slots", "error": last_error, "retry_count": 2}],
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step("extract_slots", "error", ...)],
}
```

Phase 54 copy rule: error output should use `node: "slot_resolution_gate"` and fail closed by leaving required slots unsatisfied / setting provenance reason codes. Do not let LLM failure mark slots resolved.

**Prompt assembly pattern** (`src/agent/nodes/extract_slots.py` lines 132-153):

```python
candidate_slots = state.get("candidate_slots")
node_hints = project_candidate_slot_hints_for_prompt(candidate_slots) if isinstance(candidate_slots, dict) and candidate_slots else ""
prompt_context = await load_session_prompt_context(state, config)
return ContextAssembler().assemble(
    system_prompt=EXTRACT_SLOTS_SYSTEM,
    current_user_message=str(state.get("normalized_query") or state.get("user_query") or ""),
    working_state=project_working_state(state),
    memory_context_bundle=state.get("session_context_bundle"),
    node_hints=node_hints,
)
```

**Canonical provenance shape analog** (`src/agent/nodes/contextual_intent_resolve.py` lines 407-444):

```python
classification_trace = {
    "raw_llm_classification": raw,
    "candidate_classification": raw,
    "policy_owner": "IntentPolicyRegistry",
    "policy_overrides": policy_overrides,
    "effective_classification": {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "required_slots": policy_required_slots,
    },
    "route_decision": route_decision,
    "reason_codes": reason_codes,
}
llm_outputs = {
    **(prior_llm_outputs or {}),
    "contextual_intent_resolve": {
        "raw": raw,
        "classification_trace": classification_trace,
        "eval_metadata": {...},
    },
}
```

Phase 54 copy rule: use the same layered trace idea for slot resolution: raw/candidate slots, policy owner, explicit current-turn slots, inherited accepted slots, invalidated/stale/incompatible rejected slots, resolved slots, missing required slots, route decision, reason codes.

---

### `src/agent/routing.py` (router / utility, request-response)

**Analog:** existing slot and contextual routers.

**Fail-closed wrapper pattern** (`src/agent/routing.py` lines 37-40 and 77-98):

```python
CONTEXTUAL_INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "extract_slots"}
SLOT_ROUTES = {"clarification_gate", "investigate", "long_term_memory_retrieve"}

def route_after_contextual_intent(state: AgentState) -> str:
    try:
        route = _route_after_contextual_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in CONTEXTUAL_INTENT_ROUTES else "clarification_gate"

def route_after_slots(state: AgentState) -> str:
    try:
        route = _route_after_slots(state)
    except Exception:
        return "clarification_gate"
    return route if route in SLOT_ROUTES else "clarification_gate"
```

Phase 54 copy rule: introduce/promote `route_after_slot_resolution` with this wrapper pattern; `route_after_slots` should delegate to it if retained. `CONTEXTUAL_INTENT_ROUTES` must replace `"extract_slots"` with `"slot_resolution_gate"`.

**Deterministic slot merge pattern** (`src/agent/routing.py` lines 113-164):

```python
def resolve_slots_with_metadata(state: AgentState) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    extracted = state.get("extracted_slots")
    current_slots = {key: value for key, value in (extracted or {}).items() if value not in (None, "")}
    invalidations = detect_slot_invalidations(str(state.get("user_query") or ""))
    session_memory = _session_slot_continuity(state)
    ...
    for slot, value in current_slots.items():
        resolved[slot] = value
        resolved_metadata[slot] = _current_turn_slot_metadata(...)
    ...
    decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(...)
    if decision.accepted:
        resolved[slot] = value
        resolved_metadata[slot] = {
            **metadata,
            "source": "trusted_session_memory",
            "explicit_current_turn": False,
        }
    elif decision.reason_code == "slot_invalidated":
        resolved_metadata[slot] = _invalidated_slot_metadata(metadata, invalidations[slot])
```

Phase 54 copy rule: do not bypass `resolve_slots_with_metadata()`. If adding provenance categories, derive them from this deterministic decision stream or factor it without changing behavior.

**Invalidation / current-turn metadata pattern** (`src/agent/routing.py` lines 180-268):

```python
def detect_slot_invalidations(user_query: str) -> dict[str, dict[str, Any]]:
    ...
    if invalidations:
        return invalidations
    if any(marker in lowered or marker in user_query for marker in _BROAD_INVALIDATION_MARKERS):
        return {slot: _slot_invalidation(slot) for slot in BUSINESS_ID_SLOTS}

def _current_turn_slot_metadata(...):
    metadata = {
        "source": "current_turn",
        "provenance_source": "current_query",
        "explicit_current_turn": True,
    }
    ...
    if slot in invalidations:
        metadata["slot_invalidation"] = invalidations[slot]
        metadata["invalidates_prior_slot"] = True
```

**Route decision pattern** (`src/agent/routing.py` lines 275-326):

```python
if policy.all_of or policy.any_of:
    return "extract_slots"
return route

def _route_after_slots(state: AgentState) -> str:
    intent = _intent(state)
    if not INTENT_POLICY_REGISTRY.is_known_intent(intent):
        return "clarification_gate"
    policy = SLOT_POLICY_REGISTRY.required_slots_for(intent)
    ...
    missing = missing_required_slots(policy, resolve_slots_for_completeness(state))
    if missing:
        return "clarification_gate"
    if _needs_reviewed_memory_context(state):
        return "long_term_memory_retrieve"
    return "investigate"
```

Phase 54 copy rule: active contextual route should return `"slot_resolution_gate"` for slot-required intents. Active slot router should be named `route_after_slot_resolution`, should still allow `long_term_memory_retrieve` only for Phase 55 compatibility reviewed-memory hints, and should fail closed for unknown/malformed/policy mismatch.

---

### `src/agent/intent_policy.py` (policy model / registry, transform)

**Analog:** `SlotPolicyRegistry`, `SlotInheritanceContext`, `slot_intent_compatible`.

**Decision object pattern** (`src/agent/intent_policy.py` lines 31-45):

```python
@dataclass(frozen=True)
class SlotInheritanceContext:
    tenant_id: str | None
    user_id: str | None
    thread_id: str | None
    intent: str | None
    max_age_seconds: int
    current_time: datetime | None = None

@dataclass(frozen=True)
class SlotInheritanceDecision:
    accepted: bool
    reason_code: str
    source: str | None = None
```

**Cross-intent business ID compatibility pattern** (`src/agent/intent_policy.py` lines 250-280):

```python
CROSS_INTENT_SLOT_GROUPS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "order_id": frozenset({...}),
        "refund_case_id": frozenset({...}),
        "ticket_id": frozenset({...}),
    }
)
```

**Required slots and inheritance acceptance pattern** (`src/agent/intent_policy.py` lines 407-454):

```python
def missing_required_slots(...):
    expression = _required_slot_expression(required_slots)
    slots = {key: value for key, value in (resolved_slots or {}).items() if value not in (None, "")}
    ...

def accepts_inherited_slot(...):
    if source != "trusted_session_memory":
        return SlotInheritanceDecision(False, "untrusted_source", source)
    for field, reason_code in (("tenant_id", "tenant_mismatch"), ("user_id", "user_mismatch"), ("thread_id", "thread_mismatch")):
        ...
    if invalidation:
        return SlotInheritanceDecision(False, "slot_invalidated", source)
    if not _slot_metadata_is_fresh(metadata, context):
        return SlotInheritanceDecision(False, "stale_slot", source)
    if _slot_metadata_is_intent_compatible(slot, metadata, context.intent):
        return SlotInheritanceDecision(True, "accepted", source)
    return SlotInheritanceDecision(False, "intent_incompatible", source)
```

**WR-01 invariant pattern** (`src/agent/intent_policy.py` lines 501-509):

```python
def slot_intent_compatible(slot_name: str, compatible_intents: list[str], current_intent: str | None) -> bool:
    if current_intent is None:
        return True
    if current_intent in compatible_intents:
        return True
    intent_group = CROSS_INTENT_SLOT_GROUPS.get(slot_name)
    if intent_group is None:
        return False
    return current_intent in intent_group and any(intent in intent_group for intent in compatible_intents)
```

Phase 54 copy rule: preserve this exact cross-intent behavior. `order_id` / `refund_case_id` / `ticket_id` can intentionally cross compatible business intents; non-business slots like `action_type` cannot be pre-authorized by pre-intent metadata.

---

### `src/agent/state.py` and `src/agent/schemas.py` (state/schema model, transform)

**Analog:** current `AgentState` and strict Pydantic models.

**State field pattern** (`src/agent/state.py` lines 55-90):

```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""
    ...
    classification_trace: dict[str, Any] | None
    ...
    required_slots: dict[str, Any]
    candidate_slots: dict[str, Any]
    routing_hints: dict[str, Any]
    extracted_slots: dict[str, Any] | None
```

**Schema pattern** (`src/agent/schemas.py` lines 39-95):

```python
class RequiredSlotExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all_of: list[str] = Field(default_factory=list)
    any_of: list[list[str]] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)

class SlotExtractionResult(BaseModel):
    order_id: str | None = None
    refund_case_id: str | None = None
    ticket_id: str | None = None
    merchant_id: str | None = None
    customer_id: str | None = None
    issue_type: str | None = None
    action_type: str | None = None
```

Phase 54 copy rule: if provenance becomes a first-class state key, add it to `AgentState` near `classification_trace` / slot fields. If adding a strict schema, follow `ConfigDict(extra="forbid")` like `RequiredSlotExpression`.

---

### Node and Slot Tests

**Files:** `tests/agent/test_nodes/test_slot_resolution_gate.py`, `tests/agent/test_nodes/test_extract_slots.py`, `tests/agent/test_required_slots.py`, `tests/agent/test_nodes/test_contextual_intent_resolve.py`

**Fake LLM pattern** (`tests/agent/test_nodes/test_extract_slots.py` lines 15-30):

```python
class CapturingLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def with_structured_output(self, schema):
        llm = self
        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                llm.messages = messages
                if issubclass(schema, BaseModel):
                    return schema.model_validate(llm.response)
                return llm.response
        return _Wrapper()
```

**Async node test pattern** (`tests/agent/test_nodes/test_extract_slots.py` lines 46-86):

```python
@pytest.mark.asyncio
async def test_extract_slots_prompt_uses_prompt_assembly_and_bounded_candidate_hints(monkeypatch, base_state):
    fake_llm = CapturingLLM({...})
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: fake_llm)

    result = await extract_slots_module.extract_slots({...})

    assert result["extracted_slots"]["order_id"] == "ORD-001"
    assert "extract_slots" in result["llm_outputs"]
    assert "Candidate slot hints" in prompt
```

Phase 54 copy rule: new test file should import `slot_resolution_gate` module and assert `result["trace_steps"][-1]["node"] == "slot_resolution_gate"`, plus `llm_outputs["slot_resolution_gate"]` or selected canonical output owner.

**Slot policy unit cases** (`tests/agent/test_required_slots.py` lines 49-117):

```python
decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot("order_id", metadata, _slot_policy_context())
assert decision.accepted is True
assert decision.reason_code == "accepted"

cases = [
    ({}, "missing_metadata", None),
    ({**base, "source": "raw_memory"}, "untrusted_source", "raw_memory"),
    ({**base, "tenant_id": "wrong-tenant"}, "tenant_mismatch", "trusted_session_memory"),
    ({**base, "expires_at": "not-a-date"}, "stale_slot", "trusted_session_memory"),
    ({**base, "compatible_intents": ["small_talk"]}, "intent_incompatible", "trusted_session_memory"),
]
```

**WR-01 regression cases** (`tests/agent/test_required_slots.py` lines 236-290):

```python
def test_pre_intent_session_context_rejects_incompatible_non_business_slot():
    ...
    assert resolved == {"order_id": "ORD-CURRENT"}
    assert "action_type" not in metadata
    assert route_after_slots(state) == "clarification_gate"

def test_pre_intent_session_context_preserves_cross_intent_business_id_slot():
    ...
    assert resolved == {"action_type": "issue_coupon", "order_id": "ORD-PRE-INTENT"}
    assert metadata["order_id"]["source"] == "trusted_session_memory"
    assert route_after_slots(state) == "investigate"
```

**Invalidation / override cases** (`tests/agent/test_required_slots.py` lines 303-348):

```python
state["user_query"] = "不是这个订单"
resolved, metadata = resolve_slots_with_metadata(state)
assert "order_id" not in resolved
assert metadata["order_id"]["source"] == "invalidated_trusted_session_memory"
assert route_after_slots(state) == "clarification_gate"

state["user_query"] = "不是这个订单，是 ORD-CURRENT"
state["extracted_slots"] = {"order_id": "ORD-CURRENT"}
assert metadata["order_id"]["previous_trusted_session_value"] == "ORD-SESSION"
assert route_after_slots(state) == "investigate"
```

**Candidate-only intent test pattern** (`tests/agent/test_nodes/test_contextual_intent_resolve.py` lines 70-79):

```python
result = await contextual_intent_module.contextual_intent_resolve(base_state)
for forbidden in FORBIDDEN_AUTHORITY_FIELDS:
    assert forbidden not in result
assert result["candidate_slots"] == {"order_id": "ORD-001"}
assert "extracted_slots" not in result["llm_outputs"]["contextual_intent_resolve"]
```

Phase 54 copy rule: keep candidate slots as hints only; new gate tests must prove candidate slots alone do not satisfy required slot policy.

---

### `src/agent/graph.py` (graph config / route, request-response)

**Analog:** current `build_graph()` registration and conditional edges.

**Import pattern** (`src/agent/graph.py` lines 23-46):

```python
from src.agent.nodes.contextual_intent_resolve import contextual_intent_resolve
from src.agent.nodes.extract_slots import extract_slots
...
from src.agent.routing import (
    route_after_contextual_intent,
    ...
    route_after_slots,
)
```

Phase 54 copy rule: import `slot_resolution_gate`; import `route_after_slot_resolution`; retain `extract_slots` / `route_after_slots` only if compatibility tests still need them outside active graph wiring.

**Graph node and path-map pattern** (`src/agent/graph.py` lines 282-328):

```python
builder.add_node("contextual_intent_resolve", contextual_intent_resolve, retry_policy=_llm_retry)
builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
...
builder.add_conditional_edges(
    "contextual_intent_resolve",
    route_after_contextual_intent,
    {
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
        "investigate": "investigate",
        "extract_slots": "extract_slots",
    },
)
builder.add_conditional_edges(
    "extract_slots",
    route_after_slots,
    {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "long_term_memory_retrieve": "long_term_memory_retrieve",
    },
)
```

Phase 54 copy rule: replace active node key/path-map source with `slot_resolution_gate`; replace active router with `route_after_slot_resolution`; path map may keep `long_term_memory_retrieve` destination for Phase 55 compatibility.

---

### Architecture Baseline Tests

**Files:** `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`

**Baseline constants pattern** (`tests/architecture/graph_baseline.py` lines 31-94):

```python
CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset({... "extract_slots", ...})
MIGRATION_MODE_LEGACY_NODE_MAP = {
    "extract_slots": {
        "target": "slot_resolution_gate",
        "delete_phase": "Phase 54",
        "owner_requirement": "CAGM-05",
    },
    ...
}
CURRENT_CONDITIONAL_EDGE_BASELINE = {
    ("contextual_intent_resolve", "route_after_contextual_intent"): {
        ...
        "extract_slots": "extract_slots",
    },
    ("extract_slots", "route_after_slots"): {
        ...
    },
}
```

Phase 54 copy rule: remove active `extract_slots` from baseline and migration map once cutover is done; add active `slot_resolution_gate`; update edge keys and router names atomically.

**AST extraction pattern** (`tests/architecture/graph_baseline.py` lines 153-209):

```python
def graph_add_node_names(path: Path = GRAPH_PATH) -> frozenset[str]:
    tree = ast.parse(_source(path))
    ...
    names.add(_string_literal(node.args[0], context="add_node node name"))

def graph_conditional_edge_mappings(path: Path = GRAPH_PATH) -> dict[tuple[str, str], dict[str, str]]:
    ...
    source = _string_literal(node.args[0], context="add_conditional_edges source")
    router = _name(node.args[1], context="add_conditional_edges router")
    ...
    mappings[(source, router)][_string_literal(key, ...)] = _string_literal(value, ...)
```

**Route coverage test pattern** (`tests/architecture/test_canonical_graph_baseline.py` lines 101-123):

```python
def test_current_router_mappings_match_source_baseline() -> None:
    assert graph_conditional_edge_mappings() == CURRENT_CONDITIONAL_EDGE_BASELINE

def test_router_return_values_are_covered_by_registered_path_maps() -> None:
    route_maps = graph_conditional_edge_mappings()
    router_routes = graph_router_route_values()
    registered_nodes = graph_add_node_names()
    assert set(router_routes) == {router for _source, router in route_maps}
    ...
    assert router_routes[router] <= frozenset(path_map), router
```

**Forbidden node drift pattern** (`tests/architecture/test_canonical_graph_baseline.py` lines 159-168):

```python
def test_slot_extraction_drift_is_explicitly_rejected() -> None:
    assert "slot_extraction" not in graph_add_node_names(), (
        "`slot_extraction` is not a registered main-chain graph node. ..."
    )
```

---

### Graph and Router Tests

**Files:** `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/agent/test_intent_routing.py`

**Central route-key pattern** (`tests/agent/test_graph.py` lines 53-68):

```python
ROUTER_EDGE_KEYS = {
    "route_after_contextual_intent": {"clarification_gate", "final_response", "investigate", "extract_slots"},
    "route_after_slots": {"clarification_gate", "investigate", "long_term_memory_retrieve"},
    ...
}
```

Phase 54 copy rule: update this central map to `route_after_slot_resolution` and `slot_resolution_gate`; retain `route_after_slots` only as explicit compatibility delegate coverage.

**Graph compile and projection pattern** (`tests/agent/test_graph.py` lines 924-964):

```python
def test_graph_compiles_with_investigate():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)
    assert {"contextual_intent_resolve", "investigate", "extract_slots", ...} <= nodes
    assert "classify_intent" not in nodes

def test_legacy_graph_runtime_names_project_to_target_vocabulary():
    legacy_node_targets = {"extract_slots": "slot_resolution_gate", ...}
    for legacy_node, target_node in legacy_node_targets.items():
        assert legacy_node in nodes
        assert target_graph_name(legacy_node, kind="node") == target_node
```

Phase 54 copy rule: after cutover, `slot_resolution_gate` should be in compiled graph and `extract_slots` should not. Legacy projection test should move `extract_slots` out of active-runtime assertion and into historical compatibility assertions.

**Router totality pattern** (`tests/agent/test_graph.py` lines 1013-1042):

```python
assert route_after_contextual_intent({...}) in ROUTER_EDGE_KEYS["route_after_contextual_intent"]
assert route_after_slots({...}) in ROUTER_EDGE_KEYS["route_after_slots"]
assert ROUTER_EDGE_KEYS["route_after_slots"] == {"clarification_gate", "investigate", "long_term_memory_retrieve"}
assert target_graph_name("route_after_slots", kind="router") == "route_after_slot_resolution"
```

**Contextual route test pattern** (`tests/test_graph_routing.py` lines 325-393):

```python
@pytest.mark.parametrize(("state", "expected"), [..., ("extract_slots"), ...])
def test_route_after_contextual_intent_totality_and_phase54_slot_destination(state, expected):
    route = route_after_contextual_intent(state)
    assert route in {"clarification_gate", "final_response", "investigate", "extract_slots"}
    assert route == expected

def test_route_after_contextual_intent_fails_closed_for_exceptions_or_unregistered_route(monkeypatch):
    monkeypatch.setattr(routing_module, "_route_after_contextual_intent", lambda _state: "session_memory_load")
    assert route_after_contextual_intent({}) == "clarification_gate"
```

Phase 54 copy rule: expected destination becomes `slot_resolution_gate`; keep fail-closed monkeypatch test.

**Reviewed-memory compatibility pattern** (`tests/agent/test_intent_routing.py` lines 558-594):

```python
assert route_after_slots({}) in SLOT_ROUTES
assert route_after_slots({
    "primary_intent": "policy_qa",
    "required_slots": {"all_of": [], "any_of": [], "optional": []},
    "routing_hints": {"needs_long_term_memory": True},
}) == "long_term_memory_retrieve"

assert route_after_slots({
    "primary_intent": "refund_troubleshooting",
    "extracted_slots": {},
    "routing_hints": {"needs_reviewed_memory_context": True},
}) == "clarification_gate"
```

Phase 54 copy rule: apply same assertions to `route_after_slot_resolution`; add one test that `route_after_slots(state) == route_after_slot_resolution(state)` if delegate is retained.

**Graph memory hint E2E pattern** (`tests/agent/test_graph.py` lines 1156-1177):

```python
payload["routing_hints"] = {"needs_reviewed_memory_context": True}
monkeypatch.setattr(contextual_intent_module, "_get_llm", lambda: FakeLLM(payload))
monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots("ORD-001")))
...
final_state = await graph.ainvoke(_state("订单ORD-001退款为什么没到账？"), _config(...))
assert final_state["llm_outputs"]["long_term_memory_retrieve"]["source"] == "no_reviewed_memory"
```

Phase 54 copy rule: monkeypatch `slot_resolution_gate` module after active cutover. This test preserves D-05/D-14 compatibility destination.

---

### Vocabulary, Trace, and API Projection

**Files:** `src/agent/graph_vocabulary.py`, `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `src/api/routers/agent_runs.py`, `tests/test_agent_runs_api.py`

**Vocabulary entry pattern** (`src/agent/graph_vocabulary.py` lines 13-20 and 87-136):

```python
@dataclass(frozen=True)
class GraphVocabularyEntry:
    legacy_name: str
    target_name: str
    kind: TargetGraphKind
    status: TargetGraphStatus
    runnable: bool
    reason_codes: tuple[str, ...] = ()

_entry("extract_slots", "slot_resolution_gate", "node", "compatibility_alias", True, (...))
_entry("slot_resolution_gate", "slot_resolution_gate", "node", "compatibility_alias", True, (...))
_entry("route_after_slots", "route_after_slot_resolution", "router", "compatibility_alias", True)
_entry("route_after_slot_resolution", "route_after_slot_resolution", "router", "compatibility_alias", True)
```

Phase 54 copy rule: make `slot_resolution_gate` and `route_after_slot_resolution` `runtime`; keep `extract_slots` and `route_after_slots` as `compatibility_alias` only if retained, with delete-by-Phase-58 reason codes.

**Projection helper pattern** (`src/agent/graph_vocabulary.py` lines 164-174):

```python
def project_trace_step_for_contract(step: Mapping[str, Any]) -> dict[str, Any]:
    implementation_node = str(step.get("node") or "unknown")
    entry = graph_vocabulary_entry(implementation_node, kind="node") or graph_vocabulary_entry(
        implementation_node, kind="router"
    )
    projected = dict(step)
    projected["implementation_node"] = implementation_node
    projected["target_node"] = implementation_node if entry is None else entry.target_name
    projected["target_graph_status"] = "unknown_passthrough" if entry is None else entry.status
    projected["target_graph_runnable"] = True if entry is None else entry.runnable
    return projected
```

**Vocabulary test pattern** (`tests/agent/test_graph_vocabulary.py` lines 13-45 and 178-195):

```python
@pytest.mark.parametrize(("name", "kind", "target_name", "status", "runnable"), [...])
def test_legacy_graph_names_project_to_target_vocabulary(...):
    entry = graph_vocabulary_entry(name, kind=kind)
    assert entry.target_name == target_name
    assert entry.status == status

def test_project_trace_step_preserves_original_fields_and_adds_contract_projection():
    original = {"node": "extract_slots", "status": "completed", "metrics_json": {"slot_resolution_gate": True}}
    projected = project_trace_step_for_contract(original)
    assert projected["node"] == "extract_slots"
    assert projected["target_node"] == "slot_resolution_gate"
```

**Trace summary pattern** (`src/agent/trace.py` lines 252-265; `tests/agent/test_trace.py` lines 109-163):

```python
projected_steps = [
    project_trace_step_for_contract(step if isinstance(step, dict) else {"node": "unknown"})
    for step in trace_steps
]
graph_projection_steps = [
    {
        "implementation_node": str(step["implementation_node"]),
        "target_node": str(step["target_node"]),
        "target_graph_status": str(step["target_graph_status"]),
        "target_graph_runnable": bool(step["target_graph_runnable"]),
    }
    for step in projected_steps
]
```

Test analog asserts legacy node names remain in `nodes_executed` while `target_nodes_executed` contains canonical target names.

**API/SSE label and projection pattern** (`src/api/routers/agent_runs.py` lines 56-68 and 1136-1150):

```python
NODE_MESSAGES: dict[str, str] = {
    "receive_request": "正在接收请求",
    "session_context_load": "正在加载会话上下文",
    "contextual_intent_resolve": "正在识别上下文意图",
    "classify_intent": "正在识别意图",
    "extract_slots": "正在提取关键信息",
    ...
}

def _sse_event(..., node_name: str | None = None) -> dict[str, str]:
    ...
    if node_name:
        data["target_node_name"] = target_graph_name(node_name, kind="node")
    return {"data": json.dumps(data, ensure_ascii=False)}
```

Phase 54 copy rule: add `slot_resolution_gate` message. Keep `extract_slots` label for historical display only if compatibility alias remains.

**SSE test pattern** (`tests/test_agent_runs_api.py` lines 971-986):

```python
event = _sse_event(
    event_type="step_completed",
    run_id="run-graph-projection",
    step_index=2,
    node_name="extract_slots",
    status="completed",
    message="done",
    payload={"tool_name": "slot_parser"},
)
data = json.loads(event["data"])
assert data["node_name"] == "extract_slots"
assert data["target_node_name"] == "slot_resolution_gate"
```

Phase 54 copy rule: add canonical SSE assertion for `node_name="slot_resolution_gate"` with `target_node_name == "slot_resolution_gate"` and runtime vocabulary status; preserve legacy assertion for historical rows.

**Trace API timeline projection pattern** (`tests/test_trace_api.py` lines 317-339):

```python
timeline = repo.build_timeline(
    steps=[SimpleNamespace(node_name="route_after_slots", status="completed", ...)],
    approvals=[],
    approval_steps=[],
    drafts=[],
)
assert timeline[0]["detail"]["node_name"] == "route_after_slots"
assert timeline[0]["detail"]["target_node"] == "route_after_slot_resolution"
```

Phase 54 copy rule: add canonical router row projection; keep legacy row projection without rewriting historical `node_name`.

---

### Documentation and Ledger

**Files:** `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`

**Current-source docs pattern** (`docs/current-langgraph-architecture.md` lines 1-5 and 70-101):

```markdown
# 当前 LangGraph Graph/Node 架构图

> 本图只根据当前仓库源码绘制，主要依据 `src/agent/graph.py` 的 `build_graph()` 节点/边定义，以及 `src/agent/routing.py` 和 `src/agent/graph.py` 中的条件路由函数。未把 planning 文档、README 描述或测试断言当作已实现事实。
```

The file then lists current registered nodes, LLM retry nodes, route behavior, and a compatibility ledger table with columns:

```markdown
| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
```

Phase 54 copy rule: update graph diagram and summary so active path is `contextual_intent_resolve -> slot_resolution_gate -> route_after_slot_resolution`; mark active `extract_slots` row closed in Phase 54 and retain only wrapper/import/test/historical trace surfaces if still present.

**Architecture debt write-rule pattern** (`.planning/ARCHITECTURE-DEBT.md` lines 1-11):

```markdown
# MOCA 架构债务 / 缺陷发现台账

> 本文件记录 MOCA 各子系统在代码走查、phase 实现、本地验证中**检测出的 bug、设计缺陷、遗留妥协**，以及**已完成的修复**。

## 写入规则

- 修改**工具调用 / RAG / 记忆 / 意图识别**这几个核心子系统时，检测出的 bug 或架构不完善点、以及做了哪些修复，**默认追加到本文件**对应子系统章节。
```

**Phase closeout ledger pattern** (`.planning/ARCHITECTURE-DEBT.md` lines 949-980):

```markdown
## Phase 53 Plan 02 — active graph 切到 session_context_load -> contextual_intent_resolve ✅已修复验证

**问题 / 根因**
- Phase 53-01 已新增 canonical `contextual_intent_resolve` 与非 active `route_after_contextual_intent`，但 active graph / router / policy route values 尚未同步切换；如果只改其中一层会产生 route-map drift。

**修复**
- `route_after_contextual_intent` 成为 active graph router；保留的 `route_after_intent` 仅直接委托给 contextual router，不再有独立 allowlist / 行为分叉。
```

**WR-01 invariant ledger pattern** (`.planning/ARCHITECTURE-DEBT.md` lines 1052-1076):

```markdown
## Phase 53 code review fix WR-01 — pre-intent session slot 兼容性改为 post-intent 复核 ✅已修复验证

**问题 / 根因**
- ... 旧 metadata 仍写 `intent_compatible=True`。

**修复**
- `SlotPolicyRegistry` 在存在真实 intent 和 `compatible_intents` 时重新计算兼容性，不再先信任 pre-intent 布尔值；同时保留 `order_id` / `refund_case_id` / `ticket_id` 的有意跨意图兼容。
```

Phase 54 copy rule: add a Phase 54 entry under cross-subsystem / intent recognition documenting `extract_slots` active compatibility closure, retained compatibility surfaces, validation evidence, and remaining Phase 55/58 risks.

## Shared Patterns

### Fail-Closed Routing

**Source:** `src/agent/routing.py` lines 77-98 and 309-326  
**Apply to:** `route_after_slot_resolution`, `route_after_contextual_intent`, router tests, graph baseline.

Rules:
- Wrapper catches exceptions and returns `clarification_gate`.
- Wrapper allowlists return values.
- Required-slot policy mismatch, unknown intent, malformed required slots, missing required slots, stale/incompatible/invalidated inherited slots all route to `clarification_gate`.
- `long_term_memory_retrieve` remains allowed only for reviewed/long-term memory hints until Phase 55.

### Deterministic Slot Authority

**Source:** `src/agent/routing.py` lines 113-164; `src/agent/intent_policy.py` lines 423-454  
**Apply to:** `slot_resolution_gate.py`, `routing.py`, `test_slot_resolution_gate.py`, `test_required_slots.py`.

Rules:
- LLM output proposes candidates/extracted slots only.
- Deterministic resolver decides `active_slots`.
- Session slots require trusted source, tenant/user/thread match, freshness, no invalidation, and actual-intent compatibility.
- Current-turn explicit slot overrides accepted inherited slot and records prior trusted value when relevant.

### Canonical Trace Boundary

**Source:** `src/agent/nodes/contextual_intent_resolve.py` lines 407-444; `src/agent/graph_vocabulary.py` lines 164-174  
**Apply to:** `slot_resolution_gate.py`, graph vocabulary, trace/API tests.

Rules:
- Active runtime trace for Phase 54 should use `slot_resolution_gate`.
- Historical `extract_slots` trace rows are not rewritten; projection adds `implementation_node`, `target_node`, `target_graph_status`, `target_graph_runnable`.
- New provenance payload should be additive and should not remove legacy consumer fields.

### AST-Based Graph Guardrail

**Source:** `tests/architecture/graph_baseline.py` lines 153-209; `tests/architecture/test_canonical_graph_baseline.py` lines 101-123  
**Apply to:** `graph.py`, `routing.py`, architecture tests.

Rules:
- Update active registered node baseline and conditional edge map together.
- Router return sets must be covered by path-map keys.
- Path-map values must be registered nodes.
- `slot_extraction` remains forbidden as a registered main-chain node.

### Validation Commands

Use only project entrypoints:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_slot_resolution_gate.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name -q
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture tests/test_graph_routing.py tests/test_trace_api.py
```

## No Analog Found

| File / Contract | Role | Data Flow | Reason | Planner Guidance |
|---|---|---|---|---|
| Exact `slot_resolution_trace` / provenance schema name | model / trace contract | transform | No existing dedicated slot-resolution provenance schema exists. | Use `classification_trace` structure from `contextual_intent_resolve.py` plus `active_slot_metadata` from `routing.py`; add explicit tests for each D-09 category. |

## Metadata

**Analog search scope:** `src/agent`, `src/api/routers`, `tests/agent`, `tests/architecture`, `tests/test_graph_routing.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`  
**Files scanned:** 30+ targeted source/test/doc files via `rg`, line-count checks, and non-overlapping snippet reads  
**Pattern extraction date:** 2026-07-07  
**Project constraints applied:** Chinese prose; no source edits; test commands use `UV_CACHE_DIR=/tmp/uv-cache uv run ...`; `extract_slots` active runtime closure must be recorded in docs/ledger after implementation.
