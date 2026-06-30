---
phase: 28
fixed_at: 2026-06-23T03:20:16Z
review_path: .planning/phases/28-decision-event-foundation/28-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 28: Code Review Fix Report

**Fixed at:** 2026-06-23T03:20:16Z
**Source review:** .planning/phases/28-decision-event-foundation/28-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: Cold imports of replay and agent event surfaces fail

**Status:** fixed
**Files modified:** `src/replay/decision_events.py`, `tests/replay/test_decision_events.py`
**Commit:** bd928ee
**Applied fix:** Moved `ReplayContext` behind `TYPE_CHECKING` so `src.replay` no longer imports platform projections at runtime, and added subprocess cold-import smoke coverage for `src.replay` and `src.agent.events`.

### CR-02: Stored `resource_refs` are not guarded during replay projection

**Status:** fixed: requires human verification
**Files modified:** `src/replay/service.py`, `tests/replay/test_replay_service.py`
**Commit:** 62af758
**Applied fix:** Re-validates copied stored `resource_refs` during both V3 and minimal replay projection, and added regressions proving unsafe legacy/direct rows raise before replay data is returned.

### WR-01: `reason_codes` can bypass the list/snake_case contract

**Status:** fixed: requires human verification
**Files modified:** `src/replay/decision_events.py`, `tests/replay/test_decision_events.py`
**Commit:** f03597f
**Applied fix:** Rejects non-list `reason_codes`, normalizes payload-provided `redacted_payload.reason_codes`, rejects malformed payload values, and preserves the legacy singular `redacted_payload.reason_code` behavior.

## Verification

- `uv run python -c "import src.replay" && uv run python -c "import src.agent.events"` - passed.
- `uv run ruff check src/replay/decision_events.py src/replay/service.py tests/replay/test_decision_events.py tests/replay/test_replay_service.py` - passed.
- `uv run pytest tests/replay/test_decision_events.py tests/replay/test_replay_service.py -q` - 66 passed, 1 warning.
- Orchestrator verification: `uv run python -c "import src.replay; import src.agent.events; print('cold imports ok')"` - passed.
- Orchestrator verification: `uv run ruff check src/replay/decision_events.py src/replay/service.py tests/replay/test_decision_events.py tests/replay/test_replay_service.py src/agent/events.py src/agent/nodes/memory_write.py tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/replay/test_sequence_allocator.py` - passed.
- Orchestrator verification: `uv run pytest tests/replay/test_decision_events.py tests/replay/test_replay_service.py tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/replay/test_sequence_allocator.py -q` - 97 passed, 1 warning.
- Orchestrator verification: `uv run pytest tests/replay -q` - 107 passed, 1 warning.

## Residual Risk

Full repository tests were not run. The fixed contract paths were independently verified with cold-import checks, focused Phase 28 replay/agent/memory suites, and the full `tests/replay` suite.

---

_Fixed: 2026-06-23T03:20:16Z_
_Fixer: Codex (gsd-code-fixer)_
_Iteration: 1_
