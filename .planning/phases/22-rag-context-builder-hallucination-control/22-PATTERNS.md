# Phase 22: RAG Context Builder + Hallucination Control - Pattern Map

**Mapped:** 2026-06-19
**Files analyzed:** 32
**Analogs found:** 32 / 32

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/rag_context/__init__.py` | config | transform | `src/agent/context/__init__.py` | exact |
| `src/agent/rag_context/schemas.py` | model | transform | `src/knowledge/schemas.py`, `src/tools/contracts.py` | exact |
| `src/agent/rag_context/builder.py` | service | request-response + transform | `src/knowledge/service.py`, `src/agent/context/assembler.py` | exact |
| `src/agent/rag_context/claims.py` | utility | transform | `src/knowledge/citation.py`, `src/agent/routing.py` | role-match |
| `src/agent/rag_context/verifier.py` | service | request-response + transform | `src/knowledge/citation.py`, `src/knowledge/service.py` | role-match |
| `src/agent/rag_context/routing.py` | route | request-response | `src/agent/routing.py`, `src/agent/graph.py` | exact |
| `src/agent/rag_context/metrics.py` | utility | batch + transform | `scripts/eval_rag.py` | role-match |
| `src/knowledge/service.py` | service | request-response | `src/knowledge/service.py` | exact |
| `src/repositories/policy_chunk_repo.py` | repository | CRUD | `src/repositories/policy_chunk_repo.py` | exact |
| `src/knowledge/provenance.py` | model/utility | transform | `src/knowledge/provenance.py` | exact |
| `src/agent/state.py` | model/store | event-driven | `src/agent/state.py` | exact |
| `src/agent/nodes/generate_recommendation.py` | LangGraph node | request-response | `src/agent/nodes/generate_recommendation.py` | exact |
| `src/agent/nodes/final_response.py` | LangGraph node | request-response | `src/agent/nodes/final_response.py` | exact |
| `src/agent/nodes/assess_risk_and_approval.py` | LangGraph node | request-response | `src/agent/nodes/assess_risk_and_approval.py` | exact |
| `src/agent/graph.py` | graph config | event-driven | `src/agent/graph.py` | exact |
| `src/agent/routing.py` | route | request-response | `src/agent/routing.py` | exact |
| `tests/agent/rag_context/test_context_builder.py` | test | request-response + transform | `tests/knowledge/test_service.py`, `tests/knowledge/test_provenance_lookup.py` | exact |
| `tests/agent/rag_context/test_budgeting.py` | test | transform | `tests/agent/context/test_budget.py` | exact |
| `tests/agent/rag_context/test_material_claims.py` | test | transform | `tests/knowledge/test_phase21_boundaries.py`, `tests/agent/test_policy_retrieval_ownership.py` | role-match |
| `tests/agent/rag_context/test_verifier.py` | test | request-response + transform | `tests/knowledge/test_citation_membership.py`, `tests/knowledge/test_service.py` | exact |
| `tests/agent/rag_context/test_authority_boundaries.py` | test | transform | `tests/agent/test_policy_retrieval_ownership.py`, `tests/agent/test_memory_evidence_boundary.py` | exact |
| `tests/agent/rag_context/test_semantic_verifier.py` | test | request-response | `tests/agent/conftest.py`, `tests/agent/test_nodes/test_generate_recommendation.py` | role-match |
| `tests/agent/rag_context/test_routing.py` | test | request-response | `tests/test_graph_routing.py` | exact |
| `tests/agent/rag_context/test_leakage.py` | test | transform | `tests/agent/context/test_assembler.py`, `tests/knowledge/test_phase21_boundaries.py` | exact |
| `tests/agent/test_phase22_recommendation_integration.py` | test | event-driven | `tests/agent/test_nodes/test_generate_recommendation.py` | exact |
| `tests/agent/test_phase22_action_boundary.py` | test | event-driven | `tests/test_graph_routing.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py` | exact |
| `tests/agent/test_phase22_final_response.py` | test | request-response | `tests/agent/test_nodes/test_final_response.py` | exact |
| `tests/knowledge/test_phase22_evidence_validation.py` | test | request-response | `tests/knowledge/test_service.py`, `tests/knowledge/test_provenance_lookup.py` | exact |
| `tests/knowledge/test_phase21_boundaries.py` | test | static + transform | `tests/knowledge/test_phase21_boundaries.py` | exact |
| `tests/test_graph_routing.py` | test | event-driven | `tests/test_graph_routing.py` | exact |
| `evaluation/golden/phase22_hallucination_cases.jsonl` | test fixture | batch | `evaluation/golden/rag_cases.jsonl`, `evaluation/golden/agent_cases.jsonl` | exact |
| `scripts/eval_phase22_hallucination.py` | utility/script | batch | `scripts/eval_rag.py` | exact |

## Pattern Assignments

### `src/agent/rag_context/__init__.py` (config, transform)

**Analog:** `src/agent/context/__init__.py`

**Package export pattern** (lines 1-29):
```python
"""Prompt-safe context assembly boundary."""

