# Project Research Summary

**Project:** MOCA - Merchant Operations Collaborative Agent
**Domain:** v1.5 Phase 22 RAG Context Builder + Hallucination Control
**Researched:** 2026-06-19
**Confidence:** HIGH, with MEDIUM uncertainty for concrete Level 3 semantic-verifier quality and thresholds

## Executive Summary

MOCA is an enterprise-style merchant operations agent for refund disputes, rule inquiries, compensation decisions, and support workflows. Expert-grade systems in this domain do not rely on "retrieved chunk plus citation" as proof. They separate retrieval from reasoning, build a prompt-safe context boundary, decompose answers into material claims, verify each claim against the correct authority source, and route unsafe outputs deterministically before any high-risk action path can continue.

The recommended Phase 22 approach is a bounded Reasoning Kernel inserted after the existing v1.3 hybrid retrieval and v1.4 parser/OCR provenance layers, and before recommendation, final response, risk, approval, or action-draft reasoning. Build project-owned DTOs and services: `ContextBuilder`, `RagContextBundle`, `ReasoningContext`, `MaterialClaim`, `ClaimSupportVerifier`, and deterministic verifier routing. Reuse the existing FastAPI/PostgreSQL/Pydantic/LangGraph/OpenAI-compatible stack, existing `PolicyKnowledgeService`, existing `ContextAssembler`, and existing eval/test conventions. Do not add a new RAG framework, search backend, reranker, vector database, queue, external verifier provider, or frontend source-operations UI.

The key risks are authority collapse, treating citation membership as semantic support, fail-open context assembly, conflict/freshness labels that do not affect routing, provenance/debug leakage, Phase 23/17/RAG-5 scope creep, unbounded semantic-verifier latency/cost, and evals that only test happy-path answers. Mitigate these with typed authority refs, always-on deterministic Level 1 gates, low-cost Level 2 support checks, risk-triggered Level 3 semantic checks with strict budgets, fail-closed routes, separate prompt/verifier/debug/final-response projections, static scope guards, and negative golden evals that prove refusal/manual-review behavior.

## Key Findings

### Recommended Stack

Phase 22 should be implemented with the existing MOCA stack plus new project-owned reasoning-kernel modules. The research consistently recommends no new runtime packages, no new Docker services, no new PostgreSQL extensions, no new model providers, and no new frontend dependencies for the core Phase 22 launch. The central engineering move is to consolidate evidence re-fetch, hash/tenant validation, prompt-safe citation mapping, claim support checks, and verifier routing into reusable code instead of duplicating logic inside `generate_recommendation`.

**Core technologies:**
- Existing Python 3.12 + Pydantic v2 DTO layer: define `RagContextBundle`, `ReasoningContext`, `MaterialClaim`, `ClaimVerificationResult`, and route enums - matches current contract-driven code and avoids a new schema framework.
- Existing `PolicyKnowledgeService` and `PolicyRetriever` protocol: source of canonical policy evidence, verified content re-fetch, `text_hash` checks, and provenance lookup - keeps repository details out of agent nodes.
- Existing PostgreSQL + SQLAlchemy/Alembic: authoritative store for policy chunks, source-block provenance, business facts, trace, and replay records - no new database service is needed.
- Existing `ContextAssembler` and `TokenBudgetPolicy`: final prompt assembly after RAG-specific context building - keep generic prompt assembly separate from RAG reasoning.
- Existing LangGraph deterministic routers: route verifier outcomes to allow, regenerate, refuse, manual review, risk/approval, or final response - routers remain pure and side-effect free.
- Existing OpenAI-compatible structured LLM path: use `ChatOpenAI.with_structured_output` only for bounded Level 3 semantic support when risk triggers justify it - not as a reranker or retrieval scorer.
- Existing pytest and eval scripts: add contract tests and golden hallucination-control evals - avoid adopting RAGAS/TruLens/DeepEval as Phase 22 dependencies.

### Expected Features

Phase 22 must make "evidence-backed" mean claim-supported, not merely citation-present. It should build one shared reasoning context from candidate `EvidenceRefV1` values, current business facts, trusted run/tenant context, and risk/provenance labels, then verify generated claims before final answer or action paths.

