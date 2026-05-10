---
phase: 02-rag-pipeline
plan: "07"
type: execute
wave: 5
depends_on: ["06"]
files_modified:
  - src/rag/ingestion.py
  - src/rag/retriever.py
  - tests/test_ingestion.py
  - tests/test_retriever.py
  - tests/test_rag_eval.py
  - scripts/eval_rag_hit_at_5.py
  - .planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md
  - .planning/phases/02-rag-pipeline/07-SUMMARY.md
autonomous: true
requirements: [EVAL-02]
gap_closure: true
must_haves:
  truths:
    - "Plan 06 remains the source of truth for the current gap: live Hit@5 is 58.3%, fallback accuracy is 100%, and honest golden-set calibration can raise only 7/12 to 8/12."
    - "The retrieval fix must change final ranking behavior, not merely over-fetch and then preserve the same vector-only top-5 order."
    - "Document embeddings include document title and section heading while stored PolicyChunk.content remains raw policy text."
    - "Retriever keeps user-facing top_k=5, MIN_SIMILARITY_THRESHOLD=0.55, STRONG_EVIDENCE_THRESHOLD=0.70, tenant filtering, metadata filtering, and chunk-ID citation semantics."
    - "Final evidence is selected by deterministic hybrid reranking over a deeper candidate set using vector score plus lexical/title/section overlap; no LLM judge is introduced."
    - "Live DB-backed RAG Hit@5 is at least 80% and fallback accuracy remains at least 80% after re-ingestion."
  artifacts:
    - path: "src/rag/ingestion.py"
      provides: "Embedding input enrichment with title and section context"
      contains: "chunk.section"
    - path: "tests/test_ingestion.py"
      provides: "Regression coverage for enriched embedding input and raw stored chunk content"
      contains: "embed_documents"
    - path: "src/rag/retriever.py"
      provides: "Deterministic hybrid candidate reranking over vector candidates"
      contains: "_rerank_candidates"
    - path: "tests/test_retriever.py"
      provides: "Regression tests for query prefix, candidate over-fetch, threshold filtering, and hybrid rerank promotion"
      contains: "test_hybrid_rerank"
    - path: ".planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md"
      provides: "Before/after failed-case evidence proving why Plan 07 closes or fails to close EVAL-02"
      contains: "Before Plan 07"
  key_links:
    - from: "src/rag/ingestion.py"
      to: "src/rag/retriever.py"
      via: "Documents are embedded with title/section context and queries use a matching domain prefix"
      pattern: "QUERY_PREFIX"
    - from: "src/rag/retriever.py"
      to: "src/repositories/policy_chunk_repo.py"
      via: "Retriever requests deeper tenant-filtered vector candidates before deterministic reranking"
      pattern: "search_similar"
    - from: "scripts/eval_rag_hit_at_5.py"
      to: ".planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md"
      via: "Live failed-case ranked evidence before and after retrieval changes"
      pattern: "ranked evidence"
---

# Plan 07: Close Retrieval Quality Gap with Contextual Embeddings and Hybrid Reranking

<objective>
Close the remaining Phase 2 EVAL-02 gap that Plan 06 proved is a retrieval-quality problem, not a golden-set calibration problem.

Plan 06 established that current live retrieval has `Hit@5: 58.3%` with 7/12 non-fallback hits and needs 10/12 to pass. It found only one semantically valid calibration candidate, so calibration alone cannot honestly satisfy the 80% gate.

This plan improves retrieval by:
- enriching document embedding input with title and section context;
- enriching query embedding with a short domain prefix;
- retrieving a deeper tenant-filtered vector candidate set;
- applying deterministic hybrid reranking using vector similarity plus lexical/title/section overlap;
- preserving the public top-5, fallback, tenant isolation, metadata filter, and citation contracts.
</objective>

<execution_context>
@/Users/ming/.codex/get-shit-done/workflows/execute-plan.md
@/Users/ming/.codex/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-rag-pipeline/02-CONTEXT.md
@.planning/phases/02-rag-pipeline/02-PATTERNS.md
@.planning/phases/02-rag-pipeline/04-SUMMARY.md
@.planning/phases/02-rag-pipeline/05-SUMMARY.md
@.planning/phases/02-rag-pipeline/06-PLAN.md
@.planning/phases/02-rag-pipeline/06-SUMMARY.md
@scripts/eval_rag_hit_at_5.py
@scripts/ingest_policies.py
@eval/golden_rag_queries.jsonl
@src/rag/ingestion.py
@src/rag/retriever.py
@src/repositories/policy_chunk_repo.py
@tests/test_retriever.py
@tests/test_rag_eval.py
@data/policies/

