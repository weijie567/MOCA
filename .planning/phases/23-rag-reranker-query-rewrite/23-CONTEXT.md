# Phase 23: RAG Reranker + Query Rewrite - Context

**Gathered:** 2026-06-20T01:45:20+08:00
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 23 improves policy retrieval quality on top of the current PostgreSQL hybrid retrieval path. It may add bounded query rewrite, original-query plus rewritten-query candidate generation, a project-owned reranker contract, deterministic/default local reranking, optional config-gated provider adapters, safe maintainer/eval diagnostics, ablation evals, and latency/fallback budgets.

This phase must preserve the already shipped boundaries from Phase 20, Phase 21, and Phase 22. Trusted tenant/scope/effective-date/doc-type/risk filters must apply before any candidate affects rank. Source-block, parser, OCR, provenance, raw provider payloads, and ranking diagnostics remain internal or maintainer/eval scoped. `EvidenceRefV1` remains the canonical policy evidence identity, and ContextBuilder plus MaterialClaimVerifier remain the grounding and authority gates after retrieval.

</domain>

<decisions>
## Implementation Decisions

### Query Rewrite Boundary
- **D-01:** Query rewrite is an additive retrieval-quality layer, not a replacement for the original user query. The original query must always be preserved and remain visible to eval/debug records.
- **D-02:** Rewrite output should be a typed internal retrieval input such as a `QueryRewritePlan`, with fields for the original query, bounded rewrite/query expansions, deterministic skip reason, safe summary, trigger/source metadata, and config version. The exact class name is planner discretion.
- **D-03:** Rewrite must never widen trusted authorization context. It cannot add or change tenant, merchant scope, role, risk, doc type, effective date, policy scope, or knowledge scope. These values come only from trusted context and caller filters.
- **D-04:** Specific, out-of-domain, unsafe, or missing-trusted-context queries should skip rewrite deterministically and continue through the existing safe hybrid retrieval/no-evidence behavior.
- **D-05:** The deterministic default path should be rule-first and local-testable. Domain synonym/alias expansion and bounded intent normalization are in scope; live LLM/provider rewrite is optional and must be disabled or skipped by default tests unless a later plan explicitly gates it.

### Candidate Generation And Merge
- **D-06:** Retrieval should run the original query channel first, then optional rewritten-query channels only when the rewrite plan is allowed. Original dense/sparse/fuzzy/RRF behavior remains the baseline fallback.
- **D-07:** Every original and rewritten channel must receive the same trusted filters already passed to `search_similar`, `search_sparse`, and `search_fuzzy`: tenant, effective date, doc type, risk level, and any current knowledge-scope equivalent.
- **D-08:** Merge/dedupe should happen before final ranking and before `EvidenceRefV1` construction. Dedupe within a tenant should key on `(doc_key, chunk_id, policy_version)`; selected-channel trace can record whether the candidate came from original or rewritten channels.
- **D-09:** Candidate limits must be deterministic and explicit per stage: original channel depth, rewrite channel count, per-rewrite channel top_k, merged candidate cap, final max results, and any diagnostic top_k.
- **D-10:** If rewrite generation, rewritten-channel retrieval, or merge logic errors or times out, the system falls back to the existing original-query hybrid retrieval or no-evidence path without weakening evidence validation.

### Reranker Contract
- **D-11:** Add a project-owned reranker interface that accepts internal bounded candidates or `PolicyRetrievalHit`-like DTOs and returns ranked candidates. It must not mutate canonical chunk content, text hashes, policy version identity, or `EvidenceRefV1` fields.
- **D-12:** Reranking belongs before `EvidenceRefV1` construction or inside a safe adapter that preserves final evidence rank and confidence semantics. It must not run after ContextBuilder as a substitute for canonical validation.
- **D-13:** The deterministic/default reranker should run without live credentials and preserve the current RRF fallback. It can build on existing lexical overlap, selected channels, RRF score, normalized confidence, section/title overlap, and safe metadata already available on retrieval candidates.
- **D-14:** Optional cross-encoder/external reranker adapters are allowed only behind config gates, provider/config version records, bounded candidate/text budgets, timeout and retry limits, and safe fallback to deterministic/default ranking.
- **D-15:** Reranker inputs must exclude raw source-block/OCR/parser internals, raw tool payloads, current business fact payloads, private reasoning, raw provider prompts, and unbounded policy text. Use bounded snippets or canonical chunk text budgets only.
- **D-16:** Reranker scores and score components are retrieval diagnostics, not verifier support. They cannot satisfy policy claims, business facts, approval evidence, or action authority.