**Must have (table stakes):**
- Reusable `ContextBuilder` contract - one shared evidence assembly path for recommendation, final response, verifier, and future answer nodes.
- Canonical evidence content re-fetch - move current node-local re-fetch into the builder through `PolicyKnowledgeService`.
- Level 1 deterministic evidence gates - citation membership, tenant/scope/ACL where available, `text_hash`, duplicate-key, freshness/effective-time, and authority/source-type checks.
- Prompt-safe citation map - stable citation IDs mapped to canonical `EvidenceRefV1` values and bounded snippets, without raw debug/provenance internals.
- Token budget trace with protected metadata - trim snippet text without dropping citation identity or labels.
- Deduplication and safe adjacent-chunk merge - reduce context waste while preserving traceability to canonical refs.
- Freshness, authority, conflict, and OCR-risk labels - use Phase 21 provenance and policy metadata as route-affecting safety signals, not decorative labels.
- `MaterialClaim` taxonomy - exactly three primary authority classes: `policy_claim`, `business_fact_claim`, and `action_recommendation_claim`.
- Authority binding rules - policy claims require `EvidenceRefV1`; business fact claims require `BusinessFactRefV1` or safe `ToolResultV2` refs; action recommendations require both and still cannot authorize execution.
- Level 2 lexical/span support checks - ordinary material claims need deterministic support validation stronger than membership.
- Level 3 semantic support verifier - only for high-risk, action, conflict, stale, OCR-low-confidence, or ambiguous cases, with explicit budgets and fail-closed behavior.
- Deterministic failure routing - unsupported, insufficient, conflicting, stale, unauthorized, hash-mismatched, scope-invalid, and manual-review-needed outcomes route through code-owned actions.
- Node integration - `generate_recommendation`, `final_response`, and `assess_risk_and_approval` must honor verifier output so unsupported claims cannot produce `proposed_action`, approval snapshots, or action drafts.
- Hallucination-control eval suite - cover faithfulness, citation support, refusal/manual-review routing, stale/conflict/OCR traps, business-data hallucination, memory/evidence/action authority separation, and action recommendations missing support.
- Prompt/debug boundary tests - prove raw tool payloads, retrieval debug fields, source-block/OCR raw metadata, verifier traces, and unbounded policy text do not enter ordinary prompts or final responses.

**Should have (competitive):**
- Reasoning Kernel as a first-class product boundary - makes behavior explainable as `Evidence -> MaterialClaim -> Answer/Refusal/ManualReview`.
- Claim-level authority graph - maps conclusions to policy refs, business fact refs, and action/risk constraints for audit and eval.
- Risk-triggered semantic verification - applies stronger checks where wrong answers have business impact without making every answer expensive.
- Conflict-aware answer degradation - unresolved policy conflict routes to manual review or safe refusal instead of silent model choice.
- Action recommendation proof chain - verified support remains separate from approval and execution authority.
- Budget trace as a regression artifact - lets tests assert protected metadata, exclusions, and pruning behavior.
- Maintainer-facing verifier trace - useful for debugging if kept out of ordinary API responses and prompts.

**Defer (named owner required before build):**
- Query rewrite, model reranking, cross-encoder reranking, external rerank APIs, ranking ablation, and retrieval latency tuning - owner: Phase 23 RAG Reranker + Query Rewrite.
- Real external action execution, outbox, reconciliation, external idempotency, and compensation dispatch - owner: Phase 17 External Action Execution.
- External `SearchBackend`, Vespa/OpenSearch, or a new vector database service - owner: Phase RAG-5 Optional External Search Backend.
- Policy source upload/review/lifecycle UI, source document viewer, and admin review workflows - owner: Policy Source Operations.
- `EvidenceRefV1` identity changes, source-block identity as evidence, business facts as policy evidence, or memory as claim authority - not allowed in Phase 22.
- Always-on semantic verification for all low-risk FAQ/policy QA - future hardening only if eval and latency data prove the need.

### Architecture Approach

Phase 22 should add a retrieval-after, reasoning-before evidence kernel. Current retrieval remains `investigate -> search_policy -> PolicyKnowledgeService.search(...) -> PolicyRetrievalEngine -> KnowledgeSearchResult.evidence_refs`. The new kernel consumes those candidate refs, re-fetches canonical content and safe provenance through the Knowledge facade, builds a prompt-safe `RagContextBundle`, carries current business fact refs into a `ReasoningContext`, normalizes/generates `MaterialClaim[]`, verifies support through Level 1/2/3, and emits a deterministic route for the graph.

