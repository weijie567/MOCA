# Phase 33: RAG Context Build and Claim Verification - Pattern Map

**Mapped:** 2026-06-29  
**Files analyzed:** 48  
**Analogs found:** 47 / 48  
**Project constraints applied:** tests must use `uv run pytest ...` or `.venv/bin/pytest ...`; Phase 33 must be split into dependency-ordered small plans, not one large plan.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/knowledge/schemas.py` | model | transform | `src/knowledge/schemas.py` | exact |
| `src/knowledge/service.py` | service | request-response, batch | `src/knowledge/service.py` | exact |
| `src/agent/rag_context/schemas.py` | model | transform | `src/agent/rag_context/schemas.py` | exact |
| `src/agent/rag_context/builder.py` | service/utility | transform | `src/agent/rag_context/builder.py` | exact |
| `src/agent/rag_context/verifier.py` | service/utility | transform | `src/agent/rag_context/verifier.py` | exact |
| `src/agent/rag_context/routing.py` | route | request-response, transform | `src/agent/rag_context/routing.py` | exact |
| `src/agent/rag_context/claims.py` | utility | transform | `src/agent/rag_context/claims.py` | exact |
| `src/agent/rag_context/domain_rules.py` | utility | transform | `src/agent/rag_context/verifier.py` | partial |
| `src/agent/nodes/rag_context_build.py` | node | event-driven state transform | `src/agent/nodes/generate_recommendation.py` + `src/agent/rag_context/builder.py` | role-match |
| `src/agent/nodes/claim_verify.py` | node | event-driven state transform | `src/agent/nodes/generate_recommendation.py` + `src/agent/rag_context/verifier.py` | role-match |
| `src/agent/nodes/generate_recommendation.py` | node | event-driven, request-response | `src/agent/nodes/generate_recommendation.py` | exact |
| `src/agent/nodes/assess_risk_and_approval.py` | node | event-driven | `src/agent/nodes/assess_risk_and_approval.py` | exact |
| `src/agent/nodes/action_draft.py` | node | event-driven | `src/agent/nodes/action_draft.py` | exact |
| `src/agent/nodes/receive_request.py` | node | event-driven reset | `src/agent/nodes/receive_request.py` | exact |
| `src/agent/nodes/final_response.py` | node | event-driven projection | `src/agent/nodes/final_response.py` | exact |
| `src/agent/routing.py` | route | event-driven | `src/agent/routing.py` | exact |
| `src/agent/graph.py` | config | event-driven | `src/agent/graph.py` | exact |
| `src/agent/graph_vocabulary.py` | config/utility | transform | `src/agent/graph_vocabulary.py` | exact |
| `src/agent/state.py` | store/model | stateful transform | `src/agent/state.py` | exact |
| `src/agent/working_state.py` | provider/utility | projection transform | `src/agent/working_state.py` | exact |
| `src/agent/trace.py` | utility | projection transform | `src/agent/trace.py` | exact |
| `src/api/routers/agent_runs.py` | controller | streaming, request-response | `src/api/routers/agent_runs.py` | exact |
| `src/api/routers/traces.py` | controller | request-response | `src/api/routers/traces.py` | exact |
| `src/api/schemas/agent_runs.py` | model | streaming projection | `src/api/schemas/agent_runs.py` | exact |
| `src/repositories/trace_repo.py` | repository | CRUD, projection transform | `src/repositories/trace_repo.py` | exact |
| `tests/knowledge/test_verified_evidence_package.py` | test | transform | `tests/knowledge/test_phase22_evidence_validation.py` | role-match |
| `tests/knowledge/test_claim_verification_bundle.py` | test | transform | `tests/agent/rag_context/test_verifier.py` | role-match |
| `tests/agent/test_nodes/test_rag_context_build.py` | test | event-driven | `tests/agent/rag_context/test_context_builder.py` | role-match |
| `tests/agent/test_nodes/test_claim_verify.py` | test | event-driven | `tests/agent/rag_context/test_verifier.py` | role-match |
| `tests/agent/test_rag_context_routing.py` | test | route | `tests/agent/rag_context/test_routing.py` + `tests/agent/test_graph.py` | role-match |
| `tests/architecture/test_phase33_rag_claim_boundaries.py` | test | static transform | `tests/architecture/test_phase32_static_contract.py` | role-match |
| `tests/agent/rag_context/test_context_builder.py` | test | transform | `tests/agent/rag_context/test_context_builder.py` | exact |
| `tests/agent/rag_context/test_verifier.py` | test | transform | `tests/agent/rag_context/test_verifier.py` | exact |
| `tests/agent/rag_context/test_routing.py` | test | route | `tests/agent/rag_context/test_routing.py` | exact |
| `tests/agent/rag_context/test_material_claims.py` | test | transform | `src/agent/rag_context/claims.py` + existing test file | role-match |
| `tests/agent/rag_context/test_authority_boundaries.py` | test | transform | `tests/agent/rag_context/test_verifier.py` | role-match |
| `tests/agent/rag_context/test_semantic_verifier.py` | test | transform | `src/agent/rag_context/verifier.py` semantic verifier | role-match |
| `tests/agent/rag_context/test_leakage.py` | test | projection transform | `tests/agent/rag_context/test_leakage.py` | exact |
| `tests/agent/test_nodes/test_generate_recommendation.py` | test | event-driven | `tests/agent/test_nodes/test_generate_recommendation.py` | exact |
| `tests/agent/test_nodes/test_assess_risk_and_approval.py` | test | event-driven | `tests/agent/test_nodes/test_assess_risk_and_approval.py` | exact |
| `tests/agent/test_nodes/test_receive_request.py` | test | event-driven reset | `tests/agent/test_nodes/test_receive_request.py` | exact |
| `tests/agent/test_graph.py` | test | graph/config | `tests/agent/test_graph.py` | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform | `tests/agent/test_graph_vocabulary.py` | exact |
| `tests/architecture/test_phase32_static_contract.py` | test | static transform | `tests/architecture/test_phase32_static_contract.py` | exact |
| `tests/architecture/test_action_draft_boundaries.py` | test | static/security | `tests/architecture/test_action_draft_boundaries.py` | exact |
| `tests/agent/test_trace.py` | test | projection transform | `src/agent/trace.py` tests | role-match |
| `tests/test_agent_runs_api.py` | test | request-response/streaming | `src/api/routers/agent_runs.py` tests | role-match |
| `tests/test_trace_api.py` | test | request-response | `src/api/routers/traces.py` tests | role-match |

## Pattern Assignments

### `src/knowledge/schemas.py` (model, transform)

**Analog:** `src/knowledge/schemas.py`

**Imports and strict DTO pattern** (lines 9-15, 31-42):
```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.knowledge.text_hash import evidence_text_hash

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

