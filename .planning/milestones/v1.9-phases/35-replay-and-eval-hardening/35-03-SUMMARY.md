---
phase: 35-replay-and-eval-hardening
plan: 35-03
subsystem: replay-dev-contract-tests
tags: [replay, lifecycle, operation-pairing, redaction, pytest]

requires:
  - phase: 35-01
    provides: "Phase 35 replay/eval coverage matrix and required P0 replay rows"
provides:
  - "P0 terminal/current replay timeline golden tests for normal, interrupted, resumed, rejected, responded, expired, error, and cancelled runs"
  - "Operation identity tests for started/terminal pairs and retry parent/attempt semantics"
  - "D-16 redaction negative tests for raw prompts, raw tool/action payloads, PII aliases, secrets, credentials, debug payloads, buyer names, and API keys"
affects: [phase35, replay, eval, APF-17, APF-18]

tech-stack:
  added: []
  patterns:
    - "Golden replay timelines are seeded from stored events via RunLifecycleService and ReplayService, not graph/model/tool reruns"
    - "Retry terminal events close a started retry operation while duplicate starts/terminals remain forbidden"
    - "Replay redaction rejects Phase 35 unsafe aliases at append and projection time"

key-files:
  created:
    - tests/replay/test_phase35_terminal_timelines.py
    - tests/replay/test_phase35_operation_identity.py
    - tests/replay/test_phase35_redaction_negatives.py
  modified:
    - src/replay/lifecycle.py
    - src/replay/service.py
    - src/replay/pairing.py
    - src/replay/validators.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Used existing replay event types only; no replay registry, ORM constraint, or migration event-type expansion was introduced."
  - "Approval expired timeline fixtures use the existing minimal-envelope approval event shape to avoid treating approval lifecycle events as V3 operations."
  - "Replay response projection now preserves explicit null fields inside timeline events while continuing to omit absent top-level rag_claim_summary."

patterns-established:
  - "Terminal timeline goldens assert sequence monotonicity, schema_version, final/current status semantics, and forbidden terminal/execution states."
  - "Operation identity tests assert operation_id, parent_operation_id, attempt, and pairing_status from ReplayService projections."
  - "Redaction negatives test both append-time validation and stored-row projection rejection."

requirements-completed: [APF-17, APF-18]

duration: 15 min
completed: 2026-06-29
---

# Phase 35 Plan 35-03: Golden Replay Timelines, Operation Identity, and Redaction Negatives Summary

**P0 replay golden timelines with operation retry identity and raw-payload exposure negatives enforced by focused pytest gates**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-29T15:20:38Z
- **Completed:** 2026-06-29T15:36:21Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added eight P0 terminal/current timeline goldens: `normal_completed`, `interrupted_approval_required`, `resumed_completed`, `rejected`, `responded_needs_info`, `expired`, `error`, and `cancelled`.
- Added replay operation identity tests for tool, RAG, LLM, memory, and retry paths with `operation_id`, `parent_operation_id`, `attempt`, and `pairing_status` assertions.
- Added D-16 redaction negatives for raw prompt/tool/action payloads, ticket/order/refund PII aliases, secrets, credentials, unsafe debug payloads, buyer names, and API keys.
- Kept replay audit-only: tests seed stored events through `RunLifecycleService` and `ReplayService`; no graph, LLM, tool, RAG, or external action rerun path was introduced.

## Task Commits

1. **Task 1 RED: Terminal timeline goldens** - `de21b50` (`test`)
2. **Task 1 GREEN: Terminal timeline replay support** - `51b1459` (`feat`)
3. **Task 2 RED: Operation identity and redaction negatives** - `000894e` (`test`)
4. **Task 2 GREEN: Retry identity and redaction aliases** - `b231ccb` (`feat`)

## Files Created/Modified

- `tests/replay/test_phase35_terminal_timelines.py` - P0 terminal/current replay timeline golden tests.
- `tests/replay/test_phase35_operation_identity.py` - Operation pair and retry identity projection tests.
- `tests/replay/test_phase35_redaction_negatives.py` - D-16 append/projection raw exposure negative tests.
- `src/replay/lifecycle.py` - Adds safe `cancellation_source` metadata for cancelled lifecycle replay events.
- `src/replay/service.py` - Preserves explicit `None` timeline fields while omitting absent top-level `rag_claim_summary`.
- `src/replay/pairing.py` - Allows retry terminal events to close the started retry operation while retaining duplicate guards.
- `src/replay/validators.py` - Adds Phase 35 forbidden raw/PII/debug alias keys.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese records for handled Task 1 and Task 2 validation failures.

## Decisions Made

