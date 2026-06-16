---
phase: 15-replay-event-contract
reviewed: 2026-06-16T16:21:20Z
depth: deep
files_reviewed: 27
files_reviewed_list:
  - src/actions/service.py
  - src/agent/events.py
  - src/agent/trace.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/routers/traces.py
  - src/approvals/service.py
  - src/db/migrations/versions/010_replay_event_v3.py
  - src/db/models.py
  - src/replay/__init__.py
  - src/replay/lifecycle.py
  - src/replay/pairing.py
  - src/replay/schemas.py
  - src/replay/service.py
  - src/replay/validators.py
  - tests/agent/test_events.py
  - tests/agent/test_tools/test_create_coupon_grant_draft.py
  - tests/approvals/test_needs_info_resume.py
  - tests/replay/test_lifecycle_finalizer.py
  - tests/replay/test_operation_pairing.py
  - tests/replay/test_replay_api.py
  - tests/replay/test_replay_migration_contract.py
  - tests/replay/test_replay_redaction_retention.py
  - tests/replay/test_replay_service.py
  - tests/replay/test_sequence_allocator.py
  - tests/test_agent_runs_api.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-06-16T16:21:20Z
**Depth:** deep
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Reviewed the replay event contract implementation, API projection paths, lifecycle/status writers, approval/action integration, migration/model alignment, and replay-focused tests. The change keeps `/trace` as the legacy rollback fallback and does not introduce Phase 17 `action_execution_*` event families in the reviewed source.

Two replay-contract issues remain. `/replay` currently reports stored v3 operation events as `unresolved` even when the append path validated them as paired, and the pairing check itself can race because validation happens before the per-run advisory lock is acquired. Targeted tests were not run successfully in this shell because the default interpreter is Python 3.9 and the suite imports `datetime.UTC`, which requires Python 3.11+.

## Warnings

### WR-01: `/replay` Drops Pairing Status For Persisted V3 Operation Events

**File:** `src/replay/service.py:150`
**Issue:** `get_replay()` projects each stored row with `self.project_event(event, include_retention_class=False)` and does not pass a computed `pairing_status`. For any persisted `replay_event.v3` operation event, `_projected_pairing_status()` then receives `None` and returns `unresolved` at lines 234-242. This means a `tool_call_completed` event that was validated as `paired` by `append_event()` is later exposed by `/replay` as `unresolved`, breaking the event-store-first replay contract. Existing tests cover append-time pairing but do not cover `/replay` projection of an operation start/terminal pair.
**Fix:** Recompute pairing while projecting the ordered timeline, or persist pairing status. For example:

```python
timeline = []
prior_events = []
for event in events:
    pairing_status = None
    if event.schema_version == "replay_event.v3":
        pairing_status = validate_operation_pairing(prior_events, event).pairing_status
    timeline.append(self.project_event(event, pairing_status=pairing_status, include_retention_class=False))
    prior_events.append(event)
```

Add an API/service test that appends `tool_call_started` and `tool_call_completed`, calls `get_replay()` or `/replay`, and asserts the terminal event provenance is `paired`.

### WR-02: Operation Pairing Validation Is Not Protected By The Per-Run Lock

**File:** `src/replay/service.py:84`
**Issue:** `append_event()` loads `existing_events` and validates operation pairing at lines 83-97 before acquiring the advisory lock inside `allocate_sequence()` at line 99. Two concurrent writers can both validate a terminal event against the same prior timeline before either inserts its row, then serialize only sequence allocation and both commit duplicate terminal events for the same `operation_id`. The unique `(run_id, sequence)` constraint prevents sequence collisions but does not protect pairing invariants.
**Fix:** Acquire the per-run advisory lock before reading existing events and validating pairing, then allocate the sequence under the same lock. One clean approach is to split the lock into a helper and call it once at the start of `append_event()`:

```python
await self._lock_run(run_uuid)
existing_events = await self._events_for_run(run_uuid)
pairing_result = validate_operation_pairing(existing_events, candidate)
sequence = await self._next_sequence_without_lock(run_uuid)
```

Add a concurrency test where two sessions attempt terminal events for the same started `operation_id`; exactly one should commit and the other should fail with `OperationPairingError`.

---

_Reviewed: 2026-06-16T16:21:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
