---
phase: 02-rag-pipeline
source_review: 02-REVIEW.md
status: fixed
fixed_at: 2026-05-11T03:05:00Z
findings_fixed:
  critical: 1
  warning: 5
  total: 6
---

# Phase 2 Code Review Fixes

## Fixed Findings

- CR-01: `002_rag_pipeline` now adds `doc_key` as nullable, backfills unique `legacy_<uuid>` keys for existing rows, then enforces non-null and the tenant-scoped unique constraint.
- WR-01: `scripts/seed_demo.py` now supplies stable `doc_key` values for seeded policy documents.
- WR-02: `PolicyChunkRepository.search_similar` joins `PolicyDocument` with a matching tenant condition, preventing mismatched chunk/document rows from leaking metadata.
- WR-03: `EmbeddingService` now defaults model, dimensions, batch size, and base URL from `src.config.settings`.
- WR-04: The generic FastAPI exception handler no longer returns internal exception text in public 500 responses.
- WR-05: Plan 07 retrieval fallback guard no longer suppresses high-confidence valid evidence solely because a support query lacks the hard-coded domain anchor vocabulary. The guard now reranks threshold-qualified candidates first, then applies a stronger score-and-overlap requirement only for no-anchor queries.

## Regression Coverage

- `tests/test_rag_migration.py` guards the doc_key migration order and prevents the empty string default regression.
- `tests/test_search_integration.py` covers mismatched chunk/document tenant exclusion.
- `tests/test_embedder.py` verifies `EmbeddingService()` reads embedding defaults from settings and clamps batch size.
- `tests/test_error_handlers.py` verifies generic 500 responses include trace ID but not exception text.
- `tests/test_retriever.py` verifies valid no-anchor support queries can still return strong evidence while weak out-of-domain policy matches still fall back.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check src scripts tests` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest tests/test_rag_migration.py tests/test_embedder.py tests/test_error_handlers.py tests/test_search_integration.py -q --tb=short` — 8 passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 39 passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/seed_demo.py --reset` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_retriever.py tests/test_rag_eval.py tests/test_ingestion.py -q` — 20 passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/rag/retriever.py tests/test_retriever.py` — passed
- `set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7` — passed, Hit@5 83.3%, fallback accuracy 100.0%