from src.agent.context.assembler import ContextAssembler
from src.agent.context.budget import PromptAssembly, PromptBlock, TokenBudgetPolicy
...
__all__ = [
    "ContextAssembler",
    "PromptAssembly",
    "PromptBlock",
    "TokenBudgetPolicy",
    ...
]
```

Apply the same explicit import plus `__all__` style for `RagContextBundle`, `MaterialClaim`, verifier result DTOs, and route/metric DTOs. Keep exports stable for tests.

### `src/agent/rag_context/schemas.py` (model, transform)

**Analogs:** `src/knowledge/schemas.py`, `src/tools/contracts.py`

**Canonical evidence shape to consume, not modify** (`src/knowledge/schemas.py` lines 31-69):
```python
class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)
```

**Strict DTO pattern** (`src/tools/contracts.py` lines 13-17, 58-72):
```python
class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["tool_context.v2"] = "tool_context.v2"
    tenant_id: str

class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"

class ToolResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["tool_result.v2"] = "tool_result.v2"
```

Use Pydantic `BaseModel` + `ConfigDict(extra="forbid")` for all Phase 22 DTOs. Do not add `MaterialClaim`, business refs, source-block, OCR, provenance, or verifier fields to `EvidenceRefV1`.

### `src/agent/rag_context/builder.py` (service, request-response + transform)

**Analogs:** `src/knowledge/service.py`, `src/repositories/policy_chunk_repo.py`, `src/agent/context/assembler.py`, `src/agent/context/budget.py`

**Verified evidence content lookup** (`src/knowledge/service.py` lines 113-148):
```python
async def get_verified_evidence_contents(
    self,
    *,
    tenant_id: str,
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, str]:
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return {}

    key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
    keys = [key for key, count in key_counts.items() if count == 1 and all(key)]
    if not keys:
        return {}
```

**Hash/tenant fail-closed loop** (`src/knowledge/service.py` lines 137-148):
```python
verified: dict[str, str] = {}
for ref in evidence_refs:
    key = (ref.doc_key, ref.chunk_id)
    content = contents.get(key)
    if (
        key_counts.get(key) == 1
        and ref.tenant_id == tenant_id
        and content is not None
        and evidence_text_hash(content) == ref.text_hash
    ):
        verified[ref.evidence_id] = content
