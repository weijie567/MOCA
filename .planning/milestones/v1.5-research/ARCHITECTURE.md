# Architecture Research

**Domain:** MOCA v1.5 / Phase 22 RAG Context Builder + Hallucination Control
**Researched:** 2026-06-19
**Confidence:** HIGH for integration boundaries, MEDIUM for Level 3 semantic verifier details

## Standard Architecture

### System Overview

Phase 22 should add a retrieval-after, reasoning-before evidence kernel. It should not add a retriever, query rewriter, reranker, external search backend, external action executor, or generic prompt assembly layer.

Current online retrieval remains:

```text
User query
  -> LangGraph investigate node
  -> UnifiedToolManager search_policy
  -> KnowledgeToolExecutor
  -> PolicyKnowledgeService.search(...)
  -> PolicyRetrievalEngine dense + sparse + fuzzy + RRF
  -> KnowledgeSearchResult.evidence_refs: EvidenceRefV1[]
```

Phase 22 inserts after candidate refs are retrieved and before recommendation/action reasoning:

```text
candidate EvidenceRefV1[] + BusinessContextV1 + ToolResultV2 summaries
  + trusted tenant/run/thread context
  + risk/conflict/OCR/freshness hints
    |
    v
ContextBuilder
  - canonical content re-fetch through PolicyKnowledgeService
  - tenant/scope/hash/effective-time validation
  - dedupe and adjacent-chunk merge
  - citation map E1/E2/...
  - freshness/authority/OCR/conflict labels
  - exclusion reasons
  - token budget trace
    |
    v
RagContextBundle
  - internal evidence items and validation labels
  - prompt-safe projection for ContextAssembler
  - verifier/debug trace kept separate
    |
    v
ReasoningContext
  - prompt-safe RAG bundle
  - safe business fact refs and tool summaries
  - memory context as non-authoritative context
  - risk/action hints
    |
    v
recommendation_generation LLM structured output
  -> MaterialClaim[] normalization
  -> TieredClaimVerifier
  -> deterministic route: allow | regenerate | refuse | manual_review
  -> final_response or risk/approval/action-draft path
```

The reasoning kernel should be implemented behind the existing `recommendation_generation` node first. Add a deterministic `route_after_recommendation` router only after verifier outputs are stable. Do not introduce a new registered LangGraph node unless a later phase needs independent node lifecycle replay.

### Component Responsibilities