**Major components:**
1. `src/agent/rag_context/schemas.py` - runtime DTOs for bundles, evidence context items, citation map entries, material claims, verifier results, and route enums.
2. `src/agent/rag_context/builder.py` - `ContextBuilder` that validates, filters, dedupes, labels, and budgets already-retrieved evidence refs.
3. `src/agent/rag_context/budget.py` - evidence-specific snippet budgeting that protects citation metadata and records exclusions/truncation.
4. `src/agent/rag_context/claims.py` - compatibility adapter from current `RecommendationDraft` plus native structured `MaterialClaim` normalization and authority validation.
5. `src/agent/rag_context/verifier.py` - tiered verifier for Level 1 deterministic gates, Level 2 lexical/span checks, and risk-triggered Level 3 semantic checks.
6. `src/agent/rag_context/routing.py` - pure mapping from verifier status/reason codes to `allow`, `regenerate`, `refuse`, or `manual_review`.
7. `src/knowledge/service.py` and `src/repositories/policy_chunk_repo.py` - narrow verified context lookup additions only if current helpers lack needed metadata.
8. `src/agent/nodes/generate_recommendation.py` - replace local evidence re-fetch and allowed-citation construction with ContextBuilder, claims, and verifier integration.
9. `src/agent/routing.py` and `src/agent/graph.py` - add or wire `route_after_recommendation` from verifier action to risk/approval or final response.
10. `src/agent/nodes/final_response.py` and `src/agent/nodes/assess_risk_and_approval.py` - render deterministic fail states and ensure only supported action claims reach action snapshot creation.
11. `src/agent/state.py` - add per-turn `rag_context`, `material_claims`, `claim_verification`, `verification_route`, and safe manual-review fields, reset every turn.

### Critical Pitfalls

1. **Authority collapse across policy, business, memory, and actions** - avoid a generic `refs` field; enforce typed claim support and prove memory/business refs cannot satisfy policy claims.
2. **Citation membership treated as semantic support** - keep `validate_membership` membership-only; add separate Level 2/3 claim support verification and unsupported-but-cited tests.
3. **ContextBuilder fails open on re-fetch, hash, tenant, or scope failures** - every rejected ref needs an exclusion reason and route impact; missing verified content cannot support material policy claims.
4. **Freshness, authority, conflict, or OCR labels do not affect routing** - stale/conflicting/low-confidence high-risk evidence must refuse or route to manual review unless deterministic authority rules resolve it.
5. **Prompt/debug/provenance boundary drift** - keep raw source-block/OCR data, retrieval ranks, hashes, verifier prompts/rationales, and debug traces out of ordinary prompts, user answers, memory, replay, business facts, and action snapshots.
6. **Scope creep into Phase 23, Phase 17, or RAG-5** - ContextBuilder may validate/filter/label/budget incoming refs, but must not rewrite queries, rerank, call new search backends, or execute real actions.
7. **Semantic verifier cost and latency blow up** - Level 3 must have claim/evidence/token/time/retry budgets, risk triggers, timeout metrics, and fail-closed behavior.
8. **Verifier output remains advisory** - graph routers, final response, risk gate, approval, and action snapshot creation must consume route enums so unsupported claims cannot still complete.
9. **Eval misses negative boundary cases** - golden cases must assert expected claims, support refs, verifier status, final route, and forbidden leakage, not only answer fluency.

## Implications for Roadmap

Based on research, suggested Phase 22 work-package structure:

### Phase 22.1: Reasoning Kernel Contracts, State, and Scope Guards

**Rationale:** Typed contracts and reset rules must exist before builder, verifier, or graph integration. This phase also locks the non-overlap boundaries so later implementation cannot accidentally become Phase 23, Phase 17, RAG-5, or Policy Source Operations.

**Delivers:** `rag_context` package skeleton; DTOs for `RagContextBundle`, `ReasoningContext`, `EvidenceContextItem`, `CitationMapEntry`, `MaterialClaim`, `ClaimVerificationResult`, route enums, and exclusion/status codes; per-turn state fields and reset behavior; static or contract tests preserving `EvidenceRefV1`, `BusinessFactRefV1`, `ToolResultV2`, memory, replay, and action-snapshot boundaries.

**Addresses:** MaterialClaim taxonomy, authority separation, prompt/debug boundary foundation.

**Avoids:** Authority collapse, `EvidenceRefV1` identity drift, generic refs, stale state leakage, and scope creep.

### Phase 22.2: Verified Evidence Context Lookup

**Rationale:** ContextBuilder can only be safe if it obtains canonical text and provenance labels through tenant/hash-checked Knowledge facade methods. Repository details should not leak into agent nodes.