### Diagnostics And Explanations
- **D-17:** Ranking explanations should be bounded, structured, and maintainer/eval-only. They may include selected channels, rewrite contribution, rerank contribution, rank changes, safe score components, provider/config version, fallback reason, and selected candidate IDs.
- **D-18:** Ordinary user-facing answers, prompts, memory, replay payloads, approval snapshots, and action drafts must not include raw rewrite prompts, raw provider payloads, private reasoning, parser/OCR/source-block internals, raw tool facts, unbounded policy text, or full ranking diagnostics.
- **D-19:** `KnowledgeSearchResult.query_rewrite` may carry a safe summary or compatibility value, but raw rewrite payloads and reasoning should live only in internal diagnostics/eval report structures.
- **D-20:** If API/eval schemas need diagnostic fields, add or extend internal/report-only DTOs rather than expanding `EvidenceRefV1`. Existing `EvidenceItem` excluded trace fields show the preferred pattern for non-public retrieval details.

### Eval And Latency
- **D-21:** Phase 23 needs deterministic retrieval-quality golden cases for synonym/alias queries, ambiguous merchant-support wording, underspecified questions, no-evidence/out-of-domain queries, stale/unauthorized evidence, and ranking regressions.
- **D-22:** Ablation must compare dense-only, sparse-only, fuzzy-only, current RRF baseline, rewrite-enabled, reranker-enabled, and rewrite-plus-reranker variants.
- **D-23:** Blocking metrics should include Hit@K, MRR or equivalent rank quality, citation-support compatibility, no-evidence precision, unsafe retrieval rate, fallback rate, and latency percentiles.
- **D-24:** Default tests and evals must not require live model/provider credentials. Provider adapter tests should use deterministic fakes and failure cases for timeout, provider error, malformed output, disabled provider, and budget overflow.
- **D-25:** Latency budgets should be explicit for total retrieval timeout, rewrite stage timeout, rerank stage timeout, candidate counts, text/token limits, retries, and provider/config version. Budget failure falls back to baseline retrieval or no-evidence behavior.

### Boundary Preservation
- **D-26:** Phase 23 should update existing static boundary guards to allow Phase 23-owned query rewrite/reranker symbols only in owned files, while continuing to block Phase 17 execution/outbox/compensation, RAG-5 `SearchBackend`/Vespa/OpenSearch/backend replacement, and Policy Source Operations UI.
- **D-27:** `EvidenceRefV1` field shape remains exact. Do not add rewrite, rerank, source-block, OCR, provenance, verifier, claim, business fact, or provider fields to it.
- **D-28:** ContextBuilder remains the canonical evidence validation boundary for tenant, scope, duplicate key, text hash, freshness/effective date, and latest/current version. Reranking cannot bypass or weaken this.
- **D-29:** MaterialClaimVerifier remains the authority boundary for claim support. Retrieval scores, rewrite confidence, and reranker scores are relevance signals only.
- **D-30:** Phase 23 does not expand `AgentState` authority surfaces as a substitute for the pending 17-prep AgentState cleanup. Any state additions must be redacted, retrieval-owned, and non-authoritative.

### the agent's Discretion
- Exact class and module names for query rewrite plans, reranker candidates, diagnostics DTOs, and config objects are open, provided they follow existing `src/knowledge` ownership and do not create a full external `SearchBackend`.
- Planner may choose whether to extend `scripts/eval_rag_hit_at_5.py` or create a new Phase 23 eval script, as long as ablation and latency outputs are deterministic and no-live-provider by default.
- Deterministic local reranker formula is planner/executor discretion, but it must be test-pinned and explainable through safe score components.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Active v1.6 Scope
- `.planning/ROADMAP.md` - Active Phase 23 goal, success criteria, suggested plan slices, hard boundaries, and deferred work.
- `.planning/REQUIREMENTS.md` - Phase 23 requirement set: QRW-01..QRW-05, RRK-01..RRK-06, EXP-01..EXP-04, EVAL-01..EVAL-05, BND-01..BND-06.
- `.planning/PROJECT.md` - Current milestone context, core value, shipped milestone summaries, and preserved contract boundaries.
- `.planning/STATE.md` - Current v1.6 state and pending 17-prep todo note.