| Component | New or Modified | Responsibility | Implementation Guidance |
|-----------|-----------------|----------------|-------------------------|
| `src/agent/rag_context/schemas.py` | New | Runtime schemas for `RagContextBundle`, `ReasoningContext`, `EvidenceContextItem`, `CitationMapEntry`, `MaterialClaim`, and `ClaimVerificationResult`. | Keep these as Reasoning Kernel DTOs. They do not replace `EvidenceRefV1`, `BusinessFactRefV1`, or `ToolResultV2`. |
| `src/agent/rag_context/builder.py` | New | Build prompt-safe evidence context from candidate `EvidenceRefV1` values. | Use `PolicyKnowledgeService` verified lookup helpers. Never call `PolicyRetrievalEngine.retrieve` or alter ranking. |
| `src/agent/rag_context/budget.py` | New or local helper | Evidence-specific token/character budgeting before generic prompt assembly. | Protect citation metadata and labels; trim snippet text only. Reuse `TokenBudgetPolicy` concepts but keep evidence budgeting explicit. |
| `src/agent/rag_context/claims.py` | New | Normalize LLM output into `MaterialClaim[]`; validate authority refs by claim type. | Start with an adapter from current `RecommendationDraft`, then move to native structured claim output. |
| `src/agent/rag_context/verifier.py` | New | Tiered claim verifier: Level 1 deterministic gates, Level 2 lexical/span checks, Level 3 risk-triggered semantic support. | Import existing `validate_membership` for membership, but do not change its membership-only contract. |
| `src/agent/rag_context/routing.py` | New | Deterministic mapping from verification failures to `allow`, `regenerate`, `refuse`, or `manual_review`. | Keep pure and side-effect free so it can back `route_after_recommendation`. |
| `src/knowledge/service.py` | Modified narrowly | Add or consolidate verified evidence context lookup. | Extend facade with context lookup that re-fetches content/provenance/metadata by ref. Do not expose repository details to agent nodes. |
| `src/repositories/policy_chunk_repo.py` | Modified narrowly | Supply verified context rows needed by ContextBuilder. | Existing `get_contents_by_evidence_keys` and provenance lookup are the base. Add metadata lookup only if needed for labels. Do not change search SQL ranking. |
| `src/agent/nodes/generate_recommendation.py` | Modified | Replace local content re-fetch, allowed-citation JSON, and one-claim projection with ContextBuilder + MaterialClaim + verifier. | Preserve existing skip behavior for `insufficient_evidence` and `retrieval_error`. Keep LLM retry inside the node. |
| `src/agent/routing.py` and `src/agent/graph.py` | Modified | Add `route_after_recommendation` from verifier action to `assess_risk_and_approval` or `final_response`. | This is already a target contract router in `docs/contract-spec.md`; current graph lacks it. Do not add model/tool calls to the router. |
| `src/agent/nodes/final_response.py` | Modified | Render deterministic refusal/manual-review/insufficient-evidence messages from verifier status. | Do not expose verifier trace or source-block raw metadata in user-facing text. |
| `src/agent/context/projectors.py` | Modified narrowly | Project prompt-safe RAG bundle fields. | Allow `citation_id`, citation ref fields, compact labels, and snippet text. Continue filtering hash/debug/raw/provenance fields. |
| `src/agent/context/assembler.py` | Usually unchanged | Generic prompt assembly and block budgeting. | Consume `RagContextBundle.prompt_policy_snippets` through existing `verified_policy_snippets`; ContextBuilder owns RAG-specific budgeting. |
| `src/agent/state.py` | Modified | Add per-turn fields for prompt-safe `rag_context`, `material_claims`, `claim_verification`, and `verification_route`. | Reset every turn. Keep internal debug trace redacted or out of state if it would leak into prompt/replay. |
| `src/agent/events.py` / replay | Prefer unchanged | Use existing node/LLM/RAG event families and redacted payloads. | Do not add new event types unless registry/redaction tests are included. Use `generate_recommendation` node payload summaries for Phase 22. |
| Approval/action snapshot modules | Mostly unchanged | Consume only verified `evidence_refs` selected by claim validation. | `ActionSafetySnapshot` still stores canonical `EvidenceRefV1[]`; no MaterialClaim or provenance extension is required. |

### Current-Code Constraints

- `docs/current-implementation-map.md` is useful but stale for Phase 21. Current code now has `ContextAssembler`, `DocumentBlock`, `RagIngestionJob`, chunk source-block refs, OCR metadata, and verified provenance lookup.
- `generate_recommendation.py` already performs local evidence content re-fetch and membership validation. Phase 22 should move that behavior into reusable ContextBuilder/verifier services instead of duplicating it.
- `PolicyRetrievalEngine` already implements dense + sparse + fuzzy retrieval with RRF and effective-date filtering. Phase 22 must not alter its score normalization, candidate fusion, or final rank order.
- Current policy models include `effective_date`, `risk_level`, source metadata, source-block refs, and OCR metadata. They do not currently expose full `authority_level` or `supersedes_doc_id` policy conflict semantics. Phase 22 may label authority/conflict as `unknown` and route high-risk ambiguity to manual review; adding full authority/supersedes ranking behavior belongs outside Phase 22 unless the planner scopes a very narrow context-only metadata addition.
- `PolicyKnowledgeService.get_verified_evidence_provenance(...)` intentionally returns only verified locator data. Missing provenance should not break low-risk text-only policy answers, but high-risk OCR/table-dependent claims should route to manual review if required locator/confidence data is unavailable.

## Recommended Project Structure

