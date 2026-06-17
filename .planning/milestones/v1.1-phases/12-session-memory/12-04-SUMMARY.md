---
phase: 12-session-memory
plan: "04"
subsystem: testing
tags: [session-memory, concurrency, isolation, evidence-boundary, langgraph]
requires:
  - phase: 12-session-memory
    plan: "01"
    provides: "PostgreSQL session_memories schema, repository, and CAS-capable MemoryService"
  - phase: 12-session-memory
    plan: "02"
    provides: "Trusted same-thread session_memory_load and resolved active_slots"
  - phase: 12-session-memory
    plan: "03"
    provides: "Post-response memory_write finalizer and API/SSE scheduling hooks"
provides:
  - "Async CAS and deterministic merge regression matrix for same-thread writes"
  - "Tenant, user, thread, freshness, compatibility, and explicit override inheritance tests"
  - "Graph continuity coverage for missing-slot carryover, inherited slots, and disabled/unavailable fallback"
  - "Negative evidence/action-authority boundary tests for session memory"
  - "Focused Phase 12 PostgreSQL-only verification with no Redis dependency"
affects: [phase-12, phase-15-replay, phase-16-memory, phase-13-approval, phase-14-actions]
tech-stack:
  added: []
  patterns:
    - "Session memory safety is enforced through focused async service tests plus graph-level continuity regressions."
    - "Session memory remains contextual continuity only; policy evidence, approval, and action authority stay owned by their dedicated services."
key-files:
  created:
    - tests/memory/test_session_memory_concurrency.py
    - tests/memory/test_session_memory_isolation.py
    - tests/agent/test_session_memory_integration.py
    - tests/agent/test_memory_evidence_boundary.py
  modified:
    - tests/agent/test_required_slots.py
    - src/agent/nodes/memory_write.py
key-decisions:
  - "Phase 12 remains PostgreSQL-only; Redis is not required for correctness and was not introduced."
  - "Conflicting current-turn explicit slots must return conflict/fallback behavior instead of silent precedence."
  - "Session memory candidates skip evidence, approval, proposed action, action result, risk decision, raw prompt, and raw tool payload fields."
patterns-established:
  - "Memory continuity tests exercise both DB-backed MemoryService behavior and graph fake-LLM/tool seams."
  - "Static boundary checks guard against accidental EvidenceRefV1 coupling in memory modules."
requirements-completed:
  - SESSION-01
  - SESSION-02
  - SESSION-03
duration: 17 min
completed: 2026-06-14
---

# Phase 12 Plan 04: Safety Matrix Summary

**PostgreSQL-only session memory safety matrix covering CAS merge behavior, scope isolation, graph continuity, fallback, PII blocking, and evidence/action authority boundaries**

## Performance

- **Duration:** 17 min
- **Started:** 2026-06-14T09:55:39Z
- **Completed:** 2026-06-14T10:12:03Z
- **Tasks:** 5
- **Files modified:** 6

## Accomplishments

- Added async CAS/concurrency tests proving non-conflicting same-thread writes merge required fields and explicit slot conflicts do not silently overwrite.
- Added tenant/user/thread isolation, expired/incompatible slot filtering, malformed metadata fail-closed checks, and current-turn explicit override coverage.
- Added graph continuity regressions for same-thread inherited slots, unresolved-question carryover, cross-scope clarification, disabled fallback, and unavailable-service fallback.
- Added negative tests proving session memory cannot populate policy evidence, recommendation citations, approval/action results, proposed actions, or action authorization.
- Proved PII/prohibited/raw payload memory write candidates are skipped or excluded, and verified no Redis dependency exists in Phase 12-owned paths.

## Task Commits

1. **Task 0: Add CAS and deterministic merge concurrency tests** - `ef83275` (`test(12-04)`)
2. **Task 1: Add scope isolation and stale slot matrix** - `72991c9` (`test(12-04)`)
3. **Task 2: Add graph/API same-thread continuity and fallback regressions** - `adec789` (`test(12-04)`)
4. **Task 3: Add memory-is-not-evidence/action-authority negative tests** - `9c66ba3` (`test(12-04)`)
5. **Task 4: Run focused Phase 12 verification and fix narrow failures** - no code changes required; all focused checks passed.

## Files Created/Modified

- `tests/memory/test_session_memory_concurrency.py` - Covers async same-thread safe merge, explicit slot conflict, stale-version merge, scalar merge warnings, and business-ref conflict behavior.
- `tests/memory/test_session_memory_isolation.py` - Covers same-scope positive inheritance plus cross-thread, cross-user, cross-tenant, expired, and incompatible fallback behavior.
- `tests/agent/test_session_memory_integration.py` - Covers graph continuity, unresolved-question carryover, cross-scope fallback, disabled memory, and unavailable memory service behavior.
- `tests/agent/test_memory_evidence_boundary.py` - Covers static evidence-boundary checks, memory_write candidate exclusions, PII skip behavior, and no-evidence/no-action authority paths.
- `tests/agent/test_required_slots.py` - Adds malformed expiry, missing/incompatible intent metadata, and explicit current-turn override regressions.
- `src/agent/nodes/memory_write.py` - Removes an unused static reference that mentioned `EvidenceRefV1`, preserving the no-evidence-coupling boundary.

## Decisions Made

- Redis was deliberately not introduced because the PostgreSQL-only implementation passes the Phase 12 safety matrix.
- Session memory is allowed to carry context only inside same tenant/user/thread scope and only when freshness and intent metadata validate.
- Current-turn explicit slots remain authoritative over inherited slots, while conflicting concurrent explicit slots are treated as conflicts rather than deterministic overwrites.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Verification

- `uv run pytest tests/memory tests/agent/test_session_memory_load.py tests/agent/test_memory_write_node.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_memory_evidence_boundary.py -q --tb=short` -> 39 passed, 1 warning.
- `uv run pytest tests/agent/test_graph.py tests/test_agent_runs_api.py tests/agent/test_events.py -q --tb=short` -> 44 passed, 1 warning.
- `uv run ruff check src/memory src/agent/nodes/session_memory_load.py src/agent/nodes/memory_write.py src/agent/routing.py tests/memory tests/agent/test_session_memory_load.py tests/agent/test_memory_write_node.py tests/agent/test_session_memory_integration.py tests/agent/test_memory_evidence_boundary.py` -> passed.
- `rg -n "redis|Redis" src/memory src/agent/nodes/session_memory_load.py src/agent/nodes/memory_write.py` -> no matches.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

12-05 can make the Redis evaluation decision. The safety matrix proves the authoritative PostgreSQL path is complete without Redis, so the default Phase 12 posture can remain "skip optional cache work" unless Redis is explicitly accepted later.

---
*Phase: 12-session-memory*
*Completed: 2026-06-14*
