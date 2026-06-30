---
phase: 31-memory-platform-boundary
plan: 31-03
subsystem: memory
tags: [memory, contextual-only, pydantic, service-facade, session-context]

requires:
  - phase: 31-01
    provides: RED tests for contextual-only memory DTOs and authority rejection
  - phase: 31-02
    provides: RED tests for reviewed memory context and write-decision metadata
provides:
  - Strict contextual-only memory ref/status/write-decision DTOs
  - SessionContextMemory and SessionContextBundle wrapper DTOs
  - Session context projection helper over the existing session memory bundle
  - MemoryContextService facade foundation over existing memory services
affects: [31-04, 31-05, 31-06, APF-09, APF-10]

tech-stack:
  added: []
  patterns:
    - Strict Pydantic DTOs with authority_class=contextual_only
    - Facade composition over existing memory services without storage renames
    - Target session_context wrapper projection preserving legacy SessionMemoryBundle storage names

key-files:
  created:
    - src/memory/context_refs.py
    - src/memory/context_service.py
    - .planning/phases/31-memory-platform-boundary/31-03-SUMMARY.md
  modified:
    - src/memory/schemas.py
    - src/memory/session_bundle.py
    - src/memory/__init__.py
    - src/agent/rag_context/verifier.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "SessionContextMemory is a distinct target wrapper DTO, not a direct alias, because Wave 0 tests require session_context_bundle.v1."
  - "MemoryContextService.load_reviewed_memory_context intentionally returns an empty not_implemented_in_facade bundle until Plan 31-05 wires trusted-scope retrieval."
  - "The existing verifier now treats Phase 31 contextual memory ref/status buckets as memory non-authority sources."

patterns-established:
  - "Contextual-only DTO module: memory refs/status refs live in src.memory.context_refs and avoid evidence/business/approval/replay imports."
  - "Facade skeleton: MemoryContextService composes SessionMemoryBundleService, LongTermMemoryService, and CaseMemoryService without direct repository queries."
  - "Projection helper: project_session_context_memory converts SessionMemoryBundle into a JSON-safe session_context_bundle.v1 wrapper."

requirements-completed: [APF-09, APF-10]

duration: 10min
completed: 2026-06-28
---

# Phase 31 Plan 03: Memory Context DTOs and Facade Summary

**Contextual-only memory DTOs, SessionContextMemory projection, and a MemoryContextService facade foundation over existing memory services.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-28T06:11:13Z
- **Completed:** 2026-06-28T06:20:50Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added strict contextual-only DTOs for `SessionContextRef`, `ReviewedMemoryRef`, session/reviewed retrieve status refs, reviewed memory bundles, and `MemoryWriteDecisionV2`.
- Added `SessionContextMemory` / `SessionContextBundle` wrapper DTOs and `project_session_context_memory(...)` over the existing `SessionMemoryBundle`.
- Added `MemoryContextService` with session-context delegation, reviewed-memory placeholder bundle, and pure memory write decision projection.
- Preserved all existing storage names, repository ownership, migrations, and legacy `SessionMemoryBundle` contracts.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement strict contextual-only memory DTOs and exports** - `0d4de94` (feat)
2. **Task 2: Add SessionContextMemory projection and MemoryContextService facade** - `4a74254` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/memory/context_refs.py` - Strict contextual-only memory refs, status refs, reviewed bundle, and write decision DTOs.
- `src/memory/context_service.py` - Facade skeleton over session bundle, long-term memory, and case memory services.
- `src/memory/schemas.py` - `SessionContextMemory` and `SessionContextBundle` target wrapper DTOs.
- `src/memory/session_bundle.py` - `project_session_context_memory(...)` JSON-safe projection helper.
- `src/memory/__init__.py` - Public exports for new DTOs, projection helper, and facade.
- `src/agent/rag_context/verifier.py` - Recognizes Phase 31 contextual memory buckets as non-authority memory sources.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records the handled invalid parallel DB-backed pytest run.

## Decisions Made

- Used wrapper DTOs instead of aliases for `SessionContextMemory` because the RED tests require target `session_context_bundle.v1` output while preserving `session_memory_bundle.v1`.
- Kept reviewed memory retrieval empty and fail-closed in 31-03; trusted-scope retrieval remains owned by Plan 31-05.
- Kept the verifier change narrow: only the existing contextual-source helper was extended for Phase 31 memory bucket names.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Contract Compatibility] Normalized RED-test compatibility inputs while preserving target bundle shape**
- **Found during:** Task 1
- **Issue:** The 31-01 RED tests used `SessionContextRef.source == "session_context_load"`, `retrieve_status`, and a legacy non-semantic `tenant_id` key on `ReviewedMemoryContextBundle`, while 31-03 specified target `status_ref` and strict contextual DTOs.
- **Fix:** Allowed `session_context_load` as a contextual session ref source, accepted `retrieve_status` as a validation alias for `status_ref`, and dropped the legacy bundle `tenant_id` before strict validation so serialized bundles stay target-shaped.
- **Files modified:** `src/memory/context_refs.py`
- **Verification:** `uv run pytest tests/memory/test_context_refs.py tests/agent/test_memory_evidence_boundary.py -q` passed serially.
- **Committed in:** `0d4de94`

**2. [Rule 2 - Missing Critical] Added verifier recognition for Phase 31 contextual memory buckets**
- **Found during:** Task 1 verification
- **Issue:** The verifier already rejected memory as authority for legacy `session_memory`, `case_memory`, and `prior_summaries`, but did not emit memory non-authority reason codes for new `session_context_refs`, `reviewed_memory_refs`, and `memory_status_refs`.
- **Fix:** Extended `_contextual_source_reason_codes(...)` to classify the new Phase 31 buckets as memory sources.
- **Files modified:** `src/agent/rag_context/verifier.py`
- **Verification:** `uv run pytest tests/memory/test_context_refs.py tests/agent/test_memory_evidence_boundary.py -q` passed serially.
- **Committed in:** `0d4de94`

---

**Total deviations:** 2 auto-fixed (1 contract compatibility, 1 missing critical authority-boundary recognition).
**Impact on plan:** Both changes preserve the memory contextual-only boundary and do not rename storage contracts or broaden retrieval.

## Issues Encountered

- I initially ran two DB-backed pytest commands in parallel, which invalidly collided on the shared `moca_test` schema setup. This was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`; the same commands were rerun serially and passed.
- Existing LangGraph deprecation/config warnings appeared during focused tests; they are pre-existing and non-blocking.

