---
phase: 13-approval-state-machine
plan: 06
subsystem: approvals
tags: [approval-events, replay-envelope, redaction, sla-scanner, pytest]

requires:
  - phase: 13-approval-state-machine
    provides: ApprovalService transitions, revision/hash semantics, and needs_info/edit behavior from Plans 13-03 through 13-05
provides:
  - Phase 13 approval lifecycle event additions on the minimal event envelope
  - Redacted approval event helpers that write agent_trace_events and approval_events audit rows
  - ApprovalService event emission for request, decision, edit, respond, and expiry transitions
  - Disabled-by-default ApprovalSlaScanner with safe SLA event-shape helpers
affects: [phase-13-approval-state-machine, phase-15-replay-event-contract]

tech-stack:
  added: []
  patterns:
    - Approval event helpers emit minimal trace rows and link approval audit rows through replay_event_id
    - Approval event JSON stores refs, hashes, versions, enums, and booleans only
    - SLA scanning remains configuration-disabled until Phase 15 replay/allocator gates pass

key-files:
  created:
    - src/approvals/events.py
    - src/approvals/sla_scanner.py
    - tests/approvals/test_events.py
    - tests/approvals/test_sla_scanner.py
  modified:
    - .env.example
    - src/agent/events.py
    - src/approvals/repository.py
    - src/approvals/service.py
    - src/config.py
    - tests/agent/test_events.py

key-decisions:
  - "Approval_requested, approval_decided, approval_expired, and approval_resumed are registered as minimal_event rows before Phase 15 replay enrichment."
  - "Edit and respond decisions now emit approval_decided with old_revision_ref and new_revision_ref; approval_resumed is registered as a helper but graph lifecycle wiring remains Phase 15-owned."
  - "ApprovalSlaScanner defaults to disabled via APPROVAL_SLA_SCANNER_ENABLED=false; Phase 15 owns enabling active scanning after replay and allocator gates pass."

patterns-established:
  - "Approval events use ApprovalEvent.resource_refs_json plus AgentTraceEvent.resource_refs for IDs, revision refs, hashes, and versions."
  - "Event redaction guards reject raw_prompt, raw_args, raw_payload, raw_tool_output, secrets, credentials, and pii keys."
  - "Scanner dry-run event shapes are testable without scheduler registration or disabled-path DB writes."

requirements-completed:
  - APPROVAL-03
  - APPROVAL-01
  - SNAPSHOT-01

duration: 15 min
completed: 2026-06-15
---

# Phase 13 Plan 06: Approval Events and SLA Scanner Summary

**Approval lifecycle events now emit redacted minimal envelope rows linked to approval_events, with the SLA scanner implemented but disabled by default**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-15T09:11:27Z
- **Completed:** 2026-06-15T09:26:28Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added approval event tests covering minimal event registration, retention classification, actor/resource refs, decision type coverage, required old/new revision refs, and forbidden raw/secrets/PII keys.
- Registered `approval_requested`, `approval_decided`, `approval_expired`, and `approval_resumed` in the minimal event registry and redaction guard.
- Added `src/approvals/events.py` helper functions that emit `agent_trace_events`, link/update `approval_events.replay_event_id`, and persist only safe metadata/resource/payload fields.
- Wired `ApprovalService.create_request`, `decide`, and `expire_due_request` to emit helpers after durable transition rows exist.
- Added `ApprovalSlaScanner` with `APPROVAL_SLA_SCANNER_ENABLED=false`, disabled no-op behavior, and safe reminder/escalation/expire event-shape helpers.

## Task Commits

1. **Task 1: Add approval event and SLA scanner tests** - `a95163f` (test)
2. **Task 2: Register approval event additions and add approval event helpers** - `54d202c` (feat)
3. **Task 3: Implement disabled-by-default SLA scanner and config** - `19f1209` (feat)

## Files Created/Modified

