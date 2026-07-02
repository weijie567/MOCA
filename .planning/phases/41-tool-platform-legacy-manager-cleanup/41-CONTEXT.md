# Phase 41: Tool Platform Legacy Manager Cleanup - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Source:** Source audit + user decision

<domain>
## Phase Boundary

Phase 41 removes the `UnifiedToolManager` legacy compatibility adapter from the v2.1 tool platform. The target state is a single graph-facing tool entrypoint: `ToolPlatform`.

This is a breaking cleanup/API decision. It is intentionally part of v2.1 cleanup scope and must happen before milestone review/archive.

</domain>

<decisions>
## Locked Decisions

### API / Compatibility

- **D-01:** Cancel the `UnifiedToolManager` compatibility API in Phase 41. Do not keep a deprecated wrapper unless implementation discovers a hard blocker and stops with evidence.
- **D-02:** `ToolPlatform` is the sole canonical graph-facing tool registry/dispatch entrypoint after Phase 41.
- **D-03:** Update `docs/contract-spec.md` to remove the legacy adapter contract instead of leaving code and spec inconsistent.
- **D-04:** Remove the `src.tools.__getattr__` lazy export and `__all__` entry for `UnifiedToolManager`.

### Runtime / Production Seams

- **D-05:** Remove production unwrapping of `tool_manager._platform` in `src/agent/nodes/investigate.py`; callers must provide `tool_platform` or rely on `ToolPlatform.with_defaults(session)` / empty fallback.
- **D-06:** Remove production unwrapping of `action_tool_manager._platform` in `src/agent/nodes/action_draft.py`; tests and callers must inject `action_tool_platform` or use defaults.
- **D-07:** Do not change `ToolResultV2`, `ToolInvocationOutcome`, `ToolCallContext`, `ToolPolicyDecision`, or `ToolViewV1` shapes. This phase removes a compatibility adapter only.
- **D-08:** Do not rename `src/tools/manager_results.py`; it is a safe-result helper still used by runtime/executors and is not the manager adapter.

### Helper Relocation

- **D-09:** `_side_effect_allowed` currently lives in `src/tools/manager.py` but is active architecture-test code. Move it to a non-legacy module before deleting `manager.py`.
- **D-10:** Preferred destination for `_side_effect_allowed` is `src/tools/policy.py`, because it describes policy side-effect semantics and avoids creating a new module for one helper.

### Tests / Fakes

- **D-11:** Delete or migrate `tests/agent/test_tools/test_unified_tool_manager.py`; do not keep compatibility adapter tests after the API is removed.
- **D-12:** Preserve behavior coverage by migrating still-relevant tests to `ToolPlatform` / `ToolCatalog` surfaces where needed, especially visibility, runtime invalid-response, action write dispatch, and event-family behavior.
- **D-13:** Convert fake managers in graph/investigate/policy/facade tests into platform-native fakes. They must not depend on `_platform`, `_descriptors`, or `_manager.invoke`.
- **D-14:** Update architecture tests to forbid production imports of `src.tools.manager` and to assert no `UnifiedToolManager` references remain in `src/` after cleanup.

### Spec / Review

- **D-15:** Because this phase changes public compatibility surface and `docs/contract-spec.md`, it requires an implementation code review before v2.1 archive.
- **D-16:** `docs/contract-spec.md` is normative for this API decision, so plan and implementation must include no-diff/protected-field checks for `ToolResultV2` and `ToolCallContext` while allowing the deliberate spec cleanup.

</decisions>

<canonical_refs>
## Canonical References

### Current Adapter

- `src/tools/manager.py` — `UnifiedToolManager` wrapper and `_side_effect_allowed` helper.
- `src/tools/__init__.py` — lazy export/public API surface for `UnifiedToolManager`.
- `src/tools/platform.py` — canonical replacement entrypoint.
- `src/tools/catalog.py` — descriptor lookup and current declaration-only error text that still points at `UnifiedToolManager`.

### Production Seams

- `src/agent/nodes/investigate.py` — accepts `tool_platform`, then legacy `tool_manager._platform`, then default platform.
- `src/agent/nodes/action_draft.py` — accepts `action_tool_platform`, then legacy `action_tool_manager._platform`, then default platform.

### Spec

- `docs/contract-spec.md` — current legacy adapter mentions at §6, §10, §12.6, and `UnifiedToolManager(Protocol)` block.

### Tests

- `tests/agent/test_tools/test_unified_tool_manager.py` — compatibility adapter behavior tests to delete/migrate.
- `tests/test_execute_action.py` — imports `UnifiedToolManager` for `action_tool_manager` injection.
- `tests/agent/test_phase22_action_boundary.py` — passes `action_tool_manager` fakes to prove action tool is not called when blocked.
- `tests/agent/test_graph.py` — imports `UnifiedToolManager`, has `_platform` unwrapping in test config, and manager-shaped fakes.
- `tests/agent/test_nodes/test_investigate.py` — manager-shaped fake feeding a platform wrapper.
- `tests/agent/test_policy_retrieval_ownership.py` — manager-shaped fake and outdated comments referencing manager ownership.
- `tests/knowledge/test_facade_integration.py` — manager-shaped fake and platform wrapper.
- `tests/architecture/test_action_draft_boundaries.py` — imports `_side_effect_allowed` from manager and asserts source text in manager.
- `tests/architecture/test_tool_boundaries.py` — has manager boundary assertions that must be inverted or removed.

</canonical_refs>

<specifics>
## Source Facts

- `UnifiedToolManager` is not canonical production logic; it delegates to `ToolPlatform`.
- The adapter is still a public-ish API because it is exported from `src.tools` and specified in `docs/contract-spec.md`.
- Production nodes contain compatibility unwrapping branches for `tool_manager._platform` and `action_tool_manager._platform`.
- Several tests rely on private fake-manager structures, so deleting `manager.py` requires fake migration rather than a simple file deletion.
- `src/tools/manager_results.py` is not part of this cleanup despite the name.

</specifics>

<deferred>
## Deferred Ideas

- A formal deprecation window for external consumers is not implemented. The project owner decided architecture simplicity is the goal for v2.1, so this phase performs the breaking cleanup directly.
- Any new tool-platform features beyond removing the legacy adapter are out of scope.

</deferred>

---

*Phase: 41-tool-platform-legacy-manager-cleanup*
*Context gathered: 2026-07-02*