```text
src/
+-- agent/
|   +-- rag_context/
|   |   +-- __init__.py
|   |   +-- schemas.py       # RagContextBundle, ReasoningContext, MaterialClaim, verifier DTOs
|   |   +-- builder.py       # ContextBuilder retrieval-after evidence kernel
|   |   +-- budget.py        # evidence-specific snippet budgeting and trace
|   |   +-- claims.py        # MaterialClaim normalization and authority validation
|   |   +-- verifier.py      # tiered verifier policy engine
|   |   +-- routing.py       # deterministic verification action mapping
|   +-- context/
|   |   +-- assembler.py     # existing generic prompt assembler
|   |   +-- projectors.py    # extend only for prompt-safe RAG projection
|   +-- nodes/
|   |   +-- generate_recommendation.py  # integrate builder/claims/verifier
|   |   +-- final_response.py           # deterministic failure responses
|   +-- routing.py           # add route_after_recommendation
|   +-- graph.py             # wire recommendation router if needed
+-- knowledge/
|   +-- citation.py          # keep membership-only validation
|   +-- service.py           # verified evidence context lookup helper
|   +-- schemas.py           # EvidenceRefV1 remains canonical
+-- repositories/
    +-- policy_chunk_repo.py # optional context metadata lookup, no search ranking change

tests/
+-- agent/
|   +-- rag_context/
|   |   +-- test_context_builder.py
|   |   +-- test_material_claims.py
|   |   +-- test_verifier.py
|   |   +-- test_routing.py
|   +-- test_nodes/
|       +-- test_generate_recommendation.py
|       +-- test_final_response.py
+-- knowledge/
    +-- test_evidence_context_lookup.py

eval/
+-- rag_context/
    +-- phase22_claims.jsonl
    +-- phase22_conflict_stale_ocr.jsonl
    +-- phase22_action_grounding.jsonl
```

### Structure Rationale

- **`src/agent/rag_context/`:** Phase 22 belongs to the Agent reasoning layer, not the retrieval backend. A separate package prevents the existing generic `ContextAssembler` from becoming a RAG policy engine.
- **`src/knowledge/service.py`:** content/provenance re-fetch should stay behind the Knowledge facade because repository queries must remain tenant/hash checked.
- **`src/knowledge/citation.py`:** keep current membership validator simple. Semantic support is a new verifier concern and should not be smuggled into citation membership.
- **No new `src/knowledge/reranker.py` or `SearchBackend`:** those are Phase 23 and RAG-5 respectively.
- **No action module changes beyond consumption:** Phase 22 may block unsupported action recommendations, but Phase 17 owns external execution.

## Architectural Patterns

### Pattern 1: ContextBuilder As A Reasoning Kernel

**What:** Build evidence context from already-retrieved candidate refs. The builder validates, filters, labels, and budgets evidence. It does not search.

**When to use:** In `recommendation_generation` before constructing the LLM prompt, and in tests/eval that need deterministic context assembly.

**Trade-offs:** This adds another runtime object between retrieval and generation, but it removes duplicated evidence re-fetch/hash/citation-map logic from nodes.

**Example:**

```python
bundle = await ContextBuilder(knowledge_service).build(
    candidate_evidence_refs=evidence_models,
    business_fact_refs=business_context.business_fact_refs,
    trusted_context=trusted_context,
    effective_at=run_effective_at,
    risk_hints=risk_hints,
    token_budget_chars=5000,
)

if bundle.status in {"no_valid_evidence", "unauthorized", "hash_mismatch"}:
    return verifier_route_to_safe_draft(bundle)
```

ContextBuilder input is candidate evidence. Calling `PolicyKnowledgeService.search(...)` from ContextBuilder would violate Phase 22 scope.

### Pattern 2: Internal Bundle, Prompt-Safe Projection

**What:** `RagContextBundle` can contain internal verification labels and ref objects, but prompts receive only its prompt-safe projection.

Recommended split:

```python
class EvidenceContextItem(BaseModel):
    citation_id: str              # E1, E2, ...
    ref: EvidenceRefV1            # internal canonical ref, not expanded raw into prompt
    snippet: str                  # canonical chunk content, budgeted
    title: str | None = None
    section: str | None = None
    labels: EvidenceLabels
    support_candidates: list[str] = []

class RagContextBundle(BaseModel):
    schema_version: Literal["rag_context_bundle.v1"]
    status: Literal["ready", "partial", "no_valid_evidence"]
    items: list[EvidenceContextItem]
    citation_map: dict[str, str]  # E1 -> evidence_id
    exclusions: list[EvidenceExclusion]
    token_budget_trace: TokenBudgetTrace
    verifier_trace_ref: str | None = None

    def prompt_policy_snippets(self) -> list[dict[str, str]]:
        ...
```

