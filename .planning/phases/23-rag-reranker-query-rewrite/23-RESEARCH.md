# Phase 23: RAG Reranker + Query Rewrite - Research

**Researched:** 2026-06-20 [VERIFIED: `date +%F`]
**Domain:** PostgreSQL-backed policy RAG retrieval quality, bounded query rewrite, deterministic reranking, safe diagnostics, and retrieval evals [VERIFIED: `.planning/ROADMAP.md`]
**Confidence:** HIGH for local architecture and boundaries; MEDIUM for provider-adapter strategy because no live provider was selected in Phase 23 context [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]

<user_constraints>
## User Constraints (from CONTEXT.md)

Source for every copied bullet in this section: [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]

### Locked Decisions

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

### Claude's Discretion

- Exact class and module names for query rewrite plans, reranker candidates, diagnostics DTOs, and config objects are open, provided they follow existing `src/knowledge` ownership and do not create a full external `SearchBackend`.
- Planner may choose whether to extend `scripts/eval_rag_hit_at_5.py` or create a new Phase 23 eval script, as long as ablation and latency outputs are deterministic and no-live-provider by default.
- Deterministic local reranker formula is planner/executor discretion, but it must be test-pinned and explainable through safe score components.

### Deferred Ideas (OUT OF SCOPE)

- **17-prep: AgentState Surface Contracts + Authority Isolation** - remains pending before Phase 17 External Action Execution, not part of Phase 23.
- **Phase 17 External Action Execution** - external action execution, outbox, reconciliation, compensation, external idempotency, and real side effects remain deferred.
- **Phase RAG-5 Optional External Search Backend** - full `SearchBackend`, Vespa/OpenSearch shadow testing, new vector DB service, or backend replacement remains deferred.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source-document viewer, and admin source-management workflow remains deferred.
- **post-Phase 17 Policy Scope** - tenant-over-global/default policy fallback and precedence merge remains deferred.
- **Phase 23 stretch only** - live default-demo cross-encoder provider use, maintainer CLI trace reports, and eval-driven auto-tuning are not baseline unless explicitly accepted during planning.

