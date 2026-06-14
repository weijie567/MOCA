---
phase: 12-session-memory
reviewed: 2026-06-14T12:47:44Z
reviewed_at: 2026-06-14T12:47:44Z
depth: deep
files_reviewed: 31
files_reviewed_list:
  - src/agent/events.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/investigate.py
  - src/agent/nodes/memory_write.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/session_memory_load.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/config.py
  - src/db/migrations/versions/007_session_memories.py
  - src/db/models.py
  - src/memory/__init__.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - src/memory/service.py
  - tests/agent/test_empty_session_adapter.py
  - tests/agent/test_events.py
  - tests/agent/test_graph.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_memory_write_node.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_session_memory_load.py
  - tests/memory/test_session_memory_concurrency.py
  - tests/memory/test_session_memory_isolation.py
  - tests/memory/test_session_memory_repository.py
  - tests/memory/test_session_memory_schema.py
  - tests/memory/test_session_memory_service.py
  - tests/test_agent_runs_api.py
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
finding_counts:
  critical: 1
  warning: 5
  info: 0
  total: 6
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-06-14T12:47:44Z
**Depth:** deep
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Deep review covered the session-memory schema, repository, service, graph call chain, post-response write hooks, API behavior, event persistence, and focused tests. The same-thread slot inheritance path is generally fail-closed, and tests cover many positive and negative routing cases. The open issues are concentrated in PII policy enforcement and edge-case persistence semantics: timeout rollback, first-writer races, row TTL consistency, and observable CAS merge outcomes.

Focused verification run during review:

```bash
uv run pytest tests/memory/test_session_memory_concurrency.py tests/agent/test_memory_write_node.py -q --tb=short
```

Result: 8 passed, 1 warning.

## Critical Issues

### CR-001: Sensitive PII Can Still Be Persisted

**File:** `src/memory/service.py:97`

**Issue:** `MemoryService.write_session_memory` only blocks `pii_classification == "prohibited"`, while `SessionMemoryWriteCandidate` explicitly allows `"sensitive"` and the contract says sensitive content requires redaction or review before write. The only node classifier is a four-token substring check in `src/agent/nodes/memory_write.py:18` and `src/agent/nodes/memory_write.py:177`, so raw phone numbers, raw ID numbers, credentials not containing those exact markers, or any future caller that sets `pii_classification="sensitive"` will be written directly to `session_memories`.

**Fix:**

```python
# src/memory/service.py
BLOCKED_PII = {"sensitive", "prohibited"}

if candidate.decision == "skip" or candidate.pii_classification in BLOCKED_PII:
    reason_code = "pii_blocked" if candidate.pii_classification in BLOCKED_PII else candidate.reason_code
    return _write_result(candidate, status="skipped", decision="skip", reason_code=reason_code)
```

Also replace the marker-only classifier with a shared PII classifier or at least regex coverage for raw phone/ID/credential patterns, and add tests for `pii_classification="sensitive"` plus raw identifiers without labels.

## Warnings

### WR-001: Timed-Out Memory Writes Can Be Committed Anyway

**File:** `src/agent/nodes/memory_write.py:46`

**Issue:** `asyncio.wait_for` cancels `_write_with_service` on timeout and returns a skipped `write_timeout` result, but the timeout handler does not roll back the DB session. The background scheduler then unconditionally commits the same `memory_session` in `src/api/routers/agent_runs.py:662-666`. If the coroutine flushed `memory_write_started` or part of a session-memory insert/update before cancellation, that partial work can be committed even though the node reports a timeout skip.

**Fix:**

```python
except TimeoutError:
    rollback = getattr(session, "rollback", None)
    if callable(rollback):
        await rollback()
    return _skipped(state, started_at, "write_timeout", final_response=final_response)
```

Add a regression where a fake service flushes a row or event and then blocks past the timeout; after the scheduler commits, assert no partial memory/event rows remain.

### WR-002: First Concurrent Writes to an Empty Scope Lose One Update

**File:** `src/memory/service.py:113`