The prompt projection should include:

- `citation_id`
- `evidence_id`
- `doc_key`
- `chunk_id`
- `policy_version`
- title/section when available
- compact labels such as `freshness=current`, `ocr=review_needed`, `conflict=possible`
- bounded snippet text

The prompt projection should not include:

- raw `text_hash`
- full source block locators, bbox, table JSON, parser/OCR raw metadata
- retrieval debug features such as dense/sparse/fuzzy ranks or RRF scores
- verifier trace, model judge prompt, private reasoning, approval/action snapshot bodies

### Pattern 3: MaterialClaim As Authority-Separated Output

**What:** The generator must produce structured claims with explicit authority refs. Phase 22 should use the milestone taxonomy:

```python
ClaimType = Literal[
    "policy_claim",
    "business_fact_claim",
    "action_recommendation_claim",
]

class MaterialClaim(BaseModel):
    schema_version: Literal["material_claim.v1"] = "material_claim.v1"
    claim_id: str
    claim_type: ClaimType
    claim_text: str
    risk_level: Literal["low", "medium", "high"]
    cited_evidence_ids: list[str] = []
    business_fact_refs: list[BusinessFactRefV1] = []
    tool_result_refs: list[str] = []
    depends_on_claim_ids: list[str] = []
```

Validation rules:

- `policy_claim` requires at least one cited `EvidenceRefV1` from the current `RagContextBundle`.
- `business_fact_claim` requires `BusinessFactRefV1` or safe `ToolResultV2` refs and must not cite policy evidence as factual business state.
- `action_recommendation_claim` requires both policy support and business fact support, usually through `depends_on_claim_ids`.
- Memory context may help language/continuity, but must not satisfy any material claim authority requirement.
- A recommended action claim may create a proposed action candidate only after verification; it cannot bypass risk/approval/action snapshot boundaries.

**When to use:** Every recommendation that gives a policy conclusion, business factual conclusion, or action recommendation.

**Trade-offs:** Claim generation adds structured-output burden. The payoff is deterministic routing and eval visibility.

### Pattern 4: Tiered Verifier Policy Engine

**What:** Verification is a policy engine with deterministic gates first and semantic support only when risk requires it.

```text
Level 1, always:
  - citation membership against current bundle
  - tenant/scope match
  - content hash match from canonical re-fetch
  - effective_at/freshness validity
  - business ref tenant/scope/status validity
  - claim-type authority separation

Level 2, normal path:
  - lexical/span support for cited snippets
  - numeric/date/entity consistency
  - required condition/action words present in cited evidence
  - business identifiers present only when backed by business refs

Level 3, risk-triggered:
  - semantic support judge over claim text and cited snippets only
  - conflict/stale/OCR-low-confidence/manual-review policy
  - timeout and model error fail closed
```

Triggers for Level 3:

- high-risk refund responsibility, compensation, penalty, appeal, unban, compliance, or merchant-impacting recommendations
- any `action_recommendation_claim`
- conflict labels
- stale or superseded evidence risk
- low-confidence OCR/table evidence
- Level 2 ambiguity or insufficient lexical support

Do not use verifier scores to reorder evidence. Reranking belongs to Phase 23.

### Pattern 5: Deterministic Failure Routing

**What:** Verifier output drives product behavior through a pure route map, not another LLM decision.

Recommended route map:

| Verification condition | Route | User-facing outcome |
|------------------------|-------|---------------------|
| All required claims supported | `allow` | Continue to risk/approval/action-draft path or final response. |
| Citation missing but evidence exists | `regenerate_once` | Retry structured generation once inside `recommendation_generation`; fail to insufficient evidence if still invalid. |
| Unsupported low-risk policy claim | `refuse` | Explain current evidence is insufficient for that conclusion. |
| Unauthorized or hash-mismatched evidence | `refuse` | Do not mention restricted content. Ask to retry or escalate safely. |
| Stale/superseded evidence only | `manual_review` or `refuse` | Manual review for high risk; refusal/insufficient evidence for low risk. |
| Conflict label without deterministic authority winner | `manual_review` | State that policy evidence conflicts and needs human review. |
| Business fact claim without business refs | `refuse` | Ask for missing business data or tool lookup. |
| Action recommendation missing policy or business support | `manual_review` | No proposed action, no snapshot, no draft. |
| Level 3 timeout/error | `manual_review` for high risk, `refuse` otherwise | Fail closed. |