**Canonical builder/projection pattern** (lines 44-69, 120-133):
```python
@classmethod
def build(..., text: str, retrieved_at: str, retrieval_config_version: str, ...) -> EvidenceRefV1:
    return cls(
        tenant_id=tenant_id,
        evidence_id=f"{doc_key}/{chunk_id}@{policy_version}",
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text_hash=evidence_text_hash(text),
        retrieved_at=retrieved_at,
        retrieval_config_version=retrieval_config_version,
        score=score,
        rank=rank,
    )

def canonical_evidence_projection(refs: list[EvidenceRefV1]) -> list[dict]:
    item = ref.model_dump()
    item.pop("score", None)
```

**Apply to:** add `VerifiedEvidencePackageV1`, `VerifiedEvidenceItemV1`, `ClaimVerificationBundleV1`, claim result DTOs, and status/route literals here or re-export them here. Use `ConfigDict(extra="forbid")` for new public contracts, matching `src/agent/rag_context/schemas.py`.

---

### `src/knowledge/service.py` (service, request-response/batch)

**Analog:** `src/knowledge/service.py`

**Service boundary imports and protocol pattern** (lines 11-27, 32-62):
```python
import asyncio
from collections import Counter
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchRequest, KnowledgeSearchResult
from src.knowledge.text_hash import evidence_text_hash

class PolicyRetriever(Protocol):
    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, Any]]: ...
```

**Search method error handling** (lines 106-171):
```python
async def search(self, request: KnowledgeSearchRequest, context: KnowledgeContext) -> KnowledgeSearchResult:
    merchant_id = request.filters.merchant_id
    merchant_scope = context.merchant_scope
    if merchant_scope is None:
        return self._no_evidence_result()
    if merchant_id is not None and "*" not in merchant_scope and merchant_id not in merchant_scope:
        return self._no_evidence_result()
    try:
        ...
    except asyncio.TimeoutError:
        return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
    except Exception:
        return self._error_result("SEARCH_ERROR", "Failed to search policy evidence", retryable=False)
```

**Canonical validation/exclusion pattern** (lines 298-393):
```python
async def get_verified_evidence_details(
    self,
    *,
    tenant_id: str,
    evidence_refs: list[EvidenceRefV1],
    effective_at: str | None = None,
    merchant_scope: list[str] | None = None,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> VerifiedEvidenceDetailsResult:
    effective_date = _effective_date(effective_at)
    effective_at_malformed = bool(effective_at) and effective_date is None
    try:
        UUID(tenant_id)
    except ValueError:
        return VerifiedEvidenceDetailsResult(
            excluded=[_detail_exclusion(ref, ["tenant_id_malformed"]) for ref in evidence_refs]
        )
    ...
    if evidence_text_hash(row_content) != ref.text_hash:
        reason_codes.append("text_hash_mismatch")
    if current_policy_version != ref.policy_version:
        reason_codes.append("latest_version_invalid")
    ...
    if reason_codes:
        excluded.append(_detail_exclusion(ref, reason_codes))
        continue
```

**Apply to:** implement `build_verified_context(...)` and `verify_claims(...)` as the public Knowledge boundary. Graph nodes should call these service methods, not repositories or one-off retriever calls. Preserve typed fail-closed result objects and reason codes.

---

### `src/agent/rag_context/schemas.py` (model, transform)

**Analog:** `src/agent/rag_context/schemas.py`

**Strict schema and authority enum pattern** (lines 14-45):
```python
class MaterialClaimAuthorityClass(StrEnum):
    POLICY_CLAIM = "policy_claim"
    BUSINESS_FACT_CLAIM = "business_fact_claim"
    ACTION_RECOMMENDATION_CLAIM = "action_recommendation_claim"

class MaterialClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["material_claim.v1"] = "material_claim.v1"
    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    authority_class: MaterialClaimAuthorityClass
    source_node: str = Field(min_length=1)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    dependency_claim_ids: list[str] = Field(default_factory=list)
```