- Used minimal-envelope approval lifecycle events for `approval_expired`, matching existing approval emitters and avoiding a new event type.
- Treated redaction alias expansion as a validator-only change; no service-specific ad hoc filtering was added.
- Preserved top-level replay API compatibility by omitting `rag_claim_summary` when absent while keeping strict timeline event fields visible.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added safe cancellation source metadata**
- **Found during:** Task 1 (Terminal timeline goldens)
- **Issue:** The cancelled replay timeline could not record source metadata required by the P0 golden.
- **Fix:** Added `cancellation_source` to `RunLifecycleService.mark_cancelled()` and status event payloads.
- **Files modified:** `src/replay/lifecycle.py`
- **Verification:** Task 1 pytest and ruff commands passed.
- **Committed in:** `51b1459`

**2. [Rule 1 - Bug] Preserved explicit null timeline fields in replay responses**
- **Found during:** Task 1 verification
- **Issue:** `ReplayService.get_replay(..., exclude_none=True)` removed timeline fields such as `operation_id: None`, breaking V3 replay shape and an existing regression test.
- **Fix:** Dump replay responses without nested `exclude_none`, then remove only absent top-level `rag_claim_summary`.
- **Files modified:** `src/replay/service.py`
- **Verification:** `tests/replay/test_replay_service.py` passed in Task 1 and plan-level suites.
- **Committed in:** `51b1459`

**3. [Rule 1 - Bug] Allowed retry terminal events to close retry operation pairs**
- **Found during:** Task 2 (Operation identity tests)
- **Issue:** Retry terminal events were rejected because the retry started event already used the new retry `operation_id`.
- **Fix:** Allowed terminal retry events to close an existing retry started event while keeping duplicate retry starts and duplicate terminals rejected.
- **Files modified:** `src/replay/pairing.py`
- **Verification:** Task 2 pytest and plan-level pytest passed.
- **Committed in:** `b231ccb`

**4. [Rule 2 - Missing Critical] Added D-16 forbidden redaction aliases**
- **Found during:** Task 2 (Redaction negatives)
- **Issue:** Replay validation did not reject Phase 35 aliases such as `raw_tool_payload`, `ticket_pii`, `raw_action_payload`, `unsafe_debug_payload`, `buyer_name`, and `api_key`.
- **Fix:** Added the aliases to `FORBIDDEN_REDACTED_PAYLOAD_KEYS`.
- **Files modified:** `src/replay/validators.py`
- **Verification:** Task 2 pytest and plan-level pytest passed.
- **Committed in:** `b231ccb`

---

**Total deviations:** 4 auto-fixed (2 bug fixes, 2 missing critical safeguards)
**Impact on plan:** All fixes were directly required by the planned goldens/negatives and stayed inside existing replay event types and Phase 35 scope.

## Issues Encountered

- Task 1 RED initially also exposed fixture-shape issues: `approval_expired` needed the existing minimal-envelope shape and `ReplayError` needed `retryable`. Both were fixed before GREEN and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Task 2 RED failed as intended on retry terminal pairing and missing redaction aliases. The failures were implemented and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_terminal_timelines.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_service.py -q --tb=short` - passed (`32 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/replay/test_phase35_terminal_timelines.py src/replay/lifecycle.py src/replay/service.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_operation_identity.py tests/replay/test_phase35_redaction_negatives.py tests/replay/test_operation_pairing.py tests/replay/test_replay_redaction_retention.py tests/replay/test_tool_policy_events.py -q --tb=short` - passed (`61 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/replay/test_phase35_operation_identity.py tests/replay/test_phase35_redaction_negatives.py src/replay/service.py src/replay/validators.py` - passed
- Plan-level pytest passed: `93 passed, 1 warning`
- Plan-level ruff passed.
- Acceptance `rg` probes for scenario identifiers, forbidden completed/execution assertions, operation identity fields, and D-16 aliases passed.

## Known Stubs

None. Stub-pattern scan found no placeholder/TODO/FIXME or hardcoded empty UI/data-source stubs in the created/modified replay files.

## Threat Flags

None. This plan added tests and replay validation/pairing hardening only; no new endpoint, auth path, file access pattern, schema boundary, or replay event type was introduced.

## TDD Gate Compliance

- Task 1 RED: `de21b50` added failing terminal timeline tests before implementation.
- Task 1 GREEN: `51b1459` implemented lifecycle/projection support and made the Task 1 suite pass.
- Task 2 RED: `000894e` added failing operation identity and redaction negative tests before implementation.
- Task 2 GREEN: `b231ccb` implemented retry pairing and redaction aliases and made the Task 2 suite pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `35-04-PLAN.md`. The Phase 35 replay dev-contract layer now covers P0 terminal timelines, operation retry identity, and raw exposure negatives without broadening replay event types or execution scope.

## Self-Check: PASSED

- Found created files: `tests/replay/test_phase35_terminal_timelines.py`, `tests/replay/test_phase35_operation_identity.py`, `tests/replay/test_phase35_redaction_negatives.py`, and this summary.
- Found task commits: `de21b50`, `51b1459`, `000894e`, and `b231ccb`.
- Final plan-level pytest and ruff verification passed.

---
*Phase: 35-replay-and-eval-hardening*
*Completed: 2026-06-29*
