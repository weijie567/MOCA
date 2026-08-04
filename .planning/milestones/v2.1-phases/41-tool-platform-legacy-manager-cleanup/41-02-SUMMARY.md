---
phase: 41-tool-platform-legacy-manager-cleanup
plan: 02
subsystem: tool-platform
tags: [tool-platform, graph, tests, fakes]
requires:
  - phase: 41-tool-platform-legacy-manager-cleanup
    provides: 41-01 spec/API cleanup and side-effect helper relocation
provides:
  - production graph nodes no longer unwrap legacy manager platforms
  - action and graph tests inject ToolPlatform-shaped objects
  - investigate/policy/facade fakes implement the ToolPlatform facade directly
affects: [phase-41, TPH-06, ToolPlatform, graph-tests]
tech-stack:
  added: []
  patterns: [platform-native test fakes, action_tool_platform injection, tool_platform injection]
key-files:
  created:
    - .planning/phases/41-tool-platform-legacy-manager-cleanup/41-02-SUMMARY.md
  modified:
    - src/agent/nodes/investigate.py
    - src/agent/nodes/action_draft.py
    - tests/test_execute_action.py
    - tests/agent/test_phase22_action_boundary.py
    - tests/agent/test_graph.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/agent/test_policy_retrieval_ownership.py
    - tests/knowledge/test_facade_integration.py
key-decisions:
  - "Production nodes now accept ToolPlatform-shaped injection only; legacy manager config keys are not unwrapped."
  - "Tests keep behavior coverage by moving fake dispatch state onto platform-native fakes."
requirements-completed:
  - TPH-06
duration: 20min
completed: 2026-07-02
---

# Phase 41 Plan 02 Summary: Production Seam and Fake Migration

Production graph nodes and focused tests now use ToolPlatform-shaped seams instead of manager-shaped compatibility wrappers.

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-02T05:55:00Z
- **Completed:** 2026-07-02T06:15:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Removed legacy `tool_manager._platform` unwrapping from `investigate`.
- Removed legacy `action_tool_manager._platform` unwrapping from `action_draft`.
- Migrated action and graph tests to inject `action_tool_platform` / `tool_platform` directly.
- Converted manager-shaped test fakes in investigate, policy ownership, and facade integration tests into platform-native fakes implementing `visible_tools`, `invoke`, `descriptor`, and `event_family`.

## Task Commits

1. **Task 1: Remove production legacy manager unwrapping** - `27e4630`
2. **Task 2: Migrate action and graph tests to platform injection** - `6b8ab51`
3. **Task 3: Migrate investigate/policy/facade fakes to platform-native fakes** - `e07423d`
4. **Lint cleanup for migrated fake imports** - `c3a399e`

## Verification

Passed:

```bash
rg -n "tool_manager|action_tool_manager|UnifiedToolManager|src\\.tools\\.manager|\\._platform" src/agent/nodes tests/test_execute_action.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/knowledge/test_facade_integration.py
uv run pytest tests/test_execute_action.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py -q
uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/knowledge/test_facade_integration.py -q
uv run ruff check src/agent/nodes/investigate.py src/agent/nodes/action_draft.py tests/test_execute_action.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/knowledge/test_facade_integration.py
```

Results:

- Legacy manager grep: no matches.
- Action/graph focused suite: 73 passed.
- Investigate/policy/facade focused suite: 66 passed.
- Ruff: all checks passed.

## Deviations from Plan

None - implementation stayed within the planned files and preserved tool invocation semantics.

## Issues Encountered

Ruff found one unused `typing.Any` import after fake migration; it was removed in a dedicated cleanup commit.

## User Setup Required

None.

## Next Phase Readiness

Ready for 41-03. Production seams and targeted tests no longer rely on manager-shaped injection, so the legacy adapter file and public export can be deleted after migrating remaining compatibility tests.

---
*Phase: 41-tool-platform-legacy-manager-cleanup*
*Completed: 2026-07-02*
