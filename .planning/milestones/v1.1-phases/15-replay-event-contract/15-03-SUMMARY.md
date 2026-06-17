---
phase: 15-replay-event-contract
plan: 03
subsystem: replay
tags: [replay, operation-pairing, retry, provenance, pytest]

requires:
  - phase: 15-02
    provides: ReplayService append/projection boundary and shared sequence allocator
provides:
  - Operation pairing and retry validator for ReplayEventV3 operation events
  - ReplayService append-time pairing validation
  - Paired, unresolved, and not-applicable pairing provenance projection
  - Tests for duplicate terminals, retry parent links, bounded-loop iteration, and unresolved minimal rows
affects: [15-04-run-lifecycle-finalizer, 15-05-replay-api, 15-06-replay-safety]

tech-stack:
  added: []
  patterns:
    - Replay operation pairing validation lives in src/replay/pairing.py
    - ReplayService validates V3 operation candidates before persistence and keeps projection non-mutating

key-files:
  created:
    - src/replay/pairing.py
    - tests/replay/test_operation_pairing.py
  modified:
    - src/replay/__init__.py
    - src/replay/service.py
    - tests/replay/test_replay_service.py
    - tests/replay/test_sequence_allocator.py

key-decisions:
  - "Minimal and context-less historical rows remain pairing_status=unresolved; no projection path rewrites stored rows."
  - "Non-operation V3 lifecycle/audit events project pairing_status=not_applicable instead of being mislabeled unresolved."
  - "V3 operation writes now fail closed when operation_id or positive attempt is missing."

patterns-established:
  - "validate_operation_pairing(existing_events, candidate_event) returns explicit OperationPairingStatus metadata or raises OperationPairingError."
  - "ReplayService append_event passes validation context into project_event so newly appended terminal pairs can project as paired without backwriting."

requirements-completed: [REPLAY-01, REPLAY-02]

duration: 17 min
completed: 2026-06-16
---

# Phase 15 Plan 03: Operation Pairing and Legacy Projection Summary

**ReplayEventV3 operation pairing validator with retry checks, append-time ReplayService enforcement, and unresolved historical provenance projection**

## Performance

- **Duration:** 17 min
- **Started:** 2026-06-16T14:23:28Z
- **Completed:** 2026-06-16T14:40:55Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `src/replay/pairing.py` with suffix-based started/terminal classification, `OperationPairingError`, `OperationPairingStatus`, and `validate_operation_pairing()`.
- Added tests for valid started-to-terminal pairs, duplicate terminal rejection, missing operation fields, retry parent/attempt rules, same-operation retry rejection, and bounded-loop `iteration` preservation.
- Integrated pairing validation into `ReplayService.append_event()` for V3 operation events before flush.
- Preserved unresolved provenance for minimal/historical rows and returned paired provenance only when append-time validation proves the pair.

## Task Commits

1. **Task 1 RED: operation pairing tests** - `70a944a` (test)
2. **Task 1 GREEN: operation pairing validator** - `65b2ba2` (feat)
3. **Task 2 RED: replay service pairing integration tests** - `28d0262` (test)
4. **Task 2 GREEN: ReplayService pairing validation** - `72a527e` (feat)

## Files Created/Modified

- `src/replay/pairing.py` - Operation pairing and retry validation module.
- `src/replay/__init__.py` - Exports pairing validator/status types from the replay package.
- `src/replay/service.py` - Validates V3 operation candidates before append and projects explicit pairing provenance.
- `tests/replay/test_operation_pairing.py` - Focused pairing, retry, duplicate terminal, and bounded-loop iteration tests.
- `tests/replay/test_replay_service.py` - Service integration tests for paired terminal projection and unresolved minimal rows.
- `tests/replay/test_sequence_allocator.py` - Updated one V3 operation test fixture to include required operation identity and attempt.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py -q --tb=short` - PASS, 8 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/pairing.py tests/replay/test_operation_pairing.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_operation_pairing.py -q --tb=short` - PASS, 16 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/service.py tests/replay/test_replay_service.py tests/replay/test_operation_pairing.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay -q --tb=short` - PASS, 26 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q --tb=short` - PASS, 16 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay tests/replay` - PASS.

## Decisions Made

- Treated operation pairing as fail-closed for V3 operation lifecycle events: missing `operation_id`, missing/non-positive `attempt`, duplicate started reuse, duplicate terminal, and terminal-without-start all raise `OperationPairingError`.
- Kept historical/minimal rows unresolved unless pairing is proven by append-time validation context.
- Used `not_applicable` for non-operation events such as `approval_requested`, avoiding false unresolved signals for audit/lifecycle events that do not participate in operation pairing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing V3 operation fixture for stricter service validation**
- **Found during:** Task 2 (ReplayService integration)
- **Issue:** `tests/replay/test_sequence_allocator.py` had a V3 `tool_call_started` append without `operation_id` or `attempt`; once ReplayService enforced the Phase 15 operation contract, the broader replay suite correctly rejected it.
- **Fix:** Added a generated `operation_id` and `attempt=1` to that V3 operation fixture.
- **Files modified:** `tests/replay/test_sequence_allocator.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay -q --tb=short` passed.
- **Committed in:** `72a527e`

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** No scope creep; the fix aligns an existing test fixture with the stricter operation contract introduced by this plan.

## Issues Encountered

- A parallel verification attempt hit a PostgreSQL test setup race (`pg_type_typname_nsp_index`) while two pytest processes created the same test schema concurrently. Rerunning the plan command sequentially passed.

## Known Stubs

None. Stub scan found only intentional empty dictionaries in tests, not placeholder or unwired runtime behavior.

## TDD Gate Compliance

- RED commits are present before GREEN commits for both tasks.
- GREEN commits followed the RED commits and passed the focused tests.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 15-04. ReplayService now rejects invalid V3 operation lifecycle events before append and exposes explicit pairing provenance for Plan 15 lifecycle/finalizer and replay API work.

## Self-Check: PASSED

- Verified key files exist on disk.
- Verified task commit hashes exist in git history.
- No missing summary claims found.

---
*Phase: 15-replay-event-contract*
*Completed: 2026-06-16*
