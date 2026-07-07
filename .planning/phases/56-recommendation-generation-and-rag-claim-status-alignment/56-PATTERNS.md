# Phase 56: Recommendation Generation and RAG Claim Status Alignment - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 35
**Analogs found:** 35 / 35

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agent/nodes/recommendation_generation.py` | node | request-response, transform | `src/agent/nodes/memory_context_load.py` + `src/agent/nodes/generate_recommendation.py` | exact for wrapper, exact for generation behavior |
| `src/agent/nodes/generate_recommendation.py` | node, compatibility wrapper | request-response, transform | `src/agent/nodes/long_term_memory_retrieve.py` | role-match |
| `src/agent/graph.py` | graph config | event-driven route map | `src/agent/graph.py` | exact |
| `src/agent/routing.py` | router utility | deterministic request-response | `src/agent/routing.py` | exact |
| `src/agent/graph_vocabulary.py` | compatibility vocabulary | transform, trace projection | `src/agent/graph_vocabulary.py` Phase 55 entries | exact |
| `src/agent/nodes/rag_context_build.py` | node | request-response, transform | `src/agent/nodes/rag_context_build.py` | exact |
| `src/agent/nodes/claim_verify.py` | node | request-response, transform | `src/agent/nodes/claim_verify.py` | exact |
| `src/agent/nodes/final_response.py` | node | request-response, safe projection | `src/agent/nodes/final_response.py` | exact |
| `src/api/routers/agent_runs.py` | API router | SSE streaming, request-response | `src/api/routers/agent_runs.py` Phase 55 projection | exact |
| `src/api/routers/traces.py` | API router | request-response, trace projection | `src/api/routers/traces.py` | exact |
| `src/agent/trace.py` | trace utility | batch transform, persistence | `src/agent/trace.py` | exact |
| `src/repositories/trace_repo.py` | repository | CRUD, transform | `src/repositories/trace_repo.py` | exact |
| `src/agent/rag_claim_summary.py` | projection utility | transform | `src/agent/rag_claim_summary.py` | exact |
| `tests/agent/test_nodes/test_generate_recommendation.py` | test | unit, request-response | existing tests in same file | exact |
| `tests/agent/test_nodes/test_recommendation_generation.py` | test | unit, request-response | `tests/agent/test_memory_context_load.py` + `tests/agent/test_nodes/test_generate_recommendation.py` | role-match |
| `tests/agent/test_nodes/test_claim_verify.py` | test | unit, request-response | `tests/knowledge/test_claim_verification_bundle.py` | role-match |
| `tests/agent/test_graph.py` | test | graph integration | existing Phase 55 graph tests | role-match |
| `tests/test_graph_routing.py` | test | router unit | existing routing tests in same file | exact |
| `tests/architecture/graph_baseline.py` | architecture test helper | static AST transform | `tests/architecture/graph_baseline.py` | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | architecture test | static AST guard | `tests/architecture/test_canonical_graph_baseline.py` | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform, trace projection | Phase 54/55 vocabulary tests | exact |
| `tests/agent/test_trace.py` | test | trace projection | Phase 55 trace projection tests | exact |
| `tests/test_trace_api.py` | API test | request-response, trace projection | Phase 55 trace API tests | exact |
| `tests/test_agent_runs_api.py` | API/SSE test | SSE streaming, safe projection | Phase 55 SSE projection tests | exact |
| `tests/agent/test_rag_context_routing.py` | test | router unit | existing RAG routing matrix | exact |
| `tests/agent/rag_context/test_routing.py` | test | router unit | existing claim route matrix | exact |
| `tests/knowledge/test_verified_evidence_package.py` | test | DTO validation | existing strict package tests | exact |
| `tests/knowledge/test_claim_verification_bundle.py` | test | DTO/service validation | existing strict bundle tests | exact |
| `tests/agent/test_phase22_recommendation_integration.py` | test | integration | existing generation/claim integration | role-match |
| `tests/knowledge/test_facade_integration.py` | test | integration | existing RAG/generation/claim facade path | role-match |
| `frontend/src/components/timeline/TimelineStep.tsx` | component | SSE display projection | same file local `NODE_MESSAGES` pattern | exact |
| `scripts/eval_agent.py` | script | batch eval, graph contract | same script fake LLM and expected node list | exact |
| `scripts/diagnose_latency.py` | script | batch diagnostics | `scripts/eval_agent.py` node-label pattern | role-match |
| `docs/current-langgraph-architecture.md` | docs | architecture snapshot | same doc migration compatibility table | exact |
| `.planning/ARCHITECTURE-DEBT.md` | planning ledger | docs append-only | Phase 55 debt entry | exact |

## Pattern Assignments

### `src/agent/nodes/recommendation_generation.py` (node, request-response)

**Analogs:** `src/agent/nodes/memory_context_load.py`, `src/agent/nodes/generate_recommendation.py`

**Canonical wrapper pattern** (`src/agent/nodes/memory_context_load.py` lines 16-52):
```python
async def memory_context_load(
    state: AgentState,
    config: RunnableConfig,
    *,
    memory_context_service_cls: Any | None = None,
    long_term_memory_repository_cls: Any | None = None,
    case_memory_repository_cls: Any | None = None,
    long_term_memory_service_cls: Any | None = None,
    case_memory_service_cls: Any | None = None,
    case_working_context_lifecycle_adapter_cls: Any | None = None,
) -> dict:
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

**Generation imports and ownership boundary** (`src/agent/nodes/generate_recommendation.py` lines 13-27):
```python
from src.agent.context import ContextAssembler, PromptAssembly
from src.agent.context.session_memory_bundle import load_session_prompt_context
from src.agent.prompts import GENERATE_RECOMMENDATION_SYSTEM
from src.agent.schemas import RecommendationDraft
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
from src.config import settings
from src.knowledge.citation import validate_membership
from src.knowledge.config import (
    MAX_EVIDENCE_TEXT_CHARS,
    MAX_PROMPT_EVIDENCE_ITEMS,
    MAX_PROMPT_EVIDENCE_TOTAL_CHARS,
)
from src.knowledge.schemas import EvidenceRefV1, MaterialClaimV1, VerifiedEvidencePackageV1
from src.tools.contracts import BusinessFactRefV1
```

