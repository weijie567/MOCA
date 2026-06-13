---
phase: 10-state-lifecycle-routing-migration
plan: 02
subsystem: trace-events
tags: [postgresql, sqlalchemy, alembic, trace-events, replay-foundation, pytest]
requires:
  - phase: 09-business-tool-facade
    provides: Read-tool allowlist and BusinessToolService boundary decisions
provides:
  - agent_trace_events base table and ORM model
  - minimal_event_envelope.v1 emitter and per-run sequence allocator
  - tool_call versus rag_retrieval event-family classifier
affects: [phase-10-investigate, phase-12-memory-events, phase-13-approval-events, phase-15-replay]
tech-stack:
  added: []
  patterns:
    - PostgreSQL advisory-lock sequence allocation per run
    - UUIDv5 event_id derived from run_id and sequence
    - redacted_payload guard against raw data keys
key-files:
  created:
    - src/db/migrations/versions/006_agent_trace_events.py
    - src/agent/events.py
    - tests/agent/test_events.py
  modified:
    - src/db/models.py
key-decisions:
  - "Used PostgreSQL transaction advisory lock keyed by run_id before MAX(sequence)+1 allocation; `(run_id, sequence)` remains the uniqueness backstop."
  - "Kept `iteration` inside `redacted_payload`, not as an envelope top-level field."
patterns-established:
  - "Event families are classified by call nature: get_* -> tool_call, search_* -> rag_retrieval."
  - "Emitters accept only caller-provided redacted summaries and reject raw payload-like keys."
requirements-completed: [ROUTE-02]
duration: 15 min
completed: 2026-06-13
---

# Phase 10 Plan 02: Minimal Trace Event Foundation Summary

**Minimal trace event table and emitter with monotonic per-run sequencing, event-family classification, and redacted payload guards**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-13T15:50:00Z
- **Completed:** 2026-06-13T16:05:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `AgentTraceEvent` and migration `006_agent_trace_events` with `event_id` as the single primary key and `(run_id, sequence)` uniqueness.
- Added `src/agent/events.py` with `minimal_event_envelope.v1`, event type registry, read-tool family classifier, sequence allocator, and event emitter.
- Added DB-backed tests covering monotonic sequence allocation, resume continuation, uniqueness collision rejection, classification, single-family operation emission, iteration placement, and redaction guard behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: AgentTraceEvent ORM model + 006 migration** - `2b03e87` (`feat`)
2. **Task 2: Event emitter, per-run sequence allocator, and classifier** - `4d395d2` (`feat`)
3. **Task 3: Event tests** - `4301792` (`test`)

## Files Created/Modified

- `src/db/models.py` - Adds `AgentTraceEvent` and `AgentRun.trace_events` relationship.
- `src/db/migrations/versions/006_agent_trace_events.py` - Creates the base event table and indexes.
- `src/agent/events.py` - Provides allocator, classifier, and emitter.
- `tests/agent/test_events.py` - Verifies persistence, sequencing, classification, iteration, and redaction contracts.

## Decisions Made

- Used PostgreSQL advisory locks instead of an unlocked Python counter so concurrent writers for the same run serialize sequence allocation.
- Used `uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{sequence}")` for stable event IDs derived from run ordering.
- Raised `ValueError` for redaction and allowlist violations so callers get explicit runtime failures rather than optimized-away assertions.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- True `asyncio.gather` concurrency is not safe with the shared test `AsyncSession`, so the concurrency test uses the plan-approved fallback: manual duplicate `(run_id, sequence)` insertion and `IntegrityError` assertion.

## Verification

- `uv run pytest tests/agent/test_events.py -x -q` passed: 7 tests.
- `uv run python -c "from src.db.models import AgentTraceEvent; from src.agent.events import emit_event, allocate_sequence, classify_event_family"` passed.
- ORM primary-key and uniqueness assertions passed.
- `rg` checks confirmed `minimal_event_envelope.v1`, `AgentTraceEvent`, `uq_agent_trace_events_run_seq`, and the `005_approval_tables` migration chain.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Wave 2. Plan 10-04 can now emit independent tool/RAG events from the bounded investigate loop using the Phase 10 event foundation.

---
*Phase: 10-state-lifecycle-routing-migration*
*Completed: 2026-06-13*