<interfaces>
Existing eval scoring to preserve:
```python
result = await retriever.search(query=case["query"], tenant_id=tenant_id, top_k=5)
hit = bool(set(case["expected_chunk_ids"]) & {e.chunk_id for e in result.evidence})
```

Existing retriever thresholds to preserve as user-facing evidence semantics:
```python
STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55
```

Existing repository trust boundary to preserve:
```python
PolicyChunk.tenant_id == tenant_id
PolicyDocument.tenant_id == tenant_id
similarity_expr >= min_similarity
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add retrieval audit and baseline diagnostics</name>
  <files>.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md, scripts/eval_rag_hit_at_5.py, tests/test_rag_eval.py</files>
  <read_first>
  - .planning/phases/02-rag-pipeline/06-SUMMARY.md
  - scripts/eval_rag_hit_at_5.py
  - eval/golden_rag_queries.jsonl
  - tests/test_rag_eval.py
  </read_first>
  <behavior>
  - The audit records Plan 06 baseline evidence before any retrieval change.
  - The official eval remains exact `expected_chunk_ids` Hit@5 plus fallback accuracy.
  - Diagnostics may inspect deeper candidates, but diagnostics do not change official scoring.
  </behavior>
  <action>
  Create `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md` and seed it with:
  - Plan 06 baseline: `Hit@5: 58.3%`, `Fallback accuracy: 100.0%`, 7/12 non-fallback hits.
  - The five failed-case categories and reasons from `06-SUMMARY.md`.
  - A "Before Plan 07" section for live ranked evidence.

  If `scripts/eval_rag_hit_at_5.py` already prints enough ranked failed-case evidence from Plan 06, do not broaden it. If it cannot inspect deeper candidates, add a diagnostic-only helper or flag that can request `top_k=20` for audit output while keeping default official eval behavior unchanged at `top_k=5`.

  Do not change pass/fail criteria in this task.
  </action>
  <acceptance_criteria>
  - `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md` exists.
  - Audit includes `Before Plan 07`, `Hit@5: 58.3%`, and `Fallback accuracy: 100.0%`.
  - If eval script changes, `DEFAULT_THRESHOLD = 0.80`, default `top_k=5`, and expected-chunk scoring remain unchanged.
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py -q` passes.
  </acceptance_criteria>
  <verify>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py -q</automated>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --help</automated>
  </verify>
  <done>The baseline retrieval gap is documented before implementation, and official eval scoring remains unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Enrich document embedding input with title and section context</name>
  <files>src/rag/ingestion.py, tests/test_ingestion.py</files>
  <read_first>
  - src/rag/ingestion.py
  - src/rag/chunker.py
  - scripts/ingest_policies.py
  - data/policies/refund_policy.md
  </read_first>
  <behavior>
  - Embedding text includes document title and section heading.
  - Database content remains the raw chunk text.
  - Re-running ingestion regenerates enriched embeddings without changing chunk IDs.
  </behavior>
  <action>
  Modify `src/rag/ingestion.py` so `embed_documents()` receives enriched text:
  ```python
  texts = [
      f"{title} / {chunk.section}: {chunk.content}" if chunk.section != "intro" else f"{title}: {chunk.content}"
      for chunk in chunks
  ]
  ```

  Keep `PolicyChunk.content=chunk.content` unchanged. Do not change chunk IDs, section names, document metadata, transaction shape, or repository writes.

  Add `tests/test_ingestion.py` if no suitable ingestion test file exists. Use a mock embedder/session/repository boundary where practical. The test should prove `embed_documents()` receives title/section-enriched text while persisted chunk content remains raw.
  </action>
  <acceptance_criteria>
  - `src/rag/ingestion.py` constructs embedding texts with `title` and `chunk.section`.
  - `PolicyChunk.content=chunk.content` remains present.
  - No chunker behavior or chunk IDs change.
  - `tests/test_ingestion.py` covers enriched embed input or the implementation is covered by an explicit audit note explaining why DB-heavy ingestion tests are deferred.
  </acceptance_criteria>
  <verify>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/test_retriever.py -q</automated>
  </verify>
  <done>New embeddings carry document context while persisted evidence snippets remain unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add deterministic hybrid reranking over deeper vector candidates</name>
  <files>src/rag/retriever.py, tests/test_retriever.py</files>
  <read_first>
  - src/rag/retriever.py
  - src/repositories/policy_chunk_repo.py
  - tests/test_retriever.py
  - .planning/phases/02-rag-pipeline/06-SUMMARY.md
  </read_first>
  <behavior>
  - Retriever requests a deeper candidate set from the existing tenant-filtered vector repository.
  - Final top-5 order is determined by deterministic hybrid score, not vector score alone.
  - Final evidence still excludes candidates below `MIN_SIMILARITY_THRESHOLD = 0.55`.
  - Fallback still depends on final evidence and best vector score under the existing threshold.
  </behavior>
  <action>
  Modify `src/rag/retriever.py`:
  - Add constants similar to:
    ```python
    QUERY_PREFIX = "电商售后政策查询: "
    INTERNAL_SEARCH_THRESHOLD = 0.40
    CANDIDATE_MULTIPLIER = 4
    TITLE_SECTION_BOOST = 0.10
    CONTENT_OVERLAP_BOOST = 0.05
    ```
  - Embed `f"{QUERY_PREFIX}{query}"` instead of the bare query.
  - Request deeper candidates with:
    ```python
    top_k=max(top_k * CANDIDATE_MULTIPLIER, top_k)
    min_similarity=INTERNAL_SEARCH_THRESHOLD
    ```
  - Add pure helpers such as `_query_terms(query)`, `_overlap_ratio(query_terms, text)`, and `_rerank_candidates(query, raw_results)` that:
    - normalize Chinese/alphanumeric text deterministically without external dependencies;
    - score vector similarity as the dominant component;
    - add a bounded boost for title/section overlap;
    - add a smaller bounded boost for content overlap;
    - tie-break by original vector rank to keep behavior stable.
  - Filter final reranked results to `score >= MIN_SIMILARITY_THRESHOLD` and return only the original `top_k`.

  Avoid the ineffective pattern from the old Plan 07: do not over-fetch and then simply slice the same vector order. The reranker must be capable of promoting a lower vector-ranked but lexically stronger candidate into final top-5.
  </action>
  <acceptance_criteria>
  - `src/rag/retriever.py` contains `_rerank_candidates`.
  - `Retriever.search()` calls `embed_query()` with `QUERY_PREFIX + query`.
  - `PolicyChunkRepository.search_similar()` is still the only DB retrieval path and still receives tenant/doc_type/risk_level filters.
  - Search requests `top_k * CANDIDATE_MULTIPLIER` candidates with `INTERNAL_SEARCH_THRESHOLD`.
  - Final evidence is filtered by `MIN_SIMILARITY_THRESHOLD = 0.55`.
  - `tests/test_retriever.py` proves a lexically stronger candidate initially ranked outside top-5 can be promoted into final evidence.
  - `tests/test_retriever.py` proves below-threshold candidates are not returned even if lexical overlap is high.
  - Existing strong/partial/no-evidence and tenant isolation tests still pass.
  </acceptance_criteria>
  <verify>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_retriever.py -q</automated>
  </verify>
  <done>Retriever selection uses deterministic hybrid reranking while preserving public evidence and isolation contracts.</done>
