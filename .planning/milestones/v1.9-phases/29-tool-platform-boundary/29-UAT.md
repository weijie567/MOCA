---
status: complete
phase: 29-tool-platform-boundary
source:
  - .planning/phases/29-tool-platform-boundary/29-01-SUMMARY.md
  - .planning/phases/29-tool-platform-boundary/29-02-SUMMARY.md
  - .planning/phases/29-tool-platform-boundary/29-03-SUMMARY.md
  - .planning/phases/29-tool-platform-boundary/29-04-SUMMARY.md
started: 2026-06-23T13:23:50Z
updated: 2026-06-23T13:23:50Z
mode: automated
---

## Current Test

[testing complete]

## Tests

### 1. Prompt-Safe Tool Visibility
expected: Planner-facing tool visibility is derived from `ToolPlatform.visible_tools(...)` and exposes only prompt-safe `ToolViewV1` fields, with no raw descriptor policy, executor, or side-effect metadata in planner prompts.
result: pass
evidence: `tests/tools`, `tests/agent/test_nodes/test_investigate.py`, and static negative checks passed.

### 2. Runtime Authorization Boundary
expected: Tool invocation rechecks a fresh runtime authorization decision before executor dispatch, handles legacy list-form merchant scopes without crashing, and denies out-of-scope or unauthorized calls safely.
result: pass
evidence: `tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope` passed; Phase 29 targeted gate passed.

### 3. Result Projection Raw-Sentinel Boundary
expected: `ToolResultProjector` strips raw/private/debug sentinels from normalized and prompt surfaces, including nested case-memory `policy_refs` / `source_refs` keys such as `raw_payload`, `raw_tool_payload`, and `secret`.
result: pass
evidence: focused projector/investigate regressions passed; Phase 29 targeted gate passed.

### 4. Manager, Investigate, And Conversation Integration
expected: `UnifiedToolManager`, `investigate`, and conversation tool-result persistence route through `ToolPlatform` / `ToolResultProjector` boundaries and do not persist or accumulate raw `ToolResultV2.data` directly.
result: pass
evidence: `tests/agent/test_tools/test_unified_tool_manager.py`, `tests/agent/test_nodes/test_investigate.py`, and `tests/conversation/test_service.py` passed inside the targeted gate.

### 5. Replay Policy Event Contract
expected: Tool policy visibility/runtime-auth event types are registered, retained with the expected classification, and protected by redaction/resource-ref guards without adding a parallel event envelope or table.
result: pass
evidence: `tests/replay` and `tests/architecture/test_tool_boundaries.py` passed inside the targeted gate.

### 6. Phase-Level Negative Scope Checks
expected: Phase 29 does not add generic artifact-store, rate-limit, feature-flag, MCP/dynamic discovery, or new migration table scope, and graph nodes do not directly import tool executors.
result: pass
evidence: static `rg` checks for forbidden implementation scope produced no production-scope violation; Phase 29 targeted gate passed.

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Automated Evidence

- `29-REVIEW.md` status: `clean`; Critical/Warning/Info/Total: `0/0/0/0`.
- `uv run pytest tests/tools/test_tool_platform.py::test_tool_result_projector_strips_raw_sentinels_from_case_memory_ref_lists tests/tools/test_tool_platform.py::test_tool_result_projector_blocks_raw_data_from_prompt_and_graph_surfaces tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope tests/architecture/test_tool_boundaries.py::test_graph_nodes_do_not_import_tool_executors -q` -> `6 passed, 1 warning`.
- `uv run pytest tests/tools tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/conversation/test_service.py tests/replay tests/architecture/test_tool_boundaries.py -q` -> `225 passed, 1 warning`.
- `rg -n "artifact_store|rate_limit|feature_flag|MCP|mcp" src/tools` -> no matches.
- `rg -n "CREATE TABLE|create_table\(" src/db/migrations/versions/017_tool_policy_events.py` -> no matches.

## Security Gate

`workflow.security_enforcement=true`, and `29-SECURITY.md` is verified with `threats_open: 0`. Functional UAT, security, and validation gates are complete; Phase 29 is ready for Phase 30 planning.

## Gaps

[none]