### Reviewed Todos (not folded)
- `17-prep: AgentState Surface Contracts + Authority Isolation` - reviewed via `.planning/STATE.md` and todo matching. It is intentionally deferred because Phase 23 is retrieval-quality work and must not expand AgentState authority surfaces.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QRW-01 | Produce bounded policy-search query rewrite or expansion plan for ambiguous, underspecified, or domain-synonym questions while preserving original query. [VERIFIED: `.planning/REQUIREMENTS.md`] | Use typed `QueryRewritePlan` owned by `src/knowledge`, rule-first expansion, and safe summary. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| QRW-02 | Skip rewrite deterministically for specific, out-of-domain, unsafe, or missing-trusted-context queries. [VERIFIED: `.planning/REQUIREMENTS.md`] | Reuse current domain-anchor/no-evidence behavior as skip/fallback baseline and add explicit skip reasons. [VERIFIED: `src/knowledge/retrieval.py`] |
| QRW-03 | Rewrite output cannot add tenant, merchant, role, risk, doc type, effective date, or policy-scope permissions. [VERIFIED: `.planning/REQUIREMENTS.md`] | Keep filters sourced only from `KnowledgeContext` and request filters; every channel passes tenant/doc/risk/effective date kwargs. [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`] |
| QRW-04 | Run original-query and rewritten-query candidate channels with deterministic limits and merge/dedupe before final ranking. [VERIFIED: `.planning/REQUIREMENTS.md`] | Extract existing dense/sparse/fuzzy/RRF bundle and reuse `_candidate_key()` dedupe by `(doc_key, chunk_id, policy_version)`. [VERIFIED: `src/knowledge/retrieval.py`] |
| QRW-05 | Retain original query and safe rewrite summary for eval/debug without exposing raw rewrite prompts/reasoning. [VERIFIED: `.planning/REQUIREMENTS.md`] | Use `KnowledgeSearchResult.query_rewrite` only for safe summary and internal diagnostics DTOs for raw-free details. [VERIFIED: `src/knowledge/schemas.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| RRK-01 | Expose project-owned reranker interface over bounded candidates without changing chunk content, text hashes, or policy version identity. [VERIFIED: `.planning/REQUIREMENTS.md`] | Rerank internal `PolicyRetrievalHit`/candidate DTOs before `EvidenceRefV1.build()`. [VERIFIED: `src/knowledge/retrieval.py`] |
| RRK-02 | Ship deterministic default reranker without live credentials while preserving dense/sparse/fuzzy/RRF fallback. [VERIFIED: `.planning/REQUIREMENTS.md`] | Build on current lexical overlap, selected channels, normalized confidence, RRF score, title/section overlap. [VERIFIED: `src/knowledge/retrieval.py`; `tests/knowledge/test_retrieval.py`] |
| RRK-03 | Optional external/cross-encoder adapters are config-gated, timeout-bounded, retry-bounded, and fallback-safe. [VERIFIED: `.planning/REQUIREMENTS.md`] | Implement adapter protocol and deterministic fake/failure tests; do not select a live provider for baseline. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| RRK-04 | Reranker inputs exclude raw source-block/OCR/parser internals, raw tool payloads, private reasoning, unbounded policy text, and current business fact payloads. [VERIFIED: `.planning/REQUIREMENTS.md`] | Budget candidate snippets from chunk text only and keep provenance/tool/business data out of reranker DTOs. [VERIFIED: `tests/agent/rag_context/test_leakage.py`; `src/knowledge/config.py`] |
| RRK-05 | Reranker output records safe score components, provider/config version, fallback reason, and selected candidate IDs without extending `EvidenceRefV1`. [VERIFIED: `.planning/REQUIREMENTS.md`] | Add internal/report-only diagnostics DTOs and preserve exact `EvidenceRefV1` fields. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`] |
| RRK-06 | Reranking occurs before `EvidenceRefV1` construction or through a safe adapter preserving rank, confidence, and ContextBuilder validation. [VERIFIED: `.planning/REQUIREMENTS.md`] | `retrieve_hits()` is the insertion point and `retrieve()` is the evidence-ref construction boundary. [VERIFIED: `src/knowledge/retrieval.py`] |
| EXP-01 | Generate bounded ranking explanations for maintainers/evals. [VERIFIED: `.planning/REQUIREMENTS.md`] | Extend internal trace with selected channels, rewrite/rerank contribution, rank changes, fallback reasons. [VERIFIED: `docs/rag-architecture-spec.md`; `src/api/schemas/search.py`] |
| EXP-02 | Keep ranking explanations out of ordinary prompts, final responses, memory, replay payloads, approval snapshots, and action drafts. [VERIFIED: `.planning/REQUIREMENTS.md`] | Follow existing `Field(exclude=True)` and Phase 22 leakage tests as the public-surface pattern. [VERIFIED: `src/api/schemas/search.py`; `tests/agent/rag_context/test_leakage.py`] |
| EXP-03 | Diagnostics preserve tenant isolation and cannot expose unauthorized, stale, or hash-invalid rows. [VERIFIED: `.planning/REQUIREMENTS.md`] | Apply filters before candidates affect rank and rely on ContextBuilder/service canonical validation after retrieval. [VERIFIED: `src/repositories/policy_chunk_repo.py`; `src/knowledge/service.py`] |
| EXP-04 | Retrieval traces remain separate from policy evidence identity. [VERIFIED: `.planning/REQUIREMENTS.md`] | Existing tests prove trace fields stay on hits/API excluded fields and out of `EvidenceRefV1`. [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`; `tests/knowledge/test_phase21_boundaries.py`] |
| EVAL-01 | Add golden cases for rewrite wins, synonyms, ambiguity, no-evidence, stale/unauthorized evidence, and regressions. [VERIFIED: `.planning/REQUIREMENTS.md`] | Extend existing RAG JSONL cases and preserve existing Hit@5/fallback cases. [VERIFIED: `evaluation/golden/rag_cases.jsonl`; `eval/golden_rag_queries.jsonl`] |
| EVAL-02 | Run ablations across dense-only, sparse-only, fuzzy-only, RRF, rewrite, reranker, and rewrite+reranker. [VERIFIED: `.planning/REQUIREMENTS.md`] | Add an engine mode/config path for channel variants and a dedicated ablation script/report. [VERIFIED: `scripts/eval_rag.py`; `src/knowledge/retrieval.py`] |
| EVAL-03 | Report Hit@K, MRR/rank quality, citation-support compatibility, no-evidence precision, unsafe retrieval rate, fallback rate, and latency percentiles. [VERIFIED: `.planning/REQUIREMENTS.md`] | Reuse structured report pattern from `scripts/eval_rag.py` and add metric fields. [VERIFIED: `scripts/eval_rag.py`] |
| EVAL-04 | Make rewrite/rerank latency budgets explicit. [VERIFIED: `.planning/REQUIREMENTS.md`] | Move stage budget constants to `src/knowledge/config.py` and enforce with `asyncio.wait_for` style timeouts. [VERIFIED: `src/knowledge/config.py`; `src/knowledge/retrieval.py`] |
| EVAL-05 | Timeout/provider/malformed/budget/disabled cases fall back safely. [VERIFIED: `.planning/REQUIREMENTS.md`] | Add deterministic fake adapter tests and baseline fallback assertions. [VERIFIED: `tests/knowledge/test_facade_status.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| BND-01 | Preserve Phase 20 trusted retrieval filters before ranking. [VERIFIED: `.planning/REQUIREMENTS.md`] | Keep repository filters and per-channel kwargs tests for every original/rewrite channel. [VERIFIED: `src/repositories/policy_chunk_repo.py`; `tests/knowledge/test_hybrid_retrieval.py`] |
| BND-02 | Preserve Phase 21 source-block/OCR/parser boundaries. [VERIFIED: `.planning/REQUIREMENTS.md`] | No provenance fields in `EvidenceRefV1`; raw internals remain leakage sentinels. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`; `tests/agent/rag_context/test_leakage.py`] |
| BND-03 | Preserve Phase 22 ContextBuilder and verifier authority. [VERIFIED: `.planning/REQUIREMENTS.md`] | Reranker is relevance only; `MaterialClaimVerifier` remains support authority. [VERIFIED: `tests/agent/rag_context/test_verifier.py`; `docs/rag-architecture-spec.md`] |
| BND-04 | Do not implement Phase 17 execution/outbox/compensation/side effects. [VERIFIED: `.planning/REQUIREMENTS.md`] | Static boundary guard must keep Phase 17 patterns forbidden. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`] |
| BND-05 | Do not implement RAG-5 backend replacement, Vespa/OpenSearch, new vector DB, or Policy Source Operations UI. [VERIFIED: `.planning/REQUIREMENTS.md`] | Keep implementation inside `PolicyRetrievalEngine`/repository and update guard allowlists narrowly. [VERIFIED: `docs/rag-architecture-spec.md`; `tests/knowledge/test_phase21_boundaries.py`] |
| BND-06 | Keep 17-prep AgentState cleanup future and avoid expanding AgentState authority surfaces. [VERIFIED: `.planning/REQUIREMENTS.md`] | Store only retrieval-owned redacted diagnostics/eval reports; no AgentState authority additions. [VERIFIED: `.planning/STATE.md`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
</phase_requirements>

## Summary

Phase 23 should be planned as an internal retrieval-kernel extension, not as a backend replacement or reasoning-kernel rewrite. [VERIFIED: `.planning/ROADMAP.md`; `docs/rag-architecture-spec.md`] The current seam is `PolicyRetrievalEngine.retrieve_hits()`: it returns internal `PolicyRetrievalHit` records before `retrieve()` converts them into canonical `EvidenceRefV1` values. [VERIFIED: `src/knowledge/retrieval.py`] The planner should place query rewrite, rewrite-channel merge, deterministic reranking, and diagnostics before `EvidenceRefV1.build()` and leave ContextBuilder/MaterialClaimVerifier authority unchanged. [VERIFIED: `src/knowledge/retrieval.py`; `tests/agent/rag_context/test_verifier.py`]

The primary recommendation is to use project-owned Pydantic DTOs in `src/knowledge` for `QueryRewritePlan`, reranker input/output, and retrieval diagnostics, with no new baseline package dependency. [VERIFIED: `src/knowledge/schemas.py`; `pyproject.toml`] The default path should be deterministic and local-testable: original query first, bounded rewrite expansions only when allowed, same tenant/doc/risk/effective-date filters for every channel, merge by existing candidate key, deterministic rerank, and safe fallback to original hybrid retrieval on any budget/provider failure. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `tests/knowledge/test_hybrid_retrieval.py`]

Provider work should be planned as a disabled-by-default adapter protocol with deterministic fakes, not as a selected live cross-encoder provider. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] This satisfies the adapter boundary and failure-mode requirements while keeping default tests credential-free and avoiding scope drift into provider prompts, raw payload storage, or new search infrastructure. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/agent/rag_context/test_leakage.py`]

**Primary recommendation:** Implement Phase 23 inside `src/knowledge` by extracting channel retrieval helpers, adding typed rewrite/rerank/diagnostics DTOs, enforcing stage budgets in config, and adding a dedicated ablation eval report that reuses existing RAG eval scoring patterns. [VERIFIED: `src/knowledge/retrieval.py`; `src/knowledge/config.py`; `scripts/eval_rag.py`]

## Project Constraints (from CLAUDE.md)

