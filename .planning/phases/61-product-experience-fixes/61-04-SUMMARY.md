---
phase: 61-product-experience-fixes
plan: 04
subsystem: agent metric graph integration
tags:
  - metrics
  - agent-graph
  - final-response
  - sse
dependency_graph:
  requires:
    - 61-03 scoped metric runtime
  provides:
    - metric tool invocation from existing graph
    - deterministic metric final response branch
    - safe metric SSE final payload metadata
  affects:
    - src/agent/nodes/investigate.py
    - src/agent/nodes/final_response.py
    - src/api/routers/agent_runs.py
tech_stack:
  added: []
  patterns:
    - deterministic metric fallback through ToolPlatform
    - response_kind projection from llm_outputs.final_response
    - allowlisted SSE payload metadata
key_files:
  created:
    - .planning/phases/61-product-experience-fixes/61-04-SUMMARY.md
  modified:
    - src/agent/nodes/investigate.py
    - src/agent/nodes/final_response.py
    - src/api/routers/agent_runs.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/agent/test_nodes/test_final_response.py
    - tests/agent/test_graph.py
    - tests/agent/test_intent_routing.py
    - tests/test_agent_runs_api.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
decisions:
  - Reused the existing graph nodes and routing edges; no new graph node was added.
  - Kept metric final answers deterministic and independent of RAG/policy evidence by default.
  - Projected only allowlisted metric metadata into final-response SSE payloads.
metrics:
  duration: 27m27s
  completed_at: 2026-07-09T05:03:55Z
  tasks_completed: 4
  verification: "1401 passed, 34 warnings"
---

# Phase 61 Plan 04: Metric Graph Integration Summary

Natural-language metric queries now execute through the existing agent graph and ToolPlatform, clarify missing metric slots before investigation, and return deterministic number-first metric answers with safe backend metadata for the console.

## Completed Tasks

| Task | Result | Commit |
| ---- | ------ | ------ |
| Task 1: metric investigate fallback | Complete metric slots call `query_business_metric`; incomplete metric slots do not call tools. | `582256f`, `0a094e1` |
| Task 2: metric final response branch | Added number-first count/rate responses, coupon caveat, permission-denied no-leak wording, and zero-denominator refund-rate wording. | `b0c3662`, `2582084` |
| Task 3: graph route coverage | Added deterministic graph/routing coverage for complete metric, missing-time clarification, and permission-denied no-leak final response. | `28da8f6` |
| Task 4: safe SSE payload metadata | Added final-response payload projection with `response_kind` and allowlisted metric metadata only. | `673c42e`, `fb7cd53` |

## Changed Files

- `src/agent/nodes/investigate.py`: added metric deterministic fallback through ToolPlatform using validated `active_slots`.
- `src/agent/nodes/final_response.py`: added deterministic metric answer formatting and safe `llm_outputs["final_response"]` metadata.
- `src/api/routers/agent_runs.py`: added safe final-response payload projection for metric answers.
- `tests/agent/test_nodes/test_investigate.py`: added metric fallback RED coverage.
- `tests/agent/test_nodes/test_final_response.py`: added metric final-answer RED coverage.
- `tests/agent/test_graph.py`: added fake metric tool support and graph route/no-leak coverage.
- `tests/agent/test_intent_routing.py`: added metric slot route assertions.
- `tests/test_agent_runs_api.py`: added update-stream and lifecycle-stream SSE payload safety coverage.
- `.planning/LOCAL-VALIDATION-ISSUES.md`: logged the local graph test LLM/proxy validation pitfall found during execution.

## Verification

Plan-local command:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_nodes/test_final_response.py tests/agent/test_graph.py tests/agent/test_intent_routing.py tests/test_agent_runs_api.py -q --tb=short
```

Result: `1401 passed, 34 warnings in 129.44s`.

Focused checks also passed:

- `tests/agent/test_nodes/test_investigate.py tests/tools/test_tool_platform.py`: `93 passed, 1 warning`.
- `tests/agent/test_nodes/test_final_response.py`: `32 passed, 1 warning`.
- `tests/agent/test_graph.py tests/agent/test_intent_routing.py`: `1240 passed, 34 warnings`.
- `tests/test_agent_runs_api.py`: `73 passed, 1 warning`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Isolated graph metric missing-time tests from live LLM/proxy initialization**

- **Found during:** Task 3 focused graph verification.
- **Issue:** A pre-existing dirty graph test expected aggregate order count to route to unsupported and did not monkeypatch `slot_resolution_gate` LLM. Under the current metric semantics it entered the slot gate and attempted real `ChatOpenAI` initialization, failing with missing `socksio`.
- **Fix:** Added deterministic slot-gate monkeypatching for metric graph tests and covered the intended missing-time clarification path without live LLM calls.
- **Files modified:** `tests/agent/test_graph.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Commit:** `28da8f6` for committed 61-04 graph coverage; validation log is included in the final docs commit.

### Plan Adjustments

- `src/agent/nodes/investigate_planner.py` did not need a source edit: existing planner validation and visible-tool checks already reject non-visible/write tools, while the metric path is handled by the deterministic investigate fallback.
- `src/agent/routing.py` did not need a source edit: existing route edges already supported `contextual_intent_resolve -> slot_resolution_gate -> investigate/final_response` for the metric states introduced by prior Phase 61 work.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/autopilot/phase-61.md` were intentionally not modified per execution instructions.

## Threat Flags

None. The new security-relevant surface was already covered by the plan threat model: validated slot-to-tool args, no-leak metric final response, and allowlisted SSE projection.

## Known Stubs

None found in files changed by this plan. The metric path uses deterministic fake tool results only in tests.

## Deferred Items

- Existing pre-61-04 dirty work remains in the worktree, including unrelated edits and uncommitted `tests/agent/test_graph.py` changes. These were preserved and not reverted.
- Frontend rendering, Playwright checks, and visual timeline behavior remain deferred to Plan 61-05 as planned; 61-05 was not executed.

## Self-Check: PASSED

- Verified summary file exists at `.planning/phases/61-product-experience-fixes/61-04-SUMMARY.md`.
- Verified task commits exist: `582256f`, `0a094e1`, `b0c3662`, `2582084`, `28da8f6`, `673c42e`, `fb7cd53`.
- Confirmed `.planning/STATE.md` and `.planning/ROADMAP.md` remain dirty in the worktree from prior state but were not staged for 61-04 final metadata.
