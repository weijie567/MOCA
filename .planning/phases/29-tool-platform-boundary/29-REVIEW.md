---
phase: 29-tool-platform-boundary
reviewed: 2026-06-23T13:01:32Z
depth: deep
files_reviewed: 18
files_reviewed_list:
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/investigate.py
  - src/conversation/service.py
  - src/tools/manager.py
  - src/tools/manager_results.py
  - src/tools/platform.py
  - src/tools/policy.py
  - src/tools/projection.py
  - src/tools/runtime.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/architecture/test_tool_boundaries.py
  - tests/conversation/test_service.py
  - tests/replay/test_decision_events.py
  - tests/replay/test_replay_migration_contract.py
  - tests/replay/test_tool_policy_events.py
  - tests/tools/test_tool_platform.py
  - tests/tools/test_tool_result_storage.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-23T13:01:32Z
**Depth:** deep
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Re-reviewed the Phase 29 tool-platform boundary after fix commits `e8fc63a`, `2063214`, and `29df231`. The prior action-draft boundary finding is fixed: `src/agent/nodes/action_draft.py` no longer imports `src.tools.executors.*` or constructs `ActionToolExecutor` / `UnifiedToolManager`, and `tests/architecture/test_tool_boundaries.py::test_graph_nodes_do_not_import_tool_executors` passes.

The prior merchant-scope crash is fixed and covered by `tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope`. The prior nested case-memory leakage is fixed for the currently tested `raw_payload` and `secret` keys, but a still-current raw sentinel variant remains for nested `raw_tool_payload` refs.

Verification:

```text
.venv/bin/pytest tests/architecture/test_tool_boundaries.py::test_graph_nodes_do_not_import_tool_executors tests/tools/test_tool_platform.py::test_tool_result_projector_strips_raw_sentinels_from_case_memory_ref_lists tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory -q
```

Result: `5 passed, 1 warning`.

```text
.venv/bin/pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/architecture/test_tool_boundaries.py tests/conversation/test_service.py tests/replay/test_decision_events.py tests/replay/test_replay_migration_contract.py tests/replay/test_tool_policy_events.py tests/tools/test_tool_platform.py tests/tools/test_tool_result_storage.py -q
```

Result: `163 passed, 1 warning`.

## Critical Issues

### CR-01: Nested Case-Memory `raw_tool_payload` Can Still Reach Graph State

**File:** `src/tools/projection.py:10`
**Issue:** `_sanitize_ref_list()` filters nested case-memory `policy_refs` / `source_refs` by checking `_RAW_SENTINEL_KEYS`, but that set does not include `raw_tool_payload`. A nested ref like `{"doc_key": "p1", "raw_tool_payload": "LEAK"}` survives `ToolResultProjector.project(...).normalized_result`, and `investigate` then copies those projected refs into `case_memory` at `src/agent/nodes/investigate.py:779`. That leaves a raw payload path into graph state and prompt-adjacent memory surfaces.
**Fix:**

```python
_RAW_SENTINEL_KEYS: set[str] = {
    "raw",
    "raw_payload",
    "raw_tool_payload",
    "raw_tool_output",
    "raw_args",
    "private_reasoning",
    "approval_authority_body",
    "action_authority_body",
    "debug_trace",
    "debug_blob",
    "replay_blob",
    "replay_debug_blob",
    "secret",
    "credentials",
    "pii",
}
```

Add a regression assertion to the nested case-memory ref tests using scalar `raw_tool_payload` inside `policy_refs` and `source_refs`, not only as a top-level item field.

---

_Reviewed: 2026-06-23T13:01:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
