---
status: resolved
phase: 02-rag-pipeline
source:
  - 02-VERIFICATION.md
started: 2026-05-10T14:36:00Z
updated: 2026-05-11T03:10:00Z
---

# Phase 2 Human UAT

## Current Test

Live external embedding and DB-backed retrieval verification completed. Ingestion, live search, and RAG Hit@5 now pass after Plan 07 retrieval improvements.

## Tests

### 1. Live policy ingestion

expected: `scripts/ingest_policies.py` reports 15 successful documents and the database contains non-null `policy_chunks.embedding` rows for Phase 2 doc_keys such as `refund_policy`.
command: `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`
result: passed
evidence: 15/15 manifest documents reported `success`; DB count after ingestion was `phase2_documents=15`, `phase2_chunks=90`, `embedded_chunks=90`.

### 2. Live RAG Hit@5 eval

expected: `scripts/eval_rag_hit_at_5.py` prints Hit@5 and fallback accuracy at or above 80 percent and exits 0.
command: `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7`
result: passed
evidence: Plan 07 re-ingested 15 documents / 90 chunks and the live DB-backed eval passed with `Hit@5: 83.3%`, `Fallback accuracy: 100.0%`; this closed the earlier 58.3 percent gap without changing golden-set labels.

### 3. Live search endpoint

expected: Authenticated `/api/v1/search/` calls return relevant top-5 evidence for in-scope queries, metadata filters work, and unrelated queries return `no_evidence`.
command: `POST /api/v1/search/` with a `knowledge:read` user after live ingestion.
result: passed
evidence: Login as `cs_zhang` returned 200. A refund query returned `strong_evidence` with `refund_policy_001` in top 5. A filtered SOP/high-risk compensation query returned only `compensation_approval_sop` evidence. An unrelated bank-card query returned `no_evidence` with the fallback message.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

Resolved by Plan 07. RAG Hit@5 live evaluation now passes at 83.3 percent versus the required 80 percent threshold, and fallback accuracy remains 100.0 percent.
