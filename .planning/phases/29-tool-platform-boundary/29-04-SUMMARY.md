---
phase: 29-tool-platform-boundary
plan: 04
subsystem: tools
tags: [tool-platform, manager-compat, investigate, conversation, projection]

requires:
  - phase: 29-03
    provides: "ToolPlatform facade, ToolRuntime, ToolResultProjector"
provides:
  - "UnifiedToolManager delegates to ToolPlatform for policy/runtime"
  - "Investigate uses ToolPlatform.visible_tools and ToolPlatform.invoke"
  - "Conversation storage uses ToolResultProjector for normalized data"
  - "Planner validation against ToolView names instead of raw descriptors/ALLOWLIST"
affects: [30, investigate, conversation, manager-compat]

tech-stack:
  added: []
  patterns: [manager-compat-adapter, projection-based-storage, tool-view-validation]

key-files:
  created: []
  modified:
    - src/tools/manager.py
    - src/tools/platform.py
    - src/tools/policy.py
    - src/tools/runtime.py
    - src/tools/projection.py
    - src/agent/nodes/investigate.py
    - src/conversation/service.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/tools/test_tool_result_storage.py

key-decisions:
  - "UnifiedToolManager creates ToolPlatform with custom catalog from descriptors when provided"
  - "Investigate falls back to ToolPlatform(executors={}) when session is None"
  - "ToolPlatform.with_defaults(session=None) creates stub executors for auth testing"
  - "Policy engine allows action_draft callers to execute write tools"
  - "Runtime gate order: descriptor → runtime_auth → schema validation → executor dispatch"
  - "Runtime denial status maps idempotency_required and schema_invalid to 'invalid_request'"
  - "Conversation service always projects results through ToolResultProjector"

patterns-established:
  - "Manager compat adapter: UnifiedToolManager delegates to ToolPlatform internally"
  - "ToolView validation: planner validates against visible ToolView names, not ALLOWLIST"
  - "Projection-based storage: conversation stores projector-normalized data, not raw result.data"

requirements-completed: [APF-06, APF-07]

duration: 40min
completed: 2026-06-23
---

# Phase 29 Plan 04: Manager/Investigate/Conversation Wiring Summary

**UnifiedToolManager delegates to ToolPlatform, investigate uses visible_tools/invoke, conversation stores projector-normalized data**

## Performance

- **Duration:** 40 min
- **Started:** 2026-06-23T12:30:00Z
- **Completed:** 2026-06-23T13:10:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- UnifiedToolManager now delegates to ToolPlatform for policy/runtime behavior
- investigate.py uses ToolPlatform.visible_tools for planner surface and ToolPlatform.invoke for runtime
- Planner validation checks ToolView names instead of raw descriptors/ALLOWLIST
- Conversation service always projects results through ToolResultProjector
- 197 tests pass across tools, investigate, conversation, and replay suites
- Policy engine allows action_draft callers to execute write tools (matching old manager behavior)

## Task Commits

1. **Task 1: Wire ToolPlatform into manager and investigate** - `883421f` (feat)
2. **Task 2: Route conversation storage through projector** - `9568ce4` (feat)

## Files Created/Modified

- `src/tools/manager.py` - Delegates to ToolPlatform, adds visible_tools method
- `src/tools/platform.py` - Adds stub executors, projector property, with_defaults(None) support
- `src/tools/policy.py` - Allows action_draft callers to execute write tools
- `src/tools/runtime.py` - Reorders gates (auth before schema), improves denial status mapping
- `src/tools/projection.py` - Extracts refs from ToolResultV2 envelope
- `src/agent/nodes/investigate.py` - Uses ToolPlatform for visibility, invocation, validation
- `src/conversation/service.py` - Always projects results through ToolResultProjector
- `tests/agent/test_nodes/test_investigate.py` - Adds _FakePlatform for test compatibility
- `tests/tools/test_tool_result_storage.py` - Updates assertions for projector-normalized data

## Decisions Made

- UnifiedToolManager creates ToolPlatform with custom catalog from RegisteredTool wrappers
- Investigate falls back to ToolPlatform(executors={}) when session is None and no manager provided
- _StubExecutor class provides tool registration without session for auth/visibility testing
- Policy engine side_effect check skips blocking for action_draft callers on write tools
- Runtime denial status uses explicit status_map instead of conditional logic
- ToolResultProjector extracts business_fact_refs and policy_evidence_refs from ToolResultV2 envelope

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FakeManager missing _platform attribute**
- **Found during:** Task 1 (test execution)
- **Issue:** investigate.py tried tool_manager._platform but FakeManager didn't have it
- **Fix:** Added _FakePlatform class and _platform attribute to FakeManager
- **Files modified:** tests/agent/test_nodes/test_investigate.py
- **Verification:** All 28 investigate tests pass
- **Committed in:** 883421f

**2. [Rule 2 - Missing Critical] ToolPlatform.with_defaults(session=None) crashes**
- **Found during:** Task 1 (test execution)
- **Issue:** KnowledgeToolExecutor requires session, None causes ValueError
- **Fix:** Added _StubExecutor class and with_defaults(None) creates stub registry
- **Files modified:** src/tools/platform.py
- **Verification:** Auth/visibility tests pass with session=None
- **Committed in:** 883421f

**3. [Rule 1 - Bug] ToolResultProjector missing envelope refs**
- **Found during:** Task 2 (test execution)
- **Issue:** Projector only extracted refs from data dict, not from ToolResultV2 envelope
- **Fix:** Added envelope-level ref extraction for business_fact_refs and policy_evidence_refs
- **Files modified:** src/tools/projection.py
- **Verification:** test_policy_retrieval_semantics_survive_tool_result_flattening passes
- **Committed in:** 9568ce4

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All fixes were necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing architecture test failure: `action_draft.py` imports `src.tools.executors.action` (not related to Phase 29 changes)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 29 APF-06/APF-07 integration complete
- ToolPlatform is the target graph-facing boundary for future phases
- UnifiedToolManager is now a legacy compatibility adapter
- Conversation and graph state consume projector-normalized data
- Ready for Phase 30 BusinessFactService Boundary

---
*Phase: 29-tool-platform-boundary*
*Completed: 2026-06-23*