`route_after_recommendation` should only read verifier output and return a graph node key. It must not call LLMs, tools, repositories, or services.

## Data Flow

### Request Flow

```text
receive_request
  -> classify_intent
  -> optional session_memory_load + extract_slots
  -> investigate
       - read tools return ToolResultV2 + BusinessFactRefV1
       - search_policy returns candidate EvidenceRefV1[]
       - retrieval_status/best_score drive route_after_investigate
  -> generate_recommendation
       - ContextBuilder builds RagContextBundle
       - ContextAssembler receives prompt-safe policy snippets
       - LLM returns structured recommendation + MaterialClaim[]
       - TieredClaimVerifier returns ClaimVerificationResult
       - node writes verified evidence_refs only
  -> route_after_recommendation
       - allow -> assess_risk_and_approval
       - refuse/manual_review/insufficient -> final_response
  -> assess_risk_and_approval
       - builds ActionSafetySnapshot only from verified EvidenceRefV1 refs
  -> approval_gate/action_draft/final_response
```

### State Management

Add only per-turn state fields, reset by `receive_request`:

```text
rag_context_bundle       prompt-safe summary or compact dict
reasoning_context        prompt-safe generation input summary
material_claims          MaterialClaim[] after normalization
claim_verification       ClaimVerificationResult
verification_route       allow | regenerate | refuse | manual_review
manual_review_reason     safe reason code/message
```

Do not store full prompts, raw chunk text beyond existing evidence snippet needs, raw source-block metadata, semantic verifier prompt/completion, or private reasoning in replay. Existing `evidence_refs` remains the verified, action-consumable subset written by recommendation/citation validation, not by `investigate`.

### Key Data Flows

1. **Evidence candidate to context bundle:** `EvidenceRefV1[]` from `retrieved_evidence` is re-fetched through Knowledge facade, hash checked, deduped, labeled, budgeted, and projected into `policy_refs` prompt block.
2. **Business facts to claims:** `BusinessFactRefV1[]` from `ToolResultV2` is carried into `ReasoningContext`; business factual claims must bind to these refs.
3. **Claims to verifier:** Material claims reference citation IDs/evidence IDs and business refs; verifier checks authority and support.
4. **Verifier to router:** Claim verification emits one deterministic route. No model chooses whether to allow/refuse/manual-review.
5. **Verified refs to action boundary:** Only supported claim refs are promoted to `state.evidence_refs`; approval/action snapshot code continues to hash canonical `EvidenceRefV1` only.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Recommendation |
|----------|---------------|----------------|
| `investigate` -> ContextBuilder | Candidate `EvidenceRefV1[]` plus retrieval status/score | Treat as candidates only. Do not promote to action evidence until claim verification succeeds. |
| ContextBuilder -> `PolicyKnowledgeService` | Verified content/provenance/context lookup | Add a facade helper if needed. Preserve `EvidenceRefV1` identity and Phase 20 RRF semantics. |
| ContextBuilder -> `ContextAssembler` | `prompt_policy_snippets()` list | Let ContextBuilder own evidence budget; let assembler own final prompt block assembly. |
| `generate_recommendation` -> MaterialClaim normalizer | Structured LLM output | Keep backward-compatible adapter from current `RecommendationDraft` while introducing native claims. |
| MaterialClaim verifier -> `knowledge.citation.validate_membership` | Membership-only check | Existing validator remains membership-only; semantic support lives in new verifier. |
| Verifier -> `route_after_recommendation` | `ClaimVerificationResult.action` | Pure route map. No DB/LLM/tool calls in router. |
| Verifier -> `final_response` | Safe status/reason codes | User text names missing support/conflict/manual-review, not debug internals. |
| Verifier -> `assess_risk_and_approval` | Supported `evidence_refs` and proposed action only | Action snapshots continue to use canonical `EvidenceRefV1[]`; no provenance or MaterialClaim hash contract in Phase 22. |
| Business tools -> MaterialClaim | `BusinessFactRefV1`, `ToolResultPromptSummary` | Business facts never become policy evidence; policy evidence never proves current order/refund/ticket state. |
| Memory -> MaterialClaim | Context-only snippets/source refs | Memory may shape continuity but never satisfies policy, business, approval, action, or replay authority. |
| Replay/debug -> prompt | Redacted summaries only | No raw prompt, verifier trace, source-block raw metadata, OCR payload, bbox table dump, or chain-of-thought. |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| PostgreSQL / pgvector | Existing retrieval and verified lookup store | Phase 22 may add lookup queries, not ranking semantics. |
| OpenAI-compatible chat model | Existing `ChatOpenAI` for generation; optional Level 3 judge | Level 3 input must be bounded claim + cited snippets only. Timeout/error fails closed. |
| OCR/parser outputs from Phase 21 | Consumed as labels through provenance/context lookup | Source-block and OCR raw metadata stay out of ordinary prompts and responses. |
| No external search backend | None | RAG-5 owns Vespa/OpenSearch/full `SearchBackend`. |
| No external action execution | None | Phase 17 owns outbox, reconciliation, and real side effects. |

