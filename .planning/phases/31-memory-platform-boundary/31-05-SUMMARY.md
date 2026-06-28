---
phase: 31-memory-platform-boundary
plan: 31-05
subsystem: memory
tags: [memory, trusted-context, reviewed-memory, merchant-scope, contextual-only]

requires:
  - phase: 31-02
    provides: RED reviewed-memory trusted-scope and authority-boundary tests
  - phase: 31-03
    provides: contextual-only memory DTOs and MemoryContextService facade
  - phase: 31-04
    provides: AgentState target memory_context fields and per-turn reset behavior
provides:
  - Trusted-scope reviewed long-term/case memory retrieval through MemoryContextService
  - Target reviewed_memory_context_retrieve node with structured memory_context bundle
  - long_term_memory_retrieve compatibility wrapper delegated through the target node
  - Structured memory_context prompt projection using existing memory sanitizers
affects: [31-06, 32, 33, 35, APF-10]

tech-stack:
  added: []
  patterns:
    - Trusted-scope fail-closed memory facade over existing lifecycle services
    - Target node plus legacy wrapper compatibility during graph vocabulary migration
    - Contextual-only reviewed memory refs/status refs mirrored into legacy aliases

key-files:
  created:
    - src/agent/nodes/reviewed_memory_context_retrieve.py
    - .planning/phases/31-memory-platform-boundary/31-05-SUMMARY.md
  modified:
    - src/memory/context_service.py
    - src/agent/nodes/long_term_memory_retrieve.py
    - src/agent/context/projectors.py
    - tests/agent/test_memory_evidence_boundary.py

key-decisions:
  - "Reviewed memory retrieval is fail-closed without TrustedContext, actor merchant scope, explicit/trusted merchant scope, or verified case scope."
  - "Tenant/global reviewed memory retrieval remains unsupported and returns tenant_global_memory_unsupported."
  - "The legacy long_term_memory_retrieve node delegates through reviewed_memory_context_retrieve while preserving old llm_outputs metrics."
  - "During the compatibility window, a single non-wildcard trusted actor merchant can seed the legacy wrapper path only when routing_hints.needs_long_term_memory is true."

patterns-established:
  - "MemoryContextService derives retrieval scopes from TrustedContext plus explicit/trusted merchant or case inputs, then calls LongTermMemoryService/CaseMemoryService only."
  - "reviewed_memory_context_retrieve returns memory_context, memory_context_bundle, reviewed_memory_context_retrieve_status, and legacy long_term_memory/case_memory aliases from one bundle."
  - "project_memory_context_for_prompt consumes structured long_term_items/case_items through the same prompt-safe sanitizer used for legacy memory lists."

requirements-completed: [APF-10]

duration: 19min
completed: 2026-06-28
---

# Phase 31 Plan 05: Reviewed Memory Context Boundary Summary

**Trusted-scope reviewed memory retrieval with contextual-only bundle output and legacy graph compatibility.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-06-28T06:40:01Z
- **Completed:** 2026-06-28T06:59:00Z
- **Tasks:** 2
- **Files modified:** 6 including this summary

## Accomplishments

- Replaced the reviewed-memory facade placeholder with trusted-scope retrieval that fails closed for missing trusted context, empty actor merchant scope, denied merchants, unverified case scope, tenant/global requests, and non-authoritative memory scope.
- Added `reviewed_memory_context_retrieve` returning `memory_context`, `memory_context_bundle`, `reviewed_memory_context_retrieve_status`, and legacy `long_term_memory` / `case_memory` aliases from the same contextual-only bundle.
- Converted `long_term_memory_retrieve` into a compatibility wrapper over the target node while preserving legacy `llm_outputs["long_term_memory_retrieve"]` metrics.
- Added structured memory-context prompt projection and a RED/GREEN test proving raw/private/debug/secret markers and authority refs do not reach prompt projection.

## Task Commits

