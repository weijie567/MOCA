---
phase: 15-replay-event-contract
plan: 02
subsystem: replay
tags: [replay, event-store, sqlalchemy, pytest, redaction]

requires:
  - phase: 15-01
    provides: ReplayEventV3 strict schemas, baseline replay enum, and V3-expanded agent_trace_events storage
provides:
  - ReplayService append/projection boundary
  - replay-owned redaction and retention validators
  - compatibility emit_event wrapper delegated through ReplayService
  - shared allocator tests for pre-lifecycle writer surfaces
affects: [15-03-operation-pairing, 15-04-run-lifecycle-finalizer, 15-05-replay-api, 15-06-replay-safety]

tech-stack:
  added: []
  patterns:
    - ReplayService owns advisory-lock sequence allocation and event append/projection
    - src.agent.events remains a minimal envelope compatibility facade over src.replay

key-files:
  created:
    - src/replay/service.py
    - tests/replay/test_replay_redaction_retention.py
    - tests/replay/test_sequence_allocator.py
  modified:
    - src/replay/__init__.py
    - src/replay/validators.py
    - src/agent/events.py
    - tests/replay/test_replay_service.py
    - tests/agent/test_events.py

key-decisions:
  - "ReplayService keeps the existing advisory-lock plus max(sequence)+1 allocator and does not add AgentRun.next_event_sequence or a counter table."
  - "Minimal event callers keep schema_version minimal_event_envelope.v1 and the prior return envelope while routing through ReplayService."
  - "Retention classification is replay service projection metadata and stored safely in redacted_payload for V3 writes without changing the strict ReplayRetention schema."

patterns-established:
  - "New replay append logic belongs in src/replay/service.py; legacy event helpers delegate instead of duplicating allocation or persistence."
  - "Every accepted replay event type must have an explicit EVENT_RETENTION_CLASSIFICATION entry."

requirements-completed: [REPLAY-01, REPLAY-02, REPLAY-03]

duration: 17 min
completed: 2026-06-16
---

# Phase 15 Plan 02: Replay Service Boundary Summary

**ReplayService-owned append/projection/allocation with shared redaction-retention validators and compatibility event delegation**

## Performance

- **Duration:** 17 min
- **Started:** 2026-06-16T13:58:00Z
- **Completed:** 2026-06-16T14:15:06Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `ReplayService` with advisory-lock sequence allocation, append, minimal-envelope projection, and V3 projection.
- Moved replay redaction and retention validation into `src.replay.validators`.
- Rewired `src.agent.events.emit_event()` and `allocate_sequence()` to delegate through `ReplayService` while preserving Phase 10-14 imports and minimal schema defaults.
- Added focused tests for unsafe payload rejection, explicit retention classification, resume sequence continuation, concurrent appends, and pre-lifecycle writer surface coverage.

## Task Commits

1. **Task 1 RED: ReplayService validator tests** - `357d28e` (test)
2. **Task 1 GREEN: ReplayService append boundary** - `dfdc9d4` (feat)
3. **Task 2 RED: allocator/delegation tests** - `91609f2` (test)
4. **Task 2 GREEN: compatibility wrapper delegation** - `dded347` (feat)

## Files Created/Modified

- `src/replay/service.py` - Owns shared sequence allocation, event append, minimal projection, and V3 projection.
- `src/replay/validators.py` - Adds `EVENT_RETENTION_CLASSIFICATION`, `FORBIDDEN_REDACTED_PAYLOAD_KEYS`, `guard_redacted_payload()`, and `retention_for_event_type()`.
- `src/replay/__init__.py` - Exports the new service and validator helpers.
- `src/agent/events.py` - Keeps legacy constants/functions but delegates allocation and append to `ReplayService`.
- `tests/replay/test_replay_service.py` - Adds service append and unregistered event rejection coverage.
- `tests/replay/test_replay_redaction_retention.py` - Adds recursive unsafe key and retention registry coverage.
- `tests/replay/test_sequence_allocator.py` - Adds resume, concurrency, and writer-surface allocator coverage with named deferrals.
- `tests/agent/test_events.py` - Adds compatibility delegation coverage.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_redaction_retention.py -q --tb=short` - PASS, 9 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/service.py src/replay/validators.py tests/replay/test_replay_service.py tests/replay/test_replay_redaction_retention.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/replay/test_sequence_allocator.py -q --tb=short` - PASS, 17 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/events.py tests/agent/test_events.py tests/replay/test_sequence_allocator.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_sequence_allocator.py tests/replay/test_replay_redaction_retention.py tests/agent/test_events.py -q --tb=short` - PASS, 26 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay src/agent/events.py tests/replay tests/agent/test_events.py` - PASS.

## Decisions Made

- Kept the Phase 15 allocator model as advisory transaction lock plus `max(sequence)+1`, matching D-04 and avoiding new counters.
- Preserved `src.agent.events.SCHEMA_VERSION = "minimal_event_envelope.v1"` for compatibility callers.
- Kept lifecycle/finalizer allocator coverage explicitly deferred to Plan 15-04 and external worker allocator coverage explicitly deferred to Phase 17.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first GREEN pass briefly exposed `retention_class` through the strict `ReplayRetention` schema dump. Fixed before commit by keeping strict schema unchanged and adding retention class as service projection metadata.
- Ruff caught an unused compatibility constant import in `src.agent.events`; fixed by assigning the public constant from the replay validator export.

## Known Stubs

None. Stub scan found only legitimate optional `None` defaults and empty test dictionaries, not placeholder or unwired runtime behavior.

## Threat Flags

None. The new event persistence service and unsafe-key guard were expected surfaces in the plan threat model.

## TDD Gate Compliance

- RED commits present before GREEN commits for Task 1 and Task 2.
- GREEN commits followed the RED commits and passed the focused tests.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 15-03. Replay append/projection and the shared pre-lifecycle allocator boundary are in place; operation pairing, lifecycle finalizer coverage, `/replay` API, and final replay safety cleanup remain owned by later Phase 15 plans.

## Self-Check: PASSED

- Verified key files exist on disk.
- Verified task commit hashes exist in git history.
- No missing summary claims found.

---
*Phase: 15-replay-event-contract*
*Completed: 2026-06-16*
