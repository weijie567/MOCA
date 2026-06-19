---
phase: 16-long-term-case-memory
status: coverage_manifest
created: 2026-06-19
source: tests/memory/test_phase16_requirement_coverage.py
---

# Phase 16 Requirement Coverage Manifest

This manifest records the existing automated coverage anchors for Phase 16 long-term case memory requirements. It is a retrospective coverage artifact for the committed implementation and test suite; it does not change Phase 16 runtime behavior.

## Requirement Coverage

| Requirement | Verification focus | Test files | Command |
|-------------|--------------------|------------|---------|
| MEMID-01 | Stable memory content, candidate, source, and active identity hashes. | tests/memory/test_memory_identity.py | `uv run pytest tests/memory/test_memory_identity.py -q` |
| MEMSCHEMA-01 | Phase 16 memory tables, constraints, indexes, migration preflight objects, and downgrade order. | tests/memory/test_memory_schema.py | `uv run pytest tests/memory/test_memory_schema.py -q` |
| LONGMEM-01 | Published long-term profile memory retrieval excludes unpublished states and returns bounded prompt-safe views. | tests/memory/test_long_term_memory_repository.py | `uv run pytest tests/memory/test_long_term_memory_repository.py -q` |
| LONGMEM-02 | Long-term write lifecycle handles auto-approval, duplicate active writes, expired rows, review-required candidates, and prohibited PII skips. | tests/memory/test_long_term_memory_service.py | `uv run pytest tests/memory/test_long_term_memory_service.py -q` |
| LONGMEM-03 | Long-term review, delete, supersede, and replacement flows preserve current published semantics and emit events. | tests/memory/test_long_term_memory_service.py | `uv run pytest tests/memory/test_long_term_memory_service.py -q` |
| CASEMEM-01 | Case memory candidates require review before retrieval and expose observable candidate/reject events. | tests/memory/test_case_memory_retrieval.py | `uv run pytest tests/memory/test_case_memory_retrieval.py -q` |
| CASEMEM-02 | Case memory retrieval applies metadata filters before result projection and supports text query fallback. | tests/memory/test_case_memory_retrieval.py | `uv run pytest tests/memory/test_case_memory_retrieval.py -q` |
| CASEMEM-03 | Case memory remains separate from session memory and does not project policy evidence refs. | tests/memory/test_case_memory_retrieval.py tests/memory/test_session_precedent_search.py | `uv run pytest tests/memory/test_case_memory_retrieval.py tests/memory/test_session_precedent_search.py -q` |
| TOMBSTONE-01 | Forget flows create active tombstones that immediately exclude retrieval and block same-transaction rewrites. | tests/memory/test_memory_tombstones.py | `uv run pytest tests/memory/test_memory_tombstones.py -q` |
| TOMBSTONE-02 | Tombstones block source-identity rewrites, allow expired identities to be recreated, and avoid semantic-similarity matching. | tests/memory/test_memory_tombstones.py | `uv run pytest tests/memory/test_memory_tombstones.py -q` |
| MEMCTX-01 | Semantic episode projection creates candidates only and does not mutate session memory. | tests/memory/test_semantic_episode_projection.py | `uv run pytest tests/memory/test_semantic_episode_projection.py -q` |
| MEMCTX-02 | Semantic episode and legacy session precedent projections remain prompt-safe JSON views. | tests/memory/test_semantic_episode_projection.py tests/memory/test_session_precedent_search.py | `uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_session_precedent_search.py -q` |
| MEMREVIEW-01 | Review actions require active needs-review state and record approve/reject/delete/supersede decisions. | tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py | `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py -q` |
| MEMEVAL-01 | Phase 16 requirement coverage itself is enforced by this manifest test. | tests/memory/test_phase16_requirement_coverage.py | `uv run pytest tests/memory/test_phase16_requirement_coverage.py -q` |

