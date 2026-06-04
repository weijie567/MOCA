---
phase: 07-tool-registry-contracts
plan: 04
subsystem: agent-state
tags: [pydantic, langgraph-state, api-regression, compatibility]

requires:
  - phase: 07-01
    provides: strict tool contract models and validation tests
  - phase: 07-02
    provides: safe caller-aware registry boundary
  - phase: 07-03
    provides: typed adapters and prompt-facing sanitization
provides:
  - Strict versioned InvestigationResult schema for downstream bounded investigator phases.
  - Dormant optional AgentState investigation fields.
  - Regression assertions proving graph state and public API event payloads do not expose dormant investigation fields.
affects: [phase-08-routing, phase-09-investigator, phase-10-observability]

tech-stack:
  added: []
  patterns:
    - Pydantic v2 schema contracts with Literal stop reasons and extra-field rejection
    - TypedDict optional state extensions kept dormant until later graph routing phases

key-files:
  created: []
  modified:
    - src/agent/schemas.py
    - src/agent/state.py
    - tests/agent/test_tools/test_tool_contracts.py
    - tests/agent/test_graph.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "InvestigationResult is strict and versioned with schema_version='v1' so later phases can evolve the contract explicitly."
  - "Investigation state fields remain optional dictionaries/lists in AgentState and are not wired into current graph or API serialization."
  - "Compatibility is guarded with negative assertions on graph state summaries and API event payloads."

patterns-established:
  - "Dormant future-phase state fields must be paired with regression assertions proving current response surfaces remain unchanged."
  - "API event payload tests assert both top-level absence and serialized absence for future internal-only fields."

requirements-completed: [STATE-01, STATE-02, STATE-03, STATE-04, TEST-01]

duration: 32min
completed: 2026-06-04
---

# Phase 07 Plan 04: Dormant Investigation Schema and State Summary

**Versioned investigation contracts and optional state fields now exist without changing current graph or API behavior.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-06-04T06:12:00Z
- **Completed:** 2026-06-04T06:44:02Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added strict `InvestigationResult` validation in `src/agent/schemas.py` with version, confidence bounds, stop-reason literals, evidence references, missing information, candidate action, and safety notes.
- Added dormant optional investigation keys to `AgentState` without changing graph edges, routing, recommendation behavior, API schemas, or database schema.
- Extended contract, graph, and API tests to prove the new fields validate strictly while remaining absent from current runtime outputs.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing investigation contract test** - `be56733` (test)
2. **Task 1 GREEN: dormant investigation schema/state** - `fc7507f` (feat)
3. **Task 2: investigation contract rejection tests** - `b4b1bee` (test)
4. **Task 3: dormant graph/API regression assertions** - `8690f64` (test)

## Files Created/Modified

- `src/agent/schemas.py` - Adds strict versioned `InvestigationResult`.
- `src/agent/state.py` - Adds optional dormant investigation state keys.
- `tests/agent/test_tools/test_tool_contracts.py` - Proves valid and invalid investigation schema/state behavior.
- `tests/agent/test_graph.py` - Proves current graph outputs do not contain dormant investigation fields or route through investigator nodes.
- `tests/test_agent_runs_api.py` - Proves current API event payloads do not expose dormant investigation fields.

## Decisions Made

- Kept `investigation_result` as an optional internal state field rather than exposing it through public response schemas.
- Used explicit negative assertions in API event tests so later phases must intentionally change response payloads if they expose investigator output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Recreated stale PostgreSQL container to run API regression tests**
- **Found during:** Task 3 verification
- **Issue:** `tests/test_agent_runs_api.py` could not run because the local Postgres container exited with a bogus socket lock file.
- **Fix:** Recreated the `postgres` compose container with `docker compose up -d --force-recreate postgres`, preserving the existing data volume.
- **Files modified:** None
- **Verification:** Full target command passed with `51 passed`.
- **Committed in:** Not applicable; environment fix only.

---

**Total deviations:** 1 auto-fixed (Rule 3 environment blocker)
**Impact on plan:** No implementation scope expansion. The environment repair enabled the planned API regression verification.

## Issues Encountered

- The initial target test run failed because sandboxed execution could not connect to `localhost:5432`.
- After elevated execution, the failure changed to connection refused because Postgres was not running.
- The existing Postgres container had stale lock-file state and was fixed by recreating the container while preserving the volume.

## Verification

- `uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q` - PASSED (`51 passed`, one existing LangGraph deprecation warning).

## Stub Scan

No blocking stubs found. The new investigation fields are intentionally dormant and are guarded by regression tests.

## Threat Flags

None - the implementation preserves the Phase 7 boundary: no graph routing, public API, DB, or execution behavior changes.

## User Setup Required

None - no external service configuration required. Local API regression tests require the compose Postgres service to be running.

## Next Phase Readiness

Phase 8 can consume the strict `InvestigationResult` and optional state keys when adding investigation routing, while current v1.0 graph/API behavior remains guarded by regression tests.

## Self-Check: PASSED

- Found `src/agent/schemas.py` with `InvestigationResult`.
- Found `src/agent/state.py` with dormant investigation fields.
- Found regression assertions in `tests/agent/test_graph.py` and `tests/test_agent_runs_api.py`.
- Found commits `be56733`, `fc7507f`, `b4b1bee`, and `8690f64` in git log.
- Target verification passed with `51 passed`.

---
*Phase: 07-tool-registry-contracts*
*Completed: 2026-06-04*
