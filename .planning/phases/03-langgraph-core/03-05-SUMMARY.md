---
phase: 03-langgraph-core
plan: "05"
subsystem: testing
tags: [langgraph, pytest, fakellm, memorysaver, golden-set, smoke-test]

requires:
  - phase: 03-langgraph-core
    provides: Plan 03-04 agent graph, API wiring, checkpointer lifecycle, and trace helpers
provides:
  - Deterministic FakeLLM fixtures for CI-safe agent tests
  - Tool contract tests for order, refund case, and policy search wrappers
  - Per-node tests for request reset, intent classification, evidence gate, and citation validation
  - Compiled LangGraph integration tests using MemorySaver
  - Live smoke script for manual real-LLM validation
  - 15-case Phase 3 golden set
affects: [03-langgraph-core, ci, evals, agent-quality, phase-4-approval]

tech-stack:
  added: []
  patterns:
    - Patch node-local _get_llm factories with FakeLLM for deterministic structured-output tests
    - Patch node-imported tools directly for graph integration tests
    - Use MemorySaver for DB-free compiled graph tests

key-files:
  created:
    - tests/agent/conftest.py
    - tests/agent/test_tools/test_get_order.py
    - tests/agent/test_tools/test_get_refund_case.py
    - tests/agent/test_tools/test_search_policy.py
    - tests/agent/test_nodes/test_receive_request.py
    - tests/agent/test_nodes/test_classify_intent.py
    - tests/agent/test_nodes/test_retrieve_policy_evidence.py
    - tests/agent/test_nodes/test_generate_recommendation.py
    - tests/agent/test_graph.py
    - scripts/smoke_agent_live.py
    - evals/golden_set_phase3.json
  modified: []

key-decisions:
  - "Plan 03-05 tests patch node-local _get_llm factories rather than constructing real ChatOpenAI clients, preserving CI isolation from live LLM APIs."
  - "Graph integration tests use MemorySaver and node-imported tool monkeypatches so the compiled graph is exercised without Postgres or external embeddings."
  - "The Phase 3 golden set uses synthetic order numbers and Chinese support queries only; no real PII is included."

patterns-established:
  - "FakeLLM: test-only deterministic structured output via ainvoke() and with_structured_output()."
  - "Graph tests: compile build_graph(MemorySaver()) and invoke with AsyncMock session in configurable state."
  - "Failure coverage: no evidence, low score, order not found, invalid LLM parse retry, and citation stripping are asserted directly."

requirements-completed:
  - AGNT-01
  - AGNT-02
  - AGNT-03
  - AGNT-04
  - AGNT-06
  - AGNT-08
  - RAG-05
  - SAFE-06
  - SAFE-08

duration: 6m20s
completed: 2026-05-11
---

# Phase 3 Plan 05: Agent Test Suite Summary

**CI-safe LangGraph agent acceptance suite with FakeLLM, MemorySaver graph tests, live smoke script, and a synthetic 15-case golden set**

## Performance

- **Duration:** 6m20s
- **Started:** 2026-05-11T08:22:36Z
- **Completed:** 2026-05-11T08:28:56Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- Added `tests/agent/conftest.py` with FakeLLM fixtures for deterministic structured-output tests.
- Added tool and node tests covering success, not-found, DB timeout, evidence gate, LLM parse failure, and citation validation paths.
- Added compiled graph integration tests with `MemorySaver`, including policy QA, refund troubleshooting, insufficient evidence, order not found, parse retry, cross-turn isolation, and trace summary shape.
- Added `scripts/smoke_agent_live.py` for local real-LLM smoke testing without placing live calls in CI.
- Added `evals/golden_set_phase3.json` with 15 synthetic Chinese cases covering all six AI-SPEC categories.

## Task Commits

1. **Task 1: Test infrastructure + tool tests + per-node unit tests** - `180883c` (test)
2. **Task 2: Graph integration test + failure paths + smoke script + golden set** - `2789d3d` (test)

## Files Created/Modified

- `tests/agent/__init__.py` - Agent test package marker.
- `tests/agent/conftest.py` - FakeLLM and base state fixtures.
- `tests/agent/test_tools/__init__.py` - Tool test package marker.
- `tests/agent/test_tools/test_get_order.py` - Order tool success, not-found, timeout, and PII-protection tests.
- `tests/agent/test_tools/test_get_refund_case.py` - Refund case tool success and not-found tests.
- `tests/agent/test_tools/test_search_policy.py` - Policy search success and no-evidence tests.
- `tests/agent/test_nodes/__init__.py` - Node test package marker.
- `tests/agent/test_nodes/test_receive_request.py` - Per-turn reset and run ID tests.
- `tests/agent/test_nodes/test_classify_intent.py` - Intent classification success and structured-output failure fallback tests.
- `tests/agent/test_nodes/test_retrieve_policy_evidence.py` - No-evidence, low-score, and good-evidence gate tests.
- `tests/agent/test_nodes/test_generate_recommendation.py` - Insufficient-evidence LLM skip and invalid citation stripping tests.
- `tests/agent/test_graph.py` - Full compiled graph integration and failure-path tests.
- `scripts/smoke_agent_live.py` - Manual live smoke test entrypoint for DashScope-backed runs.
- `evals/golden_set_phase3.json` - 15-case synthetic Phase 3 golden set.

## Decisions Made

- Patched `_get_llm` factories inside node modules instead of `ChatOpenAI` constructors directly. This keeps tests focused on node behavior while guaranteeing no real client construction or live API calls.
- Used `MemorySaver` in graph tests to exercise the compiled graph and checkpointer behavior without requiring Postgres.
- Kept smoke testing syntax-only in automated verification; real LLM execution remains manual and gated by `DASHSCOPE_API_KEY`.

## Deviations from Plan

None - plan intent executed as written. Narrow test adjustments were made to match actual production contracts: `receive_request` now correctly expects the node's own trace step, and graph tests patch node-local LLM factories rather than live client constructors.

## Issues Encountered

None.

## Known Stubs

None. Empty lists and `None` values found by the stub scan are intentional test inputs or schema fields, not UI/rendering stubs.

## Threat Flags

None. No production network endpoints, auth paths, file access paths, or schema changes were introduced. Golden-set entries use synthetic order numbers and support queries only.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -v --tb=short -m "not live" -q` - passed, 7 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -v --tb=short -m "not live"` - passed, 24 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 74 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import json; ..."` - passed, golden set has 15 cases and required categories.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast; ..."` - passed, smoke script syntax OK.

## User Setup Required

None for CI. Manual live smoke testing requires `DASHSCOPE_API_KEY` and a running Postgres DB.

## Next Phase Readiness

Phase 3 now has deterministic acceptance coverage for agent tools, nodes, graph-level workflows, trace summary shape, and core failure paths. Phase 4 can build approval workflow behavior against these regression tests.

## Self-Check: PASSED

- Found created files: `tests/agent/conftest.py`, `tests/agent/test_graph.py`, `scripts/smoke_agent_live.py`, `evals/golden_set_phase3.json`, `.planning/phases/03-langgraph-core/03-05-SUMMARY.md`.
- Found task commits: `180883c`, `2789d3d`.

---
*Phase: 03-langgraph-core*
*Completed: 2026-05-11*
