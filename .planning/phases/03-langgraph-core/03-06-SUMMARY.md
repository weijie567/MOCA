---
phase: 03-langgraph-core
plan: "06"
subsystem: agent
tags: [langgraph, trace, postgres, evidence_refs, pytest, ruff]

requires:
  - phase: 03-langgraph-core
    provides: "Phase 03 Plans 01-05 LangGraph graph, AgentRun/AgentStep schema, node trace steps, MemorySaver tests"
provides:
  - "AgentStep persistence maps trace_steps.tools_called into existing tool_name and tool_output_summary columns"
  - "Retrieval and recommendation nodes write compact evidence_refs into trace steps and persistent AgentState memory"
  - "Same-thread MemorySaver regression proves evidence_refs survive across turns while retrieved_evidence remains per-turn"
affects: [approval-workflow, agent-audit, rag-citations]

tech-stack:
  added: []
  patterns:
    - "Compact evidence refs only: doc_key, chunk_id, title, confidence, retrieved_at, optional section"
    - "Existing AgentStep JSONB columns carry tool/evidence audit details without schema changes"

key-files:
  created:
    - tests/agent/test_trace.py
  modified:
    - src/agent/trace.py
    - src/agent/nodes/retrieve_policy_evidence.py
    - src/agent/nodes/generate_recommendation.py
    - tests/agent/test_nodes/test_retrieve_policy_evidence.py
    - tests/agent/test_nodes/test_generate_recommendation.py
    - tests/agent/test_graph.py

key-decisions:
  - "Used existing AgentStep columns for tools_called and evidence_refs; no migration was added."
  - "Retained evidence_refs are persistent memory references only; current-turn no-evidence still produces insufficient_evidence."

patterns-established:
  - "Trace persistence normalizes tools_called plus legacy tool_name into a bounded comma-separated AgentStep.tool_name."
  - "Evidence memory merges refs by doc_key/chunk_id and preserves prior refs when current retrieval has no qualifying evidence."

requirements-completed: [AGNT-04, AGNT-05, AGNT-06, RAG-05, SAFE-06]

duration: 7min
completed: 2026-05-11
---

# Phase 03 Plan 06: Gap Closure Summary

**Trace audit rows now preserve tool/evidence details by run_id, and same-thread evidence_refs persist without weakening current-turn evidence gates.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-11T23:20:13Z
- **Completed:** 2026-05-11T23:27:01Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added a DB-backed AgentStep regression that queries by `run_id` and verifies tools_called-derived tool names plus persisted evidence refs.
- Updated trace persistence to store normalized tool names and `tools_called` in existing AgentStep columns, with no migration.
- Added node and graph regressions proving compact evidence_refs are written to persistent memory and trace steps while no-evidence turns still refuse definitive answers.

## Task Commits

1. **Task 1 RED: Trace persistence regression** - `0dcce02` (test)
2. **Task 1 GREEN: Persist trace tool names** - `61b94ba` (feat)
3. **Task 2 RED: Evidence memory node regressions** - `c9077bc` (test)
4. **Task 2 GREEN: Persist validated evidence refs** - `414d288` (feat)
5. **Task 3 Proof: Same-thread evidence memory graph regression** - `77bcd46` (test)

## Files Created/Modified

- `tests/agent/test_trace.py` - DB-backed run_id query regression for AgentStep tool and evidence persistence.
- `src/agent/trace.py` - Normalizes `tools_called` and legacy `tool_name` into existing AgentStep audit columns.
- `src/agent/nodes/retrieve_policy_evidence.py` - Extracts compact refs from retrieval results, merges them into persistent memory, and attaches them to trace steps.
- `src/agent/nodes/generate_recommendation.py` - Writes only citation-validated refs into persistent memory and recommendation trace steps.
- `tests/agent/test_nodes/test_retrieve_policy_evidence.py` - Covers retrieval ref writes and prior-ref preservation on no evidence.
- `tests/agent/test_nodes/test_generate_recommendation.py` - Covers validated recommendation refs and invalid citation exclusion.
- `tests/agent/test_graph.py` - Covers same-thread retained refs with current-turn no-evidence refusal.

## Decisions Made

- Used the existing `AgentStep.tool_name`, `tool_output_summary`, and `evidence_refs` columns rather than adding any schema or migration.
- Kept retained `AgentState.evidence_refs` as compact audit/memory references only; answer generation remains gated by current `retrieved_evidence` and validated `recommendation_draft`.

## Deviations from Plan

None - plan executed within the existing-schema gap-closure scope.

## TDD Gate Compliance

- RED test commits exist for Task 1 and Task 2 before their production fixes.
- Task 3 graph proof was added after Task 2 production behavior existed, so it passed immediately as a higher-level regression and required no additional production change.

## Issues Encountered

- Sandbox-local Postgres access was blocked for DB-backed tests with `PermissionError: [Errno 1] Operation not permitted`; reran the affected pytest commands with approved local Postgres access.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q --tb=short` - passed, 1 test.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_nodes/test_generate_recommendation.py -q --tb=short` - passed, 9 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_trace.py -q --tb=short -m "not live"` - passed, 9 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -q --tb=short -m "not live"` - passed, 36 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 86 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/trace.py tests/agent/test_trace.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/retrieve_policy_evidence.py src/agent/nodes/generate_recommendation.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_nodes/test_generate_recommendation.py` - passed.

## Known Stubs

None. Stub scan only matched intentional empty-list/type-default initialization and no-evidence test fixtures.

## User Setup Required

None.

## Next Phase Readiness

Phase 03 gap closure is complete. Phase 04 approval workflow can rely on AgentStep audit rows preserving tool/evidence details and on same-thread evidence memory being retained without being used as automatic current-turn evidence.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/03-langgraph-core/03-06-SUMMARY.md`.
- Task commits found: `0dcce02`, `61b94ba`, `c9077bc`, `414d288`, `77bcd46`.
- No files were deleted by plan commits.

---
*Phase: 03-langgraph-core*
*Completed: 2026-05-11*
