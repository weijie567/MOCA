---
phase: 16-long-term-case-memory
source_review: .planning/phases/16-long-term-case-memory/16-REVIEW.md
status: resolved
fixed: 2026-06-17T18:31:55Z
fix_commit: 506c50d
---

# Phase 16 Code Review Fixes

Phase 16 code review found 1 critical issue and 5 warnings. All findings were fixed in commit `506c50d` (`fix(16): close memory review findings`) and re-verified with focused, expanded, lint, schema-drift, and full-suite checks.

## Resolved Findings

| ID | Resolution |
| --- | --- |
| CR-01 | `LongTermMemoryService.supersede_memory()` now blocks `pii_classification="prohibited"` before mutating the previous row or inserting a replacement. Regression coverage asserts no replacement row is written and a `pii_blocked` skip event is emitted. |
| WR-01 | `canonical_source_identity_hash()` now returns `None` for source refs that lack a durable discriminator beyond `source_type` or run metadata. Durable event/message/tool/agent/business/outcome IDs still hash normally. |
| WR-02 | Long-term writes now check for an existing active `(tenant, scope, content_hash)` memory and return a skipped `duplicate_active_identity` result with an observable write event instead of hitting the unique index in normal duplicate-write flow. |
| WR-03 | `Base.metadata` now declares the case-memory embedding index as `ix_case_memories_embedding_hnsw` with HNSW/cosine options, matching migration `013_long_term_case_memory.py`. |
| WR-04 | Planner-visible `search_case_memory` results are accumulated into prompt-safe `state["case_memory"]` snippets in `investigate()` without becoming policy evidence, business facts, approval evidence, or action authority. |
| WR-05 | `MemoryToolExecutor` now preserves the required query argument in `CaseMemorySearchRequest`, rejects empty query text, and case-memory retrieval applies a content-text filter when no embedding is available. |

## Verification

- `uv run pytest tests/memory/test_memory_identity.py tests/memory/test_long_term_memory_service.py tests/memory/test_memory_schema.py tests/memory/test_case_memory_retrieval.py tests/agent/test_tools/test_unified_tool_manager.py::test_search_case_memory_dispatches_to_reviewed_case_memory_service tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory -q` - passed, 33 tests, 1 warning.
- `uv run pytest tests/memory tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_memory_evidence_boundary.py -q` - passed, 144 tests, 1 warning.
- `uv run ruff check src/ tests/` - passed.
- `uv run pytest -q` - passed, 980 tests, 6 warnings, 506.49s.
- `gsd-sdk query verify.schema-drift 16` - passed, `valid: true`, `issues: []`.

## Residual Risk

Concurrent duplicate writers can still race between the duplicate pre-check and insert at the database boundary. The normal duplicate-write path is now idempotent and evented; if Phase 16 later needs high-concurrency writer guarantees, add an insert race fallback around the active-identity unique constraint.
