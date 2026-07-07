# Phase 55: memory-context-load-cutover - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 35 new/modified candidates
**Analogs found:** 35 / 35

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/nodes/memory_context_load.py` | graph node wrapper | request-response + transform | `src/agent/nodes/long_term_memory_retrieve.py`; `src/agent/nodes/reviewed_memory_context_retrieve.py` | exact composite |
| `src/agent/nodes/long_term_memory_retrieve.py` | compatibility node wrapper | request-response + transform | same file | exact |
| `src/agent/nodes/reviewed_memory_context_retrieve.py` | graph node/service orchestrator | request-response + CRUD read | same file | exact |
| `src/memory/context_refs.py` | model/DTO | transform | same file | exact |
| `src/memory/context_service.py` | service | CRUD read + request-response | same file | exact |
| `src/agent/state.py` | model/state contract | transform | same file | exact |
| `src/agent/graph.py` | graph config | event-driven + request-response | same file | exact |
| `src/agent/routing.py` | route utility | deterministic request-response | same file | exact |
| `src/agent/graph_vocabulary.py` | utility/config | trace/API projection transform | same file | exact |
| `src/api/routers/agent_runs.py` | controller/API streaming | SSE streaming + projection | Phase 54 `slot_resolution_gate` SSE projection in same file | exact |
| `src/agent/trace.py` | utility | event-driven trace transform | same file | exact |
| `src/api/routers/traces.py` | controller/API | request-response + projection | same file | exact |
| `tests/agent/test_memory_context_load.py` | test | async node request-response | `tests/agent/test_reviewed_memory_context_retrieve.py`; `tests/agent/test_graph.py` | role-match composite |
| `tests/agent/test_reviewed_memory_context_retrieve.py` | test | async node request-response | same file | exact |
| `tests/agent/test_graph.py` | test | graph smoke + event-driven | same file | exact |
| `tests/agent/test_intent_routing.py` | test | deterministic request-response | same file | exact |
| `tests/test_graph_routing.py` | test | deterministic request-response | same file | exact |
| `tests/agent/test_graph_vocabulary.py` | test | projection transform | same file | exact |
| `tests/architecture/graph_baseline.py` | test helper | static AST transform | same file | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | architecture test | static AST transform | same file | exact |
| `tests/architecture/test_phase32_static_contract.py` | architecture test | static projection contract | `tests/agent/test_graph_vocabulary.py` | role-match |
| `tests/architecture/test_memory_contract_delta.py` | architecture test | static contract/projection | `tests/agent/test_graph_vocabulary.py`; `src/agent/graph_vocabulary.py` | role-match |
| `tests/memory/test_phase48_1_memory_compat_alignment.py` | compatibility test | file I/O + static guard | same file | exact |
| `tests/agent/test_memory_evidence_boundary.py` | boundary test | authority transform | same file | exact |
| `tests/memory/test_reviewed_memory_context_boundary.py` | integration test | CRUD read + access boundary | same file | exact |
| `tests/memory/test_context_refs.py` | model test | DTO validation transform | same file | exact |
| `tests/memory/test_phase46_session_context_alignment.py` | compatibility test | file I/O + static guard | `tests/memory/test_phase48_1_memory_compat_alignment.py`; `tests/memory/test_context_refs.py` | role-match |
| `tests/memory/test_phase47_case_precedent_alignment.py` | compatibility test | file I/O + static guard | `tests/memory/test_phase48_1_memory_compat_alignment.py`; `tests/agent/test_reviewed_memory_context_retrieve.py` | role-match |
| `tests/memory/test_phase48_long_term_preference_alignment.py` | compatibility test | file I/O + static guard | `tests/memory/test_phase48_1_memory_compat_alignment.py`; `tests/memory/test_reviewed_memory_context_boundary.py` | role-match |
| `tests/agent/test_trace.py` | test | trace projection transform | same file | exact |
| `tests/test_trace_api.py` | API test | request-response projection | same file | exact |
| `tests/test_agent_runs_api.py` | API test | SSE streaming projection | same file | exact |
| `docs/current-langgraph-architecture.md` | documentation | source snapshot transform | same file | exact |
| `.planning/ARCHITECTURE-DEBT.md` | architecture ledger | event log/documentation | Phase 54 architecture-debt row in same file | exact |
| `docs/contract-spec.md` | contract documentation | semantic contract transform | existing §9/§13 memory graph contract | role-match |

## Pattern Assignments

### `src/agent/nodes/memory_context_load.py` (graph node wrapper, request-response + transform)

**Analogs:** `src/agent/nodes/long_term_memory_retrieve.py`, `src/agent/nodes/reviewed_memory_context_retrieve.py`

**Imports pattern** (`long_term_memory_retrieve.py` lines 1-12):
```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.reviewed_memory_context_retrieve import reviewed_memory_context_retrieve
from src.agent.state import AgentState
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository
```

**Delegating wrapper pattern** (`long_term_memory_retrieve.py` lines 15-31):
```python
async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the reviewed memory context boundary."""
    result = await reviewed_memory_context_retrieve(
        state,
        config,
        long_term_memory_repository_cls=LongTermMemoryRepository,
        case_memory_repository_cls=CaseMemoryRepository,
        long_term_memory_service_cls=LongTermMemoryService,
        case_memory_service_cls=CaseMemoryService,
    )
    legacy_metrics = _legacy_metrics(result)
    result["llm_outputs"] = {
        **(state.get("llm_outputs") or {}),
        **(result.get("llm_outputs") or {}),
        "long_term_memory_retrieve": legacy_metrics,
    }
    return result
```

**Canonical output assembly pattern** (`reviewed_memory_context_retrieve.py` lines 260-273):
```python
return {
    "memory_context": memory_context,
    "memory_context_bundle": memory_context_bundle,
    "case_working_context": case_working_context,
    "case_working_context_lifecycle_status": case_working_context_status,
    "reviewed_memory_context_retrieve_status": status_ref,
    "long_term_memory": long_term_items,
    "case_memory": case_items,
    "llm_outputs": {
        **(state.get("llm_outputs") or {}),
        "reviewed_memory_context_retrieve": metrics,
    },
    "trace_steps": (state.get("trace_steps") or []) + [step],
}
```

**Metrics/source-label pattern to extend** (`reviewed_memory_context_retrieve.py` lines 318-340):
```python
def _metrics(memory_context: Mapping[str, Any]) -> dict[str, Any]:
    long_term_items = memory_context.get("long_term_items") if isinstance(memory_context.get("long_term_items"), list) else []
    case_items = memory_context.get("case_items") if isinstance(memory_context.get("case_items"), list) else []
    status_ref = memory_context.get("status_ref") if isinstance(memory_context.get("status_ref"), Mapping) else {}
    fallback_reason = status_ref.get("fallback_reason")
    filter_reasons = status_ref.get("filter_reasons") if isinstance(status_ref.get("filter_reasons"), list) else []
    return {
        "source": _source(long_term_items=long_term_items, case_items=case_items, fallback_reason=fallback_reason),
        "fallback_reason": fallback_reason,
        "long_term_count": len(long_term_items),
        "case_count": len(case_items),
        "filter_reasons": filter_reasons,
    }
```

**Planner guidance:** create `memory_context_load(...)` as the active owner and delegate to `reviewed_memory_context_retrieve(...)`. Write active metrics under `llm_outputs["memory_context_load"]`; only dual-write `llm_outputs["long_term_memory_retrieve"]` if a test/API reader proves compatibility need, and document it as Phase 58 cleanup.

---

### `src/agent/nodes/long_term_memory_retrieve.py` (compatibility wrapper)

**Analog:** same file

**Compatibility-only retained metric pattern** (lines 34-64):
```python
def _legacy_metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    long_term_memory = result.get("long_term_memory") if isinstance(result.get("long_term_memory"), list) else []
    case_memory = result.get("case_memory") if isinstance(result.get("case_memory"), list) else []
    status_ref = (
        result.get("reviewed_memory_context_retrieve_status")
        if isinstance(result.get("reviewed_memory_context_retrieve_status"), Mapping)
        else {}
    )
    fallback_reason = status_ref.get("fallback_reason")
    source = _legacy_source(
        long_term_memory=long_term_memory,
        case_memory=case_memory,
        fallback_reason=fallback_reason,
    )
    retrieved = len(long_term_memory) + len(case_memory)
    return {
        "source": source,
        "continuity_claimed": retrieved > 0,
        "retrieved": retrieved,
        "profile_count": len(long_term_memory),
        "case_count": len(case_memory),
        "fallback_reason": fallback_reason,
    }
```

**Planner guidance:** after graph cutover, this file must not be imported by `src/agent/graph.py` for active registration. Keep it only as import/test compatibility if needed.

---

### `src/agent/nodes/reviewed_memory_context_retrieve.py` (node/service orchestrator)

**Analog:** same file

**Fail-closed service error pattern** (lines 54-81):
```python
try:
    context_service = _context_service(
        configurable,
        memory_context_service_cls=memory_context_service_cls or MemoryContextService,
        long_term_memory_repository_cls=long_term_memory_repository_cls or LongTermMemoryRepository,
        case_memory_repository_cls=case_memory_repository_cls or CaseMemoryRepository,
        long_term_memory_service_cls=long_term_memory_service_cls or LongTermMemoryService,
        case_memory_service_cls=case_memory_service_cls or CaseMemoryService,
    )
    bundle = await context_service.load_reviewed_memory_context(
        trusted_context=configurable.get("trusted_context"),
        current_slots=_current_turn_slots(state),
        trusted_business_context=_trusted_business_context(state, configurable),
        requested_scopes=_requested_scopes(state, configurable),
        query=_case_memory_query(state),
        case_type=_case_type(state),
        limit=5,
    )
except Exception:
    bundle = _empty_bundle(
        fallback_reason="service_error",
        status="unavailable",
        trusted_context=configurable.get("trusted_context"),
        current_slots=_current_turn_slots(state),
    )
    node_errors = (state.get("node_errors") or []) + [
        {"node": "reviewed_memory_context_retrieve", "error_code": _SERVICE_ERROR_CODE}
    ]
```

**CWC error isolation pattern** (lines 131-156):
```python
try:
    return (
        await adapter.link_and_load_active(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            state=state,
        ),
        False,
    )
except Exception:
    return (
        CaseWorkingContextLifecycleResult(
            case_id=None,
            case_working_context=None,
            status_ref=error_status(
                reason_code="load_failed",
                read_status="error",
                tenant_id=tenant_id,
                run_id=run_id,
            ),
        ),
        True,
    )
```

**Scope hint compatibility pattern** (lines 394-399):
```python
def _uses_reviewed_memory_actor_merchant_scope_hint(state: AgentState) -> bool:
    routing_hints = state.get("routing_hints")
    return isinstance(routing_hints, Mapping) and (
        routing_hints.get("needs_reviewed_memory_context") is True
        or routing_hints.get("needs_long_term_memory") is True
    )
```

**Planner guidance:** if the canonical wrapper updates node names in trace steps or node errors, preserve fail-closed semantics and avoid broad replacement of service logic.

---

### `src/memory/context_refs.py` (DTO models)

**Analog:** same file

**Contextual-only status/ref pattern** (lines 73-85):
```python
class ReviewedMemoryContextRetrieveStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reviewed_memory_context_retrieve_status.v1"] = (
        "reviewed_memory_context_retrieve_status.v1"
    )
    status: str
    authority_class: Literal["contextual_only"] = "contextual_only"
    trusted_scope_inputs: dict[str, Any] = Field(default_factory=dict)
    effective_scopes: list[dict[str, Any]] = Field(default_factory=list)
    filter_reasons: list[str] = Field(default_factory=list)
    retrieved_refs: list[ReviewedMemoryRef] = Field(default_factory=list)
    fallback_reason: str | None = None
```

**Unified memory bundle pattern** (lines 150-161):
```python
class MemoryContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["memory_context_bundle.v1"] = "memory_context_bundle.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    session_context: SessionContextMemory
    long_term_items: list[dict[str, Any]] = Field(default_factory=list)
    case_items: list[dict[str, Any]] = Field(default_factory=list)
    session_status_ref: SessionContextLoadStatusV1 | None = None
    reviewed_status_ref: ReviewedMemoryContextRetrieveStatusV1 | None = None
    case_working_context: dict[str, Any] | None = None
    case_working_context_status_ref: CaseWorkingContextLifecycleStatusV1 | None = None
```

**Planner guidance:** if adding finite usage/source labels, prefer a constrained field in existing DTO/metrics surfaces. Do not change `authority_class` away from `Literal["contextual_only"]`.

---

### `src/memory/context_service.py` (memory context service)

**Analog:** same file

**Fail-closed reviewed-memory loader pattern** (lines 123-246):
```python
async def load_reviewed_memory_context(
    self,
    *,
    trusted_context: Any | None = None,
    current_slots: Mapping[str, Any] | None = None,
    trusted_business_context: Mapping[str, Any] | None = None,
    requested_scopes: list[dict[str, Any]] | None = None,
    query: str | None = None,
    case_type: str | None = None,
    now: datetime | None = None,
    limit: int = 5,
    **_: Any,
) -> ReviewedMemoryContextBundle:
    trusted = _parse_trusted_context(trusted_context)
    if trusted is None:
        return _empty_reviewed_memory_context(
            trusted_context=trusted_context,
            current_slots=current_slots,
            trusted_business_context=trusted_business_context,
            requested_scopes=requested_scopes,
            fallback_reason="missing_trusted_context",
            filter_reasons=["missing_trusted_context"],
        )
```

**Scope-denial pattern** (lines 431-497):
```python
def _reviewed_memory_scopes(
    trusted: TrustedContext,
    *,
    current_slots: Mapping[str, Any] | None,
    trusted_business_context: Mapping[str, Any] | None,
) -> _ReviewedMemoryScopeDecision:
    filter_reasons: list[str] = []
    effective_scopes = _identity_effective_scopes(trusted)
    retrieval_scopes: list[tuple[str, str]] = []
    explicit_merchant_id = _first_string(current_slots, ("merchant_id",))
    business_merchant_id = _trusted_business_merchant_id(trusted_business_context)
    denied_merchant_id = _first_denied_merchant(
        trusted.merchant_scope,
        [explicit_merchant_id, business_merchant_id],
    )
    if denied_merchant_id is not None:
        filter_reasons.append(f"merchant_scope_denied:{denied_merchant_id}")
        return _ReviewedMemoryScopeDecision(
            retrieval_scopes=[],
            effective_scopes=effective_scopes,
            filter_reasons=filter_reasons,
            fallback_reason="merchant_scope_denied",
        )
```

**Empty contextual bundle pattern** (lines 580-604):
```python
def _empty_reviewed_memory_context(
    *,
    trusted_context: Any | None,
    current_slots: Mapping[str, Any] | None,
    trusted_business_context: Mapping[str, Any] | None,
    requested_scopes: list[dict[str, Any]] | None,
    fallback_reason: str,
    filter_reasons: list[str],
    effective_scopes: list[dict[str, Any]] | None = None,
    status: str = "skipped",
) -> ReviewedMemoryContextBundle:
    status_ref = ReviewedMemoryContextRetrieveStatusV1(
        status=status,
        trusted_scope_inputs=_trusted_scope_inputs(
            trusted_context=trusted_context,
            current_slots=current_slots,
            trusted_business_context=trusted_business_context,
            requested_scopes=requested_scopes,
        ),
        effective_scopes=effective_scopes or [],
        filter_reasons=list(dict.fromkeys(filter_reasons)),
        retrieved_refs=[],
        fallback_reason=fallback_reason,
    )
    return ReviewedMemoryContextBundle(long_term_items=[], case_items=[], status_ref=status_ref)
```

**Planner guidance:** Phase 55 should not rewrite this service unless the canonical node needs additional finite labels. Existing scope, denial, skipped, and unavailable behavior is the pattern to preserve.

---

### `src/agent/state.py` (state contract)

**Analog:** same file

**Memory run-state fields pattern** (lines 120-134):
```python
session_context: dict[str, Any] | None
session_context_bundle: dict[str, Any] | None
session_context_load_status: dict[str, Any] | None
session_memory: dict[str, Any] | None
session_memory_bundle: dict[str, Any] | None
memory_context: dict[str, Any] | None
memory_context_bundle: dict[str, Any] | None
reviewed_memory_context_retrieve_status: dict[str, Any] | None
case_working_context: dict[str, Any] | None
case_working_context_lifecycle_status: dict[str, Any] | None
memory_write_candidates: list[dict[str, Any]] | None
memory_write_result: dict[str, Any] | None
memory_write_decision: dict[str, Any] | None
long_term_memory: list[dict[str, Any]] | None
```

**Planner guidance:** avoid state churn unless implementation introduces a canonical status key. Existing fields already cover `memory_context`, unified bundle, reviewed status, CWC, and legacy long-term/case outputs.

---

### `src/agent/graph.py` (active graph registration)

**Analog:** same file

**Node import/registration pattern** (lines 23-46 and 278-296):
```python
from src.agent.nodes.investigate import investigate
from src.agent.nodes.long_term_memory_retrieve import long_term_memory_retrieve
from src.agent.nodes.rag_context_build import rag_context_build
...
builder.add_node("slot_resolution_gate", slot_resolution_gate, retry_policy=_llm_retry)
builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)
builder.add_node("investigate", investigate)
```

**Conditional edge map pattern to cut over** (lines 320-329):
```python
builder.add_conditional_edges(
    "slot_resolution_gate",
    route_after_slot_resolution,
    {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "long_term_memory_retrieve": "long_term_memory_retrieve",
    },
)
builder.add_edge("long_term_memory_retrieve", "investigate")
```

**Planner guidance:** change import, `add_node`, route map key/destination, and direct edge together. After Phase 55, no active `builder.add_node("long_term_memory_retrieve", ...)` or `builder.add_edge("long_term_memory_retrieve", ...)` should remain.

---

### `src/agent/routing.py` (route utility)

**Analog:** same file

**Allowed route set + fail-closed wrapper pattern** (lines 37-41 and 95-104):
```python
SAFETY_ROUTES = {"session_context_load", "clarification_gate", "final_response"}
CONTEXTUAL_INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "slot_resolution_gate"}
INTENT_ROUTES = CONTEXTUAL_INTENT_ROUTES
SLOT_RESOLUTION_ROUTES = {"clarification_gate", "investigate", "long_term_memory_retrieve"}
SLOT_ROUTES = SLOT_RESOLUTION_ROUTES

def route_after_slot_resolution(state: AgentState) -> str:
    try:
        route = _route_after_slot_resolution(state)
    except Exception:
        return "clarification_gate"
    return route if route in SLOT_RESOLUTION_ROUTES else "clarification_gate"
```

**Reviewed-memory route decision pattern** (lines 478-506):
```python
def _slot_resolution_route_decision(
    state: AgentState,
    resolved_slots: dict[str, Any],
) -> tuple[list[dict[str, list[str]]], str, list[str]]:
    intent = _intent(state)
    if not INTENT_POLICY_REGISTRY.is_known_intent(intent):
        return [], "clarification_gate", ["unknown_intent"]
    ...
    if missing:
        return missing, "clarification_gate", ["missing_required_slots"]
    if _needs_reviewed_memory_context(state):
        return [], "long_term_memory_retrieve", []
    return [], "investigate", []
```

**Planner guidance:** return `memory_context_load` for both `needs_reviewed_memory_context` and retained `needs_long_term_memory` hints once slots are resolved. Keep unknown, malformed, missing-slot, and exception paths fail-closed to `clarification_gate`.

---

### `src/agent/graph_vocabulary.py` (runtime/alias projection)

**Analog:** same file

**Entry model pattern** (lines 13-38):
```python
@dataclass(frozen=True)
class GraphVocabularyEntry:
    legacy_name: str
    target_name: str
    kind: TargetGraphKind
    status: TargetGraphStatus
    runnable: bool
    reason_codes: tuple[str, ...] = ()
```

**Existing alias reason-code pattern** (lines 41-46):
```python
_PHASE54_SLOT_ALIAS_REASON_CODES = (
    "PHASE_54_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
)
```

**Current memory entries to change** (lines 91-93):
```python
_entry("long_term_memory_retrieve", "memory_context_load", "node", "compatibility_alias", True),
_entry("reviewed_memory_context_retrieve", "memory_context_load", "node", "runtime", True),
_entry("memory_context_load", "memory_context_load", "node", "compatibility_alias", True),
```

**Projection pattern** (lines 176-186):
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

**Planner guidance:** add Phase 55 reason codes, make `memory_context_load` the `runtime` node entry, demote retained `long_term_memory_retrieve` to compatibility alias with delete phase, and avoid making `reviewed_memory_context_retrieve` a second runtime owner.

---

### `tests/agent/test_memory_context_load.py` (new node tests)

**Analogs:** `tests/agent/test_reviewed_memory_context_retrieve.py`, `tests/agent/test_graph.py`

**Async node import/helper pattern** (`test_reviewed_memory_context_retrieve.py` lines 53-76):
```python
def _reviewed_memory_context_retrieve() -> Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]:
    from src.agent.nodes.reviewed_memory_context_retrieve import reviewed_memory_context_retrieve

    return reviewed_memory_context_retrieve


def _assert_empty_context_bundle(result: dict[str, Any], *, fallback_reason: str) -> dict[str, Any]:
    memory_context = result["memory_context"]
    assert set(memory_context) == {
        "schema_version",
        "authority_class",
        "long_term_items",
        "case_items",
        "status_ref",
    }
    assert memory_context["schema_version"] == "reviewed_memory_context_bundle.v1"
    assert memory_context["authority_class"] == "contextual_only"
```

**Fail-closed tests to mirror** (`test_reviewed_memory_context_retrieve.py` lines 127-177):
```python
async def test_reviewed_memory_context_retrieve_fails_closed_without_trusted_context() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()

    result = await reviewed_memory_context_retrieve(_state(), {"configurable": {"session": object()}})

    _assert_empty_context_bundle(result, fallback_reason="missing_trusted_context")


async def test_reviewed_memory_context_retrieve_denies_out_of_scope_merchant() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])
    ...
    memory_context = _assert_empty_context_bundle(result, fallback_reason="merchant_scope_denied")
    assert "merchant_scope_denied:merchant-b" in memory_context["status_ref"]["filter_reasons"]
```

**Canonical + legacy hint test pattern** (`test_reviewed_memory_context_retrieve.py` lines 237-292):
```python
async def test_reviewed_memory_context_retrieve_uses_actor_scope_for_canonical_reviewed_memory_hint() -> None:
    ...
    await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            routing_hints={"needs_reviewed_memory_context": True},
        ),
        {"configurable": {"trusted_context": trusted_context, "memory_context_service": service}},
    )

    assert service.calls[0]["trusted_business_context"] == {
        "merchant_id": "merchant-c",
        "source": "trusted_context_actor_scope",
    }
```

**Planner guidance:** test `llm_outputs["memory_context_load"]` source/usage labels, optional legacy dual-write, trace step node naming, and all contextual-only surfaces. Use fake service classes rather than hitting DB unless the behavior is service-boundary integration.

---

### `tests/agent/test_reviewed_memory_context_retrieve.py` (existing node tests)

**Analog:** same file

**Unified bundle and CWC separation pattern** (lines 372-440):
```python
result = await reviewed_memory_context_retrieve(
    _state(
        tenant_id=trusted_context.tenant_id,
        user_id=trusted_context.user_id,
        active_slots={"refund_case_id": "RF-CWC-1"},
        **_session_context_state(),
    ),
    {
        "configurable": {
            "session": object(),
            "trusted_context": trusted_context,
            "memory_context_service": FakeMemoryContextService(),
            "case_working_context_lifecycle_adapter": FakeCwcLifecycleAdapter(),
        }
    },
)

bundle = result["memory_context_bundle"]
assert bundle["schema_version"] == "memory_context_bundle.v1"
assert bundle["session_context"]["policy_topic_hints"] == ["refund_policy@v1"]
assert bundle["long_term_items"][0]["semantic_kind"] == "merchant_preference"
assert bundle["case_items"][0]["excerpt"] == "Reviewed case excerpt."
assert bundle["reviewed_status_ref"]["status"] == "loaded"
assert bundle["case_working_context"] == {"content": {"customer_request": "用户询问退款进度"}}
assert bundle["case_working_context_status_ref"]["read_status"] == "loaded"
```

**Active CWC is not reviewed precedent pattern** (lines 443-503):
```python
assert result["case_memory"] == [
    {
        "case_memory_id": "generated-precedent-1",
        "excerpt": "Approved closed_case_cwc_candidate precedent.",
    }
]
assert result["case_working_context"] == {"content": {"customer_request": "当前案件仍按 CWC 单独读取"}}
assert result["memory_context_bundle"]["case_items"] == result["case_memory"]
assert result["memory_context_bundle"]["case_working_context"] == result["case_working_context"]
```

**Adapter error isolation pattern** (lines 626-657):
```python
result = await reviewed_memory_context_retrieve(
    _state(
        tenant_id=trusted_context.tenant_id,
        user_id=trusted_context.user_id,
        active_slots={"refund_case_id": "RF-CWC-1"},
    ),
    {
        "configurable": {
            "session": object(),
            "trusted_context": trusted_context,
            "memory_context_service": FakeMemoryContextService(),
            "case_working_context_lifecycle_adapter": FailingCwcLifecycleAdapter(),
        }
    },
)

assert result["long_term_memory"][0]["semantic_kind"] == "merchant_preference"
assert result["case_memory"][0]["excerpt"] == "Reviewed case excerpt."
assert result["case_working_context"] is None
assert result["case_working_context_lifecycle_status"]["status"] == "error"
assert result["node_errors"][-1] == {
    "node": "reviewed_memory_context_retrieve",
    "error_code": "CASE_WORKING_CONTEXT_LOAD_FAILED",
}
```

---

### `tests/agent/test_graph.py` (graph smoke)

**Analog:** same file

**Router edge keys pattern** (lines 53-68):
```python
ROUTER_EDGE_KEYS = {
    "route_after_safety": {"session_context_load", "clarification_gate", "final_response"},
    "route_after_contextual_intent": {"clarification_gate", "final_response", "investigate", "slot_resolution_gate"},
    "route_after_slot_resolution": {"clarification_gate", "investigate", "long_term_memory_retrieve"},
    "route_after_risk": {"approval_gate", "final_response"},
    "route_after_approval": {"assess_risk_and_approval", "action_draft", "final_response"},
    ...
}
```

**Runtime/vocabulary projection test pattern** (lines 951-968):
```python
def test_legacy_graph_runtime_names_project_to_target_vocabulary():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)

    legacy_node_targets = {"long_term_memory_retrieve": "memory_context_load"}
    for legacy_node, target_node in legacy_node_targets.items():
        assert legacy_node in nodes
        assert target_graph_name(legacy_node, kind="node") == target_node
```

**Reviewed-memory graph smoke pattern** (lines 1164-1189):
```python
@pytest.mark.asyncio
async def test_canonical_reviewed_memory_hint_reaches_existing_long_term_memory_node(monkeypatch):
    payload = _intent("refund_troubleshooting")
    payload["routing_hints"] = {"needs_reviewed_memory_context": True}
    ...
    final_state = await graph.ainvoke(
        _state("订单ORD-001退款为什么没到账？"),
        _config(manager, events, session=object()),
    )

    assert final_state["long_term_memory"] == []
    assert final_state["case_memory"] == []
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["source"] == "no_reviewed_memory"
    nodes = [step["node"] for step in final_state["trace_steps"]]
    assert "slot_resolution_gate" in nodes
    assert "reviewed_memory_context_retrieve" in nodes
    assert nodes.index("slot_resolution_gate") < nodes.index("reviewed_memory_context_retrieve")
```

**Forbidden leakage assertion pattern** (lines 1294-1306):
```python
state_json = json.dumps(
    {"long_term_memory": final_state["long_term_memory"], "case_memory": final_state["case_memory"]},
    ensure_ascii=False,
)
forbidden_terms = [
    "EvidenceRefV1",
    "approval_authority_body",
    "action_authority_body",
    "raw_tool_payload",
    "replay_debug_blob",
    "must-not-leak",
]
assert all(term not in state_json for term in forbidden_terms)
```

**Planner guidance:** update the graph smoke to expect `memory_context_load` in active trace order after `slot_resolution_gate` and before `investigate`. Preserve leakage assertions.

---

### `tests/agent/test_intent_routing.py` and `tests/test_graph_routing.py` (routing tests)

**Analogs:** same files

**Slot-resolution route tests** (`test_intent_routing.py` lines 558-594):
```python
def test_route_after_slot_resolution_totality_and_long_term_memory_route():
    assert route_after_slot_resolution({}) in SLOT_ROUTES
    assert (
        route_after_slot_resolution(
            {
                "primary_intent": "policy_qa",
                "required_slots": {"all_of": [], "any_of": [], "optional": []},
                "extracted_slots": {},
                "routing_hints": {"needs_long_term_memory": True},
            }
        )
        == "long_term_memory_retrieve"
    )
```

**Route-map coverage pattern** (`test_graph.py` lines 1017-1049):
```python
def test_all_router_return_keys_have_edges():
    ...
    assert (
        route_after_slot_resolution(
            {"primary_intent": "policy_qa", "required_slots": {"all_of": [], "any_of": [], "optional": []}}
        )
        in ROUTER_EDGE_KEYS["route_after_slot_resolution"]
    )
    assert ROUTER_EDGE_KEYS["route_after_slot_resolution"] == {
        "clarification_gate",
        "investigate",
        "long_term_memory_retrieve",
    }
```

**Planner guidance:** update route expectations from `long_term_memory_retrieve` to `memory_context_load`, but keep `needs_long_term_memory` accepted as a compatibility hint unless the plan proves all live callers moved.

---

### `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` (static graph baseline)

**Analogs:** same files

**Baseline constants pattern** (`graph_baseline.py` lines 11-67):
```python
TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "memory_context_load",
        ...
    }
)

CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset(
    {
        ...
        "long_term_memory_retrieve",
        ...
    }
)

MIGRATION_MODE_LEGACY_NODE_MAP = {
    "long_term_memory_retrieve": {
        "target": "memory_context_load",
        "delete_phase": "Phase 55",
        "owner_requirement": "CAGM-06",
    },
    ...
}
```

**AST extraction pattern** (`graph_baseline.py` lines 148-204):
```python
def graph_add_node_names(path: Path = GRAPH_PATH) -> frozenset[str]:
    tree = ast.parse(_source(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_node"):
            continue
        if not node.args:
            raise AssertionError("Unsupported graph baseline shape: add_node without positional node name")
        names.add(_string_literal(node.args[0], context="add_node node name"))
    return frozenset(names)
```

**Migration assertion pattern** (`test_canonical_graph_baseline.py` lines 61-85):
```python
def test_migration_mode_maps_every_active_legacy_node_to_target() -> None:
    active_legacy_nodes = CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES

    assert active_legacy_nodes == frozenset(MIGRATION_MODE_LEGACY_NODE_MAP)
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {
        "long_term_memory_retrieve": {
            "target": "memory_context_load",
            "delete_phase": "Phase 55",
            "owner_requirement": "CAGM-06",
        },
        ...
    }
```

**Planner guidance:** Phase 55 changes only the Phase 55-owned row. Leave `generate_recommendation` and `assess_risk_and_approval` as Phase 56/57 legacy rows.

---

### `tests/agent/test_graph_vocabulary.py`, `tests/architecture/test_phase32_static_contract.py`, `tests/architecture/test_memory_contract_delta.py`

**Analog:** `tests/agent/test_graph_vocabulary.py`

**Parametrized vocabulary pattern** (lines 21-54):
```python
@pytest.mark.parametrize(
    ("name", "kind", "target_name", "status", "runnable"),
    [
        ("long_term_memory_retrieve", "node", "memory_context_load", "compatibility_alias", True),
        ("reviewed_memory_context_retrieve", "node", "memory_context_load", "runtime", True),
        ("extract_slots", "node", "slot_resolution_gate", "compatibility_alias", True),
        ("slot_resolution_gate", "node", "slot_resolution_gate", "runtime", True),
    ],
)
def test_legacy_graph_names_project_to_target_vocabulary(...):
    entry = graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

    assert entry is not None
    assert entry.legacy_name == name
    assert entry.target_name == target_name
    assert entry.kind == kind
    assert entry.status == status
    assert entry.runnable is runnable
    assert target_graph_name(name, kind=kind) == target_name  # type: ignore[arg-type]
```

**Alias reason-code pattern** (lines 129-148):
```python
@pytest.mark.parametrize(
    ("name", "kind", "target_name"),
    [
        ("extract_slots", "node", "slot_resolution_gate"),
        ("route_after_slots", "router", "route_after_slot_resolution"),
    ],
)
def test_phase54_retained_aliases_are_compatibility_only_with_delete_phase(...):
    entry = graph_vocabulary_entry(name, kind=kind)  # type: ignore[arg-type]

    assert entry is not None
    assert entry.target_name == target_name
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert PHASE54_ALIAS_REASON_CODES <= set(entry.reason_codes)
```

**Planner guidance:** clone the Phase 54 reason-code test shape for Phase 55 memory alias reason codes.

---

### `tests/memory/test_phase48_1_memory_compat_alignment.py` and phase 46/47/48 memory alignment tests

**Analog:** `tests/memory/test_phase48_1_memory_compat_alignment.py`

**Approved pytest command scan pattern** (lines 91-101):
```python
def test_phase48_1_plan_pytest_entrypoints_use_moca_runner() -> None:
    checked_paths = sorted(PHASE48_1_DIR.glob("48.1-*-PLAN.md")) + [PHASE48_1_DIR / "48.1-VALIDATION.md"]
    snippets: list[tuple[Path, str]] = []
    for path in checked_paths:
        snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

    assert snippets
    for path, snippet in snippets:
        assert snippet.startswith(
            ("UV_CACHE_DIR=/tmp/uv-cache uv run pytest", ".venv/bin/pytest")
        ), (path.name, snippet)
```

**Compatibility-name static guard to update** (lines 150-176):
```python
def test_reviewed_memory_hint_aliases_are_explicit() -> None:
    routing_source = _source(ROUTING_PATH)
    reviewed_node_source = _source(REVIEWED_MEMORY_NODE_PATH)

    for source in (routing_source, reviewed_node_source):
        assert "needs_reviewed_memory_context" in source
        assert "needs_long_term_memory" in source
    assert 'return "long_term_memory_retrieve"' in routing_source
```

**No destructive rename guard pattern** (lines 178-226):
```python
def test_deferred_compatibility_names_remain_static_only() -> None:
    _assert_contains(
        DB_MODELS_PATH,
        '__tablename__ = "session_memories"',
        '__tablename__ = "long_term_memories"',
        '__tablename__ = "case_memories"',
        '__tablename__ = "case_working_contexts"',
        '__tablename__ = "conversation_threads"',
        "case_id: Mapped[str | None]",
    )
    ...
```

**Planner guidance:** keep storage/API/config compatibility assertions. Change only assertions that require active graph/runtime use of `long_term_memory_retrieve`.

---

### Memory boundary tests

**Files:** `tests/agent/test_memory_evidence_boundary.py`, `tests/memory/test_reviewed_memory_context_boundary.py`, `tests/memory/test_context_refs.py`

**Contextual-only surface fixture pattern** (`test_memory_evidence_boundary.py` lines 59-126):
```python
def _planned_contextual_only_memory_surfaces(tenant_id: str) -> dict[str, dict]:
    source_identity_hash = "sha256:" + ("b" * 64)
    session_context_ref = {
        "schema_version": "session_context_ref.v1",
        "authority_class": "contextual_only",
        ...
    }
    reviewed_memory_ref = {
        "schema_version": "reviewed_memory_ref.v1",
        "authority_class": "contextual_only",
        ...
    }
    return {
        "SessionContextRef": session_context_ref,
        "ReviewedMemoryRef": reviewed_memory_ref,
        "SessionContextLoadStatusV1": {
            "schema_version": "session_context_load_status.v1",
            "status": "loaded",
            "source": "postgres_session_memory",
            "authority_class": "contextual_only",
            ...
        },
```

**Prompt projection anti-leakage pattern** (`test_memory_evidence_boundary.py` lines 560-617):
```python
projected = project_memory_context_for_prompt(memory_context)

assert "Merchant prefers payment-channel verification" in projected
assert "Similar case asks support" in projected
for marker in (
    "raw",
    "private",
    "debug",
    "secret",
    "EvidenceRefV1",
    "BusinessFactRefV1",
    "approval_authority_body",
    "action_authority_body",
    "ReplayEventV3",
    "MaterialClaim",
    "authority_class",
    "contextual_only",
    "forged-evidence-ref",
    "forged-business-ref",
):
    assert marker not in projected
```

**Cross-merchant and tenant/global denial pattern** (`test_reviewed_memory_context_boundary.py` lines 226-284):
```python
bundle = await _context_service(session).load_reviewed_memory_context(
    trusted_context=_trusted_context(seeded_session, merchant_ids=[merchant_a]),
    current_slots={"merchant_id": merchant_b},
    trusted_business_context={"merchant_id": merchant_b},
    query="refund merchant B",
    case_type="refund_dispute",
)

memory_context = _bundle_dict(bundle)
status_ref = memory_context["status_ref"]
assert memory_context["long_term_items"] == []
assert memory_context["case_items"] == []
assert any(reason.startswith("merchant_scope_denied") for reason in status_ref["filter_reasons"])
```

**DTO validation pattern** (`test_context_refs.py` lines 220-272):
```python
def test_memory_context_bundle_accepts_optional_case_working_context_without_merging_reviewed_items() -> None:
    bundle = MemoryContextBundle.model_validate(
        {
            "schema_version": "memory_context_bundle.v1",
            "authority_class": "contextual_only",
            "session_context": _session_context().model_dump(mode="json"),
            "long_term_items": [{"content": "merchant preference", "ref": _reviewed_memory_ref_payload("long_term")}],
            "case_items": [{"content": "reviewed case precedent", "ref": _reviewed_memory_ref_payload("case")}],
            "case_working_context": {
                "content": {"customer_request": "用户询问退款进度"},
                "ref": _case_working_context_ref_payload(),
            },
            "case_working_context_status_ref": _case_working_context_status_payload(),
        }
    )

    assert bundle.authority_class == "contextual_only"
    assert bundle.long_term_items[0]["ref"]["memory_type"] == "long_term"
    assert bundle.case_items[0]["ref"]["memory_type"] == "case"
```

**Planner guidance:** tests must prove memory remains contextual-only and cannot become evidence, current business fact, approval/action authority, or replay truth.

---

### Trace/API projection files

**Files:** `src/agent/trace.py`, `src/api/routers/traces.py`, `src/api/routers/agent_runs.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`

**Trace persistence preserves implementation node** (`trace.py` lines 91-130):
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
        )
```

**Trace API projection pattern** (`traces.py` lines 108-117):
```python
def _to_trace_step_response(step) -> dict[str, object]:
    projected = project_trace_step_for_contract({"node": step.node_name})
    return {
        "node": step.node_name,
        "implementation_node": projected["implementation_node"],
        "target_node": projected["target_node"],
        "status": step.status,
        "latency_ms": step.latency_ms,
        "tool_name": step.tool_name,
    }
```

**SSE projection pattern** (`agent_runs.py` lines 1130-1151):
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
    if node_name:
        data["target_node_name"] = target_graph_name(node_name, kind="node")
    return {"data": json.dumps(data, ensure_ascii=False)}
```

**SSE test pattern** (`test_agent_runs_api.py` lines 971-1004):
```python
def test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name():
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
    assert data["payload"] == {"tool_name": "slot_parser"}
```

**Trace summary test pattern** (`test_trace.py` lines 166-201):
```python
summary = build_trace_summary(
    "run-phase54-runtime-projection",
    {
        "current_intent": "refund_troubleshooting",
        "trace_steps": [
            {"node": "slot_resolution_gate", "status": "completed"},
            {"node": "route_after_slot_resolution", "status": "completed"},
        ],
        "final_response": "done",
    },
    14,
)

assert summary["nodes_executed"] == [
    "slot_resolution_gate",
    "route_after_slot_resolution",
]
assert summary["target_nodes_executed"] == [
    "slot_resolution_gate",
    "route_after_slot_resolution",
]
```

**Planner guidance:** vocabulary changes should make most trace/API projection behavior work without changing trace storage. Add `memory_context_load` display label in `NODE_MESSAGES` only if SSE output needs a better user-facing label.

---

### Docs and architecture debt

**Files:** `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`, `docs/contract-spec.md`

**Current-source snapshot pattern** (`docs/current-langgraph-architecture.md` lines 1-5):
```markdown
# 当前 LangGraph Graph/Node 架构图

> 本图只根据当前仓库源码绘制，主要依据 `src/agent/graph.py` 的 `build_graph()` 节点/边定义，以及 `src/agent/routing.py` 和 `src/agent/graph.py` 中的条件路由函数。未把 planning 文档、README 描述或测试断言当作已实现事实。
>
> 读法边界：本文件是当前源码快照，不是目标架构。
```

**Compatibility table pattern** (`docs/current-langgraph-architecture.md` lines 91-105):
```markdown
| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
|----------------|-----------------|--------|------------------|------------|--------------|
| `route_after_slots` helper | `route_after_slot_resolution` | Backward-compatible router import/test surface after active router cutover | `route_after_slots -> route_after_slot_resolution`, status `compatibility_alias`, with Phase 54 delete-by-58 reason codes | Active graph uses `route_after_slot_resolution`; helper delegates to canonical router | No later than Phase 58 |
| `long_term_memory_retrieve` active node | `memory_context_load` / Phase 55 CAGM-06 | Memory context load cutover is explicitly Phase 55-owned | `long_term_memory_retrieve -> memory_context_load`, status `compatibility_alias` | Architecture baseline keeps this as active legacy migration row | Phase 55 |
```

**Architecture debt closure pattern** (`.planning/ARCHITECTURE-DEBT.md` lines 1038-1059):
```markdown
**处理状态**
- ✅ 已关闭 active runtime debt：`src/agent/graph.py` 当前注册 `slot_resolution_gate`，不注册 `extract_slots`；active conditional edge source/router 为 `("slot_resolution_gate", "route_after_slot_resolution")`，不再有 `("extract_slots", "route_after_slots")`。
- ✅ `src/agent/graph_vocabulary.py` 已将 `slot_resolution_gate` node 与 `route_after_slot_resolution` router 标为 `runtime`；`extract_slots` node 与 `route_after_slots` router 保留为 `compatibility_alias`，reason codes 至少包含 `PHASE_54_COMPATIBILITY_ALIAS`、`HISTORICAL_TRACE_PROJECTION`、`IMPORT_TEST_COMPATIBILITY`、`DELETE_BY_PHASE_58`。
...
**剩余风险**
- 🟡 Retained compatibility surfaces must be removed or reclassified no later than Phase 58.
- 🟡 Phase 55 / 56 / 57 still own active `long_term_memory_retrieve`、`generate_recommendation`、`assess_risk_and_approval` cutovers; Phase 54 does not activate `memory_context_load`、`recommendation_generation` or `risk_gate` as active registered graph nodes.
```

**Planner guidance:** update docs after source/test cutover. Keep `docs/current-langgraph-architecture.md` as implemented fact, not target-state aspiration. If implementation intentionally diverges from `docs/contract-spec.md`, add an explicit MVP/target-state note instead of silently drifting.

## Shared Patterns

### Active Graph Identity Cutover

**Sources:** `src/agent/graph.py` lines 278-329; `src/agent/routing.py` lines 37-41 and 478-506; `tests/architecture/graph_baseline.py` lines 11-89.

**Apply to:** `src/agent/graph.py`, `src/agent/routing.py`, graph baseline tests, graph smoke tests.

The registered node key, route return value, conditional edge map key, conditional edge map destination, direct edge source, and architecture baseline must move together from `long_term_memory_retrieve` to `memory_context_load`.

### Compatibility Alias Projection

**Sources:** `src/agent/graph_vocabulary.py` lines 41-46 and 176-186; `tests/agent/test_graph_vocabulary.py` lines 129-148.

**Apply to:** `src/agent/graph_vocabulary.py`, trace/API tests, docs, architecture debt.

Retained aliases need owner/reason/delete metadata. Use Phase 55 reason codes analogous to Phase 54: `PHASE_55_COMPATIBILITY_ALIAS`, `HISTORICAL_TRACE_PROJECTION`, `IMPORT_TEST_COMPATIBILITY`, `DELETE_BY_PHASE_58`.

### Memory Authority Boundary

**Sources:** `src/memory/context_refs.py` lines 73-85 and 150-161; `tests/agent/test_memory_evidence_boundary.py` lines 560-617.

**Apply to:** all memory node, DTO, projection, and prompt tests.

All loaded memory/CWC outputs remain `authority_class="contextual_only"` and cannot satisfy `EvidenceRefV1`, `BusinessFactRefV1`, approval/action authority, or replay truth.

### Failure Handling

**Sources:** `src/agent/nodes/reviewed_memory_context_retrieve.py` lines 54-81 and 131-156; `src/memory/context_service.py` lines 580-604.

**Apply to:** `memory_context_load`, reviewed-memory tests, graph smoke.

Missing trusted context, missing actor merchant scope, denied merchant scope, missing services, and service errors return explicit skipped/unavailable context; they do not fail open and do not promote memory authority.

### Approved Verification Commands

**Source:** `tests/memory/test_phase48_1_memory_compat_alignment.py` lines 91-101; project `AGENTS.md`.

**Apply to:** all generated plans and validation sections.

Use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or a verified `.venv/bin/pytest ...`. Do not suggest bare `pytest` or bare `python -m pytest`.

## No Analog Found

All identified new/modified candidates have close analogs in the current codebase. Planner should still treat the exact finite memory usage label field name as an implementation choice, because no existing field exactly matches Phase 55's requested label set.

## Metadata

**Analog search scope:** `src/agent`, `src/memory`, `src/api/routers`, `tests/agent`, `tests/architecture`, `tests/memory`, trace/API tests, `docs`, `.planning`.

**Files scanned:** 1064 paths under the search scope.

**Pattern extraction date:** 2026-07-07
