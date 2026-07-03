---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
reviewed: 2026-07-03T15:48:54Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/current-implementation-map.md
  - src/agent/nodes/reviewed_memory_context_retrieve.py
  - src/memory/case_memory.py
  - src/memory/case_precedent.py
  - src/memory/policy.py
  - src/memory/schemas.py
  - src/repositories/refund_repo.py
  - tests/agent/test_reviewed_memory_context_retrieve.py
  - tests/memory/test_case_memory_retrieval.py
  - tests/memory/test_case_precedent_generation.py
  - tests/memory/test_memory_policy.py
  - tests/memory/test_phase47_case_precedent_alignment.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/test_memory_review_api.py
  - tests/tools/test_catalog.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 47: Code Review Report

**Reviewed:** 2026-07-03T15:48:54Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found (info only)

## Summary

Deep re-review covered the Phase 47 docs, production memory/repository/node files, and scoped regression tests, including the two post-review-fix production files. I traced closed-case candidate generation through `ClosedCasePrecedentService -> CaseMemoryService.submit_case_memory_candidate(...)`, reviewed retrieval through `reviewed_memory_context_retrieve -> MemoryContextService.load_reviewed_memory_context(...) -> CaseMemoryService.retrieve_reviewed(...)`, and planner-facing case-memory lookup through `MemoryToolExecutor`.

No critical or warning issues were found. Prior WR-01 remains fixed: `closed_case_cwc_candidate` identity now hashes the full prompt-safe projected precedent text in `src/memory/case_memory.py:786-799`, and the same-merchant distinct-content regression is covered in `tests/memory/test_case_precedent_generation.py:388-456`. Prior WR-02 remains fixed: the reviewed-memory node derives `case_type` from slot `issue_type` in `src/agent/nodes/reviewed_memory_context_retrieve.py:418-425`, and the real node/service/repository regression is covered in `tests/agent/test_reviewed_memory_context_retrieve.py:448-508`.

The remaining finding is an info-only documentation drift in the storage-model appendix. The normative Phase 47 contract text and implementation are aligned: generated closed-case candidates are review-required, hidden until approval, scoped by `CaseMemory.scope_type/scope_id`, and retrievable through metadata/text filters without requiring embeddings.

Verification run:

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py -q`

Result: `122 passed, 1 warning in 120.41s`. The warning is the existing LangGraph/LangChain pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`.

Ruff check:

`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/reviewed_memory_context_retrieve.py src/memory/case_memory.py src/memory/case_precedent.py src/memory/policy.py src/memory/schemas.py src/repositories/refund_repo.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py`

Result: `All checks passed!`

## Info

### IN-01: Contract storage model is stale for case memory scope columns

**File:** `/Users/ming/projects/MOCA/docs/contract-spec.md:2456`
**Issue:** The `case_memories` storage-model appendix still lists fields such as `merchant_id`, `action_taken_json`, `approval_outcome_json`, `outcome_label`, and `source_run_id` at `docs/contract-spec.md:2461-2483`, while the implemented ORM uses `scope_type/scope_id`, `source_ref_json`, `source_identity_hash`, `created_by_run_id`, and the metadata/source identity indexes in `src/db/models.py:508-580`. This is documentation drift, not a Phase 47 correctness blocker, because the normative Phase 47 case-memory boundary text at `docs/contract-spec.md:1521-1527` and the implementation both use `CaseMemory.scope_type/scope_id`.
**Fix:** Update the storage-model appendix to match the implemented `case_memories` schema, or explicitly label the extra fields as future target state.

---

_Reviewed: 2026-07-03T15:48:54Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
