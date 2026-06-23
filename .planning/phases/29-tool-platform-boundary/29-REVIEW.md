---
phase: 29-tool-platform-boundary
reviewed: 2026-06-23T12:44:27Z
depth: deep
files_reviewed: 17
files_reviewed_list:
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
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-23T12:44:27Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Re-reviewed the Phase 29 tool platform boundary files after commits `e8fc63a` and `2063214`. Prior CR-01 is fixed: `src/tools/projection.py` now sanitizes nested case-memory `policy_refs` and `source_refs`, and the behavior is covered by `tests/tools/test_tool_platform.py::test_tool_result_projector_strips_raw_sentinels_from_case_memory_ref_lists` plus `tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory`. Prior WR-01 is fixed: `src/tools/policy.py` now normalizes legacy list-form merchant scopes and fail-closes malformed scopes, with coverage in `tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope`.

No remaining Critical findings were found in the reviewed implementation. One Warning remains because the scoped Phase 29 architecture test still fails against the current repository.

Verification run:

```text
uv run pytest tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/architecture/test_tool_boundaries.py tests/conversation/test_service.py tests/replay/test_decision_events.py tests/replay/test_replay_migration_contract.py tests/replay/test_tool_policy_events.py tests/tools/test_tool_result_storage.py -q
```

Result: `1 failed, 162 passed, 1 warning`. The failure is `tests/architecture/test_tool_boundaries.py::test_graph_nodes_do_not_import_tool_executors`.

## Warnings

### WR-01: Action Draft Graph Node Still Imports A Tool Executor Directly

**File:** `src/agent/nodes/action_draft.py:15`
**Issue:** The scoped architecture gate at `tests/architecture/test_tool_boundaries.py:185` requires graph nodes to dispatch through the `ToolPlatform` facade and not import `src.tools.executors.*` directly. The current tree still has `from src.tools.executors.action import ActionToolExecutor` in `action_draft.py`, and line 319 constructs `UnifiedToolManager(executors=[ActionToolExecutor(session)])`. That keeps executor construction in a graph node and causes the Phase 29 boundary gate to fail.
**Fix:** Move action execution behind `ToolPlatform` or a platform-backed injected dependency, and remove the graph-node executor import. For example:

```python
from src.tools.platform import ToolPlatform

tool_platform = configurable.get("action_tool_platform") or ToolPlatform.with_defaults(session)
outcome = await tool_platform.invoke(ACTION_TOOL_NAME, args, tool_ctx, session=session)
tool_result = outcome.tool_result
```

Preserve any required test injection seam via a platform-compatible object rather than constructing `ActionToolExecutor` inside the node.

---

_Reviewed: 2026-06-23T12:44:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