## Build Order

1. **Schema and state foundation**
   - Add Reasoning Kernel DTOs under `src/agent/rag_context/schemas.py`.
   - Add per-turn state fields and reset rules.
   - Add tests proving `EvidenceRefV1`, `BusinessFactRefV1`, and `ToolResultV2` remain separate authorities.

2. **Verified evidence context lookup**
   - Extend `PolicyKnowledgeService` with a verified context lookup if current content/provenance helpers are insufficient.
   - Return content, safe title/section/page summary, effective/freshness metadata, OCR label inputs, and provenance references needed for labels.
   - Tests must cover tenant mismatch, duplicate keys, missing content, text hash mismatch, and no `EvidenceRefV1` schema change.

3. **ContextBuilder MVP**
   - Implement build from candidate refs to `RagContextBundle`.
   - Include dedupe, stable citation IDs, exclusion reasons, prompt-safe snippets, labels, and token budget trace.
   - Keep retrieval ranking untouched; tests should assert ContextBuilder never calls `retrieve`/`search`.

4. **Prompt integration without semantic verifier**
   - Replace `generate_recommendation.py` local `_policy_snippets` and `_allowed_citation_objects` logic with ContextBuilder.
   - Feed `bundle.prompt_policy_snippets()` into `ContextAssembler`.
   - Preserve existing membership validation behavior while the new claim verifier is built.

5. **MaterialClaim generation and authority validation**
   - Add a compatibility adapter from current `RecommendationDraft` to minimal claims.
   - Then extend structured output to emit `material_claims` natively.
   - Validate claim type authority deterministically before any semantic check.

6. **Level 1 and Level 2 verifier**
   - Implement membership/scope/hash/freshness/business-ref gates.
   - Add lexical/span checks for ordinary claims.
   - Add deterministic route mapping and final response support for refusal/manual-review.
   - Wire `route_after_recommendation` to skip risk/approval/action when verification is not `allow`.

7. **Level 3 semantic verifier**
   - Add only after Level 1/2 are stable.
   - Gate by risk/conflict/stale/OCR/ambiguous triggers.
   - Use strict budgets, timeout, stable output enum, and fail-closed routing.
   - Do not reuse semantic verifier as reranker or query rewrite.

8. **Action boundary hardening**
   - Ensure `action_recommendation_claim` without both policy and business support cannot produce `proposed_action`.
   - Ensure `ActionSafetySnapshot` uses only verified canonical `EvidenceRefV1[]`.
   - Add regression tests for partial evidence, unsupported claims, and manual-review route before approval/action draft.

9. **Eval and leakage tests**
   - Add Phase 22 golden sets for faithfulness, citation support, conflict/stale/OCR traps, business hallucination, and action grounding.
   - Add prompt/replay leakage tests proving debug fields, source locators, raw OCR, verifier prompts, and hashes do not enter ordinary prompts/responses.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current demo | Run ContextBuilder and Level 1/2 in-process inside `generate_recommendation`; Level 3 only for risk triggers. |