- Phase-level plans and larger changes require GSD-native review first, then independent Codex cross-checking against real repo files and tests. [VERIFIED: `CLAUDE.md`]
- Review findings must be verified with `rg`/grep and necessary source reads; unverified claims must be labeled as not found in the current repository. [VERIFIED: `CLAUDE.md`]
- `docs/contract-spec.md` is the only normative contract source, while RAG/spec docs describe target architecture and must not be mistaken for already-shipped implementation. [VERIFIED: `CLAUDE.md`; `docs/contract-spec.md`]
- If implementation and `docs/contract-spec.md` diverge, the phase must either update the spec through review or record an MVP-scope implementation compromise in spec/planning artifacts. [VERIFIED: `CLAUDE.md`]
- Deferred items must name the target owner phase; vague "later" deferrals are disallowed. [VERIFIED: `CLAUDE.md`]
- Phase B closure needs the difference record as an input for the lightweight final review. [VERIFIED: `CLAUDE.md`]
- `study_plan/` planning/portfolio/product docs default to Chinese; this research artifact is outside `study_plan/`. [VERIFIED: `AGENTS.md`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Query rewrite plan generation | API / Backend - Knowledge service/retrieval kernel | Database / Storage only through existing retrieval channels | Rewrite is an internal retrieval input and cannot add trusted scope fields; retrieval channels already apply DB filters. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `src/repositories/policy_chunk_repo.py`] |
| Original + rewritten channel retrieval | API / Backend - `PolicyRetrievalEngine` | Database / Storage - `PolicyChunkRepository` | Current dense/sparse/fuzzy fan-out lives in `PolicyRetrievalEngine`; repository methods own SQL filtering. [VERIFIED: `src/knowledge/retrieval.py`; `src/repositories/policy_chunk_repo.py`] |
| Candidate merge/dedupe | API / Backend - retrieval kernel | - | Existing `_candidate_key()` dedupes by doc/chunk/version before hits become evidence refs. [VERIFIED: `src/knowledge/retrieval.py`] |
| Deterministic default reranking | API / Backend - retrieval kernel | - | Existing lexical overlap rerank and RRF metadata are local backend logic before evidence construction. [VERIFIED: `src/knowledge/retrieval.py`] |
| Optional provider reranker adapter | API / Backend - config-gated adapter | External provider only when explicitly enabled | Provider use must be timeout/budget/fallback gated and not required for default tests. [VERIFIED: `.planning/REQUIREMENTS.md`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| Ranking diagnostics/eval explanations | API / Backend - internal DTO/report | Filesystem eval report | Diagnostics are maintainer/eval-only and must stay out of ordinary user-facing surfaces. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/agent/rag_context/test_leakage.py`] |
| Evidence identity and snapshot compatibility | API / Backend - `EvidenceRefV1` | ContextBuilder/verifier after retrieval | `EvidenceRefV1` shape is exact and ContextBuilder/verifier remain authority gates after retrieval. [VERIFIED: `src/knowledge/schemas.py`; `tests/knowledge/test_phase21_boundaries.py`] |
| Ablation eval metrics | CLI / Backend script | Database / Storage for seeded retrieval | Existing RAG eval scripts use `SessionLocal`, `PolicyRetrievalEngine`, and JSONL cases. [VERIFIED: `scripts/eval_rag.py`; `scripts/eval_rag_hit_at_5.py`] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Python | requires `>=3.12`; local `3.13.3` | Runtime for retrieval, scripts, and tests | Project `pyproject.toml` requires Python 3.12+ and local shell reports Python 3.13.3. [VERIFIED: `pyproject.toml`; `python --version`] |
| Pydantic | `2.13.4` | Typed DTOs for search request/result/evidence and new internal rewrite/rerank DTOs | Existing `KnowledgeContext`, `EvidenceRefV1`, `KnowledgeSearchRequest`, and `KnowledgeSearchResult` are Pydantic models. [VERIFIED: `uv tree`; `src/knowledge/schemas.py`] |
| SQLAlchemy asyncio | `2.0.49` | Async repository queries and DB-backed retrieval/eval | Existing repositories and eval scripts use async SQLAlchemy sessions. [VERIFIED: `uv tree`; `src/repositories/policy_chunk_repo.py`; `scripts/eval_rag.py`] |
| asyncpg | `0.31.0` | Async PostgreSQL driver dependency | Present in the resolved project dependency tree. [VERIFIED: `uv tree`] |
| psycopg | `3.3.4` | PostgreSQL driver/pool dependency used by current stack | Present in the resolved project dependency tree. [VERIFIED: `uv tree`] |
| pgvector Python package | `0.4.2` | PostgreSQL vector integration dependency | Current retrieval uses `PolicyChunk.embedding.cosine_distance(...)`; pgvector is already in the resolved stack. [VERIFIED: `uv tree`; `src/repositories/policy_chunk_repo.py`] |
| PostgreSQL full-text + pg_trgm | Existing DB capability | Sparse and fuzzy retrieval channels | Repository methods call `to_tsquery`, `ts_rank_cd`, and `similarity(...)` and tests assert those SQL constructs. [VERIFIED: `src/repositories/policy_chunk_repo.py`; `tests/knowledge/test_hybrid_retrieval.py`] |
| Project `src/knowledge` retrieval kernel | Internal | Query rewrite orchestration, candidate generation, reranking, diagnostics, evidence construction boundary | Current `PolicyRetrievalEngine`, `PolicyRetrievalHit`, config versions, and schemas are knowledge-owned. [VERIFIED: `src/knowledge/retrieval.py`; `src/knowledge/config.py`; `src/knowledge/schemas.py`] |

### Supporting

| Library / Component | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| pytest | `9.0.3` under `uv run`; shell global `pytest` is `8.4.2` | Unit/integration/boundary tests | Use `uv run pytest` for project-consistent test execution. [VERIFIED: `uv run pytest --version`; `pytest --version`] |
| pytest-asyncio | `1.3.0` | Async test support | Existing tests use `@pytest.mark.asyncio` and pyproject sets `asyncio_mode = "auto"`. [VERIFIED: `uv tree`; `pyproject.toml`; `tests/knowledge/test_hybrid_retrieval.py`] |
| OpenAI / LangChain / LangGraph packages | `openai 2.36.0`, `langchain-core 1.3.3`, `langgraph 1.1.10` | Existing agent stack, not baseline Phase 23 rewrite/rerank dependency | Do not use these for default Phase 23 rewrite/rerank unless a provider-gated adapter task explicitly opts in. [VERIFIED: `uv tree`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| Docker | CLI/server `29.4.2` | Local infrastructure path for DB-backed evals | Docker engine is reachable locally; DB client CLIs are not installed. [VERIFIED: `docker info --format '{{.ServerVersion}}'`; `command -v psql`; `command -v pg_isready`] |
| Tesseract | `5.5.2` | Phase 21 OCR dependency, regression only | Phase 23 should not add OCR behavior, but OCR leakage tests remain regression targets. [VERIFIED: `tesseract --version`; `.planning/REQUIREMENTS.md`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Internal `PolicyRetrievalEngine` extension | New `SearchBackend` abstraction | Deferred to RAG-5 and explicitly out of Phase 23 scope. [VERIFIED: `.planning/ROADMAP.md`; `docs/rag-architecture-spec.md`] |
| Deterministic local reranker | Always-on live cross-encoder/provider reranker | Live default provider use is stretch-only and default tests must not require credentials. [VERIFIED: `.planning/REQUIREMENTS.md`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`] |
| Project-owned DTOs | LangChain/LlamaIndex RAG abstractions | RAG architecture spec says MOCA's core contract/data model remains self-managed and those frameworks are not the core abstraction. [VERIFIED: `docs/rag-architecture-spec.md`] |
| PostgreSQL hybrid retrieval | Vespa/OpenSearch/new vector DB | RAG-5 owns backend replacement; current phase improves ranking on current PostgreSQL hybrid. [VERIFIED: `.planning/REQUIREMENTS.md`; `docs/rag-architecture-spec.md`] |

**Installation:**

```bash
uv sync --extra dev
```

Baseline Phase 23 should not require new packages. [VERIFIED: `pyproject.toml`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]

**Version verification:** This Python project uses `uv`, so `uv tree` is the version verification command rather than `npm view`. [VERIFIED: `pyproject.toml`; `uv tree`]

```bash
uv tree --depth 1
uv run pytest --version
python --version
```

## Architecture Patterns

### System Architecture Diagram

