# Phase 58: canonical-graph-cutover-and-no-debt-cleanup - Pattern Map

**Mapped:** 2026-07-08
**Files analyzed:** 69 concrete paths / planned artifacts
**Analogs found:** 69 / 69

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/graph_vocabulary.py` | utility | transform | `src/agent/graph_vocabulary.py` | exact |
| `src/agent/graph.py` | config / route | request-response | `src/agent/graph.py` | exact |
| `src/agent/routing.py` | route | request-response | `src/agent/routing.py` | exact |
| `src/agent/nodes/recommendation_generation.py` | graph node / service | transform | `src/agent/nodes/risk_gate.py` | role-match |
| `src/agent/nodes/risk_gate.py` | graph node / service | transform | `src/agent/nodes/risk_gate.py` | exact |
| `src/agent/nodes/memory_context_load.py` | graph node / service | transform | `src/agent/nodes/memory_context_load.py` | exact |
| `src/agent/nodes/slot_resolution_gate.py` | graph node / service | transform | `src/agent/nodes/slot_resolution_gate.py` | exact |
| `src/agent/nodes/contextual_intent_resolve.py` | graph node / service | transform | `src/agent/nodes/contextual_intent_resolve.py` | exact |
| `src/agent/nodes/session_context_load.py` | graph node / service | transform | `src/agent/nodes/session_context_load.py` | exact |
| `src/agent/nodes/generate_recommendation.py` | legacy wrapper / service | transform | `src/agent/nodes/generate_recommendation.py` | exact |
| `src/agent/nodes/assess_risk_and_approval.py` | legacy wrapper / service | transform | `src/agent/nodes/assess_risk_and_approval.py` | exact |
| `src/agent/nodes/classify_intent.py` | legacy wrapper / adapter | transform | `src/agent/nodes/classify_intent.py` | exact |
| `src/agent/nodes/session_memory_load.py` | legacy wrapper / adapter | transform | `src/agent/nodes/session_memory_load.py` | exact |
| `src/agent/nodes/extract_slots.py` | legacy node / service | transform | `src/agent/nodes/slot_resolution_gate.py` | role-match |
| `src/agent/nodes/long_term_memory_retrieve.py` | legacy wrapper / adapter | transform | `src/agent/nodes/memory_context_load.py` | role-match |
| `src/agent/nodes/reviewed_memory_context_retrieve.py` | internal helper | transform | `src/agent/nodes/memory_context_load.py` | partial |
| `src/agent/trace.py` | service | transform | `src/agent/trace.py` | exact |
| `src/repositories/trace_repo.py` | repository | CRUD / transform | `src/repositories/trace_repo.py` | exact |
| `src/api/routers/traces.py` | controller | request-response | `src/api/routers/traces.py` | exact |
| `src/api/routers/agent_runs.py` | controller | streaming / request-response | `src/api/routers/agent_runs.py` | exact |
| `src/api/routers/approvals.py` | controller | request-response | `src/api/routers/approvals.py` | exact |
| `frontend/src/components/timeline/TimelineStep.tsx` | component | event-driven / streaming display | `frontend/src/components/timeline/TimelineStep.tsx` | exact |
| `scripts/eval_agent.py` | utility | batch / eval | `scripts/eval_agent.py` | exact |
| `scripts/diagnose_latency.py` | utility | batch / diagnostics | `tests/architecture/test_canonical_graph_baseline.py` | role-match |
| `eval/replay/dev-contract-manifest.v1.json` | config | batch / static | `eval/replay/dev-contract-manifest.v1.json` | exact |
| `moca.egg-info/SOURCES.txt` | build metadata | batch | `moca.egg-info/SOURCES.txt` | exact |
| `tests/architecture/graph_baseline.py` | utility | static / transform | `tests/architecture/graph_baseline.py` | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | test | static / request-response | `tests/architecture/test_canonical_graph_baseline.py` | exact |
| `tests/agent/test_graph_vocabulary.py` | test | static / transform | `tests/agent/test_graph_vocabulary.py` | exact |
| `tests/architecture/test_phase32_static_contract.py` | test | static | `tests/architecture/test_phase32_static_contract.py` | exact |
| `tests/architecture/test_memory_contract_delta.py` | test | static | `tests/architecture/test_memory_contract_delta.py` | role-match |
| `tests/architecture/test_phase34_approval_action_boundaries.py` | test | static / request-response | `tests/architecture/test_phase34_approval_action_boundaries.py` | role-match |
| `tests/memory/test_phase48_1_memory_compat_alignment.py` | test | static | `tests/memory/test_phase48_1_memory_compat_alignment.py` | role-match |
| `tests/architecture/test_tool_boundaries.py` | test | static | `tests/architecture/test_tool_boundaries.py` | role-match |
| `tests/agent/test_graph.py` | test | request-response / graph integration | `tests/agent/test_graph.py` | exact |
| `tests/test_graph_routing.py` | test | request-response / routing | `tests/test_graph_routing.py` | exact |
| `tests/agent/test_trace.py` | test | transform | `tests/agent/test_trace.py` | exact |
| `tests/test_trace_api.py` | test | request-response | `tests/test_trace_api.py` | exact |
| `tests/test_agent_runs_api.py` | test | streaming / request-response | `tests/test_agent_runs_api.py` | exact |
| `tests/test_approval_api.py` | test | request-response / security | `tests/test_approval_api.py` | exact |
| `tests/test_approval_gate.py` | test | request-response / security | `tests/test_approval_gate.py` | exact |
| `tests/approvals/test_needs_info_resume.py` | test | request-response / service | `tests/approvals/test_needs_info_resume.py` | role-match |
| `tests/approvals/test_service_transitions.py` | test | request-response / service | `tests/approvals/test_service_transitions.py` | role-match |
| `tests/agent/test_nodes/test_risk_gate.py` | test | transform | `tests/agent/test_nodes/test_risk_gate.py` | exact |
| `tests/agent/test_nodes/test_assess_risk_and_approval.py` | test | transform / legacy compatibility | `tests/agent/test_nodes/test_risk_gate.py` | role-match |
| `tests/agent/test_nodes/test_generate_recommendation.py` | test | transform / legacy compatibility | `tests/agent/test_nodes/test_generate_recommendation.py` | exact |
| `tests/agent/test_nodes/test_extract_slots.py` | test | transform / legacy compatibility | `tests/agent/test_nodes/test_slot_resolution_gate.py` | role-match |
| `tests/agent/test_nodes/test_classify_intent.py` | test | transform / legacy compatibility | `src/agent/nodes/classify_intent.py` | role-match |
| `tests/agent/test_session_memory_load.py` | test | transform / legacy compatibility | `src/agent/nodes/session_memory_load.py` | role-match |
| `tests/agent/test_empty_session_adapter.py` | test | transform / legacy compatibility | `src/agent/nodes/session_memory_load.py` | role-match |
| `tests/agent/test_memory_context_load.py` | test | transform | `tests/agent/test_memory_context_load.py` | exact |
| `tests/agent/test_required_slots.py` | test | request-response / routing | `src/agent/routing.py` | role-match |
| `tests/agent/test_intent_routing.py` | test | request-response / routing | `src/agent/routing.py` | role-match |
| `tests/agent/test_intent_golden_contract.py` | test | request-response / routing | `tests/architecture/test_phase32_static_contract.py` | role-match |
| `tests/agent/test_phase22_action_boundary.py` | test | transform / security | `tests/agent/test_nodes/test_risk_gate.py` | role-match |
| `tests/agent/test_phase22_recommendation_integration.py` | test | transform / integration | `tests/agent/test_nodes/test_generate_recommendation.py` | role-match |
| `tests/eval/test_phase35_replay_eval_gates.py` | test | static / batch | `tests/eval/test_phase35_replay_eval_gates.py` | exact |
| `tests/eval/test_phase35_release_monitoring_manifests.py` | test | static / batch | `tests/eval/test_phase35_release_monitoring_manifests.py` | exact |
| `docs/current-langgraph-architecture.md` | docs | static | `docs/current-langgraph-architecture.md` | exact |
| `docs/architecture-overview.md` | docs | static | `docs/current-langgraph-architecture.md` | role-match |
| `docs/target-agent-platform-architecture-plan.md` | docs | static | `docs/current-langgraph-architecture.md` | role-match |
| `docs/contract-spec.md` | docs / contract | static | `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` | role-match |
| `README.md` | docs | static | `docs/current-langgraph-architecture.md` | role-match |
| `.planning/ARCHITECTURE-DEBT.md` | planning ledger | static | `.planning/ARCHITECTURE-DEBT.md` | exact |
| `.planning/ROADMAP.md` | planning metadata | static | `.planning/ROADMAP.md` | exact |
| `.planning/REQUIREMENTS.md` | planning metadata | static | `.planning/REQUIREMENTS.md` | exact |
| `.planning/STATE.md` | planning metadata | static | `.planning/STATE.md` | exact |
| `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-VALIDATION.md` | validation artifact | static / batch | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md` | role-match |
| `<phase58_static_classifier>` | utility / validation artifact | batch / static | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md` | role-match |

## Pattern Assignments

### Active Graph And Vocabulary Cleanup

**Applies to:** `src/agent/graph_vocabulary.py`, `src/agent/graph.py`, `src/agent/routing.py`, `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `tests/agent/test_graph_vocabulary.py`, `tests/architecture/test_phase32_static_contract.py`, `tests/architecture/test_memory_contract_delta.py`, `tests/architecture/test_phase34_approval_action_boundaries.py`, `tests/memory/test_phase48_1_memory_compat_alignment.py`