| Larger policy corpus | Optimize verified context lookup batching and snippet budgeting before changing retrieval. |
| More high-risk traffic | Add verifier latency budgets, cache hash-verified context by run, and track Level 3 timeout/manual-review rate. |
| More complex policy conflicts | Add explicit conflict-group metadata in ingestion/retrieval labels, but keep manual-review fallback until authority rules are deterministic. |

### Scaling Priorities

1. **First bottleneck: repeated evidence re-fetch.** Batch by `(tenant_id, doc_key, chunk_id)` and cache within one run only.
2. **Second bottleneck: Level 3 verifier latency.** Trigger only on risk labels; use strict claim and snippet budgets.
3. **Third bottleneck: prompt size.** ContextBuilder should trim snippets before `ContextAssembler`; protected citation metadata must remain.

## Anti-Patterns

### Anti-Pattern 1: ContextBuilder Calls Retrieval

**What people do:** Add query rewrite, reranker, or `PolicyRetrievalEngine.retrieve(...)` calls inside ContextBuilder.

**Why it is wrong:** Phase 22 is after retrieval. Calling retrieval changes Phase 20 RRF semantics and overlaps Phase 23.

**Do this instead:** ContextBuilder accepts candidate refs and validates/labels/budgets them.

### Anti-Pattern 2: EvidenceRefV1 Becomes A Provenance Container

**What people do:** Add page, bbox, OCR confidence, conflict labels, or support status to `EvidenceRefV1`.

**Why it is wrong:** `EvidenceRefV1` is canonical identity for Knowledge result, AgentState, replay, approval snapshots, and hash projection.

**Do this instead:** Keep provenance and labels in `RagContextBundle` / debug side paths. The canonical ref remains unchanged.

### Anti-Pattern 3: Citation Membership Equals Semantic Support

**What people do:** Treat `validate_membership(...).is_valid` as proof that the claim is true.

**Why it is wrong:** Current citation validation explicitly checks only evidence ID membership.

**Do this instead:** Use membership as Level 1, then lexical/span Level 2, and risk-triggered semantic Level 3.

### Anti-Pattern 4: Business Facts Cited As Policy Evidence

**What people do:** Let an order/refund/ticket claim cite a policy chunk, or let a policy claim cite a tool summary.

**Why it is wrong:** MOCA separates policy authority from current business facts. Mixing them causes business-data hallucination and unsafe action recommendations.

**Do this instead:** `business_fact_claim` requires `BusinessFactRefV1`/tool refs; `policy_claim` requires `EvidenceRefV1`; action claims require both.

### Anti-Pattern 5: Debug Trace In Prompt

**What people do:** Put RRF ranks, source-block locators, OCR raw payload, verifier trace, or hash fields into prompts to help the model.

**Why it is wrong:** Debug artifacts can leak internals, bloat prompt budget, and confuse the authority boundary.

**Do this instead:** Prompts get compact labels and snippets. Debug/replay gets redacted IDs, reason codes, counts, and safe summaries.

### Anti-Pattern 6: Semantic Verifier As A Reranker

**What people do:** Use Level 3 support scores to reorder evidence or improve retrieval quality.

**Why it is wrong:** Reranking/query rewrite is Phase 23. Verifier answers "can this evidence support this claim?", not "which candidate should rank higher?"

**Do this instead:** Verifier outputs support status and route action only.

### Anti-Pattern 7: Manual Review As A Prompt Suggestion

**What people do:** Ask the model to decide whether to escalate.

**Why it is wrong:** Unsupported, stale, conflicting, or high-risk failures must fail closed deterministically.

**Do this instead:** Use verifier reason codes and deterministic route mapping.

## Evaluation Integration

Phase 22 eval should add evidence-chain and routing tests, not just retrieval Hit@5.

Recommended golden categories:

