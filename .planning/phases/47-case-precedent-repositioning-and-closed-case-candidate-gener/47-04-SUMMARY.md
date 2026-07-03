---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
plan: 04
subsystem: memory
tags: [case-memory, case-precedent, retrieval, docs, validation, mem-04]

requires:
  - phase: 47-03
    provides: governed closed-case candidate submission through CaseMemoryService.submit_case_memory_candidate
provides:
  - approved closed-case generated precedent retrieval tests with query_embedding=None
  - planner-facing search_case_memory and reviewed memory context contract stability tests
  - Phase 47 docs/current map alignment for closed_case_cwc_candidate and reviewed case-memory retrieval
  - DEFER-2 delivery trace with DEFER-3 preserved for Phase 48
  - final green Phase 47 validation artifact
affects: [memory, case-memory, case-precedent, reviewed-memory-context, tools, phase-48]

tech-stack:
  added: []
  patterns:
    - TDD RED/GREEN for retrieval contract coverage
    - metadata/text-first reviewed case-memory retrieval with optional embeddings
    - source identity in source_ref_json separate from reusable retrieval scope

key-files:
  created:
    - .planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-04-SUMMARY.md
  modified:
    - tests/memory/test_case_memory_retrieval.py
    - tests/memory/test_reviewed_memory_context_boundary.py
    - tests/agent/test_reviewed_memory_context_retrieve.py
    - tests/tools/test_catalog.py
    - tests/memory/test_phase47_case_precedent_alignment.py
    - docs/contract-spec.md
    - docs/current-implementation-map.md
    - docs/architecture-overview.md
    - .planning/MEMORY-REDESIGN-DECISIONS.md
    - .planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-VALIDATION.md

key-decisions:
  - "ToolCallContext stays case-id-free; planner-facing search_case_memory scopes reviewed retrieval from tenant/user/thread/merchant context only."
  - "Closed-case candidate source identity stays in source_ref_json.business_object_type/business_object_id while reusable retrieval uses CaseMemory.scope_type/scope_id."
  - "DEFER-2 is delivered by Phase 47; DEFER-3 remains explicitly named as Phase 48 explicit preference memory scope."

patterns-established:
  - "Approved generated precedents are retrievable by metadata/text filters with query_embedding=None."
  - "Reviewed memory context keeps active CWC and reviewed case memory separate."
  - "Final validation updates occur only after exact MOCA-entrypoint commands pass."

requirements-completed: [MEM-04]

duration: 19min
completed: 2026-07-03
---

# Phase 47 Plan 04: Retrieval Contract and Validation Summary

**Reviewed closed-case generated precedents are test-locked as retrievable without embeddings while Phase 47 docs and validation now reflect the final case-memory boundary.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-03T14:37:33Z
- **Completed:** 2026-07-03T14:56:48Z
- **Tasks:** 2
- **Files modified:** 10
- **Files created:** 1

## Accomplishments

- Added TDD coverage proving approved `closed_case_cwc_candidate` rows are retrieved with `query_embedding=None` under merchant scope and exact case scope.
- Locked planner-facing `search_case_memory` and reviewed-memory-context behavior so they continue to use reviewed case memory without requiring `ToolCallContext.case_id`.
- Updated contract/current architecture docs to describe `ClosedCasePrecedentService -> CaseMemoryService.submit_case_memory_candidate(...)` and `MemoryToolExecutor -> CaseMemoryService.retrieve_reviewed(...)`.
- Recorded DEFER-2 as implemented by Phase 47 while preserving `DEFER-3 -> Phase 48` as out of scope.
- Marked `47-VALIDATION.md` complete only after the final Phase 47 automated gate passed.

## Task Commits

1. **Task 1 RED: retrieval contract tests** - `5e249cc` (test)
2. **Task 1 GREEN: retrieval test compatibility fixes** - `4caab1c` (feat)
3. **Task 2: docs/current maps and validation closeout** - `70fee08` (docs)

**Plan metadata:** pending final metadata commit.

## Files Created/Modified

- `tests/memory/test_case_memory_retrieval.py` - Added approved generated-precedent merchant and exact case-scope retrieval assertions with `query_embedding=None`.
- `tests/memory/test_reviewed_memory_context_boundary.py` - Added reviewed memory context coverage for generated precedents and approval visibility.
- `tests/agent/test_reviewed_memory_context_retrieve.py` - Locked active CWC and reviewed case memory separation.
- `tests/tools/test_catalog.py` - Guarded `search_case_memory` context construction without `case_id`.
- `tests/memory/test_phase47_case_precedent_alignment.py` - Added static contract checks for case-id-free tool context and executor scope construction.
- `docs/contract-spec.md` - Documented `closed_case_cwc_candidate`, review requirement, source identity, and retrieval scope split.
- `docs/current-implementation-map.md` - Mapped closed-case precedent generation and reviewed case-memory search.
- `docs/architecture-overview.md` - Updated the memory layer split across session context, CWC, case memory, and Phase 48 explicit preference memory.
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - Marked DEFER-2 delivered by Phase 47 and kept DEFER-3 for Phase 48.
- `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-VALIDATION.md` - Recorded green task rows and exact final command results.
- `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-04-SUMMARY.md` - Created this execution summary.

## Decisions Made

- Keep `ToolCallContext` narrow and case-id-free; exact case-scope retrieval is service-level capability, not planner context widening.
- Preserve generated candidate source identity in `source_ref_json` and retrieval publication scope in `CaseMemory.scope_type/scope_id`.
- Treat long-term explicit preference memory as Phase 48 only; Phase 47 does not implement preference writes or change `long_term_memory_retrieve`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py tests/memory/test_phase47_case_precedent_alignment.py -x -q`
  - RED result before GREEN: expected failing test, `TypeError: _case_row() got an unexpected keyword argument 'source_type'`.
  - GREEN result after implementation: `108 passed, 1 warning in 114.22s (0:01:54)`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_memory_policy.py tests/test_memory_review_api.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py -q`
  - Result: `151 passed, 1 warning in 132.84s (0:02:12)`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py tests/memory/test_phase46_session_context_alignment.py -q`
  - Result: `20 passed, 1 warning in 0.09s`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py src/repositories/refund_repo.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -q`
  - Result: `10 passed, 1 warning in 0.03s`.

The pytest warning is the existing LangGraph/LangChain pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None beyond the expected TDD RED failure before the GREEN compatibility fix.

## Known Stubs

- `docs/current-implementation-map.md:40` documents the existing `long_term_memory_retrieve` placeholder. This is intentional and remains Phase 48 explicit preference memory scope, not a Phase 47 blocker.
- Stub scan also found empty collections in test fixtures; these are intentional fixture values, not product stubs.

## Threat Flags

None - this plan added tests and documentation only, with no new network endpoint, auth path, file access pattern, schema change, or trust boundary beyond the reviewed retrieval paths already covered by the plan threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 47 is ready for closeout. Phase 48 can start from a stable boundary: `case_memories` is reviewed closed-case precedent, active case working state stays in CWC, and explicit preference memory remains separate future work.

## Self-Check: PASSED

- Verified all created/modified plan files exist.
- Verified task commits exist in git history: `5e249cc`, `4caab1c`, `70fee08`.
- No missing files or missing commits found.

---
*Phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener*
*Completed: 2026-07-03*
