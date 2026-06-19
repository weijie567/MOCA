# Stack Research

**Domain:** MOCA v1.5 / Phase 22 RAG Context Builder + Hallucination Control
**Researched:** 2026-06-19
**Confidence:** HIGH

## Recommended Stack

Phase 22 should add project-owned reasoning-kernel DTOs and services on top of the existing FastAPI/PostgreSQL/Pydantic/LangGraph stack. It should not add a new RAG framework, search backend, reranker package, queue, vector database, or external verifier service by default.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Existing Python + Pydantic DTO layer | Python `>=3.12`; Pydantic v2 via current FastAPI stack | Define `RagContextBundle`, `ReasoningContext`, `MaterialClaim`, `ClaimSupportResult`, `ClaimVerificationResult`, and deterministic routing enums | MOCA already uses Pydantic contracts for `EvidenceRefV1`, `KnowledgeSearchResult`, `ToolResultV2`, and prompt summaries. Phase 22 needs stricter project-owned DTOs, not another schema framework. |
| Existing `PolicyKnowledgeService` + `PolicyRetriever` protocol | Project-owned `knowledge_search_result.v2`, `retrieval.v3`, `rerank.v2` | Source of allowed policy evidence and canonical re-fetch/hash/provenance lookup | `generate_recommendation.py` already re-fetches chunk text and checks `text_hash`; move this into a reusable `ContextBuilder` instead of duplicating node-local evidence assembly. |
| Existing PostgreSQL + SQLAlchemy/Alembic | Existing project stack | Canonical policy chunks, source-block provenance, business facts, trace/replay records | Phase 22 should read existing stored evidence and provenance. No new database service is needed; do not change `EvidenceRefV1` identity or move policy/business facts into a new store. |
| Existing `ContextAssembler` + `TokenBudgetPolicy` | Project-owned | Final prompt assembly after RAG context building | Keep generic prompt assembly separate from RAG reasoning. `ContextBuilder` should emit prompt-safe policy blocks and budget trace; `ContextAssembler` should still decide cross-source prompt block inclusion. |
| Existing LangGraph deterministic routers | `langgraph>=0.4` from `pyproject.toml` | Route verifier failures to regenerate, refuse, manual review, risk, approval, or final response | Contract-spec requires routers to be deterministic and side-effect free. Verifier output should be state consumed by routers, not an LLM routing decision. |
| Existing OpenAI-compatible structured LLM path | `openai>=1.30`, `langchain-openai>=0.3`, `langchain-core>=0.3` | Generate structured `MaterialClaim` output and perform Level 3 semantic support only when risk-triggered | The current stack already uses `ChatOpenAI.with_structured_output`. Reuse it for bounded Level 3 semantic checks; do not introduce a verifier provider or cross-encoder in Phase 22. |
| Existing pytest/eval scripts | `pytest>=8.0`, `pytest-asyncio>=0.23` | Hallucination-control contract tests and golden evals | Current eval already covers RAG and agent flows. Extend it with claim support, refusal/manual-review routing, and authority-boundary cases instead of adding RAGAS/TruLens/DeepEval now. |

### Supporting Libraries

No new runtime package is recommended for Phase 22. Use the existing Python standard library and project dependencies:

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unicodedata`, `re`, `difflib` | Python 3.12 stdlib | Text normalization, exact/near-span matching, lexical support heuristics | Level 2 support checks should be deterministic, cheap, and testable before any LLM judge is considered. |
| Existing `src.knowledge.text_hash` | `evidence_text_hash.v1` | Verify canonical chunk text still matches `EvidenceRefV1.text_hash` | Level 1 always runs hash validation through re-fetched content, not prompt text. |
| Existing `src.knowledge.provenance` | Project-owned | Read prompt-safe source-block/OCR labels after tenant/hash verification | Use for OCR-low-confidence and source locator risk labels. Keep raw provenance/debug fields out of ordinary prompts and answers. |
| Existing `ToolResultV2` / `BusinessFactRefV1` | `tool_result.v2`, `business_fact_ref.v1` | Bind business fact claims to Tool System outputs | Business facts are not policy evidence and must not be converted into `EvidenceRefV1`. |
| Existing `EvidenceRefV1` / citation validator | `evidence_ref.v1`, `citation_validator.v2` | Level 1 citation membership foundation | Keep membership validation as a necessary but insufficient gate; add claim support verification next to it, not by redefining it. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Existing `pytest` suites | Unit and contract tests for DTOs, ContextBuilder, verifier, routing, and eval helpers | Add focused tests under `tests/knowledge/` and `tests/agent/`. Mock Level 3 LLM output in unit tests. |
| Existing golden-set eval runners | Hallucination-control regression reports | Extend `scripts/eval_agent.py`, `scripts/eval_rag.py`, or add a small `scripts/eval_hallucination_control.py` that reuses their JSONL/report conventions. |
| Existing `ruff` | Linting | No new lint or type-check tooling required. |

## Installation

```bash
# No Phase 22 runtime package additions recommended.
uv sync