1. **Task 1: Implement trusted-scope reviewed memory retrieval in MemoryContextService** - `5e1ff0f` (feat)
2. **Task 2 RED: Add structured memory projection negative test** - `2616308` (test)
3. **Task 2 GREEN: Implement reviewed memory context node and wrapper** - `2c4dc2c` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/memory/context_service.py` - Trusted-scope reviewed retrieval, fail-closed status reasons, DTO refs, and safe item projection through existing lifecycle services.
- `src/agent/nodes/reviewed_memory_context_retrieve.py` - Target graph-facing node returning structured memory context, status refs, trace metrics, node errors, and legacy aliases.
- `src/agent/nodes/long_term_memory_retrieve.py` - Legacy compatibility wrapper delegated through the target reviewed-memory node.
- `src/agent/context/projectors.py` - Adds `project_memory_context_for_prompt(...)` over structured `memory_context.long_term_items` and `memory_context.case_items`.
- `tests/agent/test_memory_evidence_boundary.py` - Adds structured memory-context projection sanitizer/non-authority regression.

## Decisions Made

- Kept storage and lifecycle ownership unchanged: `MemoryContextService` calls `LongTermMemoryService` and `CaseMemoryService`; it does not query repositories directly.
- Kept tenant/user/thread scopes as status metadata only, not prompt-facing retrieval scopes.
- Preserved legacy graph compatibility until Phase 32 by keeping `long_term_memory` / `case_memory` aliases and old `llm_outputs` metrics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Preserved reviewed item sanitizer at the service/node boundary**
- **Found during:** Task 2 (reviewed memory context node)
- **Issue:** Existing compatibility tests pass fake reviewed memory items containing unsafe authority/raw fields. Returning full service item mappings would let raw/private/debug/authority markers survive into `memory_context` and legacy aliases.
- **Fix:** Added allowlisted reviewed long-term/case item projection in `MemoryContextService` before refs are attached.
- **Files modified:** `src/memory/context_service.py`
- **Verification:** Final reviewed-memory, authority-boundary, and ruff commands passed.
- **Committed in:** `2c4dc2c`

---

**Total deviations:** 1 auto-fixed Rule 2 issue.
**Impact on plan:** The fix narrows output to prompt-safe contextual memory fields and preserves the plan's no-authority-widening boundary.

## Issues Encountered

- Expected TDD RED failure occurred for the new structured projector test before `project_memory_context_for_prompt(...)` existed.
- Existing LangGraph `allowed_objects` pending deprecation warning and node config typing warning appeared during focused tests; both are pre-existing and non-blocking.
- No authentication gates occurred.

## Known Stubs

None. Stub scan found only intentional empty lists/dicts for fail-closed bundles and default empty state fields.

## Threat Flags

None. The new reviewed-memory node/service trust surface is covered by the plan threat model; no new network endpoints, auth paths, schema changes, or direct repository queries were introduced.

## Verification

- `uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py -q` - passed (`11 passed`, 1 warning).
- `uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_graph.py::test_long_term_memory_reviewed_retrieval_safe_empty_when_no_reviewed_rows tests/agent/test_graph.py::test_long_term_memory_reviewed_retrieval_safe_empty_when_unavailable tests/agent/test_graph.py::test_long_term_memory_reviewed_snippets_flow_into_graph_state -q` - passed (`14 passed`, 4 warnings).
- `uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q` - passed (`21 passed`, 3 warnings).
- `uv run ruff check src/memory/context_service.py src/agent/nodes/reviewed_memory_context_retrieve.py src/agent/nodes/long_term_memory_retrieve.py src/agent/context/projectors.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py` - passed.
- Acceptance greps for fail-closed reasons, trusted-scope use, DTO construction, no direct SQL in `context_service.py`, target node fields, wrapper delegation, no active `_memory_scopes`, structured projector support, and sanitizer/non-authority assertions all passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 31-06 can implement memory write decision output knowing reviewed-memory reads now flow through the target contextual-only bundle and legacy aliases mirror guarded output. Phase 32 can later migrate graph vocabulary from `long_term_memory_retrieve` to `reviewed_memory_context_retrieve` without changing the target output contract.

---
*Phase: 31-memory-platform-boundary*
*Completed: 2026-06-28*

## Self-Check: PASSED

- Found summary file at `.planning/phases/31-memory-platform-boundary/31-05-SUMMARY.md`.
- Found key files `src/memory/context_service.py`, `src/agent/nodes/reviewed_memory_context_retrieve.py`, `src/agent/nodes/long_term_memory_retrieve.py`, `src/agent/context/projectors.py`, and `tests/agent/test_memory_evidence_boundary.py`.
- Found task commits `5e1ff0f`, `2616308`, and `2c4dc2c` in git history.
- Verified no shared `.planning/STATE.md`, `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md` changes were made by this executor.
- No unexpected tracked file deletions were detected in task commits.