**Delivers:** Narrow `PolicyKnowledgeService` helper for verified context rows if existing helpers are insufficient; batched lookup by candidate `EvidenceRefV1`; safe title/section/page labels; freshness/effective-time inputs; OCR/provenance label inputs; tests for tenant mismatch, missing content, duplicate keys, hash mismatch, stale/unauthorized refs, and no schema change to `EvidenceRefV1`.

**Addresses:** Canonical evidence re-fetch, Level 1 evidence gates, provenance side-path consumption.

**Avoids:** Builder fail-open behavior, direct repository access from nodes, source-block identity as authority, and raw provenance in prompts.

### Phase 22.3: ContextBuilder, Citation Map, Budgeting, and Projections

**Rationale:** The prompt-safe evidence bundle is the core dependency for claim generation, verifier input, final response citations, and eval artifacts. It must be deterministic before semantic checks are added.

**Delivers:** `ContextBuilder.build(...)` from incoming candidate refs to `RagContextBundle`; stable citation IDs; included/excluded evidence records; deduplication; safe adjacent-chunk merge; bounded snippets; protected citation metadata; token budget trace; freshness/authority/conflict/OCR labels; prompt/verifier/debug/final-response projections; tests proving no retrieval/search/rerank calls and no debug/provenance leaks.

**Addresses:** Prompt-safe citation map, token budget trace, dedupe/merge, labels, context assembly.

**Avoids:** Query rewrite/reranking creep, prompt/debug drift, token budgeting that drops citation identity, and conflict/OCR labels hidden in trace only.

### Phase 22.4: Recommendation Integration with ContextBuilder

**Rationale:** Replace the current local evidence snippet and allowed-citation logic before adding heavier claim verification. This creates one shared path while preserving current safe fallback behavior during migration.

**Delivers:** `generate_recommendation` consumes `RagContextBundle.prompt_policy_snippets()` through `ContextAssembler`; local re-fetch code removed or quarantined behind builder; existing membership validation preserved temporarily as Level 1 input; no-evidence, retrieval-error, and citation-invalid behavior kept deterministic; node tests updated for prompt safety, bounded snippets, cross-tenant/hash failures, and safe final state.

**Addresses:** Shared evidence context, prompt-safe generation input, existing behavior preservation.

**Avoids:** Duplicate evidence assembly, builder plus legacy logic divergence, and regression in current citation/fallback paths.

### Phase 22.5: MaterialClaim Generation and Level 1/2 Claim Verification

**Rationale:** Most hallucination control value comes from separating material claims and checking ordinary support deterministically. This should land before semantic Level 3 so the model judge does not mask missing contract logic.

**Delivers:** Adapter from current `RecommendationDraft` to minimal `MaterialClaim[]`; native structured claim output when stable; authority validation by claim type; Level 1 gates for membership, tenant/scope/hash/freshness, business refs, and authority separation; Level 2 lexical/span/numeric/date/entity support checks over cited snippets; unsupported-but-cited fixtures; typed `supported`, `unsupported`, `insufficient`, `ambiguous`, and failure reason outputs.

**Addresses:** Policy/business/action authority binding, membership-vs-support split, low-cost support verification.

**Avoids:** Membership-as-support, business data hallucination, memory-as-authority, policy-only action recommendations, and vague keyword-only validation.

### Phase 22.6: Deterministic Routing, Final Response, and Action Boundary Hardening

**Rationale:** Verifier output matters only if it controls graph behavior. Non-allow routes must bypass risk/approval/action paths and render safe, deterministic user-facing outcomes.

**Delivers:** Pure `route_after_recommendation`; route mapping for allow, regenerate, refuse, and manual review; one bounded regeneration path if scoped; deterministic final-response templates for insufficient, unsupported, stale, conflicting, unauthorized, hash-mismatched, business-fact-missing, and manual-review outcomes; risk/approval guard requiring supported action claims; tests proving non-allow routes cannot create `proposed_action`, approval requests, action drafts, or `ActionSafetySnapshot`.

**Addresses:** Deterministic failure routing, safe final responses, risk/approval integration.

**Avoids:** Advisory verifier output, unsupported claims reaching final/action paths, LLM-decided escalation, and manual-review as a generic system error.

### Phase 22.7: Risk-Triggered Level 3 Semantic Support

**Rationale:** Semantic support is needed for high-risk, action, conflict, stale, OCR-low-confidence, and Level 2 ambiguous cases, but it should be introduced only after deterministic gates and routing are already stable.

