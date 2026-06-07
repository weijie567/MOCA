---
phase: 08-knowledge-facade
plan: 08-06
subsystem: observability
tags: [knowledge-facade, evidence-ref, trace, agent-runs]

# Dependency graph
requires:
  - phase: 08-knowledge-facade
    provides: knowledge_search_result.v2 and canonical EvidenceRefV1 runtime state from 08-04
provides:
  - V2-aware evidence counts in trace summaries and run-step payloads
  - EvidenceRefV1 deduplication by canonical evidence_id
affects: [10-state-lifecycle-routing, 15-replay-event-contract, observability]

# Tech tracking
tech-stack:
  added: []
  patterns: [v2-first reporting reads with legacy fallback, evidence_id-first reporting dedupe]

key-files:
  created: []
  modified:
    - src/agent/trace.py
    - src/api/routers/agent_runs.py
    - tests/agent/test_trace.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "Reporting consumers prefer v2 evidence_refs while retaining legacy data.evidence fallback for historical runs."
  - "Run evidence deduplication uses evidence_id first, then chunk_id and deterministic JSON for legacy rows."

patterns-established:
  - "Observability consumers preserve public response fields while migrating their internal source shape."

requirements-completed: [KNOW-02]

# Metrics
duration: 24 min
completed: 2026-06-07
---

# Phase 8 Plan 6: Observability Consumer Migration Summary

**Trace summaries and run APIs now count v2 evidence references and preserve distinct policy versions through evidence_id-first deduplication**

## Performance

- **Duration:** 24 min
- **Started:** 2026-06-07T04:45:54Z
- **Completed:** 2026-06-07T05:10:02Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Migrated trace summary evidence counts to `knowledge_search_result.v2` `evidence_refs` with legacy stored-trace fallback.
- Migrated run-step evidence counts without changing the existing API response field.
- Changed run evidence deduplication to canonical `evidence_id`, preserving same-chunk references from distinct policy versions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate trace.py evidence_count to evidence_refs** - `9f7c551` (fix)
2. **Task 2: Migrate agent_runs.py evidence_count + dedupe key** - `e818546` (fix)

## Files Created/Modified

- `src/agent/trace.py` - Counts v2 evidence references in trace summaries with legacy fallback.
- `tests/agent/test_trace.py` - Covers v2 trace summary evidence counts.
- `src/api/routers/agent_runs.py` - Counts v2 run-step evidence and deduplicates canonical references by evidence ID.
- `tests/test_agent_runs_api.py` - Covers v2 step counts and version-distinct evidence retention.

## Decisions Made

- Preserved all existing response keys and changed only read-side derivation sources.
- Kept `data.evidence` and `chunk_id` fallbacks so historical stored runs continue to render.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The sandbox blocked the existing PostgreSQL-backed trace test from connecting to the local test database. Required suites were rerun with approved local-service access and passed.
- Concurrent plan 08-05 commits appeared during execution; its disjoint files and shared tracking files were left untouched.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q` - 2 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q` - 10 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_agent_runs_api.py -q` - 12 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q` - 273 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/trace.py src/api/routers/agent_runs.py tests/agent/test_trace.py tests/test_agent_runs_api.py` - passed.

## Known Stubs

None.

## Threat Flags

None - this plan changes reporting derivations only and adds no new trust boundary or attack surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 8 knowledge facade reporting consumers are migrated to the v2 evidence shape.
- No blockers remain for phase-level verification.

## Self-Check: PASSED

- All four owned implementation and test files exist.
- Both task commits exist.
- Focused and full test suites pass.
- Only the owned summary remains to be committed; shared planning files and untracked `CLAUDE.md` remain untouched.

---
*Phase: 08-knowledge-facade*
*Completed: 2026-06-07*
