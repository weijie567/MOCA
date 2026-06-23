---
phase: 29-tool-platform-boundary
plan: 01
subsystem: testing
tags: [tdd, red-tests, tool-platform, policy, replay-events, projection]

requires:
  - phase: 28-decision-event-foundation
    provides: DecisionEventEnvelopeV1 / emit_decision_event replay-owned emitter path
provides:
  - Wave 0 RED tests locking APF-06/APF-07 tool-platform boundary behavior before production code
  - Test names consumed by Plans 29-02 (contract tests) and 29-03/29-04 (runtime/platform/projection tests)
affects: [29-02, 29-03, 29-04, tool-platform-boundary]

tech-stack:
  added: []
  patterns:
    - TDD RED-first locking of planned contracts before implementation
    - Deferred imports of not-yet-existing modules to keep collection granular per wave

key-files:
  created:
    - tests/tools/test_tool_platform.py
    - tests/replay/test_tool_policy_events.py
  modified:
    - tests/replay/test_decision_events.py
    - tests/replay/test_replay_migration_contract.py
    - tests/agent/test_tools/test_unified_tool_manager.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/conversation/test_service.py
    - tests/architecture/test_tool_boundaries.py

key-decisions:
  - "Top-level imports in test_tool_platform.py limited to Plan 29-02 contracts/policy so the file collects as soon as 29-02 lands; ToolPlatform/ToolRuntime/ToolResultProjector imports (29-03) are deferred into the tests that exercise them so 29-02's four-test verify can run."
  - "Architecture executor-import ban matches 29-04 acceptance: all graph nodes must dispatch through ToolPlatform rather than importing src.tools.executors.* directly."
  - "Conversation smoke test selects ToolResultRecord by tool_result_id (String column), not the auto-generated UUID PK id."

patterns-established:
  - "RED tests reference planned symbols (ToolViewV1, ToolPolicyDecision, ToolPolicyEngine, ToolPlatform, ToolRuntime, ToolResultProjector, tool_policy_* event types, migration 017) and fail only because those artifacts do not exist yet."

requirements-completed: []  # Wave 0 RED tests; APF-06/APF-07 completed by later plans

duration: 1 min
completed: 2026-06-23
---

# Phase 29 Plan 01: Wave 0 RED Tests Summary

**Locked the approved tool-platform boundary (prompt-safe ToolView, runtime auth, decision events, result projection, manager/investigate/conversation wiring) with failing tests across 8 files before any production code.**

## Performance

- **Duration:** ~1 min (verification runs)
- **Tasks:** 1
- **Files modified:** 8 (2 new, 6 extended)

## Accomplishments
- Added `tests/tools/test_tool_platform.py` covering ToolViewV1 prompt-safety, prompt-safe schema projection, ToolPolicyDecision non-envelope + reason-code rules, ToolPlatform visibility/runtime-auth, and ToolResultProjector raw-sentinel stripping.
- Added `tests/replay/test_tool_policy_events.py` covering `tool_policy_visibility_recorded` / `tool_policy_runtime_auth_recorded` registration, retention, and per-field redaction/resource-ref guards.
- Extended replay, manager, investigate, conversation, and architecture tests for namespaced reason codes, migration 017 contract, manager delegation, ToolView-only planner surface, projector-normalized storage with key/value raw-sentinel checks, and ToolPlatform facade boundaries.
- Verified the plan's RED gate: suite exits non-zero with a planned-missing-artifact marker (`ToolViewV1`) and no syntax/dependency-collection errors.

## Task Commits

1. **Task 1: Wave 0 RED tests for tool platform contracts** - `3ef7e72` (test)

## Files Created/Modified
- `tests/tools/test_tool_platform.py` - RED coverage for ToolViewV1, policy, runtime, projection, platform contracts
- `tests/replay/test_tool_policy_events.py` - tool-policy event registration, payload, redaction, resource-ref RED coverage
- `tests/replay/test_decision_events.py` - namespaced extension reason-code compatibility RED
- `tests/replay/test_replay_migration_contract.py` - migration 017 event-type alignment RED
- `tests/agent/test_tools/test_unified_tool_manager.py` - compatibility adapter delegation RED
- `tests/agent/test_nodes/test_investigate.py` - ToolView prompt + projected graph-state + runtime denial RED
- `tests/conversation/test_service.py` - projector-normalized storage smoke RED
- `tests/architecture/test_tool_boundaries.py` - ToolPlatform facade + executor-import boundary RED

## Verification

Plan `<verify>` command result:
- `uv run pytest <8 files> -q` → exit status 2 (non-zero, RED).
- Output contains planned-missing-artifact marker `ToolViewV1` (ImportError: cannot import name 'ToolViewV1' from src.tools.contracts).
- No `SyntaxError` / `IndentationError` / `ModuleNotFoundError` for pytest/pydantic/sqlalchemy/alembic.

## Deviations from Plan

None.

## Post-Review Repairs

- Corrected the unavailable-tool visibility test so executor-unavailable tools are excluded from `ToolViewV1[]` and recorded only as visibility decisions with `tool_unavailable`.
- Corrected the `UnifiedToolManager` delegation test fake to match the `ToolPlatform.invoke(...) -> ToolInvocationOutcome` contract while preserving manager `invoke(...) -> ToolResultV2` compatibility.
- Removed the architecture-test exception for `action_draft.py` so the executor-import ban matches 29-04 acceptance.
- Strengthened raw-sentinel checks to cover forbidden values as well as forbidden keys, and split tool-policy event rejection into per-field assertions.

## Issues Encountered

None in the implementation run. Post-review DB-backed checks were run serially; RED failures were the intended missing-artifact/old-behavior failures, and guard-only assertions passed where the existing redaction layer already enforced them.

## Self-Check: PASSED

- [x] Wave 0 tests exist in every listed file and encode APF-06/APF-07 behavior before production code.
- [x] Test failures are intentional RED failures caused by missing planned contracts/modules, not syntax errors or unrelated environment setup.
- [x] No production file is modified by this plan.

Ready for Plan 29-02.
