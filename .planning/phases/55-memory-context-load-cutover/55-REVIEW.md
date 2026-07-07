---
phase: 55-memory-context-load-cutover
reviewed: 2026-07-07T06:52:21Z
depth: deep
files_reviewed: 21
files_reviewed_list:
  - docs/current-langgraph-architecture.md
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/long_term_memory_retrieve.py
  - src/agent/nodes/memory_context_load.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_memory_context_load.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_trace.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/architecture/test_memory_contract_delta.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/memory/test_phase48_1_memory_compat_alignment.py
  - tests/test_agent_runs_api.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 55: Code Review Report

**Reviewed:** 2026-07-07T06:52:21Z
**Depth:** deep
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Deep review covered the active graph/router cutover to `memory_context_load`, memory authority boundaries, trace/API projection, compatibility aliases, Phase 56/57/58 scope boundaries, and regression tests.

The active graph registration, conditional route map, router return values, vocabulary projection, SSE label, trace summary, and timeline projection are consistent with the Phase 55 cutover. Phase 56 `generate_recommendation` and Phase 57 `assess_risk_and_approval` remain deliberately active legacy nodes, and Phase 58 cleanup has not been implemented early.

Verification run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_routing.py tests/agent/test_memory_context_load.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_trace.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase32_static_contract.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/test_agent_runs_api.py tests/test_graph_routing.py tests/test_trace_api.py
```

Result: `1405 passed, 2 skipped, 31 warnings`.

## Warnings

### WR-01: Canonical Memory Node Still Carries Helper Metrics Key

**File:** `src/agent/nodes/memory_context_load.py:44-47`

**Issue:** `memory_context_load()` delegates to `reviewed_memory_context_retrieve()`, whose result includes `llm_outputs["reviewed_memory_context_retrieve"]`. The canonical node then merges `result["llm_outputs"]` into the active run state after only removing `long_term_memory_retrieve` in `_without_legacy_metrics()`. That means an active `memory_context_load` graph run can still expose `llm_outputs["reviewed_memory_context_retrieve"]`, even though Phase 55 documents the helper as a compatibility alias rather than a runtime owner and says active canonical metrics live under `llm_outputs["memory_context_load"]`. Current tests assert the old `long_term_memory_retrieve` key is absent, but they do not reject this helper key, so this regression can falsely pass.

**Fix:**

```python
def _without_legacy_metrics(value: Any) -> dict[str, Any]:
    metrics = dict(value) if isinstance(value, Mapping) else {}
    for key in ("long_term_memory_retrieve", "reviewed_memory_context_retrieve"):
        metrics.pop(key, None)
    return metrics
```

Also add assertions in `tests/agent/test_memory_context_load.py` and the active graph smoke tests that direct canonical runs do not include `llm_outputs["reviewed_memory_context_retrieve"]`; keep the legacy wrapper test free to add only `llm_outputs["long_term_memory_retrieve"]`.

---

_Reviewed: 2026-07-07T06:52:21Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
