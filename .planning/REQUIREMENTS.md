# Requirements: MOCA v1.6 RAG Reranker + Query Rewrite

**Defined:** 2026-06-20
**Core Value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## v1.6 Requirements

Requirements for Phase 23. Each requirement must preserve the existing v1.3 hybrid retrieval, v1.4 parser/OCR provenance, and v1.5 ContextBuilder/verifier contracts unless explicitly stated otherwise.

### Query Rewrite

- [ ] **QRW-01**: System can produce a bounded policy-search query rewrite or expansion plan for ambiguous, underspecified, or domain-synonym user questions while preserving the original user query.
- [ ] **QRW-02**: System can skip query rewrite deterministically when the original query is already specific, out of domain, unsafe, or missing trusted context.
- [ ] **QRW-03**: Query rewrite output is a typed internal retrieval input that cannot add tenant, merchant, role, risk, document-type, effective-date, or policy-scope permissions not already present in trusted context.
- [ ] **QRW-04**: Retrieval can run original-query and rewritten-query candidate channels with deterministic candidate limits and merge/dedupe behavior before final ranking.
- [ ] **QRW-05**: Search results retain the original query and safe rewrite summary for eval/debug while ordinary user-facing answers do not expose rewrite prompts, model reasoning, or raw rewrite payloads.

### Reranker Interface

- [ ] **RRK-01**: System exposes a project-owned reranker interface that accepts bounded retrieval candidates and returns ranked candidates without changing canonical chunk content, text hashes, or policy version identity.
- [ ] **RRK-02**: System ships a deterministic default reranker path that can run without live model/provider credentials and preserve existing dense/sparse/fuzzy/RRF fallback behavior.
- [ ] **RRK-03**: Optional cross-encoder or external reranker adapters are config-gated, timeout-bounded, retry-bounded, and can fall back to the deterministic local/default ranking path.
- [ ] **RRK-04**: Reranker inputs exclude raw source-block/OCR/parser internals, raw tool payloads, private reasoning, unbounded policy text, and current business fact payloads.
- [ ] **RRK-05**: Reranker output records safe score components, provider/config version, fallback reason, and selected candidate IDs for maintainer/eval use without extending `EvidenceRefV1`.
- [ ] **RRK-06**: Reranking occurs before `EvidenceRefV1` construction or through a safe adapter that preserves final evidence rank, confidence score semantics, and ContextBuilder canonical validation.

### Ranking Explanations

- [ ] **EXP-01**: System can generate bounded ranking explanations for maintainers/evals that identify selected channels, rewrite contribution, reranker contribution, rank changes, and fallback reasons.
- [ ] **EXP-02**: Ranking explanations are available only through internal diagnostics/eval/report surfaces and are not included in ordinary prompts, final responses, memory, replay payloads, approval snapshots, or action drafts.
- [ ] **EXP-03**: Ranking diagnostics preserve tenant isolation and cannot expose evidence from unauthorized tenants, scopes, stale policy versions, or hash-invalid rows.
- [ ] **EXP-04**: Retrieval traces remain separate from policy evidence identity; `EvidenceRefV1` remains limited to canonical evidence fields plus rank/score.

### Evaluation and Latency

- [ ] **EVAL-01**: System has retrieval golden cases for query rewrite recall wins, synonym/alias queries, ambiguous merchant-support wording, out-of-domain no-evidence, stale/unauthorized evidence, and ranking regressions.
- [ ] **EVAL-02**: System can run retrieval ablation comparing dense-only, sparse-only, fuzzy-only, RRF baseline, rewrite-enabled, reranker-enabled, and rewrite+reranker variants.
- [ ] **EVAL-03**: System reports blocking metrics for Hit@K, MRR or equivalent rank quality, citation-support compatibility, no-evidence precision, unsafe retrieval rate, fallback rate, and latency percentiles.
- [ ] **EVAL-04**: Rewrite/rerank latency budgets are explicit for per-stage timeout, total retrieval timeout, candidate count, text/token size, retries, and provider config version.
- [ ] **EVAL-05**: Timeout, provider error, malformed output, budget overflow, and disabled-provider cases fall back to safe baseline retrieval or no-evidence behavior without weakening evidence validation.

### Boundary Preservation