return verified
```

**Repository content query** (`src/repositories/policy_chunk_repo.py` lines 32-60):
```python
async def get_contents_by_evidence_keys(
    self,
    tenant_id: UUID,
    keys: list[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    if not keys:
        return {}
    stmt = (
        select(PolicyDocument.doc_key, PolicyChunk.chunk_id, PolicyChunk.content)
        .join(PolicyDocument, and_(PolicyChunk.doc_id == PolicyDocument.id, PolicyDocument.tenant_id == tenant_id))
        .where(PolicyChunk.tenant_id == tenant_id, tuple_(PolicyDocument.doc_key, PolicyChunk.chunk_id).in_(keys))
    )
```

**Prompt-safe assembly handoff** (`src/agent/context/assembler.py` lines 47-105):
```python
blocks: list[PromptBlock] = [
    PromptBlock("system_prompt", system_prompt, priority=100, protected=True),
]
...
policy_block = project_policy_refs_for_prompt(verified_policy_snippets)
if policy_block:
    blocks.append(PromptBlock("policy_refs", policy_block, priority=85, protected=True))
...
blocks.append(PromptBlock("current_user_message", current_user_message, priority=100, protected=True))
return self.budget_policy.apply(blocks)
```

**Budget behavior to reuse for protected citation metadata** (`src/agent/context/budget.py` lines 95-114, 139-159):
```python
class TokenBudgetPolicy:
    def apply(self, blocks: list[PromptBlock] | tuple[PromptBlock, ...]) -> PromptAssembly:
        normalized = [block.normalized() for block in blocks if block.content.strip()]
        kept = list(normalized)
        omitted: list[str] = []
        while _total_chars(kept) > self.max_chars:
            candidate_index = _lowest_value_candidate_index(kept)
            if candidate_index is None:
                break
            omitted.append(kept[candidate_index].name)
            kept.pop(candidate_index)
```

Builder should return a bundle with included/truncated/excluded traces and protected citation map metadata. It should call `ContextAssembler` for final prompt assembly rather than building prompt strings by hand.

### `src/agent/rag_context/claims.py` (utility, transform)

**Analogs:** `src/knowledge/citation.py`, `src/agent/routing.py`

**Membership-only helper pattern** (`src/knowledge/citation.py` lines 15-51):
```python
def validate_membership(
    claims: list[dict],
    evidence_refs: list[EvidenceRefV1],
) -> CitationValidationResult:
    present = {ref.evidence_id for ref in evidence_refs}
    claim_results: list[ClaimResult] = []
    all_member = True
    ...
    return CitationValidationResult(
        validator_version=CITATION_VALIDATOR_VERSION,
        claim_results=claim_results,
        is_valid=all_member and len(claim_results) > 0,
    )
```

**Dependency-map validation pattern to extend** (`src/agent/routing.py` lines 276-303):
```python
def _valid_claim_dependency_map(claim_dependency_map: Any) -> bool:
    if not isinstance(claim_dependency_map, list) or not claim_dependency_map:
        return False
    for entry in claim_dependency_map:
        if not isinstance(entry, dict):
            return False
        if not isinstance(entry.get("claim_id"), str):
            return False
        refs = entry.get("depends_on_refs")
        if not isinstance(refs, list):
            return False
```

Material claim normalization should extend this state-level dependency concept instead of inventing an incompatible dependency model.

### `src/agent/rag_context/verifier.py` (service, request-response + transform)

**Analogs:** `src/knowledge/citation.py`, `src/knowledge/service.py`, `tests/agent/conftest.py`

**Do not confuse membership with support** (`tests/knowledge/test_citation_membership.py` lines 58-68):
```python
def test_membership_does_not_infer_semantic_support() -> None:
    evidence = make_evidence_ref(text="This evidence discusses refund timing only.")
    result = validate_membership(
        [claim(text="The merchant receives a free vacation.", cited=[evidence.evidence_id])],
        [evidence],
    )
    assert result.is_valid is True
    assert result.claim_results[0].is_member is True
```

**Deterministic fake provider shape** (`tests/agent/conftest.py` lines 11-35):
```python
class FakeLLM:
    def __init__(self, response_dict: dict[str, Any]):
        self._response = response_dict

    def with_structured_output(self, schema):
        fake = self
        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                if issubclass(schema, BaseModel):
                    return schema.model_validate(fake._response)
                return fake._response
        return _Wrapper()
```

Verifier should expose Level 1/2 deterministic checks without live model calls. Level 3 provider failures, malformed outputs, timeouts, and budget overflow should return non-allow results, not raise into an allow path.

### `src/agent/rag_context/routing.py` (route, request-response)

**Analogs:** `src/agent/routing.py`, `src/agent/graph.py`

**Total fail-closed route wrapper** (`src/agent/routing.py` lines 142-150):
```python
def route_after_investigate(state: AgentState) -> str:
    try:
        route = _route_after_investigate(state)
    except Exception:
        return "final_response"
    if route in _INVESTIGATE_ROUTES:
        return route
    return "final_response"
```

**Permission dependency fail-closed behavior** (`src/agent/routing.py` lines 249-273):
```python
def _denial_blocks_required_claims(... ) -> bool:
    if not denied_resources:
        return False
    if not _valid_claim_dependency_map(claim_dependency_map):
        return True
    ...
    return not (has_independent_facts or has_independent_policy_evidence)
```

**Action boundary route precedent** (`src/agent/graph.py` lines 53-66):
```python
def route_after_risk(state: AgentState) -> str:
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed:
        return "final_response"
    if not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    if risk.get("approval_required"):
        return "approval_gate"
    return "final_response"
```

New verifier routing must be deterministic, total, and model-independent. Include explicit route constants for allow, insufficient/refusal/final response, manual review, and `regenerate_route` without implementing an auto-regeneration loop.

### `src/agent/rag_context/metrics.py` and `scripts/eval_phase22_hallucination.py` (utility, batch)

**Analog:** `scripts/eval_rag.py`

**CLI and JSONL load pattern** (`scripts/eval_rag.py` lines 53-69):
```python
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG Hit@5 Evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET, help="Path to JSONL golden set")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Minimum accepted score")
    return parser

def _load_cases(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
```

**Scoring report pattern** (`scripts/eval_rag.py` lines 172-202):
```python
return {
    "eval_type": "rag",
    "generated_at": datetime.now(UTC).isoformat(),
    "status": status,
    "thresholds": {"hit_at_5": threshold, "fallback_accuracy": threshold},
    "metrics": {
        "hit_at_5": hit_at_5,
        "fallback_accuracy": fallback_acc,
        "total_cases": total_cases,
    },
    "per_category": _finalize_category_rates(per_category),
    "failed_cases": failed_cases,
}
```

**Main fail gate pattern** (`scripts/eval_rag.py` lines 332-364):
```python
try:
    report = await run_rag_eval(...)
except FileNotFoundError:
    parser.error(f"golden set not found: {args.golden_set}")
...
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
if report["status"] == "fail":
    sys.exit(1)
```

Phase 22 eval script should be deterministic and local. Required blocking metrics: claim/citation support accuracy, route accuracy, unsafe answer rate, business hallucination rate, leakage count, Level 3 trigger rate, timeout rate, and fail-closed rate.

### `src/knowledge/service.py` (service, request-response)

**Analog:** same file.

Extend the `PolicyRetriever` protocol using the existing method style (`src/knowledge/service.py` lines 26-49). Preserve the fail-closed return style from `get_verified_evidence_contents` and `get_verified_evidence_provenance` (lines 113-210). New latest/current-version metadata lookup should return empty or typed exclusions on malformed tenant, duplicate key, repository error, wrong tenant, hash mismatch, and stale/latest-version mismatch.

### `src/repositories/policy_chunk_repo.py` (repository, CRUD)

**Analog:** same file.

Copy SQLAlchemy async query style from `get_contents_by_evidence_keys` (lines 32-60) and `get_provenance_by_evidence_keys` (lines 62-132). For latest/current policy version checks, query through `PolicyDocument` joined to `PolicyChunk`, keep tenant predicates on both tables, and dedupe ambiguous `(doc_key, chunk_id)` rows with `Counter` before returning data.

### `src/knowledge/provenance.py` (model/utility, transform)

**Analog:** same file.

**Internal-only provenance DTOs and sanitization** (lines 53-87, 103-138):
```python
class SourceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_block_id: str
    block_index: int
    block_type: str
    page_number: int | None = None
    bbox: dict[str, Any] = Field(default_factory=dict)
    table: dict[str, Any] = Field(default_factory=dict)
    parser: dict[str, Any] = Field(default_factory=dict)
    ocr: dict[str, Any] = Field(default_factory=dict)

def _safe_value(value: Any, *, allowed_keys: set[str] | None = None) -> Any:
    if isinstance(value, Mapping):
        ...
        if normalized in _FORBIDDEN_KEYS:
            continue
```

If Phase 22 adds risk labels from provenance, expose only prompt-safe labels such as OCR/provenance availability. Raw source-block IDs, bbox/table internals, parser dumps, and raw OCR metadata stay debug-only.

### `src/agent/state.py` (model/store, event-driven)

**Analog:** same file.

**State contract pattern** (lines 48-123):
```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    ...
    claim_dependency_map: list[dict[str, Any]] | None
    ...
    final_response: str | None
    tool_results: list[dict[str, Any]] | None
    llm_outputs: dict[str, Any] | None
```

Add only redacted Phase 22 state fields, e.g. verifier route/status/reason codes/safe refs/metrics. Do not store raw verifier prompts, private reasoning, unbounded policy text, raw tool payloads, raw provenance, or OCR/parser internals.

### `src/agent/nodes/generate_recommendation.py` (LangGraph node, request-response)

**Analog:** same file.

**Current node-local evidence validation to centralize** (lines 152-178):
```python
evidence_items = list(_retrieval_data(state).get("evidence_refs") or [])
evidence_models = [EvidenceRefV1(**item) for item in evidence_items]
text_by_evidence_id: dict[str, str] = {}
session = ((config or {}).get("configurable") or {}).get("session")
...
text_by_evidence_id = await PolicyKnowledgeService(
    PolicyRetrievalEngine(session)
).get_verified_evidence_contents(
    tenant_id=state["tenant_id"],
    evidence_refs=evidence_models,
)
```

**Structured output + membership-only validation currently present** (lines 180-239):
```python
structured_llm = _get_llm().with_structured_output(RecommendationDraft)
...
validation = validate_membership(claims, evidence_models)
if not validation.is_valid:
    ...
draft["citation_validation"] = validation.model_dump()
validated_refs = _validated_evidence_refs(cited_evidence_ids, evidence_by_id)
```

Replace this local re-fetch/membership-only path with the shared RAG context builder + verifier. Keep the existing `ContextAssembler` handoff from `_assemble_recommendation_prompt` (lines 294-322) and existing expected-error fallback style (lines 256-291).

### `src/agent/graph.py` and `src/agent/routing.py` (graph config/route, event-driven)

**Analog:** `src/agent/graph.py`

**Current direct edge to replace** (`src/agent/graph.py` line 168):
```python
builder.add_edge("generate_recommendation", "assess_risk_and_approval")
```

**Conditional edge pattern** (`src/agent/graph.py` lines 158-176):
```python
builder.add_conditional_edges(
    "investigate",
    route_after_investigate,
    {
        "final_response": "final_response",
        "clarification_gate": "clarification_gate",
        "recommendation_generation": "generate_recommendation",
    },
)
...
builder.add_conditional_edges(
    "assess_risk_and_approval",
    route_after_risk,
    {
        "assess_risk_and_approval": "assess_risk_and_approval",
        "approval_gate": "approval_gate",
        "final_response": "final_response",
    },
)
```

Add a conditional edge after `generate_recommendation` so non-allow verifier outcomes go to `final_response` and only allow routes continue to `assess_risk_and_approval`.

### `src/agent/nodes/final_response.py` (LangGraph node, request-response)

**Analog:** same file.

**Deterministic safe branches** (lines 184-246):
```python
async def final_response(state: AgentState) -> dict:
    started_at = _now_iso()
    draft = state.get("recommendation_draft") or {}
    ...
    if isinstance(clarification_request, dict):
        ...
        return {"final_response": response_text, "llm_outputs": {...}}
    if draft.get("recommended_action") == "retrieval_error":
        return {"final_response": _retrieval_error_response(draft), ...}
    if draft.get("recommended_action") in {"insufficient_evidence", "citation_invalid"}:
        response_text = _insufficient_response_with_context(draft, state.get("business_context") or {})
```

**Final citation projection pattern** (lines 247-266):
```python
response_text = _completed_response(draft, state.get("risk_assessment") or {})
...
"evidence_citations": [
    f"{ref.get('doc_key')} / {ref.get('chunk_id')}" for ref in draft.get("evidence_refs") or []
],
"final_status": "completed",
```

Add verifier/manual-review/refusal/insufficient branches with safe reason categories only. Never include verifier prompts/traces, raw provenance, hashes, raw tool data, or unbounded policy text.

### `src/agent/nodes/assess_risk_and_approval.py` (LangGraph node, request-response)

**Analog:** same file.

**No-action recommendations never produce proposed actions** (lines 47, 419-425):
```python
NO_ACTION_RECOMMENDATIONS = {"insufficient_evidence", "citation_invalid", "retrieval_error"}
...
if draft.get("recommended_action") in NO_ACTION_RECOMMENDATIONS:
    assessment = _fallback_risk(draft, context, rules)
    return {
        "risk_assessment": assessment,
        "proposed_action": None,
        "trace_steps": ...,
    }
```

**Snapshot fail-closed behavior** (lines 270-377):
```python
async def _attach_snapshot_binding(... ) -> dict[str, Any]:
    if not result.get("proposed_action"):
        return result
    try:
        ...
    except (ActionSafetySnapshotPersistenceError, TypeError, ValueError, ValidationError) as exc:
        safe_assessment = {
            **assessment,
            "approval_required": False,
            "risk_level": "manual_review",
            "risk_reason": f"Action safety snapshot could not be verified: {exc}",
        }
        return {
            **result,
            "risk_assessment": safe_assessment,
            "proposed_action": None,
            "auto_allowed": False,
            "safety_snapshot_verified": False,
            "final_response": "...",
        }
```

If direct node calls can receive a non-allow verifier status, add a defensive no-action guard here as well as the graph route.

### Wave 0 `tests/agent/rag_context/*` (tests, request-response/transform)

**Analogs:** `tests/knowledge/test_service.py`, `tests/knowledge/test_provenance_lookup.py`, `tests/agent/context/test_budget.py`, `tests/agent/context/test_assembler.py`, `tests/knowledge/test_citation_membership.py`

**Evidence validation tests** (`tests/knowledge/test_service.py` lines 94-146):
```python
@pytest.mark.asyncio
async def test_verified_evidence_contents_rechecks_hash_and_tenant():
    tenant_id = str(uuid4())
    valid = _evidence(tenant_id=tenant_id, text="...")
    wrong_hash = _evidence(tenant_id=tenant_id, chunk_id="chunk-2", text="old")
    wrong_tenant = _evidence(tenant_id=str(uuid4()), chunk_id="chunk-3", text="cross")
    ...
    assert result == {valid.evidence_id: "..."}
```

**Provenance safe lookup tests** (`tests/knowledge/test_provenance_lookup.py` lines 116-147, 149-172):
```python
result = await service.get_verified_evidence_provenance(...)
assert result == {evidence.evidence_id: provenance}
...
result = await service.get_verified_evidence_provenance(... wrong_hash ...)
assert result == {}
get_provenance.assert_not_awaited()
```

**Budget tests** (`tests/agent/context/test_budget.py` lines 10-31, 33-59):
```python
def test_token_budget_preserves_protected_blocks():
    policy = TokenBudgetPolicy(max_chars=220)
    blocks = [
        _block("system_prompt", "...", priority=100, protected=True),
        _block("policy_refs", "policy-refund:v1:chunk-1", priority=85, protected=True),
    ]
    assembly = policy.apply(blocks)
    assert "policy-refund:v1:chunk-1" in prompt
```

**Leakage sentinels** (`tests/agent/context/test_assembler.py` lines 17-26, 105-166, 168-234):
```python
SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_SOURCE_BLOCK_ID = "refund-policy:policy_pdf:text:0001"
...
assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
assert SHOULD_NOT_APPEAR_SOURCE_BLOCK_ID not in prompt
assert "parser_metadata_json" not in prompt
```

Use the same pytest/fake-service style for `test_context_builder.py`, `test_budgeting.py`, `test_material_claims.py`, `test_verifier.py`, `test_semantic_verifier.py`, `test_routing.py`, and `test_leakage.py`.

### Authority boundary tests

**Files:** `tests/agent/rag_context/test_authority_boundaries.py`, `tests/agent/rag_context/test_material_claims.py`

**Business facts are not policy evidence** (`tests/agent/test_policy_retrieval_ownership.py` lines 243-265):
```python
business_ref = _business_fact_ref(resource_type, resource_id)
with pytest.raises(ValidationError):
    EvidenceRefV1.model_validate(business_ref.model_dump(mode="json"))

result = ToolResultV2(
    status="success",
    policy_evidence_refs=[],
    business_fact_refs=[business_ref],
    ...
)
assert result.policy_evidence_refs == []
assert result.business_fact_refs == [business_ref]
```

**Memory cannot satisfy evidence/action authority** (`tests/agent/test_memory_evidence_boundary.py` lines 168-210, 212-286):
```python
assert final_state["retrieved_evidence"]["evidence_refs"] == []
assert final_state["policy_evidence"] == []
assert final_state.get("evidence_refs", []) == []
assert final_state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
assert final_state.get("approval_result") is None
assert final_state.get("action_result") is None
assert final_state.get("proposed_action") is None
```

Copy this negative-authority structure for policy/business/action claims: wrong authority source must not merely lower confidence; it must produce a non-allow verification result.

### Graph/action/final integration tests

**Files:** `tests/agent/test_phase22_recommendation_integration.py`, `tests/agent/test_phase22_action_boundary.py`, `tests/agent/test_phase22_final_response.py`, `tests/test_graph_routing.py`

**Route totality and fail-closed assertions** (`tests/test_graph_routing.py` lines 106-120, 382-399):
```python
@pytest.mark.parametrize("missing_field", ["action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"])
def test_route_after_risk_fails_closed_when_snapshot_or_action_hash_missing(missing_field):
    state = _risk_route_state()
    state.pop(missing_field)
    assert route_after_risk(state) == "final_response"

@pytest.mark.parametrize("state", [{}, {"retrieval_status": "error"}, {"best_score": 0.1}])
def test_route_after_investigate_totality(state):
    assert route_after_investigate(state) in VALID_INVESTIGATE_KEYS
```

**Recommendation prompt integration style** (`tests/agent/test_nodes/test_generate_recommendation.py` lines 379-434):
```python
assemblies = _spy_context_assembler(monkeypatch)
...
assert assemblies
assert fake_llm.messages == assemblies[-1].to_messages()
prompt = fake_llm.messages[-1]["content"]
assert "Allowed citation objects" in prompt
assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
```

**Final response safe branch tests** (`tests/agent/test_nodes/test_final_response.py` lines 238-338):
```python
result = await final_response(state)
assert result["final_response"] == response_text
assert result["llm_outputs"]["final_response"]["final_status"] == "error"
...
assert "permission_denied" not in result["final_response"]
assert "FORBIDDEN" not in result["final_response"]
assert "approval result" not in result["final_response"]
```

### `tests/knowledge/test_phase21_boundaries.py` (test, static + transform)

**Analog:** same file.

**Static guard pattern** (lines 16-84):
```python
FORBIDDEN_IMPLEMENTATION_PATTERNS = {
    "MaterialClaim": "MaterialClaim",
    "semantic_verifier": "semantic_verifier",
    ...
}
...
for path in _implementation_python_files():
    source = path.read_text(encoding="utf-8")
    for label, pattern in FORBIDDEN_IMPLEMENTATION_PATTERNS.items():
        if pattern in source:
            violations.append(f"{relative}: {label}")
assert violations == []
```

Phase 22 will intentionally introduce `MaterialClaim` and verifier files, so update this guard rather than deleting it. Preserve the parts that still forbid Phase 23/RAG-5 search backend/rerank/query rewrite and Phase 17 external execution scope creep.

**Evidence identity guard** (lines 112-130):
```python
fields = set(EvidenceRefV1.model_fields)
assert fields == {
    "schema_version", "tenant_id", "evidence_id", "doc_key", "chunk_id",
    "policy_version", "text_hash", "retrieved_at", "retrieval_config_version",
    "score", "rank",
}
assert fields.isdisjoint(PROVENANCE_AUTHORITY_FIELD_NAMES)
```

Keep or strengthen this exact assertion.

### `evaluation/golden/phase22_hallucination_cases.jsonl` (test fixture, batch)

**Analogs:** `evaluation/golden/rag_cases.jsonl`, `evaluation/golden/agent_cases.jsonl`, `evaluation/golden/MATCHING_RULES.md`

**JSONL shape** (`evaluation/golden/rag_cases.jsonl` lines 1-2):
```json
{"query": "...", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
{"query": "...", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_005"], "category": "refund_rule", "difficulty": "medium", "should_fallback": false}
```

**Agent golden shape** (`evaluation/golden/agent_cases.jsonl` lines 1-2):
```json
{"id":"GS-01","category":"normal_policy_qa","query":"...","expected_status":"completed","expected_final_status":"completed","expected_tools":[],"expected_response_contains":["..."],"must_not_contain":["..."]}
```

**Matching rules doc style** (`evaluation/golden/MATCHING_RULES.md` lines 71-80):
```markdown
`expected_response_contains` and `must_not_contain` use substring matching with
these rules:
- Case-insensitive for ASCII characters
- Exact match for Chinese characters
- Whitespace-normalized
```

Phase 22 cases should include explicit expected verifier route/status/reason codes and must-not-contain leakage sentinels.

## Shared Patterns

### Canonical Evidence Identity

**Source:** `src/knowledge/schemas.py` lines 31-69 and `tests/knowledge/test_phase21_boundaries.py` lines 112-130  
**Apply to:** Builder, verifier, action snapshot, final citations, all tests

Evidence identity remains exactly `EvidenceRefV1`. Phase 22 can create separate claim/bundle/verifier DTOs but must not mutate evidence identity.

### Policy Evidence Re-fetch and Fail-Closed Validation

**Source:** `src/knowledge/service.py` lines 113-210  
**Apply to:** `builder.py`, `verifier.py`, `src/knowledge/service.py`, evidence validation tests

Use tenant UUID parsing, duplicate-key rejection, repository lookup, tenant equality, content hash comparison, and empty-result fail-closed behavior. Add latest/current-version checks in this same style.

### Prompt-Safe Projection and Budgeting

**Source:** `src/agent/context/assembler.py` lines 47-105, `src/agent/context/projectors.py` lines 13-92 and 167-177, `src/agent/context/budget.py` lines 95-159  
**Apply to:** `builder.py`, `generate_recommendation.py`, `final_response.py`, leakage tests

Use explicit projectors and protected prompt blocks. Do not pass arbitrary dicts to prompts or stringify raw state.

### Business Authority Boundary

**Source:** `src/tools/contracts.py` lines 58-99, `src/business/adapters.py` lines 208-232, `tests/agent/test_policy_retrieval_ownership.py` lines 243-265  
**Apply to:** `schemas.py`, `verifier.py`, `test_authority_boundaries.py`

`BusinessFactRefV1` and safe `ToolResultV2` summaries are the only business fact authorities. Policy evidence, memory, and model output cannot support a business fact claim.

### Deterministic Routing

**Source:** `src/agent/routing.py` lines 142-190 and `src/agent/graph.py` lines 137-187  
**Apply to:** `rag_context/routing.py`, `src/agent/graph.py`, `tests/agent/rag_context/test_routing.py`, `tests/test_graph_routing.py`

Route functions catch unexpected errors and return safe defaults. Graph routes are conditional edges with explicit target maps. The model never chooses safety routes.

### Action Boundary

**Source:** `src/agent/nodes/assess_risk_and_approval.py` lines 419-425 and 270-377  
**Apply to:** verifier routing, graph integration, action-boundary tests

Non-action recommendations and snapshot verification failures produce no proposed action, no approval route, no action draft, and safe final response state.

### Deterministic Tests and Fakes

**Source:** `tests/agent/conftest.py` lines 11-35, `tests/agent/test_nodes/test_generate_recommendation.py` lines 17-32  
**Apply to:** all Phase 22 verifier/semantic-provider tests

Default tests should patch providers with deterministic fakes. No default test should require live model credentials.

## No Analog Found

No file is completely without an analog. The Level 3 semantic verifier provider abstraction has no exact existing domain implementation, but it has role-match analogs in `tests/agent/conftest.py` fake structured-output providers and the existing LangChain structured-output node patterns in `generate_recommendation.py` and `assess_risk_and_approval.py`.

## Metadata

**Analog search scope:** `src/`, `tests/`, `scripts/`, `evaluation/golden/`  
**Files scanned:** 759  
**Strong analogs read:** 26  
**Pattern extraction date:** 2026-06-19  
**Phase source files:** `22-CONTEXT.md`, `22-RESEARCH.md`, `22-VALIDATION.md`
