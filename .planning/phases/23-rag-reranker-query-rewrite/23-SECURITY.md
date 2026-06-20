---
phase: 23-rag-reranker-query-rewrite
type: security
completed: 2026-06-20
verdict: pass
---

# Phase 23 Security Review

## Verdict

PASS. Phase 23 preserves existing authority boundaries while adding rewrite, rerank, diagnostics, and eval capabilities.

## Threat Mitigations Verified

- Trusted retrieval filters remain applied before candidates influence ranking. Tests inspect tenant, doc type, risk, and effective-date filters across original and rewrite channels.
- Rewrite output cannot widen trusted filters and safe summaries exclude raw prompts/provider payloads/private reasoning.
- Reranker final scores are diagnostic-only and do not replace `PolicyRetrievalHit.score`, `EvidenceRefV1.score`, `best_score`, status thresholds, ContextBuilder validation, verifier support, approval evidence, or action authority.
- Provider adapters are disabled by default and fall back safely for disabled, timeout, error, malformed output, and budget overflow cases.
- Diagnostics and ablation reports use safe candidate IDs, bounded snippets, safe score components, config versions, and fallback reasons only.
- `EvidenceRefV1` field set remains unchanged.
- Raw rewrite prompts, raw provider payloads, ranking diagnostics, private rerank reasoning, source-block/OCR/parser internals, raw tool facts, and unbounded policy text stay out of ordinary prompt/final/memory/replay/business/action surfaces.
- Deferred Phase 17 execution/outbox/compensation, RAG-5 backend replacement, Policy Source Operations UI, and AgentState authority expansion remain blocked by static guards.

## Review Finding Fixed

- `no_evidence_precision` originally used all cases as the denominator. Fixed in `21c639e` so precision is computed over predicted no-evidence cases only.

## Residual Risk

- No live provider implementation exists in Phase 23. Future provider work must keep the disabled-by-default, timeout, retry, budget, validation, and fallback contract intact.
