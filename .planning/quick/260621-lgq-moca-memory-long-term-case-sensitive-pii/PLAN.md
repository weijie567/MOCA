# Quick Task 260621-lgq: MOCA memory long-term/case hardening

**Date:** 2026-06-21
**Status:** complete

## Scope

Fix the first four memory issues identified from current code:

1. Unify prompt-injection PII rules for long-term and case memory so sensitive memory is not written as immediately retrievable context and is not returned to prompt-facing reads.
2. Add active duplicate protection for case memory candidate writes.
3. Add a concrete management entry point for long-term and case memory review lifecycle.
4. Improve case memory relevance by avoiding broad no-query retrieval in the graph read path.

## Plan

1. Add shared memory PII constants and update long-term/case services and repositories.
2. Add duplicate lookup for case memory and return a skipped write result for duplicate active identity.
3. Add FastAPI memory review router with pending list plus approve/reject/delete/forget actions for long-term and case memory.
4. Require a query for graph-level reviewed case memory retrieval and project only safe reviewed memory.
5. Add focused tests for each changed behavior and run targeted pytest.

## Verification

- `pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/agent/test_graph.py`
- Additional API tests if a new router is added.

## Result

Completed with `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/agent/test_graph.py tests/test_memory_review_api.py`.