**Delivers:** Bounded structured semantic verifier over claim text and cited snippets only; trigger policy for high-risk/action/conflict/stale/OCR/ambiguous cases; strict max claims, max evidence refs per claim, max chars/tokens, deadline, retry count, config version, latency metrics, timeout/error fail-closed route, and mocked unit tests plus integration tests with fake slow/erroring verifier.

**Addresses:** Risk-triggered semantic verification and high-impact support judgments.

**Avoids:** Always-on verifier cost, whole-prompt judging, semantic verifier as reranker, provider timeout fail-open behavior, and opaque action authorization.

### Phase 22.8: Hallucination-Control Eval and Acceptance Gate

**Rationale:** Phase 22 should close only when negative and boundary cases prove the system refuses or escalates correctly, not merely when supported answers look fluent.

**Delivers:** Golden cases for `policy_claim_supported`, invalid citation membership, unsupported-but-cited semantic failure, business fact required, action missing policy support, action missing business support, policy conflict, stale policy version, OCR-low-confidence trap, prompt/debug leakage, memory authority boundary, unauthorized/hash-mismatched refs, and Level 3 timeout; metrics for faithfulness by claim type, citation support accuracy, refusal/manual-review accuracy, business hallucination rate, action support completeness, leakage count, Level 3 trigger rate, timeout rate, and fail-closed rate.

**Addresses:** Blocking hallucination-control eval, prompt/debug leakage tests, release confidence.

**Avoids:** Happy-path-only evals, answer-text-only acceptance, missing route assertions, and unmeasured Level 3 cost/failure behavior.

### Phase Ordering Rationale

- Start with contracts because every later component depends on the same authority taxonomy, route enums, and state reset rules.
- Add verified context lookup before ContextBuilder so builder logic is tenant/hash/scope-safe from the beginning.
- Build prompt-safe context and projections before claim generation so the LLM and verifier consume the same bounded evidence surface.
- Integrate ContextBuilder before semantic verification to remove duplicated evidence assembly and expose regressions while behavior is still mostly deterministic.
- Implement MaterialClaim and Level 1/2 before Level 3 so deterministic support checks, failure reasons, and route effects are not hidden behind a model judge.
- Wire routing and action guards before Level 3 so any verifier failure already fails closed.
- Add Level 3 late and narrowly because it is the least certain piece for latency, cost, and reliability.
- Finish with eval and leakage gates because the core success criterion is safe outcome selection under missing, conflicting, stale, unauthorized, low-confidence, and unsupported evidence.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 22.7:** Needs targeted research or current-version verification for concrete structured-output model behavior, timeout/retry options, cost/latency budgets, and semantic-verifier calibration. Any new package or provider proposal must be separately justified.
- **Phase 22.8:** Needs careful design of eval thresholds and release gates if the team wants quantitative pass/fail metrics beyond deterministic golden routes.
- **Phase 22.3:** May need narrow implementation research if current Phase 21 metadata does not expose enough authority/conflict/OCR labels; default behavior should be `unknown` plus manual-review routing for high-risk ambiguity, not new ranking.

Phases with standard patterns (skip research-phase unless implementation uncovers surprises):
- **Phase 22.1:** Pydantic DTOs, route enums, state fields, and contract guards follow established MOCA patterns.
- **Phase 22.2:** Verified lookup should follow existing `PolicyKnowledgeService` content/provenance helper patterns.
- **Phase 22.4:** Node integration follows current `generate_recommendation`, `ContextAssembler`, and citation-membership test patterns.
- **Phase 22.5:** Level 1 gates and Level 2 lexical/span checks are deterministic local code and should be planned from current contracts.
- **Phase 22.6:** Router/final-response/action-boundary hardening is established LangGraph/state-machine work in MOCA.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Strong agreement across research and project context: existing Python/Pydantic/FastAPI/PostgreSQL/LangGraph/OpenAI-compatible stack is sufficient; no new runtime dependency is recommended. |
| Features | HIGH | Table stakes and deferrals are anchored in `.planning/PROJECT.md`, current code gaps, `docs/contract-spec.md`, and the v1.3/v1.4 shipped boundaries. Level 3 verifier model quality remains MEDIUM until measured. |
| Architecture | HIGH | Component boundaries map directly to existing `PolicyKnowledgeService`, `ContextAssembler`, `generate_recommendation`, routing, final response, risk/approval, state, and eval surfaces. |
| Pitfalls | HIGH | Most risks are already visible in current code and contracts: membership-only citation validation, node-local re-fetch, authority separation, prompt projection, and action snapshot boundaries. Semantic verifier behavior remains MEDIUM. |

