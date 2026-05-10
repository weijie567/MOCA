---
status: partial
phase: 02-rag-pipeline
source:
  - 02-VERIFICATION.md
started: 2026-05-10T14:36:00Z
updated: 2026-05-10T14:36:00Z
---

# Phase 2 Human UAT

## Current Test

Awaiting live external embedding and DB-backed retrieval verification.

## Tests

### 1. Live policy ingestion

expected: `scripts/ingest_policies.py` reports 15 successful documents and the database contains non-null `policy_chunks.embedding` rows for Phase 2 doc_keys such as `refund_policy`.
command: `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id <demo tenant uuid>`
result: pending

### 2. Live RAG Hit@5 eval

expected: `scripts/eval_rag_hit_at_5.py` prints Hit@5 and fallback accuracy at or above 80 percent and exits 0.
command: `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id <demo tenant uuid>`
result: pending

### 3. Live search endpoint

expected: Authenticated `/api/v1/search/` calls return relevant top-5 evidence for in-scope queries, metadata filters work, and unrelated queries return `no_evidence`.
command: `POST /api/v1/search/` with a `knowledge:read` user after live ingestion.
result: pending

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

No implementation gaps found. These checks require live DashScope embeddings and DB-backed semantic retrieval output.
