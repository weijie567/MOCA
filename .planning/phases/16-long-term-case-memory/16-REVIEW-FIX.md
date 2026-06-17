---
phase: 16-long-term-case-memory
source_review: .planning/phases/16-long-term-case-memory/16-REVIEW.md
status: resolved
fixed: 2026-06-17T21:32:28Z
fix_commit: 2312abe
---

# Phase 16 Code Review Fixes

Phase 16 code review fixes have been applied in three passes. The first pass resolved the initial 1 critical issue and 5 warnings in commit `506c50d`. A follow-up deep review on 2026-06-18 found 3 additional long-term memory lifecycle warnings. A later Codex comprehensive lifecycle review found 4 more warning-class edge cases around pending publication, supersede anchors, expired approvals, and expired tombstone identities.

## 2026-06-18 Comprehensive Review Follow-Up

| ID | Resolution |
| --- | --- |
| WR-04 | `supersede_memory()` now requires the previous row to be current, published, undeleted, and unexpired before attaching a replacement, so deleted/rejected/pending/superseded rows cannot be used as correction anchors. |
| WR-05 | Ordinary `needs_review` long-term candidates are inserted as non-current, and legacy unpublished-current rows for the same content are retired before duplicate detection, so a later explicit/deterministic same-content write can publish normally. |
| WR-06 | Approving long-term memory now rejects expired pending rows; pending supersede approval also verifies that the previous row remains current/published/unexpired before superseding it. Expired auto-approved replacement candidates are skipped without mutating the previous memory. |
| WR-07 | Long-term and case tombstone creation now retires expired tombstones for the same content/source identity before checking for an active tombstone or inserting a replacement, aligning query behavior with the partial unique indexes. |

## 2026-06-18 Comprehensive Review Verification

- `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_memory_tombstones.py tests/memory/test_case_memory_retrieval.py -q` - passed, 31 tests, 1 warning.
- `uv run ruff check src/memory tests/memory` - passed.
- `uv run pytest tests/memory tests/agent/test_memory_evidence_boundary.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py -q` - passed, 152 tests, 1 warning.
- `uv run pytest -q` - passed, 988 tests, 6 warnings, 564.26s.

## 2026-06-18 Re-Review Resolutions

| ID | Resolution |
| --- | --- |
| WR-01 | `supersede_memory()` now inserts review-required replacements as non-current `needs_review` candidates, leaving the existing approved memory current and retrievable until the replacement is approved. Approval of the pending replacement now supersedes the previous current row atomically. |
| WR-02 | Long-term `approve_memory()` and `reject_memory()` now require an active `needs_review` row through repository-level lifecycle guards, so approved, rejected, deleted, tombstoned, or superseded rows cannot be moved back into visible lifecycle states. |
| WR-03 | Duplicate active-content detection now ignores expired rows and `write_memory()` retires expired current rows for the same identity before inserting a fresh same-content memory, avoiding retrieval gaps and unique-index conflicts. |

## 2026-06-18 Verification

- `uv run pytest tests/memory/test_long_term_memory_service.py -q` - passed, 11 tests, 1 warning.
- `uv run pytest tests/memory tests/agent/test_memory_evidence_boundary.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py -q` - passed, 147 tests, 1 warning.
- `uv run ruff check src/ tests/` - passed.
- `uv run pytest -q` - passed, 983 tests, 6 warnings, 579.79s.

## 2026-06-17 Resolved Findings

| ID | Resolution |
| --- | --- |
| CR-01 | `LongTermMemoryService.supersede_memory()` now blocks `pii_classification="prohibited"` before mutating the previous row or inserting a replacement. Regression coverage asserts no replacement row is written and a `pii_blocked` skip event is emitted. |
| WR-01 | `canonical_source_identity_hash()` now returns `None` for source refs that lack a durable discriminator beyond `source_type` or run metadata. Durable event/message/tool/agent/business/outcome IDs still hash normally. |
| WR-02 | Long-term writes now check for an existing active `(tenant, scope, content_hash)` memory and return a skipped `duplicate_active_identity` result with an observable write event instead of hitting the unique index in normal duplicate-write flow. |
| WR-03 | `Base.metadata` now declares the case-memory embedding index as `ix_case_memories_embedding_hnsw` with HNSW/cosine options, matching migration `013_long_term_case_memory.py`. |
| WR-04 | Planner-visible `search_case_memory` results are accumulated into prompt-safe `state["case_memory"]` snippets in `investigate()` without becoming policy evidence, business facts, approval evidence, or action authority. |
| WR-05 | `MemoryToolExecutor` now preserves the required query argument in `CaseMemorySearchRequest`, rejects empty query text, and case-memory retrieval applies a content-text filter when no embedding is available. |

## 2026-06-17 Verification

- `uv run pytest tests/memory/test_memory_identity.py tests/memory/test_long_term_memory_service.py tests/memory/test_memory_schema.py tests/memory/test_case_memory_retrieval.py tests/agent/test_tools/test_unified_tool_manager.py::test_search_case_memory_dispatches_to_reviewed_case_memory_service tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory -q` - passed, 33 tests, 1 warning.
- `uv run pytest tests/memory tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_memory_evidence_boundary.py -q` - passed, 144 tests, 1 warning.
- `uv run ruff check src/ tests/` - passed.
- `uv run pytest -q` - passed, 980 tests, 6 warnings, 506.49s.
- `gsd-sdk query verify.schema-drift 16` - passed, `valid: true`, `issues: []`.

## Residual Risk

Concurrent duplicate writers can still race between the duplicate pre-check/expired-row retirement and insert at the database boundary. The normal duplicate-write and expired-refresh paths are now idempotent/evented or refreshed correctly; if Phase 16 later needs high-concurrency writer guarantees, add an insert race fallback around the active-identity unique constraint.