```text
KnowledgeSearchRequest + KnowledgeContext
  -> PolicyKnowledgeService.search()
      -> merchant_scope deny-all / explicit merchant authorization gate
      -> PolicyRetrievalEngine.retrieve_hits()
          -> QueryRewritePlanner.plan(original_query, trusted context, request filters)
              -> allowed? no:
                    original query only + skip_reason
              -> allowed? yes:
                    original query first + bounded rewrite expansions
          -> ChannelRunner for each allowed query expression
              -> embed dense query
              -> search_similar(tenant/doc/risk/effective_date filters)
              -> search_sparse(same filters)
              -> search_fuzzy(same filters)
              -> RRF fuse per query expression
          -> Merge/Dedupe across original and rewrite candidates
              -> key = (doc_key, chunk_id, policy_version)
              -> record selected original/rewrite channels in internal diagnostics
          -> Reranker
              -> deterministic local ranker by default
              -> optional provider adapter only if config enabled and budgets pass
              -> provider failure/timeout/malformed/budget overflow -> deterministic fallback
          -> Bounded RetrievalDiagnostics for eval/maintainers
          -> ranked PolicyRetrievalHit list
      -> EvidenceRefV1.build() in retrieve()
      -> KnowledgeSearchResult with safe query_rewrite summary only
  -> ContextBuilder canonical validation
  -> MaterialClaimVerifier support authority
  -> final answer/action safety path
```

This data flow preserves the existing service facade, retrieval engine seam, and evidence construction boundary. [VERIFIED: `src/knowledge/service.py`; `src/knowledge/retrieval.py`; `tests/agent/rag_context/test_verifier.py`]

### Recommended Project Structure

```text
src/knowledge/
├── config.py          # retrieval/rewrite/rerank config versions, limits, timeouts
├── retrieval.py       # orchestration, channel fan-out, merge, final hit/evidence boundary
├── rewrite.py         # QueryRewritePlan and deterministic rule-first planner
├── rerank.py          # project-owned reranker protocol + deterministic/default implementation
├── diagnostics.py     # internal/eval-only ranking explanation DTOs
└── schemas.py         # public knowledge contracts; EvidenceRefV1 shape unchanged

tests/knowledge/
├── test_query_rewrite.py
├── test_reranker.py
├── test_retrieval_diagnostics.py
├── test_hybrid_retrieval.py
└── test_phase21_boundaries.py

scripts/
└── eval_rag_ablation.py

evaluation/golden/
└── rag_cases.jsonl
```

This structure keeps Phase 23 inside `src/knowledge` and avoids a new external `SearchBackend`. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `docs/rag-architecture-spec.md`]

### Pattern 1: Typed Query Rewrite Plan

**What:** Add a strict internal DTO that preserves the original query, bounded expansions, deterministic skip reason, safe summary, trigger metadata, and config version. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]

**When to use:** Use for every retrieval call so eval/debug can distinguish `skipped`, `used`, and `fallback` rewrite behavior without raw prompts. [VERIFIED: `.planning/REQUIREMENTS.md`]

**Example:**

```python
# Source: src/knowledge/schemas.py and 23-CONTEXT.md
class QueryRewritePlan(BaseModel):
    original_query: str
    expansions: list[str] = Field(default_factory=list, max_length=3)
    allowed: bool
    skip_reason: str | None = None
    safe_summary: str | None = None
    triggered_by: list[str] = Field(default_factory=list)
    config_version: str
```

### Pattern 2: Same-Filter Channel Runner

**What:** Extract the current dense/sparse/fuzzy calls into one helper that accepts query text plus trusted filters and returns fused candidates. [VERIFIED: `src/knowledge/retrieval.py`]

**When to use:** Use for the original query and each allowed rewrite expansion; tests should assert every channel received identical tenant/doc/risk/effective-date kwargs. [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`]

**Example:**

```python
# Source: src/knowledge/retrieval.py and tests/knowledge/test_hybrid_retrieval.py
async def _retrieve_candidate_bundle(query_text: str, filters: RetrievalFilters) -> list[_FusedCandidate]:
    dense = await chunk_repo.search_similar(..., **filters.repo_kwargs)
    sparse = await chunk_repo.search_sparse(..., **filters.repo_kwargs)
    fuzzy = await chunk_repo.search_fuzzy(..., **filters.repo_kwargs)
    return rrf_fuse_candidates({"dense": dense, "sparse": sparse, "fuzzy": fuzzy})
```

### Pattern 3: Pre-Evidence Reranker

**What:** Rerank internal candidates before converting them to `EvidenceRefV1`; final rank changes are allowed, but evidence identity and text hash are not. [VERIFIED: `src/knowledge/retrieval.py`; `tests/knowledge/test_phase21_boundaries.py`]

**When to use:** Use after candidate merge/dedupe and before the `hits = [...]` list receives final `rank` values. [VERIFIED: `src/knowledge/retrieval.py`]

**Example:**

```python
# Source: src/knowledge/retrieval.py and 23-CONTEXT.md
ranked_candidates, rerank_trace = await reranker.rerank(
    query=plan.original_query,
    candidates=merged_candidates[:config.MERGED_CANDIDATE_CAP],
    budget=config.rerank_budget,
)
hits = [_hit_from_candidate(candidate, rank=index) for index, candidate in enumerate(ranked_candidates, start=1)]
```

### Pattern 4: Internal Diagnostics, Public Summary

**What:** Put full ranking explanation fields in internal/eval DTOs and expose only safe summaries or excluded fields to public API surfaces. [VERIFIED: `src/api/schemas/search.py`; `tests/agent/rag_context/test_leakage.py`]

**When to use:** Use for eval reports, maintainer traces, and failed-case diagnostics; do not include diagnostics in `EvidenceRefV1`, prompt context, final response, memory, replay, approval snapshots, or action drafts. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/knowledge/test_phase21_boundaries.py`]

**Example:**

```python
# Source: src/api/schemas/search.py
class RetrievalCandidateDiagnostics(BaseModel):
    candidate_id: str
    selected_by: list[str]
    rewrite_source: str | None = None
    rerank_score_components: dict[str, float] = Field(default_factory=dict)
    fallback_reason: str | None = None
```

### Anti-Patterns to Avoid

