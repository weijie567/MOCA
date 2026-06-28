---
phase: 32-intent-graph-migration
plan: 32-04
subsystem: trace-api-merchant-context
tags: [trace, api, target-graph, merchant-context, authorization, apf-11]
requires:
  - phase: 32-01
    provides: graph vocabulary projection helper
  - phase: 32-02
    provides: policy-registry route ownership
  - phase: 32-03
    provides: slot_resolution_gate projection metadata
provides:
  - Trace summary target graph projection fields
  - SSE and trace API target node projection fields
  - Safe target_merchant_context status projection helper
  - Owner/admin-only AgentRun, trace, and replay visibility regression coverage
affects: [phase-32, trace-summary, agent-runs-api, trace-api, replay-api]
tech-stack:
  added: []
  patterns:
    - Additive API projection beside legacy persisted node names
    - Sanitizer-first status metadata projection
key-files:
  created:
    - src/agent/merchant_context.py
  modified:
    - src/agent/graph_vocabulary.py
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - src/agent/trace.py
    - src/api/routers/agent_runs.py
    - src/api/routers/traces.py
    - src/repositories/trace_repo.py
    - tests/agent/test_trace.py
    - tests/agent/test_nodes/test_receive_request.py
    - tests/test_agent_runs_api.py
    - tests/test_trace_api.py
    - tests/replay/test_replay_api.py
key-decisions:
  - "Target graph projection is additive; persisted AgentStep.node_name remains the legacy implementation/debug value."
  - "target_merchant_context is evidence/status metadata only and is not read by AgentRun, trace, or replay authorization guards."
  - "resolved target_merchant_context requires service-approved BusinessFactRef-shaped refs; raw ids, slots, memory, prompt text, and LLM text are non-authoritative."
patterns-established:
  - "Trace summaries expose target_nodes_executed and graph_projection while keeping nodes_executed unchanged."
  - "Final SSE payloads include sanitized target_merchant_context status."
requirements-completed: [APF-11]
duration: 33min
completed: 2026-06-28
---

# Phase 32 Plan 04: Trace/Eval/API and Target Merchant-Context Evidence Summary

**Additive target graph/API projection with sanitized merchant-context status metadata**

## Performance

- **Duration:** 33 min
- **Started:** 2026-06-28T13:53:43Z
- **Completed:** 2026-06-28T14:26:15Z
- **Tasks:** 3
- **Files changed:** 13

## Accomplishments

- Added target graph projection to `build_trace_summary(...)`, SSE step events, trace API step responses, and trace timeline detail.
- Preserved legacy `nodes_executed`, `node`, `node_name`, and persisted `AgentStep.node_name` fields.
- Added `project_target_merchant_context(...)` with allowlisted output fields and strict `resolved` requirements based on service-approved business fact refs.
- Reset `target_merchant_context` at `receive_request` and exposed sanitized status metadata in trace summary and final SSE payloads.
- Added broad no-widening tests proving support, manager, merchant, supervisor, and approval_manager roles remain forbidden for non-owned run status/evidence/stream, trace, and replay access.

## Task Commits

1. **Task 1 RED:** `38d9073` (test) add failing target graph projection tests.
2. **Task 1 RED correction:** `85237de` (test) align target projection test names with canonical contract names.
3. **Task 1 GREEN:** `f946aa1` (feat) project target graph names in trace APIs.
4. **Task 2 RED:** `6e8e36d` (test) add failing target merchant context tests.
5. **Task 2 GREEN:** `133ba7f` (feat) add safe target merchant context projection.
6. **Task 3 test pin:** `495b8d5` (test) pin run trace replay visibility boundaries.

## Files Created/Modified

- `src/agent/merchant_context.py` - Safe `target_merchant_context.v1` status projection helper.
- `src/agent/trace.py` - Trace summary target graph and merchant-context projections.
- `src/api/routers/agent_runs.py` - SSE target node names and final payload merchant-context status.
- `src/api/routers/traces.py` - Trace step target projection.
- `src/repositories/trace_repo.py` - Timeline target node detail.
- `src/agent/state.py` / `src/agent/nodes/receive_request.py` - `target_merchant_context` state field and reset.
- `tests/agent/test_trace.py`, `tests/agent/test_nodes/test_receive_request.py`, `tests/test_agent_runs_api.py`, `tests/test_trace_api.py`, `tests/replay/test_replay_api.py` - Projection, sanitizer, reset, and visibility coverage.

## Decisions Made

- Router names appearing in trace steps are resolved by `project_trace_step_for_contract(...)` through router aliases after node lookup.
- `target_merchant_context.status == "resolved"` is emitted only from trusted BusinessFactRef-shaped refs and never from raw ids, slots, memory, prompt summaries, or LLM text.
- Existing owner/admin-only guards already satisfied Task 3, so Task 3 was completed as regression coverage without source changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed router alias projection in trace helper**
- **Found during:** Task 1 GREEN verification
- **Issue:** `route_after_slots` inside a trace step projected as `unknown_passthrough` instead of target router alias `route_after_slot_resolution`.
- **Fix:** `project_trace_step_for_contract(...)` now checks node vocabulary first and router vocabulary second.
- **Files modified:** `src/agent/graph_vocabulary.py`
- **Commit:** `f946aa1`

**2. [TDD Gate Note] Task 3 tests passed immediately**
- **Found during:** Task 3 RED attempt
- **Issue:** Newly added no-widening tests passed because owner/admin-only run, trace, and replay guards already existed.
- **Fix:** Committed the passing regression tests as a test pin; no source change was needed.
- **Files modified:** `tests/test_agent_runs_api.py`, `tests/test_trace_api.py`, `tests/replay/test_replay_api.py`
- **Commit:** `495b8d5`

## Known Stubs

None. Empty literals found by the scan are accumulators, type defaults, or explicit test fixture assertions, not deferred implementation stubs.

## Auth Gates

None.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py -q --tb=short` - 59 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_nodes/test_receive_request.py tests/test_agent_runs_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short` - 66 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py -q --tb=short` - 70 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_nodes/test_receive_request.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short` - 91 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py src/agent/merchant_context.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/repositories/trace_repo.py src/api/schemas/agent_runs.py src/api/schemas/approvals.py tests/agent/test_trace.py tests/agent/test_nodes/test_receive_request.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py` - passed.
- Static acceptance checks for projection fields, merchant-context sanitizer coverage, legacy field preservation, and no `target_merchant_context` authorization guard usage passed.

## Next Phase Readiness

Plan 32-05 can run final mapping-doc, static architecture, no-Phase-33-scope, and focused regression verification against the completed projection surfaces.

## Self-Check: PASSED

- Found `.planning/phases/32-intent-graph-migration/32-04-SUMMARY.md`.
- Found `src/agent/merchant_context.py`.
- Found `src/api/routers/agent_runs.py`.
- Found `tests/test_trace_api.py`.
- Found commits `38d9073`, `85237de`, `f946aa1`, `6e8e36d`, `133ba7f`, and `495b8d5`.

---
*Phase: 32-intent-graph-migration*
*Completed: 2026-06-28*