**Projection separation pattern** (lines 90-159):
```python
class RagPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["rag_prompt_context.v1"] = "rag_prompt_context.v1"
    citations: list[PromptCitation] = Field(default_factory=list)
    risk_labels: list[str] = Field(default_factory=list)
    trusted_context: dict[str, str] = Field(default_factory=dict)

class RagContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    citation_map: dict[str, CitationMapEntry] = Field(default_factory=dict)
    prompt_context: RagPromptContext
    verifier_context: RagVerifierContext
    debug_context: RagDebugContext
    final_response_context: RagSafeContext
    memory_context: RagSafeContext
    replay_context: RagSafeContext
    business_fact_context: RagSafeContext
    action_snapshot_context: RagSafeContext
```

**Apply to:** keep compatibility DTOs if needed, but target package/bundle schemas must preserve prompt/verifier/replay/debug separation. Do not add raw source/OCR/verifier prompt/private reasoning to ordinary surfaces.

---

### `src/agent/rag_context/builder.py` and `src/agent/nodes/rag_context_build.py` (service/node, transform/event-driven)

**Analogs:** `src/agent/rag_context/builder.py`, current RAG build call in `src/agent/nodes/generate_recommendation.py`

**Builder orchestration pattern** (lines 47-89):
```python
class ContextBuilder:
    """Validate evidence refs and project them into safe context surfaces."""

    async def build(
        self,
        *,
        candidate_evidence_refs: Sequence[EvidenceRefV1],
        business_fact_refs: Sequence[BusinessFactRefV1],
        trusted_context: Mapping[str, Any],
        risk_hints: Sequence[Mapping[str, Any]] | None = None,
    ) -> RagContextBundle:
        build_input = RagContextBuildInput(...)
        retained_refs, initial_exclusions = _dedupe_candidates(build_input.candidate_evidence_refs)
        contents, validation_exclusions = await self._validated_contents(
            tenant_id=tenant_id,
            refs=retained_refs,
            trusted_context=build_input.trusted_context,
        )
```

**Projection return pattern** (lines 181-213):
```python
return RagContextBundle(
    tenant_id=tenant_id,
    trusted_context=dict(build_input.trusted_context),
    citation_map=citation_map,
    prompt_context=RagPromptContext(...),
    verifier_context=RagVerifierContext(
        evidence_snippets=[
            {"citation_id": citation_id, "evidence_id": entry.evidence_ref.evidence_id, "text": entry.snippet}
            for citation_id, entry in citation_map.items()
        ],
        business_fact_refs=build_input.business_fact_refs,
        safe_refs=[entry.evidence_ref.evidence_id for entry in citation_map.values()],
    ),
    debug_context=RagDebugContext(...),
    final_response_context=safe_context,
    memory_context=safe_context,
    replay_context=safe_context,
    business_fact_context=safe_context,
    action_snapshot_context=safe_context,
)
```

**Canonical validation delegation** (lines 244-271):
```python
result = await self.policy_service.get_verified_evidence_details(
    tenant_id=tenant_id,
    evidence_refs=refs,
    effective_at=_optional_str(trusted_context.get("effective_at")),
    merchant_scope=_merchant_scope(trusted_context),
    doc_type=_expected_doc_type(trusted_context),
    risk_level=_expected_risk_level(trusted_context),
)
included = _get_attr_or_key(result, "included", {})
raw_exclusions = _get_attr_or_key(result, "excluded", [])
```

**Current node anti-pattern to split** (`generate_recommendation.py` lines 182-280):
```python
evidence_models = [EvidenceRefV1(**item) for item in evidence_items]
rag_bundle = await _build_rag_context_bundle(state, config, evidence_models)
...
verification = await _verify_recommendation_with_shared_kernel(...)
...
return {
    "recommendation_draft": draft,
    "rag_context_bundle": _state_safe_rag_context_bundle(rag_bundle),
    "rag_verification": verification,
    "verifier_status": str(verification.get("overall_outcome") or ""),
    "verification_route": route_value,
    "evidence_refs": merged_refs,
}
```

**Apply to:** new `rag_context_build` should own candidate-to-package writes: `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, rejected/stale/conflict refs, and build errors. It should call `KnowledgeService.build_verified_context(...)`, return only state updates, and add a trace step with node `"rag_context_build"`.

---

### `src/agent/rag_context/verifier.py`, `src/agent/rag_context/claims.py`, and `src/agent/nodes/claim_verify.py` (service/utility/node, transform/event-driven)

**Analogs:** `src/agent/rag_context/verifier.py`, `src/agent/rag_context/claims.py`, current verification block in `generate_recommendation.py`

**Claim normalization pattern** (`claims.py` lines 15-23):
```python
def normalize_material_claim(value: MaterialClaim | Mapping[str, Any]) -> MaterialClaim:
    """Validate untrusted claim payloads at the rag_context boundary."""
    if isinstance(value, MaterialClaim):
        return value
    return MaterialClaim.model_validate(dict(value))

def normalize_material_claims(values: Iterable[MaterialClaim | Mapping[str, Any]]) -> list[MaterialClaim]:
    return [normalize_material_claim(value) for value in values]
```

**Rules-first verifier pattern** (`verifier.py` lines 280-334):
```python
async def verify_claim(
    self,
    claim: MaterialClaim,
    *,
    context_bundle: RagContextBundle | Mapping[str, Any],
    dependency_results: Sequence[Mapping[str, Any]] | None = None,
) -> MaterialClaimVerificationResult:
    context = _context_dict(context_bundle)
    level1 = self._check_level1(claim, context)
    reason_codes = list(level1.reason_codes)

    if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
        return self._verify_business_fact_claim(claim, context, level1, reason_codes)

    if claim.authority_class == MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM:
        return self._verify_action_recommendation_claim(...)
