---
status: complete
phase: 23-rag-reranker-query-rewrite
source:
  - .planning/phases/23-rag-reranker-query-rewrite/23-01-SUMMARY.md
  - .planning/phases/23-rag-reranker-query-rewrite/23-02-SUMMARY.md
  - .planning/phases/23-rag-reranker-query-rewrite/23-03-SUMMARY.md
  - .planning/phases/23-rag-reranker-query-rewrite/23-04-SUMMARY.md
  - .planning/phases/23-rag-reranker-query-rewrite/23-05-SUMMARY.md
  - .planning/phases/23-rag-reranker-query-rewrite/23-06-SUMMARY.md
started: 2026-06-20T02:10:23Z
updated: 2026-06-20T02:31:39Z
---

## Current Test

[testing complete]

## Tests

### 1. Query Rewrite Safety and Golden Aliases
expected: Ambiguous refund/shipment and support-wording queries produce bounded deterministic rewrite expansions with safe summary trigger metadata. Unsafe, out-of-domain, disabled, missing-context, and already-specific queries skip rewrite with deterministic skip reasons. Query rewrite DTOs do not store tenant, merchant scope, role, risk, effective time, raw prompt, provider payload, or private reasoning fields.
result: pass

### 2. Hybrid Retrieval Rewrite Channels and Rerank Ordering
expected: Retrieval runs the original query first, then bounded rewrite channels when applicable, passing the same tenant, doc type, risk, and effective-date filters to every channel. Original and rewrite candidates merge and dedupe before rerank and evidence construction. Rerank can promote a candidate outside the initial max_results cutoff, while EvidenceRefV1 score, rank, identity, and text hash remain retrieval-owned and clean.
result: pass

### 3. Reranker Provider Fallback and Score Validation
expected: Default reranking is deterministic, local, and credential-free. Optional provider output is sanitized and bounded; disabled, timeout, error, malformed output, budget overflow, boolean scores, and NaN scores all fall back safely with provider_malformed_output or the matching safe fallback reason instead of accepting bad provider data.
result: pass

### 4. Internal Diagnostics Without Authority Leakage
expected: retrieve_run().diagnostics carries only safe rewrite/rerank metadata, selected candidate IDs, fallback reasons, and bounded score components. Public KnowledgeSearchResult, EvidenceRefV1, ContextBuilder prompts, verifier claim support, action snapshots, AgentState, and ordinary surfaces do not treat rewrite/rerank diagnostics, raw provider payloads, selected channels, ranking explanations, or private reasoning as authority.
result: pass

### 5. Ablation CLI and Evaluation Report
expected: Running scripts/eval_rag_ablation.py with no arguments defaults to deterministic dry-run and succeeds without live provider credentials, network, Redis, or model services. Explicit deterministic-local mode fails closed until real retrieval execution exists. The dry-run report includes required variants, Phase 23 golden categories, hit/MRR/citation/no-evidence/fallback/latency metrics, config versions, fallback counters, bounded snippets, expected_variant_wins behavior, and wrong-chunk misses.
result: pass

### 6. Static Boundary and Deferred Scope Guards
expected: Phase 23 owner allowlists permit only rewrite, rerank, diagnostics, retrieval/service integration, eval, and their tests. Static guards still block deferred Phase 17 execution/outbox/compensation scope, RAG-5 backend replacement strings, Policy Source Operations UI/source-management strings, and AgentState authority expansions.
result: pass

### 7. Evidence Freshness Fail-Closed Validation
expected: Canonical evidence validation rejects stale, future-effective, expired, malformed-time, wrong-tenant, duplicate, wrong-scope, wrong-version, and text-hash-mismatched evidence with typed reason codes. A non-empty malformed effective_at does not disable freshness checks; it excludes evidence with freshness_invalid and effective_date_invalid.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
