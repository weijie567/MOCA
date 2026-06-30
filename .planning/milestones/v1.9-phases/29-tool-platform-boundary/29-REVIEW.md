---
phase: 29-tool-platform-boundary
reviewed: 2026-06-23T13:18:10Z
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
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-23T13:18:10Z
**Depth:** deep
**Files Reviewed:** 18
**Status:** clean

## Summary

Re-reviewed the Phase 29 tool-platform boundary after fix commits `e8fc63a`, `2063214`, `29df231`, and `c52833c`.

The prior `action_draft` direct executor import issue remains fixed. `src/agent/nodes/action_draft.py` imports and invokes `ToolPlatform`, and `tests/architecture/test_tool_boundaries.py::test_graph_nodes_do_not_import_tool_executors` covers graph-node executor imports.

The prior nested case-memory raw payload leaks are fixed in the reviewed path. `src/tools/projection.py` includes `raw_tool_payload` in `_RAW_SENTINEL_KEYS`, strips nested `raw_payload`, `raw_tool_payload`, and `secret` entries from case-memory `policy_refs` / `source_refs`, and removes the corresponding unsafe values from the projected surfaces. `src/agent/nodes/investigate.py` consumes projector-normalized case memory rather than raw `ToolResultV2.data`. Coverage exists in `tests/tools/test_tool_platform.py::test_tool_result_projector_strips_raw_sentinels_from_case_memory_ref_lists` and `tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory`.

The prior nested `raw_payload` / `secret` case-memory leakage and legacy list `merchant_scope` crash are also covered by current code and tests, so they are not re-reported.

Verification:

```text
.venv/bin/pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/architecture/test_tool_boundaries.py tests/conversation/test_service.py tests/replay/test_decision_events.py tests/replay/test_replay_migration_contract.py tests/replay/test_tool_policy_events.py tests/tools/test_tool_platform.py tests/tools/test_tool_result_storage.py -q
```

Result: `163 passed, 1 warning`.

All reviewed files meet quality standards. No Critical, Warning, or Info findings remain in this scope.

---

_Reviewed: 2026-06-23T13:18:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