- **Adding rewrite/rerank fields to `EvidenceRefV1`:** This breaks the exact canonical evidence shape verified by boundary tests. [VERIFIED: `src/knowledge/schemas.py`; `tests/knowledge/test_phase21_boundaries.py`]
- **Running reranking after ContextBuilder as support validation:** Reranker is relevance ranking; MaterialClaimVerifier owns support. [VERIFIED: `docs/rag-architecture-spec.md`; `tests/agent/rag_context/test_verifier.py`]
- **Provider-first rewrite/rerank in default tests:** Default tests and evals must not require live credentials. [VERIFIED: `.planning/REQUIREMENTS.md`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]
- **Letting rewritten queries change trusted filters:** Trusted filter values must come only from context/request authorization, not rewrite output. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/knowledge/test_hybrid_retrieval.py`]
- **Creating a `SearchBackend` or backend replacement seam:** RAG-5 owns that scope. [VERIFIED: `.planning/ROADMAP.md`; `docs/rag-architecture-spec.md`] 

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Evidence identity | A new rewrite/rerank-aware evidence schema | `EvidenceRefV1.build()` and `canonical_evidence_projection()` | Existing contracts and tests fix field shape, hash projection, score/rank handling, and action snapshot compatibility. [VERIFIED: `src/knowledge/schemas.py`; `tests/knowledge/test_phase21_boundaries.py`] |
| Search backend abstraction | Full `SearchBackend`, Vespa/OpenSearch adapter, new vector DB | Current `PolicyRetrievalEngine` + `PolicyChunkRepository` | Backend replacement is deferred to RAG-5; current repository already owns dense/sparse/fuzzy filters. [VERIFIED: `.planning/ROADMAP.md`; `src/repositories/policy_chunk_repo.py`] |
| Authorization/filter logic | Rewrite-owned tenant/scope/doc/risk/effective-date handling | Existing `KnowledgeContext`, service merchant-scope gate, repository filters | Current facade and tests fail closed for missing/unauthorized merchant scope and assert per-channel filters. [VERIFIED: `src/knowledge/service.py`; `tests/knowledge/test_service.py`; `tests/knowledge/test_hybrid_retrieval.py`] |
| Semantic claim support | Reranker score as support/confidence authority | ContextBuilder + `MaterialClaimVerifier` | Existing verifier tests prove citation membership and relevance are not semantic support. [VERIFIED: `tests/agent/rag_context/test_verifier.py`] |
| Diagnostics serialization | Raw prompts/provider payloads/full ranking traces in public models | Internal diagnostics DTOs plus `Field(exclude=True)` for API-only hidden fields | Existing API evidence fields exclude trace data and leakage tests block raw internals. [VERIFIED: `src/api/schemas/search.py`; `tests/agent/rag_context/test_leakage.py`] |
| Eval framework | A new unrelated eval harness | Extend/reuse `scripts/eval_rag.py` report shape or create `eval_rag_ablation.py` from its helpers | Existing script already loads JSONL, uses DB-backed engine, computes report JSON, and integrates with `eval_all.py`. [VERIFIED: `scripts/eval_rag.py`; `scripts/eval_all.py`] |

**Key insight:** Phase 23 complexity is not in picking a provider; it is in preserving identity, filters, support authority, and redaction while adding more candidate paths. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/knowledge/test_phase21_boundaries.py`; `tests/agent/rag_context/test_leakage.py`]

## Common Pitfalls

### Pitfall 1: Rewrite Widening Scope
**What goes wrong:** A rewritten query adds or implies tenant, merchant, risk, document type, or effective-date scope that the caller did not have. [VERIFIED: `.planning/REQUIREMENTS.md`]
**Why it happens:** Rewrite output is treated as a search request instead of a bounded query-expression plan. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]
**How to avoid:** Keep rewrite DTOs free of trusted filter fields and pass the same repo kwargs to every channel. [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`]
**Warning signs:** Tests inspect original channel filters but not rewrite channel filters. [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`]

### Pitfall 2: Reranker Score Replaces Evidence Confidence or Claim Support
**What goes wrong:** Provider/local rerank score becomes `EvidenceRefV1.score`, action support, or semantic support. [VERIFIED: `.planning/REQUIREMENTS.md`]
**Why it happens:** Rerank relevance and verifier support are both numeric-looking concepts. [VERIFIED: `docs/rag-architecture-spec.md`]
**How to avoid:** Preserve normalized confidence semantics for status thresholds and store rerank score components only in diagnostics. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `tests/knowledge/test_hybrid_retrieval.py`]
**Warning signs:** Tests assert `best_score` from reranker score rather than candidate confidence. [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`]

### Pitfall 3: Diagnostics Leak Into Ordinary Surfaces
**What goes wrong:** Raw rewrite prompts, raw provider payloads, source-block IDs, private reasoning, or unbounded policy text appears in prompts/final/memory/replay/action snapshots. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/agent/rag_context/test_leakage.py`]
**Why it happens:** A convenient diagnostics object is passed into public DTOs or prompt context. [VERIFIED: `src/api/schemas/search.py`; `tests/agent/rag_context/test_leakage.py`]
**How to avoid:** Separate internal/report DTOs from public DTOs and add sentinel leakage tests. [VERIFIED: `tests/agent/rag_context/test_leakage.py`]
**Warning signs:** New diagnostics fields appear in `EvidenceRefV1.model_fields` or public `RetrievalResult.model_dump()`. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`; `src/api/schemas/search.py`]

### Pitfall 4: Boundary Guard Over-Relaxation
**What goes wrong:** Static guards are deleted or broadly weakened to make Phase 23 symbols pass. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`]
**Why it happens:** Current guard intentionally forbids Phase 23 terms because Phase 22 had not implemented them. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]
**How to avoid:** Add narrow Phase 23-owned file allowlists while keeping Phase 17, RAG-5, and Policy Source Operations patterns forbidden. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]
**Warning signs:** `SearchBackend`, `Vespa`, `OpenSearch`, `external_action_execution`, or `PolicySourceOperations` become allowed outside tests/docs. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`]

### Pitfall 5: Eval Measures Only Hit@5
**What goes wrong:** Rewrite/rerank changes pass because Hit@5 stays above threshold while MRR, no-evidence precision, unsafe retrieval, fallback rate, or latency regresses. [VERIFIED: `.planning/REQUIREMENTS.md`]
**Why it happens:** Existing `eval_rag_hit_at_5.py` is a Hit@5/fallback script, not full Phase 23 ablation. [VERIFIED: `scripts/eval_rag_hit_at_5.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-DISCUSSION-LOG.md`]
**How to avoid:** Add ablation variants and latency percentiles to structured eval report. [VERIFIED: `scripts/eval_rag.py`; `.planning/REQUIREMENTS.md`]
**Warning signs:** No per-variant report for dense-only, sparse-only, fuzzy-only, RRF, rewrite, reranker, rewrite+reranker. [VERIFIED: `.planning/REQUIREMENTS.md`]

## Code Examples

Verified patterns from local sources:

### EvidenceRef Construction Boundary

```python
# Source: src/knowledge/retrieval.py
evidence_refs = [
    EvidenceRefV1.build(
        tenant_id=context.tenant_id,
        doc_key=hit.doc_key,
        chunk_id=hit.chunk_id,
        policy_version=hit.policy_version,
        text=hit.text,
        retrieved_at=context.effective_at,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=hit.score,
        rank=hit.rank,
    )
    for hit in hits
]
```

Planning implication: rewrite and rerank must act on `hits` or earlier candidates before this block. [VERIFIED: `src/knowledge/retrieval.py`]

### Existing Candidate Key

```python
# Source: src/knowledge/retrieval.py
def _candidate_key(chunk: object) -> tuple[str, str, str]:
    return (str(chunk.document.doc_key), str(chunk.chunk_id), _policy_version(chunk))
```

Planning implication: use this identity for merge/dedupe before evidence refs are built. [VERIFIED: `src/knowledge/retrieval.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]

### Public DTO Trace Exclusion Pattern

```python
# Source: src/api/schemas/search.py
class EvidenceItem(BaseModel):
    doc_key: str
    chunk_id: str
    title: str
    section: str
    score: float = Field(ge=0.0, le=1.0)
    text: str
    selected_by: list[str] | None = Field(default=None, exclude=True)
    dense_rank: int | None = Field(default=None, exclude=True)
    sparse_rank: int | None = Field(default=None, exclude=True)
    fuzzy_rank: int | None = Field(default=None, exclude=True)
    rrf_score: float | None = Field(default=None, exclude=True)
```