### Prior Milestone Contracts
- `.planning/milestones/v1.3-ROADMAP.md` - Phase 20 hybrid retrieval foundation, RRF semantics, internal trace boundary, and Phase 23 deferral.
- `.planning/milestones/v1.4-ROADMAP.md` - Phase 21 parser/OCR/source-block provenance boundaries and Phase 23 deferral.
- `.planning/milestones/v1.5-ROADMAP.md` - Phase 22 ContextBuilder/verifier scope and explicit exclusion of Phase 23 rewrite/rerank behavior.
- `.planning/milestones/v1.5-REQUIREMENTS.md` - Phase 22 evidence, verifier, leakage, and boundary requirements that Phase 23 must preserve.
- `.planning/milestones/v1.5-MILESTONE-AUDIT.md` - Confirmation that ContextBuilder/verifier/action boundaries passed and 17-prep remains deferred.
- `.planning/milestones/v1.5-phases/22-rag-context-builder-hallucination-control/22-CONTEXT.md` - Phase 22 decisions for ContextBuilder inputs, projections, canonical validation, risk labels, verifier routes, and leakage rules.
- `.planning/milestones/v1.5-phases/22-rag-context-builder-hallucination-control/22-VERIFICATION.md` - Phase 22 verification evidence and final gate outputs.

### Normative And Architecture Docs
- `docs/contract-spec.md` - Normative `KnowledgeSearchRequest`, `KnowledgeSearchResult`, `EvidenceRefV1`, canonical hash projection, retrieval/rerank config version, AgentState evidence field ownership, memory/business/evidence separation, and action snapshot evidence rules.
- `docs/rag-architecture-spec.md` - Target RAG architecture narrative; especially the Phase RAG-4 / MOCA Phase 23 section, reranker-vs-verifier separation, ranking explanation boundaries, and RAG-5 SearchBackend deferral.
- `docs/architecture-overview.md` - Knowledge/RAG facade ownership and narrative mapping to `docs/contract-spec.md`.

### Retrieval Implementation
- `src/knowledge/retrieval.py` - Current `PolicyRetrievalEngine`, `PolicyRetrievalHit`, dense/sparse/fuzzy channel calls, `rrf_fuse_candidates`, lexical `rerank_candidates`, timeout, candidate constants, filter propagation, and `EvidenceRefV1` construction boundary.
- `src/knowledge/schemas.py` - `KnowledgeContext`, exact `EvidenceRefV1` fields/build method, `KnowledgeSearchRequest`, `KnowledgeSearchResult.query_rewrite`, and `canonical_evidence_projection`.
- `src/knowledge/config.py` - Current retrieval and rerank config versions plus evidence thresholds.
- `src/knowledge/service.py` - `PolicyKnowledgeService.search`, merchant-scope deny-all behavior, `KnowledgeSearchResult` construction, canonical evidence row/detail validation, and Phase 22 reason-code paths.
- `src/repositories/policy_chunk_repo.py` - Tenant/doc/risk/effective-date filtered `search_similar`, `search_sparse`, `search_fuzzy`, and canonical evidence row lookup.
- `src/api/schemas/search.py` - Public search DTOs and excluded internal trace fields on `EvidenceItem`.

### ContextBuilder And Verifier Boundaries
- `src/agent/rag_context/builder.py` - ContextBuilder candidate dedupe, canonical row validation, safe projections, and exclusion traces.
- `src/agent/rag_context/verifier.py` - MaterialClaimVerifier authority gates and reranker-vs-support boundary.
- `src/agent/nodes/generate_recommendation.py` - Current production integration point that consumes retrieved evidence through ContextBuilder/verifier before action routing.

