---
phase: 33-rag-context-build-and-claim-verification
plan: 33-08
subsystem: api
tags: [rag, trace, replay, sse, safe-projection, tdd]

requires:
  - phase: 33-07
    provides: safe final/working projection no-leak behavior for RAG and claim verification state
provides:
  - rag_claim_summary.v1 allowlisted summary projection
  - trace, SSE, trace API, and replay-safe RAG/claim count/status exposure
  - replay payload sanitization for raw RAG package and claim verifier internals
affects: [agent-trace, agent-runs-api, trace-api, replay-api, phase-33]

tech-stack:
  added: []
  patterns:
    - dependency-free safe projection helper shared by agent trace, API, repository, and replay layers
    - optional response fields dumped with exclude_none so legacy runs omit absent Phase 33 summaries

key-files:
  created:
    - src/agent/rag_claim_summary.py
  modified:
    - src/agent/trace.py
    - src/api/routers/agent.py
    - src/api/routers/agent_runs.py
    - src/api/routers/traces.py
    - src/api/schemas/agent.py
    - src/api/schemas/agent_runs.py
    - src/api/schemas/approvals.py
    - src/replay/schemas.py
    - src/replay/service.py
    - src/repositories/trace_repo.py
    - tests/agent/test_trace.py
    - tests/test_agent_runs_api.py
    - tests/test_trace_api.py
    - tests/replay/test_replay_api.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Centralized rag_claim_summary.v1 in src/agent/rag_claim_summary.py to avoid replay lifecycle import cycles and keep projection logic consistent."
  - "Replay responses sanitize raw package/bundle/debug/verifier fields at projection time and return only the allowlisted summary."
  - "Legacy/no Phase 33 responses use exclude_none so rag_claim_summary is omitted instead of fabricated with zero counts."

patterns-established:
  - "Safe projection helpers must consume state/metrics/replay payloads through explicit allowlists rather than passing persisted dictionaries through."
  - "Metrics-only persisted traces may use stored count fields when raw evidence maps are intentionally absent."

requirements-completed: [APF-13, APF-14]

duration: 28m
completed: 2026-06-28
---

# Phase 33 Plan 08: Trace And API Safe RAG/Claim Summaries Summary

**Allowlisted `rag_claim_summary.v1` counts/statuses across trace, SSE, trace API, and replay without exposing raw RAG package or verifier internals**

## Performance

- **Duration:** 28m
- **Started:** 2026-06-28T20:37:51Z
- **Completed:** 2026-06-28T21:06:07Z
- **Tasks:** 1
- **Files modified:** 16 implementation/test/support files

## Accomplishments

- Added `rag_claim_summary.v1` with exactly the planned keys: status fields plus verified/rejected/stale/conflict/blocked/safe-support counts.
- Exposed the summary from `build_trace_summary`, SSE run events, persisted trace API responses, and replay responses.
- Sanitized replay event payloads so raw `verified_evidence_package`, `claim_verification_bundle`, debug/verifier projections, OCR/source internals, and candidate-only refs are not returned.
- Added cross-tenant/unauthorized API assertions proving summary counts/statuses are not visible outside existing run visibility scope.

## Task Commits

1. **Task 33-08-01 RED:** `3cc15d0` (`test`) - failing coverage for trace, SSE, trace API, replay, legacy omission, and unauthorized no-leak behavior.
2. **Task 33-08-01 GREEN:** `ca0589d` (`feat`) - implementation of shared safe projection helper, endpoint wiring, replay sanitization, schemas, and validation log entry.

_Note: This task used TDD and therefore has separate RED and GREEN commits._

## Files Created/Modified

- `src/agent/rag_claim_summary.py` - Shared allowlisted summary builder and replay payload sanitizer.
- `src/agent/trace.py` - Adds `rag_claim_summary` to trace summaries when Phase 33 state/metrics exist.
- `src/api/routers/agent_runs.py` - Adds safe summary to SSE payloads while preserving `ADMIN_RUN_VISIBILITY_ROLES = {"admin"}`.
- `src/api/routers/traces.py` - Adds persisted trace summary after tenant-scoped lookup and owner/admin guard.
- `src/repositories/trace_repo.py` - Builds summaries from persisted `AgentStep.metrics_json`.
- `src/replay/service.py` and `src/replay/schemas.py` - Adds top-level replay summary and sanitizes replay event payloads.
- `src/api/schemas/*.py` - Adds optional summary fields and omits absent legacy summaries.
- `tests/agent/test_trace.py`, `tests/test_agent_runs_api.py`, `tests/test_trace_api.py`, `tests/replay/test_replay_api.py` - TDD coverage for safe keys, raw-key omission, unauthorized no-leak behavior, and legacy omission.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records handled GREEN validation failures per MOCA project rule.