**Core generation pattern to preserve under canonical identity** (`src/agent/nodes/generate_recommendation.py` lines 173-277):
```python
async def generate_recommendation(state: AgentState, config: RunnableConfig = None) -> dict:
    started_at = _now_iso()
    existing_draft = state.get("recommendation_draft") or {}
    if existing_draft.get("recommended_action") in {"insufficient_evidence", "retrieval_error"}:
        return {"trace_steps": (state.get("trace_steps") or []) + [_trace_step("skipped", started_at)]}

    package = _verified_package_from_state(state)
    if not _package_allows_generation(state, package):
        return _insufficient_verified_package_result(
            state,
            started_at,
            reason_codes=_verified_package_reason_codes(state, package),
        )

    evidence_by_id = _evidence_by_id_from_package(state, package)
    evidence_models = list(evidence_by_id.values())
    evidence_id_by_citation = _evidence_id_by_citation(state, package)
    allowed_citations = _allowed_citation_objects_from_package(state, package)
    prompt_assembly = await _assemble_recommendation_prompt(
        state=state,
        config=config,
        allowed_citations=allowed_citations,
        policy_snippets=_policy_snippets_from_package(state, package),
    )
    messages = prompt_assembly.to_messages()
    structured_llm = _get_llm().with_structured_output(RecommendationDraft)
```

**Copy/adapt outcome authority:** canonical active runs should write `llm_outputs["recommendation_generation"]`, trace step `node="recommendation_generation"`, `material_claims`, `recommendation_draft`, `evidence_refs`, and nothing verifier-owned. Existing lines 255-277 are the return shape to adapt; lines 397-423 are the fail-closed insufficient-package shape to adapt.

### `src/agent/nodes/generate_recommendation.py` (compatibility wrapper, request-response)

**Analog:** `src/agent/nodes/long_term_memory_retrieve.py`

**Legacy wrapper pattern** (`src/agent/nodes/long_term_memory_retrieve.py` lines 15-31):
```python
async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the reviewed memory context boundary."""
    result = await memory_context_load(
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

**Apply:** keep `generate_recommendation` import/test compatibility narrowly. It may delegate to `recommendation_generation`; it must not remain the active graph registration or active trace/output identity for new runs unless a compatibility mirror is explicitly justified and tested.

### `src/agent/graph.py` (graph config, event-driven route map)

**Analog:** same file

**Imports pattern** (`src/agent/graph.py` lines 23-46):
```python
from src.agent.nodes.claim_verify import claim_verify
from src.agent.nodes.contextual_intent_resolve import contextual_intent_resolve
from src.agent.nodes.final_response import final_response
from src.agent.nodes.generate_recommendation import generate_recommendation
from src.agent.nodes.investigate import investigate
from src.agent.nodes.memory_context_load import memory_context_load
from src.agent.nodes.rag_context_build import rag_context_build
from src.agent.routing import (
    route_after_claim_verify,
    route_after_contextual_intent,
    route_after_investigate,
    route_after_rag_context,
    route_after_recommendation,
    route_after_safety,
    route_after_slot_resolution,
)
```

**Active node/route-map pattern to modify** (`src/agent/graph.py` lines 278-365):
```python
builder.add_node("rag_context_build", rag_context_build)
builder.add_node("generate_recommendation", generate_recommendation, retry_policy=_llm_retry)
builder.add_node("claim_verify", claim_verify)

builder.add_conditional_edges(
    "investigate",
    route_after_investigate,
    {
        "final_response": "final_response",
        "clarification_gate": "clarification_gate",
        "rag_context_build": "rag_context_build",
        "recommendation_generation": "generate_recommendation",
    },
)
builder.add_conditional_edges(
    "rag_context_build",
    route_after_rag_context,
    {
        "recommendation_generation": "generate_recommendation",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "generate_recommendation",
    route_after_recommendation,
    {
        "claim_verify": "claim_verify",
        "final_response": "final_response",
    },
)
```

**Apply:** replace active registration and both route-map destinations with `recommendation_generation`; change the `route_after_recommendation` source to `recommendation_generation`. Do not change `assess_risk_and_approval` in Phase 56.

### `src/agent/routing.py` (router utility, deterministic request-response)

**Analog:** same file

**Finite route/status allowlists** (`src/agent/routing.py` lines 21-36):
```python
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "rag_context_build", "recommendation_generation"}
_RECOMMENDATION_ROUTES = {"claim_verify", "final_response"}
RAG_CONTEXT_STATUSES = {
    "not_required",
    "verified",
    "partial",
    "no_evidence",
    "unauthorized",
    "stale",
    "conflict",
    "invalid_hash",
    "invalid_scope",
    "build_error",
}
_RAG_CONTEXT_ROUTES = {"recommendation_generation", "clarification_gate", "final_response"}
_CLAIM_VERIFY_ROUTES = {"assess_risk_and_approval", "final_response"}
```

**Public fail-closed wrapper pattern** (`src/agent/routing.py` lines 509-550):
```python
def route_after_rag_context(state: AgentState) -> str:
    """Route after deterministic RAG context package construction."""
    try:
        route = _route_after_rag_context(state)
    except Exception:
        return "final_response"
    if route in _RAG_CONTEXT_ROUTES:
        return route
    return "final_response"

def route_after_claim_verify(state: AgentState) -> str:
    """Route only from claim bundle state to registered graph node keys."""
    try:
        route = _route_after_claim_verify(state)
    except Exception:
        return "final_response"
    if route in _CLAIM_VERIFY_ROUTES:
        return route
    return "final_response"