- [ ] **BND-01**: Phase 23 preserves Phase 20 trusted retrieval filters for tenant, effective date, doc type, risk level, and knowledge scope before any candidate can affect final ranking.
- [ ] **BND-02**: Phase 23 preserves Phase 21 source-block/OCR/parser boundaries; provenance remains internal/debug/maintainer lookup data and does not become policy evidence identity.
- [ ] **BND-03**: Phase 23 preserves Phase 22 ContextBuilder and claim-verifier authority rules; reranker scores cannot substitute for semantic support, freshness, latest-version validity, or business fact authority.
- [ ] **BND-04**: Phase 23 does not implement Phase 17 external action execution, outbox, reconciliation, compensation dispatch, or external side effects.
- [ ] **BND-05**: Phase 23 does not implement RAG-5 external search backend replacement, Vespa/OpenSearch shadow testing, new vector database service, or Policy Source Operations UI.
- [ ] **BND-06**: Phase 23 keeps 17-prep AgentState cleanup as a future Phase 17 prerequisite and does not expand `AgentState` authority surfaces as part of retrieval-quality work.

## Future Requirements

Deferred to named owner phases. Tracked but not in the current roadmap.

### Phase 23 Stretch Only

- **P23-STRETCH-01**: System can use a live cross-encoder reranker provider in default local demos if credentials and deterministic fallback gates are available.
- **P23-STRETCH-02**: System can expose a maintainer CLI that prints per-case rewrite/rerank trace reports with redaction and tenant checks.
- **P23-STRETCH-03**: System can auto-tune reranker weights from eval results while preserving explicit config versioning and rollback.

### Named Future Owners

- **P17PREP-01**: AgentState Surface Contracts + Authority Isolation before real external execution — owner: 17-prep before Phase 17 External Action Execution.
- **P17-01**: Real external action execution, outbox, reconciliation, external idempotency, and compensation dispatch — owner: Phase 17 External Action Execution.
- **RAG5-01**: External `SearchBackend`, Vespa/OpenSearch, or a new vector database service — owner: Phase RAG-5 Optional External Search Backend.
- **PSO-01**: Policy source upload/review/lifecycle UI, source document viewer, and admin review workflow — owner: Policy Source Operations.
- **PSCOPE-01**: Tenant-over-global/default policy fallback and global policy precedence merge — owner: post-Phase 17 Policy Scope.

## Out of Scope

Explicitly excluded from v1.6 to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real external action execution, outbox, reconciliation, or compensation dispatch | Phase 17 owns real side effects. |
| AgentState surface-contract cleanup | Required before Phase 17, but not needed to safely do Phase 23 retrieval-quality work. |
| New search backend, Vespa/OpenSearch, or vector database replacement | Phase RAG-5 owns backend replacement; Phase 23 improves ranking on the current retrieval facade. |
| Policy source upload/review/lifecycle UI or source-document viewer | Policy Source Operations owns source-management workflows. |
| `EvidenceRefV1` identity changes | Would break policy evidence, action snapshot, replay, citation, ContextBuilder, and verifier contracts. |
| Source-block/OCR/provenance as policy evidence | Phase 21 provenance remains subordinate internal/debug metadata, not an authority ref. |
| Reranker scores as claim support | Phase 22 verifier owns support; retrieval ranking cannot replace claim verification. |
| Business facts as policy evidence | Violates Tool System authority separation. |
| Memory as policy evidence, current business fact authority, approval/action authority, replay truth, or audit truth | Violates the memory contextual-assistance boundary. |
| Always-on live provider reranking in default tests | Default tests must not require live model/provider credentials. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| QRW-01 | Phase 23 | Pending |
| QRW-02 | Phase 23 | Pending |
| QRW-03 | Phase 23 | Pending |
| QRW-04 | Phase 23 | Pending |
| QRW-05 | Phase 23 | Pending |
| RRK-01 | Phase 23 | Pending |
| RRK-02 | Phase 23 | Pending |
| RRK-03 | Phase 23 | Pending |
| RRK-04 | Phase 23 | Pending |
| RRK-05 | Phase 23 | Pending |
| RRK-06 | Phase 23 | Pending |
| EXP-01 | Phase 23 | Pending |
| EXP-02 | Phase 23 | Pending |
| EXP-03 | Phase 23 | Pending |
| EXP-04 | Phase 23 | Pending |
| EVAL-01 | Phase 23 | Pending |
| EVAL-02 | Phase 23 | Pending |
| EVAL-03 | Phase 23 | Pending |
| EVAL-04 | Phase 23 | Pending |
| EVAL-05 | Phase 23 | Pending |
| BND-01 | Phase 23 | Pending |
| BND-02 | Phase 23 | Pending |
| BND-03 | Phase 23 | Pending |
| BND-04 | Phase 23 | Pending |
| BND-05 | Phase 23 | Pending |
| BND-06 | Phase 23 | Pending |

**Coverage:**
- v1.6 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-06-20*
*Last updated: 2026-06-20 after v1.6 milestone start*