- `src/approvals/events.py` - Approval event helper functions, revision-ref enforcement, and approval-event redaction validation.
- `src/approvals/sla_scanner.py` - Feature-disabled scanner, typed scan result, and safe SLA event-shape builder.
- `tests/approvals/test_events.py` - Approval event registration, helper wiring, redaction, and revision-ref tests.
- `tests/approvals/test_sla_scanner.py` - Disabled scanner config/no-write tests and SLA event-shape tests.
- `src/agent/events.py` - Approval minimal event registration and expanded forbidden redacted payload keys.
- `src/approvals/service.py` - Service transition wiring for requested/decided/expired events.
- `src/approvals/repository.py` - Base approval audit refs and redacted payload defaults for approval_events rows.
- `src/config.py` - `approval_sla_scanner_enabled` default false config field.
- `.env.example` - `APPROVAL_SLA_SCANNER_ENABLED=false`.
- `tests/agent/test_events.py` - Central approval event retention and redaction tests.

## Verification

- `uv run pytest tests/approvals/test_events.py tests/approvals/test_sla_scanner.py tests/agent/test_events.py -q --tb=short` - **PASS**: 39 passed, 1 existing LangGraph pending-deprecation warning.
- `uv run pytest tests/approvals/test_service_transitions.py tests/approvals/test_needs_info_resume.py -q --tb=short` - **PASS**: 24 passed, 1 existing LangGraph pending-deprecation warning.
- `uv run ruff check src/agent/events.py src/approvals/events.py src/approvals/sla_scanner.py src/config.py tests/approvals/test_events.py tests/approvals/test_sla_scanner.py` - **PASS**.

## Decisions Made

- `respond` and `edit` are represented in the minimal envelope as `approval_decided` events, with `old_revision_ref` and `new_revision_ref` so Phase 15 does not infer decision semantics.
- `approval_resumed` is registered and has a helper, but no graph resume wiring was forced in Phase 13 because `approval_decided` already carries the needed decision refs; Phase 15 owns lifecycle replay/resume wiring.
- The SLA scanner has an enabled code path behind config, but no scheduler/startup hook and no disabled-path query/write side effects; Phase 15 owns scanner enablement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Enriched generic approval audit rows with base refs**
- **Found during:** Task 2 (Register approval event additions and add approval event helpers)
- **Issue:** The plan required `ApprovalEvent` rows to carry request, level, assignment, decision, revision, hash, and version refs, but existing repository inserts only included caller-provided partial refs.
- **Fix:** Updated `ApprovalRepository.insert_approval_event` to add base request/revision/hash refs plus level/assignment/decision refs whenever those rows are present.
- **Files modified:** `src/approvals/repository.py`
- **Verification:** Focused approval event tests, service transition tests, and ruff checks passed.
- **Committed in:** `54d202c`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The change keeps the plan's audit/replay contract consistent across existing approval audit rows. No new external behavior or Phase 15 replay API was introduced.

## Issues Encountered

- Focused pytest commands emit one existing LangGraph `allowed_objects` pending-deprecation warning from the dependency stack; tests pass.
- A pre-existing untracked `study_plan/` directory remains in the worktree and was not touched.

## Known Stubs

None - stub scan found only type annotations/defaults such as `None` parameters and local empty dict/list initialization, not placeholder behavior or unwired data paths.

## User Setup Required

None - no external service configuration required. `APPROVAL_SLA_SCANNER_ENABLED=false` is documented in `.env.example` and remains the Phase 13 default.

## Threat Flags

None - the new event and scanner surfaces are the planned Phase 13 threat-model surfaces and are covered by redaction, event-shape, disabled-scanner, and service-transition tests.

## Self-Check: PASSED

- Found `.planning/phases/13-approval-state-machine/13-06-SUMMARY.md`.
- Found `src/approvals/events.py` and `src/approvals/sla_scanner.py`.
- Verified task commits `a95163f`, `54d202c`, and `19f1209` resolve in git history.
- Working tree contains only this summary and expected planning-state updates before the metadata commit, plus the pre-existing untracked `study_plan/` directory.

## Next Phase Readiness

Plan 13-07 can add owner-boundary/static legacy tests on top of the new approval event helper boundary. Phase 15 can later enrich these minimal approval events into ReplayEventV3 and decide whether to enable the SLA scanner after replay coverage and allocator concurrency gates pass.

---
*Phase: 13-approval-state-machine*
*Completed: 2026-06-15*