Planning implication: Phase 23 diagnostics can exist, but ordinary serialization must exclude them or place them in internal/eval-only DTOs. [VERIFIED: `src/api/schemas/search.py`; `tests/knowledge/test_phase21_boundaries.py`]

### Structured Eval Report Pattern

```python
# Source: scripts/eval_rag.py
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

Planning implication: ablation should produce a similar machine-readable report with per-variant metrics and latency percentiles. [VERIFIED: `scripts/eval_rag.py`; `.planning/REQUIREMENTS.md`]

## State of the Art

| Old Approach | Current/Recommended Approach | When Changed | Impact |
|--------------|------------------------------|--------------|--------|
| pgvector-only retrieval plus lightweight lexical rerank | PostgreSQL hybrid dense/sparse/fuzzy + RRF with internal trace | Phase 20 / v1.3 shipped 2026-06-18 | Phase 23 must preserve current hybrid fallback and build on it. [VERIFIED: `.planning/PROJECT.md`; `.planning/milestones/v1.3-ROADMAP.md`] |
| Retrieval output directly consumed by generation | ContextBuilder re-fetches/canonical-validates evidence and MaterialClaimVerifier checks support | Phase 22 / v1.5 shipped 2026-06-19 | Reranker can improve relevance but cannot become support authority. [VERIFIED: `.planning/PROJECT.md`; `tests/agent/rag_context/test_verifier.py`] |
| Minimal selected_by/channel-rank trace | Full bounded ranking explanation for eval/maintainers in RAG-3/4 target | RAG architecture target for Phase 23 | Diagnostics should expand internally without public leakage. [VERIFIED: `docs/rag-architecture-spec.md`; `.planning/REQUIREMENTS.md`] |
| Full external `SearchBackend` target considered in architecture docs | Keep current PostgreSQL retrieval facade for Phase 23; defer backend replacement to RAG-5 | v1.6 roadmap and context | Avoid SearchBackend/Vespa/OpenSearch tasks in this phase. [VERIFIED: `.planning/ROADMAP.md`; `docs/rag-architecture-spec.md`] |

**Deprecated/outdated for Phase 23:**
- Treating `KnowledgeSearchResult.query_rewrite` as raw rewrite payload is out of scope; it may carry only a safe summary/compatibility value. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `src/knowledge/schemas.py`]
- Treating live provider calls as default test behavior is out of scope; default tests must be deterministic and credential-free. [VERIFIED: `.planning/REQUIREMENTS.md`]
- Treating RAG architecture target `SearchBackend` as current implementation scope is out of scope. [VERIFIED: `docs/rag-architecture-spec.md`; `.planning/ROADMAP.md`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

All claims in this research were verified from local repository files, local tool output, or cited official OWASP pages; no `[ASSUMED]` claims are intentionally present. [VERIFIED: research command outputs; CITED: https://owasp.org/www-project-application-security-verification-standard/]

## Open Questions (RESOLVED)

1. **RESOLVED: Exact deterministic reranker formula**
   - What we know: The formula can use lexical overlap, selected channels, RRF score, normalized confidence, section/title overlap, and safe metadata. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `src/knowledge/retrieval.py`]
   - Decision: The deterministic formula is selected in Plan 04 as the local/default reranker path. It is credential-free, no-live-provider by default, and test-pinned through `tests/knowledge/test_reranker.py`.
   - Selected formula: `final_score = baseline_score + 0.10 * lexical_overlap + 0.05 * title_section_overlap + 0.03 * channel_coverage + min(rrf_score or 0, 0.10)`, clamped to `[0, 1]` and tie-broken by `(baseline_rank, doc_key, chunk_id)`.
   - Implementation location: Plan 04 creates the reranker DTOs and formula in `src/knowledge/rerank.py`, with config/version constants in `src/knowledge/config.py` and safe score components in diagnostics.

2. **RESOLVED: Dedicated ablation script vs extending existing eval**
   - What we know: `scripts/eval_rag.py` has structured JSON reports, while `scripts/eval_rag_hit_at_5.py` has Hit@5/fallback helpers and diagnostic top-k. [VERIFIED: `scripts/eval_rag.py`; `scripts/eval_rag_hit_at_5.py`]
   - Decision: Plan 05 baseline is a dedicated `scripts/eval_rag_ablation.py` script and generated ablation report path, not an overload of `scripts/eval_rag_hit_at_5.py`.
   - Implementation location: Plan 05 creates `scripts/eval_rag_ablation.py`, appends Phase 23 cases to `evaluation/golden/rag_cases.jsonl`, and verifies report helper behavior in `tests/test_rag_ablation_eval.py`.

3. **RESOLVED: How much provider adapter code belongs in baseline**
   - What we know: Optional adapters are allowed only behind config gates and default tests must use fakes/failure cases. [VERIFIED: `.planning/REQUIREMENTS.md`]
   - Decision: Baseline provider support is an adapter protocol only. It is disabled by default, config-gated, timeout/retry/budget bounded, fake-tested, and failure-tested; there is no live default provider and no credential requirement.
   - Implementation location: Plan 04 creates `RerankerProviderAdapter` protocol and fallback behavior for `provider_disabled`, `provider_timeout`, `provider_error`, `provider_malformed_output`, and `budget_overflow`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Runtime/tests | Yes | `3.13.3` local; project requires `>=3.12` | Use `uv run` project environment. [VERIFIED: `python --version`; `pyproject.toml`] |
| uv | Dependency/test runner | Yes | `0.11.2` | Use existing virtualenv only if `uv` unavailable. [VERIFIED: `uv --version`] |
| pytest under uv | Validation | Yes | `9.0.3` | Use `uv run pytest`, not global `pytest 8.4.2`. [VERIFIED: `uv run pytest --version`; `pytest --version`] |
| Docker engine | DB-backed eval infrastructure | Yes | `29.4.2` | Use project DB if already running. [VERIFIED: `docker info --format '{{.ServerVersion}}'`] |
| PostgreSQL client `psql` | Manual DB probes | No | - | Use app `SessionLocal` scripts or install client if shell probing is needed. [VERIFIED: `command -v psql`] |
| PostgreSQL readiness CLI `pg_isready` | Manual DB readiness probes | No | - | Use Docker/app health path or install client if needed. [VERIFIED: `command -v pg_isready`] |
| Tesseract | Phase 21 OCR regression context | Yes | `5.5.2` | Not required for new Phase 23 behavior. [VERIFIED: `tesseract --version`; `.planning/REQUIREMENTS.md`] |

**Missing dependencies with no fallback:**
- None identified for planning or default unit tests. [VERIFIED: environment probes]

**Missing dependencies with fallback:**
- `psql` and `pg_isready` are absent; DB-backed evals can still use existing Python app/session scripts and Docker infrastructure. [VERIFIED: `command -v psql`; `command -v pg_isready`; `scripts/eval_rag.py`]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `9.0.3` with pytest-asyncio `1.3.0` under `uv run` [VERIFIED: `uv run pytest --version`; `uv tree`] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: `pyproject.toml`] |
| Quick run command | `uv run pytest tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py tests/knowledge/test_hybrid_retrieval.py -q --tb=short` [VERIFIED: existing test layout from `find tests/knowledge`; Wave 0 files needed] |
| Full suite command | `uv run pytest` [VERIFIED: `pyproject.toml`] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| QRW-01 | Bounded rewrite plan preserves original query | unit | `uv run pytest tests/knowledge/test_query_rewrite.py::test_rewrite_plan_preserves_original_query -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| QRW-02 | Deterministic skip reasons | unit | `uv run pytest tests/knowledge/test_query_rewrite.py::test_rewrite_skips_specific_out_of_domain_unsafe_or_missing_context -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| QRW-03 | Rewrite cannot add trusted filters | unit | `uv run pytest tests/knowledge/test_query_rewrite.py::test_rewrite_plan_cannot_widen_trusted_filters -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| QRW-04 | Original + rewrite channel limits/merge/dedupe | unit | `uv run pytest tests/knowledge/test_hybrid_retrieval.py::test_original_and_rewrite_channels_merge_before_rerank -q` | Existing file, new test needed [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`] |
| QRW-05 | Safe rewrite summary only | unit/integration | `uv run pytest tests/knowledge/test_retrieval_diagnostics.py::test_query_rewrite_summary_excludes_raw_payloads -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| RRK-01 | Project-owned reranker DTO/protocol preserves identity | unit | `uv run pytest tests/knowledge/test_reranker.py::test_reranker_preserves_candidate_identity -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| RRK-02 | Deterministic default reranker no credentials | unit | `uv run pytest tests/knowledge/test_reranker.py::test_default_reranker_is_deterministic_and_local -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| RRK-03 | Provider adapter gates/fallbacks | unit | `uv run pytest tests/knowledge/test_reranker.py::test_provider_adapter_disabled_timeout_error_malformed_and_budget_fallbacks -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| RRK-04 | Reranker input redaction/text budget | unit | `uv run pytest tests/knowledge/test_reranker.py::test_reranker_inputs_exclude_raw_internals_and_unbounded_text -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| RRK-05 | Safe score components without EvidenceRef extension | unit | `uv run pytest tests/knowledge/test_retrieval_diagnostics.py::test_rerank_diagnostics_do_not_extend_evidence_ref -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| RRK-06 | Rerank before evidence construction | unit | `uv run pytest tests/knowledge/test_reranker.py::test_rerank_occurs_before_evidence_ref_construction -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| EXP-01 | Bounded ranking explanation fields | unit | `uv run pytest tests/knowledge/test_retrieval_diagnostics.py::test_ranking_explanation_contains_safe_components -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| EXP-02 | Diagnostics excluded from ordinary surfaces | unit/regression | `uv run pytest tests/agent/rag_context/test_leakage.py tests/knowledge/test_retrieval_diagnostics.py -q --tb=short` | Partial existing, new diagnostics tests needed [VERIFIED: `tests/agent/rag_context/test_leakage.py`] |
| EXP-03 | Diagnostics respect tenant/stale/hash exclusions | integration | `uv run pytest tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_retrieval_diagnostics.py -q --tb=short` | Partial existing, new diagnostics tests needed [VERIFIED: `tests/knowledge/test_phase22_evidence_validation.py`] |
| EXP-04 | Trace separate from `EvidenceRefV1` | unit/regression | `uv run pytest tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q` | Yes [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`; smoke run passed] |
| EVAL-01 | Golden cases expanded | unit/static | `uv run pytest tests/test_rag_ablation_eval.py::test_phase23_golden_cases_cover_required_categories -q` | No - Wave 0 [VERIFIED: `find tests -maxdepth 2`] |
| EVAL-02 | Ablation variants run | unit | `uv run pytest tests/test_rag_ablation_eval.py::test_ablation_variants_include_required_modes -q` | No - Wave 0 [VERIFIED: `find tests -maxdepth 2`] |
| EVAL-03 | Blocking metrics reported | unit | `uv run pytest tests/test_rag_ablation_eval.py::test_ablation_report_contains_rank_safety_fallback_and_latency_metrics -q` | No - Wave 0 [VERIFIED: `find tests -maxdepth 2`] |
| EVAL-04 | Latency budgets explicit | unit | `uv run pytest tests/knowledge/test_retrieval_budgets.py::test_rewrite_rerank_budget_constants_are_versioned -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| EVAL-05 | Failure cases fallback safely | unit | `uv run pytest tests/knowledge/test_retrieval_budgets.py::test_stage_timeout_provider_error_malformed_budget_disabled_fallbacks -q` | No - Wave 0 [VERIFIED: `find tests/knowledge`] |
| BND-01 | Filter preservation across channels | unit | `uv run pytest tests/knowledge/test_hybrid_retrieval.py::test_each_hybrid_channel_receives_scope_filters -q` | Yes; extend for rewrite channels [VERIFIED: `tests/knowledge/test_hybrid_retrieval.py`; smoke run passed] |
| BND-02 | Source-block/OCR/parser boundaries | regression | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/rag_context/test_leakage.py -q --tb=short` | Yes [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`; `tests/agent/rag_context/test_leakage.py`] |
| BND-03 | ContextBuilder/verifier authority preserved | regression | `uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_verifier.py -q --tb=short` | Yes [VERIFIED: `tests/agent/rag_context/test_context_builder.py`; `tests/agent/rag_context/test_verifier.py`] |
| BND-04 | Phase 17 forbidden scope remains blocked | static | `uv run pytest tests/knowledge/test_phase21_boundaries.py::test_phase22_boundary_guard_still_blocks_rerank_query_rewrite_search_backend_and_execution_scope -q` | Yes; update expected guard for Phase 23 names only [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`] |
| BND-05 | RAG-5/SearchBackend/UI forbidden scope remains blocked | static | `uv run pytest tests/knowledge/test_phase21_boundaries.py::test_phase21_boundary_allows_phase22_claim_verifier_files_but_no_phase23_rag5_or_execution_surfaces -q` | Yes; update narrow allowlist [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`] |
| BND-06 | No AgentState authority expansion | static/unit | `uv run pytest tests/agent/test_working_state.py tests/knowledge/test_phase21_boundaries.py -q --tb=short` | Existing regression files; add Phase 23 sentinel if state touched [VERIFIED: `tests/agent/test_working_state.py`; `.planning/STATE.md`] |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py tests/knowledge/test_hybrid_retrieval.py -q --tb=short` after Wave 0 files exist. [VERIFIED: planned files from requirement map]
- **Per wave merge:** `uv run pytest tests/knowledge tests/agent/rag_context tests/test_rag_eval.py tests/test_rag_ablation_eval.py -q --tb=short` after eval tests exist. [VERIFIED: existing test layout]
- **Phase gate:** `uv run pytest` plus `uv run python scripts/eval_rag_ablation.py --golden-set evaluation/golden/rag_cases.jsonl --output evaluation/reports/rag_ablation.json` once the script exists. [VERIFIED: `scripts/eval_rag.py`; `.planning/REQUIREMENTS.md`]

### Wave 0 Gaps

- [ ] `tests/knowledge/test_query_rewrite.py` - covers QRW-01..QRW-05. [VERIFIED: missing from `find tests/knowledge`]
- [ ] `tests/knowledge/test_reranker.py` - covers RRK-01..RRK-06. [VERIFIED: missing from `find tests/knowledge`]
- [ ] `tests/knowledge/test_retrieval_diagnostics.py` - covers EXP-01..EXP-04 and RRK-05. [VERIFIED: missing from `find tests/knowledge`]
- [ ] `tests/knowledge/test_retrieval_budgets.py` - covers EVAL-04/EVAL-05. [VERIFIED: missing from `find tests/knowledge`]
- [ ] `tests/test_rag_ablation_eval.py` - covers EVAL-01..EVAL-03. [VERIFIED: missing from `find tests -maxdepth 2`]
- [ ] Static guard updates in `tests/knowledge/test_phase21_boundaries.py` - allow Phase 23-owned symbols only in owned files while keeping RAG-5/Phase 17/Policy Source Operations blocked. [VERIFIED: `tests/knowledge/test_phase21_boundaries.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]
- [ ] No framework install gap: pytest and pytest-asyncio are available through `uv run`. [VERIFIED: `uv run pytest --version`; `uv tree`]

### Smoke Verification Run During Research

`uv run pytest tests/test_rag_eval.py tests/knowledge/test_hybrid_retrieval.py::test_each_hybrid_channel_receives_scope_filters tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q --tb=short` passed with 8 tests and 1 LangGraph pending-deprecation warning. [VERIFIED: command output]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not explicitly set `security_enforcement` to `false`. [VERIFIED: `.planning/config.json`]

### Applicable ASVS Categories

OWASP ASVS is the official verification standard for web application technical security controls, and the OWASP ASVS repository lists latest stable version 5.0.0 dated May 2025. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No direct Phase 23 change | Do not change auth/session identity fields; use existing trusted `KnowledgeContext`. [VERIFIED: `docs/contract-spec.md`; `.planning/REQUIREMENTS.md`] |
| V3 Session Management | No direct Phase 23 change | Do not add session authority or AgentState cleanup work in Phase 23. [VERIFIED: `.planning/STATE.md`; `.planning/REQUIREMENTS.md`] |
| V4 Access Control | Yes | Enforce tenant/merchant/doc/risk/effective-date filters before candidate ranking and diagnostics. [VERIFIED: `src/knowledge/service.py`; `src/repositories/policy_chunk_repo.py`; `tests/knowledge/test_hybrid_retrieval.py`] |
| V5 Input Validation | Yes | Validate rewrite/rerank DTOs with Pydantic and bounded lengths/counts; keep raw provider payloads out of public surfaces. [VERIFIED: `src/knowledge/schemas.py`; `.planning/REQUIREMENTS.md`] |
| V6 Cryptography | Indirect only | Preserve `EvidenceRefV1.text_hash` and canonical evidence projection; do not alter hash semantics. [VERIFIED: `src/knowledge/schemas.py`; `docs/contract-spec.md`] |

### Known Threat Patterns for MOCA Phase 23

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Rewrite privilege widening | Elevation of privilege / Information disclosure | Rewrite DTO excludes trusted filter fields; channels reuse caller/service filters. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/knowledge/test_hybrid_retrieval.py`] |
| Cross-tenant diagnostic leakage | Information disclosure | Diagnostics include only selected candidate IDs and safe score components after tenant-filtered retrieval. [VERIFIED: `src/repositories/policy_chunk_repo.py`; `.planning/REQUIREMENTS.md`] |
| Provider payload leakage | Information disclosure | Provider adapters are config-gated, bounded, and raw prompts/payloads are excluded from ordinary surfaces. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `tests/agent/rag_context/test_leakage.py`] |
| Unsafe fallback on timeout/malformed provider output | Denial of service / Tampering | Stage timeouts/failure fall back to deterministic local retrieval or no-evidence behavior. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/knowledge/test_facade_status.py`] |
| Reranker score treated as action authority | Elevation of privilege | MaterialClaimVerifier and action safety remain authority gates; reranker scores remain relevance diagnostics. [VERIFIED: `tests/agent/rag_context/test_verifier.py`; `.planning/REQUIREMENTS.md`] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md` - locked Phase 23 decisions, discretion areas, deferred ideas, code context, and integration points. [VERIFIED: local file read]
- `.planning/REQUIREMENTS.md` - QRW/RRK/EXP/EVAL/BND requirement definitions. [VERIFIED: local file read]
- `.planning/ROADMAP.md` - Phase 23 goal, success criteria, suggested plan slices, and hard boundaries. [VERIFIED: local file read]
- `.planning/STATE.md` and `.planning/PROJECT.md` - milestone status, shipped boundaries, active/deferred scope. [VERIFIED: local file read]
- `docs/contract-spec.md` - normative KnowledgeService, `KnowledgeSearchResult`, `EvidenceRefV1`, hash projection, and redaction/replay rules. [VERIFIED: local file read]
- `docs/rag-architecture-spec.md` - target RAG architecture, RAG-4/Phase 23 narrative, ranking explanation, reranker/verifier separation, and RAG-5 deferral. [VERIFIED: local file read]
- `src/knowledge/retrieval.py` - current engine, `PolicyRetrievalHit`, dense/sparse/fuzzy/RRF path, timeout, and evidence construction boundary. [VERIFIED: local file read]
- `src/knowledge/schemas.py` - Pydantic knowledge contracts and exact `EvidenceRefV1` shape. [VERIFIED: local file read]
- `src/knowledge/service.py` - facade auth gate, error/no-evidence behavior, and canonical evidence validation. [VERIFIED: local file read]
- `src/repositories/policy_chunk_repo.py` - tenant/doc/risk/effective-date filters for dense/sparse/fuzzy repository methods. [VERIFIED: local file read]
- `tests/knowledge/test_hybrid_retrieval.py`, `tests/knowledge/test_retrieval.py`, `tests/knowledge/test_phase21_boundaries.py`, `tests/agent/rag_context/*` - current filter, trace, boundary, ContextBuilder, verifier, and leakage tests. [VERIFIED: local file reads]
- `scripts/eval_rag.py`, `scripts/eval_rag_hit_at_5.py`, `scripts/eval_all.py`, `evaluation/golden/rag_cases.jsonl`, `eval/golden_rag_queries.jsonl` - current RAG eval patterns and golden data. [VERIFIED: local file reads]
- `pyproject.toml`, `uv tree`, `uv run pytest --version` - project dependencies and test framework versions. [VERIFIED: local file and command output]