```

**Level 1 gate pattern** (`verifier.py` lines 398-445):
```python
membership_passed = bool(claim.cited_evidence_ids) and set(claim.cited_evidence_ids).issubset(
    set(_active_source_evidence_ids(context))
)
...
if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM:
    if claim.cited_evidence_ids:
        reason_codes.append("policy_evidence_not_business_authority")
...
business_authority = _business_authority_passed(claim, context)
if claim.authority_class == MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM and not business_authority:
    reason_codes.append("business_fact_ref_required")
```

**Action dependency pattern** (`verifier.py` lines 472-517, 826-865):
```python
dependency_reason_codes = _action_dependency_reason_codes(claim, dependency_results)
reason_codes.extend(dependency_reason_codes)
...
if dependency_reason_codes:
    return self._result(claim, VerificationOutcome.UNSUPPORTED, level1=level1, reason_codes=reason_codes)
if not _business_authority_passed(claim, context):
    reason_codes.append("business_fact_ref_required")
    return self._result(claim, VerificationOutcome.BUSINESS_FACT_MISSING, ...)
```

**Semantic verifier selection pattern** (`verifier.py` lines 916-930):
```python
def should_run_level3_semantic_verification(case: Mapping[str, Any]) -> bool:
    if authority_class == MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM.value:
        return True
    if risk_level in {"high", "critical"}:
        return True
    if level2_outcome in {Level2SupportOutcome.AMBIGUOUS.value, Level2SupportOutcome.NEEDS_SEMANTIC_REVIEW.value}:
        return True
    return bool(risk_hints & {"conflict", "stale_evidence", "ocr_low_confidence", "manual_review_sensitive"})
```

**Apply to:** new `claim_verify` should consume `material_claims`, `verified_evidence_package`, business context/fact refs, and proposed action. It should call `KnowledgeService.verify_claims(...)`, write `claim_verification_bundle`, `blocked_claims`, `safe_support_refs`, compatibility verifier fields if needed, and trace node `"claim_verify"`. `generate_recommendation` should keep material claim creation only.

---

### `src/agent/rag_context/routing.py` and `src/agent/routing.py` (route, deterministic transform)

**Analogs:** `src/agent/rag_context/routing.py`, `src/agent/routing.py`

**Backend-owned route decision pattern** (`rag_context/routing.py` lines 12-40, 100-162):
```python
class VerificationRoute(StrEnum):
    ALLOW = "allow"
    REGENERATE_ROUTE = "regenerate_route"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REFUSE = "refuse"
    MANUAL_REVIEW = "manual_review"

def determine_verification_route(verifier_state: Mapping[str, Any] | Any) -> VerificationRouteDecision:
    try:
        state = _as_mapping(verifier_state)
        reason_codes = _string_list(state.get("reason_codes"))
        outcome = _normalized(state.get("overall_outcome") or state.get("outcome") or state.get("verifier_status"))
        route = _determine_route(state, outcome, set(reason_codes))
        return _decision(route=route, overall_outcome=outcome or "unknown", reason_codes=reason_codes, ...)
    except Exception:
        return _decision(route=VerificationRoute.MANUAL_REVIEW, overall_outcome="unknown", reason_codes=["route_map_exception"])
```

**Finite graph route guard pattern** (`agent/routing.py` lines 20-23, 260-279):
```python
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "recommendation_generation"}
_RECOMMENDATION_ROUTES = {"assess_risk_and_approval", "final_response"}

def route_after_investigate(state: AgentState) -> str:
    try:
        route = _route_after_investigate(state)
    except Exception:
        return "final_response"
    if route in _INVESTIGATE_ROUTES:
        return route
    return "final_response"
```

**Current recommendation router pattern to adapt** (`agent/routing.py` lines 282-307):
```python
def _route_after_recommendation(state: AgentState) -> str:
    route = _recommendation_verification_route(state)
    if route is None or route == "allow":
        return "assess_risk_and_approval"
    return "final_response"
```

**Apply to:** add `route_after_rag_context` and `route_after_claim_verify` as pure state-only routers. Extend finite route-key sets and graph tests. Do not call LLMs, tools, repositories, retrievers, services, or external APIs in routers.

---

### `src/agent/graph.py` and `src/agent/graph_vocabulary.py` (config, event-driven)

**Analogs:** `src/agent/graph.py`, `src/agent/graph_vocabulary.py`

**LangGraph registration pattern** (`graph.py` lines 131-188):
```python
def build_graph(checkpointer: AsyncPostgresSaver):
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("investigate", investigate)
    builder.add_node("generate_recommendation", generate_recommendation, retry_policy=_llm_retry)
    builder.add_node("assess_risk_and_approval", assess_risk_and_approval, retry_policy=_llm_retry)
    ...
    builder.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {
            "final_response": "final_response",
            "clarification_gate": "clarification_gate",
            "recommendation_generation": "generate_recommendation",
        },
    )
```

**Vocabulary entry pattern** (`graph_vocabulary.py` lines 13-20, 76-91, 122-132):
```python
@dataclass(frozen=True)
class GraphVocabularyEntry:
    legacy_name: str
    target_name: str
    kind: TargetGraphKind
    status: TargetGraphStatus
    runnable: bool
    reason_codes: tuple[str, ...] = ()

