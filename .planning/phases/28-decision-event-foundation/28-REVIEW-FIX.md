---
phase: 28
phase_name: decision-event-foundation
status: fixed
source_review: external_deep_review
fixed_at: 2026-06-23T03:00:00Z
findings_fixed:
  blocker: 2
  warning: 1
---

# Phase 28 Review Fix

## Findings Disposition

1. `ReplayService.append_event(...)` flushed invalid minimal lifecycle events before `DecisionEventEnvelopeV1` validation.
   - Verdict: confirmed.
   - Fix: minimal envelope projection is now validated before `session.add(...)` / `flush()`.
   - Regression: `test_append_minimal_event_validates_before_flush_on_operation_id_failure` catches the validation error, commits the session, and asserts no additional `AgentTraceEvent` row was persisted.

2. `memory_write` emitted duplicate `memory_write_failed` terminal events on service exceptions.
   - Verdict: confirmed.
   - Fix: post-start service exceptions are now re-raised to the outer handler, which emits the single failed terminal event with the shared operation id.
   - Regression: `test_memory_write_failure_events_carry_non_null_operation_id` now asserts the exact lifecycle sequence `memory_write_started`, `memory_write_failed`.

3. Legacy minimal operation rows with null `operation_id` needed explicit compatibility coverage.
   - Verdict: partially confirmed. `project_minimal_event(...)` remains strict for the current minimal envelope contract, but `/replay` V3 projection uses `project_event(...)` and can still read historical minimal rows as unresolved provenance.
   - Fix: no production behavior change required.
   - Regression: `test_get_replay_projects_legacy_minimal_operation_row_without_operation_id` verifies legacy minimal operation rows remain readable through `ReplayService.get_replay(...)`.

## Verification

- `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/replay/test_sequence_allocator.py tests/replay/test_replay_service.py -q` - 90 passed, 1 warning.
- `uv run pytest tests/replay -q` - 100 passed, 1 warning.
- `uv run ruff check src/replay/service.py src/agent/nodes/memory_write.py tests/replay/test_decision_events.py tests/agent/test_memory_write_node.py tests/replay/test_replay_service.py` - passed.

## Residual Risk

Full repository tests were not rerun for this narrow review fix. The touched behavior is covered by focused replay and memory-write suites.
