---
phase: 12-session-memory
fixed_at: 2026-06-14T13:08:05Z
review_path: .planning/phases/12-session-memory/12-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-06-14T13:08:05Z
**Source review:** .planning/phases/12-session-memory/12-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-001: Sensitive PII Can Still Be Persisted

**Files modified:** `src/memory/service.py`, `src/agent/nodes/memory_write.py`, `tests/memory/test_session_memory_service.py`, `tests/agent/test_memory_write_node.py`
**Commit:** 078a193
**Applied fix:** Blocked both `sensitive` and `prohibited` PII classifications at the service boundary, added raw phone/ID/credential detection in the memory-write node, and covered sensitive/raw PII skip behavior with regressions.

### WR-001: Timed-Out Memory Writes Can Be Committed Anyway

**Files modified:** `src/agent/nodes/memory_write.py`, `tests/agent/test_memory_write_node.py`
**Commit:** 2c2cfd6
**Applied fix:** Rolled back the DB session on memory-write timeout before returning `write_timeout`, with a regression proving a flushed `memory_write_started` event is not committed afterward.

### WR-002: First Concurrent Writes to an Empty Scope Lose One Update

**Files modified:** `src/memory/service.py`, `tests/memory/test_session_memory_concurrency.py`
**Commit:** 7a95fb6
**Applied fix:** Treated insert-path unique constraint races as CAS misses by rolling back, reloading the active scope, and applying the deterministic merge/conflict path. Added empty-scope and expired-scope concurrent write regressions.

### WR-003: New Slot Memory Rows Do Not Get Row-Level Expiry

**Files modified:** `src/memory/service.py`, `tests/memory/test_session_memory_service.py`
**Commit:** e430e10
**Applied fix:** Set row-level `expires_at` from slot expiry during inserts and pruned expired slots before merge expiry recomputation. Added a regression that stale summary/refs no longer claim continuity after initial slot expiry.

### WR-004: CAS Merge Can Silently Drop Field Updates

**Files modified:** `src/memory/service.py`, `tests/memory/test_session_memory_service.py`
**Commit:** 78aba7e
**Applied fix:** Made over-cap summary merges observable via bounded truncation and `reason_code=summary_truncated`, and returned explicit `last_intent_conflict` on CAS retry scalar disagreement.

### WR-005: Tests Miss the Highest-Risk Persistence Edges

**Files modified:** `tests/agent/test_memory_write_node.py`
**Commit:** cb5e7f3
**Applied fix:** Added a node-level regression that verifies initial memory-write inserts use the configured slot TTL for row-level expiry. The other requested edge regressions were added alongside CR-001 and WR-001 through WR-004.

---

_Fixed: 2026-06-14T13:08:05Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