```

**RAG fail-closed core** (`src/agent/routing.py` lines 553-566):
```python
def _route_after_rag_context(state: AgentState) -> str:
    if _missing_required_validation_inputs(state):
        return "clarification_gate"

    status = _rag_context_status(state)
    if status not in RAG_CONTEXT_STATUSES:
        return "final_response"
    if status == "verified":
        return "recommendation_generation"
    if status == "not_required":
        return "recommendation_generation" if not _policy_evidence_required(state) else "final_response"
    if status == "partial":
        return "recommendation_generation" if _partial_rag_context_can_generate(state) else "final_response"
    return "final_response"
```

**Claim gate to strengthen** (`src/agent/routing.py` lines 580-592 and 641-650):
```python
def _route_after_claim_verify(state: AgentState) -> str:
    if _claim_verify_has_blocked_claims(state):
        return "final_response"
    bundle = _claim_verification_bundle(state)
    if not bundle:
        return "final_response"
    route = bundle.get("route")
    overall_status = bundle.get("overall_status")
    if route != "continue" or overall_status not in {"verified", "not_required"}:
        return "final_response"
    if _has_proposed_action(state) or _has_risk_signal(state) or _has_verified_action_recommendation(state):
        return "assess_risk_and_approval"
    return "final_response"

def _has_verified_action_recommendation(state: AgentState) -> bool:
    bundle = _claim_verification_bundle(state)
    for raw_result in bundle.get("claim_results") or []:
        result = raw_result.model_dump(mode="python") if hasattr(raw_result, "model_dump") else raw_result
        if not isinstance(result, dict):
            continue
        claim_type = result.get("claim_type") or result.get("authority_class")
        if claim_type == "action_recommendation" and result.get("allows_action_recommendation") is True:
            return True
    return False
```

**Apply:** D-56-10 requires proposed actions/action claims to require explicit `action_recommendation` allowance when action claims are present; do not let `proposed_action` alone open the risk route.

### RAG/Claim Node Files (nodes, request-response transform)

**Applies to:** `src/agent/nodes/rag_context_build.py`, `src/agent/nodes/claim_verify.py`, `src/agent/nodes/final_response.py`, `src/agent/rag_claim_summary.py`

**RAG builder writes package-owned state** (`src/agent/nodes/rag_context_build.py` lines 24-55 and 248-260):
```python
async def rag_context_build(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    candidates, invalid_candidate_count = _candidate_evidence_refs(state)
    knowledge_context = _knowledge_context_from_config(config)
    if knowledge_context is None:
        package = _build_error_package(
            candidates=candidates,
            knowledge_context=_fallback_knowledge_context(),
            retrieval_config_version=_retrieval_config_version(candidates),
            reason_code="missing_trusted_context",
        )
        return _node_result(state, package, started_at)
```

```python
def _node_result(
    state: AgentState,
    package: VerifiedEvidencePackageV1,
    started_at: str,
) -> dict[str, Any]:
    package_data = package.model_dump(mode="json")
    return {
        "rag_context_status": package.status,
        "verified_evidence_package": package_data,
        "citation_map": package_data["citation_map"],
        "evidence_map": package_data["evidence_map"],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(package, started_at)],
    }
```

**Claim verifier owns bundle and compatibility fields** (`src/agent/nodes/claim_verify.py` lines 19-37 and 56-73):
```python
async def claim_verify(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    started_at = _now_iso()
    service = _policy_knowledge_service(config)
    try:
        raw_bundle = await service.verify_claims(
            material_claims=list(state.get("material_claims") or []),
            verified_evidence_package=state.get("verified_evidence_package"),
            business_context=_mapping_or_empty(state.get("business_context")),
            proposed_action=_mapping_or_none(state.get("proposed_action")),
        )
        bundle = (
            raw_bundle
            if isinstance(raw_bundle, ClaimVerificationBundleV1)
            else ClaimVerificationBundleV1.model_validate(raw_bundle)
        )
    except Exception:
        bundle = _claim_verify_error_bundle()

    return _node_result(state, bundle, started_at)
```

```python
return {
    "claim_verification_bundle": bundle_data,
    "blocked_claims": list(bundle.blocked_claims),
    "safe_support_refs": safe_support_refs,
    "verifier_status": bundle.overall_status,
    "verification_route": _legacy_verification_route(bundle),
    "verifier_reason_codes": list(bundle.reason_codes),
    "verifier_safe_citation_refs": safe_ref_ids,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(bundle, started_at)],
}
```

**Final response safe payload precedence** (`src/agent/nodes/final_response.py` lines 403-470 and 763-795):
```python
def _verification_route_payload(state: AgentState) -> dict[str, Any] | None:
    claim_verification = _claim_verification_route_payload(state)
    if claim_verification is not None:
        return claim_verification
    rag_context = _rag_context_route_payload(state)
    if rag_context is not None:
        return rag_context
    rag_verification = state.get("rag_verification")
    if isinstance(rag_verification, dict):
        route = rag_verification.get("route")
        if isinstance(route, dict) and route.get("route") and route.get("route") != "allow":
            return rag_verification
```

```python
verification = _verification_route_payload(state)
if verification is not None:
    if _can_render_policy_qa_partial_overlap(state, draft, verification):
        response_text = _policy_qa_partial_overlap_response(draft)
        response_text = _decorate_deferred_response(response_text, state)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": _policy_qa_partial_overlap_llm_output(response_text, draft, verification),
            },
            "trace_steps": (state.get("trace_steps") or [])
            + [_trace_step("completed", started_at, _final_response_evidence_refs(state, draft))],
        }
