---
phase: 29-tool-platform-boundary
plan: 03
subsystem: tools
tags: [tool-platform, policy-engine, runtime, projection, pydantic]

requires:
  - phase: 29-02
    provides: "ToolViewV1, ToolPolicyDecision, ToolPolicyEngine, reason-code validation, event registration"
provides:
  - "ToolPlatform facade with visible_tools(...) and invoke(...)"
  - "ToolRuntime hard boundary chain before and after executor dispatch"
  - "ToolResultProjector four-layer projection boundary"
  - "Safe policy-denial ToolResultV2 mapping"
  - "Runtime availability filtering from executor registry"
affects: [29-04, investigate, conversation, manager-compat]

tech-stack:
  added: []
  patterns: [platform-facade, runtime-chain, result-projection, policy-decision-events]

key-files:
  created:
    - src/tools/platform.py
    - src/tools/runtime.py
    - src/tools/projection.py
  modified:
    - src/tools/manager_results.py
    - tests/tools/test_tool_platform.py

key-decisions:
  - "ToolPlatform delegates visibility decisions to ToolPolicyEngine and runtime auth to ToolRuntime"
  - "ToolRuntime emits runtime auth decision events through emit_decision_event only when session is available"
  - "ToolResultProjector extracts safe scalar keys from result.data rather than copying wholesale"
  - "Runtime denial status maps tool_unavailable to 'unavailable' and all other reasons to 'permission_denied'"
  - "MerchantScopeV1 must be model_dump()ed before passing to ToolCallContext.merchant_scope"

patterns-established:
  - "Platform facade pattern: ToolPlatform.visible_tools/invoke delegates to policy engine and runtime"
  - "Runtime chain pattern: descriptor → schema validation → policy decision → executor dispatch → projection"
  - "Projection layer pattern: normalized_result / prompt_projection / audit_refs / debug_projection"

requirements-completed: [APF-06, APF-07]

duration: 25min
completed: 2026-06-23
---

# Phase 29 Plan 03: ToolRuntime, ToolResultProjector, ToolPlatform Summary

**ToolPlatform facade with runtime auth chain and four-layer result projection replacing scattered allowlists**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-23T12:00:00Z
- **Completed:** 2026-06-23T12:25:00Z
- **Tasks:** 1
- **Files modified:** 5

## Accomplishments

- Created `ToolPlatform` graph-facing facade with `visible_tools(...)` and `invoke(...)` methods
- Implemented `ToolRuntime` with full gate order: descriptor lookup → input schema validation → runtime auth → executor dispatch → output schema validation → result projection → event emission
- Built `ToolResultProjector` producing four separated projection layers (normalized, prompt, audit, debug) with raw sentinel stripping
- All 20 Wave 0 RED tests now pass (10 tool_platform + 10 tool_policy_events)
- Extended `_RecordingExecutor` test helper to support multi-tool registration for scope-denial testing

## Task Commits

1. **Task 1: Implement ToolRuntime, ToolResultProjector, and ToolPlatform facade** - `470c3c7` (feat)

## Files Created/Modified

- `src/tools/platform.py` - Graph-facing ToolPlatform facade with visible_tools, invoke, descriptor, event_family
- `src/tools/runtime.py` - ToolRuntime with full gate chain and decision event emission
- `src/tools/projection.py` - ToolResultProjector with normalized/prompt/audit/debug projection layers
- `src/tools/manager_results.py` - Added "policy" to source Literal type for denial results
- `tests/tools/test_tool_platform.py` - Updated _RecordingExecutor for multi-tool, _ctx for MerchantScopeV1 conversion

## Decisions Made

- Runtime auth denial maps `tool_unavailable` → `unavailable` status, all other reasons → `permission_denied`
- `_RecordingExecutor` now accepts `set[str]` for multi-tool registration in tests
- `_ctx()` helper converts `MerchantScopeV1` to dict via `model_dump()` before passing to `ToolCallContext`
- `ToolRuntime._emit_decision_event` catches all exceptions to prevent event emission from blocking tool invocation
- `ToolPlatform._emit_visibility_event` catches all exceptions for same reason

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _RecordingExecutor only registered single tool name**
- **Found during:** Task 1 (test execution)
- **Issue:** Scope-denial test for get_merchant_risk failed because executor only handled get_order, making it unavailable before scope check
- **Fix:** Changed _RecordingExecutor to accept `str | set[str]` for tool names
- **Files modified:** tests/tools/test_tool_platform.py
- **Verification:** test_runtime_auth_rechecks_visible_tool_before_dispatch passes
- **Committed in:** 470c3c7

**2. [Rule 2 - Missing Critical] MerchantScopeV1 not convertible to ToolCallContext**
- **Found during:** Task 1 (test execution)
- **Issue:** ToolCallContext.merchant_scope expects dict/list but test passed MerchantScopeV1 directly
- **Fix:** Updated _ctx() helper to call model_dump() on Pydantic models
- **Files modified:** tests/tools/test_tool_platform.py
- **Verification:** All 10 tests pass
- **Committed in:** 470c3c7

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes were test-infrastructure corrections. No production code changes needed. No scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ToolPlatform, ToolRuntime, and ToolResultProjector are ready for integration
- Plan 29-04 can wire these into manager compatibility, investigate, and conversation seams
- 20/20 focused tests pass; broader suite (73 tests including decision events) passes

---
*Phase: 29-tool-platform-boundary*
*Completed: 2026-06-23*
