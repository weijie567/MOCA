---
phase: 28-decision-event-foundation
plan: 01
subsystem: replay
tags: [decision-events, replay, pydantic, redaction, sequence-allocator]

requires:
  - phase: 27-trustedcontextfactory-and-projections
    provides: ReplayContext trusted identity and projection-local version metadata
provides:
  - Strict DecisionEventEnvelopeV1 schema for minimal_event_envelope.v1
  - Replay-owned emit_decision_event facade over ReplayService.append_event
  - Shared resource_refs redaction guard
  - Legacy src.agent.events.emit_event wrapper delegation
  - Memory write lifecycle operation_id regression coverage
affects: [phase-29-tool-platform-boundary, phase-31-memory-platform-boundary, phase-35-replay-and-eval-hardening]

tech-stack:
  added: []
  patterns: [strict-pydantic-envelope, replay-owned-emitter, first-seen-reason-code-normalization]

key-files:
  created:
    - src/replay/decision_events.py
    - tests/replay/test_decision_events.py
  modified:
    - src/replay/validators.py
    - src/replay/service.py
    - src/replay/__init__.py
    - src/agent/events.py
    - src/agent/nodes/memory_write.py
    - tests/agent/test_events.py
    - tests/agent/test_memory_write_node.py
    - tests/replay/test_sequence_allocator.py

key-decisions:
  - "DecisionEventEnvelopeV1 maps strictly to minimal_event_envelope.v1 and does not create a second event format."
  - "Reason codes normalize into redacted_payload.reason_codes with first-seen de-duplication."
  - "Policy/model/tool versions stay under redacted_payload.versions; redaction_policy_version remains the envelope field."
  - "resource_refs use the same unsafe-key guard as redacted_payload."

patterns-established:
  - "Replay facade: new decision event writers should call src.replay.decision_events.emit_decision_event."
  - "Compatibility wrapper: existing src.agent.events.emit_event callers route through the replay-owned facade."
  - "Operation lifecycle events: node/tool/RAG/LLM/memory minimal events require operation_id."

requirements-completed: [APF-05]

duration: 18min
completed: 2026-06-23
---

# Phase 28 Plan 01: Decision Event Foundation Summary

**Replay-owned minimal decision event envelope with strict schema validation, reason/version normalization, resource-ref redaction, and wrapper compatibility**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-23T01:57:09Z
- **Completed:** 2026-06-23T02:15:32Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added `DecisionEventEnvelopeV1` and `emit_decision_event(...)` under `src/replay/decision_events.py`.
- Added recursive `guard_resource_refs(...)` and wired it into `ReplayService.append_event(...)`.
- Routed `src.agent.events.emit_event(...)` through the replay-owned emitter while preserving compatibility.
- Added focused tests for strict envelope fields, missing identity, operation-id conditions, reason/version normalization, redaction leakage, wrapper compatibility, memory operation ids, and sequence allocator ordering.

## Task Commits

1. **Task 1: Wave 0 decision-event contract tests** - `42f3b8c` (`test`)
2. **Task 2: Implement replay-owned decision event facade** - `9bb9882` (`feat`)
3. **Task 3: Route legacy event wrapper, patch memory key path, and run final gates** - `1bc9d97` (`feat`)

**Plan metadata:** this SUMMARY commit.

## Files Created/Modified

- `src/replay/decision_events.py` - Strict minimal envelope schema, emitter facade, and reason/version normalization helpers.
- `src/replay/validators.py` - Added resource refs unsafe-key guard.
- `src/replay/service.py` - Applies `guard_resource_refs(...)` and validates minimal projections through `DecisionEventEnvelopeV1`.
- `src/replay/__init__.py` - Exports the new replay decision-event public boundary.
- `src/agent/events.py` - Keeps the legacy wrapper but delegates to `emit_decision_event(...)`.
- `src/agent/nodes/memory_write.py` - Passes one memory write `operation_id` through started, terminal, and failure events.
- `tests/replay/test_decision_events.py` - Contract coverage for APF-05.
- `tests/agent/test_events.py` - Wrapper compatibility and legacy reason-code tests.
- `tests/agent/test_memory_write_node.py` - Focused memory lifecycle operation-id regressions.
- `tests/replay/test_sequence_allocator.py` - Adds the replay-owned emitter to shared allocator coverage.

## Decisions Made

- Used `src/replay/decision_events.py` as the public owner for the envelope and emitter, matching Observability / Replay ownership.
- Kept service-specific metadata inside `redacted_payload` and `redacted_payload.versions`, not top-level envelope fields.
- Preserved existing `agent_trace_events` storage and did not add DB migrations.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope expansion; Phase 28 stayed within foundation and compatibility boundaries.

## Issues Encountered

- Initial RED run exposed a stray patch marker in `tests/replay/test_decision_events.py`; removed it and reran RED successfully against missing `src.replay.decision_events`.
- A parallel pytest attempt against the shared PostgreSQL test DB caused `pg_type_typname_nsp_index` setup conflicts; reran the same suites sequentially and they passed.

## Verification

- `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py -q` - 73 passed.
- `uv run pytest tests/replay/test_sequence_allocator.py tests/platform/test_context_projections.py -q` - 11 passed.
- `uv run pytest tests/replay tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/platform/test_context_projections.py -q` - 132 passed.
- `git diff --name-only -- src/db/models.py src/db/migrations` - no output.
- `rg -n "DecisionEventEnvelopeV1|emit_decision_event|guard_resource_refs|operation_id" ...` - confirmed contract, emitter, guard, wrapper, and memory operation-id references.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 29 can build Tool Platform Boundary decision events on top of `emit_decision_event(...)`, `redacted_payload.reason_codes`, and `redacted_payload.versions` without inventing another envelope. Phase 35 can also rely on `ReplayService.project_minimal_event(...)` being schema-validated.

---
*Phase: 28-decision-event-foundation*
*Completed: 2026-06-23*