```

**Safe RAG/claim summary projection** (`src/agent/rag_claim_summary.py` lines 9-31 and 159-166):
```python
RAG_CLAIM_SUMMARY_SCHEMA_VERSION = "rag_claim_summary.v1"
_RAG_CLAIM_RAW_PAYLOAD_KEYS = frozenset(
    {
        "verified_evidence_package",
        "claim_verification_bundle",
        "debug_projection",
        "verifier_projection",
        "prompt_projection",
        "raw_semantic",
        "source_block",
        "source_block_id",
        "source_block_ids",
        "ocr",
        "ocr_metadata_json",
        "candidate_refs",
        "rejected_candidate_refs",
        "stale_refs",
        "conflict_refs",
        "safe_support_refs",
        "blocked_claims",
        "evidence_map",
    }
)
```

```python
def sanitize_rag_claim_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove raw RAG/claim internals and attach the safe summary when present."""
    summary = build_rag_claim_summary(payload)
    sanitized = {key: value for key, value in payload.items() if key not in _RAG_CLAIM_RAW_PAYLOAD_KEYS}
    sanitized.pop("rag_claim_summary", None)
    if summary is not None:
        sanitized["rag_claim_summary"] = summary
    return sanitized
```

### `src/knowledge/schemas.py` (model, validation transform)

**Analog:** same file

**Strict status vocabulary** (`src/knowledge/schemas.py` lines 73-107):
```python
RAG_CONTEXT_STATUSES = (
    "not_required",
    "verified",
    "partial",
    "no_evidence",
    "unauthorized",
    "stale",
    "conflict",
    "invalid_hash",
    "invalid_scope",
    "build_error",
)
CLAIM_TYPES = ("policy", "business_fact", "action_recommendation")
CLAIM_SUPPORT_STATUSES = ("supported", "unsupported", "partial", "ambiguous", "not_applicable", "error")
SEMANTIC_REVIEW_STATUSES = ("not_needed", "passed", "failed", "ambiguous", "timeout")
CLAIM_BUNDLE_OVERALL_STATUSES = ("verified", "blocked", "manual_review", "not_required", "error")
CLAIM_BUNDLE_ROUTES = ("continue", "final_response", "manual_review")
```

**Strict DTO pattern** (`src/knowledge/schemas.py` lines 126-195):
```python
class VerifiedEvidencePackageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["verified_evidence_package.v1"] = "verified_evidence_package.v1"
    package_id: str
    status: RagContextStatus
    evidence_items: list[EvidenceItemV1] = Field(default_factory=list)
    citation_map: dict[str, list[str]] = Field(default_factory=dict)
    evidence_map: dict[str, EvidenceRefV1] = Field(default_factory=dict)
    prompt_projection: dict[str, Any] = Field(default_factory=dict)
    verifier_projection: dict[str, Any] = Field(default_factory=dict)
    replay_snapshot_refs: list[str] = Field(default_factory=list)
    debug_projection: dict[str, Any] = Field(default_factory=dict)
```

```python
class ClaimVerificationBundleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["claim_verification_bundle.v1"] = "claim_verification_bundle.v1"
    overall_status: ClaimBundleOverallStatus
    route: ClaimBundleRoute
    claim_results: list[ClaimVerificationResultV1] = Field(default_factory=list)
    blocked_claims: list[str] = Field(default_factory=list)
    safe_support_refs: list[EvidenceRefV1] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    verifier_policy_version: str
```

### `src/agent/graph_vocabulary.py` (compatibility vocabulary, transform)

**Analog:** Phase 55 memory alias entries in same file

**Reason-code constant pattern** (`src/agent/graph_vocabulary.py` lines 41-55):
```python
_PHASE55_MEMORY_ALIAS_REASON_CODES = (
    "PHASE_55_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
)
```

**Runtime vs compatibility entries** (`src/agent/graph_vocabulary.py` lines 98-151):
```python
_entry(
    "long_term_memory_retrieve",
    "memory_context_load",
    "node",
    "compatibility_alias",
    True,
    _PHASE55_MEMORY_ALIAS_REASON_CODES,
),
_entry(
    "reviewed_memory_context_retrieve",
    "memory_context_load",
    "node",
    "compatibility_alias",
    True,
    _PHASE55_MEMORY_ALIAS_REASON_CODES,
),
_entry("memory_context_load", "memory_context_load", "node", "runtime", True),
```

**Projection function** (`src/agent/graph_vocabulary.py` lines 197-207):
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

**Apply:** add `recommendation_generation` runtime entry and `generate_recommendation -> recommendation_generation` compatibility alias with Phase 56 reason codes. Keep `assess_risk_and_approval -> risk_gate` as compatibility alias, not active cutover.

### Trace/API/SSE Projection Files

**Applies to:** `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/agent/trace.py`, `src/repositories/trace_repo.py`

**SSE message table** (`src/api/routers/agent_runs.py` lines 56-70):
```python
NODE_MESSAGES: dict[str, str] = {
    "receive_request": "正在接收请求",
    "session_context_load": "正在加载会话上下文",
    "contextual_intent_resolve": "正在识别上下文意图",
    "classify_intent": "正在识别意图",
    "slot_resolution_gate": "正在确认关键信息",
    "extract_slots": "正在提取关键信息",
    "memory_context_load": "正在加载记忆上下文",
    "investigate": "正在调查订单和规则",
    "generate_recommendation": "正在生成处理建议",
    "assess_risk_and_approval": "正在评估风险",
    "approval_gate": "需要审批，等待人工决策",
    "execute_action": "正在执行操作",
    "final_response": "已完成",
}
```

**SSE target projection preserves implementation name** (`src/api/routers/agent_runs.py` lines 1130-1152):
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

**Step payload pattern to update for canonical node** (`src/api/routers/agent_runs.py` lines 1174-1207):
```python
def _extract_step_payload(node_name: str, update: Any) -> dict[str, Any]:
    update_mapping = _as_mapping(update)
    payload: dict[str, Any] = {}

    if node_name == "investigate":
        retrieved = _as_mapping(update_mapping.get("retrieved_evidence"))
        refs = retrieved.get("evidence_refs")
        if refs is None:
            legacy = _as_mapping(retrieved.get("data") or retrieved)
            refs = legacy.get("evidence")
        payload["evidence_count"] = len(refs) if isinstance(refs, list) else 0

    if node_name == "generate_recommendation":
        recommendation = _as_mapping(update_mapping.get("recommendation_draft"))
        summary = recommendation.get("recommended_action") or recommendation.get("short_summary")
        if summary:
            payload["short_summary"] = str(summary)

    rag_claim_summary = build_rag_claim_summary(update_mapping)
    if rag_claim_summary is not None:
        payload["rag_claim_summary"] = rag_claim_summary

    return payload
```

**Trace summary projection** (`src/agent/trace.py` lines 246-304):
```python
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
```

**Trace API response projection** (`src/api/routers/traces.py` lines 108-117):
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

### Architecture Baseline Tests

**Applies to:** `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`

**Node/migration baseline pattern** (`tests/architecture/graph_baseline.py` lines 11-62):
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

MIGRATION_MODE_LEGACY_NODE_MAP = {
    "generate_recommendation": {
        "target": "recommendation_generation",
        "delete_phase": "Phase 56",
        "owner_requirement": "CAGM-07",
    },
    "assess_risk_and_approval": {
        "target": "risk_gate",
        "delete_phase": "Phase 57",
        "owner_requirement": "CAGM-08",
    },
}
```

**Route-map baseline pattern** (`tests/architecture/graph_baseline.py` lines 85-103):
```python
("investigate", "route_after_investigate"): {
    "final_response": "final_response",
    "clarification_gate": "clarification_gate",
    "rag_context_build": "rag_context_build",
    "recommendation_generation": "generate_recommendation",
},
("rag_context_build", "route_after_rag_context"): {
    "recommendation_generation": "generate_recommendation",
    "clarification_gate": "clarification_gate",
    "final_response": "final_response",
},
("generate_recommendation", "route_after_recommendation"): {
    "claim_verify": "claim_verify",
    "final_response": "final_response",
},
```

**AST helper pattern** (`tests/architecture/graph_baseline.py` lines 143-199):
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

**Assertions to adapt** (`tests/architecture/test_canonical_graph_baseline.py` lines 63-151):
```python
def test_migration_mode_maps_every_active_legacy_node_to_target() -> None:
    active_legacy_nodes = CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES

    assert active_legacy_nodes == frozenset(MIGRATION_MODE_LEGACY_NODE_MAP)
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {
        "generate_recommendation": {
            "target": "recommendation_generation",
            "delete_phase": "Phase 56",
            "owner_requirement": "CAGM-07",
        },
        "assess_risk_and_approval": {
            "target": "risk_gate",
            "delete_phase": "Phase 57",
            "owner_requirement": "CAGM-08",
        },
    }
```

**Apply:** after cutover, `CURRENT_ACTIVE_GRAPH_NODES_BASELINE` should include `recommendation_generation` and exclude `generate_recommendation`; `MIGRATION_MODE_LEGACY_NODE_MAP` should retain only `assess_risk_and_approval` for active legacy runtime.

### Vocabulary and Projection Tests

**Applies to:** `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`

**Reason-code test pattern** (`tests/agent/test_graph_vocabulary.py` lines 13-24 and 175-194):
```python
PHASE55_MEMORY_ALIAS_REASON_CODES = {
    "PHASE_55_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
}

def test_phase55_retained_memory_aliases_are_compatibility_only_with_delete_phase(name: str) -> None:
    entry = graph_vocabulary_entry(name, kind="node")
    projected = project_trace_step_for_contract({"node": name, "status": "completed"})

    assert entry is not None
    assert entry.target_name == "memory_context_load"
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert PHASE55_MEMORY_ALIAS_REASON_CODES <= set(entry.reason_codes)
    assert projected["implementation_node"] == name
    assert projected["target_node"] == "memory_context_load"
```

**Unknown passthrough/preserve fields pattern** (`tests/agent/test_graph_vocabulary.py` lines 274-304):
```python
projected = project_trace_step_for_contract(original)

assert projected["node"] == "extract_slots"
assert projected["status"] == "completed"
assert projected["latency_ms"] == 12
assert projected["metrics_json"] == {"slot_resolution_gate": True}
assert projected["implementation_node"] == "extract_slots"
assert projected["target_node"] == "slot_resolution_gate"
assert projected["target_graph_status"] == "compatibility_alias"
assert projected["target_graph_runnable"] is True
assert projected is not original
```

**Trace summary projection pattern** (`tests/agent/test_trace.py` lines 204-249):
```python
assert summary["nodes_executed"] == [
    "long_term_memory_retrieve",
    "reviewed_memory_context_retrieve",
    "memory_context_load",
]
assert summary["target_nodes_executed"] == [
    "memory_context_load",
    "memory_context_load",
    "memory_context_load",
]
assert summary["graph_projection"]["steps"] == [
    {
        "implementation_node": "long_term_memory_retrieve",
        "target_node": "memory_context_load",
        "target_graph_status": "compatibility_alias",
        "target_graph_runnable": True,
    },
```

**Trace API target projection pattern** (`tests/test_trace_api.py` lines 317-394):
```python
@pytest.mark.parametrize(
    ("node_name", "target_node"),
    [
        ("long_term_memory_retrieve", "memory_context_load"),
        ("reviewed_memory_context_retrieve", "memory_context_load"),
        ("memory_context_load", "memory_context_load"),
    ],
)
def test_build_timeline_projects_phase55_memory_node_identities(node_name: str, target_node: str):
    now = datetime.now(UTC)
    repo = TraceRepository(SimpleNamespace())

    timeline = repo.build_timeline(
        steps=[
            SimpleNamespace(
                started_at=now,
                node_name=node_name,
                status="completed",
                tool_name=None,
                latency_ms=5,
                provider_latency_ms=None,
            )
        ],
        approvals=[],
        approval_steps=[],
        drafts=[],
    )

    assert timeline[0]["detail"]["node_name"] == node_name
    assert timeline[0]["detail"]["target_node"] == target_node
```

**SSE target projection pattern** (`tests/test_agent_runs_api.py` lines 972-1028):
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

### RAG/Claim Tests

**Applies to:** `tests/agent/test_rag_context_routing.py`, `tests/agent/rag_context/test_routing.py`, `tests/knowledge/test_verified_evidence_package.py`, `tests/knowledge/test_claim_verification_bundle.py`

**RAG router matrix** (`tests/agent/test_rag_context_routing.py` lines 13-96):
```python
@pytest.mark.parametrize("status", RAG_CONTEXT_STATUSES)
def test_route_after_rag_context_is_total_over_all_statuses(status: str) -> None:
    from src.agent.routing import route_after_rag_context

    state: dict[str, Any] = {
        "rag_context_status": status,
        "verified_evidence_package": {"status": status},
        "primary_intent": "policy_qa",
        "requested_operation": "advise",
        "risk_tier": "low",
        "evidence_policy": {"evidence_required": status != "not_required"},
    }
    if status == "partial":
        state["verified_evidence_package"] = {"status": status, "evidence_map": {"policy#1": {}}}

    route = route_after_rag_context(state)

    assert route in FINITE_RAG_CONTEXT_ROUTES
```

**Claim route matrix and negative/action-positive pattern** (`tests/agent/rag_context/test_routing.py` lines 182-337):
```python
def test_route_after_recommendation_sends_claims_and_actions_to_claim_verify() -> None:
    """APF-14: material claims and action recommendations must pass through claim_verify."""
    from src.agent.routing import route_after_recommendation

    assert route_after_recommendation({"material_claims": [{"claim_id": "claim-policy"}]}) == "claim_verify"
    assert route_after_recommendation({"proposed_action": {"type": "create_compensation_review"}}) == "claim_verify"
```

```python
def test_route_after_claim_verify_sends_verified_action_recommendation_to_risk_gate() -> None:
    """APF-14: verified actionable drafts must still bind action authority through risk/snapshot."""
    from src.agent.routing import route_after_claim_verify

    route = route_after_claim_verify(
        {
            "recommendation_draft": {
                "recommended_action": "issue_coupon",
                "risk_level": "low",
                "evidence_refs": [{"doc_key": "policy_refund_timeout", "chunk_id": "chunk_001"}],
            },
            "claim_verification_bundle": {
                "overall_status": "verified",
                "route": "continue",
                "claim_results": [
                    {
                        "claim_id": "claim-action-1",
                        "claim_type": "action_recommendation",
                        "support_status": "supported",
                        "allows_action_recommendation": True,
                    }
                ],
                "blocked_claims": [],
                "safe_support_refs": [],
                "reason_codes": [],
            },
        }
    )

    assert route == "assess_risk_and_approval"
```

**Strict package tests** (`tests/knowledge/test_verified_evidence_package.py` lines 97-180):
```python
def test_verified_evidence_package_accepts_exact_rag_context_status_literals() -> None:
    """APF-13: target package status is pinned to the contract spellings."""
    statuses = {
        "not_required",
        "verified",
        "partial",
        "no_evidence",
        "unauthorized",
        "stale",
        "conflict",
        "invalid_hash",
        "invalid_scope",
        "build_error",
    }
```

```python
with pytest.raises(ValidationError):
    VerifiedEvidencePackageV1(
        package_id="pkg-unsafe",
        status="hash_warning",
        ...
    )
```

**Strict claim/action authority tests** (`tests/knowledge/test_claim_verification_bundle.py` lines 80-99, 176-204, and 483-508):
```python
claim = MaterialClaimV1(
    claim_id="claim-action",
    claim_text="Issue a compensation recommendation only after verified refund facts.",
    claim_type="action_recommendation",
    cited_evidence_ids=[ref.evidence_id],
    business_fact_refs=[business_ref],
    risk_hints=["refund_compensation"],
    generated_from_step="recommendation_generation",
)
```

```python
assert bundle.overall_status == "blocked"
assert bundle.route == "final_response"
assert bundle.blocked_claims == ["claim-business"]
assert "business_fact_ref_required" in bundle.reason_codes
assert bundle.claim_results[0].support_status == "unsupported"
```

```python
assert bundle.route == "final_response"
assert bundle.blocked_claims == ["claim-action-policy-only"]
assert bundle.safe_support_refs == []
assert "dependency_claims_required" in bundle.reason_codes
assert bundle.claim_results[0].allows_action_recommendation is False
```

### Generation Node Tests

**Applies to:** `tests/agent/test_nodes/test_generate_recommendation.py`, inferred `tests/agent/test_nodes/test_recommendation_generation.py`

**Static ownership guard** (`tests/agent/test_nodes/test_generate_recommendation.py` lines 566-585):
```python
def test_generate_recommendation_static_boundary_does_not_own_verification():
    source = inspect.getsource(generate_recommendation_module)

    forbidden_generation_owners = (
        "ContextBuilder",
        "MaterialClaimVerifier",
        "PolicyKnowledgeService",
        "PolicyRetrievalEngine",
        "RagContextBudget",
        "determine_verification_route",
        "_verify_recommendation_with_shared_kernel",
    )

    for forbidden in forbidden_generation_owners:
        assert forbidden not in source
```

**Canonical claim emission and no legacy fields** (`tests/agent/test_nodes/test_generate_recommendation.py` lines 587-626):
```python
claim = result["material_claims"][0]
assert claim["schema_version"] == "material_claim.v1"
assert claim["claim_type"] == "policy"
assert claim["generated_from_step"] == "recommendation_generation"
assert claim["cited_evidence_ids"] == [evidence.evidence_id]
assert "authority_class" not in claim
assert "source_node" not in claim
assert result["recommendation_draft"]["material_claims"] == result["material_claims"]
```

**Fail-closed no verifier-owned outputs** (`tests/agent/test_nodes/test_generate_recommendation.py` lines 630-701):
```python
assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
assert result["recommendation_draft"]["evidence_refs"] == []
assert result["material_claims"] == []
...
assert "proposed_action" not in result
assert "claim_verification_bundle" not in result
assert "safe_support_refs" not in result
```

**Canonical wrapper test analog** (`tests/agent/test_memory_context_load.py` lines 123-161 and 258-298):
```python
metrics = result["llm_outputs"]["memory_context_load"]
assert metrics["source"] == "reviewed_memory"
assert metrics["authority_class"] == "contextual_only"
assert "long_term_memory_retrieve" not in result["llm_outputs"]
assert "reviewed_memory_context_retrieve" not in result["llm_outputs"]
assert result["trace_steps"][-1]["node"] == "memory_context_load"
assert result["trace_steps"][-1]["metrics_json"] == metrics
```

```python
result = await module.long_term_memory_retrieve(_state(), {"configurable": {}})

assert calls
assert result["llm_outputs"]["memory_context_load"]["authority_class"] == "contextual_only"
assert result["llm_outputs"]["long_term_memory_retrieve"] == {
    "source": "reviewed_memory",
    "continuity_claimed": True,
    "retrieved": 2,
    "profile_count": 1,
    "case_count": 1,
    "fallback_reason": None,
}
```

### API Safe Projection Tests

**Applies to:** `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`

**Trace summary leak guard** (`tests/agent/test_trace.py` lines 738-802):
```python
assert set(summary["rag_claim_summary"]) == RAG_CLAIM_SUMMARY_KEYS
assert summary["rag_claim_summary"] == {
    "schema_version": "rag_claim_summary.v1",
    "rag_context_status": "verified",
    "verified_evidence_count": 1,
    "rejected_candidate_count": 2,
    "stale_ref_count": 1,
    "conflict_ref_count": 1,
    "claim_verification_status": "blocked",
    "blocked_claim_count": 1,
    "safe_support_ref_count": 1,
}
serialized = json.dumps(summary, ensure_ascii=False)
for forbidden in (
    "verified_evidence_package",
    "claim_verification_bundle",
    "RAW_SEMANTIC_SHOULD_NOT_LEAK",
    "DEBUG_PROJECTION_SHOULD_NOT_LEAK",
    "VERIFIER_PROJECTION_SHOULD_NOT_LEAK",
    "SOURCE_BLOCK_SHOULD_NOT_LEAK",
    "OCR_SHOULD_NOT_LEAK",
    candidate_only_ref["evidence_id"],
):
    assert forbidden not in serialized
```

**Trace API leak guard** (`tests/test_trace_api.py` lines 195-233 and 622-662):
```python
assert set(summary) == RAG_CLAIM_SUMMARY_KEYS
assert summary == {
    "schema_version": "rag_claim_summary.v1",
    "rag_context_status": "verified",
    "verified_evidence_count": 1,
    "rejected_candidate_count": 2,
    "stale_ref_count": 1,
    "conflict_ref_count": 1,
    "claim_verification_status": "blocked",
    "blocked_claim_count": 1,
    "safe_support_ref_count": 1,
}
for forbidden in (
    "verified_evidence_package",
    "debug_projection",
    "verifier_projection",
    "RAW_SEMANTIC_SHOULD_NOT_LEAK",
    "candidate-only",
):
    assert forbidden not in response.text
```

**SSE RAG/claim summary leak guard** (`tests/test_agent_runs_api.py` lines 1031-1076):
```python
claim_event = next(event for event in events if event.get("node_name") == "claim_verify")
summary = claim_event["payload"]["rag_claim_summary"]

assert set(summary) == RAG_CLAIM_SUMMARY_KEYS
assert summary == {
    "schema_version": "rag_claim_summary.v1",
    "rag_context_status": "verified",
    "verified_evidence_count": 1,
    "rejected_candidate_count": 1,
    "stale_ref_count": 0,
    "conflict_ref_count": 0,
    "claim_verification_status": "blocked",
    "blocked_claim_count": 1,
    "safe_support_ref_count": 1,
}
serialized = json.dumps(claim_event["payload"], ensure_ascii=False)
for forbidden in (
    "verified_evidence_package",
    "claim_verification_bundle",
    "RAW_SEMANTIC_SHOULD_NOT_LEAK",
    "DEBUG_PROJECTION_SHOULD_NOT_LEAK",
    "VERIFIER_PROJECTION_SHOULD_NOT_LEAK",
    "candidate-only",
):
    assert forbidden not in serialized
```

### Frontend, Eval, Docs, Debt Closeout

**Applies to:** `frontend/src/components/timeline/TimelineStep.tsx`, `scripts/eval_agent.py`, `scripts/diagnose_latency.py`, `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`

**Frontend local node label pattern** (`frontend/src/components/timeline/TimelineStep.tsx` lines 5-15 and 56-81):
```tsx
const NODE_MESSAGES: Record<string, string> = {
  receive_request: '正在接收请求',
  classify_intent: '正在识别意图',
  extract_slots: '正在提取关键信息',
  investigate: '正在调查订单和规则',
  generate_recommendation: '正在生成处理建议',
  assess_risk_and_approval: '正在判断风险等级',
  approval_gate: '需要审批，等待人工决策',
  execute_action: '正在执行操作',
  final_response: '已完成',
}
```

```tsx
export function TimelineStep({ step, isLast }: TimelineStepProps) {
  const nodeName = step.node_name ?? ''
  const message = step.message || (nodeName ? NODE_MESSAGES[nodeName] : '') || `正在执行 ${step.event_type}`
```

**Eval fake LLM and expected node pattern** (`scripts/eval_agent.py` lines 416-439 and 504-524):
```python
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes import extract_slots as extract_slots_module
from src.agent.nodes import generate_recommendation as generate_recommendation_module

patches = [
    patch.object(classify_intent_module, "_get_llm", lambda: fake_llms["classify_intent"]),
    patch.object(extract_slots_module, "_get_llm", lambda: fake_llms["extract_slots"]),
    patch.object(generate_recommendation_module, "_get_llm", lambda: fake_llms["generate_recommendation"]),
    patch.object(assess_risk_module, "_get_llm", lambda: fake_llms["assess_risk"]),
]
```

```python
nodes = ["receive_request", "classify_intent"]
if case.get("expected_intent") != "policy_qa":
    nodes.extend(["session_memory_load", "extract_slots"])
nodes.extend(["investigate", "generate_recommendation", "assess_risk_and_approval"])
```

**Current-source docs pattern** (`docs/current-langgraph-architecture.md` lines 1-6 and 88-107):
```markdown
# 当前 LangGraph Graph/Node 架构图

> 本图只根据当前仓库源码绘制，主要依据 `src/agent/graph.py` 的 `build_graph()` 节点/边定义，以及 `src/agent/routing.py` 和 `src/agent/graph.py` 中的条件路由函数。未把 planning 文档、README 描述或测试断言当作已实现事实。
```

```markdown
| `generate_recommendation` active node | `recommendation_generation` / Phase 56 CAGM-07 | Recommendation generation naming/claim status alignment is Phase 56-owned | Route maps use `recommendation_generation` route value to current `generate_recommendation` destination | Architecture baseline keeps this as active legacy migration row | Phase 56 |
| `assess_risk_and_approval` active node | `risk_gate` / Phase 57 CAGM-08 | Risk/approval canonicalization is Phase 57-owned | `assess_risk_and_approval -> risk_gate`, status `compatibility_alias` | Architecture baseline keeps this as active legacy migration row | Phase 57 |
```

**Architecture debt entry pattern** (`.planning/ARCHITECTURE-DEBT.md` lines 433-464):
```markdown
## Phase 55 Plan 03 — `memory_context_load` runtime vocabulary/API/docs closeout ✅已修复验证

**问题 / 根因**
- Phase 55-02 已把 active graph/router 切到 `memory_context_load`，但 vocabulary、trace/API/SSE projection、当前源码架构图和债务台账如果继续把 `long_term_memory_retrieve` 或 `reviewed_memory_context_retrieve` 读成 runtime owner，会让历史 trace/import/test compatibility 与当前 runtime authority 混在一起。
- `reviewed_memory_context_retrieve` 是 helper/service test surface，不应在 Phase 55 后成为第二个 runtime graph owner。
```

## Shared Patterns

### Authentication And API Authorization
**Source:** `src/api/routers/agent_runs.py` lines 31-39 and 101-107
**Apply to:** API route edits in `src/api/routers/agent_runs.py` and `src/api/routers/traces.py`
```python
from src.api.schemas.agent_runs import CreateRunRequest, RunStatusResponse
from src.api.schemas.common import ApiResponse
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, User
from src.db.session import get_session

@router.post("", response_model=ApiResponse)
async def create_agent_run(
    body: CreateRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
```

### Router Fail-Closed Defaults
**Source:** `src/agent/routing.py` lines 509-550
**Apply to:** all `route_after_*` changes
```python
try:
    route = _route_after_claim_verify(state)
except Exception:
    return "final_response"
if route in _CLAIM_VERIFY_ROUTES:
    return route
return "final_response"
```

### Strict DTO Validation
**Source:** `src/knowledge/schemas.py` lines 126-195
**Apply to:** RAG package and claim bundle changes
```python
class VerifiedEvidencePackageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

```python
class ClaimVerificationBundleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

### Compatibility Projection
**Source:** `src/agent/graph_vocabulary.py` lines 197-207
**Apply to:** trace/API/SSE/frontend display compatibility
```python
projected["implementation_node"] = implementation_node
projected["target_node"] = implementation_node if entry is None else entry.target_name
projected["target_graph_status"] = "unknown_passthrough" if entry is None else entry.status
projected["target_graph_runnable"] = True if entry is None else entry.runnable
```

### Safe RAG/Claim Projection
**Source:** `src/agent/rag_claim_summary.py` lines 159-166
**Apply to:** trace summary, Trace API, Agent Runs SSE payloads
```python
summary = build_rag_claim_summary(payload)
sanitized = {key: value for key, value in payload.items() if key not in _RAG_CLAIM_RAW_PAYLOAD_KEYS}
sanitized.pop("rag_claim_summary", None)
if summary is not None:
    sanitized["rag_claim_summary"] = summary
return sanitized
```

### Approved Verification Entrypoints
**Source:** `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md` lines 22-24
**Apply to:** all PLAN.md verification commands
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_phase22_recommendation_integration.py tests/knowledge/test_facade_integration.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/knowledge src/api tests/architecture tests/agent tests/knowledge tests/test_graph_routing.py tests/test_trace_api.py tests/test_agent_runs_api.py
```

## No Analog Found

None. New `src/agent/nodes/recommendation_generation.py` should copy the Phase 55 canonical wrapper pattern from `src/agent/nodes/memory_context_load.py` and the existing behavior from `src/agent/nodes/generate_recommendation.py`.

## Metadata

**Analog search scope:** `src/agent`, `src/api`, `src/repositories`, `tests/agent`, `tests/architecture`, `tests/knowledge`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, `docs/current-langgraph-architecture.md`, `frontend/src/components/timeline`, `scripts`, `.planning/ARCHITECTURE-DEBT.md`
**Files scanned:** 35 primary files plus repository-wide `rg` references for `generate_recommendation`, `recommendation_generation`, `rag_context_build`, `claim_verify`, `target_node`, and projection helpers.
**Pattern extraction date:** 2026-07-07