### Secondary (MEDIUM confidence)

- OWASP ASVS project page and OWASP/ASVS repository - ASVS purpose and latest stable version reference for security-domain framing. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

### Tertiary (LOW confidence)

- None. [VERIFIED: source inventory above]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - based on `pyproject.toml`, `uv tree`, local version commands, and current code imports. [VERIFIED: `pyproject.toml`; `uv tree`]
- Architecture: HIGH - based on current retrieval/service/repository code, Phase 23 context decisions, and shipped Phase 20-22 tests. [VERIFIED: `src/knowledge/retrieval.py`; `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`; `tests/knowledge/test_hybrid_retrieval.py`]
- Pitfalls: HIGH - based on explicit requirements, existing static guards, leakage tests, and verifier authority tests. [VERIFIED: `.planning/REQUIREMENTS.md`; `tests/knowledge/test_phase21_boundaries.py`; `tests/agent/rag_context/test_leakage.py`; `tests/agent/rag_context/test_verifier.py`]
- Provider adapter specifics: MEDIUM - adapter gates and fake/failure tests are locked, but no live provider/product was selected. [VERIFIED: `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]

**Research date:** 2026-06-20 [VERIFIED: `date +%F`]
**Valid until:** 2026-07-20 for local architecture; re-check provider docs if a live provider is selected. [VERIFIED: no provider selected in `.planning/phases/23-rag-reranker-query-rewrite/23-CONTEXT.md`]