# Expected verification entry points during implementation.
uv run pytest tests/knowledge tests/agent
uv run python scripts/eval_all.py
```

If a later implementation proposes any package addition, treat it as a scope exception requiring current-version verification and a written rationale. Phase 22 should be implementable with the existing dependencies in `pyproject.toml`.

## Required Project-Owned Additions

| Addition | Suggested Location | Purpose | Notes |
|----------|--------------------|---------|-------|
| `ContextBuilder` | `src/knowledge/context_builder.py` | Build bounded RAG context after retrieval and before recommendation/final reasoning | Inputs: candidate `EvidenceRefV1`, business fact refs/summaries, trusted context, risk/conflict hints, budget. Outputs: prompt-safe bundle plus internal reasoning context. |
| `RagContextBundle` | `src/knowledge/schemas.py` or `src/knowledge/reasoning_schemas.py` | Prompt-safe evidence snippets, citation map, labels, exclusions, budget trace | This is allowed into prompts. It must exclude verifier trace, raw OCR/source-block debug, raw tool output, and private provenance fields. |
| `ReasoningContext` | Same reasoning schema module | Internal evidence/business context for verifier and routing | May include verified refs, full bounded text, safe provenance labels, exclusion reasons, and risk labels. It is not ordinary user-facing text. |
| `MaterialClaim` | Same reasoning schema module | Structured claim taxonomy | Use exactly three authority classes: `policy_claim`, `business_fact_claim`, `action_recommendation_claim`. Add subtypes only as secondary fields if useful. |
| `ClaimSupportVerifier` | `src/knowledge/claim_verifier.py` | Level 1/2/3 verification policy engine | Deterministic gates first; Level 3 semantic check only after Level 1 passes and risk triggers require it. |
| `ClaimVerificationResult` | Reasoning schema module | Verifier output consumed by routers and final response | Include per-claim status, failure code, support level used, routing action, and redacted reason. Do not make it a replacement for `EvidenceRefV1`. |
| Hallucination eval dataset | `evaluation/golden/` or `eval/` following existing conventions | Faithfulness/citation/routing/authority regression cases | Include stale evidence, conflict, OCR-low-confidence, business-fact hallucination, memory/evidence separation, and action recommendation missing support. |

## Integration with Existing MOCA Boundaries

| Boundary | Recommendation | Rationale |
|----------|----------------|-----------|
| Evidence identity | Preserve `EvidenceRefV1` exactly | `EvidenceRefV1` remains canonical for policy evidence, snapshots, replay, and citation membership. Do not add page/bbox/OCR/material-claim fields to it. |
| Context assembly | Move node-local evidence re-fetch from `generate_recommendation.py` into `ContextBuilder` | Recommendation, final response, verifier, and future answer nodes need one shared source of hash-checked evidence context. |
| Prompt safety | Feed only `RagContextBundle` into `ContextAssembler` | The generic assembler should never receive raw provenance traces, verifier internals, source-block debug, raw tool results, or authority objects. |
| Policy claim support | `policy_claim` requires cited `EvidenceRefV1` and verified context membership/hash/scope/freshness | Membership alone is not semantic support; Level 2/3 must decide whether the claim text is actually supported. |
| Business fact support | `business_fact_claim` requires `BusinessFactRefV1` from `ToolResultV2` | Business facts remain Tool System outputs. They cannot be embedded as policy chunks or assigned to `EvidenceRefV1`. |
| Action recommendation support | `action_recommendation_claim` requires both policy support and business fact support | This still does not authorize execution. Risk gate, approval gate, action draft, and Phase 17 external execution boundaries remain authoritative. |
| Memory | Treat profile/session/case memory as contextual hints only | Memory can help phrasing or slot continuity, but cannot satisfy policy evidence, current business fact, approval, action, replay, or audit requirements. |
| Routing | Add verifier result fields read by `route_after_recommendation` and risk/final nodes | Routers should map `unsupported`, `insufficient`, `conflicting`, `stale`, `unauthorized`, `hash_mismatch`, and `manual_review_needed` deterministically. |
| Eval/debug | Keep detailed verifier trace out of prompts and ordinary answers | Store only redacted summaries in trace/eval output. Use full trace in test artifacts or internal debug paths if needed. |

## Verification Stack

| Level | Stack | Checks | Routing Output |
|-------|-------|--------|----------------|
| Level 1 always | Existing Pydantic DTOs, `validate_membership`, `evidence_text_hash`, trusted context | Citation membership, tenant match, scope/ACL projection, hash match, duplicate key rejection, freshness/effective-time labels | `allow_next_check`, `regenerate`, `refuse`, or `manual_review` depending on failure code |
| Level 2 ordinary claims | Python stdlib normalization/span/lexical checks | Exact span support, normalized phrase support, required-term overlap, contradiction keywords for known policy patterns, business-ref presence | `supported`, `unsupported`, or `ambiguous` |
| Level 3 risk-triggered | Existing `ChatOpenAI.with_structured_output` behind `ClaimSupportVerifier` | Semantic support only for high-risk, action, conflict, stale, OCR-low-confidence, ambiguous, or compensation/penalty claims | `allow`, `regenerate`, `refuse`, or `manual_review`; timeout/error fails closed |

Level 3 must have explicit claim count, evidence count, character/token budget, timeout, retry count, and config-version fields before implementation. It must not rerank retrieval results or replace deterministic Level 1 gates.

## Installation Impact

Phase 22 should not need:

- New Python packages.
- New Docker services.
- New PostgreSQL extensions.
- New model providers.
- New background workers.
- New frontend dependencies.

The likely code changes are new DTO/service modules, modifications to recommendation/final-response/routing nodes, and expanded tests/evals.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Project-owned `ContextBuilder` | LlamaIndex/LangChain RAG context chain | Only if a future milestone intentionally delegates MOCA's evidence contracts to a framework. Phase 22 needs exact `EvidenceRefV1`, ToolResult, approval, and replay semantics. |
| Deterministic Level 2 lexical/span checks | Cross-encoder or model reranker | Phase 23 owns reranker/query rewrite. Claim support verification must not become relevance reranking. |
| Existing OpenAI-compatible LLM for Level 3 | Dedicated verifier API/provider | Use only if Phase 22 eval proves current model path cannot meet reliability/latency needs. That would need current-version and cost research. |
| Existing eval scripts + pytest | RAGAS, TruLens, DeepEval | Consider later for broad research benchmarking. Phase 22 needs deterministic safety gates and golden contract cases more than stochastic aggregate judging. |
| Existing trace/replay surfaces | New claim-verification database tables | Add tables only if roadmap requires long-term claim-level audit queries. For Phase 22, redacted trace/eval artifacts are enough. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Query rewrite | Explicit Phase 23 scope | Use existing retrieval results and ContextBuilder filtering/labeling only. |
| Cross-encoder/model reranking or external rerank APIs | Explicit Phase 23 scope and would mix relevance ranking with support verification | Keep Level 2 deterministic; Level 3 judges support only after evidence is selected. |
| Vespa/OpenSearch/new vector DB/new search backend | Explicit RAG-5 scope | Existing PostgreSQL hybrid retrieval through `PolicyKnowledgeService`. |
| New `EvidenceRefV1` variant or added identity fields | Breaks canonical evidence identity and action snapshot/replay assumptions | Keep provenance and claim support as side-path DTOs keyed by existing refs. |
| Business tool outputs as policy evidence | Violates Tool System boundary | Use `BusinessFactRefV1` and `ToolResultV2` for business facts. |
| Memory as claim authority | Violates memory boundary | Use memory only as contextual assistance; require evidence/tool refs for material claims. |
| New action execution path | Phase 17 owns external execution | Verifier can block or route action recommendations, but cannot authorize execution. |
| Source upload/review UI | Policy Source Operations scope | Use existing persisted parser/OCR provenance labels for verification. |
| Raw provenance/debug in prompts | Leaks internal metadata and weakens prompt boundary | Use prompt-safe `RagContextBundle` labels only. |

## Stack Patterns by Variant

**Policy-only answer:**
- Build `RagContextBundle` from retrieved `EvidenceRefV1`.
- Require at least one `policy_claim`.
- Run Level 1 and Level 2.
- Route unsupported/no-evidence to insufficient evidence response, not free-form completion.

**Troubleshooting answer:**
- Build `ReasoningContext` with both policy evidence and `BusinessFactRefV1` values.
- Require separate `policy_claim` and `business_fact_claim` records.
- Final answer may combine them only through a supported `action_recommendation_claim` or explanatory recommendation.

**Action or compensation recommendation:**
- Require `strong_evidence` plus business facts.
- Run Level 3 if high-risk, compensation, penalty, stale/conflict, OCR-low-confidence, or ambiguous.
- Verifier success still only permits risk/approval evaluation; it never bypasses approval/action boundaries.

**Conflict, stale, unauthorized, hash mismatch, or OCR-low-confidence evidence:**
- Label in `ReasoningContext`.
- Do not let the model silently choose.
- Route conflict/stale/OCR-low-confidence high-risk cases to manual review; route unauthorized/hash mismatch to refuse or regenerate depending on whether fresh authorized context can be rebuilt.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Phase 22 additions | Existing `pyproject.toml` dependencies | No new package versions are recommended. |
| Pydantic DTOs | FastAPI/Pydantic v2 stack | Keep `extra="forbid"` on authority-bearing DTOs where the repo already uses it for tool contracts. |
| `ContextBuilder` | `PolicyKnowledgeService.get_verified_evidence_contents` and `get_verified_evidence_provenance` | Reuse tenant/hash-checked lookup methods. Extend retriever protocol only if missing metadata is required. |
| `ClaimSupportVerifier` | Existing `ChatOpenAI.with_structured_output` | Level 3 should be optional/risk-triggered and fail closed on validation error, timeout, or malformed model output. |
| Hallucination eval | Existing JSONL golden sets and eval reports | Add metrics without replacing Hit@5/fallback/citation membership gates. |

## Sources

- `.planning/PROJECT.md` - v1.5 scope, hard boundaries, existing stack, and shipped v1.3/v1.4 capabilities. HIGH confidence.
- `docs/rag-architecture-spec.md` sections 4.1, 4.2, 9.5, 11, 12, 13 - Context Builder, Reasoning Kernel, freshness/authority/conflict labels, hallucination-control levels, and eval categories. HIGH confidence.
- `docs/contract-spec.md` sections 8.3, 8.4, 9.5, 12.5 - canonical `EvidenceRefV1`, `BusinessToolService`, `ToolResultV2`, `BusinessFactRefV1`, deterministic routers, memory/action boundaries. HIGH confidence.
- `src/knowledge/schemas.py` - current `EvidenceRefV1`, `KnowledgeSearchResult`, membership result DTOs, and canonical evidence projection. HIGH confidence.
- `src/knowledge/service.py` - existing evidence re-fetch, tenant/hash validation, and verified provenance lookup. HIGH confidence.
- `src/agent/context/assembler.py` and `src/agent/context/budget.py` - existing prompt-safe block assembly and protected prompt budget behavior. HIGH confidence.
- `src/agent/nodes/generate_recommendation.py` - current node-local evidence re-fetch, allowed citations, and membership-only material claim projection to replace with ContextBuilder/verifier. HIGH confidence.
- `src/knowledge/citation.py` and `tests/knowledge/test_citation_membership.py` - citation membership is intentionally not semantic support. HIGH confidence.
- `src/tools/contracts.py` - current `ToolResultV2` and `BusinessFactRefV1` code contract. HIGH confidence.
- `pyproject.toml` - existing dependency ranges; no new Phase 22 dependency recommended. HIGH confidence.

## Orchestrator Summary

Phase 22 should be a project-owned reasoning-kernel extension, not a dependency or backend change. Add `ContextBuilder`, prompt-safe `RagContextBundle`, internal `ReasoningContext`, `MaterialClaim`, and `ClaimSupportVerifier`; integrate them into recommendation/final-response routing and eval. Preserve `EvidenceRefV1`, Tool System business refs, memory boundaries, approval/action gates, PostgreSQL hybrid retrieval, and Phase 23/17/RAG-5 deferrals.

---
*Stack research for: MOCA v1.5 Phase 22 RAG Context Builder + Hallucination Control*
*Researched: 2026-06-19*