</task>

<task type="auto">
  <name>Task 4: Re-ingest, run live eval, and iterate only on ranking weights if needed</name>
  <files>src/rag/ingestion.py, src/rag/retriever.py, .planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md</files>
  <read_first>
  - scripts/ingest_policies.py
  - scripts/eval_rag_hit_at_5.py
  - .env
  - .planning/phases/02-rag-pipeline/06-SUMMARY.md
  </read_first>
  <action>
  Rebuild live embeddings and evaluate against the same demo tenant:
  ```bash
  set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7
  set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7
  ```

  Record before/after failed-case evidence in `07-RETRIEVAL-AUDIT.md`.

  If Hit@5 is still below 80%, do not change the golden set as a shortcut. Inspect failed-case candidates:
  - If expected chunks are present in top-20 candidates but not final top-5, adjust only bounded reranking weights or term extraction tests.
  - If expected chunks are absent from top-20, document the remaining gap and stop with `status: gaps_found`; do not claim EVAL-02 closure.
  - If a golden label is genuinely invalid, route that to a separate calibration plan with audit evidence instead of mixing it into this retrieval plan.
  </action>
  <acceptance_criteria>
  - Ingestion reports 15/15 successful documents and 90 chunks.
  - Live eval exits 0 with Hit@5 >= 80%.
  - Fallback accuracy remains >= 80%.
  - `07-RETRIEVAL-AUDIT.md` contains "After Plan 07" with failed-case or pass evidence.
  - Any reranking weight changes are covered by deterministic tests.
  </acceptance_criteria>
  <verify>
    <automated>set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7</automated>
    <automated>set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7</automated>
  </verify>
  <done>Live DB-backed retrieval meets EVAL-02 or leaves an explicit, evidenced residual retrieval gap without weakening labels.</done>
</task>