_entry("rag_context_build", "rag_context_build", "node", "deferred_non_runnable", False, ("PHASE_33_APF_13_OWNED",))
_entry("claim_verify", "claim_verify", "node", "deferred_non_runnable", False, ("PHASE_33_APF_14_OWNED",))
```

**Apply to:** register `rag_context_build` and `claim_verify` as runnable nodes or explicit fail-closed nodes. Promote vocabulary status from `deferred_non_runnable` to `runtime` or a tested compatibility status. Update trace projection tests with the new status.

---

### `src/agent/state.py` and `src/agent/nodes/receive_request.py` (store/model + reset node)

**Analogs:** `src/agent/state.py`, `src/agent/nodes/receive_request.py`

**State field pattern** (`state.py` lines 83-99):
```python
# Phase 10: canonical ephemeral fields reset each turn by receive_request.
primary_intent: str | None
requested_operation: str | None
retrieval_status: str | None
best_score: float | None
termination_reason: str | None
policy_evidence: list[dict[str, Any]] | None
case_memory: list[dict[str, Any]] | None
claim_dependency_map: list[dict[str, Any]] | None
rag_context_bundle: dict[str, Any] | None
rag_verification: dict[str, Any] | None
verifier_status: str | None
verification_route: str | None
verifier_reason_codes: list[str] | None
verifier_safe_citation_refs: list[str] | None
verifier_metrics: dict[str, int | float | bool | str] | None
```

**Per-turn reset pattern** (`receive_request.py` lines 61-98):
```python
return {
    "retrieved_evidence": None,
    "recommendation_draft": None,
    "policy_evidence": None,
    "case_memory": None,
    "claim_dependency_map": None,
    "rag_context_bundle": None,
    "rag_verification": None,
    "verifier_status": None,
    "verification_route": None,
    "verifier_reason_codes": None,
    "verifier_safe_citation_refs": None,
    "verifier_metrics": None,
    ...
}
```

**Apply to:** add target fields and reset them together: `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, `material_claims`, `claim_verification_bundle`, `blocked_claims`, `safe_support_refs`, and any rejected/stale/conflict/build-error refs. Writer ownership tests should assert only the intended node writes these fields.

---

### `src/agent/nodes/generate_recommendation.py` (node, event-driven/request-response)

**Analog:** `src/agent/nodes/generate_recommendation.py`

**Imports to shrink after split** (lines 13-37):
```python
from src.agent.rag_context import (
    ContextBuilder,
    MaterialClaim,
    MaterialClaimAuthorityClass,
    MaterialClaimVerifier,
    RagContextBudget,
    determine_verification_route,
)
from src.knowledge.citation import validate_membership
from src.knowledge.service import PolicyKnowledgeService
```

**Material claim creation pattern to preserve** (lines 701-743):
```python
claims = [
    MaterialClaim(
        claim_id="claim-policy-1",
        claim_text=claim_text,
        authority_class=MaterialClaimAuthorityClass.POLICY_CLAIM,
        source_node="generate_recommendation",
        risk_level=draft.get("risk_level"),
        cited_evidence_ids=cited,
    )
]
...
claims.append(
    MaterialClaim(
        claim_id="claim-action-1",
        claim_text=f"{draft.get('recommended_action')}: {claim_text}",
        authority_class=MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM,
        source_node="generate_recommendation",
        risk_level=draft.get("risk_level"),
        cited_evidence_ids=cited,
        business_fact_refs=business_refs,
        dependency_claim_ids=["claim-policy-1", "claim-business-1"],
    )
)
```

**Draft mutation pattern to remove from generation** (lines 804-829):
```python
draft["verification_route"] = route
draft["verification_status"] = verification.get("overall_outcome")
draft["verification_reason_codes"] = verification.get("reason_codes") or []
draft["material_claims"] = verification.get("material_claims") or [...]
if route != "allow":
    draft["recommended_action"] = route
    draft["confidence"] = 0.0
```

**Apply to:** generation should consume `verified_evidence_package.prompt_context`, emit `material_claims`, and leave verification route/status/bundle fields untouched. If compatibility fields remain, write them in `claim_verify`, not here.

---

### `src/agent/nodes/assess_risk_and_approval.py` and `src/agent/nodes/action_draft.py` (nodes, downstream gates)

**Analogs:** current verifier gate behavior in both files

**Risk gate blocker pattern** (`assess_risk_and_approval.py` lines 152-175, 442-454):
```python
def _non_allow_verification(state: AgentState) -> bool:
    route = _verification_route(state)
    return route is not None and route != "allow"

if _non_allow_verification(state):
    return {
        "risk_assessment": _blocked_verifier_risk(state),
        "proposed_action": None,
        "approval_result": None,
        "action_draft": None,
        "action_payload_hash": None,
        "safety_snapshot_ref": None,
        "safety_snapshot_hash": None,
        "safety_snapshot_verified": False,
        "rag_verification": state.get("rag_verification"),
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("blocked", started_at)],
    }
```

**Candidate-ref fallback to remove for action binding** (`assess_risk_and_approval.py` lines 264-285):
```python
for value in (
    state.get("evidence_refs"),
    draft.get("evidence_refs"),
    (state.get("retrieved_evidence") or {}).get("evidence_refs")
    if isinstance(state.get("retrieved_evidence"), dict)
    else None,
):
    ...
```

**Action draft blocker pattern** (`action_draft.py` lines 99-111, 215-230):
```python
def _verification_blocks_action(state: AgentState) -> bool:
    route = _verification_route(state)
    return route is not None and route != "allow"

if _verification_blocks_action(state):
    return {
        "action_result": {
            "status": "error",
            "error": {"error_code": "VERIFIER_NOT_ALLOW", ...},
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
```