### Existing Tests And Evals
- `tests/knowledge/test_retrieval.py` - Current retrieval behavior and lexical rerank tests.
- `tests/knowledge/test_hybrid_retrieval.py` - Dense/sparse/fuzzy/RRF, internal trace, and filter propagation tests.
- `tests/knowledge/test_phase21_boundaries.py` - Static boundary guard currently blocking Phase 23 symbols and exact `EvidenceRefV1` field assertions.
- `tests/knowledge/test_phase22_evidence_validation.py` - Canonical validation reason codes for tenant, scope, duplicate key, hash, freshness, and latest/current policy version.
- `tests/agent/rag_context/test_context_builder.py` - ContextBuilder dedupe/projection and provenance leakage tests.
- `tests/agent/rag_context/test_verifier.py` - Claim verifier support behavior.
- `tests/agent/rag_context/test_leakage.py` - Prompt/final/memory/replay/action leakage guards for raw internals.
- `scripts/eval_rag_hit_at_5.py` - Current DB-backed RAG Hit@5 eval and diagnostic top-k report.
- `evaluation/golden/rag_cases.jsonl` - Existing RAG golden cases to extend or preserve during Phase 23 ablation work.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PolicyRetrievalEngine.retrieve_hits()` already returns internal `PolicyRetrievalHit` values before `EvidenceRefV1` construction. This is the natural insertion point for rewrite-channel merge and reranking.
- `PolicyRetrievalHit` already carries selected channels, dense/sparse/fuzzy ranks, RRF score, rank, score, and text. It can be extended or adapted for safe diagnostics without changing evidence refs.
- `rrf_fuse_candidates()` and `_candidate_key()` already provide deterministic fusion and dedupe by `(doc_key, chunk_id, policy_version)`.
- `PolicyChunkRepository.search_similar/search_sparse/search_fuzzy()` already accepts tenant, doc type, risk level, and effective date filters, which must be passed to every new channel.
- `KnowledgeSearchResult.query_rewrite` and `RERANK_CONFIG_VERSION` already exist as compatibility fields but are not yet full Phase 23 functionality.
- `EvidenceItem` uses `Field(exclude=True)` for internal retrieval trace fields, which is a useful public API leakage pattern.
- `scripts/eval_rag_hit_at_5.py` already measures Hit@5/fallback accuracy and can be extended or complemented for ablation/latency metrics.

### Established Patterns
- Retrieval filters are applied before channel results can affect ranking. Phase 23 should keep this pattern and add tests that inspect per-channel kwargs.
- Retrieval trace may exist on internal hits/eval reports but must not enter `EvidenceRefV1` or ordinary public/user-facing serialization.
- Service-level failures fail closed to no evidence or error results; provider/rewrite/rerank failures should follow the same pattern.
- Phase 22 canonical evidence validation re-fetches rows under tenant predicates and reports reason codes. Retrieval quality improvements should not duplicate or bypass that authority.
- Boundary tests use static string guards with allowlists for owner phase files. Phase 23 needs a narrow allowlist update rather than deleting the guard.

### Integration Points
- `src/knowledge/retrieval.py` is the primary runtime owner for query rewrite orchestration, candidate generation, merge/dedupe, default reranking, and timeout fallback.
- `src/knowledge/service.py` is the public facade owner for search results, config versions, safe query rewrite summary, and merchant-scope authorization behavior.
- `src/knowledge/config.py` should own explicit rewrite/rerank config versions and latency/candidate/text budgets.
- `tests/knowledge/test_hybrid_retrieval.py` and `tests/knowledge/test_retrieval.py` are the focused unit-test targets for candidate channels, filter preservation, and deterministic ranking.
- `tests/knowledge/test_phase21_boundaries.py` must be updated carefully so Phase 23-owned files are allowed while still blocking RAG-5, Phase 17, and Policy Source Operations scope.
- `src/agent/rag_context/*` and Phase 22 tests are regression targets only; Phase 23 should not move claim support or canonical validation into retrieval scoring.

</code_context>

<specifics>
## Specific Ideas

No external product reference was selected during this discussion. The practical design direction is to keep Phase 23 local, deterministic, auditable, and bounded first, then allow provider adapters only as optional seams with deterministic fakes and safe fallback.

Because interactive question UI is unavailable in this environment, recommended defaults were selected for each gray area and recorded in `23-DISCUSSION-LOG.md`. No user-provided free-form additions were folded into scope.

</specifics>

<deferred>
## Deferred Ideas

- **17-prep: AgentState Surface Contracts + Authority Isolation** - remains pending before Phase 17 External Action Execution, not part of Phase 23.
- **Phase 17 External Action Execution** - external action execution, outbox, reconciliation, compensation, external idempotency, and real side effects remain deferred.
- **Phase RAG-5 Optional External Search Backend** - full `SearchBackend`, Vespa/OpenSearch shadow testing, new vector DB service, or backend replacement remains deferred.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source-document viewer, and admin source-management workflow remain deferred.
- **post-Phase 17 Policy Scope** - tenant-over-global/default policy fallback and precedence merge remains deferred.
- **Phase 23 stretch only** - live default-demo cross-encoder provider use, maintainer CLI trace reports, and eval-driven auto-tuning are not baseline unless explicitly accepted during planning.

### Reviewed Todos (not folded)
- `17-prep: AgentState Surface Contracts + Authority Isolation` - reviewed via `.planning/STATE.md` and todo matching. It is intentionally deferred because Phase 23 is retrieval-quality work and must not expand AgentState authority surfaces.

</deferred>

---

*Phase: 23-rag-reranker-query-rewrite*
*Context gathered: 2026-06-20T01:45:20+08:00*