| Category | Expected Check |
|----------|----------------|
| `policy_claim_supported` | Supported policy claim cites evidence whose snippet contains the rule. |
| `citation_membership_invalid` | Generated nonexistent citation routes to regenerate/refuse. |
| `semantic_support_failure` | Cited chunk is related but does not support the claim. |
| `business_fact_required` | Business fact claim without `BusinessFactRefV1` refuses or asks for lookup. |
| `action_missing_policy_support` | No action recommendation reaches risk/approval/action draft. |
| `action_missing_business_support` | No action recommendation reaches risk/approval/action draft. |
| `policy_conflict` | Conflicting evidence routes to manual review unless deterministic authority rule exists. |
| `policy_stale_version` | Stale/superseded evidence cannot support a material claim. |
| `ocr_low_confidence_trap` | Low-confidence OCR evidence cannot support high-risk action without manual review. |
| `prompt_debug_leakage` | Prompt excludes hash/debug/source-block/OCR raw/verifier trace fields. |
| `memory_authority_boundary` | Memory snippets cannot satisfy policy/business/action support. |

Recommended metrics:

- faithfulness rate by claim type
- citation membership accuracy
- citation support accuracy
- refusal accuracy for no/unsupported evidence
- manual-review routing accuracy for conflict/stale/OCR/high-risk traps
- business-data hallucination rate
- action recommendation support completeness
- prompt/debug leakage count
- Level 3 trigger rate, timeout rate, and fail-closed route rate

Implementation options:

- Add `scripts/eval_rag_context_builder.py` for offline deterministic bundle/verifier cases.
- Extend `scripts/eval_agent.py` for end-to-end route assertions.
- Keep existing `scripts/eval_rag.py` and `scripts/eval_rag_hit_at_5.py` focused on retrieval; do not turn retrieval eval into hallucination-control eval.

## Explicit Non-Overlap Boundaries

| Deferred Owner | Do Not Build In Phase 22 | Allowed Phase 22 Work |
|----------------|--------------------------|-----------------------|
| Phase 23 reranker/query rewrite | Query rewrite, cross-encoder reranking, external rerank APIs, ranking explanation UI. | Consume current candidate refs and labels; verify support after retrieval. |
| Phase 17 external execution | Outbox, real dispatch, reconciliation, compensation, external idempotency worker. | Block unsupported action recommendations before risk/approval/action draft. |
| Phase RAG-5 external backend | Vespa/OpenSearch, full `SearchBackend`, vector database migration. | Add verified context lookup behind existing `PolicyKnowledgeService`. |
| post-Phase 17 Policy Scope | Tenant-over-global fallback/precedence implementation. | Enforce current tenant/scope/hash/effective-time gates. |
| Policy Source Operations | Upload/review UI and policy lifecycle workflows. | Consume Phase 21 provenance/OCR labels for context/verifier routing. |

## Sources

- `.planning/PROJECT.md` - v1.5 scope, active requirements, and hard deferrals.
- `docs/rag-architecture-spec.md` sections 4.1, 4.2, 9.5, 11, 12 - target Reasoning Kernel, Context Builder, and hallucination-control architecture.
- `docs/contract-spec.md` sections 8.0, 8.3, 8.4, 9, 12.5, 15, 17 - normative trusted context, evidence/tool/action/replay contracts.
- `docs/current-implementation-map.md` - useful baseline, but generated 2026-06-17 and stale for Phase 21 additions; current code now includes `DocumentBlock` and `ContextAssembler`.
- `src/agent/context/assembler.py` and `src/agent/context/projectors.py` - existing prompt-safe assembly and projection boundaries.
- `src/knowledge/service.py`, `src/knowledge/provenance.py`, `src/knowledge/citation.py`, `src/knowledge/retrieval.py` - Knowledge facade, provenance side path, membership-only citation validation, and Phase 20 retrieval semantics.
- `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/final_response.py`, `src/agent/nodes/investigate.py`, `src/agent/graph.py` - current graph integration points.
- `src/tools/contracts.py` - `ToolResultV2` and `BusinessFactRefV1` authority boundary.
- `src/db/models.py` and `src/repositories/policy_chunk_repo.py` - Phase 21 source-block/provenance storage now present in code.

---
*Architecture research for: MOCA Phase 22 RAG Context Builder + Hallucination Control*
*Researched: 2026-06-19*