**Overall confidence:** HIGH for Phase 22 shape and boundaries; MEDIUM for the final Level 3 semantic verifier configuration until implementation/eval data exists.

### Gaps to Address

- Level 3 semantic verifier budgets and thresholds: define max claims, refs, chars/tokens, timeout, retries, trigger policy, and fail-closed route during Phase 22.7 planning.
- Authority/conflict metadata completeness: current code may not expose full `authority_level` or `supersedes_doc_id`; label missing data as `unknown` and route high-risk ambiguity to manual review rather than adding reranking or precedence logic.
- Business fact ref coverage: verify current `ToolResultV2` and `BusinessFactRefV1` surfaces provide enough provenance for business claims; if not, add narrow prompt-safe references without converting business facts into policy evidence.
- Claim generation migration: start with a compatibility adapter from current `RecommendationDraft`, then move to native `MaterialClaim[]` once tests stabilize.
- Regeneration loop scope: decide whether Phase 22 launch includes one bounded verifier-constrained regeneration attempt or defers it as stretch; never allow unbounded retries.
- Replay/debug persistence: decide how much redacted verifier status, timing, and reason-code data to store without adding raw evidence text, verifier prompts, source-block internals, or chain-of-thought.
- Eval release gates: choose blocking thresholds for unsafe answer rate, citation support accuracy, manual-review routing, business hallucination, leakage count, and Level 3 timeout fail-closed behavior.

## Sources

### Primary (HIGH confidence)

- `.planning/PROJECT.md` - v1.5 goal, Phase 22 active requirements, shipped v1.3/v1.4 dependencies, and explicit Phase 23/17/RAG-5/Policy Source Operations deferrals.
- `.planning/research/STACK.md` - stack recommendation, no-new-dependency guidance, project-owned DTO/service additions, verification stack, and Phase 22 non-overlap boundaries.
- `.planning/research/FEATURES.md` - table stakes, differentiators, anti-features, feature dependencies, MVP definition, prioritization, and Phase 22 launch/stretch/future split.
- `.planning/research/ARCHITECTURE.md` - retrieval-after/reasoning-before system architecture, component responsibilities, data flow, build order, integration boundaries, and anti-patterns.
- `.planning/research/PITFALLS.md` - critical pitfalls, technical debt patterns, integration gotchas, performance/security/UX traps, and Phase 22 verification checklist.
- `docs/contract-spec.md` - normative `TrustedContext`, `EvidenceRefV1`, `ToolResultV2`, `BusinessFactRefV1`, memory, approval/action, router, replay, and final-response boundaries cited by the research files.
- `docs/rag-architecture-spec.md` - target `ContextBuilder`, Reasoning Kernel, freshness/authority/conflict labels, hallucination-control levels, and eval categories cited by the research files.
- Current code references cited by research: `src/knowledge/schemas.py`, `src/knowledge/service.py`, `src/knowledge/citation.py`, `src/knowledge/provenance.py`, `src/knowledge/retrieval.py`, `src/agent/context/assembler.py`, `src/agent/context/projectors.py`, `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/final_response.py`, `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/routing.py`, `src/agent/graph.py`, `src/tools/contracts.py`, `src/db/models.py`, and `src/repositories/policy_chunk_repo.py`.
- Current tests cited by research: `tests/knowledge/test_citation_membership.py`, `tests/knowledge/test_facade_integration.py`, `tests/agent/test_nodes/test_generate_recommendation.py`, `tests/agent/test_memory_evidence_boundary.py`, and `tests/knowledge/test_phase21_boundaries.py`.

### Secondary (MEDIUM confidence)

- `docs/rag_spec_suggestion.md` - advisory RAG design synthesis supporting claim-level verification, context assembly, and membership/support separation.
- RAGTruth, ACL 2024 (`https://aclanthology.org/2024.acl-long.585/`) - external evidence that RAG systems can emit unsupported or contradictory claims even with retrieved context.
- SURE-RAG, arXiv 2026 (`https://arxiv.org/abs/2605.03534`) - external support for separating retrieval from support/refute/insufficient judgments; recent preprint, not a MOCA contract.
- RT4CHART, arXiv 2026 (`https://arxiv.org/html/2603.27752v1`) - external support for decomposing outputs into independently verifiable claims; recent preprint, not a MOCA contract.
- Ragas faithfulness/context precision docs - useful evaluation vocabulary, not a required technology choice.

### Tertiary (LOW confidence)

- None used for roadmap-critical recommendations.

---
*Research completed: 2026-06-19*
*Ready for roadmap: yes*
