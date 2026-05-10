---
phase: 02-rag-pipeline
reviewed: 2026-05-10T14:24:00Z
depth: standard
files_reviewed: 38
files_reviewed_list:
  - .env.example
  - data/policies/bulk_order_refund.md
  - data/policies/compensation_approval_sop.md
  - data/policies/compensation_rules.md
  - data/policies/cross_border_refund.md
  - data/policies/customer_escalation_sop.md
  - data/policies/digital_goods_refund.md
  - data/policies/high_value_refund.md
  - data/policies/merchant_dispute_faq.md
  - data/policies/merchant_faq.md
  - data/policies/partial_refund_rules.md
  - data/policies/quality_issue_policy.md
  - data/policies/refund_policy.md
  - data/policies/refund_sop.md
  - data/policies/refund_time_limits.md
  - data/policies/return_shipping.md
  - eval/golden_rag_queries.jsonl
  - pyproject.toml
  - scripts/eval_rag_hit_at_5.py
  - scripts/ingest_policies.py
  - src/api/main.py
  - src/api/routers/search.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/db/migrations/versions/002_rag_pipeline.py
  - src/db/models.py
  - src/rag/__init__.py
  - src/rag/chunker.py
  - src/rag/citation_validator.py
  - src/rag/embedder.py
  - src/rag/ingestion.py
  - src/rag/retriever.py
  - src/rag/schemas.py
  - src/repositories/policy_chunk_repo.py
  - src/repositories/policy_document_repo.py
  - tests/test_chunker.py
  - tests/test_retriever.py
  - tests/test_search_integration.py
findings:
  critical: 1
  warning: 4
  info: 0
  total: 5
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-10T14:24:00Z
**Depth:** standard
**Files Reviewed:** 38
**Status:** issues_found

## Summary

Reviewed the Phase 2 RAG pipeline source, API route, auth scope changes, migration, ingestion/eval scripts, tests, config, and knowledge corpus. The main risks are deployment/runtime correctness around the new `doc_key` field and tenant isolation in vector search joins. The policy corpus and golden query IDs are internally consistent with the chunker.

`uv.lock` was listed in the workflow input but excluded from review under the lock-file filter.

## Critical Issues

### CR-01: Migration adds the same non-null `doc_key` to every existing document before creating a unique constraint

**File:** `src/db/migrations/versions/002_rag_pipeline.py:22`
**Issue:** The upgrade adds `policy_documents.doc_key` as `nullable=False` with `server_default=""`, then immediately creates a unique constraint on `(tenant_id, doc_key)`. Any existing tenant with more than one policy document gets `doc_key = ""` for all rows, so the unique constraint creation fails and blocks migration. This is a normal path for databases seeded from Phase 1 policy documents.
**Fix:**
```python
op.add_column("policy_documents", sa.Column("doc_key", sa.String(64), nullable=True))
op.execute("""
    UPDATE policy_documents
    SET doc_key = lower(regexp_replace(title, '[^a-zA-Z0-9]+', '_', 'g')) || '_' || left(id::text, 8)
    WHERE doc_key IS NULL
""")
op.alter_column("policy_documents", "doc_key", nullable=False)
op.create_unique_constraint(
    "uq_policy_documents_tenant_doc_key",
    "policy_documents",
    ["tenant_id", "doc_key"],
)
```

Add a migration regression test or manual verification against a database with multiple existing `policy_documents` for the same tenant.

## Warnings

### WR-01: Current demo seed path no longer satisfies the new `PolicyDocument.doc_key` contract

**File:** `src/db/models.py:154`
**Issue:** `PolicyDocument.doc_key` is now non-nullable, but the existing demo seed path still constructs `PolicyDocument` rows without `doc_key`. The new eval script tells users to run `scripts/seed_demo.py` when no tenant exists, so the documented eval setup can fail before RAG ingestion/evaluation starts.
**Fix:** Update `scripts/seed_demo.py` to pass the stable document key when creating demo documents, and add a smoke test for `scripts/seed_demo.py --reset`.
```python
document = PolicyDocument(
    id=deterministic_id("policy_document", key),
    tenant_id=tenants["demo"].id,
    doc_key=key,
    doc_type=doc_type,
    title=title,
    ...
)
```

### WR-02: Vector search joins documents without enforcing matching document tenant

**File:** `src/repositories/policy_chunk_repo.py:45`
**Issue:** `search_similar` filters `PolicyChunk.tenant_id == tenant_id`, but the joined `PolicyDocument` is only constrained by `doc_id`. If a bad import, future bug, or manual data repair creates a chunk whose `tenant_id` does not match its document's `tenant_id`, the search result can expose another tenant's document metadata and use cross-tenant metadata filters.
**Fix:** Enforce tenant ownership on both sides of the join.
```python
.join(
    PolicyDocument,
    and_(
        PolicyChunk.doc_id == PolicyDocument.id,
        PolicyDocument.tenant_id == tenant_id,
    ),
)
.where(
    and_(
        PolicyChunk.tenant_id == tenant_id,
        similarity_expr >= min_similarity,
    )
)
```

Add an integration test with a deliberately mismatched chunk/document tenant pair and assert it is not returned.

### WR-03: Embedding environment variables in `.env.example` are ignored by the runtime service

**File:** `src/rag/embedder.py:15`
**Issue:** `.env.example` exposes `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, and `EMBEDDING_BATCH_SIZE`, but `EmbeddingService()` uses hard-coded defaults unless callers pass constructor arguments manually. Operators can change the advertised env vars and still ingest/search with the old model or dimensions, causing vector dimension mismatches or unexpected retrieval behavior.
**Fix:** Add these settings to `src/config.py` and make `EmbeddingService` default from settings.
```python
from src.config import settings

model: str = settings.embedding_model
dimensions: int = settings.embedding_dimensions
batch_size: int = settings.embedding_batch_size
```

Add a unit test that monkeypatches settings/env and verifies `EmbeddingService()` picks them up.

### WR-04: Generic exception responses expose internal exception text to clients

**File:** `src/api/main.py:77`
**Issue:** The global exception handler returns `{"reason": str(exc)}` in the public 500 response. RAG failures may include database errors, provider errors, file paths, or configuration details. Authenticated and unauthenticated clients should receive the trace ID, while sensitive internals should be logged server-side only.
**Fix:**
```python
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # log exc with trace_id/run_id here
    return _error_response(request, 500, INTERNAL_ERROR, "Internal server error")
```

Add an API test that forces an internal exception and asserts the response includes the standard error code and trace ID but not the exception message.

---

_Reviewed: 2026-05-10T14:24:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