## Decisions Made

- Used a new dependency-free helper module instead of placing projection logic in `src/agent/trace.py`; replay imports this helper without pulling in replay lifecycle dependencies.
- Replay sanitization happens at projection time so existing stored rows can be rendered safely without a data migration.
- `safe_support_ref_count` uses verified evidence IDs when raw package data is available, and trusts stored metrics counts when persisted traces intentionally contain counts only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved summary helper out of `src/agent/trace.py`**
- **Found during:** Task 33-08-01 GREEN verification
- **Issue:** Importing summary helpers from `src.agent.trace` in replay service created a replay lifecycle import cycle.
- **Fix:** Created `src/agent/rag_claim_summary.py` and imported that helper from trace, API, repository, and replay layers.
- **Files modified:** `src/agent/rag_claim_summary.py`, `src/agent/trace.py`, `src/api/routers/agent_runs.py`, `src/repositories/trace_repo.py`, `src/replay/service.py`
- **Verification:** Focused suite passed after fix.
- **Committed in:** `ca0589d`

**2. [Rule 2 - Missing Critical Compatibility] Extended shared chat trace schema**
- **Found during:** Task 33-08-01 implementation
- **Issue:** `build_trace_summary()` is shared by `/agent/chat`; adding a summary there required the strict chat trace schema to preserve the safe field and omit it for legacy responses.
- **Fix:** Added optional `rag_claim_summary` to `TraceSummary` and used `exclude_none=True` for chat response dumps.
- **Files modified:** `src/api/schemas/agent.py`, `src/api/routers/agent.py`
- **Verification:** Focused suite and ruff passed.
- **Committed in:** `ca0589d`

**3. [Rule 3 - Blocking] Updated stale trace test expectation**
- **Found during:** Task 33-08-01 RED verification
- **Issue:** Existing `rag_context_build` graph projection expectation still described the node as deferred/non-runnable, but the current repository already projects it as runtime/runnable.
- **Fix:** Updated the stale expectation so RED isolated the intended missing `rag_claim_summary` behavior.
- **Files modified:** `tests/agent/test_trace.py`
- **Verification:** RED suite then failed only on the planned missing summary assertions.
- **Committed in:** `3cc15d0`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 missing critical compatibility)
**Impact on plan:** All changes are directly required for the planned safe summary to work across existing surfaces. No new endpoint or visibility model was introduced.

## Issues Encountered

- GREEN verification initially failed on an import cycle and two summary assertions. The handled details and commands were appended in Chinese to `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Metadata update hit the known Phase 33 `roadmap.update-plan-progress` checkbox mismatch; ROADMAP/STATE were manually aligned to 8/9 and the issue was logged.
- The focused test suite still emits an existing LangGraph checkpointer serializer deprecation warning; it does not affect this plan.

## Verification

Passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_projects_allowlisted_rag_claim_summary_in_step_payload tests/test_trace_api.py::test_get_run_trace_exposes_allowlisted_rag_claim_summary_from_scoped_run -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py -q --tb=short
uv run ruff check src/agent/trace.py src/agent/rag_claim_summary.py src/api/routers/agent.py src/api/routers/agent_runs.py src/api/routers/traces.py src/api/schemas/agent.py src/api/schemas/agent_runs.py src/api/schemas/approvals.py src/repositories/trace_repo.py src/replay/service.py src/replay/schemas.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py
git diff --check
rg -n "rag_claim_summary\\.v1|verified_evidence_count|rejected_candidate_count|claim_verification_status|blocked_claim_count|safe_support_ref_count" src/agent/trace.py src/agent/rag_claim_summary.py src/api/routers/agent_runs.py src/api/routers/traces.py src/repositories/trace_repo.py src/replay/service.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py
rg -n "ADMIN_RUN_VISIBILITY_ROLES = \\{\"admin\"\\}" src/api/routers/agent_runs.py src/api/routers/traces.py
```

Final focused suite result: `89 passed, 1 warning`.

## TDD Gate Compliance

- RED gate commit exists: `3cc15d0`.
- GREEN gate commit exists after RED: `ca0589d`.
- No separate refactor commit was needed.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 33-08 is ready for Plan 33-09 final static and focused phase gates. The safe summary helper is centralized and should be reused by any future Phase 33 trace/replay projection surfaces.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/33-rag-context-build-and-claim-verification/33-08-SUMMARY.md`
- Task commit found: `3cc15d0`
- Task commit found: `ca0589d`

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-28*
