---
phase: 20-rag-hybrid-retrieval
status: fixed
type: post-review-hotfix
fixed_at: 2026-06-19
---

# Phase 20 Post-Review Fix

## Context

Phase 20 was already marked complete and tagged in `v1.3` when a follow-up
manual review found two retrieval correctness issues:

1. Sparse retrieval passed the full generated query search text into
   `plainto_tsquery("simple", ...)`. PostgreSQL combines plain tsquery terms
   with AND semantics, which made Chinese n-gram sparse retrieval too strict.
2. Migration `014_rag_hybrid_retrieval` backfilled `policy_chunks.search_text`
   with a lossy SQL expression rather than the same Python builder used by
   ingestion.

## Fix

- Added a dedicated sparse query builder that emits a bounded OR tsquery over
  trusted application tokens.
- Changed sparse repository search to use `to_tsquery("simple", ...)` with the
  generated OR expression.
- Kept fuzzy retrieval on the full retrieval search text while sparse retrieval
  receives the dedicated sparse query text.
- Added a maintenance backfill path for existing rows:
  `scripts/rebuild_policy_search_text.py`.
- Did not create a new hotfix migration because Phase 21 planning already owns
  the next migration number. Existing databases should run the maintenance
  script once after deploying this fix.

## Verification

- `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/test_ingestion.py tests/test_rag_eval.py -q`
  - 23 passed, 1 warning.
- `uv run pytest tests/knowledge tests/rag tests/test_ingestion.py tests/test_rag_eval.py tests/test_search_integration.py -q`
  - 90 passed, 1 warning.
- `uv run pytest -q`
  - 1005 passed, 6 warnings.
- `uv run ruff check src/rag/search_text.py src/rag/search_text_backfill.py src/knowledge/retrieval.py src/repositories/policy_chunk_repo.py scripts/rebuild_policy_search_text.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py`
  - passed.
- `git diff --check`
  - passed.

## Operator Action

Run the following once against any database that already contains
`policy_chunks` rows created before this fix:

```bash
uv run python scripts/rebuild_policy_search_text.py
```

For a single tenant:

```bash
uv run python scripts/rebuild_policy_search_text.py --tenant-id <tenant_uuid>
```