**Primary analogs:** `src/agent/graph_vocabulary.py`, `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`

**Current vocabulary data shape** (`src/agent/graph_vocabulary.py` lines 13-20):
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

**Compatibility rows to remove or reclassify** (`src/agent/graph_vocabulary.py` lines 41-67, 151-180):
```python
_PHASE56_RECOMMENDATION_ALIAS_REASON_CODES = (
    "PHASE_56_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
)
_PHASE57_RISK_ALIAS_REASON_CODES = (
    "PHASE_57_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
)
_entry(
    "generate_recommendation",
    "recommendation_generation",
    "node",
    "compatibility_alias",
    True,
    _PHASE56_RECOMMENDATION_ALIAS_REASON_CODES,
)
_entry("risk_gate", "risk_gate", "node", "runtime", True),
_entry(
    "assess_risk_and_approval",
    "risk_gate",
    "node",
    "compatibility_alias",
    False,
    _PHASE57_RISK_ALIAS_REASON_CODES,
)
```

**Projection helper currently mixes runtime and compatibility** (`src/agent/graph_vocabulary.py` lines 206-237):
```python
def graph_vocabulary_entry(name: str, *, kind: TargetGraphKind | None = None) -> GraphVocabularyEntry | None:
    if kind is not None:
        return _ENTRY_BY_KIND_AND_NAME.get((kind, name))
    matches = [entry for entry in _ENTRIES if entry.legacy_name == name]
    if len(matches) == 1:
        return matches[0]
    return None


def target_graph_name(name: str, *, kind: TargetGraphKind | None = None) -> str:
    entry = graph_vocabulary_entry(name, kind=kind)
    if entry is None:
        return name
    return entry.target_name


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

**Active graph exact canonical registration** (`src/agent/graph.py` lines 272-286):
```python
builder.add_node("receive_request", receive_request)
builder.add_node("safety_pre_route", safety_pre_route)
builder.add_node("session_context_load", session_context_load)
builder.add_node("contextual_intent_resolve", contextual_intent_resolve, retry_policy=_llm_retry)
builder.add_node("slot_resolution_gate", slot_resolution_gate, retry_policy=_llm_retry)
builder.add_node("memory_context_load", memory_context_load)
builder.add_node("investigate", investigate)
builder.add_node("rag_context_build", rag_context_build)
builder.add_node("recommendation_generation", recommendation_generation, retry_policy=_llm_retry)
builder.add_node("claim_verify", claim_verify)
builder.add_node("risk_gate", risk_gate, retry_policy=_llm_retry)
builder.add_node("clarification_gate", clarification_gate)
builder.add_node("approval_gate", approval_gate)
builder.add_node("action_draft", action_draft)
builder.add_node("final_response", final_response, retry_policy=_llm_retry)
```

**Canonical route-map pattern to preserve** (`src/agent/graph.py` lines 340-374):
```python
builder.add_conditional_edges(
    "recommendation_generation",
    route_after_recommendation,
    {
        "claim_verify": "claim_verify",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "claim_verify",
    route_after_claim_verify,
    {
        "risk_gate": "risk_gate",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "risk_gate",
    route_after_risk,
    {
        "approval_gate": "approval_gate",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {
        "approval_gate": "approval_gate",
        "risk_gate": "risk_gate",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
)
```

**AST helper pattern for final no-debt gate** (`tests/architecture/graph_baseline.py` lines 11-29, 131-140, 406-420):
```python
TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "memory_context_load",
        "investigate",
        "rag_context_build",
        "recommendation_generation",
        "claim_verify",
        "risk_gate",
        "approval_gate",
        "action_draft",
        "clarification_gate",
        "final_response",
    }
)

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

def graph_router_route_values() -> dict[str, frozenset[str]]:
    routing_router_names = {
        "route_after_safety",
        "route_after_contextual_intent",
        "route_after_slot_resolution",
        "route_after_investigate",
        "route_after_rag_context",
        "route_after_recommendation",
        "route_after_claim_verify",
    }
    graph_router_names = {"route_after_risk", "route_after_approval"}
```

**Final skipped gate to activate** (`tests/architecture/test_canonical_graph_baseline.py` lines 225-228):
```python
def test_final_no_debt_gate_is_marked_phase58_scope() -> None:
    pytest.skip("Phase 58 cutover enforces exact canonical graph node set; Phase 51 records the gate.")
    assert graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES
```

**Planner instructions:**
- Keep `graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES`; do not rewire graph nodes unless a test proves drift.
- Remove active-runtime `compatibility_alias` rows from main graph vocabulary or move them to a historical-read projection API with a name that cannot be mistaken for runtime vocabulary.
- Update tests that currently assert Phase 53-57 `compatibility_alias` rows to assert canonical runtime rows and no active-runtime aliases.

### Legacy Wrapper Migration And Deletion

**Applies to:** `src/agent/nodes/recommendation_generation.py`, `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/risk_gate.py`, `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/classify_intent.py`, `src/agent/nodes/session_memory_load.py`, `src/agent/nodes/extract_slots.py`, `src/agent/nodes/long_term_memory_retrieve.py`, `src/agent/nodes/memory_context_load.py`, `src/agent/nodes/slot_resolution_gate.py`, `src/agent/nodes/reviewed_memory_context_retrieve.py`, all direct legacy wrapper tests.

**Primary analogs:** `src/agent/nodes/risk_gate.py`, `src/agent/nodes/memory_context_load.py`, `tests/architecture/test_tool_boundaries.py`

**Current canonical module imports legacy implementation, so move first, delete second** (`src/agent/nodes/recommendation_generation.py` lines 3-20):
```python
from langchain_core.runnables import RunnableConfig

from src.agent.nodes.generate_recommendation import _CANONICAL_NODE, _generate_recommendation_with_identity
from src.agent.state import AgentState


async def recommendation_generation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical recommendation generation graph node.

    The legacy `generate_recommendation` callable remains importable for
    compatibility; this callable owns current canonical trace/output identity.
    """
    return await _generate_recommendation_with_identity(
        state,
        config,
        output_key=_CANONICAL_NODE,
        trace_node=_CANONICAL_NODE,
    )
```

**Risk canonical wrapper with patch seam** (`src/agent/nodes/risk_gate.py` lines 5-31):
```python
from src.agent.nodes import assess_risk_and_approval as _risk_impl
from src.agent.state import AgentState

_CANONICAL_NODE = "risk_gate"


def _get_llm():
    return _risk_impl._get_llm()


async def persist_action_safety_snapshot(*args, **kwargs):
    return await _risk_impl.persist_action_safety_snapshot(*args, **kwargs)


async def risk_gate(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical risk/action graph node.

    The legacy `assess_risk_and_approval` callable remains importable for
    compatibility; this callable owns current canonical trace/output identity.
    """
    return await _risk_impl._assess_risk_and_approval_with_identity(
        state,
        config,
        output_key=_CANONICAL_NODE,
        trace_node=_CANONICAL_NODE,
        get_llm=_get_llm,
        persist_snapshot=persist_action_safety_snapshot,
    )
```

**Legacy metadata rows to delete with wrappers** (`src/agent/nodes/generate_recommendation.py` lines 54-69; `src/agent/nodes/assess_risk_and_approval.py` lines 53-68):
```python
_LEGACY_NODE = "generate_recommendation"
_CANONICAL_NODE = "recommendation_generation"
HISTORICAL_TRACE_PROJECTION = "HISTORICAL_TRACE_PROJECTION"
IMPORT_TEST_COMPATIBILITY = "IMPORT_TEST_COMPATIBILITY"
DELETE_BY_PHASE_58 = "DELETE_BY_PHASE_58"
PHASE_56_COMPATIBILITY_ALIAS = {
    "legacy_surface": _LEGACY_NODE,
    "canonical_owner": _CANONICAL_NODE,
    "reason": IMPORT_TEST_COMPATIBILITY,
    "trace_projection": HISTORICAL_TRACE_PROJECTION,
    "validation_tests": (
        "tests/agent/test_nodes/test_generate_recommendation.py",
        "tests/agent/test_phase22_recommendation_integration.py",
    ),
    "delete_phase": DELETE_BY_PHASE_58,
}
```

```python
_LEGACY_NODE = "assess_risk_and_approval"
_CANONICAL_NODE = "risk_gate"
HISTORICAL_TRACE_PROJECTION = "HISTORICAL_TRACE_PROJECTION"
IMPORT_TEST_COMPATIBILITY = "IMPORT_TEST_COMPATIBILITY"
DELETE_BY_PHASE_58 = "DELETE_BY_PHASE_58"
PHASE_57_COMPATIBILITY_ALIAS = {
    "legacy_surface": _LEGACY_NODE,
    "canonical_owner": _CANONICAL_NODE,
    "reason": IMPORT_TEST_COMPATIBILITY,
    "trace_projection": HISTORICAL_TRACE_PROJECTION,
    "validation_tests": (
        "tests/agent/test_nodes/test_risk_gate.py",
        "tests/agent/test_nodes/test_assess_risk_and_approval.py",
    ),
    "delete_phase": DELETE_BY_PHASE_58,
}
```

**Current legacy callable wrappers** (`src/agent/nodes/generate_recommendation.py` lines 192-208; `src/agent/nodes/assess_risk_and_approval.py` lines 1128-1146):
```python
async def generate_recommendation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Compatibility wrapper for historical imports/tests until Phase 58."""
    return await _generate_recommendation_with_identity(
        state,
        config,
        output_key=_LEGACY_NODE,
        trace_node=_LEGACY_NODE,
    )
```

```python
async def assess_risk_and_approval(state: AgentState, config: RunnableConfig = None) -> dict:
    """Compatibility wrapper for historical imports/tests until Phase 58."""
    return await _assess_risk_and_approval_with_identity(
        state,
        config,
        output_key=_LEGACY_NODE,
        trace_node=_LEGACY_NODE,
    )
```

**Simple delegate wrappers** (`src/agent/nodes/classify_intent.py` lines 71-85; `src/agent/nodes/session_memory_load.py` lines 16-29; `src/agent/routing.py` lines 67-68, 95-96):
```python
async def classify_intent(state: AgentState) -> dict[str, Any]:
    """Compatibility wrapper for the canonical contextual_intent_resolve node."""

    original_get_llm = _canonical._get_llm
    original_intent_registry = _canonical.INTENT_POLICY_REGISTRY
    original_slot_registry = _canonical.SLOT_POLICY_REGISTRY
    try:
        _canonical._get_llm = _get_llm
        _canonical.INTENT_POLICY_REGISTRY = INTENT_POLICY_REGISTRY
        _canonical.SLOT_POLICY_REGISTRY = SLOT_POLICY_REGISTRY
        return _with_legacy_intent_output_mirror(await _canonical.contextual_intent_resolve(state))
    finally:
        _canonical._get_llm = original_get_llm
        _canonical.INTENT_POLICY_REGISTRY = original_intent_registry
        _canonical.SLOT_POLICY_REGISTRY = original_slot_registry
```

```python
async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the target session_context_load node."""
    return await session_context_load(
        state,
        config,
        node_name="session_memory_load",
        settings_obj=settings,
        memory_service_cls=MemoryService,
        session_memory_repository_cls=SessionMemoryRepository,
        session_memory_bundle_service_cls=SessionMemoryBundleService,
        conversation_repository_cls=ConversationRepository,
        conversation_service_cls=ConversationService,
        memory_context_service_cls=MemoryContextService,
    )
```

```python
def route_after_intent(state: AgentState) -> str:
    return route_after_contextual_intent(state)

def route_after_slots(state: AgentState) -> str:
    return route_after_slot_resolution(state)
```

**Canonical module that scrubs helper/legacy identity while keeping helper implementation** (`src/agent/nodes/memory_context_load.py` lines 27-52, 104-139):
```python
"""Canonical contextual memory graph node.

The reviewed-memory helper owns storage/service semantics. This node owns
active graph identity and the Phase 55 contextual-only metrics contract.
"""
result = await reviewed_memory_context_retrieve(
    state,
    config,
    memory_context_service_cls=memory_context_service_cls,
    long_term_memory_repository_cls=long_term_memory_repository_cls,
    case_memory_repository_cls=case_memory_repository_cls,
    long_term_memory_service_cls=long_term_memory_service_cls,
    case_memory_service_cls=case_memory_service_cls,
    case_working_context_lifecycle_adapter_cls=case_working_context_lifecycle_adapter_cls,
)
result = dict(result)
canonical_metrics = _canonical_metrics(state, result)
result["llm_outputs"] = {
    **_without_legacy_metrics(state.get("llm_outputs")),
    **_without_legacy_metrics(result.get("llm_outputs")),
    _CANONICAL_NODE: canonical_metrics,
}
result["trace_steps"] = _canonical_trace_steps(state, result, canonical_metrics)
if "node_errors" in result:
    result["node_errors"] = _canonical_node_errors(result.get("node_errors"))
return result
```

```python
def _canonical_trace_steps(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    canonical_metrics: Mapping[str, Any],
) -> list[Any]:
    prior_steps = _list_value(state.get("trace_steps"))
    trace_steps = _list_value(result.get("trace_steps"))
    canonical_steps: list[Any] = []
    for index, step in enumerate(trace_steps):
        if index >= len(prior_steps) and isinstance(step, Mapping) and step.get("node") == _HELPER_NODE:
            updated_step = dict(step)
            updated_step["node"] = _CANONICAL_NODE
            updated_step["metrics_json"] = dict(canonical_metrics)
            canonical_steps.append(updated_step)
        else:
            canonical_steps.append(step)
    return canonical_steps
```

**Existing deleted-module guard pattern** (`tests/architecture/test_tool_boundaries.py` lines 104-116):
```python
def test_legacy_retrieve_policy_evidence_node_is_deleted() -> None:
    assert not (ROOT / "src" / "agent" / "nodes" / "retrieve_policy_evidence.py").exists()

    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in sorted(base.glob("**/*.py")):
            if path == Path(__file__):
                continue
            for module in _import_targets(path):
                if module == "src.agent.nodes.retrieve_policy_evidence":
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
```

**Planner instructions:**
- For `generate_recommendation.py` and `assess_risk_and_approval.py`, first move shared implementation and patch seams into canonical modules or private canonical helpers. Then delete wrappers if import scans are clean.
- For simple delegates (`classify_intent.py`, `session_memory_load.py`, route helper aliases), prefer deleting after callers/tests move to canonical imports.
- For helpers that remain implementation-only (`reviewed_memory_context_retrieve`), reclassify them as internal helper vocabulary only if needed; do not expose them as active main graph compatibility aliases.
- Add deletion guards using the `Path.exists()` plus AST import scan pattern above.

### Canonical Current-Run Projection And Historical Readability

**Applies to:** `src/agent/trace.py`, `src/repositories/trace_repo.py`, `src/api/routers/traces.py`, `src/api/routers/agent_runs.py`, `frontend/src/components/timeline/TimelineStep.tsx`, `scripts/eval_agent.py`, `scripts/diagnose_latency.py`, `eval/replay/dev-contract-manifest.v1.json`, trace/API/frontend/eval tests.

**Primary analogs:** `src/agent/trace.py`, `src/api/routers/agent_runs.py`, `scripts/eval_agent.py`

**Trace summary preserves implementation node and adds target projection** (`src/agent/trace.py` lines 246-292):
```python
def build_trace_summary(
    run_id: str,
    final_state: dict[str, Any],
    total_latency_ms: int,
) -> dict[str, Any]:
    """Build the safe trace summary returned by the API response."""
    trace_steps = final_state.get("trace_steps") or []
    nodes_executed = [str(step.get("node") or "unknown") for step in trace_steps]
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
    summary = {
        "run_id": run_id,
        "intent": final_state.get("current_intent") or "unknown",
        "nodes_executed": nodes_executed,
        "target_nodes_executed": [step["target_node"] for step in graph_projection_steps],
        "graph_projection": {
            "schema_version": "target_graph_projection.v1",
            "steps": graph_projection_steps,
        },
```

**Repository/API read projection pattern** (`src/repositories/trace_repo.py` lines 67-83; `src/api/routers/traces.py` lines 108-117):
```python
for step in steps:
    projected = project_trace_step_for_contract({"node": step.node_name})
    timeline.append(
        {
            "type": "agent_step",
            "time": step.started_at.isoformat(),
            "title": f"Node: {step.node_name}",
            "status": step.status,
            "detail": {
                "node_name": step.node_name,
                "target_node": projected["target_node"],
                "tool_name": step.tool_name,
                "latency_ms": step.latency_ms,
                "provider_latency_ms": step.provider_latency_ms,
            },
        }
    )
```

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

**SSE projection currently uses `target_graph_name` and legacy fallbacks** (`src/api/routers/agent_runs.py` lines 1132-1198):
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

def _extract_step_payload(node_name: str, update: Any) -> dict[str, Any]:
    update_mapping = _as_mapping(update)
    payload: dict[str, Any] = {}
    if node_name == "risk_gate" or node_name == "assess_risk_and_approval":
        # `assess_risk_and_approval` is historical trace projection only; DELETE_BY_PHASE_58.
        risk = _as_mapping(update_mapping.get("risk_assessment"))
        if risk.get("risk_level"):
            payload["risk_level"] = risk["risk_level"]
    if node_name in {"recommendation_generation", "generate_recommendation"}:
        recommendation = _as_mapping(update_mapping.get("recommendation_draft"))
        summary = recommendation.get("recommended_action") or recommendation.get("short_summary")
        if summary:
            payload["short_summary"] = str(summary)
```

**Frontend is display-only and should not own graph truth** (`frontend/src/components/timeline/TimelineStep.tsx` lines 5-17, 58-86):
```tsx
const NODE_MESSAGES: Record<string, string> = {
  receive_request: '正在接收请求',
  classify_intent: '正在识别意图',
  extract_slots: '正在提取关键信息',
  investigate: '正在调查订单和规则',
  recommendation_generation: '正在生成处理建议',
  generate_recommendation: '正在生成处理建议',
  risk_gate: '正在判断风险等级',
  assess_risk_and_approval: '正在判断风险等级', // historical trace display only; DELETE_BY_PHASE_58
  approval_gate: '需要审批，等待人工决策',
  execute_action: '正在执行操作',
  final_response: '已完成',
}
```

```tsx
export function TimelineStep({ step, isLast }: TimelineStepProps) {
  const nodeName = step.node_name ?? ''
  const message = step.message || (nodeName ? NODE_MESSAGES[nodeName] : '') || `正在执行 ${step.event_type}`
  const dotClass = STATUS_DOT[step.status] ?? STATUS_DOT.pending
  return (
    <li className="relative grid grid-cols-[20px_1fr_auto] gap-3 pb-4">
      ...
      <p className="mt-1 truncate text-label text-muted-foreground">
        {nodeName || step.event_type} · status: {step.status}
      </p>
```

**Eval current-run guard pattern** (`scripts/eval_agent.py` lines 60-73, 761-773, 873-898):
```python
GRAPH_CONTRACT_PATCHED_NODES = {
    "contextual_intent_resolve",
    "slot_resolution_gate",
    "recommendation_generation",
    "risk_gate",
}
GRAPH_CONTRACT_LEGACY_NODES = {
    "classify_intent",
    "session_memory_load",
    "extract_slots",
    "long_term_memory_retrieve",
    "generate_recommendation",
    "execute_action",
}
```

```python
def _assert_graph_contract_harness_current(cases: list[dict[str, Any]]) -> None:
    registered_nodes = _registered_graph_node_names()
    missing_patch_targets = GRAPH_CONTRACT_PATCHED_NODES - registered_nodes
    if missing_patch_targets:
        raise AssertionError(f"graph-contract patch targets are not active nodes: {sorted(missing_patch_targets)}")
    expected_legacy_nodes = {
        node
        for case in cases
        for node in _expected_nodes_for_case(case)
        if node in GRAPH_CONTRACT_LEGACY_NODES
    }
    if expected_legacy_nodes:
        raise AssertionError(f"graph-contract expected legacy nodes: {sorted(expected_legacy_nodes)}")
```

```python
def _expected_nodes_for_case(case: dict[str, Any]) -> list[str]:
    category = case["category"]
    if category == "permission_denied":
        return []
    nodes = ["receive_request", "safety_pre_route", "session_context_load", "contextual_intent_resolve"]
    if case.get("expected_intent") != "policy_qa":
        nodes.append("slot_resolution_gate")
    nodes.extend(["investigate"])
    if category in {"low_confidence_no_evidence", "missing_context", "tool_failure_or_not_found"}:
        return [*nodes, "final_response"]
    if case.get("expected_evidence_doc_keys"):
        nodes.append("rag_context_build")
    nodes.extend(["recommendation_generation", "claim_verify"])
    if case.get("expected_approval_required") or category in {"approval_approved", "approval_rejected", "approval_required"}:
        nodes.append("risk_gate")
```

**Planner instructions:**
- For current-run surfaces, prefer deleting legacy labels/payload branches once sources emit canonical names.
- If historical row readability remains, confine it to trace/replay data-read projection and name it historical-only. Do not call it active graph vocabulary.
- Update eval manifest rows and commands that still reference deleted legacy test paths.

### Approval Retry Canonicalization Safety

**Applies to:** `src/api/routers/approvals.py`, `src/agent/graph.py`, `tests/test_approval_api.py`, `tests/test_approval_gate.py`, `tests/test_graph_routing.py`, `tests/approvals/test_needs_info_resume.py`, `tests/approvals/test_service_transitions.py`

**Primary analogs:** `src/api/routers/approvals.py`, `src/agent/graph.py`, `.planning/ARCHITECTURE-DEBT.md`

**Existing bounded compatibility to delete or retain as data-read only** (`src/api/routers/approvals.py` lines 53-54, 572-611, 771-785):
```python
CANONICAL_RISK_ROUTE = "risk_gate"
LEGACY_RISK_ROUTE = "assess_risk_and_approval"  # DELETE_BY_PHASE_58: persisted historical retry metadata only.
```

```python
metadata = event.metadata_json or {}
resource_refs = event.resource_refs_json or {}
edited_action = None
new_action_payload_hash = None
resume_route = None
if decision.decision_type == "edit":
    edited_action = decision.edited_action_json
    new_action_payload_hash = resource_refs.get("new_action_payload_hash")
    resume_route = _canonical_retry_resume_route(metadata.get("resume_route"))
    if (
        not edited_action
        or body.edited_action != edited_action
        or not new_action_payload_hash
        or resume_route != CANONICAL_RISK_ROUTE
    ):
        raise ApprovalTransitionError("approval_conflict")

trusted = TrustedApprovalResultV1(
    approval_id=approval.id,
    tenant_id=approval.tenant_id,
    run_id=approval.run_id,
    status=approval.status,
    decision_type=decision.decision_type,
    revision=approval.revision,
    request_version=approval.version,
    level_version=level.version,
    assignment_version=assignment.version,
    action_payload_hash=approval.action_payload_hash,
    safety_snapshot_ref=approval.safety_snapshot_ref,
    safety_snapshot_hash=approval.safety_snapshot_hash,
    **binding_fields,
    decided_by=decision.actor_id,
    decided_at=decided_at,
    reason=approval.reason,
    edited_action=edited_action,
    new_action_payload_hash=new_action_payload_hash,
    resume_route=resume_route,
).model_dump(mode="json")
```

```python
def _should_resume_graph(result) -> bool:
    if not result.resume_payload:
        return False
    if result.decision_type == "edit":
        return result.resume_payload.get("resume_route") == CANONICAL_RISK_ROUTE
    return result.decision_type in {"accept", "approve", "reject", "ignore"}

def _canonical_retry_resume_route(route: object) -> str | None:
    if route == CANONICAL_RISK_ROUTE:
        return CANONICAL_RISK_ROUTE
    if route == LEGACY_RISK_ROUTE:
        # DELETE_BY_PHASE_58: server-side reconstruction of persisted pre-cutover edit retry metadata only.
        return CANONICAL_RISK_ROUTE
    return None
```

**Graph route authority is canonical only** (`src/agent/graph.py` lines 133-147):
```python
def route_after_approval(state: AgentState) -> str:
    """Route after a trusted ApprovalService resume result."""
    result = _trusted_approval_result(state)
    if result is None:
        return "final_response"
    decision_type = result.decision_type
    status = result.status
    if (
        decision_type == "edit"
        and status == "superseded"
        and result.resume_route == CANONICAL_RISK_ROUTE
        and result.new_action_payload_hash
    ):
        return CANONICAL_RISK_ROUTE
```

**Architecture debt handoff to preserve** (`.planning/ARCHITECTURE-DEBT.md` lines 1255-1275):
```markdown
## Phase 57 Plan 03 — persisted legacy approval edit retry 规范化到 `risk_gate` ✅已修复验证

**问题 / 根因**
- Phase 57-02 已把 current approval edit `resume_route` 切到 `risk_gate`，但 API retry reconstruction 仍缺少对历史持久化 `resume_route="assess_risk_and_approval"` 的只读兼容规范化。
- 如果直接接受 legacy route 作为 graph resume payload，会让旧 route 重新变成 current authority；如果完全拒绝，又会破坏已经持久化的 pre-cutover edit retry。
...
- `_terminal_decision_result_for_retry(...)` 只在读取 persisted approval event metadata 时接受 legacy route，并在构造 `TrustedApprovalResultV1` 前规范化为 canonical `risk_gate`。
- `_should_resume_graph(...)` 与 `route_after_approval(...)` 仍只接受 current canonical `risk_gate`，fresh/current legacy edit payload fail closed。
```

**Planner instructions:**
- If legacy retry metadata support remains, keep it inside server-side persisted-row reconstruction only, after approval/run/version/hash/snapshot checks.
- Tests must prove graph resume emits `risk_gate` and fresh/current legacy route values fail closed.
- If the compatibility branch is removed, update tests to confirm old persisted metadata no longer authorizes retry rather than silently accepting legacy route strings.

### Static Classifier, Validation Artifact, And Docs Closeout

**Applies to:** `<phase58_static_classifier>`, `58-VALIDATION.md`, docs files, planning ledgers, architecture/static tests.

**Primary analogs:** `57-VALIDATION.md`, `57-05-SUMMARY.md`, `tests/architecture/test_phase32_static_contract.py`, `tests/architecture/test_tool_boundaries.py`

**Phase 57 validation classification style** (`.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md` lines 56-80):
````markdown
## Static Legacy-Hit Classification

Scan command evidence:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import subprocess, collections; pat='assess_risk_and_approval'; roots=['README.md','docs','src','tests','frontend','scripts','eval','rules','.planning/ARCHITECTURE-DEBT.md','.planning/ROADMAP.md','.planning/REQUIREMENTS.md','.planning/STATE.md','.planning/phases/57-risk-gate-and-approval-gate-canonicalization']; exclude={'.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md'}; res=subprocess.run(['git','grep','-n',pat,'--',*roots],text=True,capture_output=True); ... classify by path/category; assert no unclassified rows"
```

Scope:

- Included: `README.md`, `docs/`, `src/`, `tests/`, `frontend/`, `scripts/`, `eval/`, `rules/`, top-level planning ledgers, and active Phase 57 planning artifacts.
- Excluded: this generated `57-VALIDATION.md` report itself, to avoid recursive self-counting.
- Total hits: 421
- Files: 49
- unclassified_rows: 0
````

**Category table pattern** (`57-VALIDATION.md` lines 72-99):
```markdown
| Category | Count | Meaning |
|----------|------:|---------|
| `historical_compatibility_projection` | 40 | Trace/API/frontend vocabulary and tests preserving stored historical names while projecting to `risk_gate`. |
| `legacy_wrapper_or_import_test` | 47 | Legacy wrapper implementation, direct import tests, compatibility tests, or risk-rule comments retained until Phase 58. |
| `previous_state_documentation` | 322 | Historical planning/research/review/summary/docs text describing pre-cutover state or migration context. |
| `phase58_deletion_candidate` | 12 | Explicit deletion candidates such as persisted retry constants, old dev-contract manifest rows, and stale historical docs/tests for Phase 58 cleanup. |

No remaining hit is classified as current active graph registration, current router return value, current eval node, or current approval resume route.
```

**Validation artifact signoff style** (`57-VALIDATION.md` lines 117-143):
```markdown
| Metric | Result |
|--------|--------|
| State | A - existing validation report audited |
| Requirement | CAGM-08 |
| Plans covered | 57-01, 57-02, 57-03, 57-04, 57-05 |
| gaps_found | 0 |
| resolved | 0 |
| escalated | 0 |
| tests_created | 0 |
| manual_only_blockers | 0 |
| nyquist_compliant | true |

...
- [x] `nyquist_compliant: true` set in frontmatter after approved command evidence was recorded.
```

**Validation-command scanner pattern for artifact tests** (`tests/architecture/test_phase32_static_contract.py` lines 85-92, 132-151):
```python
def test_phase32_artifacts_use_project_test_entrypoints_for_validation_commands() -> None:
    violations: list[str] = []
    for path in _phase32_artifacts():
        for line_number, command in _validation_commands(path):
            if command.startswith("pytest") or command.startswith("python -m pytest"):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {command}")

    assert violations == []

def _validation_commands(path: Path) -> list[tuple[int, str]]:
    commands: list[tuple[int, str]] = []
    in_bash_block = False
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_bash_block = stripped in {"```bash", "```sh", "```shell"}
            continue
        command = ""
        if stripped.startswith("<automated>"):
            command = stripped.removeprefix("<automated>").split("</automated>", 1)[0].strip()
        elif in_bash_block:
            command = stripped.removeprefix("$ ").strip()
        elif match := BULLET_INLINE_COMMAND_RE.match(stripped):
            command = match.group(1).strip()
        elif stripped.startswith("| `"):
            command = stripped.strip("|").split("|", 1)[0].strip().strip("`")
        if command:
            commands.append((line_number, command))
    return commands
```

**Current-source docs boundary statement** (`docs/current-langgraph-architecture.md` lines 1-6, 70-90):
```markdown
# 当前 LangGraph Graph/Node 架构图

> 本图只根据当前仓库源码绘制，主要依据 `src/agent/graph.py` 的 `build_graph()` 节点/边定义，以及 `src/agent/routing.py` 和 `src/agent/graph.py` 中的条件路由函数。未把 planning 文档、README 描述或测试断言当作已实现事实。
>
> 读法边界：本文件是当前源码快照，不是目标架构。目标 canonical runtime graph 以 `docs/target-agent-platform-architecture-plan.md` §6.1、`docs/contract-spec.md` §9 和 Phase 50 SPEC 为当前主要契约参考；当前源码已经把风险/动作决策的 active registered node 和 current route value 切到 `risk_gate`。`extract_slots`、`long_term_memory_retrieve`、`generate_recommendation` 与 `assess_risk_and_approval` 已不再是 active registered graph node；它们只保留为历史 trace / import / test / persisted metadata 兼容面。
```

```markdown
## 当前迁移兼容面

历史 traces 或测试/import/persisted metadata surface 中仍可能出现 `classify_intent`、`intent_classification`、`session_memory_load`、`route_after_intent`、`extract_slots`、`route_after_slots`、`long_term_memory_retrieve`、`reviewed_memory_context_retrieve`、`generate_recommendation`、`assess_risk_and_approval`。这些名称只通过 `src/agent/graph_vocabulary.py`、narrow wrapper/import tests 或明确的历史 retry normalization 投影到 canonical owner，不能作为 active graph registration、active route destination 或 active policy route value。
```

**Planner instructions:**
- Final classifier must cover all required legacy strings from `58-VALIDATION.md`, not just `assess_risk_and_approval`.
- Always exclude generated Phase 58 classifier/validation/PATTERNS artifacts from self-counts.
- Report total hits, file count, category counts, zero active-runtime legacy hits, and zero unclassified rows.
- Use approved MOCA entrypoints only: `UV_CACHE_DIR=/tmp/uv-cache uv run ...`, `uv run ...`, or `.venv/bin/...`.

## Shared Patterns

### Runtime vs Historical Projection

**Source:** `src/agent/graph_vocabulary.py` lines 227-237; `src/agent/trace.py` lines 246-292

**Apply to:** graph vocabulary, trace/API projection, frontend labels, eval manifest.

Pattern: active runtime vocabulary should be canonical-only. Historical stored-row readability may preserve `implementation_node`, but target projection must be named as historical/data-read projection and must not advertise active compatibility aliases.

### Canonical Current-Run Identity

**Source:** `tests/agent/test_nodes/test_risk_gate.py` lines 33-63; `tests/agent/test_nodes/test_generate_recommendation.py` lines 297-312

```python
def _assert_no_current_run_legacy_identity(result: dict) -> None:
    assert _LEGACY_NODE not in (result.get("llm_outputs") or {})
    assert all(step.get("node") != _LEGACY_NODE for step in result.get("trace_steps") or [])
    assert all(error.get("node") != _LEGACY_NODE for error in result.get("node_errors") or [])
    assert result.get("fallback_source") != _LEGACY_NODE
    assert result.get("resume_route") != _LEGACY_NODE
```

Use this pattern for any current-run canonical callable tests after wrapper deletion.

### Legacy Deletion Guards

**Source:** `tests/architecture/test_tool_boundaries.py` lines 10-18, 104-116

Use AST import scans and `Path.exists()` checks. Avoid pure text grep as the only proof because negative assertions and historical docs can intentionally contain legacy strings.

### Approval Resume Authority

**Source:** `src/api/routers/approvals.py` lines 572-611, 779-785; `src/agent/graph.py` lines 133-147

Only canonical `risk_gate` may leave the API as graph resume authority. Legacy route strings, if supported at all, are server-side persisted-row reads that canonicalize before `TrustedApprovalResultV1` is constructed.

### Validation And Command Hygiene

**Source:** `57-VALIDATION.md` lines 45-54, 56-80; `tests/architecture/test_phase32_static_contract.py` lines 85-92

All pytest/ruff/static classifier evidence must use `UV_CACHE_DIR=/tmp/uv-cache uv run ...`, `uv run ...`, or `.venv/bin/...`. Bare `pytest` or bare `python -m pytest` is invalid in MOCA.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `<phase58_static_classifier>` | utility / validation artifact | batch / static | No standalone Phase 57 classifier script exists; the closest analog is the inline classifier recorded in `57-VALIDATION.md` plus AST helper patterns from architecture tests. |

## Metadata

**Analog search scope:** `src/`, `tests/`, `frontend/`, `scripts/`, `eval/`, `docs/`, `.planning/ARCHITECTURE-DEBT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, Phase 57 artifacts.

**Files scanned:** `rg --files`, `git grep`, and focused reads over 40+ analog files/ranges.

**Pattern extraction date:** 2026-07-08