**Apply to:** keep fail-closed behavior, but read `claim_verification_bundle` or an explicit compatibility adapter. Do not allow candidate-only `retrieved_evidence.evidence_refs` into risk, approval, action draft, or safety snapshot evidence refs.

---

### `src/agent/nodes/final_response.py`, `src/agent/working_state.py`, `src/agent/trace.py`, API routers/schemas/repository (projection files)

**Analogs:** current safe final response, working-state projection, trace projection, and API visibility guards

**Final response safe verifier path** (`final_response.py` lines 272-319, 554-578):
```python
def _verification_route_payload(state: AgentState) -> dict[str, Any] | None:
    rag_verification = state.get("rag_verification")
    ...
    if isinstance(route_value, str) and route_value and route_value != "allow":
        return {"overall_outcome": state.get("verifier_status") or "unknown", ...}

if verification is not None:
    if _verification_route_value(verification) == "manual_review":
        response_text = _manual_review_response(draft, verification, state.get("business_context") or {})
    else:
        response_text = _safe_verification_response(verification)
```

**Working-state projection risk to harden** (`working_state.py` lines 133-150, 206-216):
```python
def project_working_state(state: AgentState) -> WorkingStateV1:
    return WorkingStateV1(
        ...
        retrieved_evidence_refs=_retrieved_evidence_refs(state),
        ...
    )

def _retrieved_evidence_refs(state: AgentState) -> list[dict[str, Any]]:
    for value in (
        state.get("retrieved_evidence_refs"),
        state.get("evidence_refs"),
        state.get("policy_evidence"),
        _mapping(state.get("retrieved_evidence")).get("evidence_refs"),
    ):
```

**Trace summary pattern** (`trace.py` lines 236-288):
```python
projected_steps = [
    project_trace_step_for_contract(step if isinstance(step, dict) else {"node": "unknown"})
    for step in trace_steps
]
...
retrieved = final_state.get("retrieved_evidence") or {}
refs = retrieved.get("evidence_refs")
...
return {
    "target_nodes_executed": [step["target_node"] for step in graph_projection_steps],
    "graph_projection": {"schema_version": "target_graph_projection.v1", "steps": graph_projection_steps},
    "evidence_count": evidence_count,
}
```

**Trace API visibility and safe projection pattern** (`api/routers/traces.py` lines 23-71, 106-115):
```python
run = await repo.get_run(run_uuid, user.tenant_id)
if not run:
    raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
...
projected = project_trace_step_for_contract({"node": step.node_name})
return {
    "node": step.node_name,
    "implementation_node": projected["implementation_node"],
    "target_node": projected["target_node"],
    "status": step.status,
}
```

**Repository allowlist projection pattern** (`repositories/trace_repo.py` lines 57-80, 131-146):
```python
projected = project_trace_step_for_contract({"node": step.node_name})
timeline.append(
    {
        "type": "agent_step",
        "detail": {
            "node_name": step.node_name,
            "target_node": projected["target_node"],
            "tool_name": step.tool_name,
            "latency_ms": step.latency_ms,
        },
    }
)

def _safe_draft_outcome(draft: ActionDraft) -> dict[str, Any]:
    projected = {key: outcome[key] for key in _DRAFT_OUTCOME_KEYS if key in outcome}
```

**Apply to:** expose only safe RAG/claim status/count/ref fields. Do not expose raw package/debug contexts, raw verifier prompts, raw reason payloads, raw OCR/source-block internals, or candidate refs as verified refs.

---

## Test Pattern Assignments

### Schema and service tests

**Analogs:** `tests/knowledge/test_phase22_evidence_validation.py`, `tests/agent/rag_context/test_context_builder.py`

**Evidence validation setup pattern** (`test_phase22_evidence_validation.py` lines 24-43, 85-113):
```python
def _evidence_ref(...) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=rank,
    )

class FakeCanonicalPolicyService:
    async def get_canonical_evidence_rows(...):
        return {key: row for key, row in self.rows.items() if row["tenant_id"] == tenant_id}
```

**Rejected evidence test pattern** (`test_phase22_evidence_validation.py` lines 150-183):
```python
result = await service.get_verified_evidence_details(
    tenant_id=tenant_id,
    evidence_refs=[stale_version_ref],
    effective_at="2026-06-19T00:00:00+00:00",
    merchant_scope=["merchant-001"],
    doc_type="refund_rule",
    risk_level="high",
)

assert result.included == {}
reason_codes = set(result.excluded[0].reason_codes)
assert "latest_version_invalid" in reason_codes
```

**Apply to:** new `tests/knowledge/test_verified_evidence_package.py` and `tests/knowledge/test_claim_verification_bundle.py`. Use fake canonical services and strict DTO assertions; no bare pytest commands in plan verification.

### RAG context build and no-leak tests

**Analog:** `tests/agent/rag_context/test_context_builder.py`, `tests/agent/rag_context/test_leakage.py`

**Projection separation pattern** (`test_context_builder.py` lines 108-139):
```python
bundle = await ContextBuilder(policy_service=service, max_snippet_chars=180).build(...)

assert isinstance(bundle, RagContextBundle)
assert bundle.prompt_context is not None
assert bundle.verifier_context is not None
assert bundle.debug_context is not None
assert bundle.final_response_context is not None
assert bundle.prompt_context != bundle.debug_context
assert "source_block_id" not in _json_text(bundle.prompt_context)
assert "text_hash" not in _json_text(bundle.prompt_context)
```

