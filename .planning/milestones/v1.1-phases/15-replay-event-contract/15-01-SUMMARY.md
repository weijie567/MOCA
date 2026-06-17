---
phase: 15-replay-event-contract
plan: 01
subsystem: replay
tags: [replay, pydantic, sqlalchemy, alembic, postgres]

requires:
  - phase: 10-state-lifecycle-routing-migration
    provides: minimal_event_envelope.v1 and agent_trace_events base table
  - phase: 13-approval-state-machine
    provides: approval event additions and approval_requests table
  - phase: 14-demo-action-executor-boundary
    provides: action_draft_created event and action_drafts table
provides:
  - ReplayEventV3 and ReplayResponseV3 strict schemas
  - Phase 15 baseline replay event enum
  - agent_trace_events ReplayEventV3 expansion migration
  - blocking Alembic upgrade verification
affects: [15-02-replay-service, 15-03-operation-pairing, 15-05-replay-api]

tech-stack:
  added: []
  patterns:
    - Strict Pydantic v2 replay contract schemas with ConfigDict(extra="forbid")
    - Expand-only Alembic migration preserving minimal_event_envelope.v1 rows

key-files:
  created:
    - src/replay/__init__.py
    - src/replay/schemas.py
    - src/replay/validators.py
    - src/db/migrations/versions/010_replay_event_v3.py
    - tests/replay/test_replay_service.py
    - tests/replay/test_replay_migration_contract.py
  modified:
    - src/db/models.py

key-decisions:
  - "Kept existing actor, resource_refs, and redacted_payload physical column names; ReplayEventV3 projects the contract shape without renaming Phase 10 storage."
  - "Deferred execution_id because no Phase 17 action_executions table exists in this repository yet."
  - "Recorded the blocking Alembic upgrade as an empty verification commit because Task 3 intentionally changed no files."

patterns-established:
  - "Replay schemas live under src/replay as the canonical Phase 15 contract owner."
  - "Migration event_type checks mirror src.replay.validators.REPLAY_EVENT_TYPES and are tested for parity."

requirements-completed: [REPLAY-01, REPLAY-02, REPLAY-03]

duration: 12 min
completed: 2026-06-16
---

# Phase 15 Plan 01: Replay Event Contract Foundation Summary

**ReplayEventV3 schemas, baseline replay event registry, agent_trace_events V3 expansion migration, and live Alembic head upgrade gate**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-16T13:44:41Z
- **Completed:** 2026-06-16T13:56:33Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added strict `ReplayEventV3`, `ReplayResponseV3`, provenance, retention, and error schemas.
- Added a consolidated Phase 10-15 replay event enum and validation helper.
- Expanded `AgentTraceEvent` and added Alembic revision `010_replay_event_v3` with V3 columns, checks, and replay indexes.
- Applied the live schema upgrade with `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head`.

## Task Commits

1. **Task 1 RED: replay schema contract tests** - `d830fb5` (test)
2. **Task 1 GREEN: replay schema implementation** - `43c2176` (feat)
3. **Task 2 RED: replay migration contract tests** - `062b0e7` (test)
4. **Task 2 GREEN: ORM and Alembic expansion** - `190ad5d` (feat)
5. **Task 3: blocking schema upgrade gate** - `fb1a7c8` (chore, empty verification commit)

## Files Created/Modified

- `src/replay/__init__.py` - Exports the replay schemas and validator helpers.
- `src/replay/schemas.py` - Strict ReplayEventV3 and ReplayResponseV3 Pydantic schemas.
- `src/replay/validators.py` - Baseline Phase 15 replay event registry and validator.
- `src/db/models.py` - Adds V3 nullable expansion fields, checks, and replay query indexes to AgentTraceEvent.
- `src/db/migrations/versions/010_replay_event_v3.py` - Expand-only Alembic migration for V3 columns/checks/indexes.
- `tests/replay/test_replay_service.py` - Schema and enum contract tests for native V3 and legacy minimal projections.
- `tests/replay/test_replay_migration_contract.py` - ORM/migration contract tests, enum parity, and no-backwrite assertions.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py -q --tb=short` - PASS, 4 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py -q --tb=short` - PASS, 4 passed after upgrade.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py tests/replay/test_replay_service.py -q --tb=short` - PASS, 8 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` - PASS; first run upgraded `009_action_draft_v2 -> 010_replay_event_v3`, second run confirmed head.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/schemas.py src/replay/validators.py src/db/models.py src/db/migrations/versions/010_replay_event_v3.py tests/replay` - PASS.

## Decisions Made

- Preserved existing Phase 10 storage names for `actor`, `resource_refs`, and `redacted_payload` instead of physically renaming them to `*_json`; downstream replay service can project the API contract shape.
- Did not add `execution_id` in Plan 15-01 because Phase 17 owns external execution tables and no referenced table exists yet.
- Used an empty verification commit for Task 3 so the blocking live schema upgrade gate remains visible in git history.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. PostgreSQL was reachable on `localhost:5432`, so the Docker fallback was not needed.

## Known Stubs

None.

## TDD Gate Compliance

- RED commits present before GREEN commits for Task 1 and Task 2.
- GREEN commits followed the RED commits and passed the focused tests.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 15-02. The replay schemas, baseline enum, ORM expansion, Alembic migration, and live schema upgrade gate are in place for the ReplayService append/projection work.

## Self-Check: PASSED

- Verified key files exist on disk.
- Verified task commit hashes exist in git history.
- No missing summary claims found.

---
*Phase: 15-replay-event-contract*
*Completed: 2026-06-16*
