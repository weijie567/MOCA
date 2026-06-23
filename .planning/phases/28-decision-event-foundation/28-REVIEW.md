---
phase: 28
phase_name: decision-event-foundation
reviewed: 2026-06-23T03:10:46Z
status: issues_found
depth: deep
files_reviewed: 11
files_reviewed_list:
  - src/agent/events.py
  - src/agent/nodes/memory_write.py
  - src/replay/__init__.py
  - src/replay/decision_events.py
  - src/replay/service.py
  - src/replay/validators.py
  - tests/agent/test_events.py
  - tests/agent/test_memory_write_node.py
  - tests/replay/test_decision_events.py
  - tests/replay/test_replay_service.py
  - tests/replay/test_sequence_allocator.py
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
---

# Phase 28: Code Review Report

**Reviewed:** 2026-06-23T03:10:46Z
**Depth:** deep
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Phase 28 decision-event foundation at current HEAD `5b807fe`, including the post-review fix commit. The core envelope, wrapper delegation, sequence allocator, minimal pre-flush validation, legacy V3 projection compatibility, and memory-write operation-id regressions are mostly covered. Three meaningful contract risks remain: a cold-import circular dependency, replay projection leakage for stored `resource_refs`, and incomplete runtime enforcement of the new `reason_codes: list[str]` contract.

Verification notes:

- `uv run python -c "import src.replay"` fails with a circular import.
- `uv run python -c "import src.agent.events"` fails with a circular import.
- `uv run pytest tests/replay/test_decision_events.py -q` passes, which means the current pytest import order masks the cold-start failure.

## Critical Issues

### CR-01: Cold imports of replay and agent event surfaces fail

**File:** `src/replay/decision_events.py:14`
**Issue:** `decision_events.py` imports `ReplayContext` at runtime. A fresh `import src.replay` loads `src/replay/__init__.py`, which imports `decision_events`; that import loads `src.platform.context_projections`, which loads `src.tools`, whose package initializer imports `UnifiedToolManager`, which imports `src.agent.events`, which imports `src.replay` while the package is only partially initialized. In a cold process this raises `ImportError` before replay or agent event helpers can be used. This directly breaks the replay-owned emitter and compatibility wrapper surfaces.
**Fix:**
```python
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from src.platform.context_projections import ReplayContext
```

Keep `from __future__ import annotations`, remove the runtime `ReplayContext` import, and treat the value structurally in `_resolve_identity` / `_normalize_versions` via attribute access. Add subprocess smoke coverage so pytest import order cannot hide the issue:

```python
def test_replay_and_agent_event_modules_cold_import() -> None:
    import subprocess
    import sys

    subprocess.run([sys.executable, "-c", "import src.replay"], check=True)
    subprocess.run([sys.executable, "-c", "import src.agent.events"], check=True)
```

### CR-02: Stored `resource_refs` are not guarded during replay projection

**File:** `src/replay/service.py:210`
**Issue:** `project_event(...)` re-validates `redacted_payload` before returning replay data, but it passes `event.resource_refs` through unchanged at line 228. `project_minimal_event(...)` likewise returns `resource_refs` at line 193 without a guard. New writes are protected by `append_event(...)`, but legacy rows, direct inserts, or rows created before the new guard can still expose unsafe keys through `/replay` or minimal projection. This violates the Phase 28 leakage guard contract for `resource_refs`.
**Fix:**
```python
payload = dict(event.redacted_payload or {})
refs = dict(event.resource_refs or {})
guard_redacted_payload(payload)
guard_resource_refs(refs)

# then use refs in the projection
"resource_refs": refs,
```

Apply the same pattern in `project_minimal_event(...)`. Add a regression that inserts an `AgentTraceEvent` with `resource_refs={"typed_ref": {"raw_payload": "unsafe"}}` and asserts `ReplayService(session).get_replay(run_id)` or `project_event(row)` raises before returning the unsafe ref.

## Warnings

### WR-01: `reason_codes` can bypass the list/snake_case contract

**File:** `src/replay/decision_events.py:124`
**Issue:** `normalize_reason_codes(...)` expands `reason_codes` as an arbitrary iterable. If an untyped caller passes `reason_codes="foo"`, it is treated as `["f", "o"]`; if a tuple is passed, it is accepted even though the contract says `list[str]`. Separately, `_normalize_redacted_payload(...)` copies caller payloads before normalization, so a caller can pass `redacted_payload={"reason_codes": "ScopeDenied"}` with no explicit `reason_codes` argument and persist malformed reason metadata. This is an audit contract risk because downstream replay consumers can no longer rely on `redacted_payload.reason_codes` being a first-seen, de-duped `list[str]`.
**Fix:** Reject non-list `reason_codes` at runtime and normalize or reject a pre-existing `redacted_payload["reason_codes"]` before persistence.

```python
if reason_codes is not None and not isinstance(reason_codes, list):
    raise ValueError("reason_codes must be a list[str]")

payload_reason_codes = payload.get("reason_codes")
if payload_reason_codes is not None:
    payload["reason_codes"] = normalize_reason_codes(reason_codes=payload_reason_codes) or []
```

Add negative tests for `reason_codes="scope_denied"` and `redacted_payload={"reason_codes": "ScopeDenied"}`. Keep existing legacy singular `redacted_payload.reason_code` behavior for non-migrated writers unless a later phase explicitly migrates those payloads.

---

_Reviewed: 2026-06-23T03:10:46Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