**Invalid evidence exclusion pattern** (`test_context_builder.py` lines 242-294):
```python
bundle = await ContextBuilder(policy_service=service).build(
    candidate_evidence_refs=[valid, wrong_tenant, latest_invalid, unauthorized],
    business_fact_refs=[_business_fact_ref()],
    trusted_context=_trusted_context(),
    risk_hints=[],
)

prompt_text = _json_text(bundle.prompt_context)
verifier_text = _json_text(bundle.verifier_context)
assert wrong_tenant.evidence_id not in prompt_text
assert latest_invalid.evidence_id not in verifier_text
assert {"tenant_mismatch", "latest_version_invalid", "scope_invalid"} <= exclusion_codes
```

**Leakage negative pattern** (`test_leakage.py` lines 264-361):
```python
ordinary_text = _ordinary_surface_text(bundle)
for sentinel in LEAKAGE_SENTINELS:
    assert sentinel not in ordinary_text
assert "text_hash" not in _json_text(bundle.prompt_context)
...
assert SOURCE_BLOCK_ID not in prompt_text
assert SOURCE_BLOCK_ID not in action_text
assert OCR_RAW_METADATA not in replay_text
```

**Apply to:** new `tests/agent/test_nodes/test_rag_context_build.py`, updated leakage tests, and projection tests. Include candidate-only refs not entering prompt/action/risk/approval.

### Claim verification tests

**Analog:** `tests/agent/rag_context/test_verifier.py`

**Membership-not-support pattern** (lines 113-135):
```python
result = await MaterialClaimVerifier().verify_claim(
    claim,
    context_bundle=_bundle(evidence=evidence, evidence_text="This evidence discusses refund timing only."),
)

assert result.level1.membership_passed is True
assert _value(result.outcome) == VerificationOutcome.UNSUPPORTED.value
assert "citation_membership_not_support" in result.reason_codes
assert result.allows_claim is False
```

**Business/action authority pattern** (lines 221-280):
```python
result = await MaterialClaimVerifier().verify_claim(
    claim,
    context_bundle=_bundle(..., business_refs=[]),
)
assert _value(result.outcome) == VerificationOutcome.BUSINESS_FACT_MISSING.value
assert "business_fact_ref_required" in result.reason_codes

result = await MaterialClaimVerifier().verify_claim(
    action_claim,
    dependency_results=[
        {"claim_id": "claim-policy-1", "outcome": "supported"},
        {"claim_id": "claim-business-1", "outcome": "unsupported"},
    ],
)
assert "unsupported_business_dependency" in result.reason_codes
assert result.allows_action_recommendation is False
```

**Apply to:** new `tests/agent/test_nodes/test_claim_verify.py`, `tests/knowledge/test_claim_verification_bundle.py`, and authority-boundary updates. Pin hard gates before semantic review and fail-closed malformed/budget/provider cases.

### Router and graph tests

**Analogs:** `tests/agent/rag_context/test_routing.py`, `tests/agent/test_graph.py`, `tests/agent/test_graph_vocabulary.py`, `tests/architecture/test_phase32_static_contract.py`

**Route matrix pattern** (`test_routing.py` lines 18-131):
```python
@pytest.mark.parametrize(
    ("state", "expected_route"),
    [
        ({"overall_outcome": "supported", "reason_codes": [], "risk_level": "low"}, "allow"),
        ({"overall_outcome": "hash_mismatch", "reason_codes": ["text_hash_mismatch"]}, "refuse"),
        ({"overall_outcome": "needs_manual_review", "reason_codes": ["semantic_ambiguous"]}, "manual_review"),
    ],
)
def test_verification_route_matrix_is_backend_owned(state: dict[str, Any], expected_route: str) -> None:
    result = determine_verification_route(state)
    assert _value(result.route) == expected_route
    assert result.selected_by == "backend"
    assert result.model_selected is False
```

**Graph edge key pattern** (`test_graph.py` lines 748-798):
```python
mapping = {
    "final_response": "final_response",
    "clarification_gate": "clarification_gate",
    "recommendation_generation": "generate_recommendation",
}
for state in states:
    key = route_after_investigate(state)
    assert key in mapping
    assert mapping[key] in nodes
```

**Phase 32 guard to replace** (`test_phase32_static_contract.py` lines 37-47):
```python
assert not re.search(r"builder\.add_node\(\s*['\"]rag_context_build['\"]", graph_source)
assert not re.search(r"builder\.add_node\(\s*['\"]claim_verify['\"]", graph_source)
...
assert entry.status == "deferred_non_runnable"
assert entry.runnable is False
```

**Apply to:** new `tests/agent/test_rag_context_routing.py` and `tests/architecture/test_phase33_rag_claim_boundaries.py`. Invert Phase 32 assertions once nodes become runnable. Test totality over every `rag_context_status` and claim bundle route value.

### Reset, downstream gate, and projection tests

**Analogs:** `tests/agent/test_nodes/test_receive_request.py`, `tests/agent/rag_context/test_routing.py`, `tests/architecture/test_action_draft_boundaries.py`

**Reset assertion pattern** (`test_receive_request.py` lines 86-110):
```python
state = {
    **base_state,
    "rag_context_bundle": {"schema_version": "rag_context_bundle_state_safe.v1"},
    "rag_verification": {"overall_outcome": "supported", "route": {"route": "allow"}},
    "verifier_status": "supported",
    "verification_route": "allow",
    "verifier_reason_codes": ["old_reason"],
}
result = await receive_request(state)
for field in (...):
    assert result[field] is None
```

