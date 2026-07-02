# Phase 41 Discussion Log

Date: 2026-07-02

## User Decision

The user wants v2.1 to remain open as a cleanup milestone and add a dedicated cleanup phase for `UnifiedToolManager`.

## Decisions

| Topic | Decision |
|-------|----------|
| Compatibility API | Remove `UnifiedToolManager`; do not keep compatibility for architecture simplicity. |
| Milestone scope | Keep cleanup inside v2.1 rather than opening a new milestone. |
| Review gate | Run implementation code review after Phase 41 because this is a breaking cleanup/API surface change. |
| Spec | Update `docs/contract-spec.md`; do not leave it declaring the removed legacy adapter. |
| Production seams | Migrate `tool_manager` / `action_tool_manager` legacy injections to `tool_platform` / `action_tool_platform`. |

## Non-Decisions

- No new tool capabilities.
- No `ToolResultV2` / `ToolCallContext` shape changes.
- No ownership or policy behavior redesign.