<task type="auto">
  <name>Task 5: Run regression suite and write Plan 07 summary</name>
  <files>.planning/phases/02-rag-pipeline/07-SUMMARY.md, .planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md</files>
  <read_first>
  - .planning/phases/02-rag-pipeline/06-SUMMARY.md
  - .planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md
  - .planning/phases/02-rag-pipeline/02-VERIFICATION.md
  - .planning/STATE.md
  </read_first>
  <action>
  Run focused and full verification:
  ```bash
  UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py tests/test_retriever.py tests/test_search_integration.py -q
  UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short
  UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src scripts tests
  ```

  Create `.planning/phases/02-rag-pipeline/07-SUMMARY.md` with:
  - status `complete` if live eval passes, otherwise `gaps_found`;
  - changed files and task commits;
  - before/after Hit@5 and fallback accuracy;
  - confirmation that tenant filtering, fallback threshold, and citation semantics were preserved;
  - any residual risk or follow-up plan if the live gate still fails.
  </action>
  <acceptance_criteria>
  - Focused pytest passes.
  - Full pytest passes.
  - Ruff passes.
  - `07-SUMMARY.md` exists and accurately reports pass or residual gap.
  - If live eval passed, EVAL-02 is safe to mark complete in Phase 2 verification/state docs.
  - If live eval failed, EVAL-02 remains incomplete and the summary states why.
  </acceptance_criteria>
  <verify>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py tests/test_retriever.py tests/test_search_integration.py -q</automated>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short</automated>
    <automated>UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src scripts tests</automated>
  </verify>
  <done>Plan 07 leaves an auditable summary and regression evidence aligned with the live result.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Query -> embedding provider | Query text is sent to DashScope for embedding and must not affect tenant scoping. |
| Embedding provider -> pgvector candidates | External embedding output influences candidate order but repository filters remain tenant-scoped. |
| Retriever reranker -> API evidence | Deterministic reranker changes final evidence order and must not return below-threshold evidence. |
| Local eval -> golden set | Eval labels remain exact chunk-ID expectations and are not loosened by retrieval changes. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-07-01 | Information Disclosure | Candidate retrieval | mitigate | Keep all retrieval through `PolicyChunkRepository.search_similar()` with tenant_id, doc_type, and risk_level filters. |
| T-02-07-02 | Tampering | Hybrid reranking | mitigate | Add deterministic tests proving reranking promotes lexical matches but still filters below `MIN_SIMILARITY_THRESHOLD`. |
| T-02-07-03 | Repudiation | Live eval result | mitigate | Record before/after failed-case evidence and commands in `07-RETRIEVAL-AUDIT.md` and `07-SUMMARY.md`. |
| T-02-07-04 | Denial of Service | Deeper candidate retrieval | accept | Candidate set is bounded to `top_k * CANDIDATE_MULTIPLIER` for a local/manual support corpus; no public unbounded retrieval is added. |
</threat_model>

<verification>
Overall gap closure checks:
- Plan 07 is discoverable by `gsd-sdk query phase-plan-index "02"` as plan `07`.
- `gsd-sdk query frontmatter.validate .planning/phases/02-rag-pipeline/07-PLAN.md --schema plan` passes.
- `gsd-sdk query verify.plan-structure .planning/phases/02-rag-pipeline/07-PLAN.md` passes.
- Deterministic reranker tests pass without DashScope.
- Live ingestion regenerates 90 enriched embeddings.
- Live DB-backed eval exits 0 with Hit@5 >= 80% and fallback accuracy >= 80%.
- Full pytest and ruff pass.
</verification>

<success_criteria>
- EVAL-02 is satisfied by live exact chunk-ID Hit@5 >= 80%, not by doc-only scoring or label gaming.
- RAG-02 remains satisfied: chunk IDs and stored chunk content remain stable; only embedding input changes.
- RAG-04 remains satisfied: tenant, doc_type, and risk_level filters are preserved.
- RAG-06 remains satisfied: no-evidence fallback still uses the 0.55 user-facing threshold.
- RAG-07 remains satisfied: citations still validate against returned chunk IDs.
</success_criteria>

<source_audit>
## Multi-Source Coverage Audit

| Source | Item | Coverage |
|--------|------|----------|
| 06-SUMMARY | Calibration alone cannot close the gap | Objective, Task 1, Task 4 |
| REQ | EVAL-02: measurable Hit@5 >= 80% | Tasks 4-5 |
| REQ | RAG-02: chunking/embedding pipeline | Task 2 |
| REQ | RAG-04: tenant and metadata filtering | Task 3 tests and threat model |
| REQ | RAG-06: fallback threshold | Task 3 acceptance |
| REQ | RAG-07: chunk-ID citation validation | Success criteria |
| CODE | Current vector-only retriever top-5 | Task 3 replaces final ordering with hybrid reranking |
| CODE | Eval exact expected_chunk_ids scoring | Task 1 and Task 4 preserve official scoring |
</source_audit>

<output>
After completion, create `.planning/phases/02-rag-pipeline/07-SUMMARY.md`.
</output>