**Non-allow route boundary pattern** (`test_routing.py` lines 150-162):
```python
result = determine_verification_route(state)
assert _value(result.route) != "allow"
assert result.allow_recommendation is False
assert result.allow_proposed_action is False
assert result.allow_approval_request is False
assert result.allow_action_draft is False
assert result.allow_action_safety_snapshot_evidence is False
```

**Safe projection negative pattern** (`test_action_draft_boundaries.py` lines 163-210):
```python
working_state = project_working_state({... "action_draft": {"payload": {"secret": "ACTION_PAYLOAD_SHOULD_NOT_APPEAR"}}})
serialized = working_state.model_dump_json()
assert "ACTION_PAYLOAD_SHOULD_NOT_APPEAR" not in serialized
assert "safety_snapshot_hash" not in serialized
```

**Apply to:** updated `test_receive_request.py`, risk/action/final tests, trace/API projection tests, and architecture guards. Test stale package/bundle reset and candidate-only refs blocked before risk/approval/action.

## Shared Patterns

### Strict Public Contracts
**Source:** `src/agent/rag_context/schemas.py` lines 20-45 and `src/business/schemas.py` lines 20-56  
**Apply to:** all new package/bundle/claim/status DTOs.
```python
class BusinessFactResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["business_fact_result.v1"] = "business_fact_result.v1"
    tenant_id: str
    status: Literal["ok", "partial", "not_found", "permission_denied", "stale", "unavailable", "invalid_request"]
```

### Canonical Evidence Validation
**Source:** `src/knowledge/service.py` lines 298-393  
**Apply to:** `KnowledgeService.build_verified_context`, `rag_context_build`, and package tests.  
Pattern: re-fetch canonical rows through KnowledgeService, validate tenant/scope/hash/version/effective date/doc type/risk, emit typed exclusions with reason codes, then build safe projections.

### Business Fact Authority
**Source:** `src/tools/contracts.py` lines 58-69 and `src/business/schemas.py` lines 20-56  
**Apply to:** `ClaimVerificationBundleV1`, `claim_verify`, verifier tests.
```python
class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"
    tenant_id: str
    source_system: str
    resource_type: Literal["order", "refund_case", "ticket", "logistics", "merchant_risk"]
    resource_id: str
    resource_version: str | None
```

### Deterministic Routers
**Source:** `src/agent/routing.py` lines 260-279  
**Apply to:** `route_after_rag_context`, `route_after_claim_verify`, graph tests.  
Pattern: pure state read, `try/except`, finite allowed key set, fail closed to `final_response` or `clarification_gate`.

### Writer Ownership
**Source:** current ownership gap in `src/agent/nodes/generate_recommendation.py` lines 182-280 and target reset pattern in `receive_request.py` lines 61-98  
**Apply to:** architecture guard tests and node tests.  
Pattern: `rag_context_build` is only writer for package/status/maps; `claim_verify` is only writer for bundle/blocked/safe refs; `generate_recommendation` writes recommendation/material claims only.

### Downstream Fail-Closed Gates
**Source:** `src/agent/nodes/assess_risk_and_approval.py` lines 442-454 and `src/agent/nodes/action_draft.py` lines 215-230  
**Apply to:** risk, approval, action draft, final response, snapshot binding.  
Pattern: non-allow verification clears proposed action, approval, draft, payload hash, safety snapshot refs, and verified snapshot flag.

### Safe Trace/API Projection
**Source:** `src/api/routers/traces.py` lines 23-71, `src/repositories/trace_repo.py` lines 57-80, `src/agent/trace.py` lines 236-288  
**Apply to:** trace/API/working-state projection files.  
Pattern: preserve tenant/user visibility checks; expose allowlisted node/status/count/ref summaries only; do not expose raw package/debug/verifier internals.

### Validation Command Pattern
**Source:** `AGENTS.md` lines 16-21 and `33-VALIDATION.md` test matrix  
**Apply to:** every plan and test instruction.  
Use:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q --tb=short
uv run ruff check ...
git diff --check
```
Do not use bare `pytest` or bare `python -m pytest`.

## No Exact Analog Found

| File | Role | Data Flow | Reason | Planner Guidance |
|------|------|-----------|--------|------------------|
| `src/agent/rag_context/domain_rules.py` | utility | transform | No dedicated `DomainRuleVerifier` module/class exists. Current hard-rule behavior is embedded in `MaterialClaimVerifier.check_level2_support`, `_check_level1`, and action dependency helpers. | Either add a minimal `DomainRuleVerifier` module or expose a small class in `verifier.py`. Copy strict DTO/error style from `verifier.py`; test negation/condition/threshold/time-window/exception/conflict cases so semantic review cannot override hard gates. |

## Metadata

**Analog search scope:** `src/knowledge`, `src/agent/rag_context`, `src/agent/nodes`, `src/agent/routing.py`, `src/agent/graph.py`, `src/agent/graph_vocabulary.py`, `src/agent/state.py`, `src/agent/working_state.py`, `src/agent/trace.py`, `src/api`, `src/repositories`, `src/business`, `src/tools`, focused `tests/agent`, `tests/knowledge`, and `tests/architecture`.  
**Files scanned:** 143 focused source/test paths by `rg --files` pattern scan.  
**Files excerpted:** 28.  
**Project skill directories:** no project-local `.claude/skills` or `.agents/skills` `SKILL.md` files were found.  
**Pattern extraction date:** 2026-06-29.  
**Planner note:** keep Phase 33 split into at least the five dependency-ordered units from `33-CONTEXT.md`: contracts/state/service boundary; `rag_context_build`; generation + `claim_verify`; downstream gates/projections; final focused/static/eval closure.