## Known Stubs

None. Stub scan found normal optional fields/default factories only. The `not_implemented_in_facade` reviewed-memory fallback is intentional 31-03 scope and is explicitly replaced by Plan 31-05.

## Threat Flags

None. New security-relevant memory DTO/facade/verifier surfaces are covered by the plan threat model (`T-31-authority-forgery`, `T-31-pii-leakage`, `T-31-cross-merchant`, `T-31-write-rollback`); no endpoints, auth paths, migrations, or direct repository ownership were added.

## Authentication Gates

None.

## Verification

- `uv run pytest tests/memory/test_context_refs.py tests/agent/test_memory_evidence_boundary.py -q` - passed serially (`21 passed`, 3 existing warnings).
- `uv run pytest tests/memory/test_context_refs.py tests/memory/test_session_memory_bundle.py -q` - passed serially (`16 passed`, 1 existing warning).
- `uv run ruff check src/memory/context_refs.py src/memory/context_service.py src/memory/schemas.py src/memory/session_bundle.py src/memory/__init__.py src/agent/rag_context/verifier.py tests/memory/test_context_refs.py tests/memory/test_session_memory_bundle.py tests/agent/test_memory_evidence_boundary.py` - passed.
- `rg -n "EvidenceRefV1|BusinessFactRefV1|ApprovalRequestCreateCommand|ReplayEventV3|MaterialClaim" src/memory/context_refs.py` - no matches.
- `git diff --name-only 0d4de94^..HEAD -- src/db/migrations src/db/models.py` - no storage model or migration changes.
- `git diff --check` - passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 31-04 can wire `session_context_load` and AgentState target fields using the new projection/facade. Plan 31-05 can replace the reviewed-memory placeholder with trusted-scope retrieval without changing storage names.

---
*Phase: 31-memory-platform-boundary*
*Completed: 2026-06-28*

## Self-Check: PASSED

- Found summary file at `.planning/phases/31-memory-platform-boundary/31-03-SUMMARY.md`.
- Found key files `src/memory/context_refs.py`, `src/memory/context_service.py`, `src/memory/schemas.py`, `src/memory/session_bundle.py`, `src/memory/__init__.py`, `src/agent/rag_context/verifier.py`, and `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Found task commits `0d4de94` and `4a74254` in git history.
- No unexpected tracked file deletions were detected in task commits.
- Shared `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` were not updated by this executor.
