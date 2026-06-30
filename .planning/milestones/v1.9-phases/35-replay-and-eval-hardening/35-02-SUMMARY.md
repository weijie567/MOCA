---
phase: 35-replay-and-eval-hardening
plan: 35-02
subsystem: replay-trace-permissions
tags: [replay, trace, authorization, pytest, pydantic]

requires:
  - phase: 35-01
    provides: "Phase 35 coverage matrix and replay/eval contract inventory"
provides:
  - "Replay-safe authorization proof projection for future same-merchant authorization work"
  - "Phase 35 owner/admin-only trace, replay, and AgentRun permission regression tests"
  - "Static guard coverage proving proof fields and requested_by merchant data remain non-authorizing"
affects: [phase35, replay, trace, agent-runs, APF-17]

tech-stack:
  added: []
  patterns:
    - "Projection-only proof helper returning counts/status/source without raw business identifiers"
    - "Phase-specific static/API permission regression suite"

key-files:
  created:
    - src/replay/proof_projection.py
    - tests/replay/test_phase35_trace_replay_permissions.py
  modified:
    - tests/agent/test_trace.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Replay authorization proof is projection-only evidence and is not wired into trace, replay, or AgentRun authorization guards."
  - "Phase 35 keeps business-data run/trace/replay/status/evidence/stream access closed to owner/admin visibility, with stream execution still owner-only."
  - "Approval views, tool result records, memory, trace detail, run listing, and replay artifacts are tracked as unchanged non-widening regression surfaces."

patterns-established:
  - "project_replay_authorization_proof validates BusinessFactRefV1 and BusinessFactResultV1 dictionaries before counting proof."
  - "Phase 35 permission tests inspect guard source for target merchant, proof, proof_status, and requested_by merchant shortcuts."

requirements-completed: [APF-17]

duration: 23 min
completed: 2026-06-29
---

# Phase 35 Plan 35-02: Trace/Replay Proof and Permission Hardening Summary

**Replay-safe proof status projection plus owner/admin-only trace, replay, and AgentRun permission regressions**

## Performance

- **Duration:** 23 min
- **Started:** 2026-06-29T14:51:40Z
- **Completed:** 2026-06-29T15:14:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `project_replay_authorization_proof()` with exact `replay_authorization_proof.v1` keys, strict business fact validation, fail-closed status values, and no raw business/user payload exposure.
- Added Phase 35 permission regressions proving owner/admin-only trace/replay/status/evidence visibility, cross-tenant 404s, same-tenant non-owner 403s, and same-merchant manager 403 even with valid replay proof.
- Added static guard checks proving `target_merchant_context`, `project_replay_authorization_proof`, `proof_status`, and `requested_by.*merchant` shortcuts are not used by Phase 35 authorization guards.

## Task Commits

1. **Task 1 RED: Replay proof projection tests** - `7508657` (`test`)
2. **Task 1 GREEN: Replay proof projection helper** - `325ee22` (`feat`)
3. **Task 2 RED: Phase 35 permission regression gate** - `cc2b92c` (`test`)
4. **Task 2 GREEN: Owner/admin-only permission regressions** - `fa64e57` (`test`)

## Files Created/Modified

- `src/replay/proof_projection.py` - Projection-only replay authorization proof helper with fail-closed status/source/count output.
- `tests/agent/test_trace.py` - Unit tests for proof projection status, source, strict validation, and raw-payload exclusion.
- `tests/replay/test_phase35_trace_replay_permissions.py` - Static/API permission regression tests for trace, replay, AgentRun, and unchanged adjacent surfaces.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese local validation record for the Task 1 test helper-order collection failure.

## Decisions Made

- Proof projection remains evidence for later phases only; no API authorization guard consumes it in Phase 35.
- Same-merchant manager trace/replay/run visibility remains denied until a later phase explicitly opens it with stable proof-chain authorization.
- Existing approval/tool/memory regression files are referenced as unchanged non-widening surfaces instead of broadening this plan into those ownership domains.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed proof projection test helper order**
- **Found during:** Task 1 GREEN
- **Issue:** The first GREEN run failed during pytest collection because `pytest.mark.parametrize` evaluated `_business_fact_result(...)` before the helper was defined.
- **Fix:** Moved `_business_fact_ref` and `_business_fact_result` above their first parameterized use and recorded the validation issue in Chinese.
- **Files modified:** `tests/agent/test_trace.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q --tb=short` passed with `23 passed, 1 warning`.
- **Committed in:** `325ee22`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was limited to test structure and required validation logging. Production authorization behavior was unchanged.

## Issues Encountered

- Task 1 GREEN initially hit the helper-order collection error described above.
- Task 2 used an explicit RED placeholder before replacing it with the full Phase 35 regression suite; this was expected TDD flow, not an implementation issue.
- During metadata updates, `gsd-sdk query roadmap.update-plan-progress 35` returned `updated: false` for the current ROADMAP format; ROADMAP/STATE were patched manually and the local issue was recorded.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q --tb=short` - passed (`23 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/proof_projection.py tests/agent/test_trace.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_trace_replay_permissions.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/test_approval_api.py -q --tb=short` - passed (`101 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/replay/test_phase35_trace_replay_permissions.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/test_approval_api.py` - passed
- Plan-level pytest: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_trace_replay_permissions.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_trace.py -q --tb=short` - passed (`94 passed, 1 warning`)
- Plan-level ruff: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay/proof_projection.py tests/replay/test_phase35_trace_replay_permissions.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_trace.py` - passed
- Acceptance `rg` probes for proof symbols, permission guard shortcut absence, and Phase 35 surface coverage rows - passed.

## Known Stubs

None. Stub-pattern scan found no matches in `src/replay/proof_projection.py`, `tests/agent/test_trace.py`, or `tests/replay/test_phase35_trace_replay_permissions.py`.

## Threat Flags

None. The new security-relevant surface is the planned projection helper from the threat model; no new endpoint, auth path, file access pattern, or schema trust boundary was introduced.

## TDD Gate Compliance

- Task 1 RED gate: `7508657` added failing proof projection tests before `src/replay/proof_projection.py` existed.
- Task 1 GREEN gate: `325ee22` added the projection helper and made the focused tests pass.
- Task 2 RED gate: `cc2b92c` added a failing Phase 35 permission regression gate.
- Task 2 GREEN gate: `fa64e57` replaced the RED gate with static/API regressions and made the focused suite pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `35-03-PLAN.md`. Plan 35-02 leaves trace/replay/AgentRun authorization closed to owner/admin and provides projection-only proof evidence for future same-merchant authorization planning.

## Self-Check: PASSED

- Found created files: `src/replay/proof_projection.py`, `tests/replay/test_phase35_trace_replay_permissions.py`, and `.planning/phases/35-replay-and-eval-hardening/35-02-SUMMARY.md`.
- Found task commits: `7508657`, `325ee22`, `cc2b92c`, and `fa64e57`.
- Final plan-level pytest and ruff verification passed.

---
*Phase: 35-replay-and-eval-hardening*
*Completed: 2026-06-29*
