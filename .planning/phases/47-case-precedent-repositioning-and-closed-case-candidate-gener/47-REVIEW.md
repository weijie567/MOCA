---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
reviewed: 2026-07-03T15:32:25Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/current-implementation-map.md
  - src/memory/case_precedent.py
  - src/memory/case_memory.py
  - src/agent/nodes/reviewed_memory_context_retrieve.py
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
status: clean
---

# Phase 47: Code Review Report

**Reviewed:** 2026-07-03T15:32:25Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** clean

## Summary

Re-reviewed the Phase 47 docs, implementation files, tests, and the code-review fix report after the WR-01/WR-02 fixes. Deep checks traced closed-case candidate generation through `ClosedCasePrecedentService -> CaseMemoryService.submit_case_memory_candidate(...)`, reviewed-memory retrieval through `reviewed_memory_context_retrieve -> MemoryContextService.load_reviewed_memory_context(...) -> CaseMemoryService.retrieve_reviewed(...)`, and the planner-facing reviewed case-memory boundaries.

No critical or warning issues remain. WR-01 is resolved: `closed_case_cwc_candidate` content identity now hashes the full prompt-safe projected precedent text in `src/memory/case_memory.py:786-799`, and the same-merchant distinct-content regression is covered in `tests/memory/test_case_precedent_generation.py:387`. WR-02 is resolved: the reviewed-memory node now derives `case_type` from slot `issue_type` in `src/agent/nodes/reviewed_memory_context_retrieve.py:418-425`, and the real node/service/repository regression is covered in `tests/agent/test_reviewed_memory_context_retrieve.py:448`.

Verification run:

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py -q`

Result: `122 passed, 1 warning in 123.65s`.

## Info

### IN-01: Contract storage model is stale for case memory scope columns

**File:** `/Users/ming/projects/MOCA/docs/contract-spec.md:2456`
**Issue:** The `case_memories` storage model still lists fields and indexes such as `merchant_id`, `action_taken_json`, `approval_outcome_json`, `outcome_label`, `source_run_id`, and an index on `(tenant_id, merchant_id, case_type, created_at)`, while the implemented ORM uses polymorphic `scope_type/scope_id` and the metadata index on those columns. This remains documentation drift, not a Phase 47 correctness blocker, because the normative Phase 47 case-memory boundary text and implementation use `CaseMemory.scope_type/scope_id`.
**Fix:** Update the storage model to match the implemented `case_memories` schema, or explicitly label the extra fields/index as future target state.

---

_Reviewed: 2026-07-03T15:32:25Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