**Issue:** CAS retry only protects updates after an active row already exists. When two completed turns for the same tenant/user/thread both see `existing is None`, both call `_insert`; the partial unique index on `src/db/models.py:267` lets one insert win and makes the other raise. The broad handler at `src/memory/service.py:164` rolls the loser back and returns `fallback`, so a safe non-conflicting slot can be dropped instead of reloading and merging. The same race exists when both writers replace an expired active row.

**Fix:** Handle `IntegrityError` around insert paths as a CAS miss: rollback, reload the active row in a fresh transaction, and run the same deterministic merge/conflict logic. Alternatively, serialize by scope with a transaction-scoped advisory lock before read/insert.

```python
try:
    inserted = await self._insert(candidate, now=now)
except IntegrityError:
    await self.repository.session.rollback()
    return await self._merge_after_insert_race(candidate, now)
```

Add concurrency tests that start with no active row and with an expired active row; assert non-conflicting slots both survive or return an explicit conflict reason.

### WR-003: New Slot Memory Rows Do Not Get Row-Level Expiry

**File:** `src/memory/service.py:168`

**Issue:** `_insert` writes slot-level `expires_at` values but never passes `expires_at` to `repository.insert_active`. As a result, a newly inserted slot-backed row has `SessionMemory.expires_at = NULL`. Later loads filter expired slots, but `load_session_memory` still sets `continuity_claimed=True` when `session_summary`, `last_intent`, unresolved questions, or business refs remain (`src/memory/service.py:72-80`). A row created from an expired slot can therefore continue claiming continuity via stale summary/refs after the configured TTL.

**Fix:**

```python
async def _insert(self, candidate: SessionMemoryWriteCandidate, *, now: datetime) -> SessionMemory:
    envelope = SessionSlotsEnvelopeV1(slots=candidate.explicit_slots)
    return await self.repository.insert_active(
        ...
        active_slots_json=envelope.model_dump(mode="json"),
        expires_at=_max_expiry(candidate.explicit_slots, now),
    )
```

Also prune expired slots during merge before computing `_max_expiry`, and add a test that writes a slot, advances past `session_memory_ttl_seconds`, and verifies no stale continuity is claimed from that slot's generated summary.

### WR-004: CAS Merge Can Silently Drop Field Updates

**File:** `src/memory/service.py:266`

**Issue:** `_merge_summary` returns the existing summary when the combined text exceeds `_SUMMARY_CAP`, silently dropping the candidate summary while the write can still report `written` or `merged_after_conflict` with `reason_code="eligible"`. Similarly, `_merge_last_intent` preserves the existing intent on CAS retry when it differs from the candidate (`src/memory/service.py:289`) without an observable field-level reason. This violates the phase's deterministic merge policy that concurrent scalar/JSON changes must be preserved or surfaced as an explicit conflict/fallback/merge warning.

**Fix:** Make merge helpers return structured warnings or conflicts, and propagate them into `SessionMemoryWriteResult.reason_code` / `conflict_reason`.

```python
if len(combined) > _SUMMARY_CAP:
    return _MergeResult({}, "session_summary_cap_exceeded")

if cas_retry and existing and candidate and existing != candidate:
    return _MergeResult({}, "last_intent_conflict")
```

If dropping is intentional, persist a bounded summary with an explicit truncation marker and return an observable `reason_code` such as `summary_truncated`.

### WR-005: Tests Miss the Highest-Risk Persistence Edges

**File:** `tests/memory/test_session_memory_concurrency.py:88`

**Issue:** The concurrency suite starts from an existing active row, so it does not exercise the insert race in WR-002. The timeout test uses a fake slow service that never touches the DB, so it cannot catch WR-001. Current PII tests only use labeled marker strings such as `"身份证 ..."` and do not cover `pii_classification="sensitive"` or raw numeric identifiers, leaving CR-001 untested. TTL tests cover manually expired rows, but not the service's initial insert path from WR-003.

**Fix:** Add focused regressions for:

```text
- concurrent writes when no active row exists
- concurrent replacement of an expired active row
- timeout after a flush, followed by scheduler commit
- sensitive classification and raw phone/ID values
- initial insert expiry after session_memory_ttl_seconds
- summary cap / last_intent CAS conflict observability
```

---

_Reviewed: 2026-06-14T12:47:44Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
