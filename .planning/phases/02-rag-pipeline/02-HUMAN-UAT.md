---
status: issues_found
phase: 02-rag-pipeline
source:
  - 02-VERIFICATION.md
started: 2026-05-10T14:36:00Z
updated: 2026-05-10T14:52:00Z
---

# Phase 2 Human UAT

## Current Test

Live external embedding and DB-backed retrieval verification completed. Ingestion and live search passed; RAG Hit@5 failed the 80 percent threshold.

## Tests

### 1. Live policy ingestion

expected: `scripts/ingest_policies.py` reports 15 successful documents and the database contains non-null `policy_chunks.embedding` rows for Phase 2 doc_keys such as `refund_policy`.
command: `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`
result: passed
evidence: 15/15 manifest documents reported `success`; DB count after ingestion was `phase2_documents=15`, `phase2_chunks=90`, `embedded_chunks=90`.

### 2. Live RAG Hit@5 eval

expected: `scripts/eval_rag_hit_at_5.py` prints Hit@5 and fallback accuracy at or above 80 percent and exits 0.
command: `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`
result: failed
evidence: `Hit@5: 58.3%`, `Fallback accuracy: 100.0%`; command exited non-zero because Hit@5 was below the 80 percent threshold. Failed categories included boundary, faq, refund_rule, and sop exact expected chunk matches.

### 3. Live search endpoint

expected: Authenticated `/api/v1/search/` calls return relevant top-5 evidence for in-scope queries, metadata filters work, and unrelated queries return `no_evidence`.
command: `POST /api/v1/search/` with a `knowledge:read` user after live ingestion.
result: passed
evidence: Login as `cs_zhang` returned 200. A refund query returned `strong_evidence` with `refund_policy_001` in top 5. A filtered SOP/high-risk compensation query returned only `compensation_approval_sop` evidence. An unrelated bank-card query returned `no_evidence` with the fallback message.

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

RAG Hit@5 live evaluation failed: 58.3 percent versus the required 80 percent threshold. The live endpoint returns relevant evidence for sampled queries, but the golden-set exact expected chunk matching and/or retrieval ranking needs gap closure before Phase 2 can be marked complete.
