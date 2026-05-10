---
phase: 02-rag-pipeline
source_review: 02-REVIEW.md
status: fixed
fixed_at: 2026-05-10T14:32:00Z
findings_fixed:
  critical: 1
  warning: 4
  total: 5
---

# Phase 2 Code Review Fixes

## Fixed Findings

- CR-01: `002_rag_pipeline` now adds `doc_key` as nullable, backfills unique `legacy_<uuid>` keys for existing rows, then enforces non-null and the tenant-scoped unique constraint.
- WR-01: `scripts/seed_demo.py` now supplies stable `doc_key` values for seeded policy documents.
- WR-02: `PolicyChunkRepository.search_similar` joins `PolicyDocument` with a matching tenant condition, preventing mismatched chunk/document rows from leaking metadata.
- WR-03: `EmbeddingService` now defaults model, dimensions, batch size, and base URL from `src.config.settings`.
- WR-04: The generic FastAPI exception handler no longer returns internal exception text in public 500 responses.

## Regression Coverage

- `tests/test_rag_migration.py` guards the doc_key migration order and prevents the empty string default regression.
- `tests/test_search_integration.py` covers mismatched chunk/document tenant exclusion.
- `tests/test_embedder.py` verifies `EmbeddingService()` reads embedding defaults from settings and clamps batch size.
- `tests/test_error_handlers.py` verifies generic 500 responses include trace ID but not exception text.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check src scripts tests` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest tests/test_rag_migration.py tests/test_embedder.py tests/test_error_handlers.py tests/test_search_integration.py -q --tb=short` — 8 passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 39 passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/seed_demo.py --reset` — passed
